#!/usr/bin/env python3
"""
CSV Time-Series Resampler & Aggregator
Resamples and aggregates time-series CSV data into regular intervals (hourly, daily, weekly, monthly)
with aggregation functions (sum, mean, min, max, count, first, last) and gap filling strategies.

Uses only standard Python libraries.
"""

import argparse
import csv
import json
import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta


def parse_timestamp(val):
    """Attempt parsing multiple common ISO and standard date formats."""
    val = val.strip()
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y",
        "%m/%d/%Y %H:%M:%S",
        "%m/%d/%Y"
    ]
    for fmt in formats:
        try:
            return datetime.strptime(val, fmt)
        except ValueError:
            pass
    try:
        # ISO fallback
        return datetime.fromisoformat(val)
    except Exception:
        return None


def parse_interval(interval_str):
    """Parse string like '1h', '15m', '1d', '1w', '1m' into timedelta or interval spec."""
    interval_str = interval_str.lower().strip()
    num = int(''.join(filter(str.isdigit, interval_str)) or 1)
    unit = ''.join(filter(str.isalpha, interval_str))
    
    if unit in ('m', 'min', 'minute', 'minutes'):
        return timedelta(minutes=num)
    elif unit in ('h', 'hr', 'hour', 'hours'):
        return timedelta(hours=num)
    elif unit in ('d', 'day', 'days'):
        return timedelta(days=num)
    elif unit in ('w', 'week', 'weeks'):
        return timedelta(weeks=num)
    elif unit in ('mo', 'month', 'months'):
        return timedelta(days=30 * num) # approximation for bucket grouping
    else:
        raise ValueError(f"Unknown interval unit: {unit}")


