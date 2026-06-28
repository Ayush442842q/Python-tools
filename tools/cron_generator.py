#!/usr/bin/env python3
"""
Interactive Cron Expression Generator
An interactive CLI wizard that helps users construct valid 5-field cron expressions
by asking step-by-step questions, explaining what the generated cron expression does,
and projecting the next execution times.
"""

import datetime
import sys
from typing import List, Tuple, Optional

# ANSI Colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"

def supports_color() -> bool:
    """Checks if the terminal supports color output."""
    import os
    platform_supports = sys.platform != "win32" or "ANSICON" in os.environ or "WT_SESSION" in os.environ
    is_a_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    return platform_supports and is_a_tty

if not supports_color():
    COLOR_RESET = ""
    COLOR_BOLD = ""
    COLOR_GREEN = ""
    COLOR_YELLOW = ""
    COLOR_RED = ""
    COLOR_CYAN = ""

MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
DAYS_OF_WEEK = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]

def print_header(title: str):
    print(f"\n{COLOR_BOLD}{COLOR_CYAN}=== {title} ==={COLOR_RESET}")

def get_choice(prompt: str, options: List[Tuple[str, str]]) -> str:
    """Helper to display choices and return selected option key."""
    while True:
        print(f"\n{COLOR_BOLD}{prompt}{COLOR_RESET}")
        for key, desc in options:
            print(f"  [{COLOR_GREEN}{key}{COLOR_RESET}] {desc}")
        
        choice = input(f"Select option: ").strip().lower()
        valid_keys = [o[0].lower() for o in options]
        if choice in valid_keys:
            return choice
        print(f"{COLOR_RED}Invalid option. Please try again.{COLOR_RESET}")

def get_int_input(prompt: str, min_val: int, max_val: int) -> int:
    """Gets an integer input from the user within a range."""
    while True:
        try:
            val = int(input(f"{prompt} ({min_val}-{max_val}): ").strip())
            if min_val <= val <= max_val:
                return val
            print(f"{COLOR_RED}Value must be between {min_val} and {max_val}.{COLOR_RESET}")
        except ValueError:
            print(f"{COLOR_RED}Please enter a valid integer.{COLOR_RESET}")

def get_multiple_choices(prompt: str, options: List[str], offset: int = 0) -> str:
    """Select multiple specific indices from options."""
    print(f"\n{COLOR_BOLD}{prompt}{COLOR_RESET}")
    for idx, opt in enumerate(options):
        print(f"  [{COLOR_GREEN}{idx + offset}{COLOR_RESET}] {opt}")
    
    while True:
        inp = input("Enter numbers separated by commas (e.g. 1,3,5): ").strip()
        if not inp:
            print(f"{COLOR_RED}Selection cannot be empty.{COLOR_RESET}")
            continue
        try:
            parts = [int(p.strip()) for p in inp.split(',')]
            valid_range = range(offset, len(options) + offset)
            if all(p in valid_range for p in parts):
                return ",".join(str(p) for p in sorted(list(set(parts))))
            print(f"{COLOR_RED}All selections must be within valid range.{COLOR_RESET}")
        except ValueError:
            print(f"{COLOR_RED}Invalid format. Enter comma-separated integers.{COLOR_RESET}")

def configure_minute() -> str:
    print_header("Step 1: Configure Minutes")
    choices = [
        ("A", "Every minute (*)"),
        ("B", "Every N minutes (e.g. every 5 minutes -> */5)"),
        ("C", "Specific minute(s) (e.g. at minute 0, 15, 30)"),
        ("D", "Range of minutes (e.g. between minute 10 and 20)")
    ]
    opt = get_choice("Choose minute frequency:", choices)
    if opt == "a":
        return "*"
    elif opt == "b":
        n = get_int_input("Run every N minutes: N =", 1, 59)
        return f"*/{n}"
    elif opt == "c":
        print("Select specific minutes (0-59):")
        inp = input("Enter comma separated minutes: ").strip()
        # Validation
        parts = [int(p.strip()) for p in inp.split(',') if p.strip().isdigit()]
        parts = [p for p in parts if 0 <= p <= 59]
        if not parts:
            print(f"{COLOR_YELLOW}No valid minutes entered. Defaulting to 0.{COLOR_RESET}")
            return "0"
        return ",".join(str(p) for p in sorted(list(set(parts))))
    elif opt == "d":
        start = get_int_input("Start minute", 0, 59)
        end = get_int_input("End minute", start, 59)
        return f"{start}-{end}"
    return "*"

