#!/usr/bin/env python3
"""
Command History Analyzer

Auto-detects and analyzes shell history files (PowerShell, Bash, Zsh) to generate
usage statistics, find most frequent commands, and visualize activity patterns over time.

Usage:
    python tools/command_history_analyzer.py
    python tools/command_history_analyzer.py --shell zsh
    python tools/command_history_analyzer.py --file C:/path/to/custom_history.txt
"""

import argparse
from collections import Counter
from datetime import datetime
import os
from pathlib import Path
import re
import sys
from typing import List, Tuple, Dict, Any, Optional

# ANSI Colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_DIM = "\033[2m"

def supports_color() -> bool:
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform or is_a_tty

def color_text(text: str, color_code: str) -> str:
    return f"{color_code}{text}{COLOR_RESET}" if supports_color() else text

def get_default_paths() -> Dict[str, Path]:
    """Returns the default search paths for various shells based on OS."""
    paths = {}
    home = Path.home()
    
    # PowerShell
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            paths["powershell"] = Path(appdata) / "Microsoft" / "Windows" / "PowerShell" / "PSReadLine" / "ConsoleHost_history.txt"
    else:
        paths["powershell"] = home / ".local" / "share" / "powershell" / "PSReadLine" / "ConsoleHost_history.txt"
        
    # Bash
    paths["bash"] = home / ".bash_history"
    
    # Zsh
    paths["zsh"] = home / ".zsh_history"
    
    return paths

def detect_available_histories() -> List[Tuple[str, Path]]:
    """Scans default locations and returns existing history files."""
    defaults = get_default_paths()
    available = []
    for shell, path in defaults.items():
        if path.exists():
            available.append((shell, path))
    return available

# --- Parsers ---

def parse_powershell(file_path: Path) -> Tuple[List[str], List[Optional[datetime]]]:
    """Parses PowerShell history line-by-line. No built-in timestamps by default."""
    commands = []
    timestamps = []
    
    try:
        # PowerShell history is usually UTF-8, but might have other encodings
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                cmd = line.strip()
                if cmd:
                    commands.append(cmd)
                    timestamps.append(None)
    except Exception as e:
        print(color_text(f"[-] Error reading PowerShell history: {e}", COLOR_RED), file=sys.stderr)
        
    return commands, timestamps

def parse_bash(file_path: Path) -> Tuple[List[str], List[Optional[datetime]]]:
    """Parses Bash history, supporting the timestamp format (#<epoch>)."""
    commands = []
    timestamps = []
    
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
            
        i = 0
        while i < len(lines):
            line = lines[i].strip()
            if not line:
                i += 1
                continue
                
            # If line is a timestamp indicator
            if line.startswith("#") and line[1:].isdigit():
                epoch = int(line[1:])
                dt = datetime.fromtimestamp(epoch)
                
                # The next line is the actual command
                i += 1
                if i < len(lines):
                    cmd = lines[i].strip()
                    if cmd:
                        commands.append(cmd)
                        timestamps.append(dt)
            else:
                commands.append(line)
                timestamps.append(None)
            i += 1
    except Exception as e:
        print(color_text(f"[-] Error reading Bash history: {e}", COLOR_RED), file=sys.stderr)
        
    return commands, timestamps

