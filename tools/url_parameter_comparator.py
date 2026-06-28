#!/usr/bin/env python3
"""
URL Parameter Comparator
Compares multiple URLs side-by-side to highlight differences in scheme, netloc,
path, query parameters, and parameter values.

License: MIT
"""

import sys
import os
import argparse
from urllib.parse import urlparse, parse_qs, unquote

class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    CYAN = '\033[96m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def print_header(msg):
    print(f"\n{Colors.HEADER}{Colors.BOLD}=== {msg} ==={Colors.ENDC}")

def format_value(val, color=None):
    if color:
        return f"{color}{val}{Colors.ENDC}"
    return val

def compare_urls(urls, verbose=False, show_matching=True):
    parsed_urls = []
    
    # Parse all URLs
    for idx, url in enumerate(urls):
        try:
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query, keep_blank_values=True)
            parsed_urls.append({
                'index': idx + 1,
                'original': url,
                'parsed': parsed,
                'query': query_params
            })
        except Exception as e:
            print(f"{Colors.RED}Error parsing URL {idx+1}: {e}{Colors.ENDC}")
            return

    # 1. Compare Core URL Components
    print_header("Core URL Components")
    
    components = [
        ('Scheme', lambda p: p.scheme),
        ('Host/Domain', lambda p: p.netloc),
        ('Path', lambda p: p.path),
        ('Fragment/Hash', lambda p: p.fragment)
    ]
    
    for name, getter in components:
        values = [getter(pu['parsed']) for pu in parsed_urls]
        all_same = len(set(values)) == 1
        
        print(f"{Colors.BOLD}{name:15}:{Colors.ENDC}", end=" ")
        if all_same:
            print(format_value(values[0], Colors.GREEN if values[0] else None))
        else:
            print(f"{Colors.YELLOW}[DIFFERENT]{Colors.ENDC}")
            for pu, val in zip(parsed_urls, values):
                print(f"  URL {pu['index']}: {format_value(val or '<none>', Colors.RED)}")

    # 2. Compare Query Parameter Keys
    print_header("Query Parameters Presence")
    
    all_keys = set()
    for pu in parsed_urls:
        all_keys.update(pu['query'].keys())
        
    all_keys = sorted(list(all_keys))
    
    if not all_keys:
        print("No query parameters found in any of the URLs.")
        return

    # Track presence and values
    presence_matrix = {}
    for key in all_keys:
        presence_matrix[key] = []
        for pu in parsed_urls:
            presence_matrix[key].append(key in pu['query'])

    # Output parameter presence table
    header_row = f"{'Parameter Key':30} | " + " | ".join(f"URL {pu['index']}" for pu in parsed_urls)
    print(Colors.BOLD + header_row + Colors.ENDC)
    print("-" * len(header_row))
    
    for key in all_keys:
        row_vals = []
        for present in presence_matrix[key]:
            if present:
                row_vals.append(f"{Colors.GREEN}✔ Yes{Colors.ENDC}")
            else:
                row_vals.append(f"{Colors.RED}✘ No {Colors.ENDC}")
        print(f"{key:30} | " + " | ".join(row_vals))

    # 3. Compare Values of Shared Parameters
    print_header("Parameter Values Comparison")
    
    for key in all_keys:
        # Get values across all URLs (None if parameter doesn't exist in that URL)
        raw_vals = [pu['query'].get(key) for pu in parsed_urls]
        
        # Flatten values: list of values or single string/None representation
        vals = []
        for v in raw_vals:
            if v is None:
                vals.append(None)
            elif len(v) == 1:
                vals.append(v[0])
            else:
                vals.append(str(v))
                
        # Check if they are all identical
        non_none_vals = [v for v in vals if v is not None]
        all_values_same = len(set(non_none_vals)) <= 1 and len(non_none_vals) == len(urls)
        
        if all_values_same:
            if show_matching:
                decoded_val = unquote(vals[0])
                if decoded_val != vals[0]:
                    print(f"{Colors.BOLD}{key:30}{Colors.ENDC}: {Colors.GREEN}{vals[0]}{Colors.ENDC} (Decoded: {Colors.CYAN}{decoded_val}{Colors.ENDC})")
                else:
                    print(f"{Colors.BOLD}{key:30}{Colors.ENDC}: {Colors.GREEN}{vals[0]}{Colors.ENDC}")
        else:
            print(f"{Colors.BOLD}{key:30}{Colors.ENDC}: {Colors.YELLOW}[MISMATCH]{Colors.ENDC}")
            for pu, val in zip(parsed_urls, vals):
                if val is None:
                    print(f"  URL {pu['index']}: {Colors.RED}<NOT PRESENT>{Colors.ENDC}")
                else:
                    decoded_val = unquote(val)
                    if decoded_val != val:
                        print(f"  URL {pu['index']}: {Colors.YELLOW}{val}{Colors.ENDC} (Decoded: {Colors.CYAN}{decoded_val}{Colors.ENDC})")
                    else:
                        print(f"  URL {pu['index']}: {Colors.YELLOW}{val}{Colors.ENDC}")

def main():
    parser = argparse.ArgumentParser(
        description="Compare query parameters and components of multiple URLs side-by-side.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python url_parameter_comparator.py "https://example.com/api?user=1&role=admin" "https://example.com/api?user=2&role=admin&debug=true"
  
  # Hide parameters that have matching values
  python url_parameter_comparator.py -m "https://example.com/api?a=1&b=2" "https://example.com/api?a=1&b=3"
        """
    )
    
    parser.add_argument("urls", nargs="+", help="URLs to compare (at least 2 URLs are required)")
    parser.add_argument("-m", "--hide-matching", action="store_true", help="Hide query parameters that have identical values across all URLs")
    
    args = parser.parse_args()

    if len(args.urls) < 2:
        print(f"{Colors.RED}Error: Please provide at least two URLs to compare.{Colors.ENDC}")
        parser.print_help()
        sys.exit(1)

    compare_urls(args.urls, show_matching=not args.hide_matching)

if __name__ == "__main__":
    main()
