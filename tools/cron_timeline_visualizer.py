#!/usr/bin/env python3
"""
Cron Timeline Visualizer
Parses crontab files or cron expressions and visualizes scheduled executions
over a 24-hour period using a terminal-friendly ASCII/Unicode timeline.
"""

import argparse
import datetime
import re
import sys
from typing import Dict, List, Set, Tuple

# Try to reconfigure stdout to UTF-8 on Windows to support Unicode blocks
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass


def get_timeline_char(char_type: str) -> str:
    """Returns Unicode characters if supported by stdout encoding, else ASCII fallbacks."""
    # Check if the terminal encoding supports Unicode block characters
    encoding = sys.stdout.encoding or "utf-8"
    try:
        "█".encode(encoding)
        "■".encode(encoding)
        supports_unicode = True
    except UnicodeEncodeError:
        supports_unicode = False

    if char_type == "heavy":
        return "█" if supports_unicode else "#"
    elif char_type == "light":
        return "■" if supports_unicode else "*"
    elif char_type == "idle":
        return "."
    return " "


class CronFieldParser:
    """Parses individual cron fields into sets of allowed integer values."""

    @staticmethod
    def parse_field(field: str, min_val: int, max_val: int, aliases: Dict[str, int] = None) -> Set[int]:
        if aliases:
            for name, val in aliases.items():
                field = re.sub(re.escape(name), str(val), field, flags=re.IGNORECASE)

        allowed = set()
        parts = field.split(",")
        for part in parts:
            if part == "*":
                allowed.update(range(min_val, max_val + 1))
            elif "/" in part:
                base, step = part.split("/")
                step = int(step)
                if base == "*":
                    allowed.update(range(min_val, max_val + 1, step))
                elif "-" in base:
                    start, end = base.split("-")
                    allowed.update(range(int(start), int(end) + 1, step))
                else:
                    allowed.update(range(int(base), max_val + 1, step))
            elif "-" in part:
                start, end = part.split("-")
                allowed.update(range(int(start), int(end) + 1))
            else:
                allowed.add(int(part))
        return {v for v in allowed if min_val <= v <= max_val}


class CronJob:
    """Represents a parsed cron job schedule and command."""

    MONTHS = {
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
        "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12
    }
    DAYS_OF_WEEK = {
        "sun": 0, "mon": 1, "tue": 2, "wed": 3, "thu": 4, "fri": 5, "sat": 6
    }

    def __init__(self, cron_str: str, default_command: str = "Job"):
        self.cron_str = cron_str.strip()
        self.command = default_command
        self.is_valid = False

        # Parse schedule and command
        match = re.match(r"^([^\s]+\s+[^\s]+\s+[^\s]+\s+[^\s]+\s+[^\s]+)(?:\s+(.*))?$", self.cron_str)
        if not match:
            return

        schedule_part = match.group(1)
        if match.group(2):
            self.command = match.group(2).strip()

        fields = schedule_part.split()
        if len(fields) != 5:
            return

        try:
            self.minutes = CronFieldParser.parse_field(fields[0], 0, 59)
            self.hours = CronFieldParser.parse_field(fields[1], 0, 23)
            self.doms = CronFieldParser.parse_field(fields[2], 1, 31)
            self.months = CronFieldParser.parse_field(fields[3], 1, 12, self.MONTHS)
            
            # 0 and 7 can both represent Sunday
            dows_raw = CronFieldParser.parse_field(fields[4], 0, 7, self.DAYS_OF_WEEK)
            self.dows = {0 if d == 7 else d for d in dows_raw}

            self.is_valid = True
            self.dom_restricted = fields[2] != "*"
            self.dow_restricted = fields[4] != "*"
        except ValueError:
            self.is_valid = False

    def matches(self, dt: datetime.datetime) -> bool:
        """Checks if this job is scheduled to run at the given datetime."""
        if not self.is_valid:
            return False

        if dt.minute not in self.minutes:
            return False
        if dt.hour not in self.hours:
            return False
        if dt.month not in self.months:
            return False

        # If both DOM and DOW are restricted, matching either is sufficient
        if self.dom_restricted and self.dow_restricted:
            return (dt.day in self.doms) or (dt.weekday() in self.dows)
        
        if self.dom_restricted:
            return dt.day in self.doms
        if self.dow_restricted:
            # Python weekday is 0 (Monday) to 6 (Sunday)
            # Cron weekday is 0 (Sunday) to 6 (Saturday)
            cron_dow = (dt.weekday() + 1) % 7
            return cron_dow in self.dows

        return True


def parse_crontab(content: str) -> List[CronJob]:
    """Parses a crontab file string into a list of CronJobs."""
    jobs = []
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" in line.split(None, 1)[0]:
            # Skip comments, empty lines, and env variables
            continue
        job = CronJob(line)
        if job.is_valid:
            jobs.append(job)
    return jobs


def generate_timeline(jobs: List[CronJob], date_str: str = None) -> Tuple[Dict[int, List[Tuple[int, CronJob]]], int]:
    """Simulates job runs for a day and organizes them by hour and minute."""
    if date_str:
        base_date = datetime.datetime.strptime(date_str, "%Y-%m-%d")
    else:
        base_date = datetime.datetime.now()
    
    # Start of day
    start_time = datetime.datetime(base_date.year, base_date.month, base_date.day, 0, 0)
    
    timeline = {h: [] for h in range(24)}
    total_runs = 0

    for minute_offset in range(1440):
        current_time = start_time + datetime.timedelta(minutes=minute_offset)
        hour = current_time.hour
        minute = current_time.minute

        for job in jobs:
            if job.matches(current_time):
                timeline[hour].append((minute, job))
                total_runs += 1

    return timeline, total_runs


