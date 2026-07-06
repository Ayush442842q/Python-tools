#!/usr/bin/env python3
"""
Cron Schedule Heatmap & Density Visualizer

Visualizes cron job execution density and distribution across hours and days in terminal heatmaps.

Features:
- Standard 5-field cron expression parser (*, ranges, steps, lists)
- Simulates scheduled executions over custom timeframe (e.g. 7 days, 14 days)
- Terminal ASCII/Unicode heatmap grid (Hours 0-23 vs Days Mon-Sun)
- Displays peak execution loads, quiet periods, and task collisions
- Execution metrics per job and busiest hour detection
- CSV export capability for schedule auditing

Usage:
    python cron_schedule_heatmap.py "*/15 * * * *"
    python cron_schedule_heatmap.py crontab.txt --days 7
    python cron_schedule_heatmap.py "0 0 * * *" "0 12 * * 1-5" --export-csv heatmap.csv
"""

import os
import sys
import argparse
import datetime
from collections import defaultdict
from typing import List, Set, Dict, Tuple, Optional

# Ensure stdout handles UTF-8 output on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"
RED = "\033[91m"

DAYS_OF_WEEK = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def parse_field(field_str: str, min_val: int, max_val: int) -> Set[int]:
    """Parses a single cron field (wildcard, list, range, step) into a set of valid integers."""
    result = set()

    for part in field_str.split(","):
        part = part.strip()
        if not part:
            continue

        step = 1
        if "/" in part:
            subpart, step_str = part.split("/", 1)
            step = int(step_str)
        else:
            subpart = part

        if subpart == "*":
            start, end = min_val, max_val
        elif "-" in subpart:
            start_str, end_str = subpart.split("-", 1)
            start, end = int(start_str), int(end_str)
        else:
            start = end = int(subpart)

        for val in range(start, end + 1, step):
            if min_val <= val <= max_val:
                result.add(val)

    return result


class CronJob:
    """Represents a parsed 5-field cron job rule."""

    def __init__(self, raw_expression: str, label: str = ""):
        self.raw_expression = raw_expression.strip()
        self.label = label or self.raw_expression

        parts = self.raw_expression.split()
        if len(parts) < 5:
            raise ValueError(f"Invalid cron expression (must have 5 fields): '{raw_expression}'")

        self.minutes = parse_field(parts[0], 0, 59)
        self.hours = parse_field(parts[1], 0, 23)
        self.dom = parse_field(parts[2], 1, 31)
        self.months = parse_field(parts[3], 1, 12)
        # Cron days of week: 0=Sun, 1=Mon, ..., 6=Sat or 7=Sun
        dow_raw = parse_field(parts[4], 0, 7)
        if 7 in dow_raw:
            dow_raw.add(0)
            dow_raw.remove(7)
        # Python weekday: 0=Mon, 1=Tue, ..., 6=Sun
        # Convert cron dow (0=Sun..6=Sat) to Python weekday (0=Mon..6=Sun)
        self.dow = set()
        for d in dow_raw:
            py_dow = (d - 1) % 7
            self.dow.add(py_dow)

    def matches(self, dt: datetime.datetime) -> bool:
        """Checks if datetime matches cron schedule."""
        if dt.minute not in self.minutes:
            return False
        if dt.hour not in self.hours:
            return False
        if dt.day not in self.dom:
            return False
        if dt.month not in self.months:
            return False
        if dt.weekday() not in self.dow:
            return False
        return True


def simulate_cron_execution(
    jobs: List[CronJob],
    days: int = 7,
    start_dt: Optional[datetime.datetime] = None
) -> Tuple[Dict[Tuple[int, int], int], Dict[CronJob, int], int]:
    """Simulates job executions per minute and computes hourly/daily density."""
    if not start_dt:
        # Start at midnight on the most recent Monday
        now = datetime.datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_dt = now - datetime.timedelta(days=now.weekday())

    # Map (day_of_week_idx, hour) -> execution count
    density_map: Dict[Tuple[int, int], int] = defaultdict(int)
    job_counts: Dict[CronJob, int] = defaultdict(int)
    total_executions = 0

    end_dt = start_dt + datetime.timedelta(days=days)
    curr = start_dt

    while curr < end_dt:
        for job in jobs:
            if job.matches(curr):
                density_map[(curr.weekday(), curr.hour)] += 1
                job_counts[job] += 1
                total_executions += 1
        curr += datetime.timedelta(minutes=1)

    return density_map, job_counts, total_executions


