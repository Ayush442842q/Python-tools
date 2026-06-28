#!/usr/bin/env python3
"""
SQLite Data Anonymizer - Detect and sanitize PII in SQLite databases.

This tool scans a SQLite database, runs heuristics to detect potential
personally identifiable information (PII) columns, and lets the user
interactively mask, hash, nullify, or replace them with mock data.

It generates a sanitized clone of the database to protect production data.

Usage:
    python tools/sqlite_data_anonymizer.py INPUT_DB [OUTPUT_DB] [--auto-detect]
"""

import argparse
import hashlib
import os
import random
import re
import shutil
import sqlite3
import sys


def init_colors():
    if sys.stdout.isatty() and os.name == 'nt':
        os.system('')
    use_color = sys.stdout.isatty()
    return {
        "green": "\033[92m" if use_color else "",
        "red": "\033[91m" if use_color else "",
        "yellow": "\033[93m" if use_color else "",
        "blue": "\033[94m" if use_color else "",
        "cyan": "\033[96m" if use_color else "",
        "bold": "\033[1m" if use_color else "",
        "reset": "\033[0m" if use_color else ""
    }


COLORS = init_colors()

# Mock lists for faking data
F_NAMES = ["John", "Jane", "Alice", "Bob", "Charlie", "Diana", "Ethan", "Fiona", "George", "Hannah", "Ian", "Julia"]
L_NAMES = ["Smith", "Doe", "Johnson", "Brown", "Davis", "Miller", "Wilson", "Moore", "Taylor", "Anderson", "Thomas"]
DOMAINS = ["example.com", "mockmail.net", "testco.org", "sandbox.io", "localhost.dev"]
CITIES = ["New York", "London", "Paris", "Tokyo", "Berlin", "Sydney", "Toronto", "San Francisco", "Austin", "Seattle"]
STREETS = ["Broadway", "High St", "Main St", "Park Ave", "Maple Dr", "Oak Rd", "Pine Ln", "Sunset Blvd", "Elm St"]


def get_mock_name(row_id):
    random.seed(row_id)
    return f"{random.choice(F_NAMES)} {random.choice(L_NAMES)}"


def get_mock_email(row_id):
    random.seed(row_id)
    first = random.choice(F_NAMES).lower()
    last = random.choice(L_NAMES).lower()
    domain = random.choice(DOMAINS)
    return f"{first}.{last}{row_id % 100}@{domain}"


def get_mock_phone(row_id):
    random.seed(row_id)
    return f"+1-555-{random.randint(100, 999):03d}-{random.randint(1000, 9999):04d}"


def get_mock_address(row_id):
    random.seed(row_id)
    number = random.randint(100, 9999)
    street = random.choice(STREETS)
    city = random.choice(CITIES)
    zip_code = random.randint(10000, 99999)
    return f"{number} {street}, {city} {zip_code}"


def get_mock_ip(row_id):
    random.seed(row_id)
    return f"192.168.{random.randint(1, 254)}.{random.randint(1, 254)}"


# Heuristic patterns for PII detection
PII_PATTERNS = {
    "email": re.compile(r"(email|mail|e_mail|addr_email|mailbox)", re.IGNORECASE),
    "phone": re.compile(r"(phone|tel|mobile|cell|fax|contact|phone_num)", re.IGNORECASE),
    "name": re.compile(r"(name|first_name|last_name|fname|lname|username|nick|surname|fullname)", re.IGNORECASE),
    "address": re.compile(r"(address|street|city|zip|postal|state|country|location)", re.IGNORECASE),
    "ip": re.compile(r"(ip|ip_addr|ip_address|ipv4|ipv6|host_ip)", re.IGNORECASE),
    "password": re.compile(r"(password|pass|passwd|hash|salt|secret|token|credential|key)", re.IGNORECASE)
}


