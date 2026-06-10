#!/usr/bin/env python3
"""
Log Colorizer

A standalone terminal utility to colorize log files or live log streams. 
Applies syntax highlighting to log levels, dates, times, IP addresses, URLs,
and custom keyword matches.

Supports tailing log files in real-time (like `tail -f`).

Usage:
    python tools/log_colorizer.py [options] [log_file]

Examples:
    python tools/log_colorizer.py app.log
    python tools/log_colorizer.py -t app.log
    cat app.log | python tools/log_colorizer.py
    docker logs container | python tools/log_colorizer.py -k "database,auth"
"""

import argparse
import ctypes
import os
import re
import sys
import time

# ANSI color escape sequences
RESET = "\033[0m"
BOLD = "\033[1m"
UNDERLINE = "\033[4m"

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
WHITE = "\033[97m"

DARK_GRAY = "\033[90m"

LEVEL_COLORS = {
    'ERROR': BOLD + RED,
    'FAIL': BOLD + RED,
    'FATAL': BOLD + RED,
    'CRITICAL': BOLD + RED,
    'CRIT': BOLD + RED,
    'ERR': BOLD + RED,
    
    'WARN': BOLD + YELLOW,
    'WARNING': BOLD + YELLOW,
    'WRN': BOLD + YELLOW,
    
    'INFO': GREEN,
    'SUCCESS': BOLD + GREEN,
    'OK': GREEN,
    'CONF': GREEN,
    
    'DEBUG': BLUE,
    'DEBG': BLUE,
    'DBG': BLUE,
    
    'TRACE': MAGENTA,
    'TRC': MAGENTA,
}

# Regex definitions
IP_PATTERN = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
URL_PATTERN = re.compile(r"\bhttps?://[a-zA-Z0-9.\-_~:/?#\[\]@!$&'()*+,;=]+\b")

# Matches ISO8601-like timestamps and times (e.g. 2026-06-11 12:34:56.789, 12:34:56)
TIME_PATTERN = re.compile(
    r"\b(?:\d{4}[-/]\d{2}[-/]\d{2}[ T])?\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+\-]\d{2}:?\d{2})?\b"
)

# Matches log levels inside braces, brackets, or as standalone words
LEVEL_PATTERN = re.compile(
    r"\b(ERROR|FAIL|FATAL|CRITICAL|CRIT|ERR|WARNING|WARN|WRN|INFO|SUCCESS|OK|CONF|DEBUG|DEBG|DBG|TRACE|TRC)\b",
    re.IGNORECASE
)

def enable_ansi_windows():
    """Enable virtual terminal processing in Windows 10+ console using ctypes."""
    if os.name == 'nt':
        try:
            kernel32 = ctypes.windll.kernel32
            # STD_OUTPUT_HANDLE = -11
            stdout_handle = kernel32.GetStdHandle(-11)
            if stdout_handle == -1 or stdout_handle is None:
                return False
                
            mode = ctypes.c_ulong()
            if not kernel32.GetConsoleMode(stdout_handle, ctypes.byref(mode)):
                return False
                
            # ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            mode.value |= 0x0004
            if not kernel32.SetConsoleMode(stdout_handle, mode):
                return False
            return True
        except Exception:
            return False
    return False