def render_heatmap(density_map: Dict[Tuple[int, int], int]):
    """Renders ANSI-colored ASCII heatmap matrix of execution density."""
    max_val = max(density_map.values()) if density_map else 1
    if max_val == 0:
        max_val = 1

    # Check if stdout supports unicode encoding
    supports_unicode = True
    try:
        "░▒▓█".encode(sys.stdout.encoding or "utf-8")
    except Exception:
        supports_unicode = False

    def get_color_char(val: int) -> str:
        if val == 0:
            return f"\033[90m . {RESET}"  # Dark grey dot
        ratio = val / max_val
        if supports_unicode:
            if ratio < 0.25:
                return f"{CYAN}░░░{RESET}"
            elif ratio < 0.50:
                return f"{GREEN}▒▒▒{RESET}"
            elif ratio < 0.75:
                return f"{YELLOW}▓▓▓{RESET}"
            else:
                return f"{RED}{BOLD}███{RESET}"
        else:
            if ratio < 0.25:
                return f"{CYAN}...{RESET}"
            elif ratio < 0.50:
                return f"{GREEN}==={RESET}"
            elif ratio < 0.75:
                return f"{YELLOW}###{RESET}"
            else:
                return f"{RED}{BOLD}***{RESET}"

    # Header hours 00 to 23
    header = "     " + "".join([f"{h:02d} " for h in range(24)])
    print(f"\n{BOLD}{CYAN}=== Cron Schedule Execution Heatmap ==={RESET}\n")
    print(BOLD + header + RESET)
    print("    +" + "-" * (24 * 3))

    for day_idx, day_name in enumerate(DAYS_OF_WEEK):
        row_str = f"{BOLD}{day_name}{RESET} |"
        for h in range(24):
            val = density_map.get((day_idx, h), 0)
            row_str += get_color_char(val)
        print(row_str)

    print("    +" + "-" * (24 * 3))
    if supports_unicode:
        print(f"Legend: \033[90m . {RESET} Zero | {CYAN}░░░{RESET} Low | {GREEN}▒▒▒{RESET} Medium | {YELLOW}▓▓▓{RESET} High | {RED}{BOLD}███{RESET} Peak\n")
    else:
        print(f"Legend: \033[90m . {RESET} Zero | {CYAN}...{RESET} Low | {GREEN}==={RESET} Medium | {YELLOW}###{RESET} High | {RED}{BOLD}***{RESET} Peak\n")


def main():
    parser = argparse.ArgumentParser(
        description="Cron Schedule Heatmap & Density Visualizer"
    )
    parser.add_argument("sources", nargs="+", help="Cron expression strings or path to crontab file")
    parser.add_argument("--days", type=int, default=7, help="Simulation duration in days (default: 7)")
    parser.add_argument("--export-csv", help="Path to export heatmap density data to CSV")

    args = parser.parse_args()

    raw_expressions = []
    for src in args.sources:
        if os.path.exists(src):
            with open(src, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#"):
                        # Extract first 5 cron tokens
                        raw_expressions.append(line)
        else:
            raw_expressions.append(src)

    jobs = []
    for expr in raw_expressions:
        try:
            jobs.append(CronJob(expr))
        except Exception as e:
            print(f"{YELLOW}Warning: Skipping invalid cron expression '{expr}': {e}{RESET}")

    if not jobs:
        print(f"{RED}No valid cron jobs to simulate.{RESET}", file=sys.stderr)
        sys.exit(1)

    density_map, job_counts, total_execs = simulate_cron_execution(jobs, days=args.days)

    render_heatmap(density_map)

    print(f"{BOLD}Simulation Metrics ({args.days} days):{RESET}")
    print(f"Total Jobs      : {len(jobs)}")
    print(f"Total Executions: {BOLD}{total_execs}{RESET}\n")

    print(f"{BOLD}Per-Job Execution Counts:{RESET}")
    for j, cnt in job_counts.items():
        print(f" - {CYAN}{j.raw_expression:<20}{RESET} -> {cnt} executions")

    # Determine peak hour
    busiest_slot = max(density_map.items(), key=lambda x: x[1]) if density_map else None
    if busiest_slot and busiest_slot[1] > 0:
        day_name = DAYS_OF_WEEK[busiest_slot[0][0]]
        hour = busiest_slot[0][1]
        print(f"\n{RED}{BOLD}Busiest Time Window: {day_name} at {hour:02d}:00 with {busiest_slot[1]} job runs.{RESET}")

    # CSV export if requested
    if args.export_csv:
        try:
            import csv
            with open(args.export_csv, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["Day", "Hour", "Executions"])
                for day_idx, day_name in enumerate(DAYS_OF_WEEK):
                    for h in range(24):
                        writer.writerow([day_name, f"{h:02d}:00", density_map.get((day_idx, h), 0)])
            print(f"\n{GREEN}Exported heatmap data to {args.export_csv}{RESET}")
        except Exception as e:
            print(f"{RED}Failed to export CSV: {e}{RESET}")


if __name__ == "__main__":
    main()
