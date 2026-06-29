#!/usr/bin/env python3
"""
Git Conflict Predictor
Predicts merge conflicts between two branches/commits without modifying the working tree.
"""

import argparse
import os
import subprocess
import sys
import tempfile

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"

def run_git(args, capture_output=True, check=True):
    """Run a git command and return stdout/stderr."""
    try:
        result = subprocess.run(
            ["git"] + args,
            stdout=subprocess.PIPE if capture_output else None,
            stderr=subprocess.PIPE if capture_output else None,
            text=True,
            check=check
        )
        return result.stdout.strip() if capture_output else None
    except subprocess.CalledProcessError as e:
        stderr_msg = e.stderr.strip() if e.stderr else str(e)
        raise RuntimeError(f"Git command failed: git {' '.join(args)}\nError: {stderr_msg}")
    except FileNotFoundError:
        raise RuntimeError("Git executable not found. Please ensure Git is installed and in your PATH.")

def get_current_branch():
    """Get the name of the current branch."""
    try:
        return run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    except Exception:
        return "HEAD"

def file_exists_in_commit(commit, filepath):
    """Check if a file exists in a given commit/branch."""
    try:
        run_git(["cat-file", "-e", f"{commit}:{filepath}"])
        return True
    except Exception:
        return False

def get_modified_files(base, commit):
    """Get list of files modified between base and commit."""
    output = run_git(["diff", "--name-status", base, commit])
    files = {}
    if not output:
        return files
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            status, path = parts
            files[path] = status
    return files

def predict_file_conflicts(base, branch1, branch2, filepath):
    """
    Predict conflicts for a specific file by performing a 3-way merge
    using temporary files and git merge-file.
    """
    # If the file doesn't exist in one of the branches, check for delete/modify conflicts
    exists_base = file_exists_in_commit(base, filepath)
    exists1 = file_exists_in_commit(branch1, filepath)
    exists2 = file_exists_in_commit(branch2, filepath)

    if exists_base:
        if not exists1 and not exists2:
            # Deleted in both, no conflict (both agree)
            return {"conflict": False, "type": "both_deleted", "details": "File deleted in both branches."}
        elif not exists1 and exists2:
            return {"conflict": True, "type": "delete_modify", "details": f"Conflict: Deleted in '{branch1}' but modified in '{branch2}'."}
        elif exists1 and not exists2:
            return {"conflict": True, "type": "delete_modify", "details": f"Conflict: Modified in '{branch1}' but deleted in '{branch2}'."}

    # If it is a new file in both branches
    if not exists_base and exists1 and exists2:
        # Check if contents are identical
        content1 = run_git(["show", f"{branch1}:{filepath}"])
        content2 = run_git(["show", f"{branch2}:{filepath}"])
        if content1 == content2:
            return {"conflict": False, "type": "identical_adds", "details": "Added independently with identical content."}
        else:
            return {"conflict": True, "type": "add_add", "details": f"Conflict: Added independently in both branches with different content."}

    # Standard 3-way merge logic
    try:
        base_content = run_git(["show", f"{base}:{filepath}"]) if exists_base else ""
        b1_content = run_git(["show", f"{branch1}:{filepath}"]) if exists1 else ""
        b2_content = run_git(["show", f"{branch2}:{filepath}"]) if exists2 else ""
    except Exception as e:
        return {"conflict": True, "type": "binary_or_error", "details": f"Unable to read file content: {str(e)}"}

    # Use temporary files to run git merge-file
    with tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='_base', encoding='utf-8', errors='ignore') as f_base, \
         tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='_b1', encoding='utf-8', errors='ignore') as f_b1, \
         tempfile.NamedTemporaryFile(delete=False, mode='w', suffix='_b2', encoding='utf-8', errors='ignore') as f_b2:
        
        try:
            f_base.write(base_content)
            f_b1.write(b1_content)
            f_b2.write(b2_content)
            
            f_base.close()
            f_b1.close()
            f_b2.close()

            # Run: git merge-file -p <branch1_temp> <base_temp> <branch2_temp>
            # -p sends the merged result to stdout instead of modifying files.
            # Exit code will be positive if conflicts are found, 0 if clean, negative on error.
            cmd = ["git", "merge-file", "-p", f_b1.name, f_base.name, f_b2.name]
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            # Check for conflict markers in the output
            merged_content = result.stdout
            has_conflicts = "<<<<<<<" in merged_content and "=======" in merged_content and ">>>>>>>" in merged_content
            
            if has_conflicts:
                # Count conflicts
                conflict_count = merged_content.count("<<<<<<<")
                return {
                    "conflict": True,
                    "type": "content_conflict",
                    "details": f"Content conflict: {conflict_count} conflicting block(s) detected."
                }
            return {"conflict": False, "type": "clean", "details": "Clean merge."}
            
        finally:
            # Clean up temp files
            for p in [f_base.name, f_b1.name, f_b2.name]:
                if os.path.exists(p):
                    os.unlink(p)

