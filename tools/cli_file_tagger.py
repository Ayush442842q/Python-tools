#!/usr/bin/env python3
"""
CLI File Tagger
A lightweight command-line utility to tag files and directories on your disk,
allowing you to search, filter, and run batch operations on files by custom tags.
Saves tag associations in a local SQLite database.

Usage:
    python tools/cli_file_tagger.py tag <file_path> <tag1> [<tag2> ...]
    python tools/cli_file_tagger.py untag <file_path> [<tag1> [<tag2> ...]]
    python tools/cli_file_tagger.py list
    python tools/cli_file_tagger.py search <tag1> [<tag2> ...] [--mode {and,or}]
    python tools/cli_file_tagger.py cleanup
    python tools/cli_file_tagger.py batch <tag> --exec <command>
"""

import argparse
import os
import sqlite3
import sys
from pathlib import Path

# ANSI colors for styling
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
BOLD = "\033[1m"
RESET = "\033[0m"

DB_FILE = Path.home() / ".cli_file_tagger.db"


def get_db_connection():
    """Initializes and returns a connection to the SQLite database."""
    conn = sqlite3.connect(DB_FILE)
    conn.execute("PRAGMA foreign_keys = ON;")
    # Create tables
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS file_tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT NOT NULL,
                tag TEXT NOT NULL,
                tagged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(file_path, tag)
            );
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_tags_path ON file_tags(file_path);
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_file_tags_tag ON file_tags(tag);
        """)
    return conn


def tag_file(file_path, tags):
    """Tags a file or directory with one or more tags."""
    abs_path = os.path.abspath(file_path)
    if not os.path.exists(abs_path):
        print(f"{RED}Error: File or directory '{file_path}' does not exist.{RESET}", file=sys.stderr)
        return 1

    conn = get_db_connection()
    added_count = 0
    with conn:
        for tag in tags:
            tag = tag.strip().lower()
            if not tag:
                continue
            try:
                conn.execute(
                    "INSERT INTO file_tags (file_path, tag) VALUES (?, ?);",
                    (abs_path, tag)
                )
                added_count += 1
            except sqlite3.IntegrityError:
                # Already tagged with this tag
                pass

    print(f"{GREEN}Successfully added {added_count} tag(s) to '{abs_path}'{RESET}")
    return 0


def untag_file(file_path, tags):
    """Removes tags from a file or directory. If no tags are provided, removes all tags."""
    abs_path = os.path.abspath(file_path)
    conn = get_db_connection()
    
    with conn:
        if not tags:
            cursor = conn.execute("DELETE FROM file_tags WHERE file_path = ?;", (abs_path,))
            removed = cursor.rowcount
            print(f"{GREEN}Successfully removed all tags ({removed}) from '{abs_path}'{RESET}")
        else:
            removed = 0
            for tag in tags:
                tag = tag.strip().lower()
                cursor = conn.execute(
                    "DELETE FROM file_tags WHERE file_path = ? AND tag = ?;",
                    (abs_path, tag)
                )
                removed += cursor.rowcount
            print(f"{GREEN}Successfully removed {removed} tag(s) from '{abs_path}'{RESET}")
    return 0


def list_tagged_files():
    """Lists all tagged files and their associated tags."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT file_path, GROUP_CONCAT(tag, ', ') FROM file_tags GROUP BY file_path;")
    rows = cursor.fetchall()
    
    if not rows:
        print(f"{YELLOW}No tagged files found.{RESET}")
        return 0

    print(f"\n{BOLD}{CYAN}{'File Path':<60} | {'Tags':<20}{RESET}")
    print("-" * 85)
    for file_path, tags in rows:
        exists = os.path.exists(file_path)
        status_color = RESET if exists else RED
        path_str = file_path if exists else f"{file_path} (MISSING)"
        print(f"{status_color}{path_str:<60}{RESET} | {BLUE}{tags:<20}{RESET}")
    print()
    return 0


def search_files(tags, mode):
    """Searches for files matching the specified tags in AND/OR mode."""
    tags = [t.strip().lower() for t in tags if t.strip()]
    if not tags:
        print(f"{RED}Error: Please specify at least one tag to search.{RESET}", file=sys.stderr)
        return 1

    conn = get_db_connection()
    cursor = conn.cursor()

    if mode == "or":
        placeholders = ",".join("?" for _ in tags)
        cursor.execute(
            f"SELECT file_path, GROUP_CONCAT(tag, ', ') FROM file_tags WHERE tag IN ({placeholders}) GROUP BY file_path;",
            tags
        )
        rows = cursor.fetchall()
    else:  # AND mode
        # Match files that have all of the requested tags
        placeholders = ",".join("?" for _ in tags)
        query = f"""
            SELECT file_path, GROUP_CONCAT(tag, ', ')
            FROM file_tags
            WHERE file_path IN (
                SELECT file_path
                FROM file_tags
                WHERE tag IN ({placeholders})
                GROUP BY file_path
                HAVING COUNT(DISTINCT tag) = ?
            )
            GROUP BY file_path;
        """
        cursor.execute(query, tags + [len(tags)])
        rows = cursor.fetchall()

    if not rows:
        print(f"{YELLOW}No files found matching the search criteria.{RESET}")
        return 0

    print(f"\n{BOLD}{GREEN}Found {len(rows)} matching file(s):{RESET}")
    print(f"{BOLD}{CYAN}{'File Path':<60} | {'Tags':<20}{RESET}")
    print("-" * 85)
    for file_path, file_tags in rows:
        exists = os.path.exists(file_path)
        path_str = file_path if exists else f"{file_path} (MISSING)"
        status_color = RESET if exists else RED
        print(f"{status_color}{path_str:<60}{RESET} | {BLUE}{file_tags:<20}{RESET}")
    print()
    return 0