def detect_pii_type(col_name, sample_val=None):
    """Detects if a column is a potential PII column and returns its category."""
    # Check column name heuristics
    for pii_type, pattern in PII_PATTERNS.items():
        if pattern.search(col_name):
            return pii_type
            
    # Check sample value heuristics if available
    if sample_val and isinstance(sample_val, str):
        if "@" in sample_val and "." in sample_val:
            return "email"
        if re.match(r"^\+?[\d\s\-()]{7,20}$", sample_val):
            return "phone"
        if re.match(r"^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$", sample_val):
            return "ip"
            
    return None


def get_schema_info(db_path):
    """Extracts tables, columns, and sample values from database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get all tables
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [r[0] for r in cursor.fetchall() if r[0] != 'sqlite_sequence']
    
    schema = {}
    
    for table in tables:
        # Get column info
        cursor.execute(f"PRAGMA table_info({table});")
        cols = cursor.fetchall()
        
        # Get primary key or rowid
        pk_cols = [c[1] for c in cols if c[5] > 0]
        pk = pk_cols[0] if pk_cols else "rowid"
        
        col_details = []
        for col in cols:
            col_id, col_name, col_type, not_null, default_val, is_pk = col
            
            # Fetch a sample value
            try:
                cursor.execute(f"SELECT {col_name} FROM {table} WHERE {col_name} IS NOT NULL LIMIT 1;")
                row = cursor.fetchone()
                sample = row[0] if row else None
            except sqlite3.Error:
                sample = None
                
            detected = detect_pii_type(col_name, sample)
            
            col_details.append({
                "name": col_name,
                "type": col_type,
                "is_pk": is_pk > 0,
                "sample": sample,
                "detected": detected
            })
            
        schema[table] = {
            "pk": pk,
            "columns": col_details
        }
        
    conn.close()
    return schema


def apply_anonymization(db_path, anonymize_plan):
    """Executes the anonymization changes on the target database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Enable writing
    conn.isolation_level = None
    cursor.execute("PRAGMA foreign_keys = OFF;")
    
    for table, columns in anonymize_plan.items():
        if not columns:
            continue
            
        # Get primary key / identifier column
        cursor.execute(f"PRAGMA table_info({table});")
        cols = cursor.fetchall()
        pk_cols = [c[1] for c in cols if c[5] > 0]
        pk_col = pk_cols[0] if pk_cols else "rowid"
        
        # Select identifier and columns to update
        update_cols = list(columns.keys())
        select_cols = [pk_col] + update_cols
        
        cursor.execute(f"SELECT {', '.join(select_cols)} FROM {table};")
        rows = cursor.fetchall()
        
        total_rows = len(rows)
        if total_rows == 0:
            continue
            
        print(f"Anonymizing table {COLORS['bold']}{table}{COLORS['reset']} ({total_rows} rows)...")
        
        # Prepare updates batch by batch to prevent locks
        updates = []
        for idx, row in enumerate(rows):
            pk_val = row[0]
            val_updates = {}
            
            for col_idx, col_name in enumerate(update_cols, 1):
                strategy = columns[col_name]
                orig_val = row[col_idx]
                
                if orig_val is None:
                    val_updates[col_name] = None
                    continue
                    
                row_seed = idx + 1
                
                if strategy == 'fake_name':
                    val_updates[col_name] = get_mock_name(row_seed)
                elif strategy == 'fake_email':
                    val_updates[col_name] = get_mock_email(row_seed)
                elif strategy == 'fake_phone':
                    val_updates[col_name] = get_mock_phone(row_seed)
                elif strategy == 'fake_address':
                    val_updates[col_name] = get_mock_address(row_seed)
                elif strategy == 'fake_ip':
                    val_updates[col_name] = get_mock_ip(row_seed)
                elif strategy == 'hash':
                    val_updates[col_name] = hashlib.sha256(str(orig_val).encode('utf-8')).hexdigest()[:20]
                elif strategy == 'mask_email':
                    if '@' in str(orig_val):
                        parts = str(orig_val).split('@', 1)
                        masked_user = parts[0][0] + '****' if len(parts[0]) > 1 else '*'
                        val_updates[col_name] = f"{masked_user}@{parts[1]}"
                    else:
                        val_updates[col_name] = '****@example.com'
                elif strategy == 'mask_phone':
                    val_updates[col_name] = re.sub(r'\d', '*', str(orig_val))[:-4] + str(orig_val)[-4:] if len(str(orig_val)) > 4 else '****'
                elif strategy == 'nullify':
                    val_updates[col_name] = None
                elif strategy == 'scramble':
                    s = list(str(orig_val))
                    random.seed(row_seed)
                    random.shuffle(s)
                    val_updates[col_name] = "".join(s)
                else:
                    val_updates[col_name] = orig_val
            
            # Create update statement
            set_clause = ", ".join([f"{k} = ?" for k in val_updates.keys()])
            bind_values = list(val_updates.values()) + [pk_val]
            
            updates.append((set_clause, bind_values))
            
        # Execute updates in a transaction
        cursor.execute("BEGIN TRANSACTION;")
        try:
            for clause, binds in updates:
                cursor.execute(f"UPDATE {table} SET {clause} WHERE {pk_col} = ?;", binds)
            cursor.execute("COMMIT;")
        except sqlite3.Error as e:
            cursor.execute("ROLLBACK;")
            print(f"{COLORS['red']}[!] Error updating database: {e}{COLORS['reset']}")
            conn.close()
            return False
            
    cursor.execute("PRAGMA foreign_keys = ON;")
    # Vacuum database to shrink size and clear old data slack space
    print("Vacuuming database to wipe trace of deleted variables...")
    cursor.execute("VACUUM;")
    conn.close()
    return True


