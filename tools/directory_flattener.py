#!/usr/bin/env python3
"""
Directory Flattener - Recursively flattens a nested directory structure,
moving all files to a single target directory. Supports multiple collision resolution
strategies, dry-run mode, and generates an undo mapping to restore the original files.
"""

import os
import sys
import shutil
import argparse
import json
from pathlib import Path

# ANSI colors
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def print_color(text, color):
    print(f"{color}{text}{RESET}")

def generate_flat_name(relative_path, strategy, separator="_", collision_count=0):
    """
    Generates a new flat filename based on the relative path and selected strategy.
    """
    parts = relative_path.parts
    filename = parts[-1]
    
    if strategy == "rename":
        # Combine directory parts to construct a unique name
        if len(parts) > 1:
            base_name = separator.join(parts[:-1]) + separator + filename
        else:
            base_name = filename
    else:
        # Default/simple name
        base_name = filename

    if collision_count > 0:
        path_obj = Path(base_name)
        base_name = f"{path_obj.stem}{separator}{collision_count}{path_obj.suffix}"
        
    return base_name

def flatten_directory(source_dir, dest_dir, strategy, separator, dry_run, undo_file):
    source_path = Path(source_dir).resolve()
    dest_path = Path(dest_dir).resolve()

    if not source_path.exists():
        print_color(f"Error: Source directory '{source_dir}' does not exist.", RED)
        return False

    if not dry_run:
        dest_path.mkdir(parents=True, exist_ok=True)

    print_color(f"Scanning '{source_path}' recursively...", BLUE)
    
    # Collect all files
    all_files = []
    for root, _, files in os.walk(source_path):
        for file in files:
            all_files.append(Path(root) / file)

    if not all_files:
        print_color("No files found to flatten.", YELLOW)
        return True

    print(f"Found {len(all_files)} files. Applying strategy '{strategy}'...")

    operations = []  # List of tuples (src, dest)
    dest_names = set()
    undo_map = {}

    for src_file in all_files:
        if src_file.parent == dest_path:
            # Skip files already in the target directory
            continue

        try:
            rel_path = src_file.relative_to(source_path)
        except ValueError:
            # Fallback if file isn't relative to source
            rel_path = Path(src_file.name)

        collision_count = 0
        while True:
            candidate_name = generate_flat_name(rel_path, strategy, separator, collision_count)
            target_file = dest_path / candidate_name

            if strategy == "overwrite":
                break
            
            # Check if target already exists on disk or is planned to be created
            if not target_file.exists() and target_file not in dest_names:
                break
            
            if strategy == "suffix" or strategy == "rename":
                collision_count += 1
            else:
                # Should not reach here for standard strategies
                break

        dest_names.add(target_file)
        operations.append((src_file, target_file))
        
        # Save relative paths for undo map so the script remains portable
        try:
            undo_map[str(target_file.relative_to(dest_path))] = str(src_file.resolve())
        except ValueError:
            undo_map[str(target_file)] = str(src_file)

    # Perform moves
    successful_moves = 0
    for src, dest in operations:
        src_str = str(src.relative_to(source_path) if src.is_relative_to(source_path) else src)
        dest_str = str(dest)
        
        if dry_run:
            print_color(f"[DRY-RUN] Move: '{src_str}' -> '{dest_str}'", YELLOW)
            successful_moves += 1
        else:
            try:
                # Ensure destination directory exists (can happen with suffix increments)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(src), str(dest))
                print(f"Moved: '{src_str}' -> '{dest.name}'")
                successful_moves += 1
            except Exception as e:
                print_color(f"Error moving '{src}': {e}", RED)

    # Save undo script
    if undo_map and undo_file:
        undo_path = Path(undo_file).resolve()
        if dry_run:
            print_color(f"[DRY-RUN] Would save rollback map to '{undo_path}'", YELLOW)
        else:
            try:
                # We can output a JSON map alongside instructions on how to restore
                with open(undo_path, "w", encoding="utf-8") as f:
                    json.dump(undo_map, f, indent=4)
                print_color(f"\nRollback map saved to '{undo_path}'", GREEN)
                print_color(f"To restore original directory structure, run this tool with --restore '{undo_file}'", GREEN)
            except Exception as e:
                print_color(f"Error saving undo file: {e}", RED)

    status = "Dry-run completed." if dry_run else "Flattening completed."
    print_color(f"\n{status} Successfully processed {successful_moves} of {len(operations)} files.", GREEN)
    return True

def restore_directory(restore_file, dest_dir):
    restore_path = Path(restore_file).resolve()
    dest_path = Path(dest_dir).resolve()

    if not restore_path.exists():
        print_color(f"Error: Restore file '{restore_file}' does not exist.", RED)
        return False

    try:
        with open(restore_path, "r", encoding="utf-8") as f:
            undo_map = json.load(f)
    except Exception as e:
        print_color(f"Error reading restore file: {e}", RED)
        return False

    print_color(f"Starting restoration using map '{restore_path}'...", BLUE)
    restored_count = 0
    
    for flat_rel_name, orig_abs_path in undo_map.items():
        flat_file = dest_path / flat_rel_name
        orig_file = Path(orig_abs_path)

        if not flat_file.exists():
            print_color(f"Warning: Flat file '{flat_file}' not found. Skipping.", YELLOW)
            continue

        try:
            # Create original parent directories
            orig_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(flat_file), str(orig_file))
            print(f"Restored: '{flat_rel_name}' -> '{orig_file}'")
            restored_count += 1
        except Exception as e:
            print_color(f"Error restoring '{flat_file}': {e}", RED)

    print_color(f"\nRestoration completed. Restored {restored_count} of {len(undo_map)} files.", GREEN)
    
    # Try cleaning up restore file
    try:
        os.remove(restore_path)
        print("Removed rollback configuration file.")
    except Exception:
        pass
        
    return True

def main():
    parser = argparse.ArgumentParser(
        description="Directory Flattener - Recursively moves all files from subdirectories to a single destination directory."
    )
    
    # Standard mode options
    parser.add_argument("-s", "--source", default=".", help="Source directory containing nested files (default: current directory)")
    parser.add_argument("-d", "--dest", help="Destination directory to copy/move files to (required unless restoring)")
    parser.add_argument(
        "--strategy",
        choices=["rename", "suffix", "overwrite"],
        default="rename",
        help="Strategy to resolve name collisions: "
             "'rename' prefixes folders to the filename (e.g. dir_subdir_file.txt); "
             "'suffix' appends a numerical suffix (e.g. file_1.txt); "
             "'overwrite' replaces duplicates. (default: rename)"
    )
    parser.add_argument("--sep", default="_", help="Separator characters for renaming strategies (default: '_')")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without executing moves")
    parser.add_argument("--undo-file", default="flatten_rollback.json", help="Path to write the rollback layout mapping (default: flatten_rollback.json)")
    
    # Restore mode options
    parser.add_argument("--restore", help="Path to rollback layout mapping JSON to restore files to their original directories")

    args = parser.parse_args()

    # ANSI support on Windows
    if sys.platform == "win32":
        os.system("")

    if args.restore:
        # Restore mode requires destination directory to locate the flat files
        dest_dir = args.dest if args.dest else "."
        restore_directory(args.restore, dest_dir)
    else:
        if not args.dest:
            parser.error("the following arguments are required: -d/--dest (or --restore)")
        flatten_directory(args.source, args.dest, args.strategy, args.sep, args.dry_run, args.undo_file)

if __name__ == "__main__":
    main()