def colorize_line(line, keywords=None, keyword_color=YELLOW):
    """Parse and colorize elements of a log line."""
    # Strip trailing newline for clean processing
    line_stripped = line.rstrip('\n')
    
    # 1. Colorize Log Level
    def replace_level(match):
        lvl = match.group(1).upper()
        color = LEVEL_COLORS.get(lvl, WHITE)
        return f"{color}{match.group(1)}{RESET}"
        
    line_colored = LEVEL_PATTERN.sub(replace_level, line_stripped)
    
    # 2. Colorize Timestamps
    line_colored = TIME_PATTERN.sub(lambda m: f"{CYAN}{m.group(0)}{RESET}", line_colored)
    
    # 3. Colorize IP Addresses
    line_colored = IP_PATTERN.sub(lambda m: f"{MAGENTA}{m.group(0)}{RESET}", line_colored)
    
    # 4. Colorize URLs
    line_colored = URL_PATTERN.sub(lambda m: f"{UNDERLINE}{CYAN}{m.group(0)}{RESET}", line_colored)
    
    # 5. Highlight custom keywords
    if keywords:
        for kw in keywords:
            if kw:
                # Case-insensitive replacement
                pattern = re.compile(re.escape(kw), re.IGNORECASE)
                line_colored = pattern.sub(lambda m: f"{BOLD}{keyword_color}{m.group(0)}{RESET}", line_colored)
                
    return line_colored

def tail_file(file_path, keywords=None, keyword_color=YELLOW):
    """Monitor a file in real-time, colorizing new lines as they are appended."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            # Seek to the end of the file
            f.seek(0, os.SEEK_END)
            print(f"{DARK_GRAY}Tailing {file_path.name}... Press Ctrl+C to stop.{RESET}")
            
            while True:
                line = f.readline()
                if not line:
                    time.sleep(0.1)
                    continue
                print(colorize_line(line, keywords, keyword_color))
                sys.stdout.flush()
    except KeyboardInterrupt:
        print(f"\n{DARK_GRAY}Stopped tailing.{RESET}")
    except Exception as e:
        print(f"\nError tailing file: {e}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(
        description="Colorize logs from files or stdin with support for log levels, IPs, URLs, and tailing."
    )
    parser.add_argument(
        'log_file',
        nargs='?',
        help='Log file to view. If omitted, reads from standard input.'
    )
    parser.add_argument(
        '-t', '--tail',
        action='store_true',
        help='Tail the log file in real-time (like tail -f)'
    )
    parser.add_argument(
        '-k', '--keywords',
        help='Comma-separated custom keywords to highlight (e.g. "database,auth")'
    )
    parser.add_argument(
        '--color',
        choices=['red', 'green', 'yellow', 'blue', 'magenta', 'cyan', 'white'],
        default='yellow',
        help='Color to use for custom keywords (default: yellow)'
    )
    
    args = parser.parse_args()
    
    # Enable Windows 10 ANSI escape support
    enable_ansi_windows()
    
    # Resolve custom keyword color
    color_map = {
        'red': RED,
        'green': GREEN,
        'yellow': YELLOW,
        'blue': BLUE,
        'magenta': MAGENTA,
        'cyan': CYAN,
        'white': WHITE
    }
    kw_color = color_map.get(args.color, YELLOW)
    
    keywords = [k.strip() for k in args.keywords.split(',')] if args.keywords else []
    
    if args.tail:
        if not args.log_file:
            print("Error: Live tailing requires a target file path.", file=sys.stderr)
            return 1
        log_path = Path(args.log_file)
        if not log_path.exists():
            print(f"Error: Log file '{args.log_file}' does not exist.", file=sys.stderr)
            return 1
        tail_file(log_path, keywords, kw_color)
        return 0
        
    # Standard read mode
    if args.log_file:
        log_path = Path(args.log_file)
        if not log_path.exists():
            print(f"Error: Log file '{args.log_file}' does not exist.", file=sys.stderr)
            return 1
            
        try:
            with open(log_path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    print(colorize_line(line, keywords, kw_color))
        except KeyboardInterrupt:
            pass
        except Exception as e:
            print(f"Error reading log file: {e}", file=sys.stderr)
            return 1
    else:
        # Read from stdin
        if sys.stdin.isatty():
            print("Error: No log file provided, and standard input is empty.", file=sys.stderr)
            parser.print_help()
            return 1
            
        try:
            for line in sys.stdin:
                print(colorize_line(line, keywords, kw_color))
                sys.stdout.flush()
        except KeyboardInterrupt:
            pass
            
    return 0

if __name__ == '__main__':
    sys.exit(main())
