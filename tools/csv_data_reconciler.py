#!/usr/bin/env python3
"""
CSV Data Reconciler & Financial Audit Tool

Compares two CSV datasets (source vs target / ledger vs statement) by matching
unique key columns, evaluating numeric tolerances, identifying unmatched records,
and computing field-by-field deltas. Generates executive terminal reports, CSV diffs,
and standalone interactive HTML reconciliation audit reports.

Author: Python Tools Collection
License: MIT
"""

import os
import sys
import csv
import json
import argparse
from pathlib import Path
from typing import List, Dict, Tuple, Set, Any, Optional


def read_csv_dataset(file_path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with open(file_path, "r", encoding="utf-8-sig", errors="ignore") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        rows = [row for row in reader]
    return headers, rows


def make_composite_key(row: Dict[str, str], key_cols: List[str]) -> str:
    return "||".join(str(row.get(col, '')).strip() for col in key_cols)


def reconcile_datasets(
    source_rows: List[Dict[str, str]],
    target_rows: List[Dict[str, str]],
    key_cols: List[str],
    numeric_cols: List[str],
    tolerance: float = 0.001
) -> dict:
    source_map: Dict[str, List[Dict[str, str]]] = {}
    for r in source_rows:
        k = make_composite_key(r, key_cols)
        source_map.setdefault(k, []).append(r)

    target_map: Dict[str, List[Dict[str, str]]] = {}
    for r in target_rows:
        k = make_composite_key(r, key_cols)
        target_map.setdefault(k, []).append(r)

    all_keys = set(source_map.keys()) | set(target_map.keys())

    exact_matches = []
    discrepancies = []
    source_only = []
    target_only = []

    for k in all_keys:
        in_source = k in source_map
        in_target = k in target_map

        if in_source and not in_target:
            for s_row in source_map[k]:
                source_only.append({"key": k, "row": s_row})
        elif in_target and not in_source:
            for t_row in target_map[k]:
                target_only.append({"key": k, "row": t_row})
        else:
            # Both exist - compare fields
            s_row = source_map[k][0]
            t_row = target_map[k][0]

            field_deltas = {}
            has_diff = False

            all_fields = set(s_row.keys()) | set(t_row.keys())
            for f in all_fields:
                val_s = s_row.get(f, "").strip()
                val_t = t_row.get(f, "").strip()

                if f in numeric_cols:
                    try:
                        num_s = float(val_s) if val_s != "" else 0.0
                        num_t = float(val_t) if val_t != "" else 0.0
                        diff = abs(num_s - num_t)
                        if diff > tolerance:
                            has_diff = True
                            field_deltas[f] = {
                                "source": num_s,
                                "target": num_t,
                                "delta": round(num_t - num_s, 4),
                                "abs_diff": round(diff, 4)
                            }
                    except ValueError:
                        if val_s != val_t:
                            has_diff = True
                            field_deltas[f] = {"source": val_s, "target": val_t, "delta": "string_mismatch"}
                else:
                    if val_s != val_t:
                        has_diff = True
                        field_deltas[f] = {"source": val_s, "target": val_t, "delta": "string_mismatch"}

            if has_diff:
                discrepancies.append({
                    "key": k,
                    "source_row": s_row,
                    "target_row": t_row,
                    "deltas": field_deltas
                })
            else:
                exact_matches.append({
                    "key": k,
                    "row": s_row
                })

    return {
        "summary": {
            "total_source_records": len(source_rows),
            "total_target_records": len(target_rows),
            "exact_matches": len(exact_matches),
            "discrepancies": len(discrepancies),
            "source_only": len(source_only),
            "target_only": len(target_only),
            "match_rate_pct": round((len(exact_matches) / max(1, len(source_rows))) * 100.0, 2)
        },
        "exact_matches": exact_matches,
        "discrepancies": discrepancies,
        "source_only": source_only,
        "target_only": target_only
    }


def generate_html_report(reconcile_res: dict, source_name: str, target_name: str) -> str:
    summary = reconcile_res["summary"]
    discrepancies = reconcile_res["discrepancies"]

    discrepancy_rows_html = ""
    for d in discrepancies[:100]:
        deltas_str = ", ".join(f"<b>{f}</b>: S={v['source']} vs T={v['target']} (Δ {v.get('delta', '')})" for f, v in d["deltas"].items())
        discrepancy_rows_html += f"<tr><td><code>{d['key']}</code></td><td>{deltas_str}</td></tr>"

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>CSV Data Reconciliation Audit Report</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; margin: 20px; background: #f8f9fa; color: #212529; }}
        h1 {{ color: #0d6efd; }}
        .cards {{ display: flex; gap: 15px; margin-bottom: 20px; }}
        .card {{ background: white; padding: 15px 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); flex: 1; }}
        .card-val {{ font-size: 24px; font-weight: bold; margin-top: 5px; }}
        .text-success {{ color: #198754; }}
        .text-warning {{ color: #ffc107; }}
        .text-danger {{ color: #dc3545; }}
        table {{ width: 100%; border-collapse: collapse; background: white; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 4px rgba(0,0,0,0.05); }}
        th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #dee2e6; }}
        th {{ background: #f1f3f5; font-weight: 600; }}
        code {{ background: #e9ecef; padding: 2px 6px; border-radius: 4px; font-family: monospace; }}
    </style>
</head>
<body>
    <h1>CSV Data Reconciliation Report</h1>
    <p>Comparing <strong>{source_name}</strong> against <strong>{target_name}</strong></p>

    <div class="cards">
        <div class="card">
            <div>Match Rate</div>
            <div class="card-val text-success">{summary['match_rate_pct']}%</div>
        </div>
        <div class="card">
            <div>Exact Matches</div>
            <div class="card-val">{summary['exact_matches']}</div>
        </div>
        <div class="card">
            <div>Field Discrepancies</div>
            <div class="card-val text-warning">{summary['discrepancies']}</div>
        </div>
        <div class="card">
            <div>Source Only</div>
            <div class="card-val text-danger">{summary['source_only']}</div>
        </div>
        <div class="card">
            <div>Target Only</div>
            <div class="card-val text-danger">{summary['target_only']}</div>
        </div>
    </div>

    <h2>Top Discrepancies</h2>
    <table>
        <thead>
            <tr><th>Matching Key</th><th>Field Deltas & Discrepancies</th></tr>
        </thead>
        <tbody>
            {discrepancy_rows_html if discrepancy_rows_html else '<tr><td colspan="2">No field discrepancies found.</td></tr>'}
        </tbody>
    </table>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(
        description="Reconcile two CSV datasets (source vs target), audit numeric deltas, and find unmatched records."
    )
    parser.add_argument("source_csv", help="Path to source/primary CSV file")
    parser.add_argument("target_csv", help="Path to target/secondary CSV file")
    parser.add_argument("--key", required=True, help="Comma-separated key column name(s) for record matching (e.g. 'id' or 'date,account')")
    parser.add_argument("--numeric-cols", help="Comma-separated column name(s) to evaluate numerically with delta calculation")
    parser.add_argument("--tolerance", type=float, default=0.001, help="Numeric tolerance threshold for float differences (default: 0.001)")
    parser.add_argument("--export-html", help="Save interactive HTML audit report to specified path")
    parser.add_argument("--export-json", help="Save full reconciliation report in JSON format to path")

    args = parser.parse_args()
    source_path = Path(args.source_csv)
    target_path = Path(args.target_csv)

    if not source_path.exists():
        print(f"Error: Source file '{source_path}' does not exist.", file=sys.stderr)
        sys.exit(1)
    if not target_path.exists():
        print(f"Error: Target file '{target_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    key_cols = [k.strip() for k in args.key.split(",") if k.strip()]
    numeric_cols = [n.strip() for n in args.numeric_cols.split(",")] if args.numeric_cols else []

    source_headers, source_rows = read_csv_dataset(source_path)
    target_headers, target_rows = read_csv_dataset(target_path)

    # Validate key columns exist
    missing_keys_s = [k for k in key_cols if k not in source_headers]
    missing_keys_t = [k for k in key_cols if k not in target_headers]
    if missing_keys_s or missing_keys_t:
        print(f"Error: Key column(s) missing. Source missing: {missing_keys_s}, Target missing: {missing_keys_t}", file=sys.stderr)
        sys.exit(1)

    result = reconcile_datasets(source_rows, target_rows, key_cols, numeric_cols, tolerance=args.tolerance)
    summary = result["summary"]

    print("=== CSV Data Reconciliation Executive Summary ===")
    print(f"Source Dataset  : {source_path.name} ({summary['total_source_records']} records)")
    print(f"Target Dataset  : {target_path.name} ({summary['total_target_records']} records)")
    print(f"Key Column(s)   : {', '.join(key_cols)}")
    print(f"Match Rate      : {summary['match_rate_pct']}%")
    print(f"\n--- Audit Breakdown ---")
    print(f"  Exact Matches     : {summary['exact_matches']}")
    print(f"  Field Differences : {summary['discrepancies']}")
    print(f"  Source-Only Keys  : {summary['source_only']}")
    print(f"  Target-Only Keys  : {summary['target_only']}")

    if result["discrepancies"]:
        print(f"\nSample Discrepancies (Top 3):")
        for disc in result["discrepancies"][:3]:
            print(f"  [Key: {disc['key']}]")
            for field, delta in disc["deltas"].items():
                print(f"    - {field}: Source='{delta['source']}' vs Target='{delta['target']}' (Delta: {delta.get('delta')})")

    if args.export_json:
        out_json = Path(args.export_json)
        out_json.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"\nFull JSON audit report saved to '{out_json}'.")

    if args.export_html:
        html_content = generate_html_report(result, source_path.name, target_path.name)
        out_html = Path(args.export_html)
        out_html.write_text(html_content, encoding="utf-8")
        print(f"\nInteractive HTML audit report saved to '{out_html}'.")


if __name__ == "__main__":
    main()
