#!/usr/bin/env python3
"""
Terminal Kanban Board - A CLI Kanban board manager with visual column layouts.

This tool manages tasks in a simple Kanban board layout saved to a local JSON file.
It renders tasks in parallel columns (TODO, IN PROGRESS, DONE) using Unicode characters.
"""

import sys
import os
import json
import argparse
from pathlib import Path

DEFAULT_FILE = os.path.join(os.getcwd(), ".kanban.json")

COLUMNS = ["TODO", "IN PROGRESS", "DONE"]

# ANSI Colors
COLORS = {
    'green': '\033[32m',
    'yellow': '\033[33m',
    'blue': '\033[34m',
    'magenta': '\033[35m',
    'cyan': '\033[36m',
    'bold': '\033[1m',
    'red': '\033[31m',
    'reset': '\033[0m'
}

def colorize(text, color):
    """Wrap text in ANSI color escape codes if output is a terminal"""
    if sys.stdout.isatty() and color in COLORS:
        return f"{COLORS[color]}{text}{COLORS['reset']}"
    return text

def load_board(filepath):
    """Load tasks from the JSON file."""
    if not os.path.exists(filepath):
        return {"tasks": [], "next_id": 1}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(colorize(f"Error loading Kanban board file: {e}", 'red'), file=sys.stderr)
        return {"tasks": [], "next_id": 1}

