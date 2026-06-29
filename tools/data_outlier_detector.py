#!/usr/bin/env python3
"""
Data Outlier Detector
Parses CSV or JSON datasets, automatically identifies numerical columns, and scans
for statistical outliers using IQR (Interquartile Range) and Z-score methods.
Renders an ASCII box-and-whisker plot for visual data distribution.
"""

import argparse
import csv
import json
import math
import os
import statistics
import sys
from typing import List, Dict, Any, Tuple, Optional

def load_dataset(filepath: str) -> List[Dict[str, Any]]:
    """Loads CSV or JSON dataset into a list of row dictionaries."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")
        
    _, ext = os.path.splitext(filepath.lower())
    rows = []
    
    if ext == ".csv" or ext == ".txt":
        # Detect delimiter
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            sample = f.read(2048)
            f.seek(0)
            try:
                dialect = csv.Sniffer().sniff(sample)
                reader = csv.DictReader(f, dialect=dialect)
            except Exception:
                reader = csv.DictReader(f) # Fallback to standard CSV
                
            for row in reader:
                rows.append(dict(row))
    elif ext == ".json":
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                rows = data
            elif isinstance(data, dict):
                # Check if it contains a list of objects
                for key, val in data.items():
                    if isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict):
                        rows = val
                        break
                if not rows:
                    raise ValueError("JSON dictionary must contain a list of records under one of the keys.")
            else:
                raise ValueError("JSON file must be an array of objects.")
    else:
        raise ValueError("Unsupported file format. Please provide a CSV or JSON file.")
        
    return rows

def identify_numerical_columns(rows: List[Dict[str, Any]]) -> List[str]:
    """Identifies which columns are consistently numerical."""
    if not rows:
        return []
        
    candidates = list(rows[0].keys())
    numerical_cols = []
    
    for col in candidates:
        numeric_count = 0
        total_count = 0
        
        for row in rows:
            val = row.get(col)
            if val is None or val.strip() == "":
                continue # Skip blanks
            total_count += 1
            try:
                float(val)
                numeric_count += 1
            except ValueError:
                pass
                
        # If at least 80% of non-empty values are numeric, classify as numerical column
        if total_count > 0 and (numeric_count / total_count) >= 0.8:
            numerical_cols.append(col)
            
    return numerical_cols

def extract_column_data(rows: List[Dict[str, Any]], column: str) -> List[Tuple[int, float]]:
    """Extracts numerical values with their original row index (1-based, excluding header)."""
    data = []
    for idx, row in enumerate(rows):
        val = row.get(column)
        if val is None or val.strip() == "":
            continue
        try:
            data.append((idx + 1, float(val)))
        except ValueError:
            pass
    return data

def detect_outliers_iqr(values_with_idx: List[Tuple[int, float]]) -> Tuple[List[Dict[str, Any]], Dict[str, float]]:
    """Detects outliers using the Interquartile Range (IQR) method."""
    vals = [x[1] for x in values_with_idx]
    if len(vals) < 4:
        return [], {}
        
    vals_sorted = sorted(vals)
    n = len(vals_sorted)
    
    # Calculate Q1 (25th percentile) and Q3 (75th percentile)
    q1 = statistics.median(vals_sorted[:n//2])
    q3 = statistics.median(vals_sorted[(n+1)//2:])
    
    iqr = q3 - q1
    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr
    
    outliers = []
    for idx, val in values_with_idx:
        if val < lower_bound or val > upper_bound:
            direction = "LOW" if val < lower_bound else "HIGH"
            outliers.append({
                "row": idx,
                "value": val,
                "method": "IQR",
                "info": f"{direction} (Bound: [{lower_bound:.2f}, {upper_bound:.2f}])"
            })
            
    stats = {
        "min": vals_sorted[0],
        "q1": q1,
        "median": statistics.median(vals_sorted),
        "q3": q3,
        "max": vals_sorted[-1],
        "iqr": iqr,
        "lower_bound": lower_bound,
        "upper_bound": upper_bound
    }
    
    return outliers, stats

def detect_outliers_zscore(values_with_idx: List[Tuple[int, float]], threshold: float = 3.0) -> List[Dict[str, Any]]:
    """Detects outliers using the standard Z-score method."""
    vals = [x[1] for x in values_with_idx]
    if len(vals) < 3:
        return []
        
    mean = sum(vals) / len(vals)
    std_dev = statistics.stdev(vals) if len(vals) > 1 else 0.0
    
    if std_dev == 0:
        return []
        
    outliers = []
    for idx, val in values_with_idx:
        z = (val - mean) / std_dev
        if abs(z) > threshold:
            direction = "HIGH" if z > 0 else "LOW"
            outliers.append({
                "row": idx,
                "value": val,
                "method": "Z-score",
                "info": f"{direction} (Z-Score: {z:+.2f})"
            })
            
    return outliers

def draw_ascii_boxplot(stats: Dict[str, float], outliers: List[Dict[str, Any]], width: int = 60):
    """Draws a horizontal ASCII box-and-whisker plot for a column's data distribution."""
    # Min/Max values representing the range of the plot, including outliers
    val_min = stats["min"]
    val_max = stats["max"]
    val_span = val_max - val_min
    
    if val_span == 0:
        val_span = 1.0
        
    def get_pos(val: float) -> int:
        """Helper to map data value to horizontal character position (0 to width-1)."""
        pct = (val - val_min) / val_span
        pos = int(pct * (width - 1))
        return min(max(0, pos), width - 1)

    # Position markers
    pos_min = get_pos(stats["min"])
    pos_q1 = get_pos(stats["q1"])
    pos_med = get_pos(stats["median"])
    pos_q3 = get_pos(stats["q3"])
    pos_max = get_pos(stats["max"])
    
    # Non-outlier bounds
    pos_low_b = get_pos(stats["lower_bound"])
    pos_high_b = get_pos(stats["upper_bound"])
    
    # Whiskers should stop at actual data points nearest to the bounds,
    # but for simplicity we draw from bounds or absolute min/max if bounds are wider.
    pos_whisker_l = max(pos_min, pos_low_b)
    pos_whisker_r = min(pos_max, pos_high_b)
    
    # Build plot layers
    # Row 1: labels
    labels_row = [" "] * width
    labels_row[pos_whisker_l] = "|"
    labels_row[pos_q1] = "["
    labels_row[pos_med] = "|"
    labels_row[pos_q3] = "]"
    labels_row[pos_whisker_r] = "|"
    
    # Row 2: Box plot graphic
    plot_row = [" "] * width
    
    # Left whisker line
    for i in range(pos_whisker_l + 1, pos_q1):
        plot_row[i] = "-"
        
    # Right whisker line
    for i in range(pos_q3 + 1, pos_whisker_r):
        plot_row[i] = "-"
        
    # Box contents
    for i in range(pos_q1 + 1, pos_q3):
        plot_row[i] = " "
        
    # Set marker characters
    plot_row[pos_whisker_l] = "|"
    plot_row[pos_q1] = "["
    plot_row[pos_med] = "|"
    plot_row[pos_q3] = "]"
    plot_row[pos_whisker_r] = "|"
    
    # Plot outliers as 'o'
    for o in outliers:
        pos_o = get_pos(o["value"])
        plot_row[pos_o] = "o"

    print("  Box Plot:")
    print("  " + "".join(labels_row))
    print("  " + "".join(plot_row))
    print(f"  {val_min:<12.2f}" + " " * (width - 24) + f"{val_max:>12.2f}")
    print("  (Legend: o = Outlier, | = Whisker/Median, [ ] = Q1/Q3 Box)\n")

