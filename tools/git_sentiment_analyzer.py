#!/usr/bin/env python3
"""
Git Commit Sentiment & Frustration Analyzer

Runs 'git log' to fetch commit messages, performs a lexical sentiment analysis
using a built-in vocabulary of positive/negative software development terms,
and prints a dashboard of overall project sentiment, developer mood leaderboard,
and high-frustration hot spots.

Usage:
    python git_sentiment_analyzer.py [options]
"""

import os
import sys
import subprocess
import argparse
import re
from collections import defaultdict
from datetime import datetime

# ANSI colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Built-in Sentiment Lexicon tailored for developers
SENTIMENT_DICT = {
    # Positive words (+1 to +3)
    "awesome": 3, "excellent": 3, "perfect": 3, "beautiful": 2, "clean": 2,
    "optimize": 2, "optimized": 2, "speedup": 2, "faster": 2, "correct": 2,
    "correctly": 2, "solve": 2, "solved": 2, "resolve": 2, "resolved": 2,
    "success": 2, "successful": 2, "successfully": 2, "stable": 2, "happy": 2,
    "love": 2, "great": 2, "good": 1, "improved": 1, "improve": 1,
    "addition": 1, "add": 1, "added": 1, "new": 1, "enable": 1,
    "enabled": 1, "support": 1, "supported": 1, "feature": 1, "thanks": 1,
    
    # Negative words (-1 to -3)
    "regression": -2, "regress": -2, "revert": -1, "reverted": -1, "rollback": -1,
    "workaround": -1, "hack": -1, "temporary": -1, "temp": -1, "ugly": -2,
    "mess": -2, "messy": -2, "slow": -1, "bad": -1, "wrong": -1,
    "issue": -1, "issues": -1, "bug": -1, "bugs": -1, "error": -1,
    "errors": -1, "fail": -1, "failed": -1, "failure": -1, "failures": -1,
    "broken": -2, "broke": -2, "break": -1, "frustrated": -2, "frustrating": -2,
    "annoyed": -2, "stupid": -3, "dumb": -3, "hate": -3, "damn": -3,
    "shit": -3, "crap": -3, "garbage": -3, "trash": -3, "fucking": -3,
    "horrible": -3, "terrible": -3, "wtf": -3, "brokenness": -2, "oops": -1,
}

# Words that intensify sentiment
INTENSIFIERS = {"very", "really", "extremely", "highly", "so", "much", "totally", "completely"}

# Words that negate sentiment
NEGATIONS = {"not", "never", "no", "cant", "cannot", "dont", "wont", "didnt", "isnt", "wasnt"}