def save_board(board, filepath):
    """Save tasks to the JSON file."""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(board, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(colorize(f"Error saving Kanban board file: {e}", 'red'), file=sys.stderr)
        return False

def add_task(board, title, description="", column="TODO"):
    """Add a new task to the board."""
    column = column.upper()
    if column not in COLUMNS:
        column = "TODO"
    
    task = {
        "id": board["next_id"],
        "title": title,
        "description": description,
        "column": column
    }
    board["tasks"].append(task)
    board["next_id"] += 1
    print(colorize(f"Task #{task['id']} '{title}' added to {column}.", 'green'))

def move_task(board, task_id, target_column):
    """Move a task to a different column."""
    target_column = target_column.upper()
    if target_column not in COLUMNS:
        print(colorize(f"Invalid column name. Must be one of: {', '.join(COLUMNS)}", 'red'), file=sys.stderr)
        return False
        
    for task in board["tasks"]:
        if task["id"] == task_id:
            old_col = task["column"]
            task["column"] = target_column
            print(colorize(f"Moved task #{task_id} from {old_col} to {target_column}.", 'green'))
            return True
            
    print(colorize(f"Task with ID {task_id} not found.", 'red'), file=sys.stderr)
    return False

def delete_task(board, task_id):
    """Delete a task by ID."""
    for i, task in enumerate(board["tasks"]):
        if task["id"] == task_id:
            removed = board["tasks"].pop(i)
            print(colorize(f"Deleted task #{task_id} '{removed['title']}'.", 'green'))
            return True
            
    print(colorize(f"Task with ID {task_id} not found.", 'red'), file=sys.stderr)
    return False

def wrap_text(text, width):
    """Wrap text to a specific width, returning a list of strings."""
    if not text:
        return []
    words = text.split()
    lines = []
    current_line = []
    current_length = 0
    for word in words:
        if current_length + len(word) + (1 if current_line else 0) <= width:
            current_line.append(word)
            current_length += len(word) + (1 if len(current_line) > 1 else 0)
        else:
            if current_line:
                lines.append(" ".join(current_line))
            current_line = [word]
            current_length = len(word)
    if current_line:
        lines.append(" ".join(current_line))
    return lines

def render_board(board):
    """Render the Kanban board visually in the terminal."""
    # Try reconfiguring stdout to UTF-8 on Windows to support Unicode output
    if sys.platform.startswith('win'):
        try:
            sys.stdout.reconfigure(encoding='utf-8')
        except Exception:
            pass

    # Dynamic character selection based on stdout encoding compatibility
    try:
        "┌─┐│└┘┬┼┴├┤".encode(sys.stdout.encoding or 'ascii')
        c_tl, c_hl, c_tr, c_vl, c_bl, c_br, c_tj, c_mj, c_bj, c_lj, c_rj = "┌", "─", "┐", "│", "└", "┘", "┬", "┼", "┴", "├", "┤"
    except Exception:
        c_tl, c_hl, c_tr, c_vl, c_bl, c_br, c_tj, c_mj, c_bj, c_lj, c_rj = "+", "-", "+", "|", "+", "+", "+", "+", "+", "+", "+"

    # Set column width
    col_width = 26
    
    # Separate tasks by column
    tasks_by_col = {col: [] for col in COLUMNS}
    for task in board["tasks"]:
        col = task["column"]
        if col in tasks_by_col:
            tasks_by_col[col].append(task)
            
    # Max tasks in any single column (determines row height)
    max_tasks = max(len(tasks_by_col[col]) for col in COLUMNS)
    
    # We will format tasks into cards:
    # Card format:
    # ┌────────────────────────┐
    # │ #1 Task Title          │
    # │ Task description wrapped│
    # └────────────────────────┘
    # Total card width = col_width - 2
    card_width = col_width - 2
    
    formatted_cards = {col: [] for col in COLUMNS}
    for col in COLUMNS:
        for task in tasks_by_col[col]:
            card_lines = []
            header = f"#{task['id']} {task['title']}"
            card_lines.extend(wrap_text(header, card_width))
            
            if task['description']:
                card_lines.append("-" * card_width)
                card_lines.extend(wrap_text(task['description'], card_width))
                
            # Add top, middle, bottom borders
            card = []
            card.append(c_tl + c_hl * card_width + c_tr)
            for line in card_lines:
                padding = card_width - len(line)
                card.append(c_vl + line + " " * padding + c_vl)
            card.append(c_bl + c_hl * card_width + c_br)
            formatted_cards[col].append(card)

    # Print Board Header
    border_top = c_tl + c_hl * col_width + c_tj + c_hl * col_width + c_tj + c_hl * col_width + c_tr
    border_mid = c_lj + c_hl * col_width + c_mj + c_hl * col_width + c_mj + c_hl * col_width + c_rj
    border_bottom = c_bl + c_hl * col_width + c_bj + c_hl * col_width + c_bj + c_hl * col_width + c_br
    
    print(colorize(border_top, 'blue'))
    
    # Column titles
    header_line = c_vl
    for col in COLUMNS:
        padding_left = (col_width - len(col)) // 2
        padding_right = col_width - len(col) - padding_left
        header_line += colorize(" " * padding_left + col + " " * padding_right, 'bold') + c_vl
    print(header_line)
    
    print(colorize(border_mid, 'blue'))
    
    # Render cards row by row
    # To do this, we zip formatted cards horizontally.
    # A column row displays cards from all three columns.
    # Each card consists of multiple terminal print lines.
    
    # We iterate over rows of tasks
    for row_idx in range(max_tasks):
        # We need to print each line of the cards at this row_idx
        # Let's find the max height of the cards at this row index across all columns
        col_cards = []
        for col in COLUMNS:
            if row_idx < len(formatted_cards[col]):
                col_cards.append(formatted_cards[col][row_idx])
            else:
                col_cards.append(None)
                
        max_card_lines = 0
        for card in col_cards:
            if card:
                max_card_lines = max(max_card_lines, len(card))
                
        # Now print line-by-line for this horizontal slice
        for line_idx in range(max_card_lines):
            line_str = c_vl
            for col_idx, col in enumerate(COLUMNS):
                card = col_cards[col_idx]
                if card and line_idx < len(card):
                    # Print card line with space padding to fill column width
                    content = card[line_idx]
                    line_str += content + c_vl
                else:
                    # Empty space in this column
                    line_str += " " * col_width + c_vl
            print(line_str)
            
        # Print a blank row spacing between task cards in columns
        if row_idx < max_tasks - 1:
            print(c_vl + " " * col_width + c_vl + " " * col_width + c_vl + " " * col_width + c_vl)

    # If no tasks at all
    if not board["tasks"]:
        empty_msg = "(No tasks on board)"
        padding_left = (col_width - len(empty_msg)) // 2
        padding_right = col_width - len(empty_msg) - padding_left
        empty_col = " " * padding_left + empty_msg + " " * padding_right
        print(c_vl + empty_col + c_vl + " " * col_width + c_vl + " " * col_width + c_vl)

    print(colorize(border_bottom, 'blue'))

def main():
    parser = argparse.ArgumentParser(
        description="Terminal Kanban Board - A CLI Kanban board manager with visual column layouts.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "-f", "--file", 
        default=DEFAULT_FILE, 
        help=f"Path to the kanban board JSON file (default: .kanban.json in current directory)."
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Kanban operations")
    
    # View board
    subparsers.add_parser("view", help="View the Kanban board (default action)")
    
    # Add task
    add_parser = subparsers.add_parser("add", help="Add a new task")
    add_parser.add_argument("title", help="Title of the task")
    add_parser.add_argument("-d", "--desc", default="", help="Description of the task")
    add_parser.add_argument(
        "-c", "--column", 
        choices=COLUMNS, 
        default="TODO", 
        help="Initial column for the task (default: TODO)"
    )
    
    # Move task
    move_parser = subparsers.add_parser("move", help="Move a task to a different column")
    move_parser.add_argument("id", type=int, help="ID of the task to move")
    move_parser.add_argument("column", choices=COLUMNS, help="Target column to move task into")
    
    # Delete task
    delete_parser = subparsers.add_parser("delete", help="Delete a task")
    delete_parser.add_argument("id", type=int, help="ID of the task to delete")

    args = parser.parse_args()
    
    board = load_board(args.file)
    
    if args.command == "add":
        add_task(board, args.title, args.desc, args.column)
        save_board(board, args.file)
    elif args.command == "move":
        if move_task(board, args.id, args.column):
            save_board(board, args.file)
    elif args.command == "delete":
        if delete_task(board, args.id):
            save_board(board, args.file)
    else:
        # Default action is view
        render_board(board)
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
