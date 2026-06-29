#!/usr/bin/env python3
"""
CLI Eisenhower Matrix Task Planner
A zero-dependency terminal-based task organizer using the Eisenhower Matrix.
Categorizes tasks into four quadrants based on Urgency and Importance.
Supports task persistence in a local JSON file and a beautiful 2x2 color-coded grid layout.
"""

import argparse
import json
import os
import sys

# File path for database persistence
DB_FILE = "eisenhower_tasks.json"

# ANSI color codes
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"


def load_tasks():
    """Loads tasks from the local JSON file."""
    if not os.path.exists(DB_FILE):
        return []
    try:
        with open(DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading tasks database: {e}", file=sys.stderr)
        return []


def save_tasks(tasks):
    """Saves tasks to the local JSON file."""
    try:
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(tasks, f, indent=4)
    except Exception as e:
        print(f"Error saving tasks database: {e}", file=sys.stderr)


def get_next_id(tasks):
    """Generates the next unique integer task ID."""
    if not tasks:
        return 1
    return max(task['id'] for task in tasks) + 1


def add_task(title, urgent, important):
    """Adds a new task to the matrix."""
    tasks = load_tasks()
    new_task = {
        "id": get_next_id(tasks),
        "title": title,
        "urgent": urgent,
        "important": important,
        "completed": False
    }
    tasks.append(new_task)
    save_tasks(tasks)
    
    quad = get_quadrant_name(urgent, important)
    print(f"{COLOR_GREEN}Task added successfully to {COLOR_BOLD}{quad}{COLOR_RESET}!")


def delete_task(task_id):
    """Removes a task by ID."""
    tasks = load_tasks()
    new_tasks = [t for t in tasks if t['id'] != task_id]
    if len(tasks) == len(new_tasks):
        print(f"{COLOR_RED}Task with ID {task_id} not found.{COLOR_RESET}")
    else:
        save_tasks(new_tasks)
        print(f"{COLOR_GREEN}Task {task_id} deleted.{COLOR_RESET}")


def toggle_task(task_id):
    """Toggles completion status of a task by ID."""
    tasks = load_tasks()
    found = False
    for t in tasks:
        if t['id'] == task_id:
            t['completed'] = not t['completed']
            found = True
            status = "completed" if t['completed'] else "active"
            print(f"Task {task_id} marked as {COLOR_GREEN}{status}{COLOR_RESET}.")
            break
    if not found:
        print(f"{COLOR_RED}Task with ID {task_id} not found.{COLOR_RESET}")
    else:
        save_tasks(tasks)


def get_quadrant_name(urgent, important):
    """Returns the name of the quadrant."""
    if urgent and important:
        return "Q1: Urgent & Important (Do First)"
    elif not urgent and important:
        return "Q2: Not Urgent & Important (Schedule)"
    elif urgent and not important:
        return "Q3: Urgent & Not Important (Delegate)"
    else:
        return "Q4: Not Urgent & Not Important (Eliminate)"


def format_task_line(task, width):
    """Formats a single task line to fit within a column of specified width."""
    status = "[x]" if task['completed'] else "[ ]"
    prefix = f"{status} {task['id']}: "
    text = task['title']
    
    # Check if text needs truncation
    max_text_len = width - len(prefix) - 2
    if len(text) > max_text_len:
        text = text[:max_text_len - 3] + "..."
        
    line = f"{prefix}{text}"
    # Pad to exact width
    return f"{line:<{width}}"


def display_matrix():
    """Displays the 2x2 grid representing the Eisenhower Matrix."""
    tasks = load_tasks()
    
    # Categorize tasks into quadrants
    q1 = [t for t in tasks if t['urgent'] and t['important']]
    q2 = [t for t in tasks if not t['urgent'] and t['important']]
    q3 = [t for t in tasks if t['urgent'] and not t['important']]
    q4 = [t for t in tasks if not t['urgent'] and not t['important']]
    
    col_width = 38
    border_line = "+" + "-" * (col_width + 2) + "+" + "-" * (col_width + 2) + "+"
    
    # Headers
    q1_hdr = f"{COLOR_RED}{COLOR_BOLD} Q1: URGENT & IMPORTANT (Do First){COLOR_RESET}"
    q2_hdr = f"{COLOR_BLUE}{COLOR_BOLD} Q2: IMPORTANT & NOT URGENT (Plan){COLOR_RESET}"
    q3_hdr = f"{COLOR_YELLOW}{COLOR_BOLD} Q3: URGENT & NOT IMPORTANT (Delegate){COLOR_RESET}"
    q4_hdr = f"{COLOR_GREEN}{COLOR_BOLD} Q4: NOT URGENT & NOT IMPORTANT (Drop){COLOR_RESET}"
    
    # Print Quadrant 1 and 2
    print(border_line)
    print(f"| {q1_hdr:<{col_width + 10}} | {q2_hdr:<{col_width + 10}} |")
    print(border_line)
    
    # Print rows for Q1 and Q2
    max_rows_top = max(len(q1), len(q2), 1)
    for i in range(max_rows_top):
        t1_str = format_task_line(q1[i], col_width) if i < len(q1) else " " * col_width
        t2_str = format_task_line(q2[i], col_width) if i < len(q2) else " " * col_width
        print(f"|  {t1_str}  |  {t2_str}  |")
        
    # Print Quadrant 3 and 4
    print(border_line)
    print(f"| {q3_hdr:<{col_width + 10}} | {q4_hdr:<{col_width + 10}} |")
    print(border_line)
    
    # Print rows for Q3 and Q4
    max_rows_bottom = max(len(q3), len(q4), 1)
    for i in range(max_rows_bottom):
        t3_str = format_task_line(q3[i], col_width) if i < len(q3) else " " * col_width
        t4_str = format_task_line(q4[i], col_width) if i < len(q4) else " " * col_width
        print(f"|  {t3_str}  |  {t4_str}  |")
        
    print(border_line)
    print(f"\nTasks Summary: {len(tasks)} total | Q1: {len(q1)} | Q2: {len(q2)} | Q3: {len(q3)} | Q4: {len(q4)}")


def run_interactive_mode():
    """Launches the interactive menu loop."""
    while True:
        print("\n" + "=" * 40)
        print(COLOR_BOLD + COLOR_CYAN + "      EISENHOWER MATRIX TASK PLANNER" + COLOR_RESET)
        print("=" * 40)
        display_matrix()
        print("\nOptions:")
        print("  1. Add new task")
        print("  2. Toggle task completion (check/uncheck)")
        print("  3. Delete task")
        print("  4. Quit")
        
        try:
            choice = input("\nChoose an option (1-4): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break
            
        if choice == "1":
            try:
                title = input("Enter task title: ").strip()
                if not title:
                    print("Error: Task title cannot be empty.")
                    continue
                urg = input("Is it URGENT? (y/N): ").strip().lower() == 'y'
                imp = input("Is it IMPORTANT? (y/N): ").strip().lower() == 'y'
                add_task(title, urg, imp)
            except (KeyboardInterrupt, EOFError):
                print("\nAction cancelled.")
        elif choice == "2":
            try:
                tid_str = input("Enter Task ID to toggle: ").strip()
                toggle_task(int(tid_str))
            except ValueError:
                print("Error: ID must be a valid integer.")
            except (KeyboardInterrupt, EOFError):
                print("\nAction cancelled.")
        elif choice == "3":
            try:
                tid_str = input("Enter Task ID to delete: ").strip()
                delete_task(int(tid_str))
            except ValueError:
                print("Error: ID must be a valid integer.")
            except (KeyboardInterrupt, EOFError):
                print("\nAction cancelled.")
        elif choice == "4":
            print("Goodbye!")
            break
        else:
            print("Invalid option. Try again.")


def main():
    parser = argparse.ArgumentParser(description="CLI Eisenhower Matrix Task Planner")
    parser.add_argument("-l", "--list", action="store_true", help="Print the Eisenhower Matrix grid")
    parser.add_argument("-a", "--add", type=str, metavar="TITLE", help="Add a new task with given title")
    parser.add_argument("-u", "--urgent", action="store_true", help="Flag task as Urgent (used with --add)")
    parser.add_argument("-i", "--important", action="store_true", help="Flag task as Important (used with --add)")
    parser.add_argument("-t", "--toggle", type=int, metavar="ID", help="Toggle completion of task by ID")
    parser.add_argument("-d", "--delete", type=int, metavar="ID", help="Delete task by ID")

    args = parser.parse_args()

    # If no arguments are provided, launch the interactive CLI dashboard
    if len(sys.argv) == 1:
        run_interactive_mode()
    else:
        if args.add:
            add_task(args.add, args.urgent, args.important)
        elif args.toggle is not None:
            toggle_task(args.toggle)
        elif args.delete is not None:
            delete_task(args.delete)
        elif args.list:
            display_matrix()


if __name__ == "__main__":
    main()
