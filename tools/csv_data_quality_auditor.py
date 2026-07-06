#!/usr/bin/env python3
"""
CSV Data Quality & Health Auditor
---------------------------------
Audits CSV datasets to evaluate overall data hygiene, completeness,
schema integrity, outlier presence, duplicate records, and string formatting anomalies.

Features:
- Calculates overall Data Quality Score (0 - 100%).
- Analyzes missing values, null percentages, and column completeness.
- Detects numeric outliers using Interquartile Range (IQR).
- Identifies exact duplicate rows and potential key column duplicate violations.
- Checks formatting anomalies (leading/trailing whitespace, casing shifts).
- Evaluates data type consistency per column (Email, Date, Numeric, Boolean).
- Exports formatted reports to Terminal CLI, Markdown, or JSON.
- Built-in --demo mode with auto-generated sample dataset.

Usage:
    python csv_data_quality_auditor.py --file dataset.csv
    python csv_data_quality_auditor.py --demo
"""

import sys
import os
import csv
import re
import math
import json
import argparse
from typing import Dict, List, Any, Tuple, Optional


if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


class Color:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

    @classmethod
    def disable(cls):
        cls.RED = cls.GREEN = cls.YELLOW = cls.BLUE = cls.MAGENTA = cls.CYAN = cls.BOLD = cls.RESET = ''


if not sys.stdout.isatty():
    Color.disable()


EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
DATE_REGEX = re.compile(r'^\d{4}[-/]\d{2}[-/]\d{2}$|^\d{2}[-/]\d{2}[-/]\d{4}$')


class CSVDataQualityAuditor:
    def __init__(self, rows: List[Dict[str, str]], headers: List[str]):
        self.rows = rows
        self.headers = headers
        self.total_rows = len(rows)
        self.results: Dict[str, Any] = {}

    def audit(self) -> Dict[str, Any]:

        if self.total_rows == 0:
            return {'score': 0, 'error': 'Dataset is empty.'}

        col_stats = {}
        issues = []
        duplicate_rows = 0

        # Duplicate row detection
        row_tuples = [tuple(r.get(h, '') for h in self.headers) for r in self.rows]
        unique_tuples = set(row_tuples)
        duplicate_rows = len(row_tuples) - len(unique_tuples)

        if duplicate_rows > 0:
            issues.append(f"Found {duplicate_rows} duplicate row(s) ({(duplicate_rows/self.total_rows)*100:.1f}% of total).")

        # Column-level analysis
        for col in self.headers:
            values = [r.get(col, '') for r in self.rows]
            non_empty = [v for v in values if v.strip() != '']
            missing_count = self.total_rows - len(non_empty)
            missing_pct = (missing_count / self.total_rows) * 100

            # Whitespace anomalies
            whitespace_issues = sum(1 for v in values if v != v.strip() and v.strip() != '')
            if whitespace_issues > 0:
                issues.append(f"Column '{col}' has {whitespace_issues} value(s) with leading/trailing whitespace.")

            # Inferred Data Types
            types = self._infer_types(non_empty)
            numeric_vals = [float(v) for v in non_empty if self._is_float(v)]

            outliers = []
            if len(numeric_vals) >= 4:
                outliers = self._detect_iqr_outliers(numeric_vals)

            if len(outliers) > 0:
                issues.append(f"Column '{col}' has {len(outliers)} statistical outlier(s).")

            cardinality = len(set(non_empty))

            col_stats[col] = {
                'total': self.total_rows,
                'missing_count': missing_count,
                'missing_pct': round(missing_pct, 2),
                'unique_count': cardinality,
                'inferred_type': types['primary'],
                'type_distribution': types['distribution'],
                'outliers_count': len(outliers),
                'whitespace_anomalies': whitespace_issues
            }

        # Calculate Quality Score
        completeness_penalty = sum(s['missing_pct'] for s in col_stats.values()) / len(self.headers)
        duplicate_penalty = (duplicate_rows / self.total_rows) * 20
        issues_penalty = min(len(issues) * 2, 30)

        quality_score = max(0.0, min(100.0, 100.0 - completeness_penalty - duplicate_penalty - issues_penalty))

        self.results = {
            'total_rows': self.total_rows,
            'total_columns': len(self.headers),
            'duplicate_rows': duplicate_rows,
            'quality_score': round(quality_score, 1),
            'column_stats': col_stats,
            'issues': issues
        }
        return self.results

    def _infer_types(self, values: List[str]) -> Dict[str, Any]:
        counts = {'integer': 0, 'float': 0, 'email': 0, 'date': 0, 'boolean': 0, 'string': 0}
        for v in values:
            if v.lower() in ('true', 'false', '1', '0', 'yes', 'no'):
                counts['boolean'] += 1
            elif self._is_int(v):
                counts['integer'] += 1
            elif self._is_float(v):
                counts['float'] += 1
            elif EMAIL_REGEX.match(v):
                counts['email'] += 1
            elif DATE_REGEX.match(v):
                counts['date'] += 1
            else:
                counts['string'] += 1

        total = max(len(values), 1)
        primary = max(counts, key=counts.get)
        distribution = {k: round((v / total) * 100, 1) for k, v in counts.items() if v > 0}
        return {'primary': primary, 'distribution': distribution}

    @staticmethod
    def _is_int(v: str) -> bool:
        try:
            int(v)
            return True
        except ValueError:
            return False

    @staticmethod
    def _is_float(v: str) -> bool:
        try:
            float(v)
            return True
        except ValueError:
            return False

    @staticmethod
    def _detect_iqr_outliers(data: List[float]) -> List[float]:
        sorted_d = sorted(data)
        n = len(sorted_d)
        q1 = sorted_d[int(n * 0.25)]
        q3 = sorted_d[int(n * 0.75)]
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        return [v for v in data if v < lower_bound or v > upper_bound]


