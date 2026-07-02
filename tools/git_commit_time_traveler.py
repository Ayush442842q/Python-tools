#!/usr/bin/env python3
"""
Git Commit Time-Traveler
A standalone utility to modify the author and committer dates of commits in a Git repository.
Uses git commit-tree to rebuild history cleanly and safely, supporting timestamp shifts,
randomization, and specific time configurations.
"""

import argparse
import datetime
import os
import random
import subprocess
import sys


def run_git_command(args, env=None, input_data=None):
    """Helper to run a git command and return its output."""
    try:
        proc = subprocess.Popen(
            ["git"] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            env=env or os.environ.copy()
        )
        out, err = proc.communicate(input=input_data)
        if proc.returncode != 0:
            raise RuntimeError(f"Git command failed: git {' '.join(args)}\nError: {err.decode('utf-8', errors='ignore')}")
        return out.decode('utf-8', errors='ignore').strip()
    except FileNotFoundError:
        print("Error: 'git' executable not found. Make sure Git is installed and in your PATH.", file=sys.stderr)
        sys.exit(1)


def is_git_repo():
    """Checks if the current directory is inside a git repository."""
    try:
        res = run_git_command(["rev-parse", "--is-inside-work-tree"])
        return res == "true"
    except Exception:
        return False


def get_current_branch():
    """Gets the name of the current active branch."""
    return run_git_command(["rev-parse", "--abbrev-ref", "HEAD"])


def parse_date_string(date_str):
    """Parses standard ISO or YYYY-MM-DD HH:MM:SS strings into datetime objects."""
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    raise ValueError(f"Invalid date format: {date_str}. Use YYYY-MM-DD HH:MM:SS or YYYY-MM-DD.")


def parse_delta(delta_str):
    """Parses a time offset string like '+2h', '-3d', '+1y' into a timedelta."""
    match = re.match(r"^([+-])(\d+)([hdmys])$", delta_str.strip())
    if not match:
        raise ValueError(f"Invalid offset format: {delta_str}. Example: +2h, -5d, +1y")
    sign, value, unit = match.group(1), int(match.group(2)), match.group(3)
    multiplier = -1 if sign == "-" else 1
    
    if unit == "h":
        return datetime.timedelta(hours=value * multiplier)
    elif unit == "d":
        return datetime.timedelta(days=value * multiplier)
    elif unit == "m":
        # Approximate month
        return datetime.timedelta(days=value * 30 * multiplier)
    elif unit == "y":
        # Approximate year
        return datetime.timedelta(days=value * 365 * multiplier)
    return datetime.timedelta(0)


import re

