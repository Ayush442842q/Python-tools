#!/usr/bin/env python3
"""
CSV Profiler - Profile and analyze CSV structure and statistics without external dependencies

This tool parses a CSV file, infers data types of each column, computes statistics
(min, max, mean, median, standard deviation, missing values, uniqueness), and prints
a detailed summary report to the console or writes it to a JSON file.

Usage:
    python tools/csv_profiler.py CSV_FILE [options]

Options:
    -d, --delimiter CHAR    Field delimiter (default: comma ',')
    -o, --output FILE       Write profiling results to a JSON file
    -l, --limit N           Limit analysis to the first N rows
    -h, --help              Show this help message and exit

Example:
    python tools/csv_profiler.py data.csv -d ";"
"""

import argparse
import collections
import csv
import datetime
import math
import os
import sys
import json
from typing import List, Dict, Any, Tuple, Optional


def infer_type(val: str) -> str:
    """Infer the type of a string value."""
    val = val.strip()
    if not val:
        return 'null'
    
    # Check boolean
    if val.lower() in ('true', 'false', 'yes', 'no', 't', 'f', '1', '0'):
        return 'boolean'
        
    # Check integer
    try:
        int(val)
        return 'integer'
    except ValueError:
        pass
        
    # Check float
    try:
        float(val)
        return 'float'
    except ValueError:
        pass
        
    # Check datetime
    for fmt in ('%Y-%m-%d', '%Y-%m-%d %H:%M:%S', '%m/%d/%Y', '%d/%m/%Y'):
        try:
            datetime.datetime.strptime(val, fmt)
            return 'date'
        except ValueError:
            pass
            
    return 'string'


