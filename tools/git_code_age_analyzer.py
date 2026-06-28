#!/usr/bin/env python3
"""
Git Repository Code Age and Ownership Analyzer

Recursively runs 'git blame' on all tracked files in a Git repository to compute
line-level age distributions and author ownership profiles. Identifies "zombie code"
(untouched for > 1-2 years) and highlights files written by inactive developers.
"""

import os
import sys
import subprocess
import argparse
import time
from datetime import datetime, timezone
from collections import Counter, defaultdict
from typing import Dict, List, Set, Tuple, Optional

# ANSI Colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"

def supports_color() -> bool:
    """Checks if terminal supports colors."""
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return bool(supported_platform or is_a_tty)

def color_text(text: str, color_code: str) -> str:
    """Wraps text in color codes if supported."""
    return f"{color_code}{text}{COLOR_RESET}" if supports_color() else text

def check_git_repo(path: str) -> bool:
    """Checks if the path is inside a Git repository."""
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            cwd=path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
        )
        return res.stdout.strip() == "true"
    except Exception:
        return False

def get_tracked_files(path: str) -> List[str]:
    """Retrieves all tracked files in the Git repository."""
    try:
        res = subprocess.run(
            ["git", "ls-files"],
            cwd=path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
        )
        files = [f.strip() for f in res.stdout.splitlines() if f.strip()]
        # Filter out binary or empty files if possible, but git blame handles it
        return files
    except Exception:
        return []

def get_active_authors(path: str, months: int) -> Set[str]:
    """Retrieves names of authors who have made commits within the last N months."""
    since_date = f"{months} months ago"
    try:
        res = subprocess.run(
            ["git", "log", f"--since={since_date}", "--format=%an"],
            cwd=path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
        )
        authors = {line.strip() for line in res.stdout.splitlines() if line.strip()}
        return authors
    except Exception:
        return set()

def parse_git_blame(repo_path: str, file_rel_path: str) -> Tuple[int, List[Tuple[str, int]]]:
    """
    Runs git blame --porcelain and parses line metadata.
    Returns: (total_lines, list of (author_name, timestamp))
    """
    try:
        res = subprocess.run(
            ["git", "blame", "--porcelain", file_rel_path],
            cwd=repo_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True
        )
    except Exception:
        return 0, []

    lines_metadata = []
    # Map commit SHA -> metadata dictionary to avoid duplicating parser efforts
    commit_cache = {}
    
    current_sha = None
    lines = res.stdout.splitlines()
    i = 0
    total_lines = 0
    
    while i < len(lines):
        line = lines[i]
        if not line.strip():
            i += 1
            continue
            
        # Porcelain start of block: <sha> <orig_line> <final_line> <num_lines>
        parts = line.split()
        sha = parts[0]
        
        # If sha is all zeroes, it is an uncommitted local change
        if sha == "0000000000000000000000000000000000000000":
            author = "Local Changes (Uncommitted)"
            timestamp = int(time.time())
            lines_metadata.append((author, timestamp))
            total_lines += 1
            i += 1
            # Skip past commit header details until we hit content (starts with tab)
            while i < len(lines) and not lines[i].startswith("\t"):
                i += 1
            if i < len(lines): # Skip the content line itself
                i += 1
            continue

        if sha in commit_cache:
            # We already have details, just add line metadata
            author = commit_cache[sha]["author"]
            timestamp = commit_cache[sha]["timestamp"]
            lines_metadata.append((author, timestamp))
            total_lines += 1
            i += 1
            while i < len(lines) and not lines[i].startswith("\t"):
                i += 1
            if i < len(lines):
                i += 1
        else:
            # Parse block header details
            author = "Unknown"
            timestamp = 0
            
            commit_cache[sha] = {}
            i += 1
            while i < len(lines) and not lines[i].startswith("\t"):
                detail_line = lines[i]
                if detail_line.startswith("author "):
                    author = detail_line[7:].strip()
                elif detail_line.startswith("author-time "):
                    try:
                        timestamp = int(detail_line[12:].strip())
                    except ValueError:
                        pass
                i += 1
            
            commit_cache[sha]["author"] = author
            commit_cache[sha]["timestamp"] = timestamp
            lines_metadata.append((author, timestamp))
            total_lines += 1
            
            if i < len(lines): # Skip tab content line
                i += 1
                
    return total_lines, lines_metadata