def main():
    parser = argparse.ArgumentParser(
        description="Rewrite author and committer dates in Git commit history cleanly and safely."
    )
    parser.add_argument(
        "--range",
        default="HEAD~10..HEAD",
        help="Git revision range to rewrite (e.g. HEAD~5..HEAD, branch1..branch2). Default: HEAD~10..HEAD"
    )
    parser.add_argument(
        "--shift",
        help="Shift dates by offset. Format: [+-][value][h/d/m/y] (e.g. +2h, -10d, +1y)."
    )
    parser.add_argument(
        "--randomize",
        help="Add random shift within range. Format: [min_offset]..[max_offset] (e.g. 5m..2h, 1h..12h)."
    )
    parser.add_argument(
        "--set-time",
        help="Force the time of day for all rewritten commits. Format: HH:MM:SS (e.g. 14:30:00)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Perform calculations and show proposed changes without writing to Git history."
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Bypass warnings and execute history rewrite."
    )

    args = parser.parse_args()

    if not is_git_repo():
        print("Error: Current directory is not a Git repository.", file=sys.stderr)
        return 1

    # Resolve revision range
    # Check if range is valid
    try:
        run_git_command(["rev-parse", args.range])
    except RuntimeError as e:
        print(f"Error: Invalid revision range '{args.range}'. Details: {e}", file=sys.stderr)
        return 1

    # Get list of commits in topological order (oldest first)
    try:
        commits = run_git_command(["log", "--reverse", "--format=%H", args.range]).splitlines()
        commits = [c.strip() for c in commits if c.strip()]
    except Exception as e:
        print(f"Error listing commits: {e}", file=sys.stderr)
        return 1

    if not commits:
        print("No commits found in the specified range. Check your range specifier.", file=sys.stderr)
        return 0

    print(f"Analyzing {len(commits)} commits...")

    # Parse inputs
    shift_td = None
    if args.shift:
        try:
            shift_td = parse_delta(args.shift)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1

    rand_min_td = None
    rand_max_td = None
    if args.randomize:
        match = re.match(r"^(\d+)([mh])\.\.(\d+)([mh])$", args.randomize.strip())
        if not match:
            print("Error: Invalid randomize format. Use [min]..[max] like 10m..2h or 1h..5h", file=sys.stderr)
            return 1
        min_val, min_unit, max_val, max_unit = int(match.group(1)), match.group(2), int(match.group(3)), match.group(4)
        
        def to_seconds(val, unit):
            return val * 60 if unit == "m" else val * 3600

        rand_min_secs = to_seconds(min_val, min_unit)
        rand_max_secs = to_seconds(max_val, max_unit)
        if rand_min_secs > rand_max_secs:
            print("Error: Min randomize offset cannot be greater than max offset.", file=sys.stderr)
            return 1

    set_time_obj = None
    if args.set_time:
        try:
            set_time_obj = datetime.datetime.strptime(args.set_time.strip(), "%H:%M:%S").time()
        except ValueError:
            print("Error: Invalid time format. Use HH:MM:SS.", file=sys.stderr)
            return 1

    if not (shift_td or args.randomize or set_time_obj):
        print("Error: You must specify at least one modification flag: --shift, --randomize, or --set-time.", file=sys.stderr)
        return 1

    # Map of old commit hash -> new commit hash
    rewrite_map = {}
    proposed_changes = []

    # Get details for each commit
    for idx, commit in enumerate(commits):
        # Format strings:
        # %T = tree hash
        # %P = parent hashes
        # %an = author name, %ae = author email, %ad = author date (raw unix timestamp + offset)
        # %cn = committer name, %ce = committer email, %cd = committer date (raw unix timestamp + offset)
        details = run_git_command(["log", "-n", "1", "--format=%T|%P|%an|%ae|%at|%ax|%cn|%ce|%ct|%cx", commit]).split('|')
        
        tree = details[0]
        parents = [p for p in details[1].split() if p.strip()]
        author_name = details[2]
        author_email = details[3]
        author_ts = int(details[4])
        author_tz = details[5] # raw offset (e.g. +0530)
        committer_name = details[6]
        committer_email = details[7]
        committer_ts = int(details[8])
        committer_tz = details[9]

        # Convert to datetimes
        auth_dt = datetime.datetime.fromtimestamp(author_ts, datetime.timezone.utc)
        comm_dt = datetime.datetime.fromtimestamp(committer_ts, datetime.timezone.utc)

        # Apply shifts
        new_auth_dt = auth_dt
        new_comm_dt = comm_dt

        if shift_td:
            new_auth_dt += shift_td
            new_comm_dt += shift_td

        if args.randomize:
            rand_sec = random.randint(rand_min_secs, rand_max_secs)
            rand_sign = random.choice([-1, 1])
            rand_td = datetime.timedelta(seconds=rand_sec * rand_sign)
            new_auth_dt += rand_td
            new_comm_dt += rand_td

        if set_time_obj:
            new_auth_dt = datetime.datetime.combine(new_auth_dt.date(), set_time_obj, new_auth_dt.tzinfo)
            new_comm_dt = datetime.datetime.combine(new_comm_dt.date(), set_time_obj, new_comm_dt.tzinfo)

        # Get commit message
        message = run_git_command(["log", "-n", "1", "--format=%B", commit])

        proposed_changes.append({
            'old_hash': commit[:8],
            'tree': tree,
            'parents': parents,
            'author_name': author_name,
            'author_email': author_email,
            'author_date_str': new_auth_dt.strftime("%Y-%m-%d %H:%M:%S") + " " + author_tz,
            'committer_name': committer_name,
            'committer_email': committer_email,
            'committer_date_str': new_comm_dt.strftime("%Y-%m-%d %H:%M:%S") + " " + committer_tz,
            'old_author_date': auth_dt.strftime("%Y-%m-%d %H:%M:%S"),
            'new_author_date': new_auth_dt.strftime("%Y-%m-%d %H:%M:%S"),
            'message_first_line': message.splitlines()[0] if message else "",
            'full_message': message
        })

    # Display proposed changes
    print("\nProposed Time Travel Shifts:")
    print(f"{'Commit':<10} | {'Original Date':<20} | {'New Date':<20} | {'Subject':<35}")
    print("-" * 95)
    for c in proposed_changes:
        print(f"{c['old_hash']:<10} | {c['old_author_date']:<20} | {c['new_author_date']:<20} | {c['message_first_line'][:35]:<35}")

    if args.dry_run:
        print("\n[Dry Run] No Git changes made. Exiting.")
        return 0

    print("\nWARNING: This will rewrite git history in the local repository.")
    if not args.force:
        confirm = input("Are you sure you want to perform this operation? (y/N): ")
        if confirm.lower() not in ("y", "yes"):
            print("Operation aborted.")
            return 0

    # Start rebuilding commits
    current_env = os.environ.copy()
    print("\nRebuilding commits...")

    # We also need to map the parent of the first commit if it's not in the rewritten list.
    # Any parent in rewrite_map gets replaced by its new hash. Otherwise keeps its original hash.
    for i, c in enumerate(proposed_changes):
        old_hash = commits[i]
        
        # Build parent list: use rewritten parent hashes if available
        new_parents = []
        for p in c['parents']:
            if p in rewrite_map:
                new_parents.append(rewrite_map[p])
            else:
                new_parents.append(p)

        # Set environment variables for the commit info
        current_env["GIT_AUTHOR_NAME"] = c['author_name']
        current_env["GIT_AUTHOR_EMAIL"] = c['author_email']
        current_env["GIT_AUTHOR_DATE"] = c['author_date_str']
        current_env["GIT_COMMITTER_NAME"] = c['committer_name']
        current_env["GIT_COMMITTER_EMAIL"] = c['committer_email']
        current_env["GIT_COMMITTER_DATE"] = c['committer_date_str']

        # Construct commit-tree command
        cmd_args = ["commit-tree", c['tree']]
        for np in new_parents:
            cmd_args.extend(["-p", np])

        # Run commit-tree and pass the commit message via stdin
        new_commit_hash = run_git_command(cmd_args, env=current_env, input_data=c['full_message'].encode('utf-8'))
        rewrite_map[old_hash] = new_commit_hash
        print(f"Rewrote {c['old_hash']} -> {new_commit_hash[:8]}")

    # Update active branch reference to point to the new tip
    new_tip = rewrite_map[commits[-1]]
    active_branch = get_current_branch()
    
    print(f"\nUpdating branch '{active_branch}' to new commit tip {new_tip[:8]}...")
    try:
        run_git_command(["update-ref", f"refs/heads/{active_branch}", new_tip])
        print("Success! Git history updated successfully.")
        print("Run 'git reflog' if you need to recover the previous tip.")
    except Exception as e:
        print(f"Error updating branch reference: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
