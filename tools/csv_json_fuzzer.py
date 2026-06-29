#!/usr/bin/env python3
"""
CSV/JSON Mutation Fuzzer - Takes a valid JSON or CSV seed file and generates 
mutated test cases (fuzz vectors) containing boundary values, extreme strings, 
format strings, null bytes, and SQLi/XSS payloads to test parsing application robustness.
Uses only Python standard libraries (json, csv, random, argparse).
"""

import argparse
import csv
import json
import os
import random
import sys

# Standard fuzz payloads
FUZZ_STRINGS = [
    "",  # Empty string
    "A" * 1000,  # Long buffer
    "A" * 10000,  # Extra long buffer
    "\x00",  # Null byte
    "A\x00B",  # Injected null byte
    "'; DROP TABLE users; --",  # SQL injection
    "\" OR 1=1 --",  # SQL injection
    "<script>alert(1)</script>",  # XSS payload
    "<img src=x onerror=alert(1)>",  # XSS payload
    "../../etc/passwd",  # Directory traversal
    "..\\..\\windows\\win.ini",  # Directory traversal (Windows)
    "; rm -rf / ;",  # Command injection
    "& dir &",  # Command injection (Windows)
    "%s%d%x%n",  # Format string
    "\\u0000",  # Unicode null
    "😊" * 100,  # Multi-byte emojis
    "NaN",
    "Infinity",
    "-Infinity"
]

FUZZ_NUMBERS = [
    0,
    -1,
    1,
    2147483647,  # Max 32-bit signed int
    -2147483648,  # Min 32-bit signed int
    9223372036854775807,  # Max 64-bit signed int
    -9223372036854775808,  # Min 64-bit signed int
    0.0,
    -0.0,
    1e-30,  # Tiny float
    1e+30,  # Large float
    float('nan'),
    float('inf'),
    float('-inf')
]


def mutate_value(val):
    """Applies a random mutation to a single primitive value."""
    if isinstance(val, bool):
        return not val
    elif isinstance(val, (int, float)):
        # 80% chance to replace with a standard fuzz number, 20% to offset
        if random.random() < 0.8:
            return random.choice(FUZZ_NUMBERS)
        else:
            offset = random.choice([-1, 1, 10, -10, 0.1, -0.1])
            return val + offset
    elif isinstance(val, str):
        # 80% chance to replace with fuzz string, 20% to append fuzz string
        fuzz = random.choice(FUZZ_STRINGS)
        if random.random() < 0.8:
            return fuzz
        else:
            return val + fuzz
    elif val is None:
        return random.choice(["", 0, False])
    return val


def mutate_json(data):
    """Recursively mutates a JSON object or array structure."""
    if isinstance(data, dict):
        if not data:
            return {"fuzz_key": "fuzz_val"}
            
        new_dict = {}
        for k, v in data.items():
            # Randomly delete key (10% chance)
            if random.random() < 0.1:
                continue
                
            # Randomly mutate key name (10% chance)
            if random.random() < 0.1:
                k = mutate_value(k)
                
            new_dict[k] = mutate_json(v)
            
        # Randomly add an extra fuzzed key (10% chance)
        if random.random() < 0.1:
            new_dict["fuzz_extra_" + str(random.randint(1, 100))] = random.choice(FUZZ_STRINGS)
            
        return new_dict
        
    elif isinstance(data, list):
        if not data:
            return [random.choice(FUZZ_STRINGS)]
            
        # Mutate array elements
        new_list = [mutate_json(item) for item in data]
        
        # Randomly duplicate elements or clear list (10% chance)
        if random.random() < 0.1:
            if random.random() < 0.5:
                new_list = new_list * 2
            else:
                new_list = []
        return new_list
        
    else:
        # Primitive value
        return mutate_value(data)


def mutate_csv(rows):
    """Mutates rows of a CSV dataset (retaining headers)."""
    if len(rows) <= 1:
        return rows
        
    headers = rows[0]
    mutated_rows = [headers]
    
    for r_idx in range(1, len(rows)):
        row = rows[r_idx]
        mutated_row = []
        for cell in row:
            # 30% chance to mutate this cell
            if random.random() < 0.3:
                # Try to guess type or treat as string
                try:
                    if '.' in cell:
                        val = float(cell)
                    else:
                        val = int(cell)
                    mutated_cell = str(mutate_value(val))
                except ValueError:
                    if cell.lower() in ('true', 'false'):
                        val = cell.lower() == 'true'
                        mutated_cell = str(mutate_value(val)).lower()
                    else:
                        mutated_cell = str(mutate_value(cell))
                mutated_row.append(mutated_cell)
            else:
                mutated_row.append(cell)
        mutated_rows.append(mutated_row)
        
    return mutated_rows


def main():
    parser = argparse.ArgumentParser(
        description="CSV/JSON Mutation Fuzzer - Generate structural and value-level mutations of seeds."
    )
    parser.add_argument("seed", help="Path to seed CSV or JSON file")
    parser.add_argument("-n", "--count", type=int, default=10, help="Number of mutated files to generate (default: 10)")
    parser.add_argument("-o", "--output-dir", default="fuzz_output", help="Directory to save generated test cases")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.seed):
        print(f"[-] Seed file not found: {args.seed}", file=sys.stderr)
        return 1
        
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Identify type
    is_json = args.seed.endswith(".json")
    is_csv = args.seed.endswith(".csv")
    
    if not is_json and not is_csv:
        # Try to infer by parsing
        try:
            with open(args.seed, "r", encoding="utf-8") as f:
                json.load(f)
            is_json = True
        except ValueError:
            is_csv = True
            
    # Read seed content
    try:
        with open(args.seed, "r", encoding="utf-8", newline="") as f:
            if is_json:
                seed_data = json.load(f)
            else:
                reader = csv.reader(f)
                seed_data = list(reader)
    except Exception as e:
        print(f"[-] Error reading seed file: {e}", file=sys.stderr)
        return 1
        
    print(f"[*] Read seed: {args.seed} ({'JSON' if is_json else 'CSV'})")
    print(f"[*] Generating {args.count} mutations in directory '{args.output_dir}'...")
    
    for idx in range(1, args.count + 1):
        ext = ".json" if is_json else ".csv"
        out_path = os.path.join(args.output_dir, f"fuzzed_{idx:03d}{ext}")
        
        try:
            if is_json:
                mutated = mutate_json(seed_data)
                with open(out_path, "w", encoding="utf-8") as out_file:
                    json.dump(mutated, out_file, indent=2, default=str)
            else:
                mutated = mutate_csv(seed_data)
                with open(out_path, "w", encoding="utf-8", newline="") as out_file:
                    writer = csv.writer(out_file)
                    writer.writerows(mutated)
        except Exception as e:
            print(f"[-] Error generating mutation {idx}: {e}", file=sys.stderr)
            continue
            
    print(f"[+] Successfully generated {args.count} mutated test cases in '{args.output_dir}'!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
