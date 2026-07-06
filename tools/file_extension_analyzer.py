"""
File Extension Distribution Analyzer
Recursively scans a directory to analyze file extensions (counts, total size, percentage)
and prints a clean visual summary table and horizontal ASCII bar chart.
"""
import argparse
import os
import sys
from collections import defaultdict

def format_size(bytes_size):
    """Format bytes size into a human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"

def scan_directory(directory, ignore_dirs, include_hidden):
    """Scan directory recursively and gather file stats by extension."""
    stats = defaultdict(lambda: {"count": 0, "size": 0})
    total_files = 0
    total_size = 0
    
    ignore_set = set(ignore_dirs)
    
    for root, dirs, files in os.walk(directory):
        # Filter out ignored directories in-place
        dirs[:] = [d for d in dirs if d not in ignore_set and (include_hidden or not d.startswith('.'))]
        
        for file in files:
            if not include_hidden and file.startswith('.'):
                continue
                
            filepath = os.path.join(root, file)
            try:
                # Get file size, resolving symlinks safely
                file_size = os.path.getsize(filepath)
            except (OSError, PermissionError):
                continue  # Skip unreadable files
                
            _, ext = os.path.splitext(file)
            ext = ext.lower().strip()
            
            if not ext:
                ext = "(no extension)"
                
            stats[ext]["count"] += 1
            stats[ext]["size"] += file_size
            total_files += 1
            total_size += file_size
            
    return stats, total_files, total_size

def draw_chart(percentage, width=20):
    """Generate a horizontal ASCII progress bar."""
    filled_len = int(round(width * percentage / 100))
    bar = "█" * filled_len + "░" * (width - filled_len)
    return bar

def main():
    parser = argparse.ArgumentParser(
        description="Recursively analyze the distribution of file extensions in a directory."
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="Target directory to analyze (default: current directory)."
    )
    parser.add_argument(
        "-s", "--sort",
        choices=["size", "count", "ext"],
        default="size",
        help="Sort results by 'size', 'count', or 'ext' (default: size)."
    )
    parser.add_argument(
        "-l", "--limit",
        type=int,
        default=15,
        help="Limit table to top N extensions (default: 15)."
    )
    parser.add_argument(
        "--ignore",
        default=".git,node_modules,__pycache__,.venv,venv,env,.idea,.vscode",
        help="Comma-separated list of directory names to ignore."
    )
    parser.add_argument(
        "--hidden",
        action="store_true",
        help="Include hidden files and directories (starting with a dot)."
    )
    
    args = parser.parse_args()
    
    target_dir = os.path.abspath(args.directory)
    if not os.path.isdir(target_dir):
        print(f"[ERROR] Directory not found: {target_dir}")
        sys.exit(1)
        
    ignore_dirs = [d.strip() for d in args.ignore.split(",") if d.strip()]
    
    print(f"Scanning directory: {target_dir}")
    print(f"Ignoring directories: {', '.join(ignore_dirs)}")
    print("-" * 80)
    
    stats, total_files, total_size = scan_directory(target_dir, ignore_dirs, args.hidden)
    
    if total_files == 0:
        print("[OK] No files found matching criteria.")
        sys.exit(0)
        
    # Prepare list for sorting
    data_list = []
    for ext, val in stats.items():
        data_list.append({
            "ext": ext,
            "count": val["count"],
            "size": val["size"],
            "pct_count": (val["count"] / total_files) * 100,
            "pct_size": (val["size"] / total_size) * 100 if total_size > 0 else 0
        })
        
    # Sort
    if args.sort == "size":
        data_list.sort(key=lambda x: x["size"], reverse=True)
    elif args.sort == "count":
        data_list.sort(key=lambda x: x["count"], reverse=True)
    else:
        data_list.sort(key=lambda x: x["ext"])
        
    # Format and print results
    print(f"Total Files Analyzed: {total_files}")
    print(f"Total Directory Size: {format_size(total_size)}")
    print("-" * 80)
    
    header_fmt = "{:<18} | {:>7} | {:>7}% | {:>12} | {:>7}% | {:<20}"
    row_fmt = "{:<18} | {:>7,d} | {:>7.2f}% | {:>12} | {:>7.2f}% | {:<20}"
    
    print(header_fmt.format("Extension", "Count", "Count%", "Total Size", "Size%", "Size Distribution"))
    print("=" * 80)
    
    displayed_size_pct = 0
    displayed_count_pct = 0
    
    for i, item in enumerate(data_list[:args.limit]):
        bar = draw_chart(item["pct_size"])
        print(row_fmt.format(
            item["ext"][:18],
            item["count"],
            item["pct_count"],
            format_size(item["size"]),
            item["pct_size"],
            bar
        ))
        displayed_size_pct += item["pct_size"]
        displayed_count_pct += item["pct_count"]
        
    # If truncated, print remaining
    if len(data_list) > args.limit:
        remaining = data_list[args.limit:]
        rem_count = sum(x["count"] for x in remaining)
        rem_size = sum(x["size"] for x in remaining)
        rem_pct_cnt = sum(x["pct_count"] for x in remaining)
        rem_pct_sz = sum(x["pct_size"] for x in remaining)
        
        bar = draw_chart(rem_pct_sz)
        print("-" * 80)
        print(row_fmt.format(
            f"({len(remaining)} other)",
            rem_count,
            rem_pct_cnt,
            format_size(rem_size),
            rem_pct_sz,
            bar
        ))
        
    print("-" * 80)
    sys.exit(0)

if __name__ == "__main__":
    main()
