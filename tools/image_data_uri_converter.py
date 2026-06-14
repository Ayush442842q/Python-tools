#!/usr/bin/env python3
"""
Image Data URI Converter & Inliner

A command-line tool to encode images to Base64 Data URIs, decode Data URIs back to binary,
and automatically inline local images in HTML/CSS files.

Usage:
    python tools/image_data_uri_converter.py encode logo.png --format html
    python tools/image_data_uri_converter.py decode "data:image/png;base64,iVBOR..." --out restored.png
    python tools/image_data_uri_converter.py inline index.html --out bundle.html
"""

import argparse
import sys
import os
import base64
import re

# File extensions to MIME types mapping
MIME_TYPES = {
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.gif': 'image/gif',
    '.svg': 'image/svg+xml',
    '.webp': 'image/webp',
    '.ico': 'image/x-icon',
    '.bmp': 'image/bmp'
}

def get_mime_type(filepath):
    _, ext = os.path.splitext(filepath.lower())
    return MIME_TYPES.get(ext, 'application/octet-stream')

def encode_image(filepath, format_type='raw'):
    """Encodes a local file to a base64 Data URI in various formats."""
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' not found.", file=sys.stderr)
        return None
        
    mime_type = get_mime_type(filepath)
    
    try:
        with open(filepath, 'rb') as f:
            data = f.read()
    except Exception as e:
        print(f"Error reading file '{filepath}': {e}", file=sys.stderr)
        return None

    b64_str = base64.b64encode(data).decode('ascii')
    data_uri = f"data:{mime_type};base64,{b64_str}"
    
    filename = os.path.basename(filepath)
    name_only, _ = os.path.splitext(filename)

    if format_type == 'html':
        return f'<img src="{data_uri}" alt="{name_only}" />'
    elif format_type == 'css':
        return f'background-image: url("{data_uri}");'
    elif format_type == 'markdown':
        return f'![{name_only}]({data_uri})'
    else:
        return data_uri

def decode_uri(uri_str, output_path):
    """Decodes a base64 Data URI back to a binary file."""
    # Data URI format: data:[<mediatype>][;base64],<data>
    m = re.match(r'^data:(?P<mime>[^;]+)?(?P<b64>;base64)?,(?P<data>.+)$', uri_str.strip())
    if not m:
        print("Error: Invalid Data URI format.", file=sys.stderr)
        return False
        
    mime = m.group('mime') or 'application/octet-stream'
    is_base64 = bool(m.group('b64'))
    raw_data = m.group('data')
    
    try:
        if is_base64:
            binary_data = base64.b64decode(raw_data.encode('ascii'))
        else:
            # URL unescaping for non-base64 data (e.g. SVG)
            from urllib.parse import unquote
            binary_data = unquote(raw_data).encode('utf-8')
    except Exception as e:
        print(f"Error decoding data: {e}", file=sys.stderr)
        return False
        
    try:
        with open(output_path, 'wb') as f:
            f.write(binary_data)
        print(f"Successfully decoded and wrote to: {output_path}", file=sys.stderr)
        return True
    except Exception as e:
        print(f"Error writing output file: {e}", file=sys.stderr)
        return False

