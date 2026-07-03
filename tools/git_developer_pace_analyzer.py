#!/usr/bin/env python3
"""
Git Developer Pace Analyzer
---------------------------
Analyzes the commit pacing and temporal patterns of developers in a local Git repository.
Calculates active hours, weekend work, time gaps between commits (micro-commits vs mega-commits),
burnout risk, and context-switching metrics via path entropy (how scattered changes are).
Also renders an ASCII/Unicode chart of commit velocity over the last 90 days.

Author: Antigravity
License: MIT
"""

import sys
import math
import subprocess
import argparse
from datetime import datetime, timedelta
from collections import defaultdict

# ANSI Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

def run_git_command(args):
    """Executes a git command and returns stdout as a list of lines."""
    try:
        res = subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
            encoding='utf-8',
            errors='ignore'
        )
        return res.stdout.splitlines()
    except subprocess.CalledProcessError as e:
        print(f"{RED}Git command error: {e.stderr.strip()}{RESET}", file=sys.stderr)
        return []
    except FileNotFoundError:
        print(f"{RED}Error: Git is not installed or not in PATH.{RESET}", file=sys.stderr)
        return []

def calculate_entropy(counts):
    """Calculates Shannon entropy for path focus."""
    total = sum(counts.values())
    if total == 0:
        return 0.0
    entropy = 0.0
    for count in counts.values():
        p = count / total
        entropy -= p * math.log2(p)
    return entropy

def render_timeline_chart(timeline, days_limit=90):
    """Renders a simple ASCII/Unicode bar chart of commit velocity."""
    if not timeline:
        print("No timeline data available.")
        return
        
    today = datetime.now().date()
    # Fill in missing dates in the range
    sorted_dates = []
    for i in range(days_limit - 1, -1, -1):
        d = today - timedelta(days=i)
        sorted_dates.append((d, timeline[d]))
        
    max_commits = max(timeline.values()) if timeline else 0
    if max_commits == 0:
        print("No commits in the selected timeline range.")
        return
        
    print(f"\n{BOLD}{CYAN}COMMIT PACING TIMELINE (LAST {days_limit} DAYS){RESET}")
    print(f"Bar height represents commit volume (Max daily commits: {max_commits})\n")
    
    chart_height = 8
    # We render column by column or line by line
    # Line by line is easier: 
    # For each row from chart_height down to 1:
    for r in range(chart_height, 0, -1):
        row_chars = []
        threshold = (r / chart_height) * max_commits
        for d, commits in sorted_dates:
            if commits >= threshold:
                row_chars.append("█")
            elif commits >= threshold - (0.5 / chart_height) * max_commits:
                row_chars.append("▄")
            else:
                row_chars.append(" ")
        print(f" {int(threshold):>3} | " + "".join(row_chars))
        
    print(" " * 5 + "+" + "-" * days_limit)
    
    # Print dates labels
    date_labels = f"{(today - timedelta(days=days_limit-1)).strftime('%b %d')}{' ' * (days_limit - 13)}{today.strftime('%b %d')}"
    print(" " * 7 + date_labels + "\n")

def analyze_git_history(days_limit, author_filter):
    """Parses git logs and extracts metrics."""
    # Format: COMMIT|timestamp|email|name|subject
    # followed by list of files changed
    cmd = ["git", "log", "--pretty=format:COMMIT|%at|%ae|%an|%s", "--name-only"]
    if days_limit:
        since_date = (datetime.now() - timedelta(days=days_limit)).strftime('%Y-%m-%d')
        cmd.append(f"--since={since_date}")
        
    lines = run_git_command(cmd)
    if not lines:
        return None
        
    commits_by_author = defaultdict(list)
    paths_by_author = defaultdict(lambda: defaultdict(int))
    timeline = defaultdict(int)
    
    current_author = None
    current_commit = None
    
    for line in lines:
        if line.startswith("COMMIT|"):
            parts = line.split("|", 4)
            if len(parts) >= 5:
                try:
                    ts = int(parts[1])
                    email = parts[2].lower()
                    name = parts[3]
                    subject = parts[4]
                    
                    dt = datetime.fromtimestamp(ts)
                    date_key = dt.date()
                    timeline[date_key] += 1
                    
                    if author_filter and author_filter.lower() not in email and author_filter.lower() not in name.lower():
                        current_author = None
                        continue
                        
                    current_author = email
                    current_commit = {
                        "timestamp": ts,
                        "datetime": dt,
                        "subject": subject,
                        "files": []
                    }
                    commits_by_author[current_author].append(current_commit)
                except Exception:
                    current_author = None
        elif line.strip() and current_author:
            # Parse top level folder for entropy calculation
            path = line.strip()
            current_commit["files"].append(path)
            parts = path.split("/")
            top_dir = parts[0] if parts else "root"
            paths_by_author[current_author][top_dir] += 1
            
    return commits_by_author, paths_by_author, timeline

