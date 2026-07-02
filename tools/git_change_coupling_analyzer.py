#!/usr/bin/env python3
"""
Git Change Coupling Analyzer

Analyze Git commit history to detect logical/temporal coupling (files that are frequently
changed together in the same commit). This is a valuable architectural analysis tool
to identify modularity violations and potential code smells.

Metrics calculated:
- Support: Number of commits where both files changed together
- Jaccard Similarity (Coupling Degree): C(A & B) / C(A | B)
- Confidence A -> B: Percentage of times A changed that B also changed

Usage:
    python tools/git_change_coupling_analyzer.py --min-support 3 --limit 20

Requirements:
    - Git command line installed
    - Python 3.6+
"""

import os
import sys
import subprocess
import argparse
from collections import defaultdict
from itertools import combinations

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_colored(text, color, enabled=True):
    if enabled:
        print(f"{color}{text}{RESET}")
    else:
        print(text)

def run_git_command(args, repo_path):
    """Run a git command in the target repository directory."""
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=repo_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=True
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error executing git command: {e.stderr}", file=sys.stderr)
        return None
    except FileNotFoundError:
        print("Error: Git command line tool not found in PATH.", file=sys.stderr)
        return None

def analyze_coupling(repo_path, max_commits, extensions, ignore_dirs, min_support):
    # Log command args
    log_args = ["log", "--name-only", "--pretty=format:COMMIT:%H"]
    if max_commits > 0:
        log_args.append(f"-n {max_commits}")

    git_output = run_git_command(log_args, repo_path)
    if not git_output:
        return None, "Failed to retrieve git logs."

    # Parse commits
    commits = []
    current_commit_files = set()
    
    # Process line by line
    for line in git_output.splitlines():
        line = line.strip()
        if not line:
            continue
            
        if line.startswith("COMMIT:"):
            if current_commit_files:
                commits.append(current_commit_files)
                current_commit_files = set()
        else:
            file_path = line.replace("\\", "/")
            # Filter by extensions
            if extensions:
                _, ext = os.path.splitext(file_path)
                if ext not in extensions:
                    continue
            # Filter by ignore directories
            ignored = False
            for d in ignore_dirs:
                if file_path.startswith(d.strip("/")) or f"/{d.strip('/')}/" in file_path:
                    ignored = True
                    break
            if ignored:
                continue
                
            current_commit_files.add(file_path)

    # Append the last commit
    if current_commit_files:
        commits.append(current_commit_files)

    # Calculate individual file frequencies
    file_frequencies = defaultdict(int)
    for commit_files in commits:
        for f in commit_files:
            file_frequencies[f] += 1

    # Calculate pair co-occurrences
    pair_frequencies = defaultdict(int)
    for commit_files in commits:
        if len(commit_files) < 2:
            continue
        # We only care about commits changing a reasonable number of files
        # Commits changing 50+ files are usually giant refactorings or dependency updates, ignoring them reduces noise
        if len(commit_files) > 40:
            continue
            
        for f1, f2 in combinations(sorted(commit_files), 2):
            pair_frequencies[(f1, f2)] += 1

    # Calculate metrics
    coupling_results = []
    for (f1, f2), support in pair_frequencies.items():
        if support < min_support:
            continue
            
        freq_f1 = file_frequencies[f1]
        freq_f2 = file_frequencies[f2]
        
        # Jaccard index: support / (freq_A + freq_B - support)
        union_size = freq_f1 + freq_f2 - support
        jaccard = (support / union_size) * 100 if union_size > 0 else 0
        
        # Confidence A -> B and B -> A
        conf_1_2 = (support / freq_f1) * 100
        conf_2_1 = (support / freq_f2) * 100
        
        coupling_results.append({
            "file_a": f1,
            "file_b": f2,
            "support": support,
            "freq_a": freq_f1,
            "freq_b": freq_f2,
            "jaccard": jaccard,
            "conf_a_b": conf_1_2,
            "conf_b_a": conf_2_1
        })

    # Sort by Jaccard similarity (coupling degree)
    coupling_results.sort(key=lambda x: x["jaccard"], reverse=True)
    return coupling_results, len(commits)

def main():
    parser = argparse.ArgumentParser(
        description="Analyze Git commit history to calculate logical coupling between files.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("-d", "--dir", default=".", help="Path to Git repository directory (default: current directory)")
    parser.add_argument("-n", "--commits", type=int, default=1000, help="Number of commits to analyze (default: 1000, use 0 for all)")
    parser.add_argument("-s", "--min-support", type=int, default=3, help="Minimum shared commits to include in results (default: 3)")
    parser.add_argument("-l", "--limit", type=int, default=30, help="Limit number of output pairs (default: 30)")
    parser.add_argument("-e", "--extensions", help="Comma-separated file extensions to include (e.g. .py,.js)")
    parser.add_argument("-i", "--ignore", default="tests,docs,vendor,node_modules", help="Comma-separated directories to ignore")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")

    args = parser.parse_args()
    use_color = not args.no_color and sys.stdout.isatty() and os.name != 'nt' or (os.name == 'nt' and 'COLORTERM' in os.environ)

    repo_path = os.path.abspath(args.dir)
    if not os.path.exists(os.path.join(repo_path, ".git")):
        print_colored(f"Error: Directory '{repo_path}' is not a Git repository.", RED, use_color)
        return 1

    extensions = [ext.strip() for ext in args.extensions.split(",")] if args.extensions else None
    ignore_dirs = [d.strip() for d in args.ignore.split(",")] if args.ignore else []

    print_colored(f"\n{BOLD}Analyzing logical coupling in repository: {repo_path}...{RESET}", BOLD if use_color else "", use_color)
    
    results, total_commits_or_err = analyze_coupling(
        repo_path=repo_path,
        max_commits=args.commits,
        extensions=extensions,
        ignore_dirs=ignore_dirs,
        min_support=args.min_support
    )

    if results is None:
        print_colored(f"Error: {total_commits_or_err}", RED, use_color)
        return 1

    print(f"Analyzed {total_commits_or_err} commits.")
    print(f"Found {len(results)} coupled file pairs meeting criteria (support >= {args.min_support}).")
    print("-" * 110)
    
    if not results:
        print_colored("No logical coupling pairs found.", YELLOW, use_color)
        return 0

    header = f"{'File A':<45} | {'File B':<45} | {'Support':<7} | {'Jaccard':<8} | {'Conf A->B':<9} | {'Conf B->A':<9}"
    print(header)
    print("-" * 110)

    for item in results[:args.limit]:
        # Truncate long file paths to fit table nicely
        fa = item["file_a"]
        if len(fa) > 43:
            fa = "..." + fa[-40:]
            
        fb = item["file_b"]
        if len(fb) > 43:
            fb = "..." + fb[-40:]

        row = (
            f"{fa:<45} | "
            f"{fb:<45} | "
            f"{item['support']:^7} | "
            f"{item['jaccard']:>6.1f}% | "
            f"{item['conf_a_b']:>7.1f}% | "
            f"{item['conf_b_a']:>7.1f}%"
        )
        
        # Color highly coupled pairs (Jaccard > 50%)
        if item["jaccard"] >= 50.0:
            print_colored(row, YELLOW, use_color)
        else:
            print(row)

    print("-" * 110)
    print_colored("Support: shared commits | Jaccard: overall coupling degree | Confidence: directional dependency", BLUE, use_color)
    return 0

if __name__ == "__main__":
    sys.exit(main())
