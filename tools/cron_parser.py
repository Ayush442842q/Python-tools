#!/usr/bin/env python3
"""
Cron Expression Parser - Parse cron schedule expressions and list next run times

This tool takes a standard 5-field cron expression, validates it, translates it 
into a clear plain-English explanation, and projects the next N scheduled run times.

Usage:
    python tools/cron_parser.py "CRON_EXPRESSION" [--runs N]

Example:
    python tools/cron_parser.py "*/15 9-17 * * 1-5" --runs 5
"""

import argparse
import datetime
import sys
from typing import List, Set, Tuple, Dict, Optional

# Constants
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
DAYS_OF_WEEK = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]  # 0 or 7 is Sunday

FIELD_LIMITS = {
    'minute': (0, 59),
    'hour': (0, 23),
    'day_of_month': (1, 31),
    'month': (1, 12),
    'day_of_week': (0, 7)
}


def parse_field(field_str: str, field_name: str) -> Set[int]:
    """Parses a single cron field and returns the set of active values."""
    min_val, max_val = FIELD_LIMITS[field_name]
    active_values: Set[int] = set()

    # Handle lists separated by comma
    parts = field_str.split(',')
    for part in parts:
        if not part:
            raise ValueError(f"Empty part in field {field_name}")
            
        step = 1
        # Handle step suffix (e.g. */5 or 1-10/2)
        if '/' in part:
            subpart, step_str = part.split('/', 1)
            try:
                step = int(step_str)
            except ValueError:
                raise ValueError(f"Invalid step '{step_str}' in field {field_name}")
            if step <= 0:
                raise ValueError(f"Step must be positive in field {field_name}")
        else:
            subpart = part

        # Handle range or wildcard
        if subpart == '*':
            start, end = min_val, max_val
        elif '-' in subpart:
            start_str, end_str = subpart.split('-', 1)
            start = parse_value_token(start_str, field_name)
            end = parse_value_token(end_str, field_name)
            if start > end:
                raise ValueError(f"Start value greater than end value in range '{subpart}' of field {field_name}")
        else:
            start = end = parse_value_token(subpart, field_name)

        if start < min_val or end > max_val:
            raise ValueError(f"Value out of bounds ({min_val}-{max_val}) in field {field_name}: {subpart}")

        # Add values within the step
        for val in range(start, end + 1, step):
            # Normalise day of week (7 -> 0 for Sunday consistency)
            if field_name == 'day_of_week' and val == 7:
                active_values.add(0)
            else:
                active_values.add(val)

    return active_values


def parse_value_token(token: str, field_name: str) -> int:
    """Parses a numeric or textual token into an integer."""
    token = token.upper()
    if token.isdigit():
        return int(token)
        
    if field_name == 'month':
        if token in MONTHS:
            return MONTHS.index(token) + 1
    elif field_name == 'day_of_week':
        if token in DAYS_OF_WEEK:
            return DAYS_OF_WEEK.index(token)
            
    raise ValueError(f"Invalid token '{token}' for field {field_name}")


def generate_explanation(fields_expr: List[str]) -> str:
    """Translates cron expression fields into plain-English explanation."""
    min_expr, hour_expr, dom_expr, month_expr, dow_expr = fields_expr

    # 1. Minutes
    if min_expr == '*':
        min_desc = "every minute"
    elif min_expr.startswith('*/'):
        min_desc = f"every {min_expr.split('/')[1]} minutes"
    else:
        min_desc = f"at minute {min_expr}"

    # 2. Hours
    if hour_expr == '*':
        hour_desc = "of every hour"
    elif hour_expr.startswith('*/'):
        hour_desc = f"every {hour_expr.split('/')[1]} hours"
    else:
        hour_desc = f"at hour {hour_expr}"

    # 3. Days of Month & Week
    if dom_expr == '*' and dow_expr == '*':
        day_desc = "every day"
    elif dom_expr != '*' and dow_expr == '*':
        day_desc = f"on day-of-month {dom_expr}"
    elif dom_expr == '*' and dow_expr != '*':
        day_desc = f"on day-of-week {dow_expr}"
    else:
        day_desc = f"on day-of-month {dom_expr} and day-of-week {dow_expr}"

    # 4. Months
    if month_expr == '*':
        month_desc = "of every month"
    else:
        month_desc = f"in month {month_expr}"

    return f"Runs {min_desc}, {hour_desc}, {day_desc}, {month_desc}."


