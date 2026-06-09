#!/usr/bin/env python3
"""
JSON-CSV Bidirectional Converter - A utility to convert between JSON and CSV.

Features:
- Converts JSON to CSV and CSV to JSON.
- Supports flattening nested JSON structures into a flat CSV format.
- Supports unflattening flat CSV structures back into nested JSON.
- Autodetects conversion mode based on file extensions.
"""

import argparse
import csv
import json
import os
import sys

def flatten_dict(d, parent_key='', sep='.'):
    """Recursively flatten a nested dictionary."""
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        elif isinstance(v, list):
            # For lists, we serialize them as JSON strings to maintain integrity
            items.append((new_key, json.dumps(v)))
        else:
            items.append((new_key, v))
    return dict(items)

def unflatten_dict(d, sep='.'):
    """Reconstruct a nested dictionary from a flattened one."""
    result = {}
    for k, v in d.items():
        parts = k.split(sep)
        curr = result
        for part in parts[:-1]:
            if part not in curr:
                curr[part] = {}
            # If the existing item is not a dict, overwrite it (should not happen for well-structured data)
            if not isinstance(curr[part], dict):
                curr[part] = {}
            curr = curr[part]
        
        # Try to parse lists or other JSON serializations
        last_part = parts[-1]
        val = v
        if isinstance(v, str):
            trimmed = v.strip()
            if (trimmed.startswith('[') and trimmed.endswith(']')) or (trimmed.startswith('{') and trimmed.endswith('}')):
                try:
                    val = json.loads(v)
                except json.JSONDecodeError:
                    pass
            elif trimmed.lower() == 'true':
                val = True
            elif trimmed.lower() == 'false':
                val = False
            elif trimmed.lower() == 'null':
                val = None
            else:
                # Try parsing as number
                try:
                    if '.' in trimmed:
                        val = float(trimmed)
                    else:
                        val = int(trimmed)
                except ValueError:
                    pass
        curr[last_part] = val
    return result

def json_to_csv(json_file, csv_file, delimiter=',', flatten=True, sep='.'):
    """Convert JSON file to CSV."""
    with open(json_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    if not isinstance(data, list):
        # Wrap single object in list
        data = [data]
        
    if not data:
        print("Warning: JSON file is empty or contains an empty list.")
        # Write empty CSV
        with open(csv_file, 'w', newline='', encoding='utf-8') as f:
            pass
        return

    # Flatten if required
    processed_data = []
    all_keys = set()
    for item in data:
        if isinstance(item, dict):
            flat_item = flatten_dict(item, sep=sep) if flatten else item
            processed_data.append(flat_item)
            all_keys.update(flat_item.keys())
        else:
            # Handle primitive types by putting them under a 'value' column
            processed_data.append({'value': item})
            all_keys.add('value')

    headers = sorted(list(all_keys))

    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers, delimiter=delimiter)
        writer.writeheader()
        for row in processed_data:
            # Fill in missing keys with empty strings
            full_row = {k: row.get(k, '') for k in headers}
            writer.writerow(full_row)
            
    print(f"Successfully converted JSON to CSV: '{json_file}' -> '{csv_file}'")
    print(f"Total rows written: {len(processed_data)}")

def csv_to_json(csv_file, json_file, delimiter=',', unflatten=True, sep='.', indent=4):
    """Convert CSV file to JSON."""
    data = []
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f, delimiter=delimiter)
        for row in reader:
            if unflatten:
                # Filter out empty fields to avoid polluting unflattened dictionary
                cleaned_row = {k: v for k, v in row.items() if k is not None and v != ''}
                nested = unflatten_dict(cleaned_row, sep=sep)
                data.append(nested)
            else:
                data.append(dict(row))

    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=indent)

    print(f"Successfully converted CSV to JSON: '{csv_file}' -> '{json_file}'")
    print(f"Total records written: {len(data)}")

def main():
    parser = argparse.ArgumentParser(description="JSON-CSV Bidirectional Converter - Convert data easily between formats.")
    parser.add_argument("input", help="Path to the input file (.json or .csv)")
    parser.add_argument("output", nargs="?", help="Path to the output file (optional)")
    parser.add_argument("-m", "--mode", choices=["json2csv", "csv2json"], help="Conversion mode (default: autodetect from file extension)")
    parser.add_argument("-s", "--separator", default=",", help="CSV field delimiter (default: ',')")
    parser.add_argument("--no-flatten", action="store_true", help="Disable flattening of nested JSON / unflattening of CSV keys")
    parser.add_argument("--flat-sep", default=".", help="Separator string for flattening/unflattening nested keys (default: '.')")
    parser.add_argument("-i", "--indent", type=int, default=4, help="JSON output formatting indentation (default: 4)")

    args = parser.parse_args()

    # Determine conversion mode
    input_ext = os.path.splitext(args.input.lower())[1]
    mode = args.mode
    
    if not mode:
        if input_ext == '.json':
            mode = 'json2csv'
        elif input_ext == '.csv':
            mode = 'csv2json'
        else:
            print(f"Error: Could not autodetect conversion mode for extension '{input_ext}'. Please specify -m/--mode.")
            return 1

    # Determine output file path
    output_path = args.output
    if not output_path:
        base_path = os.path.splitext(args.input)[0]
        if mode == 'json2csv':
            output_path = base_path + '.csv'
        else:
            output_path = base_path + '.json'

    # Perform conversion
    try:
        if mode == 'json2csv':
            json_to_csv(
                args.input, 
                output_path, 
                delimiter=args.separator, 
                flatten=not args.no_flatten, 
                sep=args.flat_sep
            )
        else:
            csv_to_json(
                args.input, 
                output_path, 
                delimiter=args.separator, 
                unflatten=not args.no_flatten, 
                sep=args.flat_sep,
                indent=args.indent
            )
    except FileNotFoundError:
        print(f"Error: Input file '{args.input}' not found.")
        return 1
    except json.JSONDecodeError as e:
        print(f"Error: Failed to parse JSON file '{args.input}': {e}")
        return 1
    except Exception as e:
        print(f"Error occurred during conversion: {e}")
        import traceback
        traceback.print_exc()
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
