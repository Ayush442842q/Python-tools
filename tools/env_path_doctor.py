#!/usr/bin/env python3
"""
System PATH Doctor - Diagnose, optimize, and clean system environment PATH variables.
"""

import os
import sys
import argparse
from pathlib import Path

def get_color(color_name):
    """Return ANSI escape code for terminal color if supported."""
    colors = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'bold': '\033[1m',
        'reset': '\033[0m'
    }
    # Check if terminal supports color
    if sys.platform == 'win32':
        # Enable VT100 mode in Windows console if possible
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            return ''  # Don't use colors if it fails
    return colors.get(color_name, '')

def diagnose_path(path_str=None, verbose=False):
    """Diagnose the given PATH string or system PATH if None."""
    c_red = get_color('red')
    c_green = get_color('green')
    c_yellow = get_color('yellow')
    c_blue = get_color('blue')
    c_bold = get_color('bold')
    c_reset = get_color('reset')

    if path_str is None:
        path_str = os.environ.get('PATH', '')

    if not path_str:
        print(f"{c_red}Error: PATH environment variable is empty or not set.{c_reset}")
        return

    path_sep = os.pathsep
    entries = path_str.split(path_sep)

    seen = set()
    duplicates = []
    missing = []
    warnings = []
    valid = []

    print(f"{c_bold}System PATH Doctor Diagnostics{c_reset}")
    print("=" * 60)
    print(f"Total entries found: {len(entries)}")
    print(f"Path separator used: '{path_sep}'")
    print("-" * 60)

    for idx, raw_entry in enumerate(entries, 1):
        if not raw_entry.strip():
            warnings.append((idx, raw_entry, "Empty entry in PATH (consecutive delimiters)"))
            continue

        # Check for relative path/security risk
        is_relative = False
        if raw_entry == '.' or not os.path.isabs(raw_entry):
            is_relative = True
            warnings.append((idx, raw_entry, "Relative path detected (Security Risk - can lead to DLL/Binary hijacking)"))

        norm_path = os.path.normpath(raw_entry)
        norm_case = norm_path.lower() if sys.platform == 'win32' else norm_path

        # Check for duplicates
        if norm_case in seen:
            duplicates.append((idx, raw_entry))
            continue
        seen.add(norm_case)

        # Check existence
        try:
            p = Path(norm_path)
            if not p.exists():
                missing.append((idx, raw_entry, "Directory does not exist"))
            elif not p.is_dir():
                warnings.append((idx, raw_entry, "Path points to a file, not a directory"))
            else:
                # Check for write permissions (security check)
                if sys.platform != 'win32':
                    # On Unix, check if world writable
                    try:
                        stat_info = p.stat()
                        # 0o002 is S_IWOTH (write permission for others)
                        if stat_info.st_mode & 0o002:
                            warnings.append((idx, raw_entry, "Directory is world-writable (Security Risk)"))
                    except Exception:
                        pass
                
                valid.append((idx, raw_entry))
        except Exception as e:
            missing.append((idx, raw_entry, f"Invalid path syntax or error: {str(e)}"))

    # Print Detailed Diagnostics
    if verbose:
        print(f"\n{c_bold}Detailed Entry Analysis:{c_reset}")
        for idx, entry in enumerate(entries, 1):
            norm_path = os.path.normpath(entry)
            norm_case = norm_path.lower() if sys.platform == 'win32' else norm_path
            
            # Find status
            status_str = f"{c_green}[OK]{c_reset}"
            reason = ""
            
            is_dup = any(d[0] == idx for d in duplicates)
            is_miss = any(m[0] == idx for m in missing)
            is_warn = [w for w in warnings if w[0] == idx]
            
            if is_dup:
                status_str = f"{c_yellow}[DUPLICATE]{c_reset}"
            elif is_miss:
                status_str = f"{c_red}[MISSING]{c_reset}"
                reason = next(m[2] for m in missing if m[0] == idx)
            elif is_warn:
                status_str = f"{c_yellow}[WARNING]{c_reset}"
                reason = "; ".join(w[2] for w in is_warn)

            print(f" {idx:02d}. {status_str} {entry}")
            if reason:
                print(f"     Reason: {reason}")
        print("-" * 60)

    # Print Summary
    print(f"\n{c_bold}Diagnostic Summary:{c_reset}")
    if not duplicates and not missing and not warnings:
        print(f" {c_green}[OK] Your PATH is perfectly clean and optimal!{c_reset}")
    else:
        if missing:
            print(f" {c_red}[FAIL] Missing/Broken Paths ({len(missing)}):{c_reset}")
            for _, item, reason in missing:
                print(f"   - {item} ({reason})")
        
        if duplicates:
            print(f" {c_yellow}! Duplicate Paths ({len(duplicates)}):{c_reset}")
            # Group duplicates to show occurrences
            for _, item in duplicates:
                print(f"   - {item}")
        
        if warnings:
            print(f" {c_yellow}! Warnings ({len(warnings)}):{c_reset}")
            for _, item, reason in warnings:
                print(f"   - {item}: {reason}")

    # Generate optimal path
    clean_entries = []
    clean_seen = set()
    for entry in entries:
        if not entry.strip():
            continue
        norm_path = os.path.normpath(entry)
        norm_case = norm_path.lower() if sys.platform == 'win32' else norm_path
        
        # Keep if it exists, is absolute, and is not a duplicate
        if norm_case not in clean_seen:
            try:
                p = Path(norm_path)
                if p.exists() and p.is_dir() and os.path.isabs(entry):
                    clean_entries.append(entry)
                    clean_seen.add(norm_case)
            except Exception:
                pass

    clean_path_str = path_sep.join(clean_entries)

    print("\n" + "=" * 60)
    print(f"{c_bold}Cleaned PATH Statistics:{c_reset}")
    print(f"Original entries: {len(entries)}")
    print(f"Cleaned entries:  {len(clean_entries)}")
    print(f"Removed entries:  {len(entries) - len(clean_entries)}")
    
    return clean_path_str

def main():
    parser = argparse.ArgumentParser(description="Diagnose, optimize, and clean system environment PATH variables.")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print detailed diagnostic status for every single entry")
    parser.add_argument("-s", "--set-command", action="store_true", help="Generate command to set cleaned path in terminal")
    parser.add_argument("-t", "--test", help="Test a custom path string instead of system PATH")
    
    args = parser.parse_args()
    
    custom_path = args.test
    cleaned = diagnose_path(custom_path, args.verbose)
    
    if cleaned and args.set_command:
        print("\n" + "=" * 60)
        print(f"{get_color('bold')}Shell Commands to Apply Cleaned PATH:{get_color('reset')}\n")
        
        if sys.platform == 'win32':
            print(f"{get_color('blue')}PowerShell (Current Session):{get_color('reset')}")
            print(f'$env:PATH = "{cleaned}"')
            print(f"\n{get_color('blue')}PowerShell (User Environment - Persistent):{get_color('reset')}")
            print(f'[Environment]::SetEnvironmentVariable("Path", "{cleaned}", "User")')
            print(f"\n{get_color('blue')}Command Prompt (Current Session):{get_color('reset')}")
            # Replace semicolon with local separator just in case, though on Windows it is semicolon
            cmd_cleaned = cleaned.replace('"', '^"')
            print(f'set PATH={cmd_cleaned}')
        else:
            print(f"{get_color('blue')}Bash / Zsh (Current Session & export):{get_color('reset')}")
            print(f'export PATH="{cleaned}"')
            print(f"\nTo make persistent, add the line above to your ~/.bashrc or ~/.zshrc file.")

if __name__ == '__main__':
    main()
