#!/usr/bin/env python3
"""
CSV Dataset Drift & Schema Auditor
Author: Antigravity

Analyzes structural changes and statistical data drift between a reference
CSV dataset and a target CSV dataset. Helps detect schema mismatch, missing
values, summary statistic drift, and categorical frequency shifts.
"""

import argparse
import csv
import math
import sys
from collections import Counter
from typing import Dict, List, Tuple, Any, Optional

def load_csv(filepath: str, max_rows: Optional[int] = None) -> Tuple[List[str], List[Dict[str, str]]]:
    """Loads a CSV file and returns the headers and rows as dictionaries."""
    rows = []
    try:
        with open(filepath, mode='r', encoding='utf-8-sig', errors='replace') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            for i, row in enumerate(reader):
                if max_rows is not None and i >= max_rows:
                    break
                rows.append(row)
            return headers, rows
    except FileNotFoundError:
        print(f"Error: File not found at '{filepath}'", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading '{filepath}': {e}", file=sys.stderr)
        sys.exit(1)

def infer_type(val: str) -> str:
    """Infers the data type of a cell value."""
    if not val or val.strip() == "":
        return "null"
    val_strip = val.strip()
    # Try integer
    try:
        int(val_strip)
        return "int"
    except ValueError:
        pass
    # Try float
    try:
        float(val_strip)
        return "float"
    except ValueError:
        pass
    # Try boolean
    if val_strip.lower() in ('true', 'false', 'yes', 'no', 't', 'f', '1', '0'):
        return "bool"
    return "string"

def analyze_columns(headers: List[str], rows: List[Dict[str, str]]) -> Dict[str, Dict[str, Any]]:
    """Analyzes each column in the dataset to collect type information and null rates."""
    analysis = {}
    total_rows = len(rows)
    
    for col in headers:
        types = Counter()
        null_count = 0
        numeric_vals = []
        categorical_vals = []
        
        for r in rows:
            val = r.get(col)
            if val is None or val.strip() == "":
                null_count += 1
                types["null"] += 1
            else:
                t = infer_type(val)
                types[t] += 1
                if t in ("int", "float"):
                    try:
                        numeric_vals.append(float(val.strip()))
                    except ValueError:
                        categorical_vals.append(val.strip())
                else:
                    categorical_vals.append(val.strip())
                    
        # Primary type is the most common non-null type, defaults to string
        non_null_types = {t: c for t, c in types.items() if t != "null"}
        primary_type = max(non_null_types, key=non_null_types.get) if non_null_types else "string"
        
        null_ratio = null_count / total_rows if total_rows > 0 else 0.0
        
        analysis[col] = {
            "type": primary_type,
            "null_count": null_count,
            "null_ratio": null_ratio,
            "numeric_values": numeric_vals,
            "categorical_values": categorical_vals,
            "type_counts": dict(types)
        }
    return analysis

def calculate_numeric_stats(vals: List[float]) -> Dict[str, float]:
    """Calculates summary statistics for numerical values."""
    if not vals:
        return {}
    
    sorted_vals = sorted(vals)
    n = len(sorted_vals)
    
    mean = sum(sorted_vals) / n
    variance = sum((x - mean) ** 2 for x in sorted_vals) / n
    stddev = math.sqrt(variance)
    minimum = sorted_vals[0]
    maximum = sorted_vals[-1]
    
    def percentile(p):
        idx = (n - 1) * p
        low = math.floor(idx)
        high = math.ceil(idx)
        if low == high:
            return sorted_vals[int(idx)]
        return sorted_vals[low] * (high - idx) + sorted_vals[high] * (idx - low)
        
    return {
        "count": float(n),
        "mean": mean,
        "stddev": stddev,
        "min": minimum,
        "max": maximum,
        "p25": percentile(0.25),
        "p50": percentile(0.50),
        "p75": percentile(0.75)
    }

def print_header(title: str):
    """Prints a styled header."""
    print("\n" + "=" * 80)
    print(f" {title} ".center(80, "="))
    print("=" * 80)

def print_section(title: str):
    """Prints a styled section header."""
    print(f"\n--- {title} " + "-" * (75 - len(title)))

def format_diff(ref_val: float, tgt_val: float, is_ratio: bool = False) -> str:
    """Formats difference between reference and target values."""
    diff = tgt_val - ref_val
    if is_ratio:
        pct = diff * 100
        return f"{tgt_val*100:6.2f}% ({pct:+5.2f}%)"
    else:
        if ref_val != 0:
            pct_change = (diff / ref_val) * 100
            return f"{tgt_val:10.4g} ({diff:+10.4g} / {pct_change:+.1f}%)"
        else:
            return f"{tgt_val:10.4g} ({diff:+10.4g})"

def main():
    parser = argparse.ArgumentParser(
        description="CSV Dataset Drift & Schema Auditor - Compare schemas and data distributions of two CSVs."
    )
    parser.add_argument("-r", "--reference", required=True, help="Path to reference (baseline) CSV file")
    parser.add_argument("-t", "--target", required=True, help="Path to target (comparison) CSV file")
    parser.add_argument("--max-rows", type=int, default=None, help="Limit number of rows read from each file")
    parser.add_argument("--top-n", type=int, default=5, help="Number of top categories to show in categorical drift")
    
    args = parser.parse_args()
    
    print(f"Loading reference dataset: {args.reference}...")
    ref_headers, ref_rows = load_csv(args.reference, args.max_rows)
    print(f"Loading target dataset: {args.target}...")
    tgt_headers, tgt_rows = load_csv(args.target, args.max_rows)
    
    print(f"Reference: {len(ref_rows)} rows, {len(ref_headers)} columns")
    print(f"Target:    {len(tgt_rows)} rows, {len(tgt_headers)} columns")
    
    ref_analysis = analyze_columns(ref_headers, ref_rows)
    tgt_analysis = analyze_columns(tgt_headers, tgt_rows)
    
    # 1. Schema Auditor
    print_header("SCHEMA AUDIT")
    
    added_cols = [c for c in tgt_headers if c not in ref_headers]
    removed_cols = [c for c in ref_headers if c not in tgt_headers]
    common_cols = [c for c in ref_headers if c in tgt_headers]
    
    if added_cols:
        print(f"Added columns ({len(added_cols)}): {', '.join(added_cols)}")
    else:
        print("No added columns.")
        
    if removed_cols:
        print(f"Removed columns ({len(removed_cols)}): {', '.join(removed_cols)}")
    else:
        print("No removed columns.")
        
    type_changes = []
    for col in common_cols:
        ref_type = ref_analysis[col]["type"]
        tgt_type = tgt_analysis[col]["type"]
        if ref_type != tgt_type:
            type_changes.append((col, ref_type, tgt_type))
            
    if type_changes:
        print("\nColumn Data Type Changes:")
        print(f"  {'Column Name':<30} | {'Reference Type':<15} | {'Target Type':<15}")
        print("  " + "-" * 66)
        for col, r_t, t_t in type_changes:
            print(f"  {col:<30} | {r_t:<15} | {t_t:<15}")
    else:
        print("No column data type changes detected.")
        
    # 2. Missing Value & Null Rate Auditor
    print_header("MISSING VALUES & NULL RATES SHIFT")
    print(f"  {'Column Name':<30} | {'Ref Null %':<12} | {'Tgt Null % (Shift)':<25}")
    print("  " + "-" * 75)
    for col in common_cols:
        ref_null = ref_analysis[col]["null_ratio"]
        tgt_null = tgt_analysis[col]["null_ratio"]
        null_diff = tgt_null - ref_null
        
        # Flag significant shifts (>= 5%)
        flag = " *" if abs(null_diff) >= 0.05 else ""
        print(f"  {col:<30} | {ref_null*100:10.2f}% | {tgt_null*100:10.2f}% ({null_diff*100:+.2f}%){flag}")
    print("  (* Indicates a shift >= 5.0%)")

    # 3. Numerical Summary Statistics Drift
    numeric_cols = [col for col in common_cols if ref_analysis[col]["type"] in ("int", "float") and tgt_analysis[col]["type"] in ("int", "float")]
    if numeric_cols:
        print_header("NUMERICAL STATISTICAL DRIFT")
        for col in numeric_cols:
            ref_nums = ref_analysis[col]["numeric_values"]
            tgt_nums = tgt_analysis[col]["numeric_values"]
            
            if not ref_nums or not tgt_nums:
                continue
                
            ref_stats = calculate_numeric_stats(ref_nums)
            tgt_stats = calculate_numeric_stats(tgt_nums)
            
            print_section(f"Column: {col} (Reference Type: {ref_analysis[col]['type']})")
            print(f"  {'Statistic':<12} | {'Reference':<15} | {'Target (Diff / %% Change)':<35}")
            print("  " + "-" * 68)
            for stat in ["count", "mean", "stddev", "min", "p25", "p50", "p75", "max"]:
                rv = ref_stats.get(stat, 0.0)
                tv = tgt_stats.get(stat, 0.0)
                print(f"  {stat.upper():<12} | {rv:15.4g} | {format_diff(rv, tv)}")
    else:
        print("\nNo numeric columns common to both datasets for statistical comparison.")

    # 4. Categorical / String Frequency Drift
    categorical_cols = [col for col in common_cols if col not in numeric_cols]
    if categorical_cols:
        print_header("CATEGORICAL FREQUENCY DRIFT (TOP VALUES)")
        for col in categorical_cols:
            ref_cats = ref_analysis[col]["categorical_values"]
            tgt_cats = tgt_analysis[col]["categorical_values"]
            
            if not ref_cats and not tgt_cats:
                continue
                
            ref_count = Counter(ref_cats)
            tgt_count = Counter(tgt_cats)
            
            ref_total = len(ref_cats)
            tgt_total = len(tgt_cats)
            
            # Combine unique keys from top of both
            top_ref_keys = [k for k, _ in ref_count.most_common(args.top_n)]
            top_tgt_keys = [k for k, _ in tgt_count.most_common(args.top_n)]
            combined_keys = list(dict.fromkeys(top_ref_keys + top_tgt_keys))
            
            print_section(f"Column: {col}")
            print(f"  {'Category':<25} | {'Ref Freq (%%)':<18} | {'Tgt Freq (%%) [Shift]':<25}")
            print("  " + "-" * 74)
            for key in combined_keys[:args.top_n * 2]:
                rc = ref_count.get(key, 0)
                tc = tgt_count.get(key, 0)
                
                rf = rc / ref_total if ref_total > 0 else 0.0
                tf = tc / tgt_total if tgt_total > 0 else 0.0
                shift = tf - rf
                
                key_str = str(key)
                if len(key_str) > 23:
                    key_str = key_str[:20] + "..."
                print(f"  {key_str:<25} | {rc:6d} ({rf*100:5.1f}%) | {tc:6d} ({tf*100:5.1f}%) [{shift*100:+.1f}%]")
    else:
        print("\nNo categorical/string columns common to both datasets for distribution comparison.")

    print("\nAudit completed.")

if __name__ == "__main__":
    main()
