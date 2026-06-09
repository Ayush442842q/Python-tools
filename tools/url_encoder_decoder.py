#!/usr/bin/env python3
"""
URL Encoder/Decoder

Encodes and decodes URL strings. Supports encoding/decoding of either full URLs
or component strings, space handling options (spaces as %20 or +), character encoding customization,
reading from standard input or files, and breakdown analysis of decoded URLs.

Usage:
    python tools/url_encoder_decoder.py --encode "hello world & python"
    python tools/url_encoder_decoder.py --decode "https%3A%2F%2Fexample.com%3Fq%3Dhello%2Bworld"
    python tools/url_encoder_decoder.py --decode "https://example.com?q=hello+world&category=tools" --breakdown
"""

import argparse
import sys
import os
import urllib.parse

def breakdown_url(url_str):
    """
    Parses and prints a structured breakdown of a URL.
    """
    try:
        parsed = urllib.parse.urlparse(url_str)
        print("\nURL Structural Breakdown:")
        print(f"  Scheme:   {parsed.scheme if parsed.scheme else '[None]'}")
        print(f"  Netloc:   {parsed.netloc if parsed.netloc else '[None]'}")
        print(f"  Path:     {parsed.path if parsed.path else '[None]'}")
        print(f"  Params:   {parsed.params if parsed.params else '[None]'}")
        
        # Parse query params
        if parsed.query:
            print(f"  Query String: {parsed.query}")
            query_dict = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
            print("  Query Parameters:")
            for k, v in query_dict.items():
                # v is a list of values
                val_str = ", ".join(f"'{val}'" for val in v)
                print(f"    - {k}: {val_str}")
        else:
            print("  Query String: [None]")
            
        print(f"  Fragment: {parsed.fragment if parsed.fragment else '[None]'}")
    except Exception as e:
        print(f"\n[WARNING] Could not break down URL structure: {e}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(
        description="URL Encoder/Decoder - Encode or decode strings/URLs with optional structural breakdowns."
    )
    
    # Mutually exclusive group for Action
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        '-e', '--encode', 
        action='store_true', 
        help='Encode the input text'
    )
    group.add_argument(
        '-d', '--decode', 
        action='store_true', 
        help='Decode the input text'
    )
    
    parser.add_argument(
        'text', 
        nargs='?', 
        help='The text or URL to encode/decode. If empty, reads from file or stdin.'
    )
    parser.add_argument(
        '-i', '--input', 
        help='Path to input file containing text to encode/decode.'
    )
    parser.add_argument(
        '-o', '--output', 
        help='Path to save output. If omitted, prints to console.'
    )
    parser.add_argument(
        '--plus', 
        action='store_true', 
        help='Use plus encoding/decoding (replaces spaces with "+" instead of "%%20")'
    )
    parser.add_argument(
        '--breakdown', '-b', 
        action='store_true', 
        help='After decoding, print a human-readable structural breakdown of the URL components'
    )
    parser.add_argument(
        '--encoding', 
        default='utf-8', 
        help='Character encoding to use (default: utf-8)'
    )

    args = parser.parse_args()

    # Determine input source
    input_text = ""
    if args.text is not None:
        input_text = args.text
    elif args.input:
        if not os.path.exists(args.input):
            print(f"[ERROR] Input file '{args.input}' does not exist.", file=sys.stderr)
            return 1
        try:
            with open(args.input, 'r', encoding=args.encoding, errors='replace') as f:
                input_text = f.read()
        except Exception as e:
            print(f"[ERROR] Failed to read input file '{args.input}': {e}", file=sys.stderr)
            return 1
    else:
        # Read from stdin
        if sys.stdin.isatty():
            print("[INFO] Waiting for input on stdin... (Ctrl+Z and Enter on Windows to end)", file=sys.stderr)
        try:
            input_text = sys.stdin.read()
        except Exception as e:
            print(f"[ERROR] Failed to read from stdin: {e}", file=sys.stderr)
            return 1

    if not input_text:
        print("[ERROR] Input text is empty.", file=sys.stderr)
        return 1

    result = ""
    try:
        if args.encode:
            if args.plus:
                result = urllib.parse.quote_plus(input_text, encoding=args.encoding)
            else:
                result = urllib.parse.quote(input_text, encoding=args.encoding)
        elif args.decode:
            if args.plus:
                result = urllib.parse.unquote_plus(input_text, encoding=args.encoding)
            else:
                result = urllib.parse.unquote(input_text, encoding=args.encoding)
    except Exception as e:
        print(f"[ERROR] URL operation failed: {e}", file=sys.stderr)
        return 1

    # Write output
    if args.output:
        try:
            with open(args.output, 'w', encoding=args.encoding) as f:
                f.write(result)
            print(f"[OK] Output successfully written to '{args.output}'.")
        except Exception as e:
            print(f"[ERROR] Failed to write output file '{args.output}': {e}", file=sys.stderr)
            return 1
    else:
        # Print result (use sys.stdout.write to avoid adding trailing newlines which change encoded output)
        sys.stdout.write(result)
        # Add a newline only if stdout is a terminal, to keep prompt formatting clean
        if sys.stdout.isatty():
            sys.stdout.write('\n')

    # Optionally print breakdown if requested (only makes sense for decode/URLs)
    if args.breakdown:
        url_to_breakdown = result if args.decode else input_text
        breakdown_url(url_to_breakdown)

    return 0

if __name__ == '__main__':
    sys.exit(main())
