#!/usr/bin/env python3
"""
Git Snapshot Manager
A CLI utility to take lightweight, named snapshots of your current git workspace
(including staged changes, unstaged changes, and untracked files).
Snapshots are saved as tarball archives in '.git_snapshots/' and can be listed,
restored, deleted, exported, or imported to share workspace states with teammates.

Usage:
    python tools/git_snapshot_manager.py create [-m COMMENT]
    python tools/git_snapshot_manager.py list
    python tools/git_snapshot_manager.py restore <snapshot_id> [--force]
    python tools/git_snapshot_manager.py show <snapshot_id>
    python tools/git_snapshot_manager.py delete <snapshot_id>
    python tools/git_snapshot_manager.py export <snapshot_id> <output_file.tar.gz>
    python tools/git_snapshot_manager.py import <input_file.tar.gz>
"""

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile

# ANSI colors for styling
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
BOLD = "\033[1m"
RESET = "\033[0m"

SNAPSHOT_DIR = ".git_snapshots"


def run_git(cmd):
    """Helper to run git commands and return output."""
    try:
        res = subprocess.run(
            ["git"] + cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return res.stdout.strip()
    except subprocess.CalledProcessError as e:
        raise RuntimeError(f"Git command failed: git {' '.join(cmd)}\nError: {e.stderr.strip()}")


def is_git_repo():
    """Checks if the current working directory is a git repository."""
    try:
        run_git(["rev-parse", "--is-inside-work-tree"])
        return True
    except (RuntimeError, FileNotFoundError):
        return False


def get_git_status():
    """Gathers lists of staged, unstaged, and untracked files."""
    staged = []
    unstaged = []
    untracked = []

    # Get status porcelain
    status_lines = run_git(["status", "--porcelain=v1"]).splitlines()
    for line in status_lines:
        if len(line) < 4:
            continue
        code = line[:2]
        file_path = line[3:].strip('" ')
        
        # Staged files (A, M, D, R in column 1)
        if code[0] in "AMDR":
            staged.append(file_path)
        # Unstaged files (M, D in column 2)
        if code[1] in "MD":
            unstaged.append(file_path)
        # Untracked files (?? in columns)
        if code == "??":
            untracked.append(file_path)

    return staged, unstaged, untracked


def create_snapshot(comment):
    """Creates a workspace snapshot and stores it in the snapshots folder."""
    if not is_git_repo():
        print(f"{RED}Error: Current directory is not a Git repository.{RESET}", file=sys.stderr)
        return 1

    staged, unstaged, untracked = get_git_status()
    if not staged and not unstaged and not untracked:
        print(f"{YELLOW}No changes or untracked files detected. Snapshot skipped.{RESET}")
        return 0

    # Ensure snapshots directory exists
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    snapshot_id = f"snap_{timestamp}"
    tar_path = os.path.join(SNAPSHOT_DIR, f"{snapshot_id}.tar.gz")

    branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    commit_hash = run_git(["rev-parse", "HEAD"])

    # Create temporary directory for gathering snapshot files
    with tempfile.TemporaryDirectory() as tmp_dir:
        meta = {
            "id": snapshot_id,
            "timestamp": datetime.datetime.now().isoformat(),
            "branch": branch,
            "commit": commit_hash,
            "comment": comment or "No description provided.",
            "files": {
                "staged": staged,
                "unstaged": unstaged,
                "untracked": untracked
            }
        }

        # Write metadata
        with open(os.path.join(tmp_dir, "meta.json"), "w") as f:
            json.dump(meta, f, indent=2)

        # Generate patches for modified files
        if staged:
            staged_patch = run_git(["diff", "--cached", "--binary"])
            with open(os.path.join(tmp_dir, "staged.patch"), "w", encoding="utf-8") as f:
                f.write(staged_patch)
        
        if unstaged:
            unstaged_patch = run_git(["diff", "--binary"])
            with open(os.path.join(tmp_dir, "unstaged.patch"), "w", encoding="utf-8") as f:
                f.write(unstaged_patch)

        # Copy untracked files
        if untracked:
            untracked_dir = os.path.join(tmp_dir, "untracked")
            os.makedirs(untracked_dir, exist_ok=True)
            for file in untracked:
                if os.path.exists(file):
                    dst = os.path.join(untracked_dir, file)
                    os.makedirs(os.path.dirname(dst), exist_ok=True)
                    if os.path.isdir(file):
                        shutil.copytree(file, dst)
                    else:
                        shutil.copy2(file, dst)

        # Compress into a tarball
        with tarfile.open(tar_path, "w:gz") as tar:
            for item in os.listdir(tmp_dir):
                tar.add(os.path.join(tmp_dir, item), arcname=item)

    print(f"{GREEN}Successfully created snapshot '{snapshot_id}'{RESET}")
    print(f"  Branch: {branch}")
    print(f"  Commit: {commit_hash[:8]}")
    print(f"  Staged: {len(staged)} files, Unstaged: {len(unstaged)} files, Untracked: {len(untracked)} files")
    return 0


def list_snapshots():
    """Lists all snapshots stored in the local snapshots directory."""
    if not os.path.exists(SNAPSHOT_DIR):
        print(f"{YELLOW}No snapshots directory found. Create a snapshot first.{RESET}")
        return 0

    files = [f for f in os.listdir(SNAPSHOT_DIR) if f.endswith(".tar.gz") and f.startswith("snap_")]
    if not files:
        print(f"{YELLOW}No snapshots found.{RESET}")
        return 0

    print(f"\n{BOLD}{CYAN}{'Snapshot ID':<20} | {'Branch':<15} | {'Date/Time':<20} | {'Comment'}{RESET}")
    print("-" * 90)

    for file in sorted(files, reverse=True):
        snap_id = file[:-7]
        tar_path = os.path.join(SNAPSHOT_DIR, file)
        
        try:
            with tarfile.open(tar_path, "r:gz") as tar:
                meta_file = tar.extractfile("meta.json")
                if meta_file:
                    meta = json.loads(meta_file.read().decode("utf-8"))
                    dt = datetime.datetime.fromisoformat(meta["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
                    comment = meta["comment"]
                    if len(comment) > 30:
                        comment = comment[:27] + "..."
                    print(f"{GREEN}{snap_id:<20}{RESET} | {BLUE}{meta['branch']:<15}{RESET} | {dt:<20} | {comment}")
        except Exception:
            print(f"{RED}{snap_id:<20} | CORRUPT OR INVALID SNAPSHOT FILE{RESET}")
    print()
    return 0


def show_snapshot(snapshot_id):
    """Displays detailed information about a snapshot."""
    tar_path = os.path.join(SNAPSHOT_DIR, f"{snapshot_id}.tar.gz")
    if not os.path.exists(tar_path):
        print(f"{RED}Error: Snapshot '{snapshot_id}' not found.{RESET}", file=sys.stderr)
        return 1

    try:
        with tarfile.open(tar_path, "r:gz") as tar:
            meta_file = tar.extractfile("meta.json")
            if not meta_file:
                print(f"{RED}Error: Missing metadata inside snapshot archive.{RESET}", file=sys.stderr)
                return 1
            meta = json.loads(meta_file.read().decode("utf-8"))
    except Exception as e:
        print(f"{RED}Error reading snapshot archive: {e}{RESET}", file=sys.stderr)
        return 1

    dt = datetime.datetime.fromisoformat(meta["timestamp"]).strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n{BOLD}{CYAN}Snapshot Details:{RESET}")
    print(f"  ID:          {GREEN}{meta['id']}{RESET}")
    print(f"  Created At:  {dt}")
    print(f"  Branch:      {BLUE}{meta['branch']}{RESET}")
    print(f"  Commit HEAD: {meta['commit']}")
    print(f"  Comment:     {meta['comment']}")
    
    files = meta["files"]
    print(f"\n{BOLD}Files Included:{RESET}")
    if files.get("staged"):
        print(f"  {GREEN}[Staged]{RESET}")
        for file in files["staged"]:
            print(f"    - {file}")
    if files.get("unstaged"):
        print(f"  {YELLOW}[Unstaged]{RESET}")
        for file in files["unstaged"]:
            print(f"    - {file}")
    if files.get("untracked"):
        print(f"  {BLUE}[Untracked]{RESET}")
        for file in files["untracked"]:
            print(f"    - {file}")
    print()
    return 0


def restore_snapshot(snapshot_id, force=False):
    """Restores a snapshot to the working directory."""
    if not is_git_repo():
        print(f"{RED}Error: Current directory is not a Git repository.{RESET}", file=sys.stderr)
        return 1

    tar_path = os.path.join(SNAPSHOT_DIR, f"{snapshot_id}.tar.gz")
    if not os.path.exists(tar_path):
        print(f"{RED}Error: Snapshot '{snapshot_id}' not found.{RESET}", file=sys.stderr)
        return 1

    # Check for uncommitted changes
    staged, unstaged, untracked = get_git_status()
    if (staged or unstaged or untracked) and not force:
        print(f"{YELLOW}Warning: You have uncommitted changes in your repository.{RESET}")
        print("Restoring a snapshot could cause conflicts or overwrite your current state.")
        print("Commit, stash, or snapshot your current changes first, or run with --force to overwrite.")
        return 1

    try:
        # Extract archive in a temporary directory
        with tempfile.TemporaryDirectory() as tmp_dir:
            with tarfile.open(tar_path, "r:gz") as tar:
                tar.extractall(path=tmp_dir)

            # Read metadata
            with open(os.path.join(tmp_dir, "meta.json"), "r") as f:
                meta = json.load(f)

            # Apply staged patch
            staged_patch_path = os.path.join(tmp_dir, "staged.patch")
            if os.path.exists(staged_patch_path):
                print("Applying staged changes...")
                subprocess.run(
                    ["git", "apply", "--cached", staged_patch_path],
                    check=True
                )

            # Apply unstaged patch
            unstaged_patch_path = os.path.join(tmp_dir, "unstaged.patch")
            if os.path.exists(unstaged_patch_path):
                print("Applying unstaged changes...")
                subprocess.run(
                    ["git", "apply", unstaged_patch_path],
                    check=True
                )

            # Restore untracked files
            untracked_dir = os.path.join(tmp_dir, "untracked")
            if os.path.exists(untracked_dir):
                print("Restoring untracked files...")
                for root, _, files in os.walk(untracked_dir):
                    for file in files:
                        full_path = os.path.join(root, file)
                        rel_path = os.path.relpath(full_path, untracked_dir)
                        
                        # Copy back
                        os.makedirs(os.path.dirname(rel_path), exist_ok=True)
                        shutil.copy2(full_path, rel_path)

            print(f"\n{GREEN}Successfully restored snapshot '{snapshot_id}'!{RESET}")
            print(f"Restored to match state on branch: {meta['branch']} (commit: {meta['commit'][:8]})")
    except Exception as e:
        print(f"{RED}Error restoring snapshot: {e}{RESET}", file=sys.stderr)
        return 1

    return 0


def delete_snapshot(snapshot_id):
    """Deletes a snapshot archive from the snapshots directory."""
    tar_path = os.path.join(SNAPSHOT_DIR, f"{snapshot_id}.tar.gz")
    if not os.path.exists(tar_path):
        print(f"{RED}Error: Snapshot '{snapshot_id}' not found.{RESET}", file=sys.stderr)
        return 1
    
    os.remove(tar_path)
    print(f"{GREEN}Successfully deleted snapshot '{snapshot_id}'.{RESET}")
    return 0


def export_snapshot(snapshot_id, output_file):
    """Copies a snapshot archive to an external file path."""
    tar_path = os.path.join(SNAPSHOT_DIR, f"{snapshot_id}.tar.gz")
    if not os.path.exists(tar_path):
        print(f"{RED}Error: Snapshot '{snapshot_id}' not found.{RESET}", file=sys.stderr)
        return 1

    try:
        shutil.copy2(tar_path, output_file)
        print(f"{GREEN}Successfully exported '{snapshot_id}' to '{output_file}'{RESET}")
    except Exception as e:
        print(f"{RED}Error exporting snapshot: {e}{RESET}", file=sys.stderr)
        return 1
    return 0


def import_snapshot(input_file):
    """Imports an external snapshot archive into the local snapshots directory."""
    if not os.path.exists(input_file):
        print(f"{RED}Error: File '{input_file}' not found.{RESET}", file=sys.stderr)
        return 1

    try:
        # Validate that it is a valid snapshot tarball
        with tarfile.open(input_file, "r:gz") as tar:
            meta_file = tar.extractfile("meta.json")
            if not meta_file:
                raise ValueError("Archive is missing meta.json snapshot file.")
            meta = json.loads(meta_file.read().decode("utf-8"))
            snapshot_id = meta["id"]

        os.makedirs(SNAPSHOT_DIR, exist_ok=True)
        dest_path = os.path.join(SNAPSHOT_DIR, f"{snapshot_id}.tar.gz")
        shutil.copy2(input_file, dest_path)
        print(f"{GREEN}Successfully imported snapshot '{snapshot_id}' from '{input_file}'{RESET}")
    except Exception as e:
        print(f"{RED}Error importing snapshot: {e}{RESET}", file=sys.stderr)
        return 1
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Git Snapshot Manager - Save and restore lightweight, shareable git workspace snapshots"
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="Sub-commands")

    # Create sub-parser
    create_parser = subparsers.add_parser("create", help="Create a new snapshot")
    create_parser.add_argument("-m", "--message", help="Description comment for this snapshot")

    # List sub-parser
    subparsers.add_parser("list", help="List all snapshots")

    # Restore sub-parser
    restore_parser = subparsers.add_parser("restore", help="Restore a snapshot to the working copy")
    restore_parser.add_argument("snapshot_id", help="The ID of the snapshot to restore")
    restore_parser.add_argument("-f", "--force", action="store_true", help="Force restoration, overwriting current changes")

    # Show sub-parser
    show_parser = subparsers.add_parser("show", help="Display details of a snapshot")
    show_parser.add_argument("snapshot_id", help="The ID of the snapshot to show")

    # Delete sub-parser
    delete_parser = subparsers.add_parser("delete", help="Delete a snapshot archive")
    delete_parser.add_argument("snapshot_id", help="The ID of the snapshot to delete")

    # Export sub-parser
    export_parser = subparsers.add_parser("export", help="Export a snapshot to share it")
    export_parser.add_argument("snapshot_id", help="The ID of the snapshot to export")
    export_parser.add_argument("output_file", help="File path where the snapshot should be exported")

    # Import sub-parser
    import_parser = subparsers.add_parser("import", help="Import a snapshot archive")
    import_parser.add_argument("input_file", help="File path of the snapshot archive to import")

    args = parser.parse_args()

    if args.command == "create":
        return create_snapshot(args.message)
    elif args.command == "list":
        return list_snapshots()
    elif args.command == "restore":
        return restore_snapshot(args.snapshot_id, args.force)
    elif args.command == "show":
        return show_snapshot(args.snapshot_id)
    elif args.command == "delete":
        return delete_snapshot(args.snapshot_id)
    elif args.command == "export":
        return export_snapshot(args.snapshot_id, args.output_file)
    elif args.command == "import":
        return import_snapshot(args.input_file)

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Operation cancelled by user.{RESET}")
        sys.exit(1)
