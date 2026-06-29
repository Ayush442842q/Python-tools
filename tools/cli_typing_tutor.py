#!/usr/bin/env python3
"""
CLI Typing Tutor & Speed Tester
An interactive terminal-based typing tutor that measures your typing speed (WPM),
accuracy, and error count in real-time. Supports custom texts, difficulty levels,
and Python code snippets for programming practice.
"""

import sys
import os
import time
import argparse
import random

# ANSI Colors
COLOR_RESET = "\033[0m"
COLOR_GREEN = "\033[32m"  # Correct character
COLOR_RED = "\033[41m\033[37m"  # Incorrect character (red background, white text)
COLOR_GRAY = "\033[90m"  # Untyped character
COLOR_CYAN = "\033[36m"
COLOR_YELLOW = "\033[33m"
COLOR_BOLD = "\033[1m"

PASSAGES = {
    "easy": [
        "The quick brown fox jumps over the lazy dog.",
        "Python is an easy to learn, powerful programming language.",
        "A journey of a thousand miles begins with a single step.",
        "To be or not to be, that is the question.",
        "All that glitters is not gold."
    ],
    "medium": [
        "Programming is not about what you know; it's about what you can figure out.",
        "Beautiful is better than ugly. Explicit is better than implicit. Simple is better than complex.",
        "The best way to predict the future is to invent it. Stay hungry, stay foolish.",
        "Readability counts. Special cases aren't special enough to break the rules.",
        "Errors should never pass silently. Unless explicitly silenced."
    ],
    "hard": [
        "In computer science, recursion is a method of solving a problem where the solution depends on solutions to smaller instances of the same problem.",
        "Concurrency is about dealing with lots of things at once. Parallelism is about doing lots of things at once.",
        "A cryptographic hash function is a mathematical algorithm that maps data of arbitrary size to a bit array of a fixed size.",
        "Polymorphism is the provision of a single interface to entities of different types or the use of a single symbol to represent multiple different types."
    ],
    "code": [
        "def quicksort(arr):\n    if len(arr) <= 1: return arr\n    pivot = arr[len(arr) // 2]\n    left = [x for x in arr if x < pivot]\n    middle = [x for x in arr if x == pivot]\n    right = [x for x in arr if x > pivot]\n    return quicksort(left) + middle + quicksort(right)",
        "class Node:\n    def __init__(self, key):\n        self.left = None\n        self.right = None\n        self.val = key",
        "try:\n    with open('data.txt', 'r') as f:\n        content = f.read()\nexcept FileNotFoundError as e:\n    print(f'Error: {e}')"
    ]
}

def get_char():
    """Reads a single keypress from the user, cross-platform."""
    try:
        import msvcrt
        ch = msvcrt.getch()
        if ch in (b'\x00', b'\xe0'):  # Arrow/special key prefix
            msvcrt.getch()  # Consume the second byte
            return None
        # Handle Backspace on Windows
        if ch == b'\x08':
            return 'BACKSPACE'
        # Handle Esc on Windows
        if ch == b'\x1b':
            return 'ESC'
        # Handle Enter on Windows
        if ch in (b'\r', b'\n'):
            return '\n'
        return ch.decode('utf-8', errors='ignore')
    except ImportError:
        # Posix implementation
        import tty
        import termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        
        # Interpret special keycodes
        if ch == '\x7f' or ch == '\x08':
            return 'BACKSPACE'
        elif ch == '\x1b':
            return 'ESC'
        elif ch in ('\r', '\n'):
            return '\n'
        return ch

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def render(target, typed, elapsed_time):
    """Renders the passage with correct/incorrect coloring."""
    clear_screen()
    print(f"{COLOR_BOLD}{COLOR_CYAN}=== CLI TYPING TUTOR ==={COLOR_RESET}\n")
    print("Press " + COLOR_YELLOW + "ESC" + COLOR_RESET + " at any time to exit.\n")
    
    # Render target text with user progress colored
    output = []
    errors = 0
    correct_chars = 0
    
    for i, char in enumerate(target):
        if i < len(typed):
            if typed[i] == char:
                # Correct character
                if char == '\n':
                    output.append(COLOR_GREEN + "↵\n" + COLOR_RESET)
                else:
                    output.append(COLOR_GREEN + char + COLOR_RESET)
                correct_chars += 1
            else:
                # Incorrect character
                if char == '\n':
                    output.append(COLOR_RED + "↵" + COLOR_RESET + "\n")
                elif char == ' ':
                    output.append(COLOR_RED + "█" + COLOR_RESET) # Visual space error
                else:
                    output.append(COLOR_RED + char + COLOR_RESET)
                errors += 1
        elif i == len(typed):
            # Cursor position
            if char == '\n':
                output.append(COLOR_BOLD + "↵\n" + COLOR_RESET)
            else:
                output.append(COLOR_BOLD + "\033[4m" + char + COLOR_RESET)
        else:
            # Untyped character
            output.append(COLOR_GRAY + char + COLOR_RESET)
            
    print("".join(output))
    print("\n" + "=" * 40)
    
    # Calculate stats
    wpm = 0
    accuracy = 100.0
    
    if elapsed_time > 0:
        # Standard WPM formula: (correct chars / 5) / minutes
        wpm = int((correct_chars / 5) / (elapsed_time / 60))
        
    if len(typed) > 0:
        accuracy = (correct_chars / len(typed)) * 100
        
    print(f"Time: {elapsed_time:.1f}s | WPM: {COLOR_BOLD}{COLOR_GREEN}{wpm}{COLOR_RESET} | Accuracy: {COLOR_BOLD}{COLOR_YELLOW}{accuracy:.1f}%{COLOR_RESET} | Errors: {COLOR_RED}{errors}{COLOR_RESET}")