def get_next_runs(
    minutes: Set[int], 
    hours: Set[int], 
    doms: Set[int], 
    months: Set[int], 
    dows: Set[int], 
    count: int
) -> List[datetime.datetime]:
    """Calculates the next N scheduled datetimes matching the parsed fields."""
    next_runs: List[datetime.datetime] = []
    
    # Start checking from the next minute onwards
    current = datetime.datetime.now().replace(second=0, microsecond=0)
    current += datetime.timedelta(minutes=1)
    
    # Safety iteration limit (checks up to 5 years into the future)
    max_days_to_check = 5 * 365
    start_date = current.date()
    
    while len(next_runs) < count:
        if (current.date() - start_date).days > max_days_to_check:
            break
            
        # Check month
        if current.month not in months:
            # Advance to the first day of next month
            if current.month == 12:
                current = current.replace(year=current.year + 1, month=1, day=1, hour=0, minute=0)
            else:
                current = current.replace(month=current.month + 1, day=1, hour=0, minute=0)
            continue

        # Check day-of-month and day-of-week
        # Note: in standard cron, if both DOM and DOW are restricted (not *), a match in EITHER matches the schedule.
        # But if only one is restricted, then it must match that restriction.
        dom_restricted = len(doms) < 31
        dow_restricted = len(dows) < 7
        
        matches_dom = current.day in doms
        # weekday() is 0 (Mon) to 6 (Sun). Cron is 0 (Sun) to 6 (Sat).
        cron_weekday = (current.weekday() + 1) % 7
        matches_dow = cron_weekday in dows
        
        day_matches = False
        if dom_restricted and dow_restricted:
            day_matches = matches_dom or matches_dow
        elif dom_restricted:
            day_matches = matches_dom
        elif dow_restricted:
            day_matches = matches_dow
        else:
            day_matches = True

        if not day_matches:
            # Advance to next day
            current = current.replace(hour=0, minute=0) + datetime.timedelta(days=1)
            continue

        # Check hour
        if current.hour not in hours:
            # Advance to next hour
            current = current.replace(minute=0) + datetime.timedelta(hours=1)
            continue

        # Check minute
        if current.minute not in minutes:
            # Advance to next minute
            current += datetime.timedelta(minutes=1)
            continue

        # Valid run time found!
        next_runs.append(current)
        current += datetime.timedelta(minutes=1)

    return next_runs


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse cron schedules and display upcoming runs.")
    parser.add_argument("expression", help="Cron expression inside quotes (e.g. '*/15 9-17 * * 1-5')")
    parser.add_argument("--runs", type=int, default=5, help="Number of future scheduled times to predict (default: 5)")
    
    args = parser.parse_args()
    cron_str = args.expression.strip()
    
    fields = cron_str.split()
    if len(fields) != 5:
        print(f"Error: Invalid cron expression '{cron_str}'. Standard cron requires exactly 5 fields.", file=sys.stderr)
        print("Required fields: minute hour day_of_month month day_of_week", file=sys.stderr)
        return 1

    try:
        minutes = parse_field(fields[0], 'minute')
        hours = parse_field(fields[1], 'hour')
        doms = parse_field(fields[2], 'day_of_month')
        months = parse_field(fields[3], 'month')
        dows = parse_field(fields[4], 'day_of_week')
    except ValueError as e:
        print(f"Error parsing cron expression: {e}", file=sys.stderr)
        return 1

    explanation = generate_explanation(fields)
    next_times = get_next_runs(minutes, hours, doms, months, dows, args.runs)

    print("=" * 60)
    print(f"Cron Expression:  {cron_str}")
    print(f"Explanation:      {explanation}")
    print("-" * 60)
    
    # Detail mapping
    headers = ["Field", "Expression Value", "Parsed Set Size", "Values (Preview)"]
    print(f"{headers[0]:<15} {headers[1]:<20} {headers[2]:<17} {headers[3]}")
    print("-" * 60)
    
    field_names = ['minute', 'hour', 'day_of_month', 'month', 'day_of_week']
    for idx, name in enumerate(field_names):
        val_set = [minutes, hours, doms, months, dows][idx]
        sorted_vals = sorted(list(val_set))
        if len(sorted_vals) > 10:
            preview = ", ".join(map(str, sorted_vals[:10])) + f" ... (+{len(sorted_vals)-10} more)"
        else:
            preview = ", ".join(map(str, sorted_vals))
        print(f"{name:<15} {fields[idx]:<20} {len(sorted_vals):<17} [{preview}]")
        
    print("-" * 60)
    print(f"Next {len(next_times)} Scheduled Runs (Local Time):")
    if not next_times:
        print("  No runs found in the next 5 years (check for impossible conditions like Feb 30).")
    for idx, dt in enumerate(next_times, 1):
        print(f"  {idx}. {dt.strftime('%Y-%m-%d %H:%M:%S (%A)')}")
    print("=" * 60)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
