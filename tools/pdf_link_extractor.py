#!/usr/bin/env python3
"""
PDF Hyperlink Extractor & Validator

A CLI tool that extracts all hyperlinks (URLs) embedded in a PDF document using
a pure-Python binary parser (no external library like PyPDF2/pdfplumber required).
It decodes the matched links, filters them by scheme, and optionally checks their
HTTP response status (HEAD requests) to find broken links.

Usage:
    python tools/pdf_link_extractor.py -f document.pdf
    python tools/pdf_link_extractor.py -f document.pdf --validate
"""

import argparse
import os
import re
import sys
import urllib.request
import urllib.error
from typing import Dict, Any, List, Set, Tuple

# ANSI Colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"

def supports_color() -> bool:
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform or is_a_tty

def color_text(text: str, color_code: str) -> str:
    return f"{color_code}{text}{COLOR_RESET}" if supports_color() else text

def decode_pdf_string(string_bytes: bytes) -> str:
    """Decodes a PDF literal string, resolving escaped characters."""
    decoded = []
    i = 0
    length = len(string_bytes)
    
    while i < length:
        char = string_bytes[i]
        if char == 92:  # Backslash \
            if i + 1 < length:
                next_char = string_bytes[i + 1]
                if next_char == 110:  # \n
                    decoded.append('\n')
                elif next_char == 114: # \r
                    decoded.append('\r')
                elif next_char == 116: # \t
                    decoded.append('\t')
                elif next_char == 98:  # \b
                    decoded.append('\b')
                elif next_char == 102: # \f
                    decoded.append('\f')
                elif next_char in (40, 41, 92):  # \( , \) , \\
                    decoded.append(chr(next_char))
                # Check for octal escapes \ddd
                elif 48 <= next_char <= 55:
                    octal_bytes = string_bytes[i + 1 : i + 4]
                    octal_str = "".join(chr(b) for b in octal_bytes if 48 <= b <= 55)
                    try:
                        decoded.append(chr(int(octal_str, 8)))
                    except ValueError:
                        decoded.append(chr(next_char))
                    i += len(octal_str)
                    continue
                else:
                    decoded.append(chr(next_char))
                i += 2
                continue
        decoded.append(chr(char))
        i += 1
        
    return "".join(decoded)

class PdfLinkExtractor:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.raw_urls: Set[str] = set()

    def extract_links(self) -> List[str]:
        if not os.path.isfile(self.file_path):
            return []

        try:
            with open(self.file_path, "rb") as f:
                content = f.read()
        except Exception as e:
            print(color_text(f"Error reading file: {e}", COLOR_RED), file=sys.stderr)
            return []

        # Regex patterns to locate URI actions in the PDF structure
        # Pattern 1: Literal strings /URI (https://example.com)
        literal_uri_pattern = re.compile(rb'/URI\s*\((.*?)\)', re.DOTALL)
        
        # Pattern 2: Hex strings /URI <68747470...>
        hex_uri_pattern = re.compile(rb'/URI\s*<\s*([0-9a-fA-F\s]+)\s*>', re.DOTALL)

        # Scan for literal strings
        for match in literal_uri_pattern.finditer(content):
            raw_val = match.group(1)
            # Remove matching balanced parens in case of nested structures,
            # but usually the literal string is a plain URL
            url_str = decode_pdf_string(raw_val)
            self._add_validated_url(url_str)

        # Scan for hex strings
        for match in hex_uri_pattern.finditer(content):
            hex_str = match.group(1).replace(b'\s', b'').replace(b'\n', b'').replace(b'\r', b'')
            try:
                url_str = bytes.fromhex(hex_str.decode('ascii')).decode('utf-8', errors='ignore')
                self._add_validated_url(url_str)
            except Exception:
                continue

        # Sort results
        return sorted(list(self.raw_urls))

    def _add_validated_url(self, url: str):
        url = url.strip()
        # Filter for standard web protocols
        if re.match(r'^(https?|ftp|mailto|git|file):', url, re.IGNORECASE):
            self.raw_urls.add(url)

    def validate_link(self, url: str) -> Tuple[bool, str]:
        """Performs an HTTP HEAD/GET request to verify the link's accessibility."""
        if not url.lower().startswith(('http://', 'https://')):
            return True, "Skipped (Not HTTP)"
            
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'},
            method='HEAD'
        )
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                status = response.status
                return True, f"OK (Status: {status})"
        except urllib.error.HTTPError as e:
            # Try GET if HEAD is not allowed (some servers return 405 or 403 for HEAD)
            if e.code in (403, 405):
                req.method = 'GET'
                try:
                    with urllib.request.urlopen(req, timeout=5) as response:
                        return True, f"OK (Status: {response.status})"
                except Exception as ex:
                    return False, f"Broken (HTTP Error {e.code})"
            return False, f"Broken (HTTP Error {e.code})"
        except urllib.error.URLError as e:
            return False, f"Broken ({e.reason})"
        except Exception as e:
            return False, f"Broken ({type(e).__name__})"

def main():
    parser = argparse.ArgumentParser(description="PDF Hyperlink Extractor & Validator")
    parser.add_argument("-f", "--file", required=True, help="Path to PDF file to extract links from")
    parser.add_argument("-v", "--validate", action="store_true", help="Validate links via HTTP requests")
    
    args = parser.parse_args()

    if not os.path.isfile(args.file):
        print(color_text(f"Error: File '{args.file}' does not exist.", COLOR_RED), file=sys.stderr)
        sys.exit(1)

    print(color_text(f"Scanning '{args.file}' for embedded hyperlinks...", COLOR_YELLOW))
    extractor = PdfLinkExtractor(args.file)
    links = extractor.extract_links()

    if not links:
        print(color_text("No hyperlinks found in the PDF.", COLOR_YELLOW))
        sys.exit(0)

    print(color_text(f"\nFound {len(links)} unique hyperlink(s):", COLOR_GREEN))
    
    if args.validate:
        print(color_text("Validating hyperlinks (this may take a few moments)...", COLOR_CYAN))
        
        ok_count = 0
        broken_count = 0
        skipped_count = 0
        
        for idx, url in enumerate(links, 1):
            sys.stdout.write(f" [{idx}/{len(links)}] Checking: {url[:60]}... ")
            sys.stdout.flush()
            
            is_valid, msg = extractor.validate_link(url)
            
            if "Skipped" in msg:
                status_color = COLOR_YELLOW
                skipped_count += 1
            elif is_valid:
                status_color = COLOR_GREEN
                ok_count += 1
            else:
                status_color = COLOR_RED
                broken_count += 1
                
            print(color_text(msg, status_color))
            # If broken, print the full URL under it to highlight
            if not is_valid:
                print(f"      ↳ Full Link: {color_text(url, COLOR_RED)}")
                
        print(color_text(f"\n{COLOR_BOLD}=== Validation Summary ==={COLOR_RESET}", COLOR_CYAN))
        print(f"  {color_text('Active/OK', COLOR_GREEN):<10} : {ok_count}")
        print(f"  {color_text('Broken', COLOR_RED):<10} : {broken_count}")
        print(f"  {color_text('Skipped', COLOR_YELLOW):<10} : {skipped_count}")
        
        if broken_count > 0:
            sys.exit(1)
    else:
        for idx, url in enumerate(links, 1):
            print(f"  {idx:3}. {url}")
        print()

if __name__ == "__main__":
    main()
