#!/usr/bin/env python3
"""
Cron Expression Parser
Parses standard 5-field cron expressions and displays the next 5 (or N) execution times.
Also displays the parsed schedule values for each field.
"""

import argparse
import datetime
import sys
import re

MONTH_NAMES = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12
}

WEEKDAY_NAMES = {
    'sun': 0, 'mon': 1, 'tue': 2, 'wed': 3, 'thu': 4, 'fri': 5, 'sat': 6
}

def parse_field(pattern, min_val, max_val, names=None):
    if names:
        for name, num in names.items():
            pattern = re.sub(re.escape(name), str(num), pattern, flags=re.IGNORECASE)
            
    valid_vals = set()
    parts = pattern.split(',')
    
    for part in parts:
        part = part.strip()
        if not part:
            continue
            
        step = 1
        if '/' in part:
            val_part, step_str = part.split('/', 1)
            try:
                step = int(step_str)
            except ValueError:
                raise ValueError(f"Invalid step value '{step_str}' in field pattern '{part}'")
            if step <= 0:
                raise ValueError("Step value must be greater than zero.")
        else:
            val_part = part
            
        if val_part == '*':
            start, end = min_val, max_val
            for v in range(start, end + 1, step):
                valid_vals.add(v)
        elif '-' in val_part:
            start_str, end_str = val_part.split('-', 1)
            try:
                start, end = int(start_str), int(end_str)
            except ValueError:
                raise ValueError(f"Invalid range bounds '{val_part}' in field pattern '{part}'")
            if start < min_val or end > max_val or start > end:
                raise ValueError(f"Range {start}-{end} is out of bounds [{min_val}-{max_val}] or invalid.")
            for v in range(start, end + 1, step):
                valid_vals.add(v)
        else:
            try:
                v = int(val_part)
            except ValueError:
                raise ValueError(f"Invalid number '{val_part}' in field pattern '{part}'")
                
            if v < min_val or v > max_val:
                # Handle special case: Day of week 7 is Sunday, same as 0
                if min_val == 0 and max_val == 6 and v == 7:
                    v = 0
                else:
                    raise ValueError(f"Value {v} is out of bounds [{min_val}-{max_val}].")
                    
            if '/' in part:
                for val in range(v, max_val + 1, step):
                    valid_vals.add(val)
            else:
                valid_vals.add(v)
                
    return sorted(list(valid_vals))

def get_next_executions(cron_expr, num_executions=5, base_date=None):
    if base_date is None:
        base_date = datetime.datetime.now()
        
    fields = cron_expr.strip().split()
    if len(fields) != 5:
        raise ValueError(f"Cron expression must have exactly 5 fields, found {len(fields)}.")
        
    min_pattern, hour_pattern, dom_pattern, month_pattern, dow_pattern = fields
    
    valid_mins = parse_field(min_pattern, 0, 59)
    valid_hours = parse_field(hour_pattern, 0, 23)
    valid_doms = parse_field(dom_pattern, 1, 31)
    valid_months = parse_field(month_pattern, 1, 12, MONTH_NAMES)
    valid_dows = parse_field(dow_pattern, 0, 6, WEEKDAY_NAMES)
    
    dom_restricted = (dom_pattern != '*')
    dow_restricted = (dow_pattern != '*')
    
    executions = []
    # Start looking from the next minute onwards
    current = base_date.replace(second=0, microsecond=0) + datetime.timedelta(minutes=1)
    
    # Max search limit: 10 years
    end_limit = base_date + datetime.timedelta(days=365 * 10)
    
    # Pre-convert sets for fast lookup
    mins_set = set(valid_mins)
    hours_set = set(valid_hours)
    doms_set = set(valid_doms)
    months_set = set(valid_months)
    dows_set = set(valid_dows)
    
    while len(executions) < num_executions and current < end_limit:
        # 1. Check Month
        if current.month not in months_set:
            y = current.year
            m = current.month + 1
            if m > 12:
                m = 1
                y += 1
            current = datetime.datetime(y, m, 1, 0, 0)
            continue
            
        # 2. Check Day
        cron_weekday = (current.weekday() + 1) % 7
        
        if dom_restricted and dow_restricted:
            day_matches = (current.day in doms_set) or (cron_weekday in dows_set)
        elif dom_restricted:
            day_matches = (current.day in doms_set)
        elif dow_restricted:
            day_matches = (cron_weekday in dows_set)
        else:
            day_matches = True
            
        if not day_matches:
            # Roll to next day, hour 0, minute 0
            current = (current + datetime.timedelta(days=1)).replace(hour=0, minute=0)
            continue
            
        # 3. Check Hour
        if current.hour not in hours_set:
            current = (current + datetime.timedelta(hours=1)).replace(minute=0)
            continue
            
        # 4. Check Minute
        if current.minute not in mins_set:
            current = current + datetime.timedelta(minutes=1)
            continue
            
        # Match found!
        executions.append(current)
        current = current + datetime.timedelta(minutes=1)
        
    return executions, {
        'minute': valid_mins,
        'hour': valid_hours,
        'day of month': valid_doms,
        'month': valid_months,
        'day of week': valid_dows
    }

def format_list_summary(lst, max_display=10):
    if len(lst) == 0:
        return "None"
    if len(lst) <= max_display:
        return " ".join(str(x) for x in lst)
    return " ".join(str(x) for x in lst[:max_display]) + f"... ({len(lst)} total values)"

def main():
    parser = argparse.ArgumentParser(
        description="Parses standard 5-field cron expressions and displays the next execution times.",
        epilog="Example:\n"
               "  python cron_parser.py \"*/15 0 1,15 * 1-5\"\n"
               "  python cron_parser.py \"0 12 * * 1-5\" -n 10",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("cron", help="Standard 5-field cron expression (minute hour day_of_month month day_of_week)")
    parser.add_argument("-n", "--num", type=int, default=5, help="Number of next execution times to display (default: 5)")
    parser.add_argument("-b", "--base", help="Base date/time to start from in format 'YYYY-MM-DD HH:MM' (default: current local time)")

    args = parser.parse_args()

    # Resolve base date
    base_dt = None
    if args.base:
        try:
            base_dt = datetime.datetime.strptime(args.base.strip(), "%Y-%m-%d %H:%M")
        except ValueError:
            print(f"[ERROR] Invalid base date format. Expected 'YYYY-MM-DD HH:MM', got '{args.base}'")
            sys.exit(1)
    else:
        base_dt = datetime.datetime.now()

    print(f"[*] Parsing cron expression: '{args.cron}'")
    print(f"[*] Base date/time: {base_dt.strftime('%Y-%m-%d %H:%M:%S')}")
    print("-" * 55)

    try:
        executions, parsed_fields = get_next_executions(args.cron, args.num, base_dt)
        
        # Display field breakdown
        for field, vals in parsed_fields.items():
            print(f"{field:<15} {format_list_summary(vals)}")
            
        print("-" * 55)
        print(f"Next {len(executions)} scheduled execution times:")
        if not executions:
            print("  No executions found within search limits.")
        for idx, dt in enumerate(executions, 1):
            day_name = dt.strftime("%A")
            print(f"  {idx}. {dt.strftime('%Y-%m-%d %H:%M:%S')} ({day_name})")
            
        print("[PASS] Cron expression successfully parsed.")

    except Exception as e:
        print(f"[ERROR] {str(e)}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
