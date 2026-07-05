#!/usr/bin/env python3
"""
Cron Human Explainer
--------------------
Translates standard 5-field and 6-field cron expressions into clear, natural human-readable text
and calculates the next N upcoming execution timestamps with relative time countdowns.

Author: Antigravity
License: MIT
"""

import sys
import re
import json
import argparse
from datetime import datetime, timedelta
from typing import List, Tuple, Dict, Optional

# ANSI Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"

MONTH_NAMES = ["January", "February", "March", "April", "May", "June",
               "July", "August", "September", "October", "November", "December"]

DAY_NAMES = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

MONTH_MAP = {name[:3].upper(): i + 1 for i, name in enumerate(MONTH_NAMES)}
DAY_MAP = {name[:3].upper(): i for i, name in enumerate(DAY_NAMES)}
DAY_MAP["7"] = 0  # 7 can mean Sunday in some cron parsers


def parse_field(field_str: str, min_val: int, max_val: int, name_map: Optional[Dict[str, int]] = None) -> List[int]:
    """
    Parses a single cron field into a sorted list of matched integers.
    """
    field_str = field_str.upper()
    if name_map:
        for k, v in name_map.items():
            field_str = field_str.replace(k, str(v))

    allowed = set()
    parts = field_str.split(",")

    for part in parts:
        if "/" in part:
            range_part, step_str = part.split("/", 1)
            step = int(step_str)
            if range_part == "*":
                start_val, end_val = min_val, max_val
            elif "-" in range_part:
                start_val, end_val = map(int, range_part.split("-", 1))
            else:
                start_val, end_val = int(range_part), max_val
            allowed.update(range(start_val, end_val + 1, step))
        elif "-" in part:
            start_val, end_val = map(int, part.split("-", 1))
            allowed.update(range(start_val, end_val + 1))
        elif part == "*":
            allowed.update(range(min_val, max_val + 1))
        else:
            allowed.add(int(part))

    return sorted([x for x in allowed if min_val <= x <= max_val])


def explain_field(field_str: str, unit: str, names: Optional[List[str]] = None) -> str:
    """
    Generates plain English explanation for a single field.
    """
    if field_str == "*":
        return f"every {unit}"
    if "/" in field_str and field_str.startswith("*"):
        step = field_str.split("/")[1]
        return f"every {step} {unit}s"
    if names:
        # Check if field has comma or range
        try:
            indices = parse_field(field_str, 0, len(names) - 1)
            formatted_names = [names[i] for i in indices]
            if len(formatted_names) == 1:
                return f"in {formatted_names[0]}"
            return f"in {', '.join(formatted_names[:-1])} and {formatted_names[-1]}"
        except Exception:
            pass
    return f"at {field_str} ({unit})"


def explain_cron(cron_expr: str) -> str:
    """
    Translates a 5-field cron expression into plain natural English.
    Format: minute hour dom month dow
    """
    parts = cron_expr.strip().split()
    if len(parts) == 6:
        # Include seconds if 6 fields
        sec_str, min_str, hour_str, dom_str, month_str, dow_str = parts
    elif len(parts) == 5:
        sec_str = "0"
        min_str, hour_str, dom_str, month_str, dow_str = parts
    else:
        raise ValueError("Cron expression must have 5 or 6 whitespace-separated fields.")

    min_val = parse_field(min_str, 0, 59)
    hour_val = parse_field(hour_str, 0, 23)
    dom_val = parse_field(dom_str, 1, 31)
    month_val = parse_field(month_str, 1, 12, MONTH_MAP)
    dow_val = parse_field(dow_str, 0, 6, DAY_MAP)

    explanations = []

    # Time explanation
    if min_str == "*" and hour_str == "*":
        explanations.append("Every minute")
    elif min_str.startswith("*/") and hour_str == "*":
        step = min_str.split("/")[1]
        explanations.append(f"Every {step} minutes")
    elif len(hour_val) == 1 and len(min_val) == 1:
        time_obj = datetime.strptime(f"{hour_val[0]:02d}:{min_val[0]:02d}", "%H:%M")
        explanations.append(f"At {time_obj.strftime('%I:%M %p')}")
    else:
        explanations.append(f"At minute {min_str} past hour {hour_str}")

    # Day of month explanation
    if dom_str != "*":
        explanations.append(f"on day {dom_str} of the month")

    # Month explanation
    if month_str != "*":
        m_names = [MONTH_NAMES[m - 1] for m in month_val]
        explanations.append(f"in {', '.join(m_names)}")

    # Day of week explanation
    if dow_str != "*":
        d_names = [DAY_NAMES[d] for d in dow_val]
        explanations.append(f"on {', '.join(d_names)}")

    return " ".join(explanations)