def prompt_strategy(col_name, pii_type, sample):
    """Prompts the user to pick an anonymization strategy for a column."""
    strategies = {
        'n': ('nullify', 'Nullify (replace with NULL)'),
        'h': ('hash', 'SHA-256 Hash first 20 chars'),
        's': ('scramble', 'Scramble character order'),
        'k': ('keep', 'Keep original value (No change)')
    }
    
    # Specific options based on PII category
    faking_opts = {}
    if pii_type == 'name':
        faking_opts = {'f': ('fake_name', 'Fake Name (e.g. John Smith)')}
    elif pii_type == 'email':
        faking_opts = {
            'f': ('fake_email', 'Fake Email (e.g. john.smith44@example.com)'),
            'm': ('mask_email', 'Mask Email (e.g. j****@domain.com)')
        }
    elif pii_type == 'phone':
        faking_opts = {
            'f': ('fake_phone', 'Fake Phone (e.g. +1-555-019-2831)'),
            'm': ('mask_phone', 'Mask Phone (e.g. ***-***-1234)')
        }
    elif pii_type == 'address':
        faking_opts = {'f': ('fake_address', 'Fake Address (e.g. 123 Main St, London 58319)')}
    elif pii_type == 'ip':
        faking_opts = {'f': ('fake_ip', 'Fake IP Address (e.g. 192.168.4.15)')}
    elif pii_type == 'password':
        faking_opts = {'f': ('hash', 'Cryptographic Hash (SHA-256)')}
        
    all_opts = {}
    all_opts.update(faking_opts)
    all_opts.update(strategies)
    
    print(f"\nColumn: {COLORS['cyan']}{COLORS['bold']}{col_name}{COLORS['reset']} (Detected type: {COLORS['yellow']}{pii_type or 'Unknown'}{COLORS['reset']})")
    print(f"Sample Value: {COLORS['bold']}{sample}{COLORS['reset']}")
    
    # Display options
    default_opt = 'k'
    if pii_type in ('name', 'email', 'phone', 'address', 'ip'):
        default_opt = 'f'
    elif pii_type == 'password':
        default_opt = 'h'
        
    for k, (_, desc) in all_opts.items():
        opt_str = f"[{k}]"
        if k == default_opt:
            opt_str = f"*{COLORS['green']}{opt_str}{COLORS['reset']}"
        print(f"  {opt_str} {desc}")
        
    while True:
        choice = input(f"Choose option [default={default_opt}]: ").strip().lower()
        if not choice:
            choice = default_opt
            
        if choice in all_opts:
            return all_opts[choice][0]
        print(f"{COLORS['red']}Invalid choice.{COLORS['reset']}")