def main():
    parser = argparse.ArgumentParser(
        description="Predict merge conflicts between two git branches/commits without modifying the working directory."
    )
    parser.add_argument("source", help="The branch or commit to merge in (source of changes)")
    parser.add_argument("target", nargs="?", help="The target branch or commit (defaults to current branch)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show all modified files, even non-conflicting ones")
    
    args = parser.parse_args()

    # Verify we are in a git repo
    if not os.path.exists(".git") and subprocess.run(["git", "rev-parse", "--is-inside-work-tree"], stdout=subprocess.PIPE, stderr=subprocess.PIPE).returncode != 0:
        print(f"{RED}Error: Not in a git repository.{RESET}", file=sys.stderr)
        sys.exit(1)

    target = args.target if args.target else get_current_branch()
    source = args.source

    print(f"{BOLD}{BLUE}Comparing branches:{RESET}")
    print(f"  Target branch (to merge into): {BOLD}{target}{RESET}")
    print(f"  Source branch (to be merged) : {BOLD}{source}{RESET}")

    try:
        # Check if refs exist
        target_sha = run_git(["rev-parse", target])
        source_sha = run_git(["rev-parse", source])
    except Exception as e:
        print(f"{RED}Error resolving references: {e}{RESET}", file=sys.stderr)
        sys.exit(1)

    try:
        # Find merge base
        merge_base = run_git(["merge-base", target_sha, source_sha])
        print(f"  Common ancestor (merge base) : {merge_base[:8]} ({run_git(['log', '-1', '--format=%cd (%cr)', merge_base])})")
    except Exception:
        print(f"{RED}Error: Branches do not share a common ancestor. Cannot predict conflicts.{RESET}", file=sys.stderr)
        sys.exit(1)

    if merge_base == source_sha:
        print(f"\n{GREEN}Already up-to-date. Source branch is already merged into target.{RESET}")
        sys.exit(0)
    elif merge_base == target_sha:
        print(f"\n{GREEN}Fast-forward merge possible. Target is an ancestor of Source.{RESET}")
        sys.exit(0)

    # Get modifications
    print(f"\nScanning modified files...")
    target_mods = get_modified_files(merge_base, target_sha)
    source_mods = get_modified_files(merge_base, source_sha)

    # Overlapping modified files
    overlap_files = set(target_mods.keys()) & set(source_mods.keys())
    
    # Files modified only in one branch
    only_target = set(target_mods.keys()) - set(source_mods.keys())
    only_source = set(source_mods.keys()) - set(target_mods.keys())

    conflicts = []
    clean_merges = []

    for path in overlap_files:
        result = predict_file_conflicts(merge_base, target_sha, source_sha, path)
        if result["conflict"]:
            conflicts.append((path, result["details"]))
        else:
            clean_merges.append((path, result["details"]))

    # Print results
    print("\n" + "=" * 60)
    print(f"{BOLD}SUMMARY OF CONFLICTS:{RESET}")
    print("=" * 60)

    if conflicts:
        print(f"{RED}{BOLD}Found {len(conflicts)} file conflict(s):{RESET}")
        for path, details in conflicts:
            print(f"  {RED}✘ {path}{RESET}")
            print(f"    Reason: {details}")
    else:
        print(f"{GREEN}{BOLD}✔ No merge conflicts predicted!{RESET}")

    if clean_merges and (args.verbose or not conflicts):
        print(f"\n{GREEN}{BOLD}Overlapping files that will merge cleanly ({len(clean_merges)}):{RESET}")
        for path, details in clean_merges:
            print(f"  {GREEN}✔ {path}{RESET} ({details})")

    if args.verbose:
        if only_target:
            print(f"\n{BLUE}Files modified only in Target ({len(only_target)}):{RESET}")
            for path in sorted(only_target):
                print(f"  • {path} [{target_mods[path]}]")
        if only_source:
            print(f"\n{BLUE}Files modified only in Source ({len(only_source)}):{RESET}")
            for path in sorted(only_source):
                print(f"  • {path} [{source_mods[path]}]")

    print("\n" + "=" * 60)
    sys.exit(1 if conflicts else 0)

if __name__ == "__main__":
    main()
