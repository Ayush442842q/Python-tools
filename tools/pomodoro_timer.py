#!/usr/bin/env python3
"""
Pomodoro Timer

A simple command-line Pomodoro timer.

Usage:
    python tools/pomodoro_timer.py [--work 25] [--break 5]
"""

import argparse
import sys
import time

def run_timer(minutes, label):
    seconds = minutes * 60
    while seconds > 0:
        mins, secs = divmod(seconds, 60)
        timer = f'{label}: {mins:02d}:{secs:02d}'
        print(timer, end="\r")
        time.sleep(1)
        seconds -= 1
    print(f"\n{label} session complete!")

def main():
    parser = argparse.ArgumentParser(description="Command-line Pomodoro Timer")
    parser.add_argument('--work', type=int, default=25, help='Work duration in minutes (default: 25)')
    parser.add_argument('--rest', type=int, default=5, dest="break_time", help='Break duration in minutes (default: 5)')
    args = parser.parse_args()

    print("Pomodoro timer started. Press Ctrl+C to exit.")
    try:
        while True:
            run_timer(args.work, "Work")
            run_timer(args.break_time, "Break")
    except KeyboardInterrupt:
        print("\nPomodoro timer stopped.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
