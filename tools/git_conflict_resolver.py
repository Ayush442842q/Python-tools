#!/usr/bin/env python3
"""
Git Conflict Resolver - Interactive CLI tool to find, view, and resolve Git merge conflicts.

This tool scans the current Git repository for files with merge conflicts,
highlights the conflicting sections, and allows the user to interactively choose
which version to keep (Ours, Theirs, Both, or Edit).

Usage:
    python tools/git_conflict_resolver.py [--dir DIR] [--auto-add]
"""

import argparse
import os
import re
import subprocess
import sys
import tempfile


# ANSI escape sequences for coloring
def init_colors():
    if sys.stdout.isatty() and os.name == 'nt':
        # Enable VT100 processing on Windows
        os.system('')
    
    use_color = sys.stdout.isatty()
    return {
        "green": "\033[92m" if use_color else "",
        "red": "\033[91m" if use_color else "",
        "yellow": "\033[93m" if use_color else "",
        "blue": "\033[94m" if use_color else "",
        "cyan": "\033[96m" if use_color else "",
        "bold": "\033[1m" if use_color else "",
        "reverse": "\033[7m" if use_color else "",
        "reset": "\033[0m" if use_color else ""
    }


COLORS = init_colors()


def get_conflicting_files(search_dir):
    """Retrieves a list of files with merge conflicts."""
    # First, try using git command
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=U"],
            cwd=search_dir,
            capture_output=True,
            text=True,
            check=True
        )
        files = [os.path.join(search_dir, f.strip()) for f in result.stdout.strip().split('\n') if f.strip()]
        if files:
            return files
    except (subprocess.SubprocessError, FileNotFoundError):
        pass

    # Fallback: scan files manually for conflict markers
    conflict_files = []
    conflict_marker = re.compile(r"^<<<<<<< ", re.MULTILINE)
    
    for root, _, files in os.walk(search_dir):
        # Skip git directory
        if ".git" in root or "__pycache__" in root:
            continue
        for file in files:
            file_path = os.path.join(root, file)
            # Skip large or binary files
            if os.path.getsize(file_path) > 2 * 1024 * 1024:
                continue
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    if conflict_marker.search(content):
                        conflict_files.append(file_path)
            except IOError:
                continue
    return conflict_files


class ConflictHunk:
    def __init__(self, start_line, ours, theirs, ours_label, theirs_label, raw_block):
        self.start_line = start_line
        self.ours = ours
        self.theirs = theirs
        self.ours_label = ours_label.strip() or "Ours"
        self.theirs_label = theirs_label.strip() or "Theirs"
        self.raw_block = raw_block
        self.resolved_content = None


