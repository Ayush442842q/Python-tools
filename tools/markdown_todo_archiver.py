#!/usr/bin/env python3
"""
Markdown Todo Archiver

Archive completed tasks (e.g., `- [x]`) from a Markdown file to a separate archive file
or to a completed section at the end of the file, preserving the original section structure.

Usage:
    python tools/markdown_todo_archiver.py -f TODO.md -a ARCHIVE.md

Requirements:
    - Python 3.6+
"""

import os
import sys
import re
import argparse
from datetime import datetime

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

def archive_todos(source_path, archive_path, same_file, date_format, clean_sections, use_color):
    if not os.path.exists(source_path):
        print_colored(f"Error: Source file '{source_path}' does not exist.", RED, use_color)
        return False

    try:
        with open(source_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        print_colored(f"Error reading source file: {e}", RED, use_color)
        return False

    header_pattern = re.compile(r"^(#{1,6})\s+(.+)$")
    todo_pattern = re.compile(r"^(\s*[-*+]\s+\[)([ xX])(\]\s+)(.+)$")

    new_source_lines = []
    completed_tasks = []
    
    current_section = "Uncategorized"
    current_header_lines = []
    
    # We will trace sections and only keep headers if they have remaining content.
    # To handle files accurately, we parse line-by-line.
    section_tasks = {}
    
    for line in lines:
        stripped = line.strip()
        header_match = header_pattern.match(stripped)
        
        if header_match:
            current_section = header_match.group(2).strip()
            # If the user is archiving to the same file, we skip the completed section header itself
            if same_file and current_section.lower() == "completed tasks":
                current_section = "Completed Tasks Section"
                
        todo_match = todo_pattern.match(line)
        if todo_match:
            prefix = todo_match.group(1)
            status = todo_match.group(2)
            suffix = todo_match.group(3)
            task_text = todo_match.group(4).strip()
            
            if status.lower() == 'x':
                completed_tasks.append({
                    "section": current_section if current_section != "Completed Tasks Section" else "General",
                    "text": task_text,
                    "date": datetime.now().strftime(date_format)
                })
                # Skip this line in the new source file
                continue
        
        new_source_lines.append(line)

    if not completed_tasks:
        print_colored("No completed tasks found to archive.", YELLOW, use_color)
        return True

    # If archiving to a separate file
    if not same_file:
        # Write clean source file back
        if clean_sections:
            new_source_lines = remove_empty_sections(new_source_lines)
            
        try:
            with open(source_path, "w", encoding="utf-8") as f:
                f.writelines(new_source_lines)
        except Exception as e:
            print_colored(f"Error writing to source file: {e}", RED, use_color)
            return False

        # Append to archive file
        write_to_archive_file(archive_path, completed_tasks, use_color)
    else:
        # Same file archiving
        clean_lines = remove_completed_section(new_source_lines)
        if clean_sections:
            clean_lines = remove_empty_sections(clean_lines)

        # Build the Completed Tasks section
        completed_section_lines = []
        completed_section_lines.append("\n## Completed Tasks\n\n")
        
        # Group by date or section
        by_date = {}
        for task in completed_tasks:
            by_date.setdefault(task["date"], []).append(task)
            
        for date_str, tasks in sorted(by_date.items(), reverse=True):
            completed_section_lines.append(f"### Archived on {date_str}\n")
            for t in tasks:
                completed_section_lines.append(f"- [x] {t['text']} *(from {t['section']})*\n")
            completed_section_lines.append("\n")

        # Strip trailing empty lines from clean_lines and append completed section
        while clean_lines and clean_lines[-1].strip() == "":
            clean_lines.pop()
        clean_lines.append("\n")
        clean_lines.extend(completed_section_lines)

        try:
            with open(source_path, "w", encoding="utf-8") as f:
                f.writelines(clean_lines)
        except Exception as e:
            print_colored(f"Error writing same-file updates: {e}", RED, use_color)
            return False

    print_colored(f"Successfully archived {len(completed_tasks)} task(s)!", GREEN, use_color)
    for t in completed_tasks:
        print(f"  - [x] {t['text']} (from section: '{t['section']}')")
        
    return True

def remove_completed_section(lines):
    """Remove existing '## Completed Tasks' section to rebuild it."""
    clean_lines = []
    skipping = False
    header_pattern = re.compile(r"^##\s+Completed Tasks\s*$")
    other_header_pattern = re.compile(r"^#+\s+.+$")
    
    for line in lines:
        if header_pattern.match(line.strip()):
            skipping = True
            continue
        if skipping and other_header_pattern.match(line.strip()):
            # Found a new main section header, stop skipping
            skipping = False
        if not skipping:
            clean_lines.append(line)
            
    return clean_lines

def remove_empty_sections(lines):
    """Remove headers that no longer have any tasks or content beneath them."""
    header_pattern = re.compile(r"^(#{1,6})\s+(.+)$")
    todo_pattern = re.compile(r"^\s*[-*+]\s+\[([ xX])\]\s+(.+)$")
    
    cleaned = []
    buffer = []
    has_content = False
    
    for line in lines:
        stripped = line.strip()
        if header_pattern.match(stripped):
            if buffer and (has_content or any(todo_pattern.match(l) for l in buffer)):
                cleaned.extend(buffer)
            buffer = [line]
            has_content = False
        else:
            if stripped != "":
                # If there's any non-empty non-todo text, it is general content
                if not todo_pattern.match(line):
                    has_content = True
            buffer.append(line)
            
    if buffer and (has_content or any(todo_pattern.match(l) for l in buffer)):
        cleaned.extend(buffer)
        
    return cleaned

def write_to_archive_file(archive_path, completed_tasks, use_color):
    """Write archived tasks to a separate file, grouping by date."""
    existing_content = ""
    if os.path.exists(archive_path):
        try:
            with open(archive_path, "r", encoding="utf-8") as f:
                existing_content = f.read()
        except Exception:
            pass

    # Parse existing content to integrate new tasks nicely
    # For simplicity, we append to the top under a header, or just append at the end.
    # Let's generate the markdown block
    archive_lines = []
    if not existing_content:
        archive_lines.append("# Archived Tasks\n\n")
    
    by_date = {}
    for task in completed_tasks:
        by_date.setdefault(task["date"], []).append(task)
        
    for date_str, tasks in sorted(by_date.items(), reverse=True):
        archive_lines.append(f"## Completed on {date_str}\n")
        for t in tasks:
            archive_lines.append(f"- [x] {t['text']} *(from {t['section']})*\n")
        archive_lines.append("\n")

    try:
        # Append to the top of the file after the title if it exists, or just append
        if existing_content:
            # Let's prepend after the main title
            title_match = re.match(r"^#\s+.+?\n+", existing_content)
            if title_match:
                split_idx = title_match.end()
                updated_content = existing_content[:split_idx] + "".join(archive_lines) + existing_content[split_idx:]
            else:
                updated_content = "".join(archive_lines) + "\n" + existing_content
        else:
            updated_content = "".join(archive_lines)
            
        with open(archive_path, "w", encoding="utf-8") as f:
            f.write(updated_content)
            
        print_colored(f"Archived items saved to '{archive_path}'", BLUE, use_color)
    except Exception as e:
        print_colored(f"Error writing to archive file: {e}", RED, use_color)

def main():
    parser = argparse.ArgumentParser(
        description="Archive completed tasks from a Markdown TODO list.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("-f", "--file", default="TODO.md", help="Path to source Markdown file (default: TODO.md)")
    parser.add_argument("-a", "--archive", default="ARCHIVE.md", help="Path to archive Markdown file (default: ARCHIVE.md)")
    parser.add_argument("--same-file", action="store_true", help="Archive to a 'Completed Tasks' section at the end of the same file instead of a separate file")
    parser.add_argument("--date-format", default="%Y-%m-%d", help="Date format for archiving (default: %%Y-%%m-%%d)")
    parser.add_argument("--keep-empty-sections", action="store_true", help="Do not remove sections/headers that end up empty after archiving")
    parser.add_argument("--no-color", action="store_true", help="Disable colored CLI output")

    args = parser.parse_args()
    
    use_color = not args.no_color and sys.stdout.isatty() and os.name != 'nt' or (os.name == 'nt' and 'COLORTERM' in os.environ)
    clean_sections = not args.keep_empty_sections

    success = archive_todos(
        source_path=args.file,
        archive_path=args.archive,
        same_file=args.same_file,
        date_format=args.date_format,
        clean_sections=clean_sections,
        use_color=use_color
    )
    
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
