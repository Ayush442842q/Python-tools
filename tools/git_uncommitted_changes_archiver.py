#!/usr/bin/env python3
"""
Git Uncommitted Changes Snapshot & Archive Utility

Captures all uncommitted state in a git repository (staged changes, unstaged changes,
and untracked files) into a standalone timestamped ZIP archive.
Provides a restore command (`--restore <archive.zip>`) to unpack and apply saved patches.

Usage:
    python git_uncommitted_changes_archiver.py [options]
    python git_uncommitted_changes_archiver.py --restore snapshot.zip
"""

import os
import sys
import subprocess
import zipfile
import json
import datetime
import argparse
from typing import Dict, Any

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def run_git_cmd(args: list, cwd: str = ".") -> str:
    """Executes a git command and returns stdout as string."""
    try:
        res = subprocess.run(["git"] + args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return res.stdout
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Git command failed: git {' '.join(args)}\nError: {e.stderr.strip()}")


def get_repo_info(repo_dir: str) -> Dict[str, Any]:
    """Gather git repository metadata."""
    branch = run_git_cmd(["rev-parse", "--abbrev-ref", "HEAD"], repo_dir).strip()
    commit_hash = run_git_cmd(["rev-parse", "HEAD"], repo_dir).strip()
    user_name = run_git_cmd(["config", "user.name"], repo_dir).strip() or "Unknown"
    user_email = run_git_cmd(["config", "user.email"], repo_dir).strip() or "Unknown"
    
    return {
        "timestamp": datetime.datetime.now().isoformat(),
        "branch": branch,
        "commit_hash": commit_hash,
        "user": f"{user_name} <{user_email}>"
    }


def get_untracked_files(repo_dir: str) -> list:
    """Returns list of relative paths for untracked files."""
    stdout = run_git_cmd(["ls-files", "--others", "--exclude-standard"], repo_dir)
    return [line.strip() for line in stdout.splitlines() if line.strip()]


def create_snapshot(repo_dir: str, output_path: str = None) -> str:
    """Creates ZIP snapshot containing git diffs and untracked files."""
    meta = get_repo_info(repo_dir)

    # Diffs
    staged_diff = run_git_cmd(["diff", "--cached"], repo_dir)
    unstaged_diff = run_git_cmd(["diff"], repo_dir)
    untracked_files = get_untracked_files(repo_dir)

    has_changes = bool(staged_diff.strip() or unstaged_diff.strip() or untracked_files)
    if not has_changes:
        print(f"{YELLOW}No uncommitted changes or untracked files found in repository.{RESET}")
        return None

    if not output_path:
        timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = f"git_snapshot_{meta['branch'].replace('/', '_')}_{timestamp_str}.zip"

    meta["staged_diff_bytes"] = len(staged_diff)
    meta["unstaged_diff_bytes"] = len(unstaged_diff)
    meta["untracked_files"] = untracked_files

    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        # Write metadata
        zipf.writestr("metadata.json", json.dumps(meta, indent=2))
        
        # Write diffs
        if staged_diff:
            zipf.writestr("staged.patch", staged_diff)
        if unstaged_diff:
            zipf.writestr("unstaged.patch", unstaged_diff)

        # Write untracked files
        for rel_file in untracked_files:
            full_path = os.path.join(repo_dir, rel_file)
            if os.path.isfile(full_path):
                zipf.write(full_path, arcname=os.path.join("untracked", rel_file))

    print(f"\n{GREEN}Snapshot successfully archived to '{output_path}'!{RESET}")
    print(f"  Branch: {meta['branch']}")
    print(f"  Head Commit: {meta['commit_hash'][:8]}")
    print(f"  Staged Diff: {len(staged_diff)} bytes")
    print(f"  Unstaged Diff: {len(unstaged_diff)} bytes")
    print(f"  Untracked Files: {len(untracked_files)}")
    print()

    return output_path


def restore_snapshot(snapshot_zip: str, repo_dir: str):
    """Restores snapshot patches and untracked files into repo_dir."""
    if not os.path.exists(snapshot_zip):
        print(f"{RED}Error: Snapshot file '{snapshot_zip}' does not exist.{RESET}")
        sys.exit(1)

    print(f"\n{CYAN}Restoring snapshot from '{snapshot_zip}'...{RESET}")

    with zipfile.ZipFile(snapshot_zip, "r") as zipf:
        namelist = zipf.namelist()

        if "metadata.json" in namelist:
            meta = json.loads(zipf.read("metadata.json").decode("utf-8"))
            print(f"  Original Branch: {meta.get('branch')}")
            print(f"  Original Timestamp: {meta.get('timestamp')}")

        # Restore untracked files
        untracked_prefix = "untracked/"
        for name in namelist:
            if name.startswith(untracked_prefix) and not name.endswith("/"):
                rel_path = name[len(untracked_prefix):]
                dest_path = os.path.join(repo_dir, rel_path)
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                with open(dest_path, "wb") as f:
                    f.write(zipf.read(name))
                print(f"  {GREEN}+ Restored untracked file:{RESET} {rel_path}")

        # Apply unstaged patch
        if "unstaged.patch" in namelist:
            patch_data = zipf.read("unstaged.patch").decode("utf-8")
            if patch_data.strip():
                tmp_patch = "_tmp_unstaged.patch"
                with open(tmp_patch, "w", encoding="utf-8") as f:
                    f.write(patch_data)
                try:
                    run_git_cmd(["apply", tmp_patch], repo_dir)
                    print(f"  {GREEN}+ Applied unstaged diff patch.{RESET}")
                finally:
                    if os.path.exists(tmp_patch):
                        os.remove(tmp_patch)

        # Apply staged patch
        if "staged.patch" in namelist:
            patch_data = zipf.read("staged.patch").decode("utf-8")
            if patch_data.strip():
                tmp_patch = "_tmp_staged.patch"
                with open(tmp_patch, "w", encoding="utf-8") as f:
                    f.write(patch_data)
                try:
                    run_git_cmd(["apply", "--cached", tmp_patch], repo_dir)
                    print(f"  {GREEN}+ Applied staged diff patch.{RESET}")
                finally:
                    if os.path.exists(tmp_patch):
                        os.remove(tmp_patch)

    print(f"\n{BOLD}{GREEN}Snapshot restoration complete!{RESET}\n")


def main():
    parser = argparse.ArgumentParser(description="Git Uncommitted Changes Snapshot & Archive Utility")
    parser.add_argument("--repo", default=".", help="Path to git repository (default: current dir)")
    parser.add_argument("--output", "-o", help="Custom output ZIP filename for archive")
    parser.add_argument("--restore", "-r", help="ZIP archive file to restore")

    args = parser.parse_args()

    repo_dir = os.path.abspath(args.repo)
    if not os.path.exists(os.path.join(repo_dir, ".git")):
        print(f"{RED}Error: '{repo_dir}' is not a valid Git repository root.{RESET}")
        sys.exit(1)

    if args.restore:
        restore_snapshot(args.restore, repo_dir)
    else:
        create_snapshot(repo_dir, args.output)


if __name__ == "__main__":
    main()