def compile_metrics(commits_by_author, paths_by_author):
    stats = {}
    for author, commits in commits_by_author.items():
        if not commits:
            continue
            
        # Chronological sorting for gaps analysis
        commits.sort(key=lambda x: x["timestamp"])
        
        hours = [0] * 24
        weekends = 0
        late_nights = 0  # 10 PM to 5 AM
        
        gaps = []
        for i in range(1, len(commits)):
            gap = commits[i]["timestamp"] - commits[i-1]["timestamp"]
            gaps.append(gap)
            
        for c in commits:
            dt = c["datetime"]
            hours[dt.hour] += 1
            if dt.weekday() >= 5: # Saturday/Sunday
                weekends += 1
            if dt.hour >= 22 or dt.hour <= 5:
                late_nights += 1
                
        total_commits = len(commits)
        weekend_pct = (weekends / total_commits) * 100
        latenight_pct = (late_nights / total_commits) * 100
        
        # Gap analysis
        micro_commits = sum(1 for g in gaps if g < 300) # < 5 mins
        mega_commits = sum(1 for g in gaps if g > 172800) # > 48 hours
        
        avg_gap = sum(gaps) / len(gaps) if gaps else 0
        # Median gap
        sorted_gaps = sorted(gaps)
        median_gap = sorted_gaps[len(sorted_gaps)//2] if sorted_gaps else 0
        
        # Path entropy
        dir_counts = paths_by_author[author]
        entropy = calculate_entropy(dir_counts)
        
        # Burnout Risk Index (0-100)
        # Factors: late night working (40%), weekend working (30%), gap pattern/variance (30%)
        # Normal late night < 5%, weekend < 5%
        burnout_score = (latenight_pct * 0.4) + (weekend_pct * 0.3)
        # High volume of quick micro commits can show frantic pacing
        micro_pct = (micro_commits / len(gaps) * 100) if gaps else 0
        burnout_score += (micro_pct * 0.3)
        burnout_score = min(100.0, burnout_score)
        
        stats[author] = {
            "total_commits": total_commits,
            "weekend_pct": weekend_pct,
            "latenight_pct": latenight_pct,
            "avg_gap": avg_gap,
            "median_gap": median_gap,
            "micro_commits": micro_commits,
            "mega_commits": mega_commits,
            "entropy": entropy,
            "burnout_score": burnout_score,
            "name": commits[0]["subject"] # fallback placeholder for metadata
        }
    return stats

def format_duration(seconds):
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds/60:.1f}m"
    elif seconds < 86400:
        return f"{seconds/3600:.1f}h"
    else:
        return f"{seconds/86400:.1f}d"

def main():
    parser = argparse.ArgumentParser(
        description="Git Developer Pace Analyzer - Analyze pacing, temporal distributions, context-switching, and burnout metrics.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--days", type=int, default=90, help="Timeline depth in days (default: 90).")
    parser.add_argument("--author", help="Filter statistics to a specific author email or name.")
    parser.add_argument("--no-chart", action="store_true", help="Skip rendering the daily commit velocity chart.")
    
    args = parser.parse_args()
    
    # Check if we are inside a Git repository
    git_check = run_git_command(["git", "rev-parse", "--is-inside-work-tree"])
    if not git_check or git_check[0] != "true":
        print(f"{RED}Error: Current directory is not a Git repository.{RESET}")
        sys.exit(1)
        
    print(f"{BOLD}[*] Analyzing Git repository commit pacing metrics...{RESET}")
    
    raw_data = analyze_git_history(args.days, args.author)
    if not raw_data:
        print(f"{YELLOW}No commits found in the last {args.days} days.{RESET}")
        sys.exit(0)
        
    commits_by_author, paths_by_author, timeline = raw_data
    stats = compile_metrics(commits_by_author, paths_by_author)
    
    if not stats:
        print(f"{YELLOW}No metrics computed. Check author filter.{RESET}")
        sys.exit(0)
        
    # Render daily commit chart
    if not args.no_chart:
        render_timeline_chart(timeline, args.days)
        
    # Display stats table
    print("=" * 110)
    print(f"{BOLD}{'DEVELOPER COMMIT PACING & BURNOUT INDEX':^110}{RESET}")
    print("=" * 110)
    print(f"| {'Developer (Email)':<30} | {'Commits':>7} | {'Late Nt%':>8} | {'Wkend%':>6} | {'Median Gap':>10} | {'Micro/Mega':>12} | {'Entropy':>7} | {'Burnout%':>8} |")
    print("-" * 110)
    
    for author, s in stats.items():
        median_gap_str = format_duration(s["median_gap"])
        micro_mega_str = f"{s['micro_commits']}/{s['mega_commits']}"
        
        # Colorize burnout score
        b_score = s["burnout_score"]
        if b_score >= 60:
            b_color = RED
        elif b_score >= 30:
            b_color = YELLOW
        else:
            b_color = GREEN
            
        b_str = f"{b_color}{b_score:6.1f}%{RESET}"
        
        # Truncate author email if needed
        author_disp = author[:30]
        
        print(f"| {author_disp:<30} | {s['total_commits']:>7} | {s['latenight_pct']:>7.1f}% | {s['weekend_pct']:>5.1f}% | {median_gap_str:>10} | {micro_mega_str:>12} | {s['entropy']:>7.2f} | {b_str} |")
        
    print("=" * 110)
    
    # Interpretation tips
    print(f"\n{BOLD}Pacing Metrics Guide:{RESET}")
    print(f"  • {BOLD}Late Nt% / Wkend%{RESET}: High percentages (>15%) suggest unsustainable working hours (Burnout Risk).")
    print(f"  • {BOLD}Median Gap{RESET}: Typical time elapsed between commits. Shorter indicates rapid iteration or micro-commits.")
    print(f"  • {BOLD}Micro/Mega{RESET}: Gaps < 5 mins (micro) vs gaps > 2 days (mega). Rapid micro commits often occur in bursts.")
    print(f"  • {BOLD}Path Entropy{RESET}: A measure of context switching (0.0 to log2(N)). Higher values (>2.0) mean changes are scattered across many folders.")
    print(f"  • {BOLD}Burnout Risk Score{RESET}: Evaluated based on late-night sessions, weekend workloads, and rapid burst frequency.")
    print()

if __name__ == "__main__":
    main()
