#!/usr/bin/env python3
"""
Log Colorizer & Highlight Tool
Reads logs from stdin or a file and colorizes standard log levels and custom regex patterns.
"""

import argparse
import re
import sys
import time
import os

# ANSI escape codes for colors
RESET = "\033[0m"
BOLD = "\033[1m"

# Text Colors
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"

# Background Colors
BG_RED = "\033[41m"
BG_YELLOW = "\033[43m"
BG_BLUE = "\033[44m"

# Default pattern highlighting color (cyan background with black text or just bold yellow text)
HIGHLIGHT_COLOR = f"\033[1;30;103m" # Bold black text on bright yellow background

# Severity mapping to colors
LEVEL_STYLES = {
    'DEBUG': CYAN,
    'INFO': GREEN,
    'NOTICE': BLUE,
    'WARN': YELLOW,
    'WARNING': YELLOW,
    'ERROR': RED,
    'ERR': RED,
    'CRITICAL': BOLD + RED,
    'FATAL': BOLD + BG_RED + WHITE,
    'SEVERE': BOLD + RED,
    'SUCCESS': BOLD + GREEN,
}

# Compile standard log level regexes
# Looks for brackets, colons, or boundaries around keywords, e.g. [INFO], INFO:, [ERROR]
LEVEL_PATTERNS = [
    (re.compile(r'\b(' + '|'.join(LEVEL_STYLES.keys()) + r')\b', re.IGNORECASE), None)
]

def get_styled_level(match):
    word = match.group(1)
    upper_word = word.upper()
    style = LEVEL_STYLES.get(upper_word, RESET)
    return f"{style}{word}{RESET}"

def colorize_line(line, custom_regex=None, ignore_case=False):
    # Strip newline for processing, but we'll add it back
    line_content = line.rstrip('\r\n')
    
    # 1. Apply level highlighting
    for pattern, _ in LEVEL_PATTERNS:
        line_content = pattern.sub(get_styled_level, line_content)
        
    # 2. Apply custom pattern highlighting
    if custom_regex:
        flags = re.IGNORECASE if ignore_case else 0
        try:
            compiled_custom = re.compile(f"({custom_regex})", flags)
            line_content = compiled_custom.sub(lambda m: f"{HIGHLIGHT_COLOR}{m.group(1)}{RESET}", line_content)
        except re.error as e:
            # If invalid regex, treat as literal text
            escaped = re.escape(custom_regex)
            compiled_custom = re.compile(f"({escaped})", flags)
            line_content = compiled_custom.sub(lambda m: f"{HIGHLIGHT_COLOR}{m.group(1)}{RESET}", line_content)
            
    return line_content

def process_stream(stream, custom_pattern=None, ignore_case=False):
    try:
        for line in stream:
            colored = colorize_line(line, custom_pattern, ignore_case)
            print(colored)
            sys.stdout.flush()
    except KeyboardInterrupt:
        pass

def follow_file(file_path, custom_pattern=None, ignore_case=False):
    """Implement tail -f logic with colorizing."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            # Go to the end of the file
            f.seek(0, os.SEEK_END)
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.1)
                    continue
                colored = colorize_line(line, custom_pattern, ignore_case)
                print(colored)
                sys.stdout.flush()
    except KeyboardInterrupt:
        print("\nStopping log tail.")
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(description='Colorize and highlight terminal log lines.')
    parser.add_argument('file', nargs='?', default=None,
                        help='Log file to read (reads from stdin if not specified)')
    parser.add_argument('-p', '--pattern', type=str, default=None,
                        help='Custom regex pattern or keyword to highlight')
    parser.add_argument('-i', '--ignore-case', action='store_true',
                        help='Ignore case for custom pattern matching')
    parser.add_argument('-f', '--follow', action='store_true',
                        help='Follow the file (like tail -f, only valid when file is specified)')

    # Check if stdout is a TTY (if not, we might want to disable colors, but usually log colorizers are run to be seen)
    # We will support a flag to disable colors if needed, but default to True for this tool
    parser.add_argument('--no-color', action='store_true', help='Disable all ANSI color codes')

    args = parser.parse_args()

    if args.no_color:
        global RESET, BOLD, RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE, BG_RED, BG_YELLOW, BG_BLUE, HIGHLIGHT_COLOR, LEVEL_STYLES
        RESET = BOLD = RED = GREEN = YELLOW = BLUE = MAGENTA = CYAN = WHITE = BG_RED = BG_YELLOW = BG_BLUE = HIGHLIGHT_COLOR = ""
        LEVEL_STYLES = {k: "" for k in LEVEL_STYLES}

    if args.file:
        if not os.path.exists(args.file):
            print(f"Error: File '{args.file}' not found.", file=sys.stderr)
            sys.exit(1)
            
        if args.follow:
            follow_file(args.file, args.pattern, args.ignore_case)
        else:
            with open(args.file, 'r', encoding='utf-8', errors='ignore') as f:
                process_stream(f, args.pattern, args.ignore_case)
    else:
        if args.follow:
            print("Warning: --follow is ignored when reading from standard input.", file=sys.stderr)
        # Check if stdin has data
        if sys.stdin.isatty():
            print("Log Colorizer: Waiting for stdin... Press Ctrl+C to exit.")
        process_stream(sys.stdin, args.pattern, args.ignore_case)

if __name__ == '__main__':
    main()
