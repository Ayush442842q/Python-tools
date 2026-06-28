#!/usr/bin/env python3
"""
Cron Schedule Collision Finder & Timeline Analyzer
Parses cron expressions or crontab files, projects execution schedules,
detects simultaneous job executions (collisions), and visualizes cron concurrency.
"""

import sys
import datetime
import argparse
from typing import List, Tuple, Set, Dict, Any

# ANSI colors for formatted output
COLORS = {
    "BLUE": "\033[94m",
    "CYAN": "\033[96m",
    "GREEN": "\033[92m",
    "YELLOW": "\033[93m",
    "RED": "\033[91m",
    "BOLD": "\033[1m",
    "RESET": "\033[0m"
}

def parse_cron_field(expr: str, min_val: int, max_val: int) -> Set[int]:
    """Parse a single cron field expression into a set of valid integers."""
    valid_vals = set()
    
    # Split list items
    parts = expr.split(",")
    for part in parts:
        part = part.strip()
        if not part:
            continue
            
        step = 1
        if "/" in part:
            val_range, step_str = part.split("/", 1)
            step = int(step_str)
            part = val_range.strip()
            
        if part == "*":
            start, end = min_val, max_val
        elif "-" in part:
            start_str, end_str = part.split("-", 1)
            start, end = int(start_str), int(end_str)
        else:
            start = end = int(part)
            
        # Ensure values are within logical bounds
        start = max(min_val, min(start, max_val))
        end = max(min_val, min(end, max_val))
        
        # Populate values
        for val in range(start, end + 1, step):
            valid_vals.add(val)
            
    return valid_vals

class CronJob:
    def __init__(self, schedule: str, command: str):
        self.schedule = schedule.strip()
        self.command = command.strip() or "Unnamed Job"
        
        # Parse fields
        fields = self.schedule.split()
        if len(fields) != 5:
            raise ValueError(f"Invalid cron expression (must be 5 fields): '{schedule}'")
            
        # standard cron limits:
        # minute: 0-59, hour: 0-23, day of month: 1-31, month: 1-12, day of week: 0-7 (0 and 7 are Sunday)
        self.minutes = parse_cron_field(fields[0], 0, 59)
        self.hours = parse_cron_field(fields[1], 0, 23)
        self.doms = parse_cron_field(fields[2], 1, 31)
        self.months = parse_cron_field(fields[3], 1, 12)
        
        # Convert day of week (cron 0-7 -> python 0-6 where Monday is 0, Sunday is 6)
        cron_dows = parse_cron_field(fields[4], 0, 7)
        self.dows = set()
        for d in cron_dows:
            if d == 0 or d == 7:
                self.dows.add(6)  # Sunday
            else:
                self.dows.add(d - 1)

    def matches(self, dt: datetime.datetime) -> bool:
        """Check if the cron job matches the given datetime."""
        # Note: standard cron has OR behavior for DOM and DOW if both are specified and not *.
        # For simplicity and general use, we do a basic intersection check.
        if dt.minute not in self.minutes:
            return False
        if dt.hour not in self.hours:
            return False
        if dt.month not in self.months:
            return False
        if dt.day not in self.doms:
            return False
        if dt.weekday() not in self.dows:
            return False
        return True

def parse_crontab(filepath: str) -> List[CronJob]:
    """Parse crontab file and return a list of CronJob instances."""
    jobs = []
    with open(filepath, 'r', encoding='utf-8') as f:
        for idx, line in enumerate(f, start=1):
            line = line.strip()
            # Skip comments and blank lines
            if not line or line.startswith("#") or line.startswith(";"):
                continue
                
            # Try to split cron fields from the job name/command
            parts = line.split(None, 5)
            if len(parts) >= 5:
                schedule = " ".join(parts[:5])
                command = parts[5] if len(parts) > 5 else f"Job on line {idx}"
                try:
                    jobs.append(CronJob(schedule, command))
                except ValueError as e:
                    print(f"Warning: Line {idx} is invalid: {e}", file=sys.stderr)
            else:
                print(f"Warning: Line {idx} does not have enough fields to be a cron job", file=sys.stderr)
    return jobs

def project_schedule(jobs: List[CronJob], start_dt: datetime.datetime, hours_window: int) -> Dict[datetime.datetime, List[CronJob]]:
    """Generate the execution schedule for all jobs minute-by-minute within the time window."""
    schedule_map = {}
    end_dt = start_dt + datetime.timedelta(hours=hours_window)
    
    curr = start_dt.replace(second=0, microsecond=0)
    # Check minute by minute
    while curr < end_dt:
        matched_jobs = []
        for job in jobs:
            if job.matches(curr):
                matched_jobs.append(job)
                
        if matched_jobs:
            schedule_map[curr] = matched_jobs
            
        curr += datetime.timedelta(minutes=1)
        
    return schedule_map

