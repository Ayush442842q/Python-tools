#!/usr/bin/env python3
"""
SQLite Data Quality Auditor
Analyzes SQLite databases for dynamic data type mismatches (e.g. text in integer columns),
null/empty value rates, foreign key violations, and column format anomalies (like emails/timestamps).
"""

import sqlite3
import re
import argparse
import os
import sys
from typing import Dict, List, Tuple, Any

# Common format regexes
EMAIL_RE = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
TIMESTAMP_RE = re.compile(r'^\d{4}-\d{2}-\d{2}(?:\s|T)\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?$')


def get_tables(conn: sqlite3.Connection) -> List[str]:
    """Get list of user-defined tables in the database."""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    return [row[0] for row in cursor.fetchall()]


def get_table_schema(conn: sqlite3.Connection, table: str) -> List[Dict[str, Any]]:
    """Get schema info for a specific table."""
    cursor = conn.cursor()
    cursor.execute(f"PRAGMA table_info({table});")
    schema = []
    # PRAGMA table_info returns: cid, name, type, notnull, dflt_value, pk
    for row in cursor.fetchall():
        schema.append({
            'cid': row[0],
            'name': row[1],
            'declared_type': row[2].upper(),
            'notnull': bool(row[3]),
            'pk': bool(row[5])
        })
    return schema


