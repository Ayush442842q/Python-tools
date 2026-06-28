#!/usr/bin/env python3
"""
CSV Data Synthesizer

Scans an input CSV file to analyze column types and distributions, and then
generates a synthetic dataset of any size that mimics the original data structure.

Usage:
    python tools/csv_data_synthesizer.py input.csv -o synthetic_output.csv -n 500
"""

import os
import sys
import csv
import random
import re
import argparse
from datetime import datetime, timedelta
from collections import Counter
from typing import List, Dict, Any, Tuple

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_colored(text: str, color: str):
    """Print text with ANSI color if stdout is a tty."""
    if sys.stdout.isatty():
        print(f"{color}{text}{RESET}")
    else:
        print(text)

class ColumnProfile:
    def __init__(self, name: str):
        self.name = name
        self.total_count = 0
        self.null_count = 0
        self.col_type = "text"  # int, float, date, email, phone, category, text
        self.values: List[str] = []
        
        # Stats
        self.min_val: Any = None
        self.max_val: Any = None
        self.category_weights: Dict[str, float] = {}
        self.mean_length = 0
        
    def analyze(self):
        """Analyzes values to determine types and calculate distributions."""
        if not self.values:
            self.col_type = "text"
            return

        non_null_vals = [v for v in self.values if v.strip()]
        self.null_count = len(self.values) - len(non_null_vals)
        self.total_count = len(self.values)

        if not non_null_vals:
            self.col_type = "text"
            return

        # Attempt to detect type
        is_int = True
        is_float = True
        is_date = True
        is_email = True
        is_phone = True
        
        email_pattern = re.compile(r'[^@]+@[^@]+\.[^@]+')
        phone_pattern = re.compile(r'^\+?[0-9\-\s\(\)\.]{7,20}$')
        date_formats = ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%Y-%m-%d %H:%M:%S']

        detected_date_format = None

        for val in non_null_vals:
            val_strip = val.strip()
            
            # Check integer
            if is_int:
                try:
                    int(val_strip)
                except ValueError:
                    is_int = False
            
            # Check float
            if is_float:
                try:
                    float(val_strip)
                except ValueError:
                    is_float = False
                    
            # Check email
            if is_email:
                if not email_pattern.match(val_strip):
                    is_email = False
                    
            # Check phone
            if is_phone:
                if not phone_pattern.match(val_strip):
                    is_phone = False
            
            # Check date
            if is_date:
                matched_date = False
                if detected_date_format:
                    try:
                        datetime.strptime(val_strip, detected_date_format)
                        matched_date = True
                    except ValueError:
                        pass
                else:
                    for fmt in date_formats:
                        try:
                            datetime.strptime(val_strip, fmt)
                            detected_date_format = fmt
                            matched_date = True
                            break
                        except ValueError:
                            pass
                if not matched_date:
                    is_date = False

        # Assign column type based on analysis
        if is_int:
            self.col_type = "int"
            int_vals = [int(v.strip()) for v in non_null_vals]
            self.min_val = min(int_vals)
            self.max_val = max(int_vals)
        elif is_float:
            self.col_type = "float"
            float_vals = [float(v.strip()) for v in non_null_vals]
            self.min_val = min(float_vals)
            self.max_val = max(float_vals)
        elif is_date:
            self.col_type = "date"
            self.date_format = detected_date_format
            date_vals = [datetime.strptime(v.strip(), self.date_format) for v in non_null_vals]
            self.min_val = min(date_vals)
            self.max_val = max(date_vals)
        elif is_email:
            self.col_type = "email"
        elif is_phone:
            self.col_type = "phone"
        else:
            # Check if categorical (few unique values compared to total size)
            unique_count = len(set(non_null_vals))
            if unique_count < 20 or (unique_count / len(non_null_vals) < 0.15):
                self.col_type = "category"
                counter = Counter(non_null_vals)
                total = sum(counter.values())
                self.category_weights = {k: v / total for k, v in counter.items()}
            else:
                self.col_type = "text"
                self.mean_length = int(sum(len(v) for v in non_null_vals) / len(non_null_vals))

    def generate_value(self) -> str:
        """Generates a random value fitting the calculated distribution."""
        # Decide if null
        if self.total_count > 0 and random.random() < (self.null_count / self.total_count):
            return ""

        if self.col_type == "int":
            return str(random.randint(self.min_val, self.max_val))
            
        elif self.col_type == "float":
            return f"{random.uniform(self.min_val, self.max_val):.4f}"
            
        elif self.col_type == "date":
            delta_seconds = int((self.max_val - self.min_val).total_seconds())
            random_seconds = random.randint(0, max(0, delta_seconds))
            rand_date = self.min_val + timedelta(seconds=random_seconds)
            return rand_date.strftime(self.date_format)
            
        elif self.col_type == "email":
            domains = ["example.com", "test.org", "demo.net", "gmail.com", "yahoo.com"]
            user = "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=8))
            return f"{user}@{random.choice(domains)}"
            
        elif self.col_type == "phone":
            # standard format: +1-555-XXX-XXXX or similar
            return f"+1-{random.randint(200,999)}-{random.randint(200,999)}-{random.randint(1000,9999)}"
            
        elif self.col_type == "category":
            choices = list(self.category_weights.keys())
            weights = list(self.category_weights.values())
            return random.choices(choices, weights=weights)[0]
            
        else: # text
            words = ["lorem", "ipsum", "dolor", "sit", "amet", "consectetur", "adipiscing", "elit", "sed", "do", "eiusmod", "tempor"]
            length = max(5, int(random.gauss(self.mean_length, max(1, self.mean_length // 4))))
            text = " ".join(random.choices(words, k=length // 5 + 1))
            return text[:length].strip()

def synthesize_csv(input_path: str, output_path: str, count: int):
    """Parses input CSV, profiles columns, and writes synthetic CSV."""
    if not os.path.exists(input_path):
        print_colored(f"[-] Error: Input file not found: {input_path}", RED)
        sys.exit(1)

    print_colored(f"[*] Reading and profiling '{input_path}'...", BLUE)
    
    profiles: List[ColumnProfile] = []
    headers: List[str] = []

    try:
        with open(input_path, "r", newline="", encoding="utf-8", errors="ignore") as f:
            reader = csv.reader(f)
            headers = next(reader, [])
            if not headers:
                print_colored("[-] Error: CSV file has no headers or is empty.", RED)
                sys.exit(1)
                
            profiles = [ColumnProfile(name) for name in headers]
            
            for row in reader:
                # Pad row if columns don't match header length
                while len(row) < len(headers):
                    row.append("")
                for i, val in enumerate(row[:len(headers)]):
                    profiles[i].values.append(val)
    except Exception as e:
        print_colored(f"[-] Error parsing CSV: {e}", RED)
        sys.exit(1)

    print_colored("[*] Analyzing column profiles...", BLUE)
    for p in profiles:
        p.analyze()
        print(f"    - Column '{p.name}': Type={p.col_type.upper()}, NullCount={p.null_count}/{p.total_count}")

    print_colored(f"[*] Generating {count} synthetic rows...", BLUE)
    try:
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(headers)
            
            for _ in range(count):
                row = [p.generate_value() for p in profiles]
                writer.writerow(row)
        print_colored(f"[+] Successfully wrote synthetic data to '{output_path}'!", GREEN)
    except Exception as e:
        print_colored(f"[-] Error writing output CSV: {e}", RED)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Create synthetic CSV data matching distribution of input CSV.")
    parser.add_argument("input_csv", help="Source CSV file to analyze")
    parser.add_argument("-o", "--output", required=True, help="Destination CSV file for synthetic data")
    parser.add_argument("-n", "--rows", type=int, default=100, help="Number of rows to generate (default: 100)")
    
    args = parser.parse_args()
    synthesize_csv(args.input_csv, args.output, args.rows)

if __name__ == "__main__":
    main()
