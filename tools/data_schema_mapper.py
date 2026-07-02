#!/usr/bin/env python3
"""
Data Schema Mapper & Migrator
An interactive command-line tool to map, transform, and migrate data between
different CSV and JSON structures. Supports custom field-to-field mapping,
type conversions, string concatenations, date conversions, and default values.
"""

import argparse
import csv
import datetime
import json
import os
import sys

# Formatting colors
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
BOLD = "\033[1m"
RESET = "\033[0m"


def load_dataset(file_path):
    """Loads a CSV or JSON file into a list of dictionaries."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    _, ext = os.path.splitext(file_path.lower())
    if ext == ".json":
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            elif isinstance(data, dict):
                return [data]
            else:
                raise ValueError("JSON file must contain a list of records or a single dictionary object.")
    elif ext in (".csv", ".tsv"):
        delimiter = "\t" if ext == ".tsv" else ","
        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            return [dict(row) for row in reader]
    else:
        raise ValueError(f"Unsupported file format: {ext}. Only JSON, CSV, and TSV are supported.")


def write_dataset(data, file_path):
    """Writes a list of dictionaries to a CSV or JSON file."""
    _, ext = os.path.splitext(file_path.lower())
    
    if ext == ".json":
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    elif ext in (".csv", ".tsv"):
        if not data:
            raise ValueError("No data records to write.")
        delimiter = "\t" if ext == ".tsv" else ","
        # Extract headers from all records to handle sparse fields
        headers = set()
        for r in data:
            headers.update(r.keys())
        headers = sorted(list(headers))
        
        with open(file_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=headers, delimiter=delimiter)
            writer.writeheader()
            writer.writerows(data)
    else:
        raise ValueError(f"Unsupported export format: {ext}")


class DataTransformer:
    def __init__(self, mapping_rules):
        self.rules = mapping_rules  # dict of target_field -> rule_definition

    def transform_record(self, src_record):
        """Applies transformation rules to a single source record to produce target record."""
        target_record = {}
        for target_field, rule in self.rules.items():
            value = None
            rule_type = rule.get("type", "direct")
            
            if rule_type == "direct":
                src_field = rule.get("source_field")
                value = src_record.get(src_field) if src_field else None
                
            elif rule_type == "constant":
                value = rule.get("value")
                
            elif rule_type == "concatenate":
                fields = rule.get("source_fields", [])
                sep = rule.get("separator", " ")
                vals = [str(src_record.get(f, "")) for f in fields if src_record.get(f) is not None]
                value = sep.join(vals) if vals else None
                
            elif rule_type == "date_format":
                src_field = rule.get("source_field")
                src_val = src_record.get(src_field) if src_field else None
                if src_val:
                    src_format = rule.get("input_format", "%Y-%m-%d")
                    out_format = rule.get("output_format", "%Y-%m-%d")
                    try:
                        dt = datetime.datetime.strptime(str(src_val).strip(), src_format)
                        value = dt.strftime(out_format)
                    except ValueError:
                        value = src_val  # Fallback to raw string if parsing fails
                else:
                    value = None

            # Apply Type Casting
            cast_type = rule.get("cast")
            if value is not None and cast_type:
                try:
                    if cast_type == "int":
                        value = int(float(value))
                    elif cast_type == "float":
                        value = float(value)
                    elif cast_type == "str":
                        value = str(value)
                    elif cast_type == "bool":
                        val_str = str(value).lower().strip()
                        value = val_str in ("true", "1", "yes", "t", "y")
                except (ValueError, TypeError):
                    pass # Keep original value on error
            
            # Apply Default Value if empty
            if (value is None or value == "") and "default" in rule:
                value = rule["default"]
                
            target_record[target_field] = value
            
        return target_record

    def transform_dataset(self, dataset):
        return [self.transform_record(r) for r in dataset]


def run_interactive_wizard(src_fields):
    """Interactively guides the user to define a schema mapping configuration."""
    print(f"\n{BOLD}=== Interactive Mapping Wizard ==={RESET}")
    print(f"Detected Source Fields: {YELLOW}{', '.join(src_fields)}{RESET}\n")
    
    mapping = {}
    
    while True:
        target_field = input(f"Enter {BOLD}Target Field Name{RESET} (or leave empty to finish): ").strip()
        if not target_field:
            break
            
        print("\nChoose Mapping Type:")
        print("  1. Direct Field Mapping (copy from source field)")
        print("  2. Constant Value (hardcode a value for all records)")
        print("  3. Concatenate Fields (join multiple source fields together)")
        print("  4. Date Format Conversion")
        choice = input("Enter Choice (1-4): ").strip()
        
        rule = {}
        if choice == "1":
            rule["type"] = "direct"
            print(f"Available source fields: {', '.join(src_fields)}")
            src_f = input("Source Field: ").strip()
            if src_f in src_fields:
                rule["source_field"] = src_f
            else:
                print(f"{RED}Warning: field '{src_f}' not in source. Direct mapping registered anyway.{RESET}")
                rule["source_field"] = src_f
                
        elif choice == "2":
            rule["type"] = "constant"
            rule["value"] = input("Constant Value: ")
            
        elif choice == "3":
            rule["type"] = "concatenate"
            print(f"Available source fields: {', '.join(src_fields)}")
            fields_input = input("Source fields to concatenate (comma-separated): ").strip()
            rule["source_fields"] = [f.strip() for f in fields_input.split(",") if f.strip()]
            rule["separator"] = input("Separator character (default: space): ") or " "
            
        elif choice == "4":
            rule["type"] = "date_format"
            rule["source_field"] = input("Source Date Field: ").strip()
            rule["input_format"] = input("Input Date Format (e.g. %d/%m/%Y or %Y-%m-%d): ").strip() or "%Y-%m-%d"
            rule["output_format"] = input("Output Date Format (e.g. %Y-%m-%d or %B %d, %Y): ").strip() or "%Y-%m-%d"
            
        else:
            print(f"{RED}Invalid mapping type. Setting direct mapping template.{RESET}")
            rule["type"] = "direct"
            rule["source_field"] = ""

        # Option to cast types
        cast_choice = input("Apply Type Casting? (int/float/str/bool or leave empty): ").strip().lower()
        if cast_choice in ("int", "float", "str", "bool"):
            rule["cast"] = cast_choice
            
        # Option for default value
        default_val = input("Default value if empty/null (leave empty for none): ")
        if default_val:
            rule["default"] = default_val
            
        mapping[target_field] = rule
        print(f"{GREEN}✓ Added mapping rule for '{target_field}'{RESET}\n")
        
    return mapping


def main():
    parser = argparse.ArgumentParser(description="Data Schema Mapper & Migrator Utility")
    parser.add_argument("-s", "--source", required=True, help="Path to the source CSV/JSON file")
    parser.add_argument("-t", "--target", required=True, help="Path to output CSV/JSON file")
    parser.add_argument("-m", "--mapping", help="Path to mapping rules configuration JSON file")
    parser.add_argument("-p", "--preview", type=int, default=3, help="Number of records to preview in console (default: 3)")
    args = parser.parse_args()

    # Load source dataset
    try:
        source_data = load_dataset(args.source)
        print(f"{GREEN}✓ Successfully loaded source dataset: {RESET}{len(source_data)} records found.")
    except Exception as e:
        print(f"{RED}Error loading source file: {e}{RESET}")
        sys.exit(1)

    # Gather source fields
    if not source_data:
        print(f"{RED}Error: Source dataset is empty.{RESET}")
        sys.exit(1)
    source_fields = list(source_data[0].keys())

    # Get or generate mapping rules
    mapping_rules = {}
    if args.mapping:
        if os.path.exists(args.mapping):
            try:
                with open(args.mapping, "r") as f:
                    mapping_rules = json.load(f)
                print(f"{GREEN}✓ Successfully loaded mapping rules configuration.{RESET}")
            except Exception as e:
                print(f"{RED}Error loading mapping rules file: {e}{RESET}")
                sys.exit(1)
        else:
            print(f"{RED}Mapping file {args.mapping} not found. Running wizard...{RESET}")
            mapping_rules = run_interactive_wizard(source_fields)
    else:
        mapping_rules = run_interactive_wizard(source_fields)

    # Let user save the mapping file if they ran interactive wizard
    if not args.mapping:
        save_rules = input("\nWould you like to save these mapping rules to a JSON file? (y/n): ").strip().lower()
        if save_rules == "y":
            rules_path = input("Enter file path (e.g. mapping.json): ").strip()
            try:
                with open(rules_path, "w") as f:
                    json.dump(mapping_rules, f, indent=2)
                print(f"{GREEN}✓ Rules saved to {rules_path}{RESET}")
            except Exception as e:
                print(f"{RED}Error saving rules file: {e}{RESET}")

    # Perform transformation
    print(f"\n{CYAN}* Transforming dataset...{RESET}")
    transformer = DataTransformer(mapping_rules)
    target_data = transformer.transform_dataset(source_data)

    # Display preview
    preview_count = min(args.preview, len(target_data))
    if preview_count > 0:
        print(f"\n{BOLD}=== Preview (First {preview_count} Records) ==={RESET}")
        for i in range(preview_count):
            print(f"\n{BOLD}Record #{i+1}:{RESET}")
            print(json.dumps(target_data[i], indent=2))
        print(f"{BOLD}========================================={RESET}\n")

    # Export target dataset
    try:
        write_dataset(target_data, args.target)
        print(f"{GREEN}✓ Successfully migrated dataset to target: {RESET}{args.target}")
    except Exception as e:
        print(f"{RED}Error exporting to target file: {e}{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
