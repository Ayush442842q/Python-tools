#!/usr/bin/env python3
"""
PDF Metadata Extractor - A utility to inspect PDF file structures and extract
document metadata (e.g. Title, Author, Creation Date, Producer) and XMP metadata streams.
"""

import argparse
import sys
import os
import re
import zlib

def tokenize_pdf(data):
    """Tokenizes PDF bytes into structural elements, strings, numbers, and names."""
    tokens = []
    i = 0
    n = len(data)
    while i < n:
        # Skip PDF whitespace
        while i < n and data[i:i+1] in b' \t\r\n\x00\x0c':
            i += 1
        if i >= n:
            break
            
        char = data[i:i+1]
        
        # Literal string (...)
        if char == b'(':
            start = i
            depth = 1
            i += 1
            while i < n and depth > 0:
                if data[i:i+1] == b'\\' and i + 1 < n:
                    i += 2  # skip escaped character
                elif data[i:i+1] == b'(':
                    depth += 1
                    i += 1
                elif data[i:i+1] == b')':
                    depth -= 1
                    i += 1
                else:
                    i += 1
            tokens.append(data[start:i])
            
        # Hex string <...> or dictionary <<
        elif char == b'<':
            if i + 1 < n and data[i+1:i+2] == b'<':
                tokens.append(b'<<')
                i += 2
            else:
                # Scan to closing '>'
                start = i
                i += 1
                while i < n and data[i:i+1] != b'>':
                    i += 1
                if i < n:
                    i += 1
                tokens.append(data[start:i])
                
        # Array [ ]
        elif char == b'[':
            tokens.append(b'[')
            i += 1
        elif char == b']':
            tokens.append(b']')
            i += 1
            
        # Dictionary >> or single >
        elif char == b'>':
            if i + 1 < n and data[i+1:i+2] == b'>':
                tokens.append(b'>>')
                i += 2
            else:
                tokens.append(b'>')
                i += 1
                
        # Name /Name
        elif char == b'/':
            start = i
            i += 1
            # Read until delimiter
            while i < n and data[i:i+1] not in b' \t\r\n\x00\x0c/()<>[]{}%':
                i += 1
            tokens.append(data[start:i])
            
        # Other identifiers/numbers
        else:
            start = i
            while i < n and data[i:i+1] not in b' \t\r\n\x00\x0c/()<>[]{}%':
                i += 1
            tokens.append(data[start:i])
            
    return tokens

def parse_pdf_string(val_bytes):
    """Parses PDF literal/hex strings and decodes them, handling UTF-16BE BOM and backslash escapes."""
    if val_bytes.startswith(b'(') and val_bytes.endswith(b')'):
        # Literal string
        content = val_bytes[1:-1]
        escaped = []
        i = 0
        n = len(content)
        while i < n:
            if content[i:i+1] == b'\\' and i + 1 < n:
                next_char = content[i+1:i+2]
                if next_char == b'n':
                    escaped.append(b'\n')
                    i += 2
                elif next_char == b'r':
                    escaped.append(b'\r')
                    i += 2
                elif next_char == b't':
                    escaped.append(b'\t')
                    i += 2
                elif next_char == b'b':
                    escaped.append(b'\b')
                    i += 2
                elif next_char == b'f':
                    escaped.append(b'\f')
                    i += 2
                elif next_char in (b'(', b')', b'\\'):
                    escaped.append(next_char)
                    i += 2
                elif next_char.isdigit():
                    # Octal escape sequence (up to 3 octal digits)
                    octal_digits = []
                    j = 1
                    while j <= 3 and i + j < n and content[i+j:i+j+1].isdigit():
                        octal_digits.append(content[i+j:i+j+1])
                        j += 1
                    octal_str = b"".join(octal_digits)
                    try:
                        val = int(octal_str, 8)
                        escaped.append(bytes([val]))
                    except ValueError:
                        escaped.append(content[i:i+j])
                    i += j
                else:
                    escaped.append(next_char)
                    i += 2
            else:
                escaped.append(content[i:i+1])
                i += 1
        decoded_bytes = b"".join(escaped)
        if decoded_bytes.startswith(b'\xfe\xff'):
            try:
                return decoded_bytes[2:].decode('utf-16-be')
            except Exception:
                pass
        try:
            return decoded_bytes.decode('utf-8')
        except UnicodeDecodeError:
            return decoded_bytes.decode('latin-1')

    elif val_bytes.startswith(b'<') and val_bytes.endswith(b'>'):
        # Hex string
        hex_content = val_bytes[1:-1].replace(b' ', b'').replace(b'\r', b'').replace(b'\n', b'')
        if len(hex_content) % 2 != 0:
            hex_content += b'0'
        try:
            decoded_bytes = bytes.fromhex(hex_content.decode('ascii'))
            if decoded_bytes.startswith(b'\xfe\xff'):
                return decoded_bytes[2:].decode('utf-16-be')
            try:
                return decoded_bytes.decode('utf-8')
            except UnicodeDecodeError:
                return decoded_bytes.decode('latin-1')
        except Exception:
            return hex_content.decode('latin-1', errors='ignore')
            
    return val_bytes.decode('utf-8', errors='ignore')

