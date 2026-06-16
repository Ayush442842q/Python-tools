#!/usr/bin/env python3
"""
CLI Time Tracker

A terminal-based time tracking utility. Let's you clock in/out of projects,
track tasks, view session history, and generate summary reports.

Usage:
    python tools/time_tracker.py start "My Project" --task "Coding"
    python tools/time_tracker.py status
    python tools/time_tracker.py stop
    python tools/time_tracker.py list
    python tools/time_tracker.py report
"""

import argparse
import json
import os
import sys
from datetime import datetime, timedelta

DEFAULT_DB_FILE = os.path.expanduser('~/.cli_time_tracker.json')

def load_data(db_path):
    """Loads time tracking data from the JSON file."""
    if not os.path.exists(db_path):
        return {"sessions": [], "active_session": None}
    try:
        with open(db_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Error loading data from {db_path}: {e}", file=sys.stderr)
        return {"sessions": [], "active_session": None}

def save_data(data, db_path):
    """Saves time tracking data to the JSON file."""
    try:
        temp_path = db_path + '.tmp'
        with open(temp_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        if os.path.exists(db_path):
            os.remove(db_path)
        os.rename(temp_path, db_path)
        return True
    except Exception as e:
        print(f"❌ Error saving data to {db_path}: {e}", file=sys.stderr)
        return False

def format_duration(seconds):
    """Formats a duration in seconds to H:M:S."""
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"

def start_session(args, db_path):
    """Clocks into a project and task."""
    data = load_data(db_path)
    if data.get("active_session"):
        active = data["active_session"]
        start_time = datetime.fromisoformat(active["start_time"])
        elapsed = datetime.now() - start_time
        print(f"⚠️ You are already clocked in!")
        print(f"Project: {active['project']} | Task: {active['task']}")
        print(f"Started: {active['start_time']} ({format_duration(elapsed.total_seconds())} ago)")
        return 1

    now = datetime.now()
    active_session = {
        "project": args.project,
        "task": args.task or "General",
        "start_time": now.isoformat()
    }
    data["active_session"] = active_session
    if save_data(data, db_path):
        print(f"⏱️ Clocked in to project: '{args.project}' | Task: '{active_session['task']}'")
        print(f"Start Time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
    return 0

def stop_session(args, db_path):
    """Clocks out of the current active session."""
    data = load_data(db_path)
    active = data.get("active_session")
    if not active:
        print("⚠️ No active session found. Use 'start' to clock in.")
        return 1

    now = datetime.now()
    start_time = datetime.fromisoformat(active["start_time"])
    duration = (now - start_time).total_seconds()
    
    # Calculate next ID
    sessions = data.get("sessions", [])
    next_id = max([s.get('id', 0) for s in sessions]) + 1 if sessions else 1

    new_session = {
        "id": next_id,
        "project": active["project"],
        "task": active["task"],
        "start_time": active["start_time"],
        "end_time": now.isoformat(),
        "duration_seconds": duration
    }
    
    data["sessions"].append(new_session)
    data["active_session"] = None
    
    if save_data(data, db_path):
        print(f"✅ Clocked out of project: '{new_session['project']}' | Task: '{new_session['task']}'")
        print(f"Duration: {format_duration(duration)}")
    return 0

def show_status(args, db_path):
    """Shows the status of the current active session."""
    data = load_data(db_path)
    active = data.get("active_session")
    if not active:
        print("😴 Not clocked in. Use 'start' to begin tracking time.")
        return 0

    start_time = datetime.fromisoformat(active["start_time"])
    elapsed = datetime.now() - start_time
    print("\n" + "=" * 40)
    print("           ACTIVE SESSION         ")
    print("=" * 40)
    print(f"Project   : {active['project']}")
    print(f"Task      : {active['task']}")
    print(f"Started   : {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Elapsed   : {format_duration(elapsed.total_seconds())}")
    print("=" * 40 + "\n")
    return 0

def list_sessions(args, db_path):
    """Lists recent time tracking sessions."""
    data = load_data(db_path)
    sessions = data.get("sessions", [])
    if not sessions:
        print("No logged sessions found. Use 'start' and 'stop' to track your time!")
        return 0

    limit = args.limit or len(sessions)
    recent_sessions = sessions[-limit:]

    print("\n" + "=" * 90)
    print(f"{'ID':<4} | {'PROJECT':<20} | {'TASK':<15} | {'START TIME':<19} | {'END TIME':<19} | {'DURATION'}")
    print("-" * 90)
    for s in reversed(recent_sessions):
        start = datetime.fromisoformat(s["start_time"]).strftime('%Y-%m-%d %H:%M:%S')
        end = datetime.fromisoformat(s["end_time"]).strftime('%Y-%m-%d %H:%M:%S')
        duration = format_duration(s["duration_seconds"])
        
        # Truncate strings if too long
        proj = s["project"][:20] if len(s["project"]) > 20 else s["project"]
        task = s["task"][:15] if len(s["task"]) > 15 else s["task"]
        
        print(f"{s['id']:<4} | {proj:<20} | {task:<15} | {start:<19} | {end:<19} | {duration}")
    print("=" * 90 + "\n")
    return 0

def delete_session(args, db_path):
    """Deletes a session from log by ID."""
    data = load_data(db_path)
    sessions = data.get("sessions", [])
    session_id = args.id
    
    initial_len = len(sessions)
    sessions = [s for s in sessions if s['id'] != session_id]
    
    if len(sessions) < initial_len:
        data["sessions"] = sessions
        if save_data(data, db_path):
            print(f"🗑️ Deleted session #{session_id}.")
            return 0
    else:
        print(f"❌ Session #{session_id} not found.", file=sys.stderr)
        return 1

def show_report(args, db_path):
    """Generates a summary report of time spent."""
    data = load_data(db_path)
    sessions = data.get("sessions", [])
    if not sessions:
        print("No logged sessions found.")
        return 0

    # Grouping
    group = {}
    total_seconds = 0
    
    for s in sessions:
        key = s["project"] if args.by == 'project' else s["task"]
        group[key] = group.get(key, 0) + s["duration_seconds"]
        total_seconds += s["duration_seconds"]

    if total_seconds == 0:
        print("No time logged yet.")
        return 0

    print("\n" + "=" * 55)
    print(f"        TIME TRACKING REPORT BY {args.by.upper()}")
    print("=" * 55)
    print(f"Total Time Logged: {format_duration(total_seconds)}")
    print("-" * 55)

    # Sort descending by duration
    sorted_group = sorted(group.items(), key=lambda x: x[1], reverse=True)
    max_label_len = max(len(k) for k in group.keys())
    max_label_len = max(max_label_len, 10)

    # Plot ASCII bar chart
    for label, secs in sorted_group:
        pct = (secs / total_seconds) * 100
        duration_str = format_duration(secs)
        bar_len = int(pct / 5)  # 1 block per 5%
        bar = "█" * bar_len
        print(f"{label:<{max_label_len}} | {duration_str:<9} | {bar:<20} | {pct:5.1f}%")
        
    print("=" * 55 + "\n")
    return 0

def main():
    parser = argparse.ArgumentParser(description="CLI Time Tracker - Clock in/out of projects and view productivity reports.")
    parser.add_argument('--db', default=DEFAULT_DB_FILE, help=f'Path to the database file (default: {DEFAULT_DB_FILE})')
    
    subparsers = parser.add_subparsers(dest='command', help='Subcommands')
    
    # Start
    start_parser = subparsers.add_parser('start', help='Clock in to a project')
    start_parser.add_argument('project', help='Project name')
    start_parser.add_argument('-t', '--task', default='General', help='Task name (default: General)')
    
    # Stop
    subparsers.add_parser('stop', help='Clock out of active project')
    
    # Status
    subparsers.add_parser('status', help='Show status of current session')
    
    # List
    list_parser = subparsers.add_parser('list', help='List recent sessions')
    list_parser.add_argument('-n', '--limit', type=int, default=10, help='Max sessions to show (default: 10)')
    
    # Delete
    delete_parser = subparsers.add_parser('delete', help='Delete a session')
    delete_parser.add_argument('id', type=int, help='Session ID to delete')
    
    # Report
    report_parser = subparsers.add_parser('report', help='Show summary reports')
    report_parser.add_argument('--by', choices=['project', 'task'], default='project', help='Group report by (default: project)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
        
    db_path = args.db
    
    if args.command == 'start':
        return start_session(args, db_path)
    elif args.command == 'stop':
        return stop_session(args, db_path)
    elif args.command == 'status':
        return show_status(args, db_path)
    elif args.command == 'list':
        return list_sessions(args, db_path)
    elif args.command == 'delete':
        return delete_session(args, db_path)
    elif args.command == 'report':
        return show_report(args, db_path)
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