def get_git_logs(author=None, since=None, until=None, branch=None, max_count=None):
    """Fetch git log commit data separated by boundary."""
    # Format: ---COMMIT--- \n author \n date \n subject \n body
    boundary = "---COMMIT---"
    cmd = ["git", "log", f"--pretty=format:{boundary}%n%an%n%ad%n%s%n%b", "--date=iso"]
    
    if branch:
        cmd.append(branch)
    if author:
        cmd.append(f"--author={author}")
    if since:
        cmd.append(f"--since={since}")
    if until:
        cmd.append(f"--until={until}")
    if max_count:
        cmd.append(f"-n {max_count}")
        
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True, encoding="utf-8")
        return result.stdout, boundary
    except subprocess.CalledProcessError as e:
        print(f"Error executing git command: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print("Error: 'git' command not found. Please install Git.", file=sys.stderr)
        sys.exit(1)

def clean_and_tokenize(text):
    """Convert text to clean lowercase tokens, keeping alphanumeric parts."""
    text_clean = re.sub(r'[^a-zA-Z\s]', '', text.lower())
    return text_clean.split()

def analyze_sentiment(message):
    """
    Lexical sentiment analysis with intensifiers and negation.
    Returns (score, matched_words_list)
    """
    tokens = clean_and_tokenize(message)
    score = 0
    matched = []
    
    negated = False
    negation_counter = 0
    
    for i, token in enumerate(tokens):
        # Handle negation state decay
        if negated:
            negation_counter += 1
            if negation_counter > 2: # negation affects next 2 tokens max
                negated = False
                
        # Check negation
        if token in NEGATIONS:
            negated = True
            negation_counter = 0
            continue
            
        # Check lexicon
        if token in SENTIMENT_DICT:
            val = SENTIMENT_DICT[token]
            
            # Apply intensifier multiplier from previous token
            multiplier = 1
            if i > 0 and tokens[i-1] in INTENSIFIERS:
                multiplier = 1.5
                
            # Apply negation inversion
            if negated:
                val = -val * 0.8 # flip sign, slightly reduce intensity
                negated = False  # consume negation
                
            score += val * multiplier
            matched.append((token, val * multiplier))
            
    return score, matched

def parse_commits(log_stdout, boundary):
    """Parse git log output into a list of commit dictionaries."""
    commits = []
    raw_blocks = log_stdout.split(boundary + "\n")
    
    for block in raw_blocks:
        if not block.strip():
            continue
        lines = block.splitlines()
        if len(lines) < 3:
            continue
            
        author = lines[0].strip()
        date_str = lines[1].strip()
        subject = lines[2].strip()
        body = "\n".join(lines[3:]) if len(lines) > 3 else ""
        
        full_message = f"{subject}\n{body}"
        score, matches = analyze_sentiment(full_message)
        
        commits.append({
            "author": author,
            "date": date_str,
            "subject": subject,
            "message": full_message,
            "score": score,
            "matches": matches
        })
    return commits

def get_overall_verdict(avg_score):
    """Translate numerical score to a user-friendly mood label."""
    if avg_score > 0.6: return f"{GREEN}Very Happy / Productive{RESET}"
    elif avg_score > 0.2: return f"{GREEN}Positive / Stable{RESET}"
    elif avg_score >= -0.2: return f"{YELLOW}Neutral / Routine{RESET}"
    elif avg_score >= -0.6: return f"{RED}Frustrated / Stressed{RESET}"
    else: return f"{RED}Highly Frustrated / Urgent Code Smells{RESET}"

def main():
    parser = argparse.ArgumentParser(description="Analyze Git commit message sentiment.")
    parser.add_argument("--author", help="Filter commits by author name or email pattern")
    parser.add_argument("--since", help="Filter commits since date")
    parser.add_argument("--until", help="Filter commits until date")
    parser.add_argument("--branch", help="Specific branch/ref to analyze")
    parser.add_argument("--max-count", "-n", type=int, default=500, help="Max commits to analyze (default: 500)")
    parser.add_argument("--no-color", action="store_true", help="Disable color coding in output")
    
    args = parser.parse_args()
    
    if not os.path.exists(".git"):
        # Check parents
        is_in_repo = False
        curr_dir = os.getcwd()
        while True:
            if os.path.exists(os.path.join(curr_dir, ".git")):
                is_in_repo = True
                break
            parent = os.path.dirname(curr_dir)
            if parent == curr_dir:
                break
            curr_dir = parent
        if not is_in_repo:
            print("Error: Must run inside a Git repository.", file=sys.stderr)
            sys.exit(1)
            
    print("Reading Git log...")
    log_output, boundary = get_git_logs(
        author=args.author,
        since=args.since,
        until=args.until,
        branch=args.branch,
        max_count=args.max_count
    )
    
    commits = parse_commits(log_output, boundary)
    if not commits:
        print("No commits found matching search criteria.")
        sys.exit(0)
        
    # Aggregations
    total_score = 0
    author_scores = defaultdict(list)
    frustrated_commits = []
    happy_commits = []
    
    keyword_counts = defaultdict(int)
    keywords_of_interest = ["fix", "bug", "hack", "refactor", "regression", "revert", "temp", "stable"]
    
    for c in commits:
        score = c["score"]
        total_score += score
        author_scores[c["author"]].append(score)
        
        # Categorize hotspots
        if score <= -1.5:
            frustrated_commits.append(c)
        elif score >= 1.5:
            happy_commits.append(c)
            
        # Count keywords of interest in message
        msg_lower = c["message"].lower()
        for kw in keywords_of_interest:
            if kw in msg_lower:
                keyword_counts[kw] += 1
                
    avg_score = total_score / len(commits)
    
    # Sort happy/frustrated lists by magnitude of scores
    frustrated_commits.sort(key=lambda x: x["score"])
    happy_commits.sort(key=lambda x: x["score"], reverse=True)
    
    # Author Leaderboard
    author_leaderboard = []
    for auth, scores in author_scores.items():
        if len(scores) >= 3: # Need at least 3 commits to show on leaderboard
            author_leaderboard.append((sum(scores)/len(scores), auth, len(scores)))
    author_leaderboard.sort(reverse=True)
    
    # Print results
    print(f"\n{BOLD}{CYAN}=== GIT COMMIT SENTIMENT DASHBOARD ===={RESET}")
    print(f"Commits Analyzed:  {len(commits)}")
    print(f"Overall Score:     {BOLD}{avg_score:+.3f}{RESET}")
    print(f"Project Verdict:   {get_overall_verdict(avg_score)}")
    print("-" * 50)
    
    print(f"\n{BOLD}Keyword Occurrences:{RESET}")
    for kw in keywords_of_interest:
        count = keyword_counts[kw]
        pct = (count / len(commits)) * 100
        bar = "#" * int(pct // 2) if pct > 0 else ""
        print(f"  {kw:<12} {count:<5} ({pct:4.1f}%) {bar}")
        
    if author_leaderboard:
        print(f"\n{BOLD}Developer Mood Leaderboard (min 3 commits):{RESET}")
        print(f"  {'Score':<8} {'Author':<30} {'Commits':<8}")
        print("  " + "-" * 48)
        for score, auth, count in author_leaderboard:
            color = GREEN if score > 0.1 else (RED if score < -0.1 else YELLOW)
            if args.no_color:
                print(f"  {score:+5.2f}   {auth[:28]:<30} {count:<8}")
            else:
                print(f"  {color}{score:+5.2f}{RESET}   {auth[:28]:<30} {count:<8}")
                
    if frustrated_commits:
        print(f"\n{BOLD}{RED}Top Frustrated / Hot-spot Commits:{RESET}")
        for c in frustrated_commits[:5]:
            date_short = c["date"][:10]
            print(f"  [{c['score']:+4.1f}] {BOLD}{c['author'][:18]}{RESET} ({date_short}): {RED}{c['subject'][:50]}{RESET}")
            # print matched triggers
            triggers = [f"{t} ({v:+g})" for t, v in c["matches"] if v < 0]
            if triggers:
                print(f"    ↳ Frustration Triggers: {', '.join(triggers)}")
                
    if happy_commits:
        print(f"\n{BOLD}{GREEN}Top Positive / High-morale Commits:{RESET}")
        for c in happy_commits[:5]:
            date_short = c["date"][:10]
            print(f"  [{c['score']:+4.1f}] {BOLD}{c['author'][:18]}{RESET} ({date_short}): {GREEN}{c['subject'][:50]}{RESET}")
            triggers = [f"{t} ({v:+g})" for t, v in c["matches"] if v > 0]
            if triggers:
                print(f"    ↳ Positive Triggers: {', '.join(triggers)}")
    print()

if __name__ == "__main__":
    main()
