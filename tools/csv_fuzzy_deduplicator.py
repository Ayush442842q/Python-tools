#!/usr/bin/env python3
"""
csv_fuzzy_deduplicator - CSV Fuzzy Record Deduplicator

Finds, groups, and merges near-duplicate records in CSV datasets using customizable
string similarity algorithms (Levenshtein distance, SequenceMatcher, or Jaccard index)
across specified columns.

Usage:
    python tools/csv_fuzzy_deduplicator.py <input_csv> [options]

Examples:
    python tools/csv_fuzzy_deduplicator.py data.csv --columns name,address --threshold 0.85
    python tools/csv_fuzzy_deduplicator.py data.csv --method jaccard --output deduplicated.csv
    python tools/csv_fuzzy_deduplicator.py --generate-sample sample_contacts.csv
"""

import argparse
import csv
import difflib
import math
import os
import sys
from typing import List, Dict, Tuple, Set, Any


def levenshtein_similarity(s1: str, s2: str) -> float:
    """Calculate normalized Levenshtein similarity between two strings (0.0 to 1.0)."""
    s1, s2 = s1.lower().strip(), s2.lower().strip()
    if s1 == s2:
        return 1.0
    len1, len2 = len(s1), len(s2)
    if len1 == 0 or len2 == 0:
        return 0.0

    # Dynamic programming for Levenshtein distance
    dp = [[0] * (len2 + 1) for _ in range(len1 + 1)]
    for i in range(len1 + 1):
        dp[i][0] = i
    for j in range(len2 + 1):
        dp[0][j] = j

    for i in range(1, len1 + 1):
        for j in range(1, len2 + 1):
            cost = 0 if s1[i - 1] == s2[j - 1] else 1
            dp[i][j] = min(
                dp[i - 1][j] + 1,      # deletion
                dp[i][j - 1] + 1,      # insertion
                dp[i - 1][j - 1] + cost # substitution
            )

    distance = dp[len1][len2]
    max_len = max(len1, len2)
    return 1.0 - (distance / max_len)


def sequence_similarity(s1: str, s2: str) -> float:
    """Calculate SequenceMatcher similarity between two strings (0.0 to 1.0)."""
    s1, s2 = s1.lower().strip(), s2.lower().strip()
    if s1 == s2:
        return 1.0
    return difflib.SequenceMatcher(None, s1, s2).ratio()


def jaccard_similarity(s1: str, s2: str) -> float:
    """Calculate word-based Jaccard similarity index between two strings (0.0 to 1.0)."""
    words1 = set(s1.lower().strip().split())
    words2 = set(s2.lower().strip().split())
    if not words1 and not words2:
        return 1.0
    if not words1 or not words2:
        return 0.0
    intersection = words1.intersection(words2)
    union = words1.union(words2)
    return len(intersection) / len(union)


SIMILARITY_METHODS = {
    'levenshtein': levenshtein_similarity,
    'sequence': sequence_similarity,
    'jaccard': jaccard_similarity
}


def compute_row_similarity(row1: Dict[str, str], row2: Dict[str, str], columns: List[str], method: str) -> float:
    """Compute weighted average similarity across target columns between two CSV rows."""
    sim_func = SIMILARITY_METHODS.get(method.lower(), sequence_similarity)
    scores = []
    for col in columns:
        val1 = row1.get(col, '')
        val2 = row2.get(col, '')
        scores.append(sim_func(str(val1), str(val2)))
    return sum(scores) / len(scores) if scores else 0.0


def find_duplicate_clusters(rows: List[Dict[str, str]], columns: List[str], threshold: float, method: str) -> List[List[int]]:
    """Group row indices into duplicate clusters using connected components graph logic."""
    n = len(rows)
    parent = list(range(n))

    def find(i: int) -> int:
        if parent[i] == i:
            return i
        parent[i] = find(parent[i])
        return parent[i]

    def union(i: int, j: int):
        root_i = find(i)
        root_j = find(j)
        if root_i != root_j:
            parent[root_i] = root_j

    # Pairwise comparison across rows
    for i in range(n):
        for j in range(i + 1, n):
            sim = compute_row_similarity(rows[i], rows[j], columns, method)
            if sim >= threshold:
                union(i, j)

    # Collect clusters
    clusters_dict: Dict[int, List[int]] = {}
    for i in range(n):
        root = find(i)
        clusters_dict.setdefault(root, []).append(i)

    return list(clusters_dict.values())


def merge_cluster_rows(rows: List[Dict[str, str]], strategy: str = 'longest') -> Dict[str, str]:
    """Merge a list of duplicate rows into a single row based on selection strategy."""
    if not rows:
        return {}
    if strategy == 'first':
        return rows[0]
    if strategy == 'last':
        return rows[-1]

    # 'longest' strategy: choose non-empty or longest value for each field
    fieldnames = list(rows[0].keys())
    merged = {}
    for field in fieldnames:
        best_val = ""
        for r in rows:
            val = str(r.get(field, "")).strip()
            if len(val) > len(best_val):
                best_val = val
        merged[field] = best_val
    return merged


