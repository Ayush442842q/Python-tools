#!/usr/bin/env python3
"""
JSON Schema Mock Data Generator

Generates realistic mock data conforming to a given JSON Schema (Draft-07 subset)
using pure Python standard libraries. Supports standard data types, formats,
enums, nested objects, and arrays.

Usage:
    python tools/json_schema_mock_generator.py <schema_file> [options]
"""

import sys
import os
import json
import random
import string
import argparse
from datetime import datetime, timedelta

# Terminal colors
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"

# Sample lists for generating realistic strings
FIRST_NAMES = ["James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda", "William", "Elizabeth"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]
DOMAINS = ["example.com", "test.org", "gmail.com", "yahoo.com", "outlook.com", "company.io"]
WORDS = ["lorem", "ipsum", "dolor", "sit", "amet", "consectetur", "adipiscing", "elit", "sed", "do", "eiusmod", "tempor"]

def print_banner():
    banner = f"""
{CYAN}{BOLD}=========================================================
     🎲   JSON SCHEMA MOCK DATA GENERATOR   🎲
========================================================={RESET}
"""
    print(banner)

def generate_mock_value(schema):
    """Recursively generates mock data matching the given JSON Schema."""
    if not isinstance(schema, dict):
        return None

    # Handle enum
    if "enum" in schema:
        return random.choice(schema["enum"])

    # Handle const
    if "const" in schema:
        return schema["const"]

    # Determine type
    schema_type = schema.get("type", "string")

    if isinstance(schema_type, list):
        # Pick one valid type (ignoring 'null' if possible for better mock values)
        non_null_types = [t for t in schema_type if t != "null"]
        schema_type = random.choice(non_null_types) if non_null_types else "null"

    if schema_type == "null":
        return None

    if schema_type == "boolean":
        return random.choice([True, False])

    if schema_type in ("integer", "number"):
        minimum = schema.get("minimum", 1)
        maximum = schema.get("maximum", 100)
        
        # Check exclusive boundaries
        if "exclusiveMinimum" in schema:
            minimum = schema["exclusiveMinimum"] + 1
        if "exclusiveMaximum" in schema:
            maximum = schema["exclusiveMaximum"] - 1

        if schema_type == "integer":
            return random.randint(int(minimum), int(maximum))
        else:
            return round(random.uniform(float(minimum), float(maximum)), 2)

    if schema_type == "string":
        fmt = schema.get("format", "")
        
        if fmt == "email":
            first = random.choice(FIRST_NAMES).lower()
            last = random.choice(LAST_NAMES).lower()
            domain = random.choice(DOMAINS)
            return f"{first}.{last}@{domain}"
            
        elif fmt in ("date", "date-time"):
            days_ago = random.randint(0, 365 * 5)
            dt = datetime.now() - timedelta(days=days_ago)
            if fmt == "date":
                return dt.strftime("%Y-%m-%d")
            else:
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
                
        elif fmt == "uuid":
            return "-".join([
                "".join(random.choices(string.hexdigits.lower(), k=8)),
                "".join(random.choices(string.hexdigits.lower(), k=4)),
                "4" + "".join(random.choices(string.hexdigits.lower(), k=3)), # UUID v4 marker
                "".join(random.choices("89ab", k=1)) + "".join(random.choices(string.hexdigits.lower(), k=3)),
                "".join(random.choices(string.hexdigits.lower(), k=12))
            ])
            
        elif fmt == "ipv4":
            return f"{random.randint(1, 254)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"
            
        elif fmt == "hostname":
            return f"www.{random.choice(WORDS)}.{random.choice(DOMAINS)}"
            
        elif fmt == "uri":
            return f"https://www.{random.choice(WORDS)}.{random.choice(DOMAINS)}/{random.choice(WORDS)}"

        # Default string generation
        min_len = schema.get("minLength", 5)
        max_len = schema.get("maxLength", 15)
        
        # Make a readable word string if possible
        word_count = max(1, min_len // 6)
        text = " ".join(random.choices(WORDS, k=word_count)).capitalize()
        
        # Ensure it fits constraints
        if len(text) < min_len:
            text += "".join(random.choices(string.ascii_lowercase, k=min_len - len(text)))
        if len(text) > max_len:
            text = text[:max_len]
            
        return text

    if schema_type == "object":
        properties = schema.get("properties", {})
        required = schema.get("required", [])
        obj = {}
        
        for prop_name, prop_schema in properties.items():
            # If not required, random chance to include it (e.g. 80% chance)
            if prop_name in required or random.random() < 0.8:
                obj[prop_name] = generate_mock_value(prop_schema)
                
        return obj

    if schema_type == "array":
        items_schema = schema.get("items", {})
        min_items = schema.get("minItems", 1)
        max_items = schema.get("maxItems", 5)
        count = random.randint(min_items, max_items)
        
        return [generate_mock_value(items_schema) for _ in range(count)]

    return None

def main():
    parser = argparse.ArgumentParser(
        description="JSON Schema Mock Data Generator - Create mock data records adhering to a JSON Schema file.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("schema", help="Path to the JSON Schema file")
    parser.add_argument("--count", "-n", type=int, default=1, help="Number of mock records to generate (default: 1)")
    parser.add_argument("--output", "-o", help="Save output to a JSON file instead of stdout")
    parser.add_argument("--seed", "-s", type=int, help="Seed value for reproducible random generations")
    parser.add_argument("--pretty", "-p", action="store_true", help="Format JSON with indentation")
    
    args = parser.parse_args()
    print_banner()

    if args.seed is not None:
        random.seed(args.seed)

    if not os.path.exists(args.schema):
        print(f"{RED}Error: Schema file '{args.schema}' not found.{RESET}", file=sys.stderr)
        return 1

    try:
        with open(args.schema, "r", encoding="utf-8") as f:
            schema_data = json.load(f)
    except Exception as e:
        print(f"{RED}Error: Failed to parse schema JSON: {e}{RESET}", file=sys.stderr)
        return 1

    print(f"📄 Loaded schema: {BOLD}{os.path.basename(args.schema)}{RESET}")
    print(f"🎲 Generating {args.count} mock record(s)...")

    results = []
    for _ in range(args.count):
        results.append(generate_mock_value(schema_data))

    # Determine final structure: single object if count=1 and no array wrapper desired, or list of objects
    output_data = results[0] if args.count == 1 else results
    indent = 4 if args.pretty or args.output else None
    json_str = json.dumps(output_data, indent=indent, ensure_ascii=False)

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(json_str)
            print(f"{GREEN}Successfully wrote mock data to: '{args.output}'{RESET}")
        except Exception as e:
            print(f"{RED}Failed to write to file: {e}{RESET}", file=sys.stderr)
            return 1
    else:
        print(f"\n{BOLD}Generated Output:{RESET}")
        print(json_str)

    return 0

if __name__ == "__main__":
    sys.exit(main())
