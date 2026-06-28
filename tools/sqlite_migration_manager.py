#!/usr/bin/env python3
"""
SQLite Database Migration Manager

A lightweight schema migration system for SQLite. Manages SQL migration files,
tracks applied migrations, and supports UP/DOWN migrations (rollbacks).

Usage:
    python tools/sqlite_migration_manager.py <command> [options]

Commands:
    init      Initialize migrations folder and database tracking table
    create    Create a new timestamped migration template file
    migrate   Run all pending migrations (Up)
    rollback  Roll back the last applied migration (Down)
    status    Show list of applied and pending migrations
"""

import sys
import os
import re
import sqlite3
import argparse
import datetime

# Terminal colors
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"

MIGRATION_TEMPLATE = """-- Migration: {name}
-- Created: {timestamp}

-- +migrate Up
-- Write your UP migration SQL statements here
-- Example: CREATE TABLE users (id INTEGER PRIMARY KEY, username TEXT);


-- +migrate Down
-- Write your DOWN migration SQL statements here (to rollback UP changes)
-- Example: DROP TABLE users;
"""

def print_banner():
    banner = f"""
{CYAN}{BOLD}=========================================================
      🗄️  SQLITE DATABASE MIGRATION MANAGER  🗄️
========================================================={RESET}
"""
    print(banner)


