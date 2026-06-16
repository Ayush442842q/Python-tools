#!/usr/bin/env python3
"""
Custom Mock Data Generator

Generates synthetic datasets in CSV, JSON, or SQL format based on user-defined schemas.
Supports auto-incrementing IDs, names, emails, phone numbers, dates, numbers, text, 
custom choices, and UUIDs. Requires no external dependencies (like Faker).

Usage:
    python tools/mock_data_generator.py -n 50 -f csv -s "id:id,name:name,email:email,status:choice[Active|Inactive],score:number[1-100]" -o output.csv
    python tools/mock_data_generator.py -n 5 -f sql --table users -s "id:id,name:name,created_at:date[2020-01-01:2025-12-31]"
"""

import argparse
import csv
import json
import random
import re
import sys
import uuid
from datetime import datetime, timedelta

# Mock lists for generation without external dependencies
FIRST_NAMES = [
    "James", "Mary", "John", "Patricia", "Robert", "Jennifer", "Michael", "Linda", "William", "Elizabeth",
    "David", "Barbara", "Richard", "Susan", "Joseph", "Jessica", "Thomas", "Sarah", "Charles", "Karen",
    "Christopher", "Lisa", "Daniel", "Nancy", "Matthew", "Betty", "Anthony", "Sandra", "Mark", "Margaret",
    "Donald", "Ashley", "Steven", "Kimberly", "Paul", "Emily", "Andrew", "Donna", "Joshua", "Michelle"
]

LAST_NAMES = [
    "Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez",
    "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin",
    "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez", "Lewis", "Robinson",
    "Walker", "Young", "Allen", "King", "Wright", "Scott", "Torres", "Nguyen", "Hill", "Flores"
]

DOMAINS = ["example.com", "test.org", "mockmail.net", "company.io", "web.com"]

LOREM_WORDS = [
    "lorem", "ipsum", "dolor", "sit", "amet", "consectetur", "adipiscing", "elit", "sed", "do", 
    "eiusmod", "tempor", "incididunt", "ut", "labore", "et", "dolore", "magna", "aliqua", "ut", 
    "enim", "ad", "minim", "veniam", "quis", "nostrud", "exercitation", "ullamco", "laboris", "nisi"
]

def generate_name():
    return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"

def generate_email(name):
    clean_name = re.sub(r'[^a-zA-Z0-9]', '', name.lower())
    return f"{clean_name}{random.randint(10, 99)}@{random.choice(DOMAINS)}"

def generate_phone():
    return f"+1-{random.randint(200, 999)}-{random.randint(200, 999)}-{random.randint(1000, 9999)}"

def generate_date(param_str):
    # Default range: past year
    start_date = datetime.now() - timedelta(days=365)
    end_date = datetime.now()
    
    if param_str:
        try:
            parts = param_str.split(':')
            if len(parts) == 2:
                start_date = datetime.strptime(parts[0], "%Y-%m-%d")
                end_date = datetime.strptime(parts[1], "%Y-%m-%d")
        except Exception:
            pass
            
    delta = end_date - start_date
    int_delta = int(delta.total_seconds())
    if int_delta <= 0:
        return start_date.strftime("%Y-%m-%d %H:%M:%S")
    random_second = random.randint(0, int_delta)
    return (start_date + timedelta(seconds=random_second)).strftime("%Y-%m-%d %H:%M:%S")

def generate_number(param_str):
    # Default: 1-100 int
    min_val, max_val = 1, 100
    is_float = False
    
    if param_str:
        try:
            # Parse [1-100] or [1.5-10.5]
            parts = param_str.split('-')
            if len(parts) == 2:
                if '.' in parts[0] or '.' in parts[1]:
                    min_val = float(parts[0])
                    max_val = float(parts[1])
                    is_float = True
                else:
                    min_val = int(parts[0])
                    max_val = int(parts[1])
        except Exception:
            pass
            
    if is_float:
        return round(random.uniform(min_val, max_val), 2)
    return random.randint(int(min_val), int(max_val))

def generate_choice(param_str):
    # Parse options like "Active|Inactive|Pending"
    if not param_str:
        return "Option"
    choices = param_str.split('|')
    return random.choice(choices)

def generate_text(param_str):
    # Default: 10 words
    word_count = 10
    if param_str:
        try:
            word_count = int(param_str)
        except ValueError:
            pass
    words = [random.choice(LOREM_WORDS) for _ in range(word_count)]
    return " ".join(words).capitalize() + "."

