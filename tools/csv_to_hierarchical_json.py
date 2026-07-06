"""
CSV to Hierarchical JSON Converter
Converts a CSV with dot-notated headers (e.g. user.name.first, user.roles.0)
into a nested hierarchical JSON, and vice versa.
"""
import argparse
import csv
import json
import os
import re
import sys

def parse_val(val):
    """Safely coerce CSV string value to proper primitive type."""
    if not val:
        return None
    val_lower = val.strip().lower()
    if val_lower == 'true':
        return True
    if val_lower == 'false':
        return False
    # Check if integer
    if re.match(r'^-?\d+$', val.strip()):
        return int(val.strip())
    # Check if float
    if re.match(r'^-?\d+\.\d+$', val.strip()):
        return float(val.strip())
    return val

def set_nested_value(obj, path, value):
    """Set value in object/list using dot-separated path."""
    parts = []
    # Parse parts, handling potential array indices
    for part in path.split('.'):
        if part.isdigit():
            parts.append(int(part))
        else:
            parts.append(part)
            
    current = obj
    for i, part in enumerate(parts[:-1]):
        nxt_part = parts[i + 1]
        
        if isinstance(current, dict):
            if part not in current:
                current[part] = [] if isinstance(nxt_part, int) else {}
            current = current[part]
        elif isinstance(current, list):
            # Extend list if index is out of bounds
            while len(current) <= part:
                current.append(None)
            if current[part] is None:
                current[part] = [] if isinstance(nxt_part, int) else {}
            current = current[part]
            
    # Set final value
    last_part = parts[-1]
    if isinstance(current, dict):
        current[last_part] = value
    elif isinstance(current, list):
        while len(current) <= last_part:
            current.append(None)
        current[last_part] = value

def flatten_json(obj, prefix=''):
    """Flatten nested JSON into a single-level dictionary of dot-notation paths."""
    items = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            new_key = f"{prefix}.{k}" if prefix else k
            items.update(flatten_json(v, new_key))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            new_key = f"{prefix}.{i}" if prefix else str(i)
            items.update(flatten_json(v, new_key))
    else:
        items[prefix] = obj
    return items

def csv_to_json(csv_path):
    """Convert CSV file to hierarchical JSON."""
    result = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        headers = next(reader, None)
        if not headers:
            return result
            
        for row in reader:
            # We initialize row object as dictionary (default root is dict)
            row_obj = {}
            for col_idx, cell in enumerate(row):
                if col_idx < len(headers):
                    header = headers[col_idx]
                    val = parse_val(cell)
                    if val is not None:
                        set_nested_value(row_obj, header, val)
            result.append(row_obj)
    return result

def json_to_csv(json_path, csv_path):
    """Convert nested JSON file back to a flat CSV."""
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    if not isinstance(data, list):
        data = [data]
        
    # Flatten all rows to determine headers
    flattened_rows = [flatten_json(row) for row in data]
    
    # Collect all unique headers/keys
    headers = sorted(list(set(k for row in flattened_rows for k in row.keys())))
    
    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(headers)
        for row in flattened_rows:
            writer.writerow([row.get(h, '') for h in headers])

def main():
    parser = argparse.ArgumentParser(
        description="Convert flat CSV with dot-notated headers to hierarchical JSON, and vice versa."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--csv-to-json",
        action="store_true",
        help="Convert CSV to hierarchical JSON."
    )
    group.add_argument(
        "--json-to-csv",
        action="store_true",
        help="Convert hierarchical JSON to CSV."
    )
    parser.add_argument(
        "-i", "--input",
        required=True,
        help="Path to the input file."
    )
    parser.add_argument(
        "-o", "--output",
        help="Path to the output file. If not specified, JSON will print to stdout."
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indentation spaces (default: 2)."
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(f"[ERROR] Input file does not exist: {args.input}")
        sys.exit(1)
        
    try:
        if args.csv_to_json:
            result = csv_to_json(args.input)
            json_str = json.dumps(result, indent=args.indent, ensure_ascii=False)
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(json_str)
                print(f"[OK] Hierarchical JSON successfully saved to '{args.output}'.")
            else:
                print(json_str)
                
        elif args.json_to_csv:
            if not args.output:
                print("[ERROR] Output CSV file path is required when converting JSON to CSV.")
                sys.exit(1)
            json_to_csv(args.input, args.output)
            print(f"[OK] CSV file successfully saved to '{args.output}'.")
            
    except Exception as e:
        print(f"[ERROR] Process failed: {e}")
        sys.exit(1)
        
    sys.exit(0)

if __name__ == "__main__":
    main()