def parse_zsh(file_path: Path) -> Tuple[List[str], List[Optional[datetime]]]:
    """Parses Zsh history formatting: ': <epoch>:<duration>;<command>'."""
    commands = []
    timestamps = []
    
    # Zsh history uses a special format or raw commands.
    # Regex: : 1623838383:0;cmd
    zsh_pattern = re.compile(r"^:\s*(\d+):\s*\d+;(.*)$")
    
    try:
        # Open with ISO-8859-1 or utf-8 with ignore to prevent crash on non-ASCII binary strings
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            current_command = []
            current_timestamp = None
            
            for line in f:
                # Check for continuation lines in case of multi-line commands
                match = zsh_pattern.match(line)
                if match:
                    # Save previous command if any
                    if current_command:
                        commands.append("\n".join(current_command))
                        timestamps.append(current_timestamp)
                        
                    epoch = int(match.group(1))
                    current_timestamp = datetime.fromtimestamp(epoch)
                    current_command = [match.group(2).rstrip()]
                else:
                    if line.strip():
                        # If zsh file contains plain commands (no timestamp enabled)
                        if not current_command and not line.startswith(":"):
                            commands.append(line.strip())
                            timestamps.append(None)
                        else:
                            current_command.append(line.rstrip())
                            
            # Add final command
            if current_command:
                commands.append("\n".join(current_command))
                timestamps.append(current_timestamp)
                
    except Exception as e:
        print(color_text(f"[-] Error reading Zsh history: {e}", COLOR_RED), file=sys.stderr)
        
    return commands, timestamps

# --- Analysis & Visualizations ---

def supports_unicode() -> bool:
    """Checks if standard output can encode Unicode bar chart characters."""
    try:
        "█░".encode(sys.stdout.encoding or 'ascii')
        return True
    except Exception:
        return False

def make_ascii_bar(val: int, max_val: int, width: int = 20) -> str:
    """Generates an ASCII bar chart representation."""
    if max_val == 0:
        return ""
    fill_len = int((val / max_val) * width)
    unicode_ok = supports_unicode()
    fill_char = "█" if unicode_ok else "#"
    empty_char = "░" if unicode_ok else "-"
    return fill_char * fill_len + empty_char * (width - fill_len)


def display_stats(shell_name: str, file_path: Path, commands: List[str], timestamps: List[Optional[datetime]], limit: int):
    """Generates and displays the command line analytics dashboard."""
    if not commands:
        print(color_text(f"[-] No commands loaded from {file_path}. Is the file empty?", COLOR_YELLOW))
        return
        
    # General stats
    total = len(commands)
    unique = len(set(commands))
    dups_pct = ((total - unique) / total) * 100 if total > 0 else 0
    avg_len = sum(len(c) for c in commands) / total if total > 0 else 0
    
    print("\n" + color_text(f"=== SHELL HISTORY DASHBOARD: {shell_name.upper()} ===", COLOR_BOLD + COLOR_CYAN))
    print(f"Source file:   {file_path}")
    print(f"Total entries: {color_text(str(total), COLOR_BOLD)}")
    print(f"Unique cmds:   {color_text(str(unique), COLOR_BOLD)}")
    print(f"Dups rate:     {dups_pct:.1f}%")
    print(f"Avg cmd len:   {avg_len:.1f} characters")
    print("-" * 60)
    
    # Extract binary names (first word of command)
    binaries = []
    for c in commands:
        parts = c.split()
        if parts:
            # Strip path prefixes like ./ or /usr/bin/ if any
            name = os.path.basename(parts[0])
            binaries.append(name)
            
    binary_counts = Counter(binaries)
    cmd_counts = Counter(commands)
    
    # Top Executables
    print("\n" + color_text(f"Top {limit} Commands / Executables:", COLOR_BOLD))
    top_bins = binary_counts.most_common(limit)
    max_bin_count = top_bins[0][1] if top_bins else 1
    for rank, (name, count) in enumerate(top_bins, 1):
        bar = make_ascii_bar(count, max_bin_count)
        print(f" {rank:>2}. {name:<15} | {count:>5} {color_text(bar, COLOR_GREEN)}")
        
    # Top Full Commands
    print("\n" + color_text(f"Top {limit} Exact Full Commands:", COLOR_BOLD))
    top_cmds = cmd_counts.most_common(limit)
    for rank, (cmd, count) in enumerate(top_cmds, 1):
        # Truncate cmd for neat table
        disp_cmd = cmd.replace("\n", " ; ")
        if len(disp_cmd) > 40:
            disp_cmd = disp_cmd[:37] + "..."
        print(f" {rank:>2}. {count:>4}x  {color_text(disp_cmd, COLOR_YELLOW)}")
        
    # Time-based analytics (if timestamps are available)
    valid_ts = [t for t in timestamps if t is not None]
    if valid_ts:
        print("\n" + color_text("Activity by Hour (24h clock):", COLOR_BOLD))
        hours = [t.hour for t in valid_ts]
        hour_counts = Counter(hours)
        max_hour_count = max(hour_counts.values()) if hour_counts else 1
        
        for hour in range(24):
            count = hour_counts.get(hour, 0)
            bar = make_ascii_bar(count, max_hour_count, width=15)
            print(f"  {hour:02d}:00 | {count:>4} {color_text(bar, COLOR_CYAN)}")
            
        print("\n" + color_text("Activity by Weekday:", COLOR_BOLD))
        weekday_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
        wdays = [t.weekday() for t in valid_ts]
        wday_counts = Counter(wdays)
        max_wday_count = max(wday_counts.values()) if wday_counts else 1
        
        for idx, day_name in enumerate(weekday_names):
            count = wday_counts.get(idx, 0)
            bar = make_ascii_bar(count, max_wday_count, width=15)
            print(f"  {day_name:<9} | {count:>4} {color_text(bar, COLOR_CYAN)}")
    else:
        print("\n" + color_text("[-] Time-based statistics unavailable (no timestamps found in history).", COLOR_DIM))
        
    print("\n" + color_text("=" * 45, COLOR_CYAN))

