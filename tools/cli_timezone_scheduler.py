#!/usr/bin/env python3
"""
CLI Timezone Scheduler
A terminal-based meeting planner helper that displays overlapping business hours
across multiple timezones using a color-coded 24-hour visual grid.
"""

import os
import sys
import argparse
from datetime import datetime, timedelta, timezone

# Enable ANSI escape sequences on Windows
if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        stdout_handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        if kernel32.GetConsoleMode(stdout_handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(stdout_handle, mode.value | 0x0004)
    except Exception:
        pass

# Fallback database of common timezones (offsets in hours from UTC)
COMMON_OFFSETS = {
    "UTC": 0.0,
    "GMT": 0.0,
    "BST": 1.0,
    "CET": 1.0,
    "CEST": 2.0,
    "EET": 2.0,
    "EEST": 3.0,
    "MSK": 3.0,
    "IST": 5.5,
    "PKT": 5.0,
    "ICT": 7.0,
    "CST-CN": 8.0,
    "SGT": 8.0,
    "JST": 9.0,
    "KST": 9.0,
    "AEST": 10.0,
    "AEDT": 11.0,
    "NZST": 12.0,
    "NZDT": 13.0,
    "HST": -10.0,
    "AKST": -9.0,
    "AKDT": -8.0,
    "PST": -8.0,
    "PDT": -7.0,
    "MST": -7.0,
    "MDT": -6.0,
    "CST": -6.0,
    "CDT": -5.0,
    "EST": -5.0,
    "EDT": -4.0,
    "AST": -4.0,
    "ADT": -3.0,
    "ART": -3.0,
    "BRT": -3.0,
}


def get_timezone_offset(tz_name):
    """Retrieves timezone offset in hours using zoneinfo, pytz, or fallback dictionary."""
    tz_name_upper = tz_name.upper()
    
    # 1. Check numeric offset format (e.g. +5.5, -8, +05:30)
    if tz_name.startswith(("+", "-")) or tz_name.isdigit():
        try:
            # Parse sign and values
            sign = -1 if tz_name.startswith("-") else 1
            val_str = tz_name.lstrip("+-")
            if ":" in val_str:
                h, m = map(int, val_str.split(":"))
                return sign * (h + m / 60.0)
            else:
                return sign * float(val_str)
        except ValueError:
            pass

    # 2. Check common offsets dictionary
    if tz_name_upper in COMMON_OFFSETS:
        return COMMON_OFFSETS[tz_name_upper]

    # 3. Try Python's zoneinfo (Python 3.9+)
    try:
        from zoneinfo import ZoneInfo
        zi = ZoneInfo(tz_name)
        # Get offset for current time
        dt = datetime.now(zi)
        return dt.utcoffset().total_seconds() / 3600.0
    except Exception:
        pass

    # 4. Try pytz
    try:
        import pytz
        tz = pytz.timezone(tz_name)
        dt = datetime.now(tz)
        return dt.utcoffset().total_seconds() / 3600.0
    except Exception:
        pass

    raise ValueError(f"Unknown timezone: {tz_name}")


# ANSI Colors
RESET = "\033[0m"
BOLD = "\033[1m"
UNDERLINE = "\033[4m"
GREEN = "\033[92m"
RED = "\033[91m"

# BG Colors (black text inside colored blocks)
BG_GREEN = "\033[42m\033[30m"   # Business hours
BG_YELLOW = "\033[43m\033[30m"  # Waking / personal hours
BG_RED = "\033[41m\033[97m"     # Sleep hours (white text)
BG_GRAY = "\033[100m\033[37m"   # Late night / dim

COLOR_LEGEND = (
    f"{BG_GREEN}  Green  {RESET} Business (9-17)   "
    f"{BG_YELLOW}  Yellow {RESET} Personal (7-9, 17-22)   "
    f"{BG_RED}   Red   {RESET} Sleep (22-7)"
)


def get_hour_category(hour, biz_start=9, biz_end=17, sleep_start=22, sleep_end=7):
    """Categorizes the hour as Business, Personal, or Sleep."""
    # Sleep hours handle crossing midnight (e.g. 22 to 7)
    is_sleep = False
    if sleep_start > sleep_end:
        is_sleep = (hour >= sleep_start or hour < sleep_end)
    else:
        is_sleep = (sleep_start <= hour < sleep_end)
        
    if is_sleep:
        return "sleep"
    elif biz_start <= hour < biz_end:
        return "business"
    else:
        return "personal"


def main():
    parser = argparse.ArgumentParser(
        description="CLI Timezone Scheduler - Visual meeting planner across timezones."
    )
    parser.add_argument(
        "timezones",
        nargs="*",
        default=["PST", "UTC", "IST", "JST"],
        help="List of timezones to display (abbreviations, names like 'America/New_York', or offsets like '+5.5')"
    )
    parser.add_argument(
        "--biz-start",
        type=int,
        default=9,
        help="Start hour of business day (default: 9)"
    )
    parser.add_argument(
        "--biz-end",
        type=int,
        default=17,
        help="End hour of business day (default: 17)"
    )
    parser.add_argument(
        "--base",
        default="UTC",
        help="The base timezone for the grid columns (default: UTC)"
    )
    parser.add_argument(
        "--date",
        help="Target date in YYYY-MM-DD format (defaults to today)"
    )

    args = parser.parse_args()

    # Parse target date
    if args.date:
        try:
            target_date = datetime.strptime(args.date, "%Y-%m-%d").date()
        except ValueError:
            print(f"Error: Invalid date format. Use YYYY-MM-DD.")
            sys.exit(1)
    else:
        target_date = datetime.today().date()

    # Resolve offsets
    resolved_tzs = []
    base_offset = 0.0
    
    try:
        base_offset = get_timezone_offset(args.base)
    except ValueError as e:
        print(f"Error resolving base timezone: {e}")
        sys.exit(1)

    for tz in args.timezones:
        try:
            offset = get_timezone_offset(tz)
            resolved_tzs.append((tz, offset))
        except ValueError as e:
            print(f"Warning: {e}. Skipping.")

    if not resolved_tzs:
        print("Error: No valid timezones to display.")
        sys.exit(1)

    # Print Header
    print("\n" + "=" * 105)
    print(f" {BOLD}Global Timezone Meeting Scheduler{RESET} | Date: {BOLD}{target_date}{RESET}")
    print(f" Columns based on {BOLD}{args.base}{RESET} hours (UTC{base_offset:+.1f} if fractional, else standard offset)")
    print("=" * 105)

    # Print Time header row
    # Col 1: Timezone name (15 chars)
    # Col 2: Grid of hours (24 cols * 3 chars = 72 chars)
    # Col 3: Local date status if different
    sys.stdout.write(f"{'Timezone (Offset)':<20} |")
    for h in range(24):
        sys.stdout.write(f" {h:02d}")
    sys.stdout.write("\n" + "-" * 105 + "\n")

    # We will track which base hours are business hours across *all* selected timezones
    overlap_hours = []

    # Print each timezone row
    for tz_name, offset in resolved_tzs:
        # Offset difference relative to base offset
        offset_diff = offset - base_offset
        
        # Display name
        tz_label = f"{tz_name} (UTC{offset:+.1f})"
        sys.stdout.write(f"{tz_label:<20} |")

        for base_hour in range(24):
            # Calculate local hour in this timezone
            local_hour_float = (base_hour + offset_diff) % 24
            local_hour = int(local_hour_float)
            
            # Categorize the local hour
            cat = get_hour_category(local_hour, biz_start=args.biz_start, biz_end=args.biz_end)
            
            # Print with color
            if cat == "business":
                sys.stdout.write(f"{BG_GREEN} {local_hour:02d}{RESET}")
            elif cat == "personal":
                sys.stdout.write(f"{BG_YELLOW} {local_hour:02d}{RESET}")
            else:
                sys.stdout.write(f"{BG_GRAY} {local_hour:02d}{RESET}")

        sys.stdout.write("\n")

    sys.stdout.write("-" * 105 + "\n")

    # Compute overlap hours
    # For each base hour, check if it's business hours in all timezones
    for base_hour in range(24):
        all_biz = True
        for tz_name, offset in resolved_tzs:
            offset_diff = offset - base_offset
            local_hour = int((base_hour + offset_diff) % 24)
            cat = get_hour_category(local_hour, biz_start=args.biz_start, biz_end=args.biz_end)
            if cat != "business":
                all_biz = False
                break
        if all_biz:
            overlap_hours.append(base_hour)

    # Print Overlap row
    sys.stdout.write(f"{BOLD}{'Overlap (Biz Hours)':<20}{RESET} |")
    for base_hour in range(24):
        if base_hour in overlap_hours:
            # Highlight overlap hour
            sys.stdout.write(f"{BG_GREEN} {base_hour:02d}{RESET}")
        else:
            sys.stdout.write(" --")
    sys.stdout.write("\n" + "=" * 105 + "\n")

    # Print legend
    print(COLOR_LEGEND)
    if overlap_hours:
        overlap_times = ", ".join(f"{h:02d}:00" for h in overlap_hours)
        print(f"\n{BOLD}{GREEN}Best Meeting Slots (in {args.base}):{RESET} {overlap_times}")
    else:
        print(f"\n{BOLD}{RED}No overlapping business hours found.{RESET} Consider expanding window or checking alternate timezones.")
    print()


if __name__ == "__main__":
    main()