class MigrationManager:
    def __init__(self, db_path, migrations_dir):
        self.db_path = db_path
        self.migrations_dir = migrations_dir
        self.migrations_table = "schema_migrations"

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def init(self):
        """Initializes the directory and database tracking table."""
        # Create folder
        if not os.path.exists(self.migrations_dir):
            os.makedirs(self.migrations_dir)
            print(f"Created migrations directory: {BOLD}{self.migrations_dir}{RESET}")
        else:
            print(f"Migrations directory already exists: {BOLD}{self.migrations_dir}{RESET}")

        # Create table
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.migrations_table} (
                    version TEXT PRIMARY KEY,
                    name TEXT,
                    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            conn.commit()
            print(f"Initialized database tracking table: {BOLD}{self.migrations_table}{RESET}")
        except sqlite3.Error as e:
            print(f"{RED}Database Error: {e}{RESET}")
        finally:
            conn.close()

    def create(self, name):
        """Creates a new migration template file."""
        if not os.path.exists(self.migrations_dir):
            print(f"{RED}Error: Migrations folder '{self.migrations_dir}' does not exist. Run 'init' first.{RESET}")
            return False

        # Generate prefix
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        sanitized_name = re.sub(r"[^a-zA-Z0-9_]", "_", name).lower().strip("_")
        filename = f"{timestamp}_{sanitized_name}.sql"
        filepath = os.path.join(self.migrations_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(MIGRATION_TEMPLATE.format(name=name, timestamp=datetime.datetime.now().isoformat()))

        print(f"Created new migration file: {BOLD}{GREEN}{filepath}{RESET}")
        return True

    def _parse_migration_file(self, filepath):
        """Parses up and down sections from a migration SQL file."""
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()

        up_sql = ""
        down_sql = ""
        
        # Split into up/down sections
        up_match = re.search(r"--\s*\+migrate\s+Up(.*?)(?=--\s*\+migrate\s+Down|$)", content, re.DOTALL | re.IGNORECASE)
        down_match = re.search(r"--\s*\+migrate\s+Down(.*)", content, re.DOTALL | re.IGNORECASE)
        
        if up_match:
            up_sql = up_match.group(1).strip()
        if down_match:
            down_sql = down_match.group(1).strip()
            
        return up_sql, down_sql

    def _get_all_migrations(self):
        """Returns a sorted list of all migrations in the folder."""
        if not os.path.exists(self.migrations_dir):
            return []
            
        migrations = []
        for f in os.listdir(self.migrations_dir):
            if f.endswith(".sql"):
                match = re.match(r"^(\d{14})_(.+)\.sql$", f)
                if match:
                    migrations.append({
                        "version": match.group(1),
                        "name": match.group(2),
                        "filename": f,
                        "filepath": os.path.join(self.migrations_dir, f)
                    })
        # Sort by version timestamp
        migrations.sort(key=lambda x: x["version"])
        return migrations

    def _get_applied_migrations(self):
        """Returns a list of versions of applied migrations from the DB."""
        conn = self._get_connection()
        applied = {}
        try:
            cursor = conn.cursor()
            # Check if table exists
            cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{self.migrations_table}'")
            if not cursor.fetchone():
                return {}
                
            cursor.execute(f"SELECT version, applied_at FROM {self.migrations_table} ORDER BY version ASC")
            for row in cursor.fetchall():
                applied[row[0]] = row[1]
        except sqlite3.Error as e:
            print(f"{RED}Error reading migration table: {e}{RESET}")
        finally:
            conn.close()
        return applied

    def migrate(self):
        """Runs all pending UP migrations."""
        all_m = self._get_all_migrations()
        applied = self._get_applied_migrations()

        pending = [m for m in all_m if m["version"] not in applied]

        if not pending:
            print(f"{GREEN}Database is up to date. No pending migrations.{RESET}")
            return

        conn = self._get_connection()
        try:
            for m in pending:
                print(f"Applying migration {BOLD}{m['filename']}{RESET}...")
                up_sql, _ = self._parse_migration_file(m["filepath"])
                
                # Execute in transaction
                cursor = conn.cursor()
                if up_sql.strip():
                    cursor.executescript(up_sql)
                    
                # Mark as applied
                cursor.execute(
                    f"INSERT INTO {self.migrations_table} (version, name) VALUES (?, ?)", 
                    (m["version"], m["name"])
                )
                conn.commit()
                print(f"  -> {GREEN}Success{RESET}")
            print(f"\n{BOLD}{GREEN}Successfully applied {len(pending)} migration(s).{RESET}")
        except sqlite3.Error as e:
            conn.rollback()
            print(f"{RED}Migration failed! Database rolled back. Error: {e}{RESET}")
        finally:
            conn.close()

    def rollback(self):
        """Rolls back the last applied migration."""
        applied = self._get_applied_migrations()
        if not applied:
            print(f"{YELLOW}No applied migrations found to roll back.{RESET}")
            return

        # Get last applied version
        last_version = sorted(applied.keys())[-1]
        
        all_m = self._get_all_migrations()
        matching_migration = next((m for m in all_m if m["version"] == last_version), None)

        if not matching_migration:
            print(f"{RED}Error: Migration file for applied version {last_version} not found in folder.{RESET}")
            return

        print(f"Rolling back migration {BOLD}{matching_migration['filename']}{RESET}...")
        _, down_sql = self._parse_migration_file(matching_migration["filepath"])

        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            if down_sql.strip():
                cursor.executescript(down_sql)
            
            # Remove from tracking table
            cursor.execute(f"DELETE FROM {self.migrations_table} WHERE version = ?", (last_version,))
            conn.commit()
            print(f"  -> {GREEN}Successfully rolled back{RESET}")
        except sqlite3.Error as e:
            conn.rollback()
            print(f"{RED}Rollback failed! Database transaction rolled back. Error: {e}{RESET}")
        finally:
            conn.close()

    def status(self):
        """Displays migration status."""
        all_m = self._get_all_migrations()
        applied = self._get_applied_migrations()

        if not all_m:
            print(f"{YELLOW}No migration files found in migrations directory.{RESET}")
            return

        print(f"{BOLD}{'Status':<10} | {'Version/Timestamp':<16} | {'Migration Name'}{RESET}")
        print("-" * 60)
        
        for m in all_m:
            ver = m["version"]
            if ver in applied:
                status_str = f"{GREEN}Applied{RESET}"
                details = f"(at {applied[ver]})"
            else:
                status_str = f"{YELLOW}Pending{RESET}"
                details = ""
                
            print(f"{status_str:<19} | {ver:<16} | {m['name']} {details}")


def main():
    print_banner()
    parser = argparse.ArgumentParser(
        description="SQLite Schema Migration Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("command", choices=["init", "create", "migrate", "rollback", "status"],
                        help="The migration command to run")
    parser.add_argument("name", nargs="?", default="migration",
                        help="Name of the migration (only used for 'create')")
    parser.add_argument("--db", default="database.db",
                        help="Path to the SQLite database file (default: database.db)")
    parser.add_argument("--dir", default="migrations",
                        help="Directory where migration SQL files are stored (default: migrations)")

    args = parser.parse_args()

    manager = MigrationManager(args.db, args.dir)

    if args.command == "init":
        manager.init()
    elif args.command == "create":
        manager.create(args.name)
    elif args.command == "migrate":
        manager.migrate()
    elif args.command == "rollback":
        manager.rollback()
    elif args.command == "status":
        manager.status()

    return 0

if __name__ == "__main__":
    sys.exit(main())
