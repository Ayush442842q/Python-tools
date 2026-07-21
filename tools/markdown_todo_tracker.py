#!/usr/bin/env python3
"""
Markdown Todo Tracker

Scan a Markdown file for task lists (e.g., `- [ ]` and `- [x]`),
calculate completion statistics, and print a progress report.

Usage:
    python tools/markdown_todo_tracker.py <markdown_file> [options]

Requirements:
    - Python 3.6+
"""

import os
import sys
import re
import argparse

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_colored(text, color, enabled=True):
    """Print text with ANSI color if enabled."""
    if enabled:
        print(f"{color}{text}{RESET}")
    else:
        print(text)

def generate_progress_bar(percentage, width=30):
    """Generate a text-based progress bar."""
    filled_len = int(round(width * percentage / 100))
    bar = "█" * filled_len + "░" * (width - filled_len)
    return bar

def analyze_markdown_todos(file_path):
    """Parse Markdown file and extract todo tasks grouped by sections."""
    if not os.path.exists(file_path):
        return None, f"File not found: {file_path}"
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        return None, f"Error reading file: {e}"

    sections = []
    current_section = "General"
    current_tasks = []
    
    # Regex to match headers: e.g., "# Header"
    header_pattern = re.compile(r"^(#{1,6})\s+(.+)$")
    # Regex to match markdown checklist tasks: e.g., "- [ ] task" or "* [x] task"
    todo_pattern = re.compile(r"^\s*[-*+]\s+\[([ xX])\]\s+(.+)$")

    for line_num, line in enumerate(lines, 1):
        line_stripped = line.strip()
        
        # Check for headers
        header_match = header_pattern.match(line_stripped)
        if header_match:
            # If we had tasks in the previous section, save them
            if current_tasks:
                sections.append({
                    "name": current_section,
                    "tasks": current_tasks
                })
            current_section = header_match.group(2)
            current_tasks = []
            continue
            
        # Check for todo checklist items
        todo_match = todo_pattern.match(line)
        if todo_match:
            status_char = todo_match.group(1)
            task_text = todo_match.group(2)
            is_completed = status_char.lower() == "x"
            current_tasks.append({
                "text": task_text,
                "completed": is_completed,
                "line": line_num
            })

    # Add the last section
    if current_tasks:
        sections.append({
            "name": current_section,
            "tasks": current_tasks
        })
        
    return sections, None

def main():
    parser = argparse.ArgumentParser(
        description="Scan a Markdown file for task lists and track progress.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("file", help="Path to the Markdown file (.md)")
    parser.add_argument("-s", "--sections", action="store_true", help="Show detailed breakdown by section")
    parser.add_argument("-p", "--pending", action="store_true", help="List all pending/incomplete tasks")
    parser.add_argument("-c", "--completed", action="store_true", help="List all completed tasks")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output in terminal")

    args = parser.parse_args()
    use_color = not args.no_color and sys.stdout.isatty() and os.name != 'nt' or (os.name == 'nt' and 'COLORTERM' in os.environ)

    sections, err = analyze_markdown_todos(args.file)
    if err:
        print_colored(f"Error: {err}", RED, use_color)
        return 1

    total_tasks = 0
    completed_tasks = 0
    all_todos = []

    for sec in sections:
        for t in sec["tasks"]:
            total_tasks += 1
            if t["completed"]:
                completed_tasks += 1
            all_todos.append((sec["name"], t))

    if total_tasks == 0:
        print_colored(f"No task checklists found in {args.file}.", YELLOW, use_color)
        print("Tasks are written in markdown as: - [ ] Task description")
        return 0

    percentage = (completed_tasks / total_tasks) * 100
    bar = generate_progress_bar(percentage)

    # Output overall summary
    print_colored(f"\n{BOLD}Task Progress for {os.path.basename(args.file)}:{RESET}", BOLD if use_color else "", use_color)
    print(f"Progress: [{bar}] {percentage:.1f}% ({completed_tasks}/{total_tasks} completed)\n")

    # Show section breakdown if requested
    if args.sections:
        print_colored(f"{BOLD}Breakdown by Section:{RESET}", BOLD if use_color else "", use_color)
        for sec in sections:
            sec_total = len(sec["tasks"])
            sec_completed = sum(1 for t in sec["tasks"] if t["completed"])
            sec_pct = (sec_completed / sec_total) * 100 if sec_total > 0 else 0
            sec_bar = generate_progress_bar(sec_pct, width=15)
            print(f"  - {sec['name']:<25} [{sec_bar}] {sec_pct:5.1f}% ({sec_completed}/{sec_total})")
        print()

    # Show pending tasks if requested
    if args.pending:
        pending_todos = [t for t in all_todos if not t[1]["completed"]]
        if pending_todos:
            print_colored(f"{BOLD}Pending Tasks ({len(pending_todos)}):{RESET}", YELLOW, use_color)
            for sec_name, task in pending_todos:
                print(f"  [ ] {task['text']} ({sec_name}, line {task['line']})")
        else:
            print_colored("No pending tasks!", GREEN, use_color)
        print()

    # Show completed tasks if requested
    if args.completed:
        completed_todos = [t for t in all_todos if t[1]["completed"]]
        if completed_todos:
            print_colored(f"{BOLD}Completed Tasks ({len(completed_todos)}):{RESET}", GREEN, use_color)
            for sec_name, task in completed_todos:
                print(f"  [x] {task['text']} ({sec_name}, line {task['line']})")
        else:
            print("No completed tasks yet.")
        print()

    return 0

if __name__ == "__main__":
    sys.exit(main())
