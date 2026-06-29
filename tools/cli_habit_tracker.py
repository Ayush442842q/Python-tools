#!/usr/bin/env python3
"""
CLI Habit Tracker
A terminal-based habit and streak tracker with visual calendars.
Saves data to a local JSON file (~/.cli_habit_tracker.json).
"""

import os
import sys
import json
import argparse
import calendar
from datetime import datetime, timedelta

# Enable ANSI escape sequences on Windows if possible
if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        stdout_handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_ulong()
        if kernel32.GetConsoleMode(stdout_handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(stdout_handle, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except Exception:
        pass

# Configure stdout encoding to UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Styles
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"
CHECK_MARK = "✔"

DB_FILE = os.path.expanduser("~/.cli_habit_tracker.json")


def load_data():
    """Loads habit data from the JSON file."""
    if not os.path.exists(DB_FILE):
        return {}
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"{RED}Error loading data file: {e}. Starting fresh.{RESET}")
        return {}


def save_data(data):
    """Saves habit data to the JSON file."""
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"{RED}Error saving data file: {e}{RESET}")


def calculate_streaks(dates_list):
    """
    Given a list of dates (strings in YYYY-MM-DD),
    calculates current streak and longest streak.
    """
    if not dates_list:
        return 0, 0

    # Parse and sort unique dates
    parsed_dates = sorted(list(set(datetime.strptime(d, "%Y-%m-%d").date() for d in dates_list)))
    
    # Calculate streaks
    longest_streak = 0
    current_streak = 0
    temp_streak = 0
    prev_date = None

    for d in parsed_dates:
        if prev_date is None:
            temp_streak = 1
        elif d - prev_date == timedelta(days=1):
            temp_streak += 1
        else:
            if temp_streak > longest_streak:
                longest_streak = temp_streak
            temp_streak = 1
        prev_date = d

    if temp_streak > longest_streak:
        longest_streak = temp_streak

    # Calculate current streak (must include today or yesterday)
    today = datetime.today().date()
    yesterday = today - timedelta(days=1)
    
    if parsed_dates[-1] == today:
        current_streak = temp_streak
    elif parsed_dates[-1] == yesterday:
        current_streak = temp_streak
    else:
        current_streak = 0

    return current_streak, longest_streak


def cmd_add(args, data):
    """Adds a new habit."""
    name = args.name.strip()
    if not name:
        print(f"{RED}Habit name cannot be empty.{RESET}")
        return

    if name in data:
        print(f"{YELLOW}Habit '{name}' already exists.{RESET}")
        return

    data[name] = {
        "created_at": datetime.today().strftime("%Y-%m-%d"),
        "history": []
    }
    save_data(data)
    print(f"{GREEN}Successfully added habit '{name}'!{RESET}")


def cmd_check(args, data):
    """Checks off a habit for a given date."""
    name = args.name.strip()
    if name not in data:
        print(f"{RED}Habit '{name}' not found. Use 'add' to create it.{RESET}")
        return

    date_str = args.date or datetime.today().strftime("%Y-%m-%d")
    try:
        datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        print(f"{RED}Invalid date format. Use YYYY-MM-DD.{RESET}")
        return

    if date_str in data[name]["history"]:
        print(f"{YELLOW}Habit '{name}' is already completed for {date_str}.{RESET}")
        return

    data[name]["history"].append(date_str)
    save_data(data)
    print(f"{GREEN}Checked off '{name}' for {date_str}! Keep it up!{RESET}")


def cmd_uncheck(args, data):
    """Removes completion of a habit for a given date."""
    name = args.name.strip()
    if name not in data:
        print(f"{RED}Habit '{name}' not found.{RESET}")
        return

    date_str = args.date or datetime.today().strftime("%Y-%m-%d")
    if date_str not in data[name]["history"]:
        print(f"{YELLOW}Habit '{name}' was not completed on {date_str}.{RESET}")
        return

    data[name]["history"].remove(date_str)
    save_data(data)
    print(f"{YELLOW}Removed completion check for '{name}' on {date_str}.{RESET}")