def inline_assets(target_file, output_path=None):
    """Scans an HTML or CSS file, finds references to local images, and inlines them."""
    if not os.path.exists(target_file):
        print(f"Error: Target file '{target_file}' not found.", file=sys.stderr)
        return False
        
    try:
        with open(target_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading target file: {e}", file=sys.stderr)
        return False

    base_dir = os.path.dirname(os.path.abspath(target_file))

    # Regex patterns for identifying files
    # 1. HTML img src: src="filename.png" or src='filename.png'
    # 2. CSS url: url("filename.png") or url('filename.png') or url(filename.png)
    
    inlined_count = 0

    def replace_html_src(match):
        nonlocal inlined_count
        quote = match.group(1)
        img_path = match.group(2)
        
        # Skip absolute/remote URLs and already inlined data
        if img_path.startswith(('http://', 'https://', 'data:', '/')):
            return match.group(0)
            
        full_path = os.path.join(base_dir, img_path)
        if os.path.exists(full_path):
            data_uri = encode_image(full_path, 'raw')
            if data_uri:
                inlined_count += 1
                return f'src={quote}{data_uri}{quote}'
        return match.group(0)

    def replace_css_url(match):
        nonlocal inlined_count
        # Match can have quotes or no quotes
        quote = match.group(2) or ''
        img_path = match.group(3)
        
        # Skip absolute/remote URLs and already inlined data
        if img_path.startswith(('http://', 'https://', 'data:', '/')):
            return match.group(0)
            
        full_path = os.path.join(base_dir, img_path)
        if os.path.exists(full_path):
            data_uri = encode_image(full_path, 'raw')
            if data_uri:
                inlined_count += 1
                return f'url({quote}{data_uri}{quote})'
        return match.group(0)

    # Replace HTML src matches
    # src="path" or src='path'
    content = re.sub(r'\bsrc=(["\'])(.*?)\1', replace_html_src, content)
    
    # Replace CSS url(path) matches
    # url("path") or url('path') or url(path)
    content = re.sub(r'\burl\((["\']?)(.*?)\1\)', replace_css_url, content)

    print(f"Inlined {inlined_count} image assets.", file=sys.stderr)

    if output_path:
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f"Saved self-contained bundle to: {output_path}", file=sys.stderr)
        except Exception as e:
            print(f"Error writing bundle output: {e}", file=sys.stderr)
            return False
    else:
        sys.stdout.write(content)
        
    return True

def main():
    parser = argparse.ArgumentParser(description="Encode images to Base64 Data URIs, decode them, or inline them in web documents.")
    subparsers = parser.add_subparsers(dest="action", required=True, help="Action to perform")
    
    # Encode subparser
    enc_parser = subparsers.add_parser("encode", help="Encode an image to a Data URI")
    enc_parser.add_argument("image_path", help="Path to the image file")
    enc_parser.add_argument("--format", choices=['raw', 'html', 'css', 'markdown'], default='raw',
                            help="Output format: raw URI, HTML tag, CSS url, or Markdown syntax")
    enc_parser.add_argument("--out", help="Write output to file instead of stdout")

    # Decode subparser
    dec_parser = subparsers.add_parser("decode", help="Decode a Data URI back to a binary image file")
    dec_parser.add_argument("uri", help="Data URI string (or path to file containing only the URI)")
    dec_parser.add_argument("--out", required=True, help="Output image file path (e.g. output.png)")

    # Inline subparser
    inline_parser = subparsers.add_parser("inline", help="Scan HTML/CSS and inline all local image references")
    inline_parser.add_argument("target_file", help="Path to HTML or CSS file")
    inline_parser.add_argument("--out", help="Write bundle to file instead of stdout")
    
    args = parser.parse_args()

    if args.action == "encode":
        result = encode_image(args.image_path, args.format)
        if not result:
            return 1
        if args.out:
            try:
                with open(args.out, 'w', encoding='utf-8') as f:
                    f.write(result + '\n')
                print(f"Saved Data URI output to: {args.out}", file=sys.stderr)
            except Exception as e:
                print(f"Error writing output file: {e}", file=sys.stderr)
                return 1
        else:
            print(result)
            
    elif args.action == "decode":
        uri_str = args.uri
        # If input uri is a file path, read the URI from the file
        if os.path.exists(uri_str):
            try:
                with open(uri_str, 'r', encoding='utf-8') as f:
                    uri_str = f.read().strip()
            except Exception as e:
                print(f"Error reading URI file: {e}", file=sys.stderr)
                return 1
        success = decode_uri(uri_str, args.out)
        return 0 if success else 1
        
    elif args.action == "inline":
        success = inline_assets(args.target_file, args.out)
        return 0 if success else 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
