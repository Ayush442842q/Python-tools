#!/usr/bin/env python3
"""
file_patcher - File patch applicator and diff generator

Generate unified diffs between files and apply unified patch/diff files.
This tool runs entirely on the standard library.

Usage:
    # Generate a patch
    python tools/file_patcher.py diff original.txt modified.txt -o changes.patch

    # Apply a patch
    python tools/file_patcher.py patch original.txt changes.patch [-o output.txt] [--dry-run] [--no-backup]

Example:
    python tools/file_patcher.py diff file1.txt file2.txt -o mypatch.diff
    python tools/file_patcher.py patch file1.txt mypatch.diff
"""

import argparse
import difflib
import os
import re
import sys
import shutil


def generate_diff(original_path, modified_path, output_path=None):
    """Generate a unified diff between two files."""
    try:
        with open(original_path, 'r', encoding='utf-8', errors='replace') as f:
            orig_lines = f.readlines()
        with open(modified_path, 'r', encoding='utf-8', errors='replace') as f:
            mod_lines = f.readlines()
    except Exception as e:
        print(f"Error reading source files: {e}", file=sys.stderr)
        return 1

    diff = difflib.unified_diff(
        orig_lines,
        mod_lines,
        fromfile=original_path,
        tofile=modified_path
    )

    diff_text = "".join(diff)

    if output_path:
        try:
            write_mode = 'w'
            with open(output_path, write_mode, encoding='utf-8') as f:
                f.write(diff_text)
            print(f"Diff successfully written to {output_path}")
        except Exception as e:
            print(f"Error writing output file: {e}", file=sys.stderr)
            return 1
    else:
        sys.stdout.write(diff_text)

    return 0


def parse_patch(patch_lines):
    """
    Parse a unified diff patch.
    Returns a list of hunks. Each hunk is a dict:
        {
            'old_start': int,
            'old_len': int,
            'new_start': int,
            'new_len': int,
            'hunk_lines': list of strings
        }
    """
    hunks = []
    current_hunk = None
    hunk_header_re = re.compile(r'^@@\s+-(\d+),?(\d*)\s+\+(\d+),?(\d*)\s+@@')

    for line in patch_lines:
        match = hunk_header_re.match(line)
        if match:
            if current_hunk:
                hunks.append(current_hunk)
            
            old_start = int(match.group(1))
            old_len = int(match.group(2)) if match.group(2) else 1
            new_start = int(match.group(3))
            new_len = int(match.group(4)) if match.group(4) else 1
            
            current_hunk = {
                'old_start': old_start,
                'old_len': old_len,
                'new_start': new_start,
                'new_len': new_len,
                'hunk_lines': []
            }
        elif current_hunk is not None:
            # We only care about line markings (+, -, or space/empty) inside the hunk
            if line.startswith('+') or line.startswith('-') or line.startswith(' ') or line == '\n':
                current_hunk['hunk_lines'].append(line)
            else:
                # End of hunk content or unexpected line
                pass

    if current_hunk:
        hunks.append(current_hunk)
        
    return hunks


def apply_patch(base_lines, hunks):
    """
    Apply hunks to base_lines.
    Returns (success, result_lines, error_message)
    """
    result = list(base_lines)
    offset = 0  # track how hunk positions shift as lines are added/removed

    for idx, hunk in enumerate(hunks):
        old_start = hunk['old_start'] - 1  # 0-indexed line number
        old_len = hunk['old_len']
        hunk_lines = hunk['hunk_lines']

        # Find target position in the current state of result
        target_pos = old_start + offset
        
        # Extract the expected original lines from hunk (lines starting with ' ' or '-')
        expected_orig = [l[1:] for l in hunk_lines if l.startswith(' ') or l.startswith('-')]
        # Extract replacement lines (lines starting with ' ' or '+')
        replacement = [l[1:] for l in hunk_lines if l.startswith(' ') or l.startswith('+')]

        # Check if the text matches at target position
        actual_slice = result[target_pos:target_pos + old_len]
        
        # Verify length and content
        match_success = False
        if len(actual_slice) == len(expected_orig):
            # Check for exact match
            if all(a == e for a, e in zip(actual_slice, expected_orig)):
                match_success = True

        # If not matched at target_pos, search nearby (fuzz match/offset correction)
        if not match_success:
            print(f"Warning: Exact match failed for hunk #{idx+1} at line {old_start+1}. Searching environment...", file=sys.stderr)
            found = False
            # Search within a window of 100 lines around target_pos
            for search_offset in range(1, 100):
                for direction in (-1, 1):
                    test_pos = target_pos + search_offset * direction
                    if 0 <= test_pos <= len(result) - old_len:
                        test_slice = result[test_pos:test_pos + old_len]
                        if len(test_slice) == len(expected_orig) and all(a == e for a, e in zip(test_slice, expected_orig)):
                            target_pos = test_pos
                            offset = target_pos - old_start
                            found = True
                            print(f"Hunk #{idx+1} successfully matched with offset {offset} lines.", file=sys.stderr)
                            break
                if found:
                    match_success = True
                    break
            
        if not match_success:
            return False, [], f"Hunk #{idx+1} failed to apply: original content mismatch at line {old_start+1}."

        # Replace slice
        result[target_pos:target_pos + old_len] = replacement
        
        # Update offset
        offset += len(replacement) - old_len

    return True, result, ""