def cmd_list(args, data):
    """Lists all habits with streak stats."""
    if not data:
        print(f"{YELLOW}No habits tracked yet. Add one using 'add <name>'.{RESET}")
        return

    print(f"\n{BOLD}{CYAN}Current Habits & Streaks:{RESET}")
    print("-" * 65)
    print(f"{'Habit Name':<25} | {'Total':<6} | {'Current Streak':<15} | {'Longest Streak'}")
    print("-" * 65)
    for name, info in sorted(data.items()):
        history = info.get("history", [])
        curr, longest = calculate_streaks(history)
        total = len(history)
        
        # Color code streaks
        curr_str = f"{GREEN}{curr} days{RESET}" if curr > 0 else f"{DIM}0 days{RESET}"
        long_str = f"{YELLOW}{longest} days{RESET}" if longest > 0 else f"{DIM}0 days{RESET}"
        
        print(f"{name:<25} | {total:<6} | {curr_str:<24} | {long_str}")
    print("-" * 65)


def cmd_show(args, data):
    """Displays a calendar visual for a habit."""
    name = args.name.strip()
    if name not in data:
        print(f"{RED}Habit '{name}' not found.{RESET}")
        return

    history = set(data[name]["history"])
    
    # Parse month and year
    if args.month:
        try:
            dt = datetime.strptime(args.month, "%Y-%m")
            year, month = dt.year, dt.month
        except ValueError:
            print(f"{RED}Invalid month format. Use YYYY-MM.{RESET}")
            return
    else:
        today = datetime.today()
        year, month = today.year, today.month

    # Generate calendar month grid
    cal = calendar.monthcalendar(year, month)
    month_name = calendar.month_name[month]

    print(f"\n{BOLD}{CYAN}Habit Calendar: {name}{RESET}")
    print(f"{BOLD}{month_name} {year}{RESET}")
    print("-----------------------------")
    print(" Mo  Tu  We  Th  Fr  Sa  Su")
    
    for week in cal:
        week_str = ""
        for day in week:
            if day == 0:
                week_str += "    "
            else:
                date_str = f"{year}:{month:02d}:{day:02d}"
                # Format to standard YYYY-MM-DD
                formatted_date = f"{year}-{month:02d}-{day:02d}"
                
                if formatted_date in history:
                    # Highlight checked-off days
                    week_str += f" {GREEN}{day:02d}{RESET} "
                else:
                    week_str += f" {day:02d} "
        print(week_str)
    print("-----------------------------")
    curr, longest = calculate_streaks(list(history))
    print(f"Total Completions: {len(history)}")
    print(f"Current Streak:    {GREEN}{curr} days{RESET}")
    print(f"Longest Streak:    {YELLOW}{longest} days{RESET}")
    print()


def cmd_delete(args, data):
    """Deletes a habit."""
    name = args.name.strip()
    if name not in data:
        print(f"{RED}Habit '{name}' not found.{RESET}")
        return

    # Prompt confirmation
    confirm = input(f"Are you sure you want to delete '{name}'? (y/N): ").strip().lower()
    if confirm == 'y':
        del data[name]
        save_data(data)
        print(f"{GREEN}Deleted habit '{name}'.{RESET}")
    else:
        print(f"{YELLOW}Delete cancelled.{RESET}")


def main():
    parser = argparse.ArgumentParser(
        description="CLI Habit Tracker - Track habits, streaks, and progress."
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # Add habit
    p_add = subparsers.add_parser("add", help="Add a new habit")
    p_add.add_argument("name", help="Name of the habit to track")

    # Check habit
    p_check = subparsers.add_parser("check", help="Mark habit as completed for a date")
    p_check.add_argument("name", help="Name of the habit")
    p_check.add_argument("--date", help="Date in YYYY-MM-DD format (defaults to today)")

    # Uncheck habit
    p_uncheck = subparsers.add_parser("uncheck", help="Unmark habit completion")
    p_uncheck.add_argument("name", help="Name of the habit")
    p_uncheck.add_argument("--date", help="Date in YYYY-MM-DD format (defaults to today)")

    # List habits
    subparsers.add_parser("list", help="List all habits and their current streaks")

    # Show calendar
    p_show = subparsers.add_parser("show", help="Show calendar visualization for a habit")
    p_show.add_argument("name", help="Name of the habit")
    p_show.add_argument("--month", help="Month to view in YYYY-MM format (defaults to current month)")

    # Delete habit
    p_delete = subparsers.add_parser("delete", help="Delete a habit")
    p_delete.add_argument("name", help="Name of the habit to delete")

    args = parser.parse_args()

    # Load data
    data = load_data()

    # Routing commands
    if args.command == "add":
        cmd_add(args, data)
    elif args.command == "check":
        cmd_check(args, data)
    elif args.command == "uncheck":
        cmd_uncheck(args, data)
    elif args.command == "list":
        cmd_list(args, data)
    elif args.command == "show":
        cmd_show(args, data)
    elif args.command == "delete":
        cmd_delete(args, data)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
