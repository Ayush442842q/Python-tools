#!/usr/bin/env python3
"""
CLI Directory Size Browser

An interactive command-line utility to browse directory size hierarchies, identify large folders/files,
and perform cleanups (deletion) directly through a numbered interface.

Usage:
    python cli_dir_size_browser.py [path]
"""

import os
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Tuple

def format_size(bytes_size: int) -> str:
    """Format bytes into human-readable size."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024
    return f"{bytes_size:.2f} PB"

def get_dir_contents_size(path: Path) -> Tuple[int, List[Dict]]:
    """Scan a directory and calculate size of its children."""
    total_size = 0
    items = []
    
    try:
        for entry in os.scandir(path):
            entry_path = Path(entry.path)
            item_info = {
                "name": entry.name,
                "path": entry_path,
                "is_dir": entry.is_dir(),
                "size": 0
            }
            
            if entry.is_dir():
                # Recursively get directory size
                dir_size = get_dir_size_recursive(entry_path)
                item_info["size"] = dir_size
                total_size += dir_size
            else:
                try:
                    file_size = entry.stat().st_size
                    item_info["size"] = file_size
                    total_size += file_size
                except (PermissionError, FileNotFoundError):
                    pass
            items.append(item_info)
    except PermissionError:
        print(f"\033[91mPermission Denied: Cannot read {path}\033[0m")
    except FileNotFoundError:
        print(f"\033[91mNot Found: {path}\033[0m")
        
    # Sort items by size descending
    items.sort(key=lambda x: x["size"], reverse=True)
    return total_size, items

def get_dir_size_recursive(path: Path) -> int:
    """Recursively calculate directory size."""
    total = 0
    try:
        for entry in os.scandir(path):
            if entry.is_dir(follow_symlinks=False):
                total += get_dir_size_recursive(Path(entry.path))
            else:
                try:
                    total += entry.stat(follow_symlinks=False).st_size
                except (PermissionError, FileNotFoundError):
                    pass
    except (PermissionError, FileNotFoundError):
        pass
    return total

def interactive_loop(start_path: Path):
    """Main interactive terminal loop."""
    current_path = start_path.resolve()
    
    while True:
        # Clear screen helper
        os.system('cls' if os.name == 'nt' else 'clear')
        
        print("\033[95m========================================================\033[0m")
        print("\033[1;94m CLI Directory Size Browser & Cleanup Utility\033[0m")
        print(f"\033[95m========================================================\033[0m")
        print(f"\033[1mCurrent Directory:\033[0m \033[96m{current_path}\033[0m\n")
        
        print("Scanning folder contents...")
        total_size, items = get_dir_contents_size(current_path)
        
        print(f"\033[1mTotal Directory Size:\033[0m \033[92m{format_size(total_size)}\033[0m")
        print(f"Items found: {len(items)}\n")
        
        # Display table headers
        print(f" \033[4m{'No.':<4} {'Type':<6} {'Size':<12} {'Name':<35}\033[0m")
        
        # Display menu items (paginated/limited to 25 to fit standard terminal)
        max_display = 25
        displayed_items = items[:max_display]
        
        for idx, item in enumerate(displayed_items, 1):
            itype = "\033[94mDIR\033[0m" if item["is_dir"] else "FILE"
            size_str = format_size(item["size"])
            name_str = item["name"] + ("/" if item["is_dir"] else "")
            
            # Highlight large items (e.g. > 100MB)
            if item["size"] > 100 * 1024 * 1024:
                size_str = f"\033[91m{size_str:<12}\033[0m"
            else:
                size_str = f"{size_str:<12}"
                
            print(f" [{idx:<2}] {itype:<14} {size_str} {name_str}")
            
        if len(items) > max_display:
            print(f" ... and {len(items) - max_display} more items (smaller size)")
            
        print("\n\033[1mCommands:\033[0m")
        print("  - Type a number (\033[92m1-N\033[0m) to navigate into a directory or inspect a file.")
        print("  - Type '\033[92mb\033[0m' to go back/up one level.")
        print("  - Type '\033[91md <num>\033[0m' to delete file or directory (e.g. 'd 3').")
        print("  - Type '\033[93mq\033[0m' to exit.")
        
        try:
            choice = input("\nChoose an action: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting browser...")
            break
            
        if choice == 'q':
            break
        elif choice == 'b':
            current_path = current_path.parent
        elif choice.startswith('d '):
            try:
                item_idx = int(choice.split()[1]) - 1
                if 0 <= item_idx < len(displayed_items):
                    target = displayed_items[item_idx]
                    confirm = input(f"Are you sure you want to delete {target['name']} ({format_size(target['size'])})? [y/N]: ").strip().lower()
                    if confirm == 'y':
                        if target["is_dir"]:
                            import shutil
                            shutil.rmtree(target["path"])
                        else:
                            os.remove(target["path"])
                        print("Deleted successfully. Press Enter to refresh...")
                        input()
                else:
                    print("Invalid index. Press Enter to try again.")
                    input()
            except (ValueError, IndexError) as e:
                print("Usage: d <number>. Press Enter to try again.")
                input()
            except Exception as e:
                print(f"Error deleting: {e}. Press Enter to continue.")
                input()
        else:
            try:
                item_idx = int(choice) - 1
                if 0 <= item_idx < len(displayed_items):
                    target = displayed_items[item_idx]
                    if target["is_dir"]:
                        current_path = target["path"]
                    else:
                        print(f"\nFile: {target['name']}")
                        print(f"Path: {target['path']}")
                        print(f"Size: {format_size(target['size'])}")
                        print("\nPress Enter to return...")
                        input()
                else:
                    print("Number out of range. Press Enter to try again.")
                    input()
            except ValueError:
                # Invalid command
                pass

def main():
    parser = argparse.ArgumentParser(
        description="CLI Directory Size Browser: Interactively navigate and clean large directories.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Starting directory path (default: current directory)"
    )
    args = parser.parse_args()
    
    start_path = Path(args.path)
    if not start_path.is_dir():
        print(f"Error: {start_path} is not a valid directory.")
        sys.exit(1)
        
    interactive_loop(start_path)

if __name__ == "__main__":
    main()
