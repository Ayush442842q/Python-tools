#!/usr/bin/env python3
"""
Git Author Alias Resolver & Mailmap Generator
Analyzes a Git repository's history to detect similar/duplicate author names and emails,
and generates or updates a .mailmap file to consolidate developer profiles.
"""

import os
import sys
import subprocess
import argparse
from collections import Counter

def levenshtein_distance(s1, s2):
    """Calculate the Levenshtein distance between two strings."""
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)

    previous_row = range(len(s2) + 1)
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]

def get_git_authors(repo_path):
    """Extract author name and email list from git log."""
    try:
        # Run git log command to get all authors format: Name|Email
        result = subprocess.run(
            ["git", "-C", repo_path, "log", '--format=%an|%ae'],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.splitlines()
    except subprocess.CalledProcessError as e:
        print(f"Error executing git command: {e}")
        print("Make sure this is a valid Git repository and Git is installed.")
        sys.exit(1)

def find_aliases(authors_commits, threshold=2):
    """Find potential aliases based on name and email similarities."""
    unique_authors = list(authors_commits.keys())
    suggestions = []
    processed = set()

    # Sort authors by commit count descending so canonical is likely the one with more commits
    unique_authors.sort(key=lambda x: authors_commits[x], reverse=True)

    for i, auth1 in enumerate(unique_authors):
        if auth1 in processed:
            continue
        
        name1, email1 = auth1
        canon_commits = authors_commits[auth1]
        aliases_found = []

        for j in range(i + 1, len(unique_authors)):
            auth2 = unique_authors[j]
            if auth2 in processed:
                continue
                
            name2, email2 = auth2
            alias_commits = authors_commits[auth2]

            is_alias = False
            reason = ""

            # Check 1: Same email, different name
            if email1.lower() == email2.lower() and name1.lower() != name2.lower():
                is_alias = True
                reason = "Same email, different name spelling"
            
            # Check 2: Same name, different email
            elif name1.lower() == name2.lower() and email1.lower() != email2.lower():
                is_alias = True
                reason = "Same name, different email address"

            # Check 3: Similar name (low Levenshtein distance) and similar email or high commit disparity
            else:
                dist = levenshtein_distance(name1.lower(), name2.lower())
                if dist <= threshold and len(name1) > 3 and len(name2) > 3:
                    is_alias = True
                    reason = f"Highly similar names (Edit distance {dist})"
                
                # Check 4: Username portion of email is the same as the name
                else:
                    user1 = email1.split('@')[0].lower()
                    user2 = email2.split('@')[0].lower()
                    if user1 == user2 and user1 != "" and len(user1) > 3:
                        is_alias = True
                        reason = "Same local part in email address"

        if is_alias:
            aliases_found.append((auth2, reason))
            processed.add(auth2)

        if aliases_found:
            suggestions.append({
                "canonical": auth1,
                "canon_commits": canon_commits,
                "aliases": aliases_found
            })
            processed.add(auth1)

    return suggestions

def write_mailmap(repo_path, suggestions, dry_run=False):
    """Write/Update the .mailmap file in the repository root."""
    mailmap_path = os.path.join(repo_path, ".mailmap")
    existing_lines = []

    if os.path.exists(mailmap_path):
        try:
            with open(mailmap_path, 'r', encoding='utf-8') as f:
                existing_lines = f.read().splitlines()
        except Exception as e:
            print(f"Warning reading existing .mailmap: {e}")

    new_entries = []
    for sug in suggestions:
        canon_name, canon_email = sug["canonical"]
        for alias, reason in sug["aliases"]:
            alias_name, alias_email = alias
            # Format: Canonical Name <canonical@email.com> Alias Name <alias@email.com>
            # Or if names match: Canonical Name <canonical@email.com> <alias@email.com>
            if canon_name.lower() == alias_name.lower():
                entry = f"{canon_name} <{canon_email}> <{alias_email}>"
            else:
                entry = f"{canon_name} <{canon_email}> {alias_name} <{alias_email}>"
            
            # Avoid duplicating existing lines
            if not any(entry in line for line in existing_lines):
                new_entries.append(entry)

    if not new_entries:
        print("\nNo new mailmap entries to write.")
        return

    if dry_run:
        print("\n[Dry Run] New .mailmap entries that would be added:")
        for entry in new_entries:
            print(f"  {entry}")
    else:
        try:
            with open(mailmap_path, 'a', encoding='utf-8') as f:
                # Add newline if existing file doesn't end with one
                if existing_lines and not existing_lines[-1].strip() == "":
                    f.write("\n")
                
                f.write("# Generated/Updated by Git Author Alias Resolver\n")
                for entry in new_entries:
                    f.write(f"{entry}\n")
            print(f"\n✓ Successfully added {len(new_entries)} entries to {mailmap_path}")
        except Exception as e:
            print(f"Error writing to .mailmap: {e}")

def main():
    parser = argparse.ArgumentParser(description="Git Author Alias Resolver & Mailmap Generator")
    parser.add_argument("repo", nargs="?", default=".", help="Path to the Git repository (default: current directory)")
    parser.add_argument("-t", "--threshold", type=int, default=2, help="Levenshtein distance threshold for similar names (default: 2)")
    parser.add_argument("-w", "--write", action="store_true", help="Write suggestions to .mailmap file")
    parser.add_argument("-d", "--dry-run", action="store_true", help="Print what would be written to .mailmap without modifying it")
    
    args = parser.parse_args()

    # Verify repo directory
    git_dir = os.path.join(args.repo, ".git")
    if not os.path.exists(git_dir):
        print(f"Error: Directory '{args.repo}' is not a Git repository (missing .git folder).")
        sys.exit(1)

    print("Analyzing Git commit history...")
    raw_authors = get_git_authors(args.repo)
    if not raw_authors:
        print("No commits found in the repository.")
        sys.exit(0)

    # Process and count commits per author profile
    authors_commits = Counter()
    for line in raw_authors:
        if '|' in line:
            name, email = line.split('|', 1)
            authors_commits[(name.strip(), email.strip())] += 1

    print(f"Found {len(authors_commits)} unique author-email combinations across {len(raw_authors)} commits.")

    suggestions = find_aliases(authors_commits, args.threshold)

    if not suggestions:
        print("\n✓ No duplicate author profiles or aliases detected.")
        sys.exit(0)

    print("\nPotential Author Aliases & Duplicates Detected:")
    print("=" * 70)
    for sug in suggestions:
        canon_name, canon_email = sug["canonical"]
        print(f"Canonical Profile: {canon_name} <{canon_email}> ({sug['canon_commits']} commits)")
        for alias, reason in sug["aliases"]:
            alias_name, alias_email = alias
            alias_commits = authors_commits[alias]
            print(f"  ↳ Alias: {alias_name} <{alias_email}> ({alias_commits} commits)")
            print(f"    Reason: {reason}")
        print("-" * 70)

    if args.write or args.dry_run:
        write_mailmap(args.repo, suggestions, dry_run=args.dry_run)
    else:
        print("\nRun with '--write' to automatically generate/append these mappings to .mailmap")
        print("Run with '--dry-run' to review formatted mailmap entries without writing.")

if __name__ == "__main__":
    main()
