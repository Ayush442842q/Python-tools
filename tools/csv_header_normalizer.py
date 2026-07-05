#!/usr/bin/env python3
"""
CSV Header Normalizer

Standardizes, cleans, and normalizes column header names across CSV files.
Converts casing (snake_case, camelCase, etc.), strips special characters/accents,
resolves duplicate header collisions, and logs header mapping audits.
"""

import os
import sys
import csv
import re
import json
import unicodedata
import argparse

# Terminal Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def strip_accents(text):
    """Normalize unicode characters to ASCII (e.g. café -> cafe)."""
    nfkd = unicodedata.normalize('NFKD', text)
    return "".join([c for c in nfkd if not unicodedata.combining(c)])


def normalize_string(header, case_style='snake'):
    """Normalizes a single header string into target casing style."""
    # 1. Strip accents and lower/clean special chars
    clean = strip_accents(header).strip()
    
    # 2. Split words on non-alphanumeric characters or camelCase boundaries
    # Add space before capitals in camelCase words
    clean = re.sub(r'([a-z0-9])([A-Z])', r'\1 \2', clean)
    words = re.findall(r'[A-Za-z0-9]+', clean)

    if not words:
        return "unnamed_column"

    if case_style == 'snake':
        return "_".join([w.lower() for w in words])
    elif case_style == 'camel':
        return words[0].lower() + "".join([w.capitalize() for w in words[1:]])
    elif case_style == 'pascal':
        return "".join([w.capitalize() for w in words])
    elif case_style == 'kebab':
        return "-".join([w.lower() for w in words])
    elif case_style == 'upper':
        return "_".join([w.upper() for w in words])
    elif case_style == 'lower':
        return "".join([w.lower() for w in words])
    else:
        return "_".join([w.lower() for w in words])


def deduplicate_headers(headers):
    """Resolves duplicate column names by appending incremental indices."""
    seen = {}
    deduped = []
    for h in headers:
        if h in seen:
            seen[h] += 1
            deduped.append(f"{h}_{seen[h]}")
        else:
            seen[h] = 0
            deduped.append(h)
    return deduped


def process_csv(file_path, case_style='snake', in_place=False, output_path=None, dry_run=False):
    """Processes a CSV file and normalizes its headers."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"CSV file '{file_path}' not found.")

    with open(file_path, 'r', encoding='utf-8-sig', newline='') as f:
        reader = csv.reader(f)
        try:
            raw_headers = next(reader)
        except StopIteration:
            print(f"{YELLOW}[WARNING]{RESET} File '{file_path}' is empty.", file=sys.stderr)
            return [], {}

        rows = list(reader)

    normalized_raw = [normalize_string(h, case_style) for h in raw_headers]
    final_headers = deduplicate_headers(normalized_raw)

    mapping = dict(zip(raw_headers, final_headers))

    if dry_run:
        print(f"{CYAN}--- DRY RUN ({file_path}) ---{RESET}")
        print("Original Headers:  ", raw_headers)
        print("Normalized Headers:", final_headers)
        return final_headers, mapping

    if in_place or output_path:
        target = file_path if in_place else output_path
        with open(target, 'w', encoding='utf-8', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(final_headers)
            writer.writerows(rows)
        print(f"{GREEN}[SUCCESS]{RESET} Written normalized CSV to '{target}'.")
    else:
        writer = csv.writer(sys.stdout)
        writer.writerow(final_headers)
        writer.writerows(rows)

    return final_headers, mapping


def main():
    parser = argparse.ArgumentParser(
        description="CSV Header Normalizer - Clean and standardize column header names across CSV files."
    )
    parser.add_argument("target", help="CSV file or directory path to process")
    parser.add_argument(
        "-c", "--case",
        choices=['snake', 'camel', 'pascal', 'kebab', 'upper', 'lower'],
        default='snake',
        help="Target casing style for headers (default: snake)"
    )
    parser.add_argument("-o", "--output", help="Output CSV path (for single file mode)")
    parser.add_argument("-i", "--in-place", action="store_true", help="Modify CSV file(s) in-place")
    parser.add_argument("-m", "--map-json", help="Export header transformation JSON mapping file")
    parser.add_argument("--dry-run", action="store_true", help="Preview normalized headers without writing changes")
    parser.add_argument("-r", "--recursive", action="store_true", help="Recursively process directory")

    args = parser.parse_args()

    if not os.path.exists(args.target):
        print(f"{RED}[ERROR]{RESET} Target '{args.target}' does not exist.", file=sys.stderr)
        sys.exit(1)

    all_mappings = {}

    if os.path.isfile(args.target):
        _, mapping = process_csv(args.target, case_style=args.case, in_place=args.in_place, output_path=args.output, dry_run=args.dry_run)
        all_mappings[args.target] = mapping
    elif os.path.isdir(args.target):
        if not args.in_place and not args.dry_run:
            print(f"{RED}[ERROR]{RESET} Directory mode requires --in-place or --dry-run flag.", file=sys.stderr)
            sys.exit(1)

        count = 0
        for root, _, files in os.walk(args.target):
            for file in files:
                if file.endswith('.csv'):
                    fp = os.path.join(root, file)
                    _, mapping = process_csv(fp, case_style=args.case, in_place=args.in_place, dry_run=args.dry_run)
                    all_mappings[fp] = mapping
                    count += 1
            if not args.recursive:
                break

        print(f"{GREEN}[SUCCESS]{RESET} Processed {count} CSV files.")

    if args.map_json:
        with open(args.map_json, 'w', encoding='utf-8') as f:
            json.dump(all_mappings, f, indent=2)
        print(f"{GREEN}[SUCCESS]{RESET} Saved header mapping JSON to '{args.map_json}'.")


if __name__ == '__main__':
    main()
