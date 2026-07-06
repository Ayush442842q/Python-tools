#!/usr/bin/env python3
"""
SQL DDL Mock Data Generator - Parses SQL CREATE TABLE statements and generates mock INSERT statements.
Supports mapping column names and types to realistic mock data (names, emails, dates, phones, UUIDs, etc.).
"""

import os
import re
import sys
import random
import argparse
from datetime import datetime, timedelta

# ANSI color codes for TUI
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_BLUE = "\033[94m"
COLOR_RESET = "\033[0m"

def log_success(message):
    print(f"{COLOR_GREEN}[✓] {message}{COLOR_RESET}")

def log_warn(message):
    print(f"{COLOR_YELLOW}[!] {message}{COLOR_RESET}")

def log_error(message):
    print(f"{COLOR_RED}[✗] {message}{COLOR_RESET}", file=sys.stderr)

def log_info(message):
    print(f"{COLOR_BLUE}[i] {message}{COLOR_RESET}")

# Built-in lightweight mock datasets
FIRST_NAMES = ["John", "Jane", "Alice", "Bob", "Charlie", "Diana", "Ethan", "Fiona", "George", "Hannah", "Ian", "Julia", "Kevin", "Laura", "Michael", "Nina", "Oscar", "Penelope", "Quinn", "Ryan", "Sarah", "Thomas", "Ursula", "Victor", "Wendy", "Xavier", "Yolanda", "Zachary"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin", "Lee", "Perez", "Thompson", "White", "Harris", "Sanchez", "Clark", "Ramirez"]
DOMAINS = ["example.com", "testmail.org", "company.net", "webmail.com", "service.io", "domain.co", "app.tech"]
CITIES = ["New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia", "San Antonio", "San Diego", "Dallas", "San Jose", "London", "Paris", "Berlin", "Tokyo", "Sydney", "Toronto"]
COUNTRIES = ["United States", "United Kingdom", "Canada", "Australia", "Germany", "France", "Japan", "India", "Brazil", "South Africa", "Mexico", "Italy", "Spain", "Netherlands"]
WORDS = ["lorem", "ipsum", "dolor", "sit", "amet", "consectetur", "adipiscing", "elit", "sed", "do", "eiusmod", "tempor", "incididunt", "ut", "labore", "et", "dolore", "magna", "aliqua"]

def generate_random_sentence(word_count=5):
    return " ".join(random.choice(WORDS) for _ in range(word_count)).capitalize()

def generate_mock_value(col_name, col_type, row_index, auto_increment=True):
    """Generates mock data for a column based on its name and type rules."""
    col_name_lower = col_name.lower().strip('`"[]')
    col_type_upper = col_type.upper().strip()
    
    # 1. Primary key auto-increment heuristic
    if auto_increment and (col_name_lower == "id" or col_name_lower.endswith("_id")) and ("INT" in col_type_upper or "SERIAL" in col_type_upper):
        return str(row_index + 1)
        
    # 2. Email Heuristic
    if "email" in col_name_lower:
        fn = random.choice(FIRST_NAMES).lower()
        ln = random.choice(LAST_NAMES).lower()
        num = random.randint(10, 99)
        return f"'{fn}.{ln}{num}@{random.choice(DOMAINS)}'"
        
    # 3. First Name Heuristic
    if "first_name" in col_name_lower or "firstname" in col_name_lower:
        return f"'{random.choice(FIRST_NAMES)}'"
        
    # 4. Last Name Heuristic
    if "last_name" in col_name_lower or "lastname" in col_name_lower:
        return f"'{random.choice(LAST_NAMES)}'"
        
    # 5. Full Name Heuristic
    if "name" in col_name_lower:
        return f"'{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}'"
        
    # 6. Phone Heuristic
    if "phone" in col_name_lower or "mobile" in col_name_lower or "tel" in col_name_lower:
        return f"'+1-555-{random.randint(100, 999):03d}-{random.randint(1000, 9999):04d}'"
        
    # 7. City Heuristic
    if "city" in col_name_lower:
        return f"'{random.choice(CITIES)}'"
        
    # 8. Country Heuristic
    if "country" in col_name_lower:
        return f"'{random.choice(COUNTRIES)}'"
        
    # 9. Address Heuristic
    if "address" in col_name_lower:
        num = random.randint(100, 9999)
        street = random.choice(LAST_NAMES)
        suffix = random.choice(["St", "Ave", "Rd", "Dr", "Ln", "Way"])
        return f"'{num} {street} {suffix}'"
        
    # 10. UUID / Token Heuristic
    if "uuid" in col_name_lower or col_type_upper == "UUID" or "guid" in col_name_lower:
        # Standard UUIDv4 structure mock
        part1 = f"{random.randint(0, 0xFFFFFFFF):08x}"
        part2 = f"{random.randint(0, 0xFFFF):04x}"
        part3 = f"4{random.randint(0, 0x0FFF):03x}"
        part4 = f"{random.randint(0x8000, 0xBFFF):04x}"
        part5 = f"{random.randint(0, 0xFFFFFFFFFFFF):012x}"
        return f"'{part1}-{part2}-{part3}-{part4}-{part5}'"
        
    # 11. Date / Timestamp Heuristic
    if "date" in col_name_lower or "time" in col_name_lower or "created_at" in col_name_lower or "updated_at" in col_name_lower or col_type_upper in ["DATE", "DATETIME", "TIMESTAMP"]:
        base_date = datetime.now() - timedelta(days=random.randint(0, 365))
        if col_type_upper == "DATE":
            return f"'{base_date.strftime('%Y-%m-%d')}'"
        else:
            # Add random hour/min/sec
            base_date = base_date.replace(hour=random.randint(0, 23), minute=random.randint(0, 59), second=random.randint(0, 59))
            return f"'{base_date.strftime('%Y-%m-%d %H:%M:%S')}'"
            
    # 12. Price / Money Heuristic
    if "price" in col_name_lower or "amount" in col_name_lower or "salary" in col_name_lower or "cost" in col_name_lower:
        val = round(random.uniform(5.0, 500.0), 2)
        return f"{val}"
        
    # 13. Boolean Heuristic
    if "is_" in col_name_lower or "has_" in col_name_lower or "active" in col_name_lower or col_type_upper == "BOOLEAN" or col_type_upper == "BOOL":
        if col_type_upper in ["BOOLEAN", "BOOL"]:
            return random.choice(["TRUE", "FALSE"])
        return random.choice(["1", "0"])
        
    # 14. Fallbacks by SQL Type
    if "INT" in col_type_upper or "SERIAL" in col_type_upper:
        return str(random.randint(1, 100))
        
    if "FLOAT" in col_type_upper or "DOUBLE" in col_type_upper or "DECIMAL" in col_type_upper or "NUMERIC" in col_type_upper:
        return f"{round(random.uniform(0.0, 100.0), 4)}"
        
    if "CHAR" in col_type_upper or "TEXT" in col_type_upper or "CLOB" in col_type_upper:
        # Default short text
        word = random.choice(WORDS)
        if "VARCHAR" in col_type_upper:
            # Extract length if present, e.g. VARCHAR(255)
            match = re.search(r'VARCHAR\s*\((\d+)\)', col_type_upper)
            if match:
                length = int(match.group(1))
                if length < 10:
                    return f"'{word[:length]}'"
        return f"'{word.title()}'"
        
    # Absolute fallback
    return "NULL"

def parse_ddl_statements(ddl_content):
    """Parses CREATE TABLE DDL commands and returns list of tables with columns details."""
    # Normalize whitespace, remove SQL comments
    ddl_content = re.sub(r'--.*$', '', ddl_content, flags=re.MULTILINE)
    ddl_content = re.sub(r'/\*.*?\*/', '', ddl_content, flags=re.DOTALL)
    
    # Match CREATE TABLE statements block
    table_pattern = re.compile(
        r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_`"\[\]\.]+)\s*\((.*?)\)\s*(?:;|\Z)',
        re.IGNORECASE | re.DOTALL
    )
    
    tables = []
    
    for match in table_pattern.finditer(ddl_content):
        table_name = match.group(1).strip('`"[]')
        columns_block = match.group(2).strip()
        
        # Split columns, being careful with parenthesis (like VARCHAR(255), DECIMAL(10,2))
        columns = []
        paren_depth = 0
        current_col = []
        
        for char in columns_block:
            if char == '(':
                paren_depth += 1
                current_col.append(char)
            elif char == ')':
                paren_depth -= 1
                current_col.append(char)
            elif char == ',' and paren_depth == 0:
                columns.append("".join(current_col).strip())
                current_col = []
            else:
                current_col.append(char)
                
        if current_col:
            columns.append("".join(current_col).strip())
            
        # Parse each column line
        parsed_cols = []
        for col_line in columns:
            col_line_stripped = col_line.strip()
            if not col_line_stripped:
                continue
                
            # Skip table level constraint keywords
            upper_line = col_line_stripped.upper()
            if any(upper_line.startswith(kw) for kw in ["PRIMARY KEY", "FOREIGN KEY", "UNIQUE", "CHECK", "CONSTRAINT", "INDEX"]):
                continue
                
            # Extract column name and type
            # Expected pattern: name type [constraints...]
            # Standard SQL allows quoted/bracketed column names
            tokens = col_line_stripped.split()
            if len(tokens) >= 2:
                col_name = tokens[0]
                # Combine type in case of spacing, e.g. "DOUBLE PRECISION" or "INT UNSIGNED"
                # But stop at first constraint keyword
                col_type_tokens = []
                for t in tokens[1:]:
                    if t.upper() in ["NOT", "NULL", "PRIMARY", "UNIQUE", "DEFAULT", "AUTO_INCREMENT", "REFERENCES", "CHECK"]:
                        break
                    col_type_tokens.append(t)
                col_type = " ".join(col_type_tokens)
                if not col_type:
                    col_type = tokens[1] # fallback
                    
                parsed_cols.append({
                    "name": col_name,
                    "type": col_type,
                    "raw": col_line_stripped
                })
                
        tables.append({
            "name": table_name,
            "columns": parsed_cols
        })
        
    return tables

def generate_mock_inserts(tables, num_rows=10, db_format="SQL"):
    """Generates mock INSERT INTO statements for parsed tables."""
    insert_queries = []
    
    for table in tables:
        table_name = table["name"]
        columns = table["columns"]
        
        if not columns:
            continue
            
        col_names = [col["name"] for col in columns]
        col_names_str = ", ".join(col_names)
        
        insert_queries.append(f"-- Mock data for table: {table_name}")
        
        for i in range(num_rows):
            values = []
            for col in columns:
                val = generate_mock_value(col["name"], col["type"], i)
                # Apply dialect overrides
                if db_format == "POSTGRES" and val in ["TRUE", "FALSE"]:
                    # Postgres boolean literal check (already upper case)
                    pass
                values.append(val)
                
            values_str = ", ".join(values)
            insert_queries.append(f"INSERT INTO {table_name} ({col_names_str}) VALUES ({values_str});")
            
        insert_queries.append("") # Spacer
        
    return "\n".join(insert_queries)

def main():
    parser = argparse.ArgumentParser(description="Generate mock INSERT statements from SQL DDL (CREATE TABLE) statements.")
    parser.add_argument("input", help="Path to SQL DDL input file containing CREATE TABLE statement(s).")
    parser.add_argument("-o", "--output", help="Path to save generated INSERT queries. Prints to terminal if omitted.")
    parser.add_argument("-n", "--rows", type=int, default=10, help="Number of mock rows to generate per table (default: 10).")
    parser.add_argument("-f", "--format", choices=["SQL", "POSTGRES", "SQLITE"], default="SQL", help="SQL Dialect format rules.")
    
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
        
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        log_error(f"Input file not found: {args.input}")
        sys.exit(1)
        
    try:
        with open(args.input, "r", encoding="utf-8") as f:
            ddl_content = f.read()
    except Exception as e:
        log_error(f"Failed to read input file: {e}")
        sys.exit(1)
        
    log_info(f"Parsing SQL DDL: {args.input}")
    
    tables = parse_ddl_statements(ddl_content)
    if not tables:
        log_error("Could not find or parse any valid CREATE TABLE statements in the input file.")
        sys.exit(1)
        
    for t in tables:
        log_info(f"Found table '{t['name']}' with {len(t['columns'])} columns.")
        
    inserts = generate_mock_inserts(tables, num_rows=args.rows, db_format=args.format)
    
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(inserts)
            log_success(f"Generated mock data saved to: {args.output}")
        except Exception as e:
            log_error(f"Failed to write output file: {e}")
            sys.exit(1)
    else:
        print("\n--- GENERATED SQL INSERT QUERIES ---")
        print(inserts)

if __name__ == "__main__":
    main()