def configure_hour() -> str:
    print_header("Step 2: Configure Hours")
    choices = [
        ("A", "Every hour (*)"),
        ("B", "Every N hours (e.g. every 2 hours -> */2)"),
        ("C", "Specific hour(s) (e.g. 9 AM, 5 PM)"),
        ("D", "Range of hours (e.g. during work hours 9-17)")
    ]
    opt = get_choice("Choose hour frequency:", choices)
    if opt == "a":
        return "*"
    elif opt == "b":
        n = get_int_input("Run every N hours: N =", 1, 23)
        return f"*/{n}"
    elif opt == "c":
        print("Select specific hours (0-23, where 0=Midnight, 12=Noon, 13=1 PM, etc.):")
        inp = input("Enter comma separated hours: ").strip()
        parts = [int(p.strip()) for p in inp.split(',') if p.strip().isdigit()]
        parts = [p for p in parts if 0 <= p <= 23]
        if not parts:
            print(f"{COLOR_YELLOW}No valid hours entered. Defaulting to *.{COLOR_RESET}")
            return "*"
        return ",".join(str(p) for p in sorted(list(set(parts))))
    elif opt == "d":
        start = get_int_input("Start hour", 0, 23)
        end = get_int_input("End hour", start, 23)
        return f"{start}-{end}"
    return "*"

def configure_dom() -> str:
    print_header("Step 3: Configure Day of Month")
    choices = [
        ("A", "Every day (*)"),
        ("B", "Specific day(s) of the month (e.g. 1st, 15th)"),
        ("C", "Range of days (e.g. 1st to 10th)")
    ]
    opt = get_choice("Choose day of month frequency:", choices)
    if opt == "a":
        return "*"
    elif opt == "b":
        print("Select specific days of the month (1-31):")
        inp = input("Enter comma separated days: ").strip()
        parts = [int(p.strip()) for p in inp.split(',') if p.strip().isdigit()]
        parts = [p for p in parts if 1 <= p <= 31]
        if not parts:
            print(f"{COLOR_YELLOW}No valid days entered. Defaulting to *.{COLOR_RESET}")
            return "*"
        return ",".join(str(p) for p in sorted(list(set(parts))))
    elif opt == "c":
        start = get_int_input("Start day", 1, 31)
        end = get_int_input("End day", start, 31)
        return f"{start}-{end}"
    return "*"

def configure_month() -> str:
    print_header("Step 4: Configure Months")
    choices = [
        ("A", "Every month (*)"),
        ("B", "Specific month(s) (e.g. January, June, December)")
    ]
    opt = get_choice("Choose month frequency:", choices)
    if opt == "a":
        return "*"
    elif opt == "b":
        return get_multiple_choices("Select specific months:", MONTHS, offset=1)
    return "*"

def configure_dow() -> str:
    print_header("Step 5: Configure Day of Week")
    choices = [
        ("A", "Every day of the week (*)"),
        ("B", "Specific day(s) of the week (e.g. Weekends, Weekdays)")
    ]
    opt = get_choice("Choose day of week frequency:", choices)
    if opt == "a":
        return "*"
    elif opt == "b":
        return get_multiple_choices("Select specific days (0=Sunday, 1=Monday, etc.):", DAYS_OF_WEEK, offset=0)
    return "*"

def explain_field(field_val: str, field_type: str) -> str:
    """Helper to translate cron field syntax to English."""
    if field_val == "*":
        return f"every {field_type}"
    
    if field_val.startswith("*/"):
        step = field_val.split("/")[1]
        return f"every {step} {field_type}s"
    
    if "-" in field_val and "/" in field_val:
        # e.g. 1-10/2
        r_part, step = field_val.split("/")
        start, end = r_part.split("-")
        return f"every {step} {field_type}s from {start} to {end}"

    if "-" in field_val:
        start, end = field_val.split("-")
        return f"from {field_type} {start} to {end}"

    if "," in field_val:
        return f"on {field_type}s: {field_val}"
        
    return f"at {field_type} {field_val}"

def explain_cron(min_f: str, hour_f: str, dom_f: str, month_f: str, dow_f: str) -> str:
    """Generates an approximate readable explanation."""
    min_exp = explain_field(min_f, "minute")
    hour_exp = explain_field(hour_f, "hour")
    dom_exp = explain_field(dom_f, "day of month")
    
    # Translate Month values if numeric
    month_name_exp = month_f
    if month_f != "*" and not any(m in month_f for m in MONTHS):
        parts = month_f.split(",")
        named_parts = []
        for p in parts:
            try:
                named_parts.append(MONTHS[int(p) - 1])
            except (ValueError, IndexError):
                named_parts.append(p)
        month_name_exp = ",".join(named_parts)
    month_exp = explain_field(month_name_exp, "month")
    
    # Translate DOW values if numeric
    dow_name_exp = dow_f
    if dow_f != "*" and not any(d in dow_f for d in DAYS_OF_WEEK):
        parts = dow_f.split(",")
        named_parts = []
        for p in parts:
            try:
                named_parts.append(DAYS_OF_WEEK[int(p)])
            except (ValueError, IndexError):
                named_parts.append(p)
        dow_name_exp = ",".join(named_parts)
    dow_exp = explain_field(dow_name_exp, "day of week")

    explanation = f"Runs {min_exp}, {hour_exp}, {dom_exp}, in {month_exp}, and {dow_exp}."
    # Clean up double space or grammar issues slightly
    explanation = explanation.replace("every minute, every hour", "every minute of every hour")
    explanation = explanation.replace("every day of month, in every month", "every day")
    explanation = explanation.replace("and every day of week.", "")
    if explanation.endswith(", "):
        explanation = explanation[:-2] + "."
    return explanation