def run_patch(base_path, patch_path, output_path=None, dry_run=False, no_backup=False):
    """Apply unified patch to a base file."""
    if not os.path.exists(base_path):
        print(f"Error: Base file '{base_path}' not found.", file=sys.stderr)
        return 1
    if not os.path.exists(patch_path):
        print(f"Error: Patch file '{patch_path}' not found.", file=sys.stderr)
        return 1

    try:
        with open(base_path, 'r', encoding='utf-8', errors='replace') as f:
            base_lines = f.readlines()
        with open(patch_path, 'r', encoding='utf-8') as f:
            patch_lines = f.readlines()
    except Exception as e:
        print(f"Error reading files: {e}", file=sys.stderr)
        return 1

    hunks = parse_patch(patch_lines)
    if not hunks:
        print("Error: No valid unified diff hunks found in patch file.", file=sys.stderr)
        return 1

    success, new_lines, err_msg = apply_patch(base_lines, hunks)
    if not success:
        print(f"Patch failed: {err_msg}", file=sys.stderr)
        return 1

    if dry_run:
        print("Dry run successful! Patch would apply cleanly.")
        return 0

    dest_path = output_path if output_path else base_path

    # Create backup if overwriting and backups are enabled
    if dest_path == base_path and not no_backup:
        backup_path = base_path + ".orig"
        try:
            shutil.copyfile(base_path, backup_path)
            print(f"Backup created at: {backup_path}")
        except Exception as e:
            print(f"Warning: Could not create backup: {e}", file=sys.stderr)

    try:
        write_mode = 'w'
        with open(dest_path, write_mode, encoding='utf-8') as f:
            f.writelines(new_lines)
        print(f"Patch successfully applied to {dest_path}")
    except Exception as e:
        print(f"Error writing to target file '{dest_path}': {e}", file=sys.stderr)
        return 1

    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Standalone File Patcher and Unified Diff Generator"
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="Subcommands")

    # Diff subcommand
    diff_parser = subparsers.add_parser("diff", help="Generate a unified patch between two files")
    diff_parser.add_argument("original", help="Path to original file")
    diff_parser.add_argument("modified", help="Path to modified file")
    diff_parser.add_argument("-o", "--output", help="Write diff to file instead of stdout")

    # Patch subcommand
    patch_parser = subparsers.add_parser("patch", help="Apply a unified patch file to a base file")
    patch_parser.add_argument("base_file", help="File to patch")
    patch_parser.add_argument("patch_file", help="Unified diff/patch file to apply")
    patch_parser.add_argument("-o", "--output", help="Write output to a new file (default: modifies in-place)")
    patch_parser.add_argument("--dry-run", action="store_true", help="Simulate patch application without modifying files")
    patch_parser.add_argument("--no-backup", action="store_true", help="Do not create a backup file (.orig) when overwriting in-place")

    args = parser.parse_args()

    if args.command == "diff":
        return generate_diff(args.original, args.modified, args.output)
    elif args.command == "patch":
        return run_patch(
            args.base_file,
            args.patch_file,
            output_path=args.output,
            dry_run=args.dry_run,
            no_backup=args.no_backup
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