def parse_conflicts(file_path):
    """Parses a conflicting file and returns its lines and conflict hunks."""
    with open(file_path, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    hunks = []
    new_lines = []
    
    in_conflict = False
    conflict_start_idx = -1
    separator_idx = -1
    
    ours_buf = []
    theirs_buf = []
    ours_label = ""
    theirs_label = ""
    
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("<<<<<<<"):
            in_conflict = True
            conflict_start_idx = i
            ours_label = line[7:].strip()
            ours_buf = []
            theirs_buf = []
        elif line.startswith("=======") and in_conflict:
            separator_idx = i
        elif line.startswith(">>>>>>>") and in_conflict:
            theirs_label = line[7:].strip()
            # We found the end of the conflict block
            raw_block = "".join(lines[conflict_start_idx:i+1])
            hunk = ConflictHunk(
                start_line=conflict_start_idx + 1,
                ours=ours_buf,
                theirs=theirs_buf,
                ours_label=ours_label,
                theirs_label=theirs_label,
                raw_block=raw_block
            )
            hunks.append(hunk)
            new_lines.append(hunk)  # Place the hunk object placeholder in the list
            in_conflict = False
        else:
            if in_conflict:
                if separator_idx == -1:
                    ours_buf.append(line)
                else:
                    theirs_buf.append(line)
            else:
                new_lines.append(line)
        
        # Reset separator_idx if we exit conflict
        if not in_conflict:
            separator_idx = -1
            
        i += 1
        
    return new_lines, hunks


def launch_editor(initial_content):
    """Launches the default editor with initial content and returns the edited content."""
    editor = os.environ.get('VISUAL') or os.environ.get('EDITOR') or 'notepad' if os.name == 'nt' else 'nano'
    with tempfile.NamedTemporaryFile(suffix=".tmp", delete=False, mode='w', encoding='utf-8') as tf:
        tf.write(initial_content)
        temp_name = tf.name
    
    try:
        subprocess.run([editor, temp_name], check=True)
        with open(temp_name, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        print(f"{COLORS['red']}Failed to open editor: {e}{COLORS['reset']}")
        return None
    finally:
        try:
            os.unlink(temp_name)
        except OSError:
            pass


def display_hunk(hunk, index, total):
    """Visualizes the conflict hunk on screen."""
    print(f"\n{COLORS['bold']}{COLORS['yellow']}Conflict {index}/{total} (around line {hunk.start_line}){COLORS['reset']}")
    print(f"{COLORS['cyan']}--- {hunk.ours_label} (Ours) ----------------------{COLORS['reset']}")
    for i, line in enumerate(hunk.ours):
        print(f"{COLORS['green']}+ {line.rstrip()}{COLORS['reset']}")
    print(f"{COLORS['cyan']}=== separator ==============================={COLORS['reset']}")
    for i, line in enumerate(hunk.theirs):
        print(f"{COLORS['red']}- {line.rstrip()}{COLORS['reset']}")
    print(f"{COLORS['cyan']}>>> {hunk.theirs_label} (Theirs) ------------------{COLORS['reset']}")


def resolve_hunk(hunk, index, total):
    """Interactively resolves a conflict hunk."""
    display_hunk(hunk, index, total)
    
    while True:
        prompt = (
            f"\nChoose resolution:\n"
            f"  [{COLORS['green']}1{COLORS['reset']}] Keep Ours ({hunk.ours_label})\n"
            f"  [{COLORS['red']}2{COLORS['reset']}] Keep Theirs ({hunk.theirs_label})\n"
            f"  [3] Keep Both (Ours first)\n"
            f"  [4] Keep Both (Theirs first)\n"
            f"  [5] Edit manually in editor\n"
            f"  [s] Skip / Keep markers\n"
            f"Select [1-5, s]: "
        )
        choice = input(prompt).strip().lower()
        
        if choice == '1':
            hunk.resolved_content = "".join(hunk.ours)
            return True
        elif choice == '2':
            hunk.resolved_content = "".join(hunk.theirs)
            return True
        elif choice == '3':
            hunk.resolved_content = "".join(hunk.ours + hunk.theirs)
            return True
        elif choice == '4':
            hunk.resolved_content = "".join(hunk.theirs + hunk.ours)
            return True
        elif choice == '5':
            initial = f"# Edit conflict. Lines starting with '#' will be kept as is.\n# Delete this line and resolve the conflict below.\n"
            initial += "<<<<<<< " + hunk.ours_label + "\n" + "".join(hunk.ours)
            initial += "=======\n" + "".join(hunk.theirs)
            initial += ">>>>>>> " + hunk.theirs_label + "\n"
            
            edited = launch_editor(initial)
            if edited is not None:
                # Remove comment lines
                edited_lines = [l for l in edited.splitlines(keepends=True) if not l.startswith('#')]
                hunk.resolved_content = "".join(edited_lines)
                return True
        elif choice == 's':
            hunk.resolved_content = hunk.raw_block
            return False
        else:
            print(f"{COLORS['red']}Invalid selection. Please try again.{COLORS['reset']}")


def write_resolved_file(file_path, structured_lines):
    """Reconstructs and writes the resolved contents back to the file."""
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            for item in structured_lines:
                if isinstance(item, ConflictHunk):
                    f.write(item.resolved_content)
                else:
                    f.write(item)
        return True
    except Exception as e:
        print(f"{COLORS['red']}Error writing to file {file_path}: {e}{COLORS['reset']}")
        return False


def run_git_add(file_path):
    """Stages the resolved file in Git."""
    try:
        subprocess.run(["git", "add", file_path], check=True, capture_output=True)
        print(f"{COLORS['green']}Staged {os.path.basename(file_path)} in git.{COLORS['reset']}")
    except (subprocess.SubprocessError, FileNotFoundError):
        pass


def main():
    parser = argparse.ArgumentParser(description="Interactive Git Conflict Resolver")
    parser.add_argument("--dir", default=".", help="Directory to scan for conflicts (default: current directory)")
    parser.add_argument("--auto-add", action="store_true", help="Automatically run 'git add' on resolved files")
    args = parser.parse_args()

    search_dir = os.path.abspath(args.dir)
    print(f"{COLORS['bold']}{COLORS['cyan']}Scanning for Git conflicts in: {search_dir}{COLORS['reset']}")
    
    conflicting_files = get_conflicting_files(search_dir)
    
    if not conflicting_files:
        print(f"{COLORS['green']}No merge conflicts found!{COLORS['reset']}")
        return

    print(f"{COLORS['yellow']}Found {len(conflicting_files)} files with merge conflicts:{COLORS['reset']}")
    for f in conflicting_files:
        print(f"  - {os.path.relpath(f, search_dir)}")
        
    for file_idx, file_path in enumerate(conflicting_files, 1):
        rel_path = os.path.relpath(file_path, search_dir)
        print(f"\n{COLORS['reverse']}{COLORS['bold']} Processing file {file_idx}/{len(conflicting_files)}: {rel_path} {COLORS['reset']}")
        
        structured_lines, hunks = parse_conflicts(file_path)
        
        if not hunks:
            print(f"{COLORS['yellow']}No parsable conflicts in {rel_path}. Skipping.{COLORS['reset']}")
            continue
            
        resolved_count = 0
        for hunk_idx, hunk in enumerate(hunks, 1):
            success = resolve_hunk(hunk, hunk_idx, len(hunks))
            if success:
                resolved_count += 1
                
        if resolved_count > 0:
            print(f"\nSaving resolutions to {rel_path}...")
            if write_resolved_file(file_path, structured_lines):
                print(f"{COLORS['green']}Saved successfully! ({resolved_count}/{len(hunks)} conflicts resolved){COLORS['reset']}")
                if args.auto_add or (resolved_count == len(hunks)):
                    # Ask to git add if not auto-added
                    if args.auto_add:
                        run_git_add(file_path)
                    else:
                        add_choice = input(f"Would you like to run 'git add' on this file? [Y/n]: ").strip().lower()
                        if add_choice in ('', 'y', 'yes'):
                            run_git_add(file_path)
            else:
                print(f"{COLORS['red']}Failed to save file!{COLORS['reset']}")
        else:
            print(f"{COLORS['yellow']}No modifications made to {rel_path}.{COLORS['reset']}")

    print(f"\n{COLORS['bold']}{COLORS['green']}All files processed!{COLORS['reset']}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{COLORS['yellow']}Resolution aborted by user.{COLORS['reset']}")
        sys.exit(1)
