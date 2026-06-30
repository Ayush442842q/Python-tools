#!/usr/bin/env python3
"""
SQLite Database Storage & Space Analyzer
A command-line tool to analyze a SQLite database file, reporting table and index space usage,
row counts, average row sizes, freelist space, and optimization suggestions.
"""

import os
import sys
import sqlite3
import argparse

def get_db_info(conn):
    """Retrieve basic database parameters."""
    cursor = conn.cursor()
    cursor.execute("PRAGMA page_size")
    page_size = cursor.fetchone()[0]
    
    cursor.execute("PRAGMA page_count")
    page_count = cursor.fetchone()[0]
    
    cursor.execute("PRAGMA freelist_count")
    freelist_count = cursor.fetchone()[0]
    
    cursor.execute("PRAGMA auto_vacuum")
    auto_vacuum = cursor.fetchone()[0]
    
    cursor.execute("PRAGMA encoding")
    encoding = cursor.fetchone()[0]
    
    return {
        "page_size": page_size,
        "page_count": page_count,
        "freelist_count": freelist_count,
        "auto_vacuum": auto_vacuum,
        "encoding": encoding
    }

def get_tables_and_indexes(conn):
    """Retrieve list of user tables and indexes."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT type, name, tbl_name, sql 
        FROM sqlite_schema 
        WHERE name NOT LIKE 'sqlite_%' AND name IS NOT NULL
    """)
    rows = cursor.fetchall()
    tables = []
    indexes = []
    for r_type, name, tbl_name, sql in rows:
        if r_type == 'table':
            tables.append({"name": name, "sql": sql})
        elif r_type == 'index':
            indexes.append({"name": name, "tbl_name": tbl_name, "sql": sql})
    return tables, indexes

def check_dbstat(conn):
    """Check if the dbstat virtual table module is available in this SQLite build."""
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM sqlite_dbstat LIMIT 1")
        return True
    except sqlite3.OperationalError:
        return False

def analyze_with_dbstat(conn, db_info):
    """Analyze space distribution using sqlite_dbstat."""
    cursor = conn.cursor()
    cursor.execute("""
        SELECT name, 
               sum(pgsize) as bytes, 
               count(*) as pages,
               sum(CASE WHEN pagetype='overflow' THEN 1 ELSE 0 END) as overflow_pages
        FROM sqlite_dbstat
        GROUP BY name
        ORDER BY bytes DESC
    """)
    dbstat_rows = cursor.fetchall()
    
    stats = {}
    for name, bytes_used, pages, overflow in dbstat_rows:
        stats[name] = {
            "bytes": bytes_used,
            "pages": pages,
            "overflow_pages": overflow
        }
    return stats