def generate_sample_csv(filename: str):
    """Generate a sample CSV file containing near-duplicate records for testing."""
    sample_data = [
        ["name", "email", "company", "city"],
        ["Johnathan Doe", "john.doe@acme.com", "Acme Corporation", "New York"],
        ["Jonathon Doe", "john.d@acme.com", "Acme Corp.", "New York City"],
        ["Alice Smith", "alice@techcorp.io", "TechCorp Ltd", "San Francisco"],
        ["Alice Smith", "asmith@techcorp.io", "TechCorp Inc.", "San Francisco"],
        ["Bob Johnson", "bob.j@global.org", "Global Systems", "Chicago"],
        ["Robert Johnson", "bob.johnson@global.org", "Global Systems Inc", "Chicago"],
        ["Charlie Brown", "charlie@peanuts.com", "Comic World", "Minneapolis"],
    ]
    with open(filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(sample_data)
    print(f"[+] Sample CSV created at: {filename}")


def main():
    parser = argparse.ArgumentParser(
        description="Find and merge near-duplicate records in CSV files using fuzzy matching algorithms."
    )
    parser.add_argument("input_csv", nargs="?", help="Path to input CSV file")
    parser.add_argument("-o", "--output", help="Path to output deduplicated CSV file")
    parser.add_argument("-c", "--columns", help="Comma-separated list of column names to compare (default: all columns)")
    parser.add_argument("-t", "--threshold", type=float, default=0.80, help="Similarity threshold between 0.0 and 1.0 (default: 0.80)")
    parser.add_argument("-m", "--method", choices=['levenshtein', 'sequence', 'jaccard'], default='sequence', help="Similarity metric method (default: sequence)")
    parser.add_argument("-s", "--strategy", choices=['first', 'last', 'longest'], default='longest', help="Deduplication merge strategy (default: longest)")
    parser.add_argument("--report", help="Save detailed duplicate cluster report to a CSV file")
    parser.add_argument("--generate-sample", help="Generate a sample CSV file for testing")

    args = parser.parse_args()

    if args.generate_sample:
        sample_path = args.generate_sample if isinstance(args.generate_sample, str) else "sample_contacts.csv"
        generate_sample_csv(sample_path)
        if not args.input_csv:
            sys.exit(0)

    if not args.input_csv:
        parser.print_help()
        sys.exit(1)

    if not os.path.exists(args.input_csv):
        print(f"Error: Input file '{args.input_csv}' does not exist.", file=sys.stderr)
        sys.exit(1)

    with open(args.input_csv, 'r', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        if not fieldnames:
            print("Error: Empty or invalid CSV file.", file=sys.stderr)
            sys.exit(1)
        rows = list(reader)

    if not rows:
        print("CSV contains no data rows.")
        sys.exit(0)

    target_columns = [col.strip() for col in args.columns.split(',')] if args.columns else list(fieldnames)
    invalid_cols = [col for col in target_columns if col not in fieldnames]
    if invalid_cols:
        print(f"Error: Columns {invalid_cols} not found in CSV header.", file=sys.stderr)
        sys.exit(1)

    print(f"[*] Scanning {len(rows)} rows across columns: {', '.join(target_columns)}")
    print(f"[*] Similarity metric: {args.method} (Threshold: {args.threshold})")

    clusters = find_duplicate_clusters(rows, target_columns, args.threshold, args.method)
    duplicate_clusters = [c for c in clusters if len(c) > 1]

    print("\n" + "=" * 60)
    print(f"SUMMARY: Found {len(duplicate_clusters)} near-duplicate cluster(s) among {len(rows)} records.")
    print("=" * 60)

    report_rows = []
    deduplicated_rows = []

    for cluster_id, cluster in enumerate(clusters, 1):
        cluster_records = [rows[idx] for idx in cluster]
        merged = merge_cluster_rows(cluster_records, args.strategy)
        deduplicated_rows.append(merged)

        if len(cluster) > 1:
            print(f"\n--- Cluster #{cluster_id} ({len(cluster)} records) ---")
            for idx in cluster:
                row_str = " | ".join(f"{col}: {rows[idx].get(col, '')}" for col in target_columns)
                print(f"  [Row {idx + 2}] {row_str}")
                report_row = dict(rows[idx])
                report_row['cluster_id'] = cluster_id
                report_rows.append(report_row)

    if args.report:
        report_fields = ['cluster_id'] + list(fieldnames)
        with open(args.report, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=report_fields)
            writer.writeheader()
            writer.writerows(report_rows)
        print(f"\n[+] Duplicate report saved to: {args.report}")

    if args.output:
        with open(args.output, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(deduplicated_rows)
        print(f"[+] Deduplicated dataset ({len(deduplicated_rows)} rows) saved to: {args.output}")


if __name__ == "__main__":
    main()
