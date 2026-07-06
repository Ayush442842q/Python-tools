#!/usr/bin/env python3
"""
Git Ownership Entropy & Fragmentation Analyzer
----------------------------------------------
Analyzes the commit history of a Git repository to calculate the ownership
entropy (Shannon Entropy) and contribution inequality (Gini Coefficient)
on a per-file basis.

Files with high commit rates and fragmented ownership (high entropy, low top author share)
are statistically shown to be more prone to bugs and coordination debt.

Author: Antigravity
License: MIT
"""

import os
import sys
import math
import subprocess
import argparse
import json
from collections import defaultdict
from typing import Dict, List, Tuple, Any

def run_git_command(args: List[str], cwd: str) -> str:
    """Run a git command and return its stdout."""
    try:
        result = subprocess.run(
            ["git"] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            cwd=cwd
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Git command failed: {' '.join(e.cmd)}", file=sys.stderr)
        print(e.stderr, file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("Error: 'git' executable not found. Make sure Git is installed and in your PATH.", file=sys.stderr)
        sys.exit(1)

def get_git_log_data(cwd: str) -> Dict[str, Dict[str, int]]:
    """
    Get commit author frequencies per file.
    Returns: { file_path: { author_email: commit_count } }
    """
    # %aE is author email, --numstat outputs: added deleted file_path
    log_output = run_git_command(
        ["log", "--use-mailmap", "--no-merges", "--pretty=format:AUTHOR:%aE", "--numstat"],
        cwd=cwd
    )

    file_author_commits = defaultdict(lambda: defaultdict(int))
    current_author = None

    for line in log_output.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("AUTHOR:"):
            current_author = line.split("AUTHOR:", 1)[1].strip()
        elif current_author:
            # Parse numstat line: <added> <deleted> <filepath>
            parts = line.split(None, 2)
            if len(parts) == 3:
                filepath = parts[2].strip()
                # Ignore binary files or missing stats
                if parts[0] == "-" or parts[1] == "-":
                    continue
                file_author_commits[filepath][current_author] += 1

    return file_author_commits

def calculate_entropy(author_commits: Dict[str, int], total_commits: int) -> float:
    """Calculate Shannon Entropy of author contributions."""
    entropy = 0.0
    for commits in author_commits.values():
        p = commits / total_commits
        if p > 0:
            entropy -= p * math.log2(p)
    return entropy

def calculate_gini(commits_list: List[int]) -> float:
    """
    Calculate the Gini coefficient of author contributions.
    Gini coefficient of 0 = perfect equality (everyone contributed equally).
    Gini coefficient of 1 = complete inequality (one person contributed everything).
    """
    n = len(commits_list)
    if n <= 1:
        return 1.0  # Single author owns it completely
    
    sorted_commits = sorted(commits_list)
    cumulative_sum = 0
    sum_of_commits = sum(sorted_commits)
    
    if sum_of_commits == 0:
        return 0.0

    for idx, commits in enumerate(sorted_commits, 1):
        cumulative_sum += commits * (n - idx + 1)
        
    return (n + 1 - 2 * (cumulative_sum / sum_of_commits)) / n

def analyze_ownership(file_author_commits: Dict[str, Dict[str, int]]) -> List[Dict[str, Any]]:
    """Process files and compute metrics."""
    results = []
    
    for filepath, authors in file_author_commits.items():
        total_commits = sum(authors.values())
        if total_commits == 0:
            continue

        unique_authors = len(authors)
        entropy = calculate_entropy(authors, total_commits)
        
        # Determine top contributor
        top_author = max(authors, key=authors.get)
        top_commits = authors[top_author]
        top_share = top_commits / total_commits

        # Gini Coefficient
        gini = calculate_gini(list(authors.values()))

        # Risk Score (heuristic): combining total commits (velocity) and entropy (fragmentation)
        # High commit files with many equal authors are high coordination risk
        normalized_commits = min(total_commits / 50.0, 1.0)  # cap at 50 commits
        normalized_entropy = min(entropy / 3.0, 1.0)         # cap at entropy of 3.0 (8+ active authors)
        risk_score = normalized_commits * normalized_entropy

        results.append({
            "file": filepath,
            "total_commits": total_commits,
            "unique_authors": unique_authors,
            "entropy": round(entropy, 3),
            "gini": round(gini, 3),
            "top_author": top_author,
            "top_share_pct": round(top_share * 100, 1),
            "risk_score": round(risk_score, 3)
        })

    # Sort by risk score descending
    results.sort(key=lambda x: x["risk_score"], reverse=True)
    return results

def main():
    parser = argparse.ArgumentParser(description="Git Ownership Entropy & Contribution Fragmentation Analyzer.")
    parser.add_argument("path", nargs="?", default=".", help="Path to the Git repository directory")
    parser.add_argument("--limit", type=int, default=20, help="Limit output to top N highest-risk files")
    parser.add_argument("--min-commits", type=int, default=3, help="Ignore files with fewer than N commits")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    args = parser.parse_args()

    repo_path = os.path.abspath(args.path)
    if not os.path.exists(os.path.join(repo_path, ".git")):
        print(f"Error: Directory '{repo_path}' is not a Git repository.", file=sys.stderr)
        sys.exit(1)

    # Fetch data
    file_author_commits = get_git_log_data(repo_path)
    
    # Filter by minimum commits
    filtered_data = {
        fp: auths for fp, auths in file_author_commits.items()
        if sum(auths.values()) >= args.min_commits
    }

    analysis = analyze_ownership(filtered_data)
    limited_analysis = analysis[:args.limit]

    if args.json:
        print(json.dumps({
            "repository": repo_path,
            "total_files_analyzed": len(analysis),
            "metrics": limited_analysis
        }, indent=2))
        return

    # Visual Table Report
    print("=" * 115)
    print(f"GIT OWNERSHIP ENTROPY & FRAGMENTATION ANALYZER: {repo_path}")
    print(f"Top {args.limit} files ranked by coordination risk (High commits + High author fragmentation)")
    print("=" * 115)
    print(f"{'File Path':<40} | {'Commits':<7} | {'Authors':<7} | {'Top Author Share':<17} | {'Entropy':<7} | {'Gini':<6} | {'Risk Rating':<12}")
    print("-" * 115)

    for item in limited_analysis:
        # Determine risk color/text
        score = item["risk_score"]
        if score > 0.6:
            rating = "\033[91mCRITICAL\033[0m"
        elif score > 0.4:
            rating = "\033[91mHIGH\033[0m"
        elif score > 0.2:
            rating = "\033[93mMEDIUM\033[0m"
        else:
            rating = "\033[92mLOW\033[0m"

        top_share = f"{item['top_share_pct']}%"
        
        # Truncate long paths
        path = item["file"]
        if len(path) > 40:
            path = "..." + path[-37:]

        print(f"{path:<40} | {item['total_commits']:<7} | {item['unique_authors']:<7} | {top_share:<17} | {item['entropy']:<7} | {item['gini']:<6} | {rating:<12}")

    print("=" * 115)
    print("Interpretation:")
    print("  * Entropy: Higher entropy (e.g. > 1.5) means many authors have edited this file in similar proportions.")
    print("  * Gini: Lower Gini coefficient means more equal contribution (higher shared ownership/fragmentation).")
    print("  * Risk: Files with high commit frequency and fragmented ownership are communication hotspots prone to bugs.")

if __name__ == "__main__":
    main()
