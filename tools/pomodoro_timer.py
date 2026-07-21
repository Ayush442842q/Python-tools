#!/usr/bin/env python3
"""
Pomodoro Timer - Terminal-based productivity timer

A customizable Pomodoro timer with a live progress bar, audio/bell alerts,
pause/resume capability, and optional logging of completed work sessions.

Usage:
    python tools/pomodoro_timer.py [options]

Options:
    -w, --work          Work duration in minutes (default: 25)
    -b, --short-break   Short break duration in minutes (default: 5)
    -l, --long-break    Long break duration in minutes (default: 15)
    -c, --cycles        Cycles before a long break (default: 4)
    -o, --log           Log file path to record completed sessions (default: pomodoro_log.md)
    --no-bell           Disable terminal bell alert on transition

Example:
    python tools/pomodoro_timer.py -w 50 -b 10
"""

import argparse
import sys
import time
import os
from datetime import datetime

# ANSI escape codes for styling
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
BLUE = "\033[34m"
CLEAR_LINE = "\033[K"

def log_session(log_file, duration):
    """Log a completed work session to a markdown file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"| {timestamp} | Work Session | {duration} mins | Completed |\n"
    
    file_exists = os.path.exists(log_file)
    try:
        with open(log_file, "a", encoding="utf-8") as f:
            if not file_exists or os.path.getsize(log_file) == 0:
                f.write("# Pomodoro Session Log\n\n")
                f.write("| Date & Time | Session Type | Duration | Status |\n")
                f.write("|-------------|--------------|----------|--------|\n")
            f.write(log_entry)
        return True
    except Exception as e:
        print(f"\n{RED}Error writing to log file: {e}{RESET}", file=sys.stderr)
        return False

def format_time(seconds):
    """Format seconds into MM:SS."""
    mins = seconds // 60
    secs = seconds % 60
    return f"{mins:02d}:{secs:02d}"

def run_timer(label, duration_mins, use_bell, color):
    """Run a single countdown timer with a progress bar and pause capability."""
    total_seconds = int(duration_mins * 60)
    elapsed_seconds = 0
    
    print(f"\n{BOLD}{color}Starting {label} ({duration_mins} mins)...{RESET}")
    
    width = 30  # Width of progress bar
    
    while elapsed_seconds < total_seconds:
        try:
            percent = elapsed_seconds / total_seconds
            filled = int(width * percent)
            bar = "█" * filled + "░" * (width - filled)
            
            rem = total_seconds - elapsed_seconds
            sys.stdout.write(f"\r{color}[{bar}] {int(percent * 100)}% - {format_time(rem)} remaining{RESET}{CLEAR_LINE}")
            sys.stdout.flush()
            
            time.sleep(1)
            elapsed_seconds += 1
            
        except KeyboardInterrupt:
            # Handle pause
            print(f"\n\n{YELLOW}Timer paused.{RESET}")
            print("Options: [r]esume, [s]kip session, [q]uit")
            try:
                choice = input("Choice: ").strip().lower()
            except (KeyboardInterrupt, EOFError):
                choice = 'q'
            
            if choice == 'q':
                print(f"\n{RED}Pomodoro session aborted.{RESET}")
                sys.exit(0)
            elif choice == 's':
                print(f"\n{YELLOW}Session skipped.{RESET}")
                return False
            else:
                print(f"{GREEN}Resuming {label}...{RESET}")
                # Print bar again to clean up the line
                continue
                
    # Complete
    bar = "█" * width
    sys.stdout.write(f"\r{color}[{bar}] 100% - 00:00 remaining{RESET}{CLEAR_LINE}\n")
    sys.stdout.flush()
    
    if use_bell:
        # Trigger terminal bell/audio prompt
        sys.stdout.write("\a")
        sys.stdout.flush()
        
    print(f"{GREEN}✔ {label} completed!{RESET}")
    return True

def main():
    parser = argparse.ArgumentParser(description="Terminal-based customizable Pomodoro timer")
    parser.add_argument("-w", "--work", type=float, default=25, help="Work duration in minutes (default: 25)")
    parser.add_argument("-b", "--short-break", type=float, default=5, help="Short break duration in minutes (default: 5)")
    parser.add_argument("-l", "--long-break", type=float, default=15, help="Long break duration in minutes (default: 15)")
    parser.add_argument("-c", "--cycles", type=int, default=4, help="Cycles before a long break (default: 4)")
    parser.add_argument("-o", "--log", type=str, default="pomodoro_log.md", help="Log file path (default: pomodoro_log.md)")
    parser.add_argument("--no-bell", action="store_true", help="Disable terminal beep alert")
    
    args = parser.parse_args()
    
    if args.work <= 0 or args.short_break <= 0 or args.long_break <= 0:
        print("Error: Durations must be positive numbers.", file=sys.stderr)
        return 1
        
    if args.cycles <= 0:
        print("Error: Cycles count must be greater than zero.", file=sys.stderr)
        return 1
        
    use_bell = not args.no_bell
    
    print(f"{BOLD}{GREEN}========================================={RESET}")
    print(f"{BOLD}{GREEN}      POMODORO PRODUCTIVITY TIMER        {RESET}")
    print(f"{BOLD}{GREEN}========================================={RESET}")
    print(f"Work: {args.work} mins | Short Break: {args.short_break} mins | Long Break: {args.long_break} mins")
    print(f"Cycles pattern: {args.cycles} work sessions -> Long Break")
    print(f"Logs: {args.log}")
    print("Press Ctrl+C to pause/options menu.")
    
    cycle = 1
    while True:
        # 1. Work Session
        print(f"\n{BOLD}{CYAN}--- Cycle {cycle} ---{RESET}")
        completed = run_timer("Work Session", args.work, use_bell, GREEN)
        if completed:
            log_session(args.log, args.work)
            
        # Check if we should do a long break or short break
        if cycle % args.cycles == 0:
            run_timer("Long Break", args.long_break, use_bell, BLUE)
        else:
            run_timer("Short Break", args.short_break, use_bell, YELLOW)
            
        cycle += 1
        
        # Ask if the user wants to continue
        try:
            print(f"\nPress Enter to start Cycle {cycle} (or Ctrl+C to exit)...")
            input()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{GREEN}Thanks for working! Goodbye.{RESET}")
            break
            
    return 0

if __name__ == "__main__":
    sys.exit(main())