def print_column_report(col_name: str, values_with_idx: List[Tuple[int, float]], method: str, z_threshold: float):
    """Audits a single column and prints a comprehensive outlier analysis."""
    print("=" * 70)
    print(f" Column: {col_name.upper()} ({len(values_with_idx)} non-empty entries)")
    print("=" * 70)
    
    outliers_iqr, stats = detect_outliers_iqr(values_with_idx)
    outliers_z = detect_outliers_zscore(values_with_idx, threshold=z_threshold)
    
    if not stats:
        print("[-] Insufficient numeric data points (minimum 4 required for IQR).\n")
        return
        
    print(f"  Summary Statistics:")
    print(f"    - Min:    {stats['min']:.4f}")
    print(f"    - Q1:     {stats['q1']:.4f}")
    print(f"    - Median: {stats['median']:.4f}")
    print(f"    - Q3:     {stats['q3']:.4f}")
    print(f"    - Max:    {stats['max']:.4f}")
    print(f"    - IQR:    {stats['iqr']:.4f}")
    print()
    
    # Draw ASCII plot
    draw_ascii_boxplot(stats, outliers_iqr)
    
    # Select target outliers based on user request method
    selected_outliers = outliers_iqr if method == "iqr" else outliers_z
    
    print(f"  Detected Outliers (Method: {method.upper()}):")
    if selected_outliers:
        print(f"    {'Row Index':<12} | {'Value':<15} | Details")
        print("    " + "-" * 55)
        # Limit print to top 20 outliers to prevent spamming
        for o in selected_outliers[:20]:
            print(f"    {o['row']:<12} | {o['value']:<15.4f} | {o['info']}")
            
        if len(selected_outliers) > 20:
            print(f"    ... and {len(selected_outliers) - 20} more outliers.")
    else:
        print("    No outliers detected under this configuration.")
    print()

def main():
    parser = argparse.ArgumentParser(
        description="Dataset Outlier Scanner. Reads CSV/JSON, finds numerical anomalies, and plots box-plots."
    )
    parser.add_argument("file", help="Path to input CSV or JSON dataset file")
    parser.add_argument(
        "-m", "--method", 
        choices=["iqr", "zscore"], 
        default="iqr", 
        help="Outlier detection method: IQR or Z-score (default: iqr)"
    )
    parser.add_argument(
        "-z", "--z-threshold", 
        type=float, 
        default=3.0, 
        help="Z-score threshold index (default: 3.0)"
    )
    parser.add_argument(
        "-c", "--column", 
        help="Specific column name to analyze (scans all numerical columns if omitted)"
    )
    args = parser.parse_args()

    try:
        rows = load_dataset(args.file)
        if not rows:
            print("[-] Error: Dataset is empty.")
            sys.exit(1)
            
        numerical_cols = identify_numerical_columns(rows)
        if not numerical_cols:
            print("[-] Error: No numerical columns identified in the dataset.")
            sys.exit(1)
            
        # Filter columns
        target_cols = numerical_cols
        if args.column:
            if args.column in numerical_cols:
                target_cols = [args.column]
            else:
                print(f"[-] Error: Column '{args.column}' is not a recognized numerical column.")
                print(f"    Available numerical columns: {', '.join(numerical_cols)}")
                sys.exit(1)
                
        print(f"[*] Loaded dataset: '{args.file}' containing {len(rows)} records.")
        print(f"[*] Found {len(numerical_cols)} numerical columns: {', '.join(numerical_cols)}")
        print(f"[*] Running outlier detection (method: {args.method.upper()})...\n")
        
        for col in target_cols:
            values_with_idx = extract_column_data(rows, col)
            print_column_report(col, values_with_idx, args.method, args.z_threshold)
            
    except Exception as e:
        print(f"[-] Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