def parse_schema(schema_str):
    """
    Parses fields like "name:name,email:email,age:number[18-65],role:choice[Admin|User]"
    Returns a list of dicts: [{'name': 'age', 'type': 'number', 'param': '18-65'}]
    """
    fields = []
    # Match comma separated fields, handling nested brackets
    # E.g. "role:choice[Admin|User],age:number[18-65]"
    pattern = r'([a-zA-Z0-9_]+):([a-zA-Z]+)(?:\[([^\]]+)\])?'
    matches = re.findall(pattern, schema_str)
    
    for name, field_type, param in matches:
        fields.append({
            'name': name,
            'type': field_type.lower(),
            'param': param
        })
    return fields

def generate_dataset(fields, count):
    dataset = []
    for i in range(1, count + 1):
        row = {}
        # Keep track of generated names in this row to link with email if necessary
        row_name = None
        
        for field in fields:
            ftype = field['type']
            fparam = field['param']
            fname = field['name']
            
            if ftype == 'id':
                row[fname] = i
            elif ftype == 'uuid':
                row[fname] = str(uuid.uuid4())
            elif ftype == 'name':
                row_name = generate_name()
                row[fname] = row_name
            elif ftype == 'email':
                # Try to use row's name if we generated it, else make new
                ref_name = row_name or generate_name()
                row[fname] = generate_email(ref_name)
            elif ftype == 'phone':
                row[fname] = generate_phone()
            elif ftype == 'date':
                row[fname] = generate_date(fparam)
            elif ftype == 'number':
                row[fname] = generate_number(fparam)
            elif ftype == 'choice':
                row[fname] = generate_choice(fparam)
            elif ftype == 'text':
                row[fname] = generate_text(fparam)
            elif ftype == 'boolean':
                row[fname] = random.choice([True, False])
            else:
                row[fname] = f"unknown_{ftype}"
        dataset.append(row)
    return dataset

def export_csv(dataset, headers, stream):
    writer = csv.DictWriter(stream, fieldnames=headers)
    writer.writeheader()
    for row in dataset:
        writer.writerow(row)

def export_sql(dataset, headers, table_name, stream):
    for row in dataset:
        cols = []
        vals = []
        for h in headers:
            cols.append(f"`{h}`")
            val = row[h]
            if isinstance(val, (int, float)):
                vals.append(str(val))
            elif isinstance(val, bool):
                vals.append("1" if val else "0")
            elif val is None:
                vals.append("NULL")
            else:
                # Escape single quotes
                escaped = str(val).replace("'", "''")
                vals.append(f"'{escaped}'")
                
        col_str = ", ".join(cols)
        val_str = ", ".join(vals)
        stream.write(f"INSERT INTO `{table_name}` ({col_str}) VALUES ({val_str});\n")

def main():
    parser = argparse.ArgumentParser(description="Custom Mock Data Generator - Generate synthetic datasets in JSON, CSV, or SQL format.")
    parser.add_argument('-n', '--count', type=int, default=10, help='Number of rows to generate (default: 10)')
    parser.add_argument('-f', '--format', choices=['json', 'csv', 'sql'], default='json', help='Output format (default: json)')
    parser.add_argument('-s', '--schema', required=True, 
                        help='Schema definition. Example: "id:id,username:text[1],email:email,status:choice[Active|Inactive],score:number[1-100]"')
    parser.add_argument('--table', default='mock_data', help='SQL table name (default: mock_data)')
    parser.add_argument('-o', '--output', help='Output file path (prints to console if omitted)')

    args = parser.parse_args()

    fields = parse_schema(args.schema)
    if not fields:
        print("❌ Error: Invalid schema format. Please define columns as name:type[parameter].", file=sys.stderr)
        print("Types: id, uuid, name, email, phone, date, number, choice, text, boolean.", file=sys.stderr)
        return 1

    dataset = generate_dataset(fields, args.count)
    headers = [f['name'] for f in fields]

    # Open output stream
    if args.output:
        try:
            stream = open(args.output, 'w', encoding='utf-8', newline='')
        except IOError as e:
            print(f"❌ Error opening output file: {e}", file=sys.stderr)
            return 1
    else:
        stream = sys.stdout

    try:
        if args.format == 'json':
            json.dump(dataset, stream, indent=4)
            if not args.output:
                stream.write('\n')
        elif args.format == 'csv':
            export_csv(dataset, headers, stream)
        elif args.format == 'sql':
            export_sql(dataset, headers, args.table, stream)
    finally:
        if args.output:
            stream.close()
            print(f"🎉 Generated {args.count} mock rows in {args.format.upper()} format and saved to: {args.output}")

    return 0

if __name__ == "__main__":
    sys.exit(main())
