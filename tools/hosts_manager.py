#!/usr/bin/env python3
"""
Hosts File Manager - Manage system hosts mappings

A cross-platform utility to inspect and manipulate host name resolution mappings
in the system's hosts file. Supports listing, adding, removing, enabling, and
disabling entries. Handles permissions gracefully.

Usage:
    python tools/hosts_manager.py [options]

Options:
    -l, --list          List all hosts mappings (grouped by active and disabled)
    -a, --add           Add a new mapping: IP HOSTNAME (e.g. -a 127.0.0.1 dev.local)
    -r, --remove        Remove all mappings for a specific hostname
    -d, --disable       Disable mapping(s) for a specific hostname (comment out)
    -e, --enable        Enable mapping(s) for a specific hostname (uncomment)
    -b, --backup        Create a timestamped backup of the hosts file
    --dry-run           Preview changes without writing to the hosts file

Examples:
    python tools/hosts_manager.py --list
    python tools/hosts_manager.py --add 127.0.0.1 mysite.local --dry-run
"""

import argparse
import sys
import os
import shutil
import platform
from datetime import datetime

# ANSI escape codes
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"

def get_hosts_path():
    """Get platform-specific hosts file path."""
    system = platform.system()
    if system == "Windows":
        return os.path.join(os.environ.get("SystemRoot", "C:\\Windows"), "System32", "drivers", "etc", "hosts")
    else:
        return "/etc/hosts"

def parse_hosts_file(path):
    """
    Parse hosts file into a list of dictionaries.
    Each item contains raw line, is_mapping (bool), is_active (bool), ip, host, comment.
    """
    entries = []
    if not os.path.exists(path):
        return entries
        
    try:
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                stripped = line.strip()
                # Check if it's a comment
                if not stripped:
                    entries.append({"raw": line, "type": "empty"})
                    continue
                    
                if stripped.startswith("#"):
                    # Check if it's a commented mapping
                    content = stripped[1:].strip()
                    parts = content.split()
                    if len(parts) >= 2 and is_valid_ip(parts[0]):
                        entries.append({
                            "raw": line,
                            "type": "mapping",
                            "is_active": False,
                            "ip": parts[0],
                            "host": parts[1],
                            "comment": " ".join(parts[2:]) if len(parts) > 2 else ""
                        })
                    else:
                        entries.append({"raw": line, "type": "comment"})
                else:
                    parts = stripped.split()
                    # Check if it's a valid mapping
                    if len(parts) >= 2 and is_valid_ip(parts[0]):
                        entries.append({
                            "raw": line,
                            "type": "mapping",
                            "is_active": True,
                            "ip": parts[0],
                            "host": parts[1],
                            "comment": " ".join(parts[2:]) if len(parts) > 2 else ""
                        })
                    else:
                        entries.append({"raw": line, "type": "other"})
    except Exception as e:
        print(f"{RED}Error reading hosts file: {e}{RESET}", file=sys.stderr)
        sys.exit(1)
        
    return entries

def is_valid_ip(ip_str):
    """Very basic IP address check (IPv4 or IPv6 placeholder)."""
    # Simple check for IPv4 or IPv6 address format
    if ":" in ip_str: # Simple IPv6 check
        return True
    parts = ip_str.split('.')
    if len(parts) == 4:
        try:
            return all(0 <= int(part) <= 255 for part in parts)
        except ValueError:
            return False
    return False