def calculate_stats(values: List[Any], val_type: str) -> Dict[str, Any]:
    """Calculate statistics based on inferred type."""
    stats: Dict[str, Any] = {}
    
    if not values:
        return stats

    if val_type in ('integer', 'float'):
        numeric = [float(v) for v in values if v is not None]
        if not numeric:
            return stats
        
        numeric.sort()
        n = len(numeric)
        
        stats['min'] = min(numeric)
        stats['max'] = max(numeric)
        
        mean = sum(numeric) / n
        stats['mean'] = mean
        
        # Median
        if n % 2 == 1:
            stats['median'] = numeric[n // 2]
        else:
            stats['median'] = (numeric[n // 2 - 1] + numeric[n // 2]) / 2.0
            
        # Standard deviation
        variance = sum((x - mean) ** 2 for x in numeric) / n
        stats['std_dev'] = math.sqrt(variance)

    elif val_type == 'string':
        lengths = [len(str(v)) for v in values if v is not None]
        if lengths:
            stats['min_len'] = min(lengths)
            stats['max_len'] = max(lengths)
            stats['avg_len'] = sum(lengths) / len(lengths)

    # Frequency and Mode
    counter = collections.Counter(values)
    most_common = counter.most_common(1)
    if most_common:
        mode_val, mode_count = most_common[0]
        stats['mode'] = str(mode_val)
        stats['mode_freq'] = mode_count

    return stats


def profile_csv(file_path: str, delimiter: str, limit: Optional[int]) -> Tuple[List[str], Dict[str, Any], int]:
    """Profile the CSV file structure and values."""
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        # Sneak peek to auto-detect dialect if delimiter not specified
        try:
            sample = f.read(2048)
            f.seek(0)
            if not delimiter:
                dialect = csv.Sniffer().sniff(sample)
                delimiter = dialect.delimiter
        except Exception:
            if not delimiter:
                delimiter = ','

        reader = csv.reader(f, delimiter=delimiter)
        try:
            headers = next(reader)
        except StopIteration:
            raise ValueError("CSV file is empty.")

        # Clean headers
        headers = [h.strip() if h else f"Unnamed_{i}" for i, h in enumerate(headers)]
        num_cols = len(headers)
        
        col_data = collections.defaultdict(list)
        null_counts = collections.defaultdict(int)
        row_count = 0

        for row in reader:
            if limit and row_count >= limit:
                break
                
            # Handle row size mismatch
            if len(row) < num_cols:
                row.extend([''] * (num_cols - len(row)))
            elif len(row) > num_cols:
                row = row[:num_cols]

            for i, val in enumerate(row):
                val_stripped = val.strip()
                if val_stripped == '':
                    null_counts[i] += 1
                else:
                    col_data[i].append(val_stripped)

            row_count += 1

    profile = {}
    for i in range(num_cols):
        col_name = headers[i]
        vals = col_data[i]
        nulls = null_counts[i]
        
        # Determine column type by voting on types
        types = [infer_type(v) for v in vals]
        type_counts = collections.Counter(types)
        
        # Get most common type that is not 'null'
        inferred_type = 'string'
        for t, _ in type_counts.most_common():
            if t != 'null':
                inferred_type = t
                break
                
        # Calculate distinct value count
        distinct_vals = len(set(vals))
        
        # Convert values to correct inferred type where possible
        typed_vals = []
        for v in vals:
            try:
                if inferred_type == 'integer':
                    typed_vals.append(int(v))
                elif inferred_type == 'float':
                    typed_vals.append(float(v))
                elif inferred_type == 'boolean':
                    typed_vals.append(v.lower() in ('true', 'yes', 't', '1'))
                else:
                    typed_vals.append(v)
            except ValueError:
                typed_vals.append(v) # Fallback to string

        stats = calculate_stats(typed_vals, inferred_type)
        
        profile[col_name] = {
            'index': i,
            'type': inferred_type,
            'non_null_count': len(vals),
            'null_count': nulls,
            'null_percentage': (nulls / (row_count) * 100) if row_count > 0 else 0.0,
            'distinct_count': distinct_vals,
            'uniqueness_percentage': (distinct_vals / len(vals) * 100) if vals else 0.0,
            'statistics': stats
        }

    return headers, profile, row_count


def render_report(headers: List[str], profile: Dict[str, Any], total_rows: int):
    """Render profile report in a clean terminal table layout."""
    print("=" * 100)
    print(f"CSV FILE PROFILER REPORT - Total Processed Rows: {total_rows}")
    print("=" * 100)
    
    # Table layout parameters
    col_width_name = max(len(h) for h in headers)
    col_width_name = max(col_width_name, 12)
    
    header_fmt = f"{{:<{col_width_name}}} | {{:<8}} | {{:<9}} | {{:<9}} | {{:<10}} | {{:<20}}"
    print(header_fmt.format("Column Name", "Type", "Nulls (%)", "Distinct", "Unique (%)", "Metrics Summary"))
    print("-" * 100)
    
    for name in headers:
        col = profile[name]
        null_desc = f"{col['null_count']} ({col['null_percentage']:.1f}%)"
        unique_desc = f"{col['uniqueness_percentage']:.1f}%"
        
        stats = col['statistics']
        metrics = []
        
        if col['type'] in ('integer', 'float'):
            if 'min' in stats:
                metrics.append(f"min={stats['min']:.2f}")
            if 'max' in stats:
                metrics.append(f"max={stats['max']:.2f}")
            if 'mean' in stats:
                metrics.append(f"mean={stats['mean']:.2f}")
            if 'median' in stats:
                metrics.append(f"median={stats['median']:.2f}")
        elif col['type'] == 'string':
            if 'avg_len' in stats:
                metrics.append(f"avg_len={stats['avg_len']:.1f}")
            if 'mode' in stats:
                metrics.append(f"mode='{stats['mode']}'")
        elif col['type'] == 'boolean':
            if 'mode' in stats:
                metrics.append(f"mode={stats['mode']}")
                
        metrics_summary = ", ".join(metrics)[:40]
        
        print(header_fmt.format(
            name[:col_width_name], 
            col['type'], 
            null_desc, 
            col['distinct_count'], 
            unique_desc, 
            metrics_summary
        ))
    print("=" * 100)


def main():
    parser = argparse.ArgumentParser(description="Profile CSV column structure and descriptive statistics.")
    parser.add_argument("csvfile", help="Path to the CSV file to profile")
    parser.add_argument("-d", "--delimiter", help="Field delimiter character (defaults to auto-detect or comma)")
    parser.add_argument("-o", "--output", help="Write profiling results as JSON to specified output path")
    parser.add_argument("-l", "--limit", type=int, help="Limit analysis to first N data rows")

    args = parser.parse_args()

    if not os.path.exists(args.csvfile):
        print(f"Error: CSV file not found: {args.csvfile}", file=sys.stderr)
        return 1

    try:
        headers, profile, total_rows = profile_csv(args.csvfile, args.delimiter, args.limit)
    except Exception as e:
        print(f"Error profiling CSV: {e}", file=sys.stderr)
        return 1

    if args.output:
        try:
            w_mode = 'w'
            with open(args.output, w_mode, encoding='utf-8') as f:
                json.dump({
                    'total_rows': total_rows,
                    'columns': profile
                }, f, indent=2)
            print(f"Profiling report written to {args.output}")
        except Exception as e:
            print(f"Error writing output file: {e}", file=sys.stderr)
            return 1
    else:
        render_report(headers, profile, total_rows)

    return 0


if __name__ == "__main__":
    sys.exit(main())