def display_timeline(schedule_map: Dict[datetime.datetime, List[CronJob]], start_dt: datetime.datetime, hours_window: int) -> None:
    """Print an ASCII timeline representing cron job execution density."""
    print(f"\n{COLORS['BOLD']}--- Hourly Concurrency Density Timeline ---{COLORS['RESET']}")
    print(f"Start Time: {start_dt.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Duration:   {hours_window} hours\n")
    
    # Process hourly buckets
    for h in range(hours_window):
        hour_dt = start_dt + datetime.timedelta(hours=h)
        hour_start = hour_dt.replace(minute=0, second=0, microsecond=0)
        
        # Count total triggers in this hour
        total_triggers = 0
        peak_concurrency = 0
        jobs_in_hour = set()
        
        for m in range(60):
            check_dt = hour_start + datetime.timedelta(minutes=m)
            if check_dt in schedule_map:
                trigger_count = len(schedule_map[check_dt])
                total_triggers += trigger_count
                peak_concurrency = max(peak_concurrency, trigger_count)
                for job in schedule_map[check_dt]:
                    jobs_in_hour.add(job.command)
                    
        # Generate ASCII bar (scaled to max 40 chars)
        bar_len = min(40, total_triggers)
        bar = "█" * bar_len
        
        # Color coding bar depending on density
        if peak_concurrency > 3:
            color = COLORS["RED"]
        elif peak_concurrency > 1:
            color = COLORS["YELLOW"]
        elif total_triggers > 0:
            color = COLORS["GREEN"]
        else:
            color = COLORS["RESET"]
            bar = "."
            
        hour_label = hour_start.strftime("%m-%d %H:%M")
        meta_info = f"({total_triggers:2} runs, max concurrency: {peak_concurrency})" if total_triggers > 0 else ""
        
        print(f" {hour_label} | {color}{bar:<40}{COLORS['RESET']} {meta_info}")

def display_collisions(schedule_map: Dict[datetime.datetime, List[CronJob]]) -> None:
    """Analyze and print all execution collisions (when multiple jobs run at the same minute)."""
    collisions = {dt: jobs for dt, jobs in schedule_map.items() if len(jobs) > 1}
    
    print(f"\n{COLORS['BOLD']}--- Cron Schedule Collisions ---{COLORS['RESET']}")
    if not collisions:
        print(f"{COLORS['GREEN']}No timing collisions detected! No two jobs run in the same minute.{COLORS['RESET']}")
        return
        
    print(f"Detected {len(collisions)} instances of timing collisions:\n")
    
    # Sort collisions chronologically
    sorted_times = sorted(collisions.keys())
    for dt in sorted_times[:30]:  # Limit to top 30
        jobs = collisions[dt]
        time_str = dt.strftime("%Y-%m-%d %H:%M")
        print(f" {COLORS['RED']}{time_str}{COLORS['RESET']} - {COLORS['BOLD']}{len(jobs)} jobs colliding:{COLORS['RESET']}")
        for j in jobs:
            print(f"   * [{j.schedule}] {j.command}")
            
    if len(sorted_times) > 30:
        print(f"   ... and {len(sorted_times) - 30} more collisions.")

def main():
    parser = argparse.ArgumentParser(
        description="Cron Schedule Collision Finder & Timeline Analyzer.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/cron_collision_finder.py -c "*/5 * * * *" "0 * * * *" -w 12
  python tools/cron_collision_finder.py -f my_crontab.txt --window 48
        """
    )
    parser.add_argument("-c", "--cron", action="append", help="Cron expression to analyze (can specify multiple)")
    parser.add_argument("-f", "--file", help="Path to crontab file containing cron jobs")
    parser.add_argument("-w", "--window", type=int, default=24, help="Analysis window in hours (default: 24)")
    parser.add_argument("-s", "--start", help="Start timestamp for analysis (ISO YYYY-MM-DD HH:MM, default: now)")

    args = parser.parse_args()

    jobs = []
    
    # Load from file
    if args.file:
        try:
            jobs.extend(parse_crontab(args.file))
        except Exception as e:
            print(f"Error loading crontab file {args.file}: {e}", file=sys.stderr)
            sys.exit(1)
            
    # Load from cron arguments
    if args.cron:
        for idx, expr in enumerate(args.cron, start=1):
            try:
                jobs.append(CronJob(expr, f"CLI Cron Job #{idx}"))
            except ValueError as e:
                print(f"Error parsing cron argument '{expr}': {e}", file=sys.stderr)
                sys.exit(1)

    if not jobs:
        print("Error: No cron jobs specified. Use -c/--cron or -f/--file to load jobs.", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    # Parse start time
    if args.start:
        try:
            start_dt = datetime.datetime.fromisoformat(args.start)
        except ValueError:
            try:
                start_dt = datetime.datetime.strptime(args.start, "%Y-%m-%d %H:%M")
            except ValueError:
                print("Error: Start time must be in ISO format (YYYY-MM-DD[THH:MM] or YYYY-MM-DD HH:MM)", file=sys.stderr)
                sys.exit(1)
    else:
        start_dt = datetime.datetime.now()

    print(f"Loaded {len(jobs)} cron jobs.")
    
    # Run projection
    schedule_map = project_schedule(jobs, start_dt, args.window)
    
    # Display results
    display_timeline(schedule_map, start_dt, args.window)
    display_collisions(schedule_map)

if __name__ == "__main__":
    main()