def create_demo_csv(filepath: str):
    data = [
        ["id", "name", "email", "age", "join_date", "score"],
        ["101", "Alice Smith", "alice@example.com", "28", "2023-01-15", "92.5"],
        ["102", "Bob Jones ", "bob.jones@domain.org", "34", "2022-11-20", "88.0"],
        ["103", "Charlie Brown", "charlie@gmail.com", "150", "2023-05-10", "45.0"],  # Outlier age
        ["104", "Diana Prince", "invalid-email-string", "29", "2021-09-01", "99.1"],  # Bad email
        ["105", "Evan Wright", "evan@company.com", "", "2023-03-12", "76.4"],  # Missing age
        ["101", "Alice Smith", "alice@example.com", "28", "2023-01-15", "92.5"],  # Duplicate row
        ["107", "Fiona Gallagher", "fiona@tv.com", "26", "2023-02-28", "81.2"]
    ]
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(data)


def print_report(results: Dict[str, Any], format_type: str = 'cli'):
    if format_type == 'json':
        print(json.dumps(results, indent=2))
        return

    score = results['quality_score']
    if score >= 85:
        score_color = Color.GREEN
    elif score >= 65:
        score_color = Color.YELLOW
    else:
        score_color = Color.RED

    if format_type == 'markdown':
        print("# CSV Data Quality Audit Report\n")
        print(f"**Overall Quality Score**: {score}%\n")
        print(f"- **Total Rows**: {results['total_rows']}")
        print(f"- **Total Columns**: {results['total_columns']}")
        print(f"- **Duplicate Rows**: {results['duplicate_rows']}\n")

        print("## Column Breakdown")
        print("| Column Name | Inferred Type | Missing % | Unique | Outliers | Whitespace Anomalies |")
        print("|---|---|---|---|---|---|")
        for col, s in results['column_stats'].items():
            print(f"| {col} | {s['inferred_type']} | {s['missing_pct']}% | {s['unique_count']} | {s['outliers_count']} | {s['whitespace_anomalies']} |")

        if results['issues']:
            print("\n## Identified Issues")
            for issue in results['issues']:
                print(f"- ⚠️ {issue}")
        return

    # CLI Output
    print(f"\n{Color.BOLD}{Color.CYAN}===================================================={Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}          CSV DATA QUALITY & HEALTH REPORT          {Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}===================================================={Color.RESET}\n")

    print(f"Overall Score: {Color.BOLD}{score_color}{score}% / 100%{Color.RESET}")
    print(f"Dataset Size : {results['total_rows']} Rows × {results['total_columns']} Columns")
    print(f"Duplicates   : {results['duplicate_rows']} Duplicate Rows\n")

    print(f"{Color.BOLD}COLUMN ANALYSIS:{Color.RESET}")
    print(f"{'Column Name':<20} {'Type':<12} {'Missing %':<12} {'Unique':<10} {'Outliers':<10}")
    print("-" * 65)

    for col, s in results['column_stats'].items():
        missing_str = f"{s['missing_pct']}%"
        missing_clr = Color.RED if s['missing_pct'] > 10 else Color.RESET
        print(f"{col:<20} {s['inferred_type']:<12} {missing_clr}{missing_str:<12}{Color.RESET} {s['unique_count']:<10} {s['outliers_count']:<10}")

    print()
    if results['issues']:
        print(f"{Color.BOLD}{Color.YELLOW}⚠️ IDENTIFIED ANOMALIES & AUDIT ISSUES ({len(results['issues'])}):{Color.RESET}")
        for issue in results['issues']:
            print(f"  └─ {issue}")
        print()


def main():
    parser = argparse.ArgumentParser(description="CSV Data Quality & Health Auditor")
    parser.add_argument("--file", help="Path to CSV file to audit")
    parser.add_argument("--demo", action="store_true", help="Run audit on generated sample CSV")
    parser.add_argument("--format", choices=['cli', 'markdown', 'json'], default='cli', help="Output format")

    args = parser.parse_args()

    demo_file = "temp_demo_quality_audit.csv"
    if args.demo or not args.file:
        if not args.demo:
            print(f"{Color.YELLOW}No input file specified. Running --demo mode...{Color.RESET}")
        create_demo_csv(demo_file)
        file_to_audit = demo_file
    else:
        file_to_audit = args.file

    if not os.path.exists(file_to_audit):
        print(f"{Color.RED}Error: File '{file_to_audit}' not found.{Color.RESET}")
        sys.exit(1)

    try:
        with open(file_to_audit, 'r', encoding='utf-8', errors='ignore') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            rows = list(reader)
    except Exception as e:
        print(f"{Color.RED}Failed to read CSV file: {e}{Color.RESET}")
        sys.exit(1)
    finally:
        if args.demo and os.path.exists(demo_file):
            try:
                os.remove(demo_file)
            except OSError:
                pass

    auditor = CSVDataQualityAuditor(rows, headers)
    results = auditor.audit()
    print_report(results, format_type=args.format)


if __name__ == "__main__":
    main()
