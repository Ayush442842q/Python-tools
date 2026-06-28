#!/usr/bin/env python3
"""
SQLite Database Health & Optimization Tool - Check, reindex, vacuum, and tune SQLite databases.

This tool performs maintenance operations on SQLite databases:
  - Integrity check (PRAGMA integrity_check)
  - Foreign key validation (PRAGMA foreign_key_check)
  - Database defragmentation and size reduction (VACUUM)
  - Index rebuilding (REINDEX)
  - Stats aggregation for the query planner (ANALYZE)
  - Before/after database size analysis and performance recommendations
"""

import os
import sys
import sqlite3
import time
import argparse

# ANSI color codes
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"
COLOR_RESET = "\033[0m"

def format_size(size_bytes):
    """Format bytes to human readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"

class SqliteDbOptimizer:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = None
        self.cursor = None

    def connect(self):
        if not os.path.exists(self.db_path):
            print(f"{COLOR_RED}Error: Database file '{self.db_path}' not found.{COLOR_RESET}", file=sys.stderr)
            return False
        try:
            # Connect in normal read/write mode
            self.conn = sqlite3.connect(self.db_path)
            self.cursor = self.conn.cursor()
            return True
        except Exception as e:
            print(f"{COLOR_RED}Failed to connect to database: {e}{COLOR_RESET}", file=sys.stderr)
            return False

    def close(self):
        if self.conn:
            self.conn.close()

    def get_pragma(self, pragma_name):
        try:
            self.cursor.execute(f"PRAGMA {pragma_name};")
            res = self.cursor.fetchone()
            return res[0] if res else None
        except Exception:
            return None

    def run_pragma_check(self, pragma_cmd, success_val="ok"):
        try:
            self.cursor.execute(f"PRAGMA {pragma_cmd};")
            res = self.cursor.fetchall()
            if not res:
                return True, "No issues found"
            if len(res) == 1 and str(res[0][0]).lower() == success_val:
                return True, "No issues found"
            return False, str(res)
        except Exception as e:
            return False, f"Error: {e}"

    def optimize(self, run_integrity, run_vacuum, run_reindex, run_analyze):
        start_size = os.path.getsize(self.db_path)
        print(f"Database: {COLOR_CYAN}{self.db_path}{COLOR_RESET}")
        print(f"Initial Size: {COLOR_BOLD}{format_size(start_size)}{COLOR_RESET}\n")

        # 1. Inspect Database Properties
        print(f"{COLOR_BOLD}=== Database Metadata ==={COLOR_RESET}")
        page_size = self.get_pragma("page_size")
        page_count = self.get_pragma("page_count")
        journal_mode = self.get_pragma("journal_mode")
        auto_vacuum = self.get_pragma("auto_vacuum")
        user_version = self.get_pragma("user_version")
        
        print(f"  Page Size:      {COLOR_CYAN}{page_size} bytes{COLOR_RESET}")
        print(f"  Page Count:     {COLOR_CYAN}{page_count}{COLOR_RESET}")
        print(f"  Journal Mode:   {COLOR_CYAN}{journal_mode}{COLOR_RESET}")
        print(f"  Auto-Vacuum:    {COLOR_CYAN}{auto_vacuum}{COLOR_RESET}")
        print(f"  User Version:   {COLOR_CYAN}{user_version}{COLOR_RESET}")
        print()

        # 2. Integrity Checks
        if run_integrity:
            print(f"{COLOR_BOLD}=== Health Checks ==={COLOR_RESET}")
            
            # Integrity Check
            print("  Running PRAGMA integrity_check...", end="", flush=True)
            t_start = time.perf_counter()
            ok, msg = self.run_pragma_check("integrity_check")
            t_diff = time.perf_counter() - t_start
            if ok:
                print(f" {COLOR_GREEN}PASSED{COLOR_RESET} ({t_diff:.3f}s)")
            else:
                print(f" {COLOR_RED}FAILED{COLOR_RESET} ({t_diff:.3f}s)")
                print(f"    Details: {msg}")

            # Foreign Key Check
            print("  Running PRAGMA foreign_key_check...", end="", flush=True)
            t_start = time.perf_counter()
            self.cursor.execute("PRAGMA foreign_key_check;")
            fk_violations = self.cursor.fetchall()
            t_diff = time.perf_counter() - t_start
            if not fk_violations:
                print(f" {COLOR_GREEN}PASSED{COLOR_RESET} ({t_diff:.3f}s)")
            else:
                print(f" {COLOR_RED}FAILED{COLOR_RESET} ({t_diff:.3f}s)")
                print(f"    Found {len(fk_violations)} foreign key violations.")
            print()

        # 3. Index Rebuilding
        if run_reindex:
            print(f"{COLOR_BOLD}=== Index Maintenance ==={COLOR_RESET}")
            print("  Reindexing tables (REINDEX)...", end="", flush=True)
            t_start = time.perf_counter()
            try:
                self.cursor.execute("REINDEX;")
                self.conn.commit()
                t_diff = time.perf_counter() - t_start
                print(f" {COLOR_GREEN}SUCCESS{COLOR_RESET} ({t_diff:.3f}s)")
            except Exception as e:
                print(f" {COLOR_RED}FAILED{COLOR_RESET}: {e}")
            print()

        # 4. Statistics Analyzer
        if run_analyze:
            print(f"{COLOR_BOLD}=== Query Statistics ==={COLOR_RESET}")
            print("  Analyzing query planner stats (ANALYZE)...", end="", flush=True)
            t_start = time.perf_counter()
            try:
                self.cursor.execute("ANALYZE;")
                self.conn.commit()
                t_diff = time.perf_counter() - t_start
                print(f" {COLOR_GREEN}SUCCESS{COLOR_RESET} ({t_diff:.3f}s)")
            except Exception as e:
                print(f" {COLOR_RED}FAILED{COLOR_RESET}: {e}")
            print()

        # 5. Database Vacuuming (defragments and shrinks)
        # Note: VACUUM requires closing connection or running it directly outside a transaction block
        if run_vacuum:
            print(f"{COLOR_BOLD}=== Database Defragmentation ==={COLOR_RESET}")
            print("  Shrinking database (VACUUM)...", end="", flush=True)
            t_start = time.perf_counter()
            try:
                # VACUUM cannot be run inside a transaction
                self.conn.isolation_level = None
                self.cursor.execute("VACUUM;")
                self.conn.isolation_level = ""  # restore transaction mode
                t_diff = time.perf_counter() - t_start
                print(f" {COLOR_GREEN}SUCCESS{COLOR_RESET} ({t_diff:.3f}s)")
            except Exception as e:
                print(f" {COLOR_RED}FAILED{COLOR_RESET}: {e}")
            print()

        # Before & After Size Analysis
        end_size = os.path.getsize(self.db_path)
        saved = start_size - end_size
        pct = (saved / start_size) * 100 if start_size > 0 else 0

        print(f"{COLOR_BOLD}=== Optimization Results ==={COLOR_RESET}")
        print(f"  Before Size:    {COLOR_BOLD}{format_size(start_size)}{COLOR_RESET}")
        print(f"  After Size:     {COLOR_BOLD}{format_size(end_size)}{COLOR_RESET}")
        if saved > 0:
            print(f"  Space Reclaimed: {COLOR_GREEN}{format_size(saved)}{COLOR_RESET} ({pct:.1f}% reduction)")
        elif saved < 0:
            print(f"  Space Increased: {COLOR_YELLOW}{format_size(-saved)}{COLOR_RESET} (due to ANALYZE stats tables)")
        else:
            print(f"  Space Reclaimed: {COLOR_CYAN}0 bytes{COLOR_RESET} (database was already fully optimized)")

        # Performance Recommendations
        print(f"\n{COLOR_BOLD}=== Performance Tuning Tips ==={COLOR_RESET}")
        if journal_mode != "wal":
            print(f"  {COLOR_YELLOW}TIP:{COLOR_RESET} Current journal mode is '{journal_mode}'. WAL (Write-Ahead Logging) is significantly faster")
            print("       for concurrent reads and writes. To enable: PRAGMA journal_mode=WAL;")
        else:
            print(f"  {COLOR_GREEN}✓{COLOR_RESET} WAL mode is enabled (good for concurrent access).")

        synch = self.get_pragma("synchronous")
        # synchronous = 2 (NORMAL/FULL), 1 (NORMAL), 0 (OFF)
        if synch == 2:
            print(f"  {COLOR_YELLOW}TIP:{COLOR_RESET} Synchronous is set to FULL (2). For faster writes, consider setting it to NORMAL (1).")
            print("       It remains completely transaction-safe in WAL mode.")

        # Check for indices count
        self.cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='index';")
        indices_count = self.cursor.fetchone()[0]
        self.cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table';")
        tables_count = self.cursor.fetchone()[0]
        print(f"  Schema info: {tables_count} tables, {indices_count} indexes.")

def main():
    parser = argparse.ArgumentParser(description="SQLite Database Health & Performance Optimization Utility.")
    parser.add_argument("db_file", help="Path to the SQLite database file")
    parser.add_argument("-n", "--no-vacuum", action="store_true", help="Skip VACUUM optimization")
    parser.add_argument("-k", "--no-reindex", action="store_true", help="Skip REINDEX operation")
    parser.add_argument("-s", "--no-analyze", action="store_true", help="Skip ANALYZE stats updates")
    parser.add_argument("-c", "--no-check", action="store_true", help="Skip database integrity check")
    
    args = parser.parse_args()

    optimizer = SqliteDbOptimizer(args.db_file)
    if not optimizer.connect():
        sys.exit(1)

    try:
        optimizer.optimize(
            run_integrity=not args.no_check,
            run_vacuum=not args.no_vacuum,
            run_reindex=not args.no_reindex,
            run_analyze=not args.no_analyze
        )
    finally:
        optimizer.close()

if __name__ == "__main__":
    main()