def get_next_runs(cron_expr: str, count: int = 5, start_time: Optional[datetime] = None) -> List[datetime]:
    """
    Calculates next execution datetimes for a 5-field cron expression.
    """
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        raise ValueError("Calculations support standard 5-field cron expressions.")

    min_str, hour_str, dom_str, month_str, dow_str = parts
    min_set = set(parse_field(min_str, 0, 59))
    hour_set = set(parse_field(hour_str, 0, 23))
    dom_set = set(parse_field(dom_str, 1, 31))
    month_set = set(parse_field(month_str, 1, 12, MONTH_MAP))
    dow_set = set(parse_field(dow_str, 0, 6, DAY_MAP))

    current = start_time or datetime.now()
    # Align to current minute + 1
    current = current.replace(second=0, microsecond=0) + timedelta(minutes=1)

    next_runs = []
    max_search_days = 366
    days_searched = 0

    while len(next_runs) < count and days_searched < max_search_days:
        if current.month in month_set:
            # Python datetime weekday: Mon=0 .. Sun=6 -> Cron: Sun=0, Mon=1 .. Sat=6
            cron_dow = (current.weekday() + 1) % 7
            dom_matches = current.day in dom_set if dom_str != "*" else True
            dow_matches = cron_dow in dow_set if dow_str != "*" else True

            # If both dom and dow are specified (not *), usually either matching triggers run
            day_valid = (dom_matches and dow_matches) if (dom_str == "*" or dow_str == "*") else (dom_matches or dow_matches)

            if day_valid and current.hour in hour_set and current.minute in min_set:
                next_runs.append(current)

        current += timedelta(minutes=1)
        if current.minute == 0 and current.hour == 0:
            days_searched += 1

    return next_runs


def main():
    parser = argparse.ArgumentParser(
        description="Translate cron expressions into natural English and list upcoming execution times."
    )
    parser.add_argument("cron", nargs="?", help="Cron expression inside quotes (e.g. '*/15 9-17 * * 1-5')")
    parser.add_argument("-n", "--count", type=int, default=5, help="Number of upcoming execution times to display (default: 5)")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")

    args = parser.parse_args()

    if not args.cron:
        print(f"{BLUE}{BOLD}Cron Human Explainer - Demo Mode{RESET}\n")
        demo_expr = "*/15 9-17 1 * 1-5"
        print(f"Cron Expression: {BOLD}{demo_expr}{RESET}")
        explanation = explain_cron(demo_expr)
        print(f"Explanation: {GREEN}{explanation}{RESET}\n")

        print(f"{BOLD}Upcoming Execution Times:{RESET}")
        runs = get_next_runs(demo_expr, count=5)
        now = datetime.now()
        for i, run in enumerate(runs, 1):
            diff = run - now
            mins, secs = divmod(diff.total_seconds(), 60)
            hours, mins = divmod(mins, 60)
            countdown = f"in {int(hours)}h {int(mins)}m" if hours else f"in {int(mins)}m"
            print(f"  {i}. {run.strftime('%Y-%m-%d %I:%M %p')} ({GREEN}{countdown}{RESET})")
        return

    try:
        explanation = explain_cron(args.cron)
        runs = get_next_runs(args.cron, count=args.count) if len(args.cron.split()) == 5 else []
    except Exception as e:
        print(f"{RED}Error parsing cron expression: {e}{RESET}")
        sys.exit(1)

    if args.json:
        data = {
            "cron": args.cron,
            "explanation": explanation,
            "upcoming_runs": [r.isoformat() for r in runs]
        }
        print(json.dumps(data, indent=2))
    else:
        print(f"{BOLD}Cron:{RESET} {args.cron}")
        print(f"{BOLD}Explanation:{RESET} {GREEN}{explanation}{RESET}\n")
        if runs:
            print(f"{BOLD}Next {len(runs)} Executions:{RESET}")
            now = datetime.now()
            for i, run in enumerate(runs, 1):
                diff = run - now
                mins = int(diff.total_seconds() // 60)
                hours, mins = divmod(mins, 60)
                countdown = f"in {hours}h {mins}m" if hours else f"in {mins}m"
                print(f"  {i}. {run.strftime('%Y-%m-%d %I:%M:%S %p')} ({countdown})")


if __name__ == "__main__":
    main()