def analyze_code_age(repo_path: str, active_months: int) -> int:
    """Performs full blame parsing and generates age/ownership metrics."""
    if not check_git_repo(repo_path):
        print(color_text("Error: Directory is not a valid Git repository.", COLOR_RED), file=sys.stderr)
        return 1
        
    print(f"Loading git history diagnostics from: {color_text(os.path.abspath(repo_path), COLOR_BOLD)}")
    
    files = get_tracked_files(repo_path)
    if not files:
        print("No tracked files found in the repository.")
        return 0
        
    print(f"Tracking files count: {len(files)}")
    
    active_authors = get_active_authors(repo_path, active_months)
    print(f"Active developers in the last {active_months} months: {len(active_authors)}")
    print("-" * 80)
    
    now_ts = int(time.time())
    one_day_sec = 86400
    
    # Global metrics
    total_loc = 0
    total_age_days = 0.0
    
    # Age brackets
    brackets = {
        "1. < 30 days": 0,
        "2. 30 - 180 days": 0,
        "3. 180 - 365 days": 0,
        "4. 1 - 2 years": 0,
        "5. > 2 years": 0
    }
    
    global_authors = Counter()
    global_inactive_loc = 0
    
    # File-level details
    file_records = []
    
    # Simple console progress indicator
    processed_count = 0
    print("[*] Performing line-level code autopsy...")
    
    for f in files:
        # Ignore common lockfiles/binary files if needed, but let's check blame returns
        loc, lines_meta = parse_git_blame(repo_path, f)
        if loc == 0:
            continue
            
        total_loc += loc
        file_age_days_sum = 0.0
        inactive_loc_count = 0
        file_authors = Counter()
        
        for author, ts in lines_meta:
            global_authors[author] += 1
            file_authors[author] += 1
            
            # Compute age
            age_days = max(0.0, (now_ts - ts) / one_day_sec)
            file_age_days_sum += age_days
            total_age_days += age_days
            
            # Sort into brackets
            if age_days < 30:
                brackets["1. < 30 days"] += 1
            elif age_days < 180:
                brackets["2. 30 - 180 days"] += 1
            elif age_days < 365:
                brackets["3. 180 - 365 days"] += 1
            elif age_days < 730:
                brackets["4. 1 - 2 years"] += 1
            else:
                brackets["5. > 2 years"] += 1
                
            # Check author activity
            if author not in active_authors and author != "Local Changes (Uncommitted)":
                inactive_loc_count += 1
                global_inactive_loc += 1
                
        avg_file_age = file_age_days_sum / loc
        pct_inactive = (inactive_loc_count / loc) * 100.0
        top_author = file_authors.most_common(1)[0][0] if file_authors else "Unknown"
        
        file_records.append({
            "path": f,
            "loc": loc,
            "avg_age_days": avg_file_age,
            "pct_inactive": pct_inactive,
            "top_author": top_author
        })
        
        processed_count += 1
        if processed_count % 50 == 0:
            print(f"  Processed {processed_count}/{len(files)} files...")
            
    if total_loc == 0:
        print("No lines of code could be parsed using git blame.")
        return 0
        
    print("-" * 80)
    print(f"{color_text('Repository-wide Summary Statistics:', COLOR_BOLD)}")
    print(f"  Total Tracked Files:     {len(files)}")
    print(f"  Total Lines of Code:     {total_loc}")
    print(f"  Average Code Line Age:   {total_age_days / total_loc:.1f} days ({total_age_days / total_loc / 365.25:.2f} years)")
    
    inactive_pct = (global_inactive_loc / total_loc) * 100.0
    inactive_color = COLOR_GREEN if inactive_pct < 20 else (COLOR_YELLOW if inactive_pct < 50 else COLOR_RED)
    print(f"  Zombie/Orphaned Code %:  {color_text(f'{inactive_pct:.2f}%', inactive_color)} (written by inactive authors)")
    print("-" * 80)
    
    # Bracket table
    print(f"{color_text('Code Age Distribution Profile:', COLOR_BOLD)}")
    for bracket, count in sorted(brackets.items()):
        pct = (count / total_loc) * 100.0
        bar = "█" * int(pct / 2)
        print(f"  {bracket:<18} : {count:<8} ({pct:>5.1f}%) {color_text(bar, COLOR_CYAN)}")
    print("-" * 80)
    
    # Author breakdown
    print(f"{color_text('Top Contributors (by live code ownership):', COLOR_BOLD)}")
    sorted_authors = sorted(global_authors.items(), key=lambda x: x[1], reverse=True)
    for idx, (author, loc_count) in enumerate(sorted_authors[:10], 1):
        pct = (loc_count / total_loc) * 100.0
        status = color_text("Active", COLOR_GREEN) if author in active_authors or author == "Local Changes (Uncommitted)" else color_text("Inactive", COLOR_RED)
        print(f"  {idx:>2}. {author:<30} : {loc_count:<8} ({pct:>5.2f}%) [{status}]")
    print("-" * 80)
    
    # Oldest files (Zombies)
    print(f"{color_text('Top 10 Oldest Files (Zombie Code Candidates):', COLOR_BOLD)}")
    sorted_by_age = sorted(file_records, key=lambda x: x["avg_age_days"], reverse=True)
    print(f"{COLOR_BOLD}{'FILE PATH':<50} | {'LOC':<6} | {'AVG AGE (Y)':<11} | {'TOP CONTRIBUTOR'}{COLOR_RESET}")
    print("-" * 80)
    for record in sorted_by_age[:10]:
        years = record["avg_age_days"] / 365.25
        print(f"{record['path'][:50]:<50} | {record['loc']:<6} | {years:>9.2f} y | {record['top_author']}")
    print("-" * 80)
    
    # High Risk files (Inactive ownership)
    print(f"{color_text('Top 10 High-Risk Files (Orphaned Code - Written by Inactive Authors):', COLOR_BOLD)}")
    sorted_by_risk = sorted(file_records, key=lambda x: x["pct_inactive"], reverse=True)
    # Filter files with at least 15 lines of code to avoid 1-line script bias
    risk_candidates = [r for r in sorted_by_risk if r["loc"] >= 15]
    print(f"{COLOR_BOLD}{'FILE PATH':<50} | {'LOC':<6} | {'ORPHAN %':<8} | {'TOP CONTRIBUTOR'}{COLOR_RESET}")
    print("-" * 80)
    for record in risk_candidates[:10]:
        print(f"{record['path'][:50]:<50} | {record['loc']:<6} | {record['pct_inactive']:>7.2f}% | {record['top_author']}")
    print("-" * 80)
    
    return 0

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Git Repository Code Age and Ownership Analyzer",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("repo", nargs="?", default=".", help="Path to Git repository root (default: current directory)")
    parser.add_argument("-m", "--months", type=int, default=12, help="Number of months to qualify developer activity status (default: 12)")
    
    args = parser.parse_args()
    
    return analyze_code_age(args.repo, args.months)

if __name__ == "__main__":
    sys.exit(main())