def cleanup_db():
    """Removes tag associations for files that no longer exist on disk."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT file_path FROM file_tags;")
    paths = [row[0] for row in cursor.fetchall()]
    
    missing_paths = [p for p in paths if not os.path.exists(p)]
    
    if not missing_paths:
        print(f"{GREEN}All tagged files are present on disk. No cleanup needed.{RESET}")
        return 0

    with conn:
        placeholders = ",".join("?" for _ in missing_paths)
        cursor.execute(
            f"DELETE FROM file_tags WHERE file_path IN ({placeholders});",
            missing_paths
        )
        deleted = cursor.rowcount

    print(f"{GREEN}Cleanup complete. Removed {deleted} tag mapping(s) for {len(missing_paths)} missing file(s).{RESET}")
    return 0


def batch_execute(tag, command):
    """Executes a terminal command on all files tagged with the specified tag."""
    tag = tag.strip().lower()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT DISTINCT file_path FROM file_tags WHERE tag = ?;", (tag,))
    paths = [row[0] for row in cursor.fetchall() if os.path.exists(row[0])]

    if not paths:
        print(f"{YELLOW}No existing files found with tag '{tag}'.{RESET}")
        return 0

    import subprocess
    print(f"{BOLD}Executing command on {len(paths)} file(s) tagged '{tag}':{RESET}")
    
    success = 0
    for path in paths:
        # Interpolate '{}' with file path if present, otherwise append file path
        if "{}" in command:
            cmd_run = command.replace("{}", f'"{path}"')
        else:
            cmd_run = f'{command} "{path}"'

        print(f"\n{CYAN}Running: {cmd_run}{RESET}")
        try:
            # Run the command
            result = subprocess.run(cmd_run, shell=True, text=True)
            if result.returncode == 0:
                success += 1
            else:
                print(f"{RED}Command failed with exit code {result.returncode} for: {path}{RESET}")
        except Exception as e:
            print(f"{RED}Exception occurred while running command for {path}: {e}{RESET}")

    print(f"\n{GREEN}Batch execution finished. {success}/{len(paths)} successful.{RESET}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="CLI File Tagger - Tag files and search/operate on them",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli_file_tagger.py tag document.pdf work reference
  python cli_file_tagger.py search work reference --mode and
  python cli_file_tagger.py list
  python cli_file_tagger.py untag document.pdf reference
  python cli_file_tagger.py cleanup
  python cli_file_tagger.py batch work --exec "cp {} ~/backup/"
"""
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="Sub-commands")

    # Tag sub-command
    tag_parser = subparsers.add_parser("tag", help="Tag a file or directory")
    tag_parser.add_argument("file_path", help="Path to the file or directory to tag")
    tag_parser.add_argument("tags", nargs="+", help="One or more tags to apply")

    # Untag sub-command
    untag_parser = subparsers.add_parser("untag", help="Remove tag(s) from a file or directory")
    untag_parser.add_argument("file_path", help="Path to the file or directory")
    untag_parser.add_argument("tags", nargs="*", help="Tags to remove (if omitted, removes all tags)")

    # List sub-command
    subparsers.add_parser("list", help="List all tagged files and their tags")

    # Search sub-command
    search_parser = subparsers.add_parser("search", help="Search files by tag")
    search_parser.add_argument("tags", nargs="+", help="Tags to search for")
    search_parser.add_argument("--mode", choices=["and", "or"], default="or", help="Search mode: and (all tags must match) or or (any tag matches)")

    # Cleanup sub-command
    subparsers.add_parser("cleanup", help="Clean up tag associations for missing files")

    # Batch sub-command
    batch_parser = subparsers.add_parser("batch", help="Run a command on all files matching a tag")
    batch_parser.add_argument("tag", help="Tag matching the files")
    batch_parser.add_argument("--exec", required=True, dest="exec_cmd", help="Command to run. Use '{}' to placeholder the file path.")

    args = parser.parse_args()

    if args.command == "tag":
        return tag_file(args.file_path, args.tags)
    elif args.command == "untag":
        return untag_file(args.file_path, args.tags)
    elif args.command == "list":
        return list_tagged_files()
    elif args.command == "search":
        return search_files(args.tags, args.mode)
    elif args.command == "cleanup":
        return cleanup_db()
    elif args.command == "batch":
        return batch_execute(args.tag, args.exec_cmd)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Operation cancelled by user.{RESET}")
        sys.exit(1)
