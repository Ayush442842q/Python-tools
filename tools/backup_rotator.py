#!/usr/bin/env python3
"""
Grandfather-Father-Son (GFS) Backup Rotator
Manages backup directories or files by applying a GFS retention policy.
Keeps a configurable number of daily, weekly, monthly, and yearly backups,
and deletes the rest to save disk space.
"""

import os
import sys
import re
import datetime
import argparse

# Console colors
COLOR_RESET = "\033[0m"
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"

# Regex patterns to search for dates in filenames
DATE_PATTERNS = [
    re.compile(r'(\d{4})-(\d{2})-(\d{2})[_-](\d{2})(\d{2})(\d{2})'),  # YYYY-MM-DD_HHMMSS
    re.compile(r'(\d{4})-(\d{2})-(\d{2})'),                         # YYYY-MM-DD
    re.compile(r'(\d{8})[_-](\d{6})'),                              # YYYYMMDD_HHMMSS
    re.compile(r'(\d{8})'),                                         # YYYYMMDD
]

def extract_date(filename, filepath):
    # Try parsing date from filename
    for pattern in DATE_PATTERNS:
        match = pattern.search(filename)
        if match:
            try:
                groups = match.groups()
                if len(groups) == 1:
                    # YYYYMMDD
                    s = groups[0]
                    return datetime.date(int(s[0:4]), int(s[4:6]), int(s[6:8]))
                elif len(groups) == 2:
                    # YYYYMMDD and HHMMSS
                    s = groups[0]
                    return datetime.date(int(s[0:4]), int(s[4:6]), int(s[6:8]))
                elif len(groups) >= 3:
                    # YYYY, MM, DD
                    return datetime.date(int(groups[0]), int(groups[1]), int(groups[2]))
            except ValueError:
                pass

    # Fallback: file modification time
    try:
        mtime = os.path.getmtime(filepath)
        return datetime.date.fromtimestamp(mtime)
    except Exception:
        return None


def get_week_identifier(date):
    # Return (year, iso_week)
    return date.isocalendar()[:2]


def get_month_identifier(date):
    return (date.year, date.month)


def get_year_identifier(date):
    return date.year


def evaluate_backups(backup_dir, keep_days, keep_weeks, keep_months, keep_years):
    if not os.path.exists(backup_dir):
        raise ValueError(f"Directory '{backup_dir}' does not exist.")

    # Find all backup files/folders
    entries = []
    for entry in os.listdir(backup_dir):
        # Ignore hidden files
        if entry.startswith('.'):
            continue
        
        path = os.path.join(backup_dir, entry)
        date = extract_date(entry, path)
        if date:
            entries.append({
                "name": entry,
                "path": path,
                "date": date,
                "keep": False,
                "reason": ""
            })

    # Sort entries newest first
    entries.sort(key=lambda x: x["date"], reverse=True)
    if not entries:
        return []

    reference_date = datetime.date.today()

    # Buckets to keep
    daily_keep = set()
    weekly_keep = {}  # week_id -> entry
    monthly_keep = {} # month_id -> entry
    yearly_keep = {}  # year_id -> entry

    for entry in entries:
        edate = entry["date"]
        age_days = (reference_date - edate).days

        # 1. Daily bucket
        if age_days < keep_days:
            entry["keep"] = True
            entry["reason"] = f"Daily (< {keep_days} days old)"
            daily_keep.add(edate)
            continue

        # 2. Weekly bucket
        week_id = get_week_identifier(edate)
        # Check if week is within weekly retention range
        # Approximate: age of week start
        week_start = edate - datetime.timedelta(days=edate.weekday())
        week_age_weeks = (reference_date - week_start).days // 7
        if week_age_weeks < keep_weeks:
            # We keep the newest backup within each week
            if week_id not in weekly_keep:
                weekly_keep[week_id] = entry
                entry["keep"] = True
                entry["reason"] = f"Weekly snapshot (Week {week_id[1]}, {week_id[0]})"
                continue

        # 3. Monthly bucket
        month_id = get_month_identifier(edate)
        month_age_months = (reference_date.year - edate.year) * 12 + (reference_date.month - edate.month)
        if month_age_months < keep_months:
            # Keep newest backup in each month
            if month_id not in monthly_keep:
                monthly_keep[month_id] = entry
                entry["keep"] = True
                entry["reason"] = f"Monthly snapshot ({edate.strftime('%B %Y')})"
                continue

        # 4. Yearly bucket
        year_id = get_year_identifier(edate)
        year_age_years = reference_date.year - edate.year
        if year_age_years < keep_years:
            # Keep newest backup in each year
            if year_id not in yearly_keep:
                yearly_keep[year_id] = entry
                entry["keep"] = True
                entry["reason"] = f"Yearly snapshot ({edate.year})"
                continue

    return entries


def prune_backups(entries, dry_run=True):
    deleted_count = 0
    kept_count = 0
    
    print(f"\n{COLOR_BOLD}{COLOR_CYAN}=== Backup Evaluation Report ==={COLOR_RESET}\n")
    
    for entry in reversed(entries):  # Print oldest first
        if entry["keep"]:
            print(f"  {COLOR_GREEN}[KEEP]{COLOR_RESET} {entry['name']} (Date: {entry['date']}) - Reason: {entry['reason']}")
            kept_count += 1
        else:
            print(f"  {COLOR_RED}[PRUNE]{COLOR_RESET} {entry['name']} (Date: {entry['date']}) - Age: {(datetime.date.today() - entry['date']).days} days")
            deleted_count += 1

    print(f"\nSummary: {kept_count} backups kept, {deleted_count} backups marked for deletion/pruning.")

    if deleted_count == 0:
        print("[*] No backups need to be pruned.")
        return

    if dry_run:
        print(f"\n{COLOR_YELLOW}[*] Dry-run enabled. No files or directories were deleted.{COLOR_RESET}")
        return

    # Prompt user for confirmation
    confirm = input(f"\n{COLOR_BOLD}{COLOR_RED}Are you sure you want to permanently delete these {deleted_count} backups? (y/N): {COLOR_RESET}").strip().lower()
    if confirm != 'y':
        print("[*] Pruning cancelled.")
        return

    for entry in entries:
        if not entry["keep"]:
            path = entry["path"]
            print(f"[-] Deleting {entry['name']}...")
            try:
                if os.path.isdir(path):
                    import shutil
                    shutil.rmtree(path)
                else:
                    os.remove(path)
            except Exception as e:
                print(f"  [!] Error deleting {entry['name']}: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Grandfather-Father-Son (GFS) Backup Rotator")
    parser.add_argument("backup_dir", help="Directory containing the backup files/folders")
    parser.add_argument("--keep-days", type=int, default=7, help="Number of daily backups to keep (default: 7)")
    parser.add_argument("--keep-weeks", type=int, default=4, help="Number of weekly snapshots to keep (default: 4)")
    parser.add_argument("--keep-months", type=int, default=12, help="Number of monthly snapshots to keep (default: 12)")
    parser.add_argument("--keep-years", type=int, default=3, help="Number of yearly snapshots to keep (default: 3)")
    parser.add_argument("--execute", action="store_true", help="Execute deletion (otherwise runs in dry-run mode)")

    args = parser.parse_args()

    try:
        entries = evaluate_backups(
            args.backup_dir,
            args.keep_days,
            args.keep_weeks,
            args.keep_months,
            args.keep_years
        )
        prune_backups(entries, dry_run=not args.execute)
    except Exception as e:
        print(f"[-] Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
