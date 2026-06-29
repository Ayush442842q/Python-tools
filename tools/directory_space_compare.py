#!/usr/bin/env python3
"""
Directory Disk Space Compare Tool
Recursively scans two directories and compares their sizes and file counts side-by-side.
Identifies added, deleted, and modified files, aggregates differences at the directory
level, and prints a formatted console table of space differences.
"""

import sys
import os
import argparse
from collections import defaultdict

# ANSI Colors
COLOR_RESET = "\033[0m"
COLOR_GREEN = "\033[32m"
COLOR_RED = "\033[31m"
COLOR_CYAN = "\033[36m"
COLOR_YELLOW = "\033[33m"
COLOR_BOLD = "\033[1m"

def format_size(size_bytes):
    """Formats bytes to a human-readable string."""
    sign = "+" if size_bytes > 0 else "-" if size_bytes < 0 else ""
    size = abs(size_bytes)
    if size == 0:
        return "0 B"
    
    suffixes = ['B', 'KB', 'MB', 'GB', 'TB']
    i = 0
    while size >= 1024 and i < len(suffixes) - 1:
        size /= 1024.0
        i += 1
    val = f"{size:.2f}".rstrip('0').rstrip('.')
    return f"{sign}{val} {suffixes[i]}"

def get_dir_inventory(root_path):
    """Scans a directory recursively and returns a map of relative_path -> size_bytes for all files."""
    inventory = {}
    root_path = os.path.abspath(root_path)
    
    for root, _, files in os.walk(root_path):
        for file in files:
            full_path = os.path.join(root, file)
            try:
                # Use os.path.getsize, handle symlinks/permission issues gracefully
                size = os.path.getsize(full_path)
                rel_path = os.path.relpath(full_path, root_path)
                # Normalize separators to forward slashes for cross-platform matching
                rel_path = rel_path.replace(os.sep, '/')
                inventory[rel_path] = size
            except (OSError, PermissionError):
                continue
    return inventory

def rollup_folder_sizes(file_inventory):
    """Rolls up file sizes into their containing folders."""
    folder_sizes = defaultdict(int)
    for rel_path, size in file_inventory.items():
        parts = rel_path.split('/')
        # Add to all ancestor directories
        for i in range(len(parts)):
            ancestor = '/'.join(parts[:i])
            if not ancestor:
                ancestor = "."
            folder_sizes[ancestor] += size
    return dict(folder_sizes)

def compare_inventories(inv_a, inv_b, threshold_bytes=0):
    """Compares two file inventories and returns added, deleted, modified, and folder differences."""
    all_rel_paths = set(inv_a.keys()) | set(inv_b.keys())
    
    file_diffs = []
    summary = {
        "added_count": 0, "added_size": 0,
        "deleted_count": 0, "deleted_size": 0,
        "modified_count": 0, "modified_diff": 0,
        "unchanged_count": 0,
        "total_size_a": sum(inv_a.values()),
        "total_size_b": sum(inv_b.values())
    }
    
    for path in all_rel_paths:
        size_a = inv_a.get(path)
        size_b = inv_b.get(path)
        
        if size_a is None:
            # Added in B
            diff = size_b
            pct = 100.0
            status = "ADDED"
            summary["added_count"] += 1
            summary["added_size"] += size_b
        elif size_b is None:
            # Deleted in B
            diff = -size_a
            pct = -100.0
            status = "DELETED"
            summary["deleted_count"] += 1
            summary["deleted_size"] += size_a
        else:
            diff = size_b - size_a
            if diff == 0:
                summary["unchanged_count"] += 1
                continue
            pct = (diff / size_a) * 100.0 if size_a > 0 else 100.0
            status = "MODIFIED"
            summary["modified_count"] += 1
            summary["modified_diff"] += diff
            
        if abs(diff) >= threshold_bytes:
            file_diffs.append({
                "path": path,
                "type": "file",
                "size_a": size_a if size_a is not None else 0,
                "size_b": size_b if size_b is not None else 0,
                "diff": diff,
                "pct": pct,
                "status": status
            })
            
    # Roll up folder level diffs
    folders_a = rollup_folder_sizes(inv_a)
    folders_b = rollup_folder_sizes(inv_b)
    all_folders = set(folders_a.keys()) | set(folders_b.keys())
    
    folder_diffs = []
    for folder in all_folders:
        if folder == ".":
            continue
        size_a = folders_a.get(folder, 0)
        size_b = folders_b.get(folder, 0)
        diff = size_b - size_a
        
        if diff == 0:
            continue
            
        pct = (diff / size_a) * 100.0 if size_a > 0 else 100.0
        status = "MODIFIED"
        if size_a == 0:
            status = "ADDED"
        elif size_b == 0:
            status = "DELETED"
            
        if abs(diff) >= threshold_bytes:
            folder_diffs.append({
                "path": folder + "/",
                "type": "dir",
                "size_a": size_a,
                "size_b": size_b,
                "diff": diff,
                "pct": pct,
                "status": status
            })
            
    return file_diffs, folder_diffs, summary