def floor_datetime(dt, interval):
    """Floor a datetime to the start of interval bucket."""
    seconds = int(interval.total_seconds())
    if seconds >= 86400 * 30: # Monthly
        return datetime(dt.year, dt.month, 1)
    elif seconds >= 86400 * 7: # Weekly
        start_of_week = dt - timedelta(days=dt.weekday())
        return datetime(start_of_week.year, start_of_week.month, start_of_week.day)
    elif seconds >= 86400: # Daily
        return datetime(dt.year, dt.month, dt.day)
    else:
        epoch = datetime(1970, 1, 1)
        total_sec = int((dt - epoch).total_seconds())
        floored_sec = (total_sec // seconds) * seconds
        return epoch + timedelta(seconds=floored_sec)


def aggregate_values(values, method):
    if not values:
        return None
    if method == "sum":
        return sum(values)
    elif method in ("mean", "avg"):
        return sum(values) / len(values)
    elif method == "min":
        return min(values)
    elif method == "max":
        return max(values)
    elif method == "count":
        return len(values)
    elif method == "first":
        return values[0]
    elif method == "last":
        return values[-1]
    else:
        return sum(values) / len(values)


def draw_ascii_sparkline(series, width=40):
    """Draw a simple ASCII line chart in terminal."""
    if not series:
        return ""
    vals = [v for _, v in series if v is not None]
    if not vals:
        return ""
    min_v, max_v = min(vals), max(vals)
    rng = max_v - min_v if max_v != min_v else 1.0
    
    # Check if stdout supports unicode block characters
    try:
        "▂".encode(sys.stdout.encoding or 'ascii')
        ticks = " ▂▃▄▅▆▇█"
    except Exception:
        ticks = " .:-=+*#%"

    chart = []
    for _, v in series:
        if v is None:
            chart.append(" ")
        else:
            idx = int(((v - min_v) / rng) * (len(ticks) - 1))
            chart.append(ticks[idx])
    return "".join(chart)


def resample_csv(reader, time_col, value_cols, interval_td, agg_method="mean", fill_strategy="none"):
    rows = list(reader)
    if not rows:
        return [], []

    # Map timestamps to floored bucket
    buckets = defaultdict(lambda: defaultdict(list))
    all_dates = []

    for row in rows:
        dt_raw = row.get(time_col)
        if not dt_raw:
            continue
        dt = parse_timestamp(dt_raw)
        if not dt:
            continue

        bucket_dt = floor_datetime(dt, interval_td)
        all_dates.append(bucket_dt)

        for col in value_cols:
            if col in row and row[col] != "":
                try:
                    buckets[bucket_dt][col].append(float(row[col]))
                except ValueError:
                    pass

    if not all_dates:
        return [], []

    min_dt, max_dt = min(all_dates), max(all_dates)

    # Generate continuous series if filling required
    curr = min_dt
    sorted_buckets = []
    while curr <= max_dt:
        sorted_buckets.append(curr)
        curr += interval_td

    output_rows = []
    last_known = {col: None for col in value_cols}

    for bucket_dt in sorted_buckets:
        row_out = {"timestamp": bucket_dt.strftime("%Y-%m-%d %H:%M:%S")}
        bucket_data = buckets.get(bucket_dt, {})

        for col in value_cols:
            vals = bucket_data.get(col, [])
            if vals:
                agg = aggregate_values(vals, agg_method)
                row_out[col] = round(agg, 4)
                last_known[col] = row_out[col]
            else:
                if fill_strategy == "zero":
                    row_out[col] = 0.0
                elif fill_strategy == "ffill":
                    row_out[col] = last_known[col]
                else:
                    row_out[col] = None
        output_rows.append(row_out)

    return output_rows, value_cols


def run_demo():
    print("=== Running CSV Time-Series Resampler Demo ===")
    sample_csv_data = [
        {"timestamp": "2026-07-06 01:05:00", "requests": "120", "cpu_pct": "45.2"},
        {"timestamp": "2026-07-06 01:22:00", "requests": "180", "cpu_pct": "58.1"},
        {"timestamp": "2026-07-06 02:10:00", "requests": "250", "cpu_pct": "72.4"},
        {"timestamp": "2026-07-06 02:45:00", "requests": "310", "cpu_pct": "81.0"},
        {"timestamp": "2026-07-06 03:15:00", "requests": "90",  "cpu_pct": "32.5"},
        {"timestamp": "2026-07-06 04:50:00", "requests": "400", "cpu_pct": "94.8"}
    ]

    interval_td = parse_interval("1h")
    res, cols = resample_csv(sample_csv_data, "timestamp", ["requests", "cpu_pct"], interval_td, agg_method="mean", fill_strategy="zero")

    print("\nResampled 1-Hour Aggregated Results (Mean):")
    print(f"{'Timestamp':<22} {'Requests (Mean)':<18} {'CPU Pct (Mean)'}")
    print("-" * 55)
    for r in res:
        print(f"{r['timestamp']:<22} {str(r['requests']):<18} {str(r['cpu_pct'])}")

    spark = draw_ascii_sparkline([(r['timestamp'], r['requests']) for r in res])
    print(f"\nRequests Trend Sparkline: [{spark}]")


def main():
    parser = argparse.ArgumentParser(
        description="CSV Time-Series Resampler & Aggregator - Resample time series CSV files to uniform time buckets."
    )
    parser.add_argument("file", nargs="?", help="CSV file path")
    parser.add_argument("-t", "--time-col", default="timestamp", help="Name of time/date column")
    parser.add_argument("-v", "--value-cols", help="Comma-separated list of value columns to aggregate")
    parser.add_argument("-i", "--interval", default="1h", help="Resample interval (e.g. 15m, 1h, 1d, 1w)")
    parser.add_argument("-a", "--agg", choices=["sum", "mean", "min", "max", "count", "first", "last"], default="mean", help="Aggregation method")
    parser.add_argument("-f", "--fill", choices=["none", "zero", "ffill"], default="none", help="Gap filling strategy")
    parser.add_argument("--json", action="store_true", help="Output JSON format")
    parser.add_argument("--demo", action="store_true", help="Run demonstration")

    args = parser.parse_args()

    if args.demo or (not args.file and sys.stdin.isatty()):
        run_demo()
        return

    try:
        interval_td = parse_interval(args.interval)
    except Exception as e:
        print(f"Error parsing interval: {e}", file=sys.stderr)
        sys.exit(1)

    if args.file:
        if not os.path.exists(args.file):
            print(f"Error: File '{args.file}' not found.", file=sys.stderr)
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8", errors="ignore") as f:
            reader = list(csv.DictReader(f))
    else:
        reader = list(csv.DictReader(sys.stdin))

    if not reader:
        print("No CSV data provided.", file=sys.stderr)
        sys.exit(1)

    all_keys = list(reader[0].keys())
    if args.time_col not in all_keys:
        print(f"Error: Time column '{args.time_col}' not found in CSV headers: {all_keys}", file=sys.stderr)
        sys.exit(1)

    if args.value_cols:
        val_cols = [c.strip() for c in args.value_cols.split(",") if c.strip() in all_keys]
    else:
        val_cols = [c for c in all_keys if c != args.time_col]

    res, cols = resample_csv(reader, args.time_col, val_cols, interval_td, agg_method=args.agg, fill_strategy=args.fill)

    if args.json:
        print(json.dumps(res, indent=2))
    else:
        writer = csv.DictWriter(sys.stdout, fieldnames=["timestamp"] + val_cols)
        writer.writeheader()
        for r in res:
            writer.writerow(r)


if __name__ == "__main__":
    main()
