#!/usr/bin/env python3
"""
Countdown Timer

A simple command-line countdown timer.

Usage:
    python tools/countdown_timer.py --seconds 60
"""

import argparse
import sys
import time

def main():
    parser = argparse.ArgumentParser(description="Command-line Countdown Timer")
    parser.add_argument('-s', '--seconds', type=int, required=True, help='Seconds to countdown')
    args = parser.parse_args()

    seconds = args.seconds
    print(f"Starting countdown for {seconds} seconds...")
    try:
        while seconds > 0:
            mins, secs = divmod(seconds, 60)
            timer = f'{mins:02d}:{secs:02d}'
            print(timer, end="\r")
            time.sleep(1)
            seconds -= 1
        print("\n00:00 - Time is up!")
    except KeyboardInterrupt:
        print("\nCountdown stopped.")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