def main():
    parser = argparse.ArgumentParser(description="SQLite Database PII Anonymizer")
    parser.add_argument("input_db", help="Path to input SQLite database file")
    parser.add_argument("output_db", nargs="?", help="Path to output SQLite database file (creates copy)")
    parser.add_argument("--auto", action="store_true", help="Automatically anonymize detected columns without prompting")
    args = parser.parse_args()

    in_db = os.path.abspath(args.input_db)
    if not os.path.exists(in_db):
        print(f"{COLORS['red']}[!] File does not exist: {in_db}{COLORS['reset']}")
        sys.exit(1)
        
    out_db = args.output_db
    if not out_db:
        base, ext = os.path.splitext(in_db)
        out_db = f"{base}_anonymized{ext}"
    out_db = os.path.abspath(out_db)
    
    if in_db == out_db:
        choice = input(f"{COLORS['red']}[!] WARNING: Output path is same as input. Overwrite original? [y/N]: {COLORS['reset']}").strip().lower()
        if choice not in ('y', 'yes'):
            print("Operation canceled.")
            sys.exit(0)
    else:
        print(f"Creating sandbox copy of database: {COLORS['green']}{os.path.basename(out_db)}{COLORS['reset']}")
        shutil.copyfile(in_db, out_db)
        
    print(f"\nAnalyzing schema of: {os.path.basename(out_db)}...")
    try:
        schema = get_schema_info(out_db)
    except sqlite3.Error as e:
        print(f"{COLORS['red']}[!] Failed to open database schema: {e}{COLORS['reset']}")
        if in_db != out_db:
            os.remove(out_db)
        sys.exit(1)
        
    anonymize_plan = {}
    
    # Build plan
    for table, info in schema.items():
        table_plan = {}
        columns = info["columns"]
        
        has_pii = any(col["detected"] is not None for col in columns)
        if not has_pii and args.auto:
            continue
            
        print(f"\n==========================================")
        print(f"Table: {COLORS['bold']}{COLORS['cyan']}{table}{COLORS['reset']}")
        print(f"==========================================")
        
        for col in columns:
            if col["is_pk"]:
                continue
                
            # If auto-anonymizing, use default strategies
            if args.auto:
                if col["detected"]:
                    # Select default strategy
                    if col["detected"] == "name":
                        table_plan[col["name"]] = "fake_name"
                    elif col["detected"] == "email":
                        table_plan[col["name"]] = "fake_email"
                    elif col["detected"] == "phone":
                        table_plan[col["name"]] = "fake_phone"
                    elif col["detected"] == "address":
                        table_plan[col["name"]] = "fake_address"
                    elif col["detected"] == "ip":
                        table_plan[col["name"]] = "fake_ip"
                    elif col["detected"] == "password":
                        table_plan[col["name"]] = "hash"
                    print(f"  Column {col['name']} -> Automatically applying '{table_plan[col['name']]}'")
                continue
                
            # Prompt user
            strategy = prompt_strategy(col["name"], col["detected"], col["sample"])
            if strategy != 'keep':
                table_plan[col["name"]] = strategy
                
        if table_plan:
            anonymize_plan[table] = table_plan
            
    if not anonymize_plan:
        print(f"\n{COLORS['green']}No columns selected for anonymization. Database remains unchanged.{COLORS['reset']}")
        if in_db != out_db:
            os.remove(out_db)
        return
        
    # Execute plan
    print(f"\n{COLORS['bold']}{COLORS['yellow']}Starting anonymization process...{COLORS['reset']}")
    success = apply_anonymization(out_db, anonymize_plan)
    
    if success:
        print(f"\n{COLORS['bold']}{COLORS['green']}Anonymization complete!{COLORS['reset']}")
        print(f"Sanitized database saved to: {COLORS['cyan']}{out_db}{COLORS['reset']}")
    else:
        print(f"\n{COLORS['red']}[!] Anonymization failed!{COLORS['reset']}")
        if in_db != out_db:
            try:
                os.remove(out_db)
            except OSError:
                pass


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{COLORS['yellow']}Anonymization canceled.{COLORS['reset']}")
        sys.exit(1)
