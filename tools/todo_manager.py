#!/usr/bin/env python3
"""
CLI Todo Manager

A terminal-based todo and task list manager. Lets you add, list, complete,
delete, and summarize tasks, persisting the data in a JSON file.

Usage:
    python tools/todo_manager.py add "Buy groceries" --priority High --category Shopping
    python tools/todo_manager.py list
    python tools/todo_manager.py complete 1
    python tools/todo_manager.py stats
"""

import argparse
import json
import os
import sys
from datetime import datetime

DEFAULT_DB_FILE = os.path.expanduser('~/.todo_list.json')

def load_tasks(db_path):
    """Loads tasks from the JSON database file."""
    if not os.path.exists(db_path):
        return []
    try:
        with open(db_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading tasks from {db_path}: {e}", file=sys.stderr)
        return []

def save_tasks(tasks, db_path):
    """Saves tasks to the JSON database file."""
    try:
        # Save atomically
        temp_path = db_path + '.tmp'
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(tasks, f, indent=4)
        if os.path.exists(db_path):
            os.remove(db_path)
        os.rename(temp_path, db_path)
        return True
    except Exception as e:
        print(f"Error saving tasks to {db_path}: {e}", file=sys.stderr)
        return False

def add_task(args, db_path):
    """Adds a new task to the list."""
    tasks = load_tasks(db_path)
    
    # Calculate next ID
    next_id = max([t.get('id', 0) for t in tasks]) + 1 if tasks else 1
    
    task = {
        'id': next_id,
        'description': args.description,
        'priority': args.priority,
        'category': args.category.capitalize(),
        'completed': False,
        'created_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'due_date': args.due_date if args.due_date else None,
        'completed_at': None
    }
    
    tasks.append(task)
    if save_tasks(tasks, db_path):
        print(f"✅ Task #{next_id} successfully added: '{args.description}'")

def list_tasks(args, db_path):
    """Lists tasks with optional filters and sorting."""
    tasks = load_tasks(db_path)
    
    if not tasks:
        print("No tasks found. Use the 'add' command to create your first task!")
        return

    # Filter tasks
    filtered_tasks = tasks
    if not args.all:
        filtered_tasks = [t for t in filtered_tasks if not t['completed']]
        
    if args.category:
        filtered_tasks = [t for t in filtered_tasks if t['category'].lower() == args.category.lower()]
        
    if args.priority:
        filtered_tasks = [t for t in filtered_tasks if t['priority'].lower() == args.priority.lower()]

    if not filtered_tasks:
        print("No tasks matched your filter criteria.")
        return

    # Format table output
    print("\n" + "=" * 85)
    print(f"{'ID':<4} | {'STATUS':<5} | {'PRIORITY':<8} | {'CATEGORY':<12} | {'DUE DATE':<10} | {'DESCRIPTION'}")
    print("-" * 85)
    
    for t in sorted(filtered_tasks, key=lambda x: (x['completed'], x['id'])):
        status = "☑️" if t['completed'] else "☐"
        due = t['due_date'] if t['due_date'] else "-"
        # Truncate description if too long
        desc = t['description']
        if len(desc) > 38:
            desc = desc[:35] + "..."
            
        print(f"{t['id']:<4} | {status:<5} | {t['priority']:<8} | {t['category']:<12} | {due:<10} | {desc}")
    print("=" * 85 + "\n")

def complete_task(args, db_path):
    """Marks a task as completed."""
    tasks = load_tasks(db_path)
    task_id = args.id
    
    found = False
    for t in tasks:
        if t['id'] == task_id:
            if t['completed']:
                print(f"Task #{task_id} is already completed.")
                return
            t['completed'] = True
            t['completed_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            found = True
            break
            
    if found:
        if save_tasks(tasks, db_path):
            print(f"✅ Marked task #{task_id} as completed!")
    else:
        print(f"❌ Task #{task_id} not found.", file=sys.stderr)

def delete_task(args, db_path):
    """Deletes a task from the list."""
    tasks = load_tasks(db_path)
    task_id = args.id
    
    initial_len = len(tasks)
    tasks = [t for t in tasks if t['id'] != task_id]
    
    if len(tasks) < initial_len:
        if save_tasks(tasks, db_path):
            print(f"🗑️ Deleted task #{task_id}.")
    else:
        print(f"❌ Task #{task_id} not found.", file=sys.stderr)

def show_stats(args, db_path):
    """Displays task completion metrics."""
    tasks = load_tasks(db_path)
    if not tasks:
        print("No tasks found. Add tasks to see statistics.")
        return
        
    total = len(tasks)
    completed = sum(1 for t in tasks if t['completed'])
    pending = total - completed
    pct = (completed / total) * 100 if total > 0 else 0
    
    # Priority breakdown
    high = sum(1 for t in tasks if t['priority'] == 'High' and not t['completed'])
    med = sum(1 for t in tasks if t['priority'] == 'Medium' and not t['completed'])
    low = sum(1 for t in tasks if t['priority'] == 'Low' and not t['completed'])

    print("\n" + "=" * 40)
    print("           TODO LIST STATISTICS         ")
    print("=" * 40)
    print(f"Total Tasks        : {total}")
    print(f"Completed Tasks    : {completed} ({pct:.1f}%)")
    print(f"Pending Tasks      : {pending}")
    print("-" * 40)
    print("Pending by Priority:")
    print(f"  🔴 High          : {high}")
    print(f"  🟡 Medium        : {med}")
    print(f"  🟢 Low           : {low}")
    print("=" * 40 + "\n")

def main():
    parser = argparse.ArgumentParser(description="CLI Todo Manager - Keep track of your tasks from the command line.")
    parser.add_argument('--db', default=DEFAULT_DB_FILE, help=f'Path to the JSON database file (default: {DEFAULT_DB_FILE})')
    
    subparsers = parser.add_subparsers(dest='command', help='Subcommands')
    
    # Add parser
    add_parser = subparsers.add_parser('add', help='Add a new task')
    add_parser.add_argument('description', help='Task description')
    add_parser.add_argument('-p', '--priority', choices=['Low', 'Medium', 'High'], default='Medium', help='Priority level (default: Medium)')
    add_parser.add_argument('-c', '--category', default='General', help='Category name (default: General)')
    add_parser.add_argument('-d', '--due-date', help='Due date (YYYY-MM-DD)')
    
    # List parser
    list_parser = subparsers.add_parser('list', help='List tasks')
    list_parser.add_argument('-a', '--all', action='store_true', help='Show all tasks, including completed ones')
    list_parser.add_argument('-c', '--category', help='Filter by category')
    list_parser.add_argument('-p', '--priority', help='Filter by priority')
    
    # Complete parser
    complete_parser = subparsers.add_parser('complete', help='Mark a task as completed')
    complete_parser.add_argument('id', type=int, help='The task ID to complete')
    
    # Delete parser
    delete_parser = subparsers.add_parser('delete', help='Delete a task')
    delete_parser.add_argument('id', type=int, help='The task ID to delete')
    
    # Stats parser
    subparsers.add_parser('stats', help='Show todo list metrics')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
        
    db_path = args.db
    
    if args.command == 'add':
        add_task(args, db_path)
    elif args.command == 'list':
        list_tasks(args, db_path)
    elif args.command == 'complete':
        complete_task(args, db_path)
    elif args.command == 'delete':
        delete_task(args, db_path)
    elif args.command == 'stats':
        show_stats(args, db_path)
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
