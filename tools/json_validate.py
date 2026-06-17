#!/usr/bin/env python3
"""
json_validate - Validate JSON file and pretty‑print if valid

Usage:
    python tools/json_validate.py [FILE]

Example:
    python tools/json_validate.py config.json
"""

import json, argparse, sys

def main():
    parser = argparse.ArgumentParser(description="Validate JSON file")
    parser.add_argument('path', help='JSON file path')
    args = parser.parse_args()
    try:
        with open(args.path, 'r') as f:
            data = json.load(f)
        print(json.dumps(data, indent=4))
    except Exception as e:
        print(f"Invalid JSON: {e}", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
