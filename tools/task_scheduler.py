#!/usr/bin/env python3
"""
Task Scheduler Automation - Schedule and automate repetitive tasks.

This script provides a simple interface to schedule tasks (commands, scripts, 
Python functions) to run at specified intervals or specific times.
"""

import os
import sys
import time
import argparse
import subprocess
import schedule
import threading
from datetime import datetime, timedelta
from typing import Callable, List, Optional
import signal
import json
import sqlite3
from pathlib import Path

# Try to import schedule, provide helpful error if not available
try:
    import schedule
except ImportError:
    print("Error: The 'schedule' package is required. Install it with:")
    print("pip install schedule")
    sys.exit(1)

class TaskScheduler:
    """A simple task scheduler for automating repetitive tasks."""
    
    def __init__(self, db_path: str = "~/.task_scheduler.db"):
        self.db_path = os.path.expanduser(db_path)
        self.jobs = []
        self.running = False
        self.init_database()
    
    def init_database(self):
        """Initialize the SQLite database for storing scheduled tasks."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                command TEXT NOT NULL,
                schedule_type TEXT NOT NULL,
                schedule_value TEXT NOT NULL,
                enabled BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_run TIMESTAMP,
                next_run TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
    
    def add_task(self, name: str, command: str, schedule_type: str, schedule_value: str):
        """Add a new scheduled task."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO tasks (name, command, schedule_type, schedule_value)
            VALUES (?, ?, ?, ?)
        ''', (name, command, schedule_type, schedule_value))
        task_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return task_id
    
    def remove_task(self, task_id: int):
        """Remove a scheduled task."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
        conn.commit()
        conn.close()
    
    def list_tasks(self):
        """List all scheduled tasks."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT * FROM tasks ORDER BY created_at')
        tasks = cursor.fetchall()
        conn.close()
        return tasks
    
    def enable_task(self, task_id: int):
        """Enable a scheduled task."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('UPDATE tasks SET enabled = 1 WHERE id = ?', (task_id,))
        conn.commit()
        conn.close()
    
    def disable_task(self, task_id: int):
        """Disable a scheduled task."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('UPDATE tasks SET enabled = 0 WHERE id = ?', (task_id,))
        conn.commit()
        conn.close()
    
    def run_command(self, command: str):
        """Execute a command and return the result."""
        try:
            result = subprocess.run(
                command, 
                shell=True, 
                capture_output=True, 
                text=True, 
                timeout=300  # 5 minute timeout
            )
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"[{timestamp}] Executed: {command}")
            if result.stdout:
                print(f"  STDOUT: {result.stdout.strip()}")
            if result.stderr:
                print(f"  STDERR: {result.stderr.strip()}")
            print(f"  Return code: {result.returncode}")
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            print(f"[{datetime.now()}] Command timed out: {command}")
            return False
        except Exception as e:
            print(f"[{datetime.now()}] Error executing command: {e}")
            return False
    
    def setup_schedule_from_db(self):
        """Load tasks from database and set up schedule."""
        # Clear existing schedule
        schedule.clear()
        
        # Load enabled tasks from database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute('SELECT id, name, command, schedule_type, schedule_value FROM tasks WHERE enabled = 1')
        tasks = cursor.fetchall()
        conn.close()
        
        for task_id, name, command, schedule_type, schedule_value in tasks:
            job = None
            try:
                if schedule_type == "seconds":
                    job = schedule.every(int(schedule_value)).seconds.do(self.run_command, command)
                elif schedule_type == "minutes":
                    job = schedule.every(int(schedule_value)).minutes.do(self.run_command, command)
                elif schedule_type == "hours":
                    job = schedule.every(int(schedule_value)).hours.do(self.run_command, command)
                elif schedule_type == "days":
                    job = schedule.every(int(schedule_value)).days.do(self.run_command, command)
                elif schedule_type == "weekdays":
                    # schedule_value should be comma-separated weekdays (mon,tue,wed,thu,fri,sat,sun)
                    days = [d.strip().lower() for d in schedule_value.split(',')]
                    for day in days:
                        if day in ['monday', 'mon']:
                            job = schedule.every().monday.do(self.run_command, command)
                        elif day in ['tuesday', 'tue']:
                            job = schedule.every().tuesday.do(self.run_command, command)
                        elif day in ['wednesday', 'wed']:
                            job = schedule.every().wednesday.do(self.run_command, command)
                        elif day in ['thursday', 'thu']:
                            job = schedule.every().thursday.do(self.run_command, command)
                        elif day in ['friday', 'fri']:
                            job = schedule.every().friday.do(self.run_command, command)
                        elif day in ['saturday', 'sat']:
                            job = schedule.every().saturday.do(self.run_command, command)
                        elif day in ['sunday', 'sun']:
                            job = schedule.every().sunday.do(self.run_command, command)
                elif schedule_type == "daily_at":
                    # schedule_value should be in HH:MM format (24-hour)
                    job = schedule.every().day.at(schedule_value).do(self.run_command, command)
                elif schedule_type == "weekly_on":
                    # schedule_value should be "DAY HH:MM" (e.g., "monday 09:00")
                    parts = schedule_value.split()
                    if len(parts) >= 2:
                        day = parts[0].lower()
                        time_str = parts[1]
                        if day in ['monday', 'mon']:
                            job = schedule.every().monday.at(time_str).do(self.run_command, command)
                        elif day in ['tuesday', 'tue']:
                            job = schedule.every().tuesday.at(time_str).do(self.run_command, command)
                        elif day in ['wednesday', 'wed']:
                            job = schedule.every().wednesday.at(time_str).do(self.run_command, command)
                        elif day in ['thursday', 'thu']:
                            job = schedule.every().thursday.at(time_str).do(self.run_command, command)
                        elif day in ['friday', 'fri']:
                            job = schedule.every().friday.at(time_str).do(self.run_command, command)
                        elif day in ['saturday', 'sat']:
                            job = schedule.every().saturday.at(time_str).do(self.run_command, command)
                        elif day in ['sunday', 'sun']:
                            job = schedule.every().sunday.at(time_str).do(self.run_command, command)
                
                if job:
                    # Tag the job with task ID for potential management
                    job.tag(f"task_{task_id}", name)
                    
            except ValueError as e:
                print(f"Warning: Invalid schedule value for task '{name}': {e}")
            except Exception as e:
                print(f"Warning: Could not schedule task '{name}': {e}")
    
    def run_continuously(self, interval=1):
        """Run the scheduler continuously."""
        self.running = True
        print("Task scheduler started. Press Ctrl+C to stop.")
        
        def run_loop():
            while self.running:
                schedule.run_pending()
                time.sleep(interval)
        
        # Run in a separate thread to allow for clean shutdown
        scheduler_thread = threading.Thread(target=run_loop, daemon=True)
        scheduler_thread.start()
        
        try:
            while self.running:
                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopping task scheduler...")
            self.running = False
            scheduler_thread.join(timeout=5)
    
    def start(self):
        """Start the task scheduler."""
        self.setup_schedule_from_db()
        self.run_continuously()
    
    def stop(self):
        """Stop the task scheduler."""
        self.running = False

def main():
    parser = argparse.ArgumentParser(description="Task Scheduler Automation")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Add task command
    add_parser = subparsers.add_parser('add', help='Add a new scheduled task')
    add_parser.add_argument('name', help='Name of the task')
    add_parser.add_argument('command', help='Command to execute')
    add_parser.add_argument('--schedule-type', choices=['seconds', 'minutes', 'hours', 'days', 'weekdays', 'daily_at', 'weekly_on'],
                           required=True, help='Type of schedule')
    add_parser.add_argument('--schedule-value', required=True, help='Value for the schedule (e.g., 30 for every 30 minutes, or "09:00" for daily at 9 AM)')
    
    # List tasks command
    list_parser = subparsers.add_parser('list', help='List all scheduled tasks')
    
    # Remove task command
    remove_parser = subparsers.add_parser('remove', help='Remove a scheduled task')
    remove_parser.add_argument('task_id', type=int, help='ID of the task to remove')
    
    # Enable task command
    enable_parser = subparsers.add_parser('enable', help='Enable a scheduled task')
    enable_parser.add_argument('task_id', type=int, help='ID of the task to enable')
    
    # Disable task command
    disable_parser = subparsers.add_parser('disable', help='Disable a scheduled task')
    disable_parser.add_argument('task_id', type=int, help='ID of the task to disable')
    
    # Run scheduler command
    run_parser = subparsers.add_parser('run', help='Run the task scheduler')
    run_parser.add_argument('--interval', type=int, default=1, help='Check interval in seconds (default: 1)')
    
    # Test command
    test_parser = subparsers.add_parser('test', help='Test a command immediately')
    test_parser.add_argument('command', help='Command to test')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    scheduler = TaskScheduler()
    
    if args.command == 'add':
        task_id = scheduler.add_task(args.name, args.command, args.schedule_type, args.schedule_value)
        print(f"Task '{args.name}' added with ID {task_id}")
        print(f"Schedule: every {args.schedule_value} {args.schedule_type}")
    
    elif args.command == 'list':
        tasks = scheduler.list_tasks()
        if not tasks:
            print("No tasks scheduled.")
            return
        
        print("\nScheduled Tasks:")
        print("-" * 100)
        print(f"{'ID':<4} {'Name':<20} {'Command':<30} {'Schedule':<15} {'Enabled':<8} {'Created':<20}")
        print("-" * 100)
        for task in tasks:
            task_id, name, command, schedule_type, schedule_value, enabled, created_at, last_run, next_run = task
            enabled_str = "Yes" if enabled else "No"
            schedule_str = f"every {schedule_value} {schedule_type}"
            if schedule_type == 'daily_at':
                schedule_str = f"daily at {schedule_value}"
            elif schedule_type == 'weekly_on':
                schedule_str = f"weekly on {schedule_value}"
            print(f"{task_id:<4} {name:<20} {command:<30} {schedule_str:<15} {enabled_str:<8} {created_at:<20}")
    
    elif args.command == 'remove':
        scheduler.remove_task(args.task_id)
        print(f"Task {args.task_id} removed.")
    
    elif args.command == 'enable':
        scheduler.enable_task(args.task_id)
        print(f"Task {args.task_id} enabled.")
    
    elif args.command == 'disable':
        scheduler.disable_task(args.task_id)
        print(f"Task {args.task_id} disabled.")
    
    elif args.command == 'run':
        scheduler.setup_schedule_from_db()
        scheduler.run_continuously(args.interval)
    
    elif args.command == 'test':
        print(f"Testing command: {args.command}")
        success = scheduler.run_command(args.command)
        if success:
            print("Command executed successfully.")
        else:
            print("Command failed.")

if __name__ == "__main__":
    main()