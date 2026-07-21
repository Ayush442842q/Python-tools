#!/usr/bin/env python3
"""
URL Parser & Query Inspector - Parses URLs and breaks down their components.
Inspects paths, hosts, ports, fragments, and lists decoded key-value query parameters.
"""

import argparse
import json
import sys
from urllib.parse import urlparse, parse_qsl, unquote

def parse_url(url_str):
    """Parses URL components into a dictionary."""
    try:
        parsed = urlparse(url_str)
        query_params = parse_qsl(parsed.query, keep_blank_values=True)
        
        # Build query parameters structure
        params_list = []
        for key, val in query_params:
            params_list.append({
                'key': key,
                'raw_value': val,
                'decoded_value': unquote(val)
            })

        # Separate port from hostname
        host = parsed.hostname or ""
        port = parsed.port or ""

        # Check credentials
        username = parsed.username or ""
        password = parsed.password or ""

        path_segments = [seg for seg in parsed.path.split('/') if seg]

        return {
            'valid': True,
            'url': url_str,
            'scheme': parsed.scheme,
            'netloc': parsed.netloc,
            'username': username,
            'password': password,
            'host': host,
            'port': port,
            'path': parsed.path,
            'path_segments': path_segments,
            'query_raw': parsed.query,
            'query_params': params_list,
            'fragment': parsed.fragment
        }
    except Exception as e:
        return {
            'valid': False,
            'url': url_str,
            'error': str(e)
        }

def print_human_readable(data):
    """Prints URL components in a beautifully structured terminal report."""
    if not data['valid']:
        print(f"Error: Invalid URL. {data.get('error')}", file=sys.stderr)
        return

    border = "=" * 60
    section_divider = "-" * 60
    
    print(border)
    print("URL ANALYSIS REPORT")
    print(border)
    print(f"Target URL : {data['url']}")
    print(section_divider)
    print("COMPONENTS:")
    print(f"  Scheme    : {data['scheme']}")
    print(f"  Netloc    : {data['netloc']}")
    if data['username']:
        print(f"  Username  : {data['username']}")
    if data['password']:
        print(f"  Password  : {'*' * len(data['password'])}")
    print(f"  Host/IP   : {data['host']}")
    if data['port']:
        print(f"  Port      : {data['port']}")
    print(f"  Path      : {data['path']}")
    if data['path_segments']:
        print(f"  Segments  : {data['path_segments']}")
    if data['fragment']:
        print(f"  Fragment  : {data['fragment']}")
        
    print(section_divider)
    print("QUERY PARAMETERS:")
    if not data['query_params']:
        print("  No query parameters found.")
    else:
        # Determine formatting width
        max_key_len = max(len(p['key']) for p in data['query_params'])
        max_key_len = max(max_key_len, 3)
        print(f"  {'Key'.ljust(max_key_len)} | {'Decoded Value'}")
        print(f"  {'-' * max_key_len}-|-{'-' * (55 - max_key_len)}")
        for p in data['query_params']:
            print(f"  {p['key'].ljust(max_key_len)} : {p['decoded_value']}")
            
    print(border)

def main():
    parser = argparse.ArgumentParser(
        description="URL Parser & Query Inspector - Decode and analyze URL components offline."
    )
    parser.add_argument("url", nargs="?", help="URL string to parse")
    parser.add_argument("-u", "--url-arg", dest="url_arg", help="Direct URL argument")
    parser.add_argument("-j", "--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("-o", "--output", help="Save report to file")

    args = parser.parse_args()

    url_to_parse = args.url_arg or args.url

    if not url_to_parse:
        print("URL Parser & Query Inspector")
        print("Usage: python url_parser.py <URL> [options]")
        return 1

    analysis = parse_url(url_to_parse)

    if args.json:
        output_str = json.dumps(analysis, indent=2)
        print(output_str)
    else:
        # We temporarily hijack stdout to write to a string if output is required
        import io
        old_stdout = sys.stdout
        sys.stdout = buffer = io.StringIO()
        print_human_readable(analysis)
        sys.stdout = old_stdout
        output_str = buffer.getvalue()
        print(output_str)

    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output_str)
            print(f"[+] URL analysis saved to: {args.output}")
        except Exception as e:
            print(f"Error saving to output file: {e}", file=sys.stderr)
            return 1

    return 0 if analysis['valid'] else 1

if __name__ == "__main__":
    sys.exit(main())