# --- Main ---

def main():
    parser = argparse.ArgumentParser(
        description="Command History Analyzer: Generate stats and analytics from terminal history files.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("-s", "--shell", choices=["powershell", "bash", "zsh"],
                        help="Specify shell to analyze (default: auto-detect)")
    parser.add_argument("-f", "--file", help="Path to custom history file")
    parser.add_argument("-l", "--limit", type=int, default=10, help="Limit of top items to display (default: 10)")
    
    args = parser.parse_args()
    
    selected_shell = None
    selected_path = None
    
    if args.file:
        selected_path = Path(args.file)
        if not selected_path.exists():
            print(color_text(f"[-] Specified file does not exist: {selected_path}", COLOR_RED), file=sys.stderr)
            sys.exit(1)
            
        if args.shell:
            selected_shell = args.shell
        else:
            # Guess shell from filename
            name = selected_path.name.lower()
            if "bash" in name:
                selected_shell = "bash"
            elif "zsh" in name:
                selected_shell = "zsh"
            elif "powershell" in name or "consolehost" in name:
                selected_shell = "powershell"
            else:
                # Default guess
                selected_shell = "bash"
    else:
        # Auto-detect available shell histories
        histories = detect_available_histories()
        
        if not histories:
            print(color_text("[-] No standard shell history files found on this machine.", COLOR_RED), file=sys.stderr)
            print("Please provide a path to a history file with the --file flag.")
            sys.exit(1)
            
        if args.shell:
            # Find specific requested shell in available ones
            matched = [h for h in histories if h[0] == args.shell]
            if not matched:
                # Fallback to defaults search path anyway
                defaults = get_default_paths()
                selected_shell = args.shell
                selected_path = defaults[selected_shell]
            else:
                selected_shell, selected_path = matched[0]
        else:
            # Select the first available history
            selected_shell, selected_path = histories[0]
            if len(histories) > 1:
                print(color_text("[*] Multiple histories detected. Analyzing first choice. Options:", COLOR_CYAN))
                for sh, p in histories:
                    print(f"  - {sh}: {p}")
                    
    print(f"Analyzing {selected_shell} history from: {selected_path}...")
    
    # Parse history file
    if selected_shell == "powershell":
        commands, timestamps = parse_powershell(selected_path)
    elif selected_shell == "zsh":
        commands, timestamps = parse_zsh(selected_path)
    else: # bash
        commands, timestamps = parse_bash(selected_path)
        
    display_stats(selected_shell, selected_path, commands, timestamps, args.limit)

if __name__ == "__main__":
    main()