def parse_pdf_date(date_str):
    """Converts a PDF D:YYYYMMDDHHmmSS timezone string to a human-readable date format."""
    if not date_str:
        return date_str
    if date_str.startswith("D:"):
        date_str = date_str[2:]
    
    # Match YYYY MM DD HH mm SS
    match = re.match(r'^(\d{4})(\d{2})?(\d{2})?(\d{2})?(\d{2})?(\d{2})?(.*)$', date_str)
    if not match:
        return date_str
    
    parts = list(match.groups())
    year = parts[0]
    month = parts[1] or "01"
    day = parts[2] or "01"
    hour = parts[3] or "00"
    minute = parts[4] or "00"
    second = parts[5] or "00"
    tz = parts[6] or ""
    
    tz = tz.replace("'", "")
    if tz == "Z":
        tz = " UTC"
    elif tz:
        if len(tz) >= 5 and (tz[0] == '+' or tz[0] == '-'):
            tz = f" {tz[0]}{tz[1:3]}:{tz[3:5]}"
            
    return f"{year}-{month}-{day} {hour}:{minute}:{second}{tz}"

def find_object_dict(data, obj_id, gen_id):
    """Scans binary data to locate and extract the dictionary block of a specific PDF object."""
    pattern = re.compile(rb'\b' + re.escape(obj_id) + rb'\s+' + re.escape(gen_id) + rb'\s+obj\b')
    match = pattern.search(data)
    if not match:
        return None
    
    start_pos = match.end()
    dict_start = data.find(b'<<', start_pos)
    if dict_start == -1:
        return None
        
    pos = dict_start + 2
    depth = 1
    while pos < len(data) and depth > 0:
        next_open = data.find(b'<<', pos)
        next_close = data.find(b'>>', pos)
        
        if next_open == -1 and next_close == -1:
            break
            
        if next_open != -1 and (next_close == -1 or next_open < next_close):
            depth += 1
            pos = next_open + 2
        else:
            depth -= 1
            pos = next_close + 2
            
    if depth == 0:
        return data[dict_start + 2 : pos - 2]
    return None

def extract_stream(data, obj_id, gen_id, dictionary_bytes):
    """Extracts and decompresses stream content if compressed via FlateDecode."""
    pattern = re.compile(rb'\b' + re.escape(obj_id) + rb'\s+' + re.escape(gen_id) + rb'\s+obj\b')
    match = pattern.search(data)
    if not match:
        return None
    
    start_pos = match.end()
    stream_kw = data.find(b'stream', start_pos)
    if stream_kw == -1:
        return None
        
    if data[stream_kw + 6 : stream_kw + 8] == b'\r\n':
        stream_start = stream_kw + 8
    elif data[stream_kw + 6 : stream_kw + 7] == b'\n':
        stream_start = stream_kw + 7
    else:
        stream_start = stream_kw + 6
        
    endstream_kw = data.find(b'endstream', stream_start)
    if endstream_kw == -1:
        return None
        
    stream_end = endstream_kw
    if data[endstream_kw - 2 : endstream_kw] == b'\r\n':
        stream_end = endstream_kw - 2
    elif data[endstream_kw - 1 : endstream_kw] == b'\n':
        stream_end = endstream_kw - 1
        
    stream_data = data[stream_start:stream_end]
    
    # Decompress FlateDecode streams
    # Check dictionary bytes for FlateDecode
    if b'/FlateDecode' in dictionary_bytes:
        try:
            return zlib.decompress(stream_data)
        except Exception:
            # Try with -15 windowBits for raw deflate if it fails
            try:
                return zlib.decompress(stream_data, -15)
            except Exception:
                pass
    return stream_data

def parse_dict_keys(dict_bytes):
    """Parses key-value pairs from a tokenized PDF dictionary."""
    pairs = {}
    tokens = tokenize_pdf(dict_bytes)
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token.startswith(b'/'):
            key = token[1:].decode('utf-8', errors='ignore')
            if i + 1 < len(tokens):
                next_token = tokens[i+1]
                # Is it an indirect reference 'obj_id gen_id R'?
                if (next_token.isdigit() and i + 3 < len(tokens) 
                        and tokens[i+2].isdigit() and tokens[i+3] == b'R'):
                    pairs[key] = tokens[i+1] + b' ' + tokens[i+2] + b' ' + tokens[i+3]
                    i += 4
                else:
                    pairs[key] = next_token
                    i += 2
            else:
                pairs[key] = b''
                i += 1
        else:
            i += 1
    return pairs