def write_hosts_file(path, entries, dry_run=False):
    """Write parsed entries list back to the hosts file."""
    lines = []
    for entry in entries:
        if entry["type"] == "mapping":
            comment_str = f" # {entry['comment']}" if entry.get('comment') else ""
            if entry["is_active"]:
                lines.append(f"{entry['ip']}\t{entry['host']}{comment_str}\n")
            else:
                lines.append(f"# {entry['ip']}\t{entry['host']}{comment_str}\n")
        else:
            lines.append(entry["raw"])
            
    content = "".join(lines)
    
    if dry_run:
        print(f"\n{BOLD}{YELLOW}--- DRY RUN: PREVIEW OF OUTPUT ---{RESET}")
        print(content)
        print(f"{BOLD}{YELLOW}----------------------------------{RESET}\n")
        return True
        
    try:
        # Try writing
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        return True
    except PermissionError:
        print(f"\n{RED}{BOLD}Permission Denied!{RESET}")
        print("Editing the hosts file requires administrator / root privileges.")
        if platform.system() == "Windows":
            print(f"Please run your command shell (PowerShell or CMD) as {BOLD}Administrator{RESET}.")
        else:
            print(f"Please run this tool using {BOLD}sudo{RESET}:")
            print(f"  sudo python {' '.join(sys.argv)}")
        print()
        return False
    except Exception as e:
        print(f"{RED}Error writing to hosts file: {e}{RESET}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(description="Manage system hosts mappings")
    parser.add_argument("-l", "--list", action="store_true", help="List all hosts mappings")
    parser.add_argument("-a", "--add", nargs=2, metavar=("IP", "HOSTNAME"), help="Add a new IP to hostname mapping")
    parser.add_argument("-r", "--remove", metavar="HOSTNAME", help="Remove all mappings for a specific hostname")
    parser.add_argument("-d", "--disable", metavar="HOSTNAME", help="Disable mapping(s) for a specific hostname")
    parser.add_argument("-e", "--enable", metavar="HOSTNAME", help="Enable mapping(s) for a specific hostname")
    parser.add_argument("-b", "--backup", action="store_true", help="Backup current hosts file to local folder")
    parser.add_argument("--dry-run", action="store_true", help="Preview changes without saving")
    
    args = parser.parse_args()
    
    hosts_path = get_hosts_path()
    
    # Check if there are no arguments
    if len(sys.argv) == 1:
        parser.print_help()
        return 0
        
    print(f"{BOLD}{GREEN}========================================={RESET}")
    print(f"{BOLD}{GREEN}          SYSTEM HOSTS MANAGER           {RESET}")
    print(f"{BOLD}{GREEN}========================================={RESET}")
    print(f"Hosts File: {hosts_path}")
    print()
    
    # 1. Backup operation
    if args.backup:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"hosts_backup_{timestamp}"
        try:
            shutil.copy(hosts_path, backup_name)
            print(f"{GREEN}✔ Backup successfully created: {backup_name}{RESET}")
        except Exception as e:
            print(f"{RED}Failed to create backup: {e}{RESET}", file=sys.stderr)
            return 1
        return 0
        
    entries = parse_hosts_file(hosts_path)
    modified = False
    
    # 2. List mappings
    if args.list:
        mappings = [e for e in entries if e["type"] == "mapping"]
        if not mappings:
            print("No host mappings found.")
            return 0
            
        print(f"{BOLD}{CYAN}Active Mappings:{RESET}")
        active = [m for m in mappings if m["is_active"]]
        if active:
            for m in active:
                comment = f" ({m['comment']})" if m['comment'] else ""
                print(f"  {GREEN}●{RESET} {m['ip']:<20} {BOLD}{m['host']}{RESET}{comment}")
        else:
            print("  None")
            
        print(f"\n{BOLD}{YELLOW}Disabled Mappings (Commented Out):{RESET}")
        disabled = [m for m in mappings if not m["is_active"]]
        if disabled:
            for m in disabled:
                comment = f" ({m['comment']})" if m['comment'] else ""
                print(f"  {RED}○{RESET} {m['ip']:<20} {m['host']}{comment}")
        else:
            print("  None")
        return 0
        
    # 3. Add mapping
    if args.add:
        ip, host = args.add
        if not is_valid_ip(ip):
            print(f"{RED}Error: Invalid IP address format: {ip}{RESET}", file=sys.stderr)
            return 1
            
        # Check if mapping already exists
        exists = False
        for entry in entries:
            if entry["type"] == "mapping" and entry["host"].lower() == host.lower():
                if entry["ip"] == ip:
                    if not entry["is_active"]:
                        entry["is_active"] = True
                        modified = True
                        print(f"Enabling existing mapping: {ip} -> {host}")
                    else:
                        print(f"Mapping already exists and is active: {ip} -> {host}")
                    exists = True
                    break
                    
        if not exists:
            entries.append({
                "type": "mapping",
                "is_active": True,
                "ip": ip,
                "host": host,
                "comment": "Added by Hosts Manager"
            })
            modified = True
            print(f"Adding new mapping: {ip} -> {host}")
            
    # 4. Remove mapping
    if args.remove:
        host = args.remove
        new_entries = []
        for entry in entries:
            if entry["type"] == "mapping" and entry["host"].lower() == host.lower():
                print(f"Removing mapping: {entry['ip']} -> {entry['host']}")
                modified = True
            else:
                new_entries.append(entry)
        entries = new_entries
        
    # 5. Disable mapping
    if args.disable:
        host = args.disable
        for entry in entries:
            if entry["type"] == "mapping" and entry["host"].lower() == host.lower():
                if entry["is_active"]:
                    entry["is_active"] = False
                    modified = True
                    print(f"Disabled mapping: {entry['ip']} -> {entry['host']}")
                    
    # 6. Enable mapping
    if args.enable:
        host = args.enable
        for entry in entries:
            if entry["type"] == "mapping" and entry["host"].lower() == host.lower():
                if not entry["is_active"]:
                    entry["is_active"] = True
                    modified = True
                    print(f"Enabled mapping: {entry['ip']} -> {entry['host']}")
                    
    if modified:
        success = write_hosts_file(hosts_path, entries, args.dry_run)
        if success:
            if args.dry_run:
                print(f"{YELLOW}Dry-run completed. No files modified.{RESET}")
            else:
                print(f"{GREEN}✔ Hosts file updated successfully.{RESET}")
        else:
            return 1
    else:
        print("No changes needed.")
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