def main():
    parser = argparse.ArgumentParser(description="SQLite Database Storage & Space Analyzer")
    parser.add_argument("db_file", help="Path to the SQLite database file")
    args = parser.parse_args()

    if not os.path.exists(args.db_file):
        print(f"Error: Database file '{args.db_file}' does not exist.")
        sys.exit(1)

    file_size = os.path.getsize(args.db_file)
    if file_size == 0:
        print(f"Database '{args.db_file}' is an empty file (0 bytes).")
        sys.exit(0)

    try:
        conn = sqlite3.connect(args.db_file)
    except Exception as e:
        print(f"Error: Could not open database file: {e}")
        sys.exit(1)

    try:
        db_info = get_db_info(conn)
        tables, indexes = get_tables_and_indexes(conn)
        
        has_dbstat = check_dbstat(conn)
        dbstat_stats = analyze_with_dbstat(conn, db_info) if has_dbstat else {}
        
        # Calculate sizes and row counts
        table_reports = []
        cursor = conn.cursor()
        
        for t in tables:
            t_name = t["name"]
            try:
                cursor.execute(f"SELECT COUNT(*) FROM [{t_name}]")
                row_count = cursor.fetchone()[0]
            except Exception:
                row_count = "N/A"
                
            bytes_used = dbstat_stats.get(t_name, {}).get("bytes", "N/A")
            pages_used = dbstat_stats.get(t_name, {}).get("pages", "N/A")
            overflow_pages = dbstat_stats.get(t_name, {}).get("overflow_pages", "N/A")
            
            table_reports.append({
                "name": t_name,
                "rows": row_count,
                "bytes": bytes_used,
                "pages": pages_used,
                "overflow": overflow_pages
            })
            
        index_reports = []
        for idx in indexes:
            idx_name = idx["name"]
            tbl_name = idx["tbl_name"]
            bytes_used = dbstat_stats.get(idx_name, {}).get("bytes", "N/A")
            pages_used = dbstat_stats.get(idx_name, {}).get("pages", "N/A")
            
            index_reports.append({
                "name": idx_name,
                "table": tbl_name,
                "bytes": bytes_used,
                "pages": pages_used
            })

    except Exception as e:
        print(f"Error reading database metadata: {e}")
        conn.close()
        sys.exit(1)
        
    conn.close()

    # Output Summary Report
    print("=" * 65)
    print(f" SQLITE STORAGE REPORT: {os.path.basename(args.db_file)}")
    print("=" * 65)
    print(f"File Path:       {args.db_file}")
    print(f"File Size:       {file_size:,} bytes")
    print(f"Page Size:       {db_info['page_size']} bytes")
    print(f"Total Pages:     {db_info['page_count']}")
    
    freelist_pct = (db_info['freelist_count'] / db_info['page_count'] * 100) if db_info['page_count'] > 0 else 0
    freelist_bytes = db_info['freelist_count'] * db_info['page_size']
    print(f"Freelist Pages:  {db_info['freelist_count']} ({freelist_pct:.2f}% of file - {freelist_bytes:,} bytes free)")
    print(f"Database Encoding: {db_info['encoding']}")
    
    auto_vac_modes = {0: "NONE", 1: "FULL", 2: "INCREMENTAL"}
    print(f"Auto Vacuum:     {auto_vac_modes.get(db_info['auto_vacuum'], 'UNKNOWN')}")
    print(f"Analysis Method: {'dbstat extension (highly accurate)' if has_dbstat else 'Basic schema inspection (no dbstat)'}")
    print("-" * 65)
    
    print("\nTABLES SUMMARY:")
    print(f"{'Table Name':<25} | {'Rows':>10} | {'Size (Bytes)':>12} | {'Pages':>8}")
    print("-" * 65)
    for r in sorted(table_reports, key=lambda x: x["name"]):
        rows_str = f"{r['rows']:,}" if isinstance(r['rows'], int) else str(r['rows'])
        bytes_str = f"{r['bytes']:,}" if isinstance(r['bytes'], int) else str(r['bytes'])
        pages_str = str(r['pages'])
        print(f"{r['name']:<25} | {rows_str:>10} | {bytes_str:>12} | {pages_str:>8}")

    if index_reports:
        print("\nINDEXES SUMMARY:")
        print(f"{'Index Name':<25} | {'On Table':<20} | {'Size (Bytes)':>12}")
        print("-" * 65)
        for r in sorted(index_reports, key=lambda x: x["name"]):
            bytes_str = f"{r['bytes']:,}" if isinstance(r['bytes'], int) else str(r['bytes'])
            print(f"{r['name']:<25} | {r['table']:<20} | {bytes_str:>12}")
            
    print("\nOPTIMIZATION RECOMMENDATIONS:")
    needs_optimize = False
    
    if db_info['freelist_count'] > 0:
        needs_optimize = True
        print(f" [*] Vacuuming recommended: Running 'VACUUM;' will reclaim {freelist_bytes:,} bytes of free space.")
        
    # Check if there are no indexes on tables with lots of rows
    large_unindexed = []
    for r in table_reports:
        if isinstance(r['rows'], int) and r['rows'] > 5000:
            # Check if has indexes
            has_idx = any(idx['table'] == r['name'] for idx in index_reports)
            if not has_idx:
                large_unindexed.append(r['name'])
                
    if large_unindexed:
        needs_optimize = True
        for t_name in large_unindexed:
            print(f" [*] Index inspection: Table '{t_name}' has >5,000 rows but no user indexes. Consider adding index keys for query speedups.")
            
    if not needs_optimize:
        print(" [✓] Database looks well-optimized. No immediate actions needed.")
        
    print("=" * 65)

if __name__ == "__main__":
    main()
