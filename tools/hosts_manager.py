#!/usr/bin/env python3
"""
Hosts File Manager

Lists, adds, removes, or toggles local DNS entries in the system's hosts file.
Requires administrative privileges to modify the hosts file.

Usage:
    python tools/hosts_manager.py --list
    python tools/hosts_manager.py --add "127.0.0.1" "test.local"
    python tools/hosts_manager.py --remove "test.local"
"""

import argparse
import ctypes
import os
import sys

def get_hosts_path():
    if sys.platform == 'win32':
        return os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'System32\\drivers\\etc\\hosts')
    else:
        return '/etc/hosts'

def is_admin():
    try:
        if sys.platform == 'win32':
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        else:
            return os.getuid() == 0
    except Exception:
        return False

def print_safe(text):
    # Encodes and decodes with 'replace' handler to safely print non-encodable chars in Windows console
    if hasattr(sys.stdout, 'encoding') and sys.stdout.encoding:
        print(text.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding))
    else:
        print(text)

def list_entries(hosts_path):
    print(f"Reading hosts file from: {hosts_path}\n")
    try:
        # Use utf-8-sig to automatically strip UTF-8 BOM if present
        with open(hosts_path, 'r', encoding='utf-8-sig') as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith('#'):
                    print_safe(stripped)
    except PermissionError:
        print("Error: Permission denied. Please run this command with administrative privileges.")
    except Exception as e:
        print(f"Error reading hosts file: {e}")

def add_entry(hosts_path, ip, hostname):
    if not is_admin():
        print("Error: Administrative privileges are required to modify the hosts file.")
        print("Please run this script as Administrator (Windows) or using sudo (macOS/Linux).")
        return 1

    entry = f"{ip}\t{hostname}\n"
    try:
        with open(hosts_path, 'a', encoding='utf-8') as f:
            f.write(entry)
        print(f"Successfully added: {ip} -> {hostname}")
        return 0
    except Exception as e:
        print(f"Error writing to hosts file: {e}")
        return 1

def remove_entry(hosts_path, hostname):
    if not is_admin():
        print("Error: Administrative privileges are required to modify the hosts file.")
        return 1

    lines = []
    found = False
    try:
        with open(hosts_path, 'r', encoding='utf-8-sig') as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) >= 2 and parts[1] == hostname:
                    found = True
                    continue  # Skip this line
                lines.append(line)
        
        if not found:
            print(f"Hostname '{hostname}' not found in hosts file.")
            return 0

        with open(hosts_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)
            
        print(f"Successfully removed entries for: {hostname}")
        return 0
    except Exception as e:
        print(f"Error modifying hosts file: {e}")
        return 1

def main():
    parser = argparse.ArgumentParser(description="Hosts File Manager - View and edit system hosts file")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('-l', '--list', action='store_true', help='List active non-comment entries')
    group.add_argument('-a', '--add', metavar=('IP', 'HOSTNAME'), nargs=2, help='Add a new DNS redirection mapping')
    group.add_argument('-r', '--remove', metavar='HOSTNAME', help='Remove mappings for a specific hostname')
    
    args = parser.parse_args()
    hosts_path = get_hosts_path()

    if args.list:
        list_entries(hosts_path)
        return 0
    elif args.add:
        return add_entry(hosts_path, args.add[0], args.add[1])
    elif args.remove:
        return remove_entry(hosts_path, args.remove)

if __name__ == "__main__":
    sys.exit(main())