def audit_table(conn: sqlite3.Connection, table: str, schema: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Perform data quality checks on a single table."""
    cursor = conn.cursor()
    
    # Get total row count
    cursor.execute(f"SELECT COUNT(*) FROM {table};")
    total_rows = cursor.fetchone()[0]
    
    col_stats = {}
    for col in schema:
        col_name = col['name']
        declared_type = col['declared_type']
        
        col_stats[col_name] = {
            'declared_type': declared_type or 'BLOB/NONE',
            'null_count': 0,
            'empty_string_count': 0,
            'type_mismatches': 0,
            'format_anomalies': 0,
            'type_distribution': {}
        }
        
    if total_rows == 0:
        return {'total_rows': 0, 'column_stats': col_stats, 'fk_errors': []}

    # Retrieve all data for scanning
    cursor.execute(f"SELECT {', '.join(col['name'] for col in schema)} FROM {table};")
    rows = cursor.fetchall()
    
    for row in rows:
        for idx, val in enumerate(row):
            col_info = schema[idx]
            col_name = col_info['name']
            stats = col_stats[col_name]
            
            # 1. Null check
            if val is None:
                stats['null_count'] += 1
                stats['type_distribution']['NULL'] = stats['type_distribution'].get('NULL', 0) + 1
                continue
                
            # Track actual python datatype
            py_type = type(val).__name__
            stats['type_distribution'][py_type] = stats['type_distribution'].get(py_type, 0) + 1
            
            # 2. Empty string check
            if isinstance(val, str) and val.strip() == '':
                stats['empty_string_count'] += 1
                
            # 3. Dynamic Type Mismatch Check (SQLite dynamic typing allows inserting anything)
            declared = col_info['declared_type']
            if declared:
                mismatch = False
                # Approximate SQLite types affinities: INT/INTEGER, REAL/FLOAT, TEXT/VARCHAR, BLOB
                if 'INT' in declared and not isinstance(val, int):
                    mismatch = True
                elif ('REAL' in declared or 'FLOAT' in declared) and not isinstance(val, (int, float)):
                    mismatch = True
                elif ('CHAR' in declared or 'TEXT' in declared or 'CLOB' in declared) and not isinstance(val, str):
                    mismatch = True
                elif 'BLOB' in declared and not isinstance(val, bytes):
                    mismatch = True
                    
                if mismatch:
                    stats['type_mismatches'] += 1
                    
            # 4. Format checks based on column names (heuristic)
            if isinstance(val, str) and val.strip():
                col_lower = col_name.lower()
                if 'email' in col_lower and not EMAIL_RE.match(val):
                    stats['format_anomalies'] += 1
                elif ('time' in col_lower or 'date' in col_lower) and not TIMESTAMP_RE.match(val):
                    # Check if it's a timestamp, otherwise flag as potential format anomaly
                    stats['format_anomalies'] += 1

    # Check foreign key violations for this table
    fk_errors = []
    cursor.execute(f"PRAGMA foreign_key_check({table});")
    # Returns: table, rowid, parent, fkid
    for row in cursor.fetchall():
        fk_errors.append({
            'rowid': row[1],
            'parent_table': row[2],
            'fkid': row[3]
        })
        
    return {
        'total_rows': total_rows,
        'column_stats': col_stats,
        'fk_errors': fk_errors
    }


def main():
    parser = argparse.ArgumentParser(description="Audit data quality of a SQLite database.")
    parser.add_argument("db_path", help="Path to the SQLite database file")
    parser.add_argument("--tables", nargs="*", help="Limit audit to specific tables")
    parser.add_argument("--verbose", action="store_true", help="Print detailed columns breakdown")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.db_path):
        print(f"Error: Database file not found: {args.db_path}", file=sys.stderr)
        sys.exit(1)
        
    try:
        conn = sqlite3.connect(args.db_path)
    except sqlite3.Error as e:
        print(f"SQLite connection error: {e}", file=sys.stderr)
        sys.exit(1)
        
    tables = args.tables or get_tables(conn)
    
    print("====================================================")
    print(f"        SQLITE DATA QUALITY AUDIT REPORT")
    print(f"  Database: {os.path.basename(args.db_path)}")
    print("====================================================\n")
    
    all_passed = True
    
    for table in tables:
        try:
            schema = get_table_schema(conn, table)
            audit_res = audit_table(conn, table, schema)
        except sqlite3.Error as e:
            print(f"[-] Error auditing table '{table}': {e}\n")
            continue
            
        total_rows = audit_res['total_rows']
        col_stats = audit_res['column_stats']
        fk_errors = audit_res['fk_errors']
        
        has_warnings = False
        table_report = []
        
        table_report.append(f"Table: {table} ({total_rows} rows)")
        table_report.append("-" * (len(table) + 15))
        
        # Check foreign key violations
        if fk_errors:
            has_warnings = True
            table_report.append(f"  [!] Foreign Key Violations: {len(fk_errors)} rows orphaned!")
            for err in fk_errors[:3]:  # Show first 3
                table_report.append(f"      RowID {err['rowid']} failed constraint for parent table '{err['parent_table']}'")
            if len(fk_errors) > 3:
                table_report.append(f"      ... and {len(fk_errors) - 3} more")
                
        # Scan column statistics
        for col_name, stats in col_stats.items():
            col_warnings = []
            
            # Check Null rates
            if stats['null_count'] > 0:
                null_rate = (stats['null_count'] / total_rows) * 100
                if null_rate > 50.0:  # Warn if more than 50% are Null
                    col_warnings.append(f"High Null rate ({null_rate:.1f}%)")
                    
            # Check empty strings
            if stats['empty_string_count'] > 0:
                col_warnings.append(f"{stats['empty_string_count']} empty strings")
                
            # Type mismatches
            if stats['type_mismatches'] > 0:
                col_warnings.append(f"{stats['type_mismatches']} dynamic type mismatches")
                
            # Format anomalies
            if stats['format_anomalies'] > 0:
                col_warnings.append(f"{stats['format_anomalies']} formatting anomalies (email/date format)")
                
            if col_warnings or args.verbose:
                has_warnings = True
                warning_str = ", ".join(col_warnings) if col_warnings else "Healthy"
                prefix = "[!]" if col_warnings else "[+]"
                table_report.append(f"  {prefix} Column: {col_name} (Declared: {stats['declared_type']})")
                table_report.append(f"      Actual Types: {stats['type_distribution']}")
                if col_warnings:
                    table_report.append(f"      Issues: {warning_str}")
                    
        if has_warnings:
            all_passed = False
            for line in table_report:
                print(line)
            print()
        else:
            print(f"[+] Table: {table} ({total_rows} rows) - All columns clean & healthy.\n")
            
    conn.close()
    
    if all_passed:
        print("====================================================")
        print("  [SUCCESS] Database data quality looks pristine!")
        print("====================================================")
    else:
        print("====================================================")
        print("  [WARNING] Data quality issues detected. Review above.")
        print("====================================================")


if __name__ == "__main__":
    main()
