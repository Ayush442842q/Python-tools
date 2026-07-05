#!/usr/bin/env python3
"""
SQL Schema & Migration Drift Detector
Scans SQL migration files, compares schema expectations against an active SQLite database
or dump file, and reports missing tables, column mismatches, and schema drift.
"""

import argparse
import os
import re
import sqlite3
import sys

# Ensure UTF-8 output encoding on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ANSI Colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def extract_schema_from_sql_content(sql_text):
    tables = {}
    indices = set()

    # Normalize comments
    sql_text = re.sub(r"--.*?\n", "\n", sql_text)

    # Extract CREATE TABLE statements
    table_matches = re.finditer(
        r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([`\"'\[]?\w+[`\"'\]]?)\s*\((.*?)\);",
        sql_text,
        re.DOTALL | re.IGNORECASE
    )

    for match in table_matches:
        table_name = match.group(1).strip("`\"'[]").lower()
        body = match.group(2)
        
        columns = {}
        for line in body.split(","):
            line = line.strip()
            if not line or line.upper().startswith(("PRIMARY KEY", "FOREIGN KEY", "CONSTRAINT", "UNIQUE")):
                continue
            parts = line.split()
            if parts:
                col_name = parts[0].strip("`\"'[]").lower()
                col_type = parts[1].upper() if len(parts) > 1 else "TEXT"
                columns[col_name] = col_type

        tables[table_name] = columns

    # Extract CREATE INDEX
    idx_matches = re.finditer(
        r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?([`\"'\[]?\w+[`\"'\]]?)",
        sql_text,
        re.IGNORECASE
    )
    for match in idx_matches:
        indices.add(match.group(1).strip("`\"'[]").lower())

    return tables, indices


def extract_schema_from_sqlite(db_path):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    tables = {}
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tbl_rows = cursor.fetchall()

    for (tbl_name,) in tbl_rows:
        tbl_name_lower = tbl_name.lower()
        cursor.execute(f"PRAGMA table_info('{tbl_name}')")
        cols = {}
        for col in cursor.fetchall():
            c_name = col[1].lower()
            c_type = col[2].upper() if col[2] else "TEXT"
            cols[c_name] = c_type
        tables[tbl_name_lower] = cols

    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%';")
    indices = set(row[0].lower() for row in cursor.fetchall())

    conn.close()
    return tables, indices


def compare_schemas(expected_tables, expected_indices, actual_tables, actual_indices):
    drift_report = {
        "missing_tables": [],
        "extra_tables": [],
        "column_mismatches": [],
        "missing_indices": []
    }

    for t_name, exp_cols in expected_tables.items():
        if t_name not in actual_tables:
            drift_report["missing_tables"].append(t_name)
        else:
            act_cols = actual_tables[t_name]
            missing_cols = []
            type_diffs = []
            for col_n, col_t in exp_cols.items():
                if col_n not in act_cols:
                    missing_cols.append((col_n, col_t))
                elif act_cols[col_n] != col_t:
                    type_diffs.append((col_n, col_t, act_cols[col_n]))

            if missing_cols or type_diffs:
                drift_report["column_mismatches"].append({
                    "table": t_name,
                    "missing_cols": missing_cols,
                    "type_diffs": type_diffs
                })

    for t_name in actual_tables:
        if t_name not in expected_tables:
            drift_report["extra_tables"].append(t_name)

    for idx in expected_indices:
        if idx not in actual_indices:
            drift_report["missing_indices"].append(idx)

    return drift_report


def run_demo():
    expected_sql = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username VARCHAR(50),
    email TEXT,
    created_at TIMESTAMP
);

CREATE TABLE orders (
    id INTEGER PRIMARY KEY,
    user_id INTEGER,
    amount DECIMAL(10,2),
    status TEXT
);

CREATE INDEX idx_users_email ON users(email);
"""

    actual_sql = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    username VARCHAR(50),
    created_at TIMESTAMP
);

CREATE TABLE legacy_data (
    id INTEGER PRIMARY KEY,
    notes TEXT
);
"""

    print(f"{BOLD}{CYAN}=== SQL Migration Drift Detector Demo ==={RESET}\n")
    exp_tables, exp_indices = extract_schema_from_sql_content(expected_sql)
    act_tables, act_indices = extract_schema_from_sql_content(actual_sql)

    report = compare_schemas(exp_tables, exp_indices, act_tables, act_indices)

    print(f"{BOLD}Drift Analysis Summary:{RESET}\n")

    if report["missing_tables"]:
        print(f"{RED}Missing Tables ({len(report['missing_tables'])}):{RESET}")
        for t in report["missing_tables"]:
            print(f"  • {t}")

    if report["extra_tables"]:
        print(f"\n{YELLOW}Extra Tables in Database ({len(report['extra_tables'])}):{RESET}")
        for t in report["extra_tables"]:
            print(f"  • {t}")

    if report["column_mismatches"]:
        print(f"\n{RED}Column Mismatches ({len(report['column_mismatches'])}):{RESET}")
        for item in report["column_mismatches"]:
            print(f"  Table: {BOLD}{item['table']}{RESET}")
            for col_n, col_t in item["missing_cols"]:
                print(f"    - Missing Column: {col_n} ({col_t})")
            for col_n, exp_t, act_t in item["type_diffs"]:
                print(f"    - Type Diff     : {col_n} expected '{exp_t}', found '{act_t}'")

    if report["missing_indices"]:
        print(f"\n{YELLOW}Missing Indices ({len(report['missing_indices'])}):{RESET}")
        for idx in report["missing_indices"]:
            print(f"  • {idx}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Detect SQL schema migration drift between expected migration files and actual database/dump."
    )
    parser.add_argument("--migrations", help="Path to migration SQL file or directory containing .sql files")
    parser.add_argument("--db", help="Path to SQLite database file (.sqlite, .db) or target SQL dump file")
    parser.add_argument("--demo", action="store_true", help="Run self-contained demo")

    args = parser.parse_args()

    if args.demo or not (args.migrations and args.db):
        if not (args.migrations and args.db) and not args.demo:
            print(f"{YELLOW}Migration path and DB target required. Running demo mode...{RESET}\n")
        run_demo()
        return

    # Parse migrations
    expected_tables = {}
    expected_indices = set()

    if os.path.isfile(args.migrations):
        with open(args.migrations, "r", encoding="utf-8") as f:
            t, i = extract_schema_from_sql_content(f.read())
            expected_tables.update(t)
            expected_indices.update(i)
    elif os.path.isdir(args.migrations):
        for root, _, files in os.walk(args.migrations):
            for file in sorted(files):
                if file.endswith(".sql"):
                    with open(os.path.join(root, file), "r", encoding="utf-8") as f:
                        t, i = extract_schema_from_sql_content(f.read())
                        expected_tables.update(t)
                        expected_indices.update(i)

    # Parse actual target
    if args.db.endswith((".db", ".sqlite", ".sqlite3")):
        actual_tables, actual_indices = extract_schema_from_sqlite(args.db)
    else:
        with open(args.db, "r", encoding="utf-8") as f:
            actual_tables, actual_indices = extract_schema_from_sql_content(f.read())

    report = compare_schemas(expected_tables, expected_indices, actual_tables, actual_indices)

    print(f"\n{BOLD}{CYAN}=== SQL Migration Drift Report ==={RESET}\n")

    has_drift = any([report["missing_tables"], report["column_mismatches"], report["missing_indices"]])

    if not has_drift:
        print(f"{GREEN}✓ No schema drift detected! Target database matches migration expectations.{RESET}")
        return

    if report["missing_tables"]:
        print(f"{RED}Missing Tables:{RESET}")
        for t in report["missing_tables"]:
            print(f"  • {t}")

    if report["column_mismatches"]:
        print(f"\n{RED}Column Mismatches:{RESET}")
        for item in report["column_mismatches"]:
            print(f"  Table '{BOLD}{item['table']}{RESET}':")
            for col_n, col_t in item["missing_cols"]:
                print(f"    - Missing Column: {col_n} ({col_t})")
            for col_n, exp_t, act_t in item["type_diffs"]:
                print(f"    - Type Diff     : {col_n} (Expected: {exp_t}, Found: {act_t})")

    if report["missing_indices"]:
        print(f"\n{YELLOW}Missing Indices:{RESET}")
        for idx in report["missing_indices"]:
            print(f"  • {idx}")


if __name__ == "__main__":
    main()