def print_timeline(timeline: Dict[int, List[Tuple[int, CronJob]]], total_runs: int, date_label: str):
    """Renders the timeline to the console."""
    print(f"\nCron Timeline for {date_label}")
    print(f"Total Scheduled Executions: {total_runs}\n")

    if total_runs == 0:
        print("No job runs scheduled for this period.")
        return

    heavy_char = get_timeline_char("heavy")
    light_char = get_timeline_char("light")
    idle_char = get_timeline_char("idle")

    # Visual timeline header
    print(" Hour  " + "".join([str(m // 10) if m % 10 == 0 else " " for m in range(60)]))
    print("       " + "".join([str(m % 10) if m % 10 == 0 else "." for m in range(60)]) + "  [Runs]")
    print(" " + "-" * 73)

    for hour in range(24):
        runs_in_hour = timeline[hour]
        run_minutes = {minute for minute, _ in runs_in_hour}
        
        # Build hourly character line
        line_chars = []
        for m in range(60):
            if m in run_minutes:
                # Count overlaps at this minute
                overlaps = sum(1 for minute, _ in runs_in_hour if minute == m)
                if overlaps > 1:
                    line_chars.append(f"\033[91m{heavy_char}\033[0m" if sys.stdout.isatty() else heavy_char)
                else:
                    line_chars.append(f"\033[92m{heavy_char}\033[0m" if sys.stdout.isatty() else light_char)
            else:
                line_chars.append(idle_char)
        
        hour_str = f"{hour:02d}:00"
        runs_count = len(runs_in_hour)
        runs_count_str = f"({runs_count})" if runs_count > 0 else ""
        print(f" {hour_str} " + "".join(line_chars) + f"  {runs_count_str}")

    print(" " + "-" * 73)
    print(f"Legend: [{idle_char}] Idle   [{light_char}] 1 Job   [{heavy_char}] Multiple Overlapping Jobs")


def print_hotspots(timeline: Dict[int, List[Tuple[int, CronJob]]]):
    """Prints hours and minutes with high volumes of scheduled jobs."""
    hourly_counts = [(h, len(timeline[h])) for h in range(24)]
    hourly_counts.sort(key=lambda x: x[1], reverse=True)

    print("\n--- Hourly Hotspots ---")
    for hour, count in hourly_counts[:5]:
        if count > 0:
            print(f" Hour {hour:02d}:00 - {count} execution(s)")

    # Minute hotspots
    minute_counts = {}
    for hour, runs in timeline.items():
        for minute, job in runs:
            key = f"{hour:02d}:{minute:02d}"
            minute_counts[key] = minute_counts.get(key, 0) + 1
    
    minute_hotspots = sorted(minute_counts.items(), key=lambda x: x[1], reverse=True)
    print("\n--- Top Minute Hotspots ---")
    for time_str, count in minute_hotspots[:5]:
        if count > 0:
            print(f" Time {time_str} - {count} concurrent job(s)")


def print_job_list(timeline: Dict[int, List[Tuple[int, CronJob]]]):
    """Prints details of all scheduled jobs and their execution times."""
    print("\n--- Scheduled Job List (Chronological) ---")
    printed_any = False
    for hour in range(24):
        runs = sorted(timeline[hour], key=lambda x: x[0])
        for minute, job in runs:
            print(f" {hour:02d}:{minute:02d} | Command: {job.command} (Schedule: {job.cron_str.split(None, 5)[:5]})")
            printed_any = True
    if not printed_any:
        print(" No jobs scheduled.")


def main():
    parser = argparse.ArgumentParser(
        description="Visualize cron schedule execution patterns over a 24-hour period."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-f", "--file", help="Path to a crontab file to parse")
    group.add_argument("-e", "--expression", nargs="+", help="One or more cron expressions to visualize (e.g. '*/15 * * * *')")
    
    parser.add_argument("-d", "--date", help="Target date in YYYY-MM-DD format (default: today)")
    parser.add_argument("-l", "--list-jobs", action="store_true", help="Print the detailed list of jobs chronologically")
    parser.add_argument("-s", "--hotspots", action="store_true", help="Print hotspots and concurrency bottlenecks")

    args = parser.parse_args()

    jobs = []
    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                jobs = parse_crontab(f.read())
        except Exception as e:
            print(f"Error reading file {args.file}: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.expression:
        for idx, expr in enumerate(args.expression):
            job = CronJob(expr, default_command=f"Job #{idx + 1}")
            if job.is_valid:
                jobs.append(job)
            else:
                print(f"Warning: Invalid cron expression skipped: '{expr}'", file=sys.stderr)

    if not jobs:
        print("No valid cron schedules found.", file=sys.stderr)
        sys.exit(1)

    target_date = args.date or datetime.datetime.now().strftime("%Y-%m-%d")
    timeline, total_runs = generate_timeline(jobs, target_date)

    print_timeline(timeline, total_runs, target_date)

    if args.hotspots:
        print_hotspots(timeline)

    if args.list_jobs:
        print_job_list(timeline)


if __name__ == "__main__":
    main()