def parse_xmp_metadata(xmp_bytes):
    """Uses regex to extract common metadata fields from an XMP XML stream."""
    try:
        xmp_str = xmp_bytes.decode('utf-8', errors='ignore')
    except Exception:
        return {}
        
    fields = {
        "Title": [r'<dc:title[^>]*>\s*<rdf:Alt>\s*<rdf:li[^>]*>(.*?)</rdf:li>', r'<dc:title[^>]*>(.*?)</dc:title>'],
        "Author": [r'<dc:creator[^>]*>\s*<rdf:Seq>\s*<rdf:li[^>]*>(.*?)</rdf:li>', r'<dc:creator[^>]*>(.*?)</dc:creator>'],
        "Producer": [r'<pdf:Producer>(.*?)</pdf:Producer>'],
        "Creator": [r'<xmp:CreatorTool>(.*?)</xmp:CreatorTool>'],
        "CreationDate": [r'<xmp:CreateDate>(.*?)</xmp:CreateDate>'],
        "ModDate": [r'<xmp:ModifyDate>(.*?)</xmp:ModifyDate>']
    }
    
    metadata = {}
    for name, patterns in fields.items():
        for pattern in patterns:
            match = re.search(pattern, xmp_str, re.DOTALL)
            if match:
                val = match.group(1).strip()
                val = re.sub(r'<[^>]+>', '', val) # Strip internal XML tags
                metadata[name] = val
                break
    return metadata

def main():
    parser = argparse.ArgumentParser(
        description="PDF Metadata Extractor - Inspect structural PDF properties and extract metadata."
    )
    parser.add_argument("pdf_file", help="Path to the PDF file to inspect")
    parser.add_argument("-x", "--xmp", action="store_true", help="Dump raw XMP metadata stream if present")
    
    args = parser.parse_args()

    if not os.path.isfile(args.pdf_file):
        print(f"[ERROR] File not found: {args.pdf_file}", file=sys.stderr)
        sys.exit(1)

    try:
        with open(args.pdf_file, 'rb') as f:
            data = f.read()
    except Exception as e:
        print(f"[ERROR] Could not read file: {e}", file=sys.stderr)
        sys.exit(1)

    # Simple validation of PDF file signature
    if not data.startswith(b'%PDF-'):
        print("[WARNING] File does not start with standard PDF header signature. Attempting analysis anyway.", file=sys.stderr)

    # 1. Extract PDF Version from first line
    pdf_version = "Unknown"
    first_line_match = re.match(rb'^%PDF-(\d+\.\d+)', data)
    if first_line_match:
        pdf_version = first_line_match.group(1).decode('ascii')

    # 2. Look for /Info reference in the trailer/cross-reference sections
    # Multiple matches are possible in updated files; take the last (most recent) one
    info_matches = re.findall(br'/Info\s+(\d+)\s+(\d+)\s+R', data)
    info_dict = {}
    info_obj_str = "None"
    
    if info_matches:
        info_obj_id, info_gen_id = info_matches[-1]
        info_obj_str = f"{info_obj_id.decode('ascii')} {info_gen_id.decode('ascii')} R"
        
        # Locate dictionary
        dict_bytes = find_object_dict(data, info_obj_id, info_gen_id)
        if dict_bytes:
            info_dict = parse_dict_keys(dict_bytes)

    # 3. Look for /Metadata reference (XMP stream)
    metadata_matches = re.findall(br'/Metadata\s+(\d+)\s+(\d+)\s+R', data)
    xmp_raw = None
    xmp_metadata = {}
    
    if metadata_matches:
        meta_obj_id, meta_gen_id = metadata_matches[-1]
        dict_bytes = find_object_dict(data, meta_obj_id, meta_gen_id)
        if dict_bytes:
            xmp_raw = extract_stream(data, meta_obj_id, meta_gen_id, dict_bytes)
            if xmp_raw:
                xmp_metadata = parse_xmp_metadata(xmp_raw)

    # Consolidate metadata values
    # Prioritize /Info dict, fall back to XMP metadata
    consolidated = {}
    metadata_keys = ["Title", "Author", "Subject", "Keywords", "Creator", "Producer", "CreationDate", "ModDate"]
    
    for key in metadata_keys:
        val = info_dict.get(key, b'')
        if val:
            parsed_val = parse_pdf_string(val)
        else:
            # Fall back to XMP
            parsed_val = xmp_metadata.get(key, "")
            
        if key in ("CreationDate", "ModDate") and parsed_val:
            parsed_val = parse_pdf_date(parsed_val)
            
        consolidated[key] = parsed_val

    # Print Report
    print(f"--- PDF Metadata Report: {os.path.basename(args.pdf_file)} ---")
    print(f"File Size:          {len(data)} bytes")
    print(f"PDF Version:        {pdf_version}")
    print(f"Info Object:        {info_obj_str}")
    print(f"Metadata Object:    {metadata_matches[-1][0].decode('ascii') if metadata_matches else 'None'}")
    print("\n--- Metadata Fields ---")
    for key, val in consolidated.items():
        # Clean up empty spaces and output
        display_val = val.strip() if val else "[Not Specified]"
        print(f"{key:<15}: {display_val}")
        
    if args.xmp:
        print("\n--- Raw XMP Metadata Stream ---")
        if xmp_raw:
            try:
                print(xmp_raw.decode('utf-8', errors='ignore'))
            except Exception as e:
                print(f"[ERROR] Could not decode XMP stream: {e}", file=sys.stderr)
        else:
            print("[INFO] No metadata stream found in PDF.")
            
    print("-" * (len(os.path.basename(args.pdf_file)) + 25))

if __name__ == "__main__":
    main()