def print_comparison_table(diffs, sort_key="diff", reverse=True):
    """Renders a beautiful ASCII comparison table."""
    # Sort the diffs
    if sort_key == "pct":
        diffs = sorted(diffs, key=lambda x: x["pct"], reverse=reverse)
    elif sort_key == "path":
        diffs = sorted(diffs, key=lambda x: x["path"], reverse=reverse)
    else: # default is absolute change size
        diffs = sorted(diffs, key=lambda x: abs(x["diff"]), reverse=reverse)
        
    print(f"\n{COLOR_BOLD}{COLOR_CYAN}=== SIZE DIFFERENCES BY ITEM ==={COLOR_RESET}")
    header = f"{'Item Path':<50} | {'Type':<4} | {'Size A':<12} | {'Size B':<12} | {'Change':<12} | {'% Change':<9} | {'Status':<8}"
    print(header)
    print("-" * len(header))
    
    for item in diffs:
        path = item["path"]
        # Truncate very long paths to keep columns aligned
        if len(path) > 48:
            path = "..." + path[-45:]
            
        type_str = "DIR" if item["type"] == "dir" else "FILE"
        size_a_str = format_size(item["size_a"]).replace("+", "").replace("-", "") if item["size_a"] > 0 else "0 B"
        size_b_str = format_size(item["size_b"]).replace("+", "").replace("-", "") if item["size_b"] > 0 else "0 B"
        
        diff_val = item["diff"]
        diff_str = format_size(diff_val)
        if diff_val > 0:
            diff_str = COLOR_GREEN + diff_str + COLOR_RESET
        elif diff_val < 0:
            diff_str = COLOR_RED + diff_str + COLOR_RESET
            
        pct_val = item["pct"]
        pct_sign = "+" if pct_val > 0 else ""
        pct_str = f"{pct_sign}{pct_val:.1f}%"
        if pct_val > 0:
            pct_str = COLOR_GREEN + pct_str + COLOR_RESET
        elif pct_val < 0:
            pct_str = COLOR_RED + pct_str + COLOR_RESET
            
        status = item["status"]
        if status == "ADDED":
            status_str = COLOR_GREEN + status + COLOR_RESET
        elif status == "DELETED":
            status_str = COLOR_RED + status + COLOR_RESET
        else:
            status_str = COLOR_YELLOW + status + COLOR_RESET
            
        print(f"{path:<50} | {type_str:<4} | {size_a_str:>12} | {size_b_str:>12} | {diff_str:>21} | {pct_str:>18} | {status_str:<8}")

def main():
    parser = argparse.ArgumentParser(description="Directory Disk Space Side-by-Side Comparison Tool")
    parser.add_argument("dir_a", help="Reference directory (A)")
    parser.add_argument("dir_b", help="Comparison directory (B)")
    parser.add_argument("-t", "--threshold", type=str, default="0",
                        help="Filter out changes smaller than threshold (e.g. '10KB', '1MB', or bytes)")
    parser.add_argument("-s", "--sort", choices=["diff", "path", "pct"], default="diff",
                        help="Sort comparison output by: diff (absolute size change), path (alphabetical), pct (percentage change)")
    parser.add_argument("-f", "--files-only", action="store_true", help="Only show file differences (hide directory rollups)")
    
    args = parser.parse_args()
    
    # Parse threshold
    threshold_bytes = 0
    t_str = args.threshold.upper()
    try:
        if t_str.endswith("KB"):
            threshold_bytes = int(float(t_str[:-2]) * 1024)
        elif t_str.endswith("MB"):
            threshold_bytes = int(float(t_str[:-2]) * 1024 * 1024)
        elif t_str.endswith("GB"):
            threshold_bytes = int(float(t_str[:-2]) * 1024 * 1024 * 1024)
        else:
            threshold_bytes = int(t_str)
    except ValueError:
        print(f"Error: Invalid threshold format: '{args.threshold}'. Use e.g. 100, 10KB, 1.5MB")
        sys.exit(1)
        
    if not (os.path.isdir(args.dir_a) and os.path.isdir(args.dir_b)):
        print("Error: Both arguments must be valid directories.")
        sys.exit(1)
        
    print(f"Scanning Dir A: {args.dir_a}...")
    inv_a = get_dir_inventory(args.dir_a)
    print(f"Scanning Dir B: {args.dir_b}...")
    inv_b = get_dir_inventory(args.dir_b)
    
    file_diffs, folder_diffs, summary = compare_inventories(inv_a, inv_b, threshold_bytes)
    
    # Display comparison table
    display_items = file_diffs
    if not args.files_only:
        display_items = file_diffs + folder_diffs
        
    if display_items:
        print_comparison_table(display_items, sort_key=args.sort)
    else:
        print("\nNo size differences found exceeding threshold.")
        
    # Summary Dashboard
    print(f"\n{COLOR_BOLD}{COLOR_CYAN}=== COMPARISON SUMMARY ==={COLOR_RESET}")
    print(f"Total Size A: {format_size(summary['total_size_a']).replace('+', '')}")
    print(f"Total Size B: {format_size(summary['total_size_b']).replace('+', '')}")
    
    net_diff = summary['total_size_b'] - summary['total_size_a']
    net_pct = (net_diff / summary['total_size_a']) * 100.0 if summary['total_size_a'] > 0 else 0.0
    net_color = COLOR_GREEN if net_diff > 0 else COLOR_RED if net_diff < 0 else ""
    net_sign = "+" if net_diff > 0 else ""
    print(f"Net Change  : {net_color}{net_sign}{format_size(net_diff)} ({net_sign}{net_pct:.2f}%){COLOR_RESET}")
    print("-" * 30)
    print(f"Files Added     : {COLOR_GREEN}{summary['added_count']}{COLOR_RESET} ({format_size(summary['added_size']).replace('+', '')})")
    print(f"Files Deleted   : {COLOR_RED}{summary['deleted_count']}{COLOR_RESET} ({format_size(summary['deleted_size']).replace('+', '')})")
    print(f"Files Modified  : {COLOR_YELLOW}{summary['modified_count']}{COLOR_RESET} ({format_size(summary['modified_diff'])})")
    print(f"Files Unchanged : {summary['unchanged_count']}")

if __name__ == "__main__":
    main()