def run_typing_test(target_text):
    # Normalize line endings to LF
    target = target_text.replace('\r\n', '\n').strip()
    typed = []
    
    clear_screen()
    print(f"{COLOR_BOLD}{COLOR_CYAN}=== CLI TYPING TUTOR ==={COLOR_RESET}\n")
    print("Passage loaded. Press any key to start typing...")
    get_char() # Wait for first keypress to start timer
    
    start_time = time.time()
    last_render = 0
    
    while len(typed) < len(target):
        elapsed = time.time() - start_time
        
        # Throttle redraws slightly to prevent stutter
        if elapsed - last_render > 0.05:
            render(target, typed, elapsed)
            last_render = elapsed
            
        char = get_char()
        if char == 'ESC':
            print(f"\n{COLOR_YELLOW}Test aborted by user.{COLOR_RESET}")
            return False
        elif char == 'BACKSPACE':
            if typed:
                typed.pop()
        elif char is not None:
            # Accept input character
            typed.append(char)
            
    # Final stats
    elapsed = time.time() - start_time
    render(target, typed, elapsed)
    
    correct_chars = sum(1 for t, g in zip(typed, target) if t == g)
    wpm = int((correct_chars / 5) / (elapsed / 60)) if elapsed > 0 else 0
    accuracy = (correct_chars / len(target)) * 100 if target else 100
    errors = len(target) - correct_chars
    
    print("\n" + COLOR_BOLD + COLOR_GREEN + "=== TEST COMPLETED! ===" + COLOR_RESET)
    print(f"Final WPM      : {COLOR_BOLD}{COLOR_GREEN}{wpm}{COLOR_RESET}")
    print(f"Accuracy       : {COLOR_BOLD}{COLOR_YELLOW}{accuracy:.1f}%{COLOR_RESET}")
    print(f"Time Taken     : {elapsed:.1f} seconds")
    print(f"Total Errors   : {COLOR_RED}{errors}{COLOR_RESET}")
    return True

def main():
    parser = argparse.ArgumentParser(description="Interactive CLI Typing Tutor & Speed Tester")
    parser.add_argument("-f", "--file", help="Path to a text file to practice typing custom content")
    parser.add_argument("-d", "--difficulty", choices=["easy", "medium", "hard", "code"], default="medium",
                        help="Difficulty level of the preset passage (default: medium)")
    args = parser.parse_args()
    
    target_text = ""
    
    if args.file:
        if not os.path.exists(args.file):
            print(f"Error: File '{args.file}' not found.")
            sys.exit(1)
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                target_text = f.read()
        except Exception as e:
            print(f"Error reading file: {e}")
            sys.exit(1)
    else:
        # Use preset
        target_text = random.choice(PASSAGES[args.difficulty])
        
    if not target_text.strip():
        print("Error: The text passage is empty.")
        sys.exit(1)
        
    # Run the test
    try:
        run_typing_test(target_text)
    except KeyboardInterrupt:
        print(f"\n{COLOR_YELLOW}Test interrupted.{COLOR_RESET}")

if __name__ == "__main__":
    main()