def parse_cron_field_to_set(field_str: str, min_val: int, max_val: int) -> List[int]:
    """Expands field string to a set of valid integers."""
    if field_str == "*":
        return list(range(min_val, max_val + 1))
        
    vals = set()
    parts = field_str.split(",")
    for part in parts:
        step = 1
        if "/" in part:
            subpart, step_str = part.split("/")
            step = int(step_str)
        else:
            subpart = part
            
        if subpart == "*":
            start, end = min_val, max_val
        elif "-" in subpart:
            start_str, end_str = subpart.split("-")
            start, end = int(start_str), int(end_str)
        else:
            start = end = int(subpart)
            
        for v in range(start, end + 1, step):
            if min_val <= v <= max_val:
                vals.add(v)
    return sorted(list(vals))

def project_next_runs(cron_expr: str, count: int = 5) -> List[datetime.datetime]:
    """Helper to predict the next execution timestamps."""
    parts = cron_expr.split()
    if len(parts) != 5:
        return []
    
    min_f, hour_f, dom_f, month_f, dow_f = parts
    
    minutes = parse_cron_field_to_set(min_f, 0, 59)
    hours = parse_cron_field_to_set(hour_f, 0, 23)
    doms = parse_cron_field_to_set(dom_f, 1, 31)
    months = parse_cron_field_to_set(month_f, 1, 12)
    # 0 or 7 can be Sunday. Map 7 to 0
    dows_raw = parse_cron_field_to_set(dow_f, 0, 7)
    dows = set()
    for d in dows_raw:
        dows.add(0 if d == 7 else d)
        
    next_runs = []
    now = datetime.datetime.now().replace(second=0, microsecond=0)
    current = now + datetime.timedelta(minutes=1)
    
    # Simple search for matching times (cap search to 2 years to prevent loops)
    limit_year = current.year + 2
    while len(next_runs) < count and current.year <= limit_year:
        if current.month in months:
            if current.day in doms:
                # weekday check: python weekday() returns 0 (Mon) to 6 (Sun).
                # Our DOW: 0 (Sun) to 6 (Sat)
                py_wd = current.weekday()
                cron_wd = (py_wd + 1) % 7
                if cron_wd in dows:
                    if current.hour in hours:
                        if current.minute in minutes:
                            next_runs.append(current)
        current += datetime.timedelta(minutes=1)
        
    return next_runs

def main():
    print(f"{COLOR_BOLD}{COLOR_GREEN}============================================")
    print("   INTERACTIVE CRON EXPRESSION GENERATOR    ")
    print(f"============================================{COLOR_RESET}")
    
    try:
        min_f = configure_minute()
        hour_f = configure_hour()
        dom_f = configure_dom()
        month_f = configure_month()
        dow_f = configure_dow()
        
        cron_expr = f"{min_f} {hour_f} {dom_f} {month_f} {dow_f}"
        
        print_header("Generated Cron Expression")
        print(f"  {COLOR_BOLD}{COLOR_YELLOW}{cron_expr}{COLOR_RESET}")
        
        explanation = explain_cron(min_f, hour_f, dom_f, month_f, dow_f)
        print(f"\n{COLOR_BOLD}Plain English Explanation:{COLOR_RESET}")
        print(f"  {explanation}")
        
        # Calculate next execution times
        print(f"\n{COLOR_BOLD}Next 5 Scheduled Executions:{COLOR_RESET}")
        runs = project_next_runs(cron_expr, 5)
        if runs:
            for idx, r in enumerate(runs, 1):
                print(f"  {idx}. {COLOR_GREEN}{r.strftime('%Y-%m-%d %H:%M:%S')}{COLOR_RESET} ({r.strftime('%A')})")
        else:
            print(f"  {COLOR_RED}Could not calculate next executions (check constraints).{COLOR_RESET}")
            
        print(f"\n{COLOR_BOLD}Usage Example:{COLOR_RESET}")
        print(f"  crontab -e")
        print(f"  {cron_expr} /path/to/your/script.sh")
        print(f"\n{COLOR_GREEN}Have a productive day!{COLOR_RESET}\n")

    except KeyboardInterrupt:
        print(f"\n\n{COLOR_RED}Operation cancelled.{COLOR_RESET}\n")
        sys.exit(0)

if __name__ == "__main__":
    main()
