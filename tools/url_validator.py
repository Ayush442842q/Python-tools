#!/usr/bin/env python3

"""
URL Validator - A tool to validate and check if URLs are accessible.
"""

import requests
import sys
import argparse
from urllib.parse import urlparse

def is_valid_url(url):
    """Check if the URL format is valid"""
    try:
        result = urlparse(url)
        return all([result.scheme, result.netloc])
    except Exception:
        return False

def check_url_status(url):
    """Check the HTTP status of a URL"""
    try:
        response = requests.head(url, allow_redirects=True, timeout=10)
        return response.status_code
    except Exception as e:
        return str(e)

def main():
    # Set up argument parser
    parser = argparse.ArgumentParser(description="URL Validator - Check if URLs are valid and accessible")
    parser.add_argument("url", nargs="?", help="URL to validate and check")
    parser.add_argument("--url", dest="url_check", help="The URL to validate and check")
    parser.add_argument("-f", "--file", help="Input file containing URLs to validate", default=None)
    
    args = parser.parse_args()
    
    # Determine the URL source
    if args.file:
        # Read URLs from file
        try:
            with open(args.file, 'r') as f:
                urls = [line.strip() for line in f if line.strip()]
        except FileNotFoundError:
            print(f"Error: File '{args.file}' not found.")
            return
    else:
        # Use command line argument
        url = args.url_check or args.url
        if url:
            urls = [url]
        else:
            print("URL Validator")
            print("Usage: python url_validator.py <URL>")
            print("   or: python url_validator.py --url <URL>")
            print("   or: python url_validator.py -f <file_with_urls.txt>")
            return
    
    # Process each URL
    for url in urls:
        print(f"Validating: {url}")
        if is_valid_url(url):
            print("✓ Valid URL format")
            status = check_url_status(url)
            if isinstance(status, int):
                if 200 <= status < 400:
                    print(f"✓ Status: {status} - Success")
                else:
                    print(f"✗ Status: {status}")
            else:
                print(f"✗ Error: {status}")
        else:
            print("✗ Invalid URL format")
        print()

if __name__ == "__main__":
    main()