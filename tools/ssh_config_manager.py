#!/usr/bin/env python3
"""
SSH Configuration Manager

A CLI tool to list, parse, add, delete, and test connections to hosts defined
in the SSH configuration file (~/.ssh/config).

Usage:
    python tools/ssh_config_manager.py list
    python tools/ssh_config_manager.py add my-server --host-name 192.168.1.50 --user admin --port 22
    python tools/ssh_config_manager.py delete my-server
    python tools/ssh_config_manager.py test my-server
"""

import os
import re
import sys
import socket
import argparse
from pathlib import Path

DEFAULT_SSH_CONFIG = Path.home() / ".ssh" / "config"

def parse_config(config_path):
    """Parse the SSH config file and return a list of host configurations."""
    if not config_path.exists():
        return []

    hosts = []
    current_host = None
    
    with open(config_path, "r", encoding="utf-8") as f:
        for line in f:
            line_stripped = line.strip()
            # Ignore empty lines or comments
            if not line_stripped or line_stripped.startswith("#"):
                continue
            
            # Match directive and value (handles space or equals separator)
            match = re.match(r"^(\w+)(?:\s+|\s*=\s*)(.+)$", line_stripped)
            if not match:
                continue
                
            key, val = match.groups()
            key_lower = key.lower()
            
            if key_lower == "host":
                if current_host:
                    hosts.append(current_host)
                # SSH config can define multiple pattern aliases separated by spaces
                current_host = {"host": val, "options": {}}
            elif current_host:
                current_host["options"][key] = val
                
        if current_host:
            hosts.append(current_host)
            
    return hosts

def write_config(config_path, hosts):
    """Write the host configurations back to the SSH config file."""
    # Ensure directory exists
    config_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(config_path, "w", encoding="utf-8") as f:
        f.write("# Generated and managed by SSH Configuration Manager\n\n")
        for h in hosts:
            f.write(f"Host {h['host']}\n")
            for key, val in h["options"].items():
                f.write(f"    {key} {val}\n")
            f.write("\n")

def list_hosts(hosts, test_conn=False):
    """Display the list of configured hosts in a formatted table."""
    if not hosts:
        print("No hosts found in SSH configuration.")
        return

    # Print header
    print(f"{'Host Alias':<20} | {'HostName/IP':<30} | {'User':<15} | {'Port':<6} | {'Status' if test_conn else ''}")
    print("-" * (85 if test_conn else 78))
    
    for h in hosts:
        alias = h["host"]
        opts = h["options"]
        hostname = opts.get("HostName", opts.get("hostname", "-"))
        user = opts.get("User", opts.get("user", "-"))
        port = opts.get("Port", opts.get("port", "22"))
        
        status_str = ""
        if test_conn:
            if hostname != "-":
                status_str = "Testing..."
                # Quick TCP socket connection test
                try:
                    p = int(port)
                    with socket.create_connection((hostname, p), timeout=2.0) as sock:
                        status_str = "\033[92mONLINE\033[0m"
                except Exception:
                    status_str = "\033[91mOFFLINE\033[0m"
            else:
                status_str = "N/A"
                
        print(f"{alias:<20} | {hostname:<30} | {user:<15} | {port:<6} | {status_str}")

def test_host(alias, config_path):
    """Test connection to a specific host by its alias."""
    hosts = parse_config(config_path)
    target = next((h for h in hosts if h["host"] == alias), None)
    
    if not target:
        print(f"Error: Host '{alias}' not found in configuration.")
        return False
        
    opts = target["options"]
    hostname = opts.get("HostName", opts.get("hostname"))
    port = int(opts.get("Port", opts.get("port", 22)))
    user = opts.get("User", opts.get("user", "default"))
    
    if not hostname:
        print(f"Error: HostName not defined for alias '{alias}'.")
        return False
        
    print(f"Testing SSH connection to '{alias}' ({hostname}:{port}) as user '{user}'...")
    try:
        with socket.create_connection((hostname, port), timeout=3.0) as sock:
            print(f"✓ Success! Port {port} is open and accepting connections.")
            return True
    except Exception as e:
        print(f"✗ Failed to connect to {hostname}:{port}. Error: {e}")
        return False

def add_host(alias, args, config_path):
    """Add a new host entry to the config file."""
    hosts = parse_config(config_path)
    
    # Check if host already exists
    if any(h["host"] == alias for h in hosts):
        print(f"Error: Host alias '{alias}' already exists in configuration.")
        return False
        
    options = {}
    if args.host_name:
        options["HostName"] = args.host_name
    if args.user:
        options["User"] = args.user
    if args.port:
        options["Port"] = args.port
    if args.identity_file:
        options["IdentityFile"] = args.identity_file
    if args.proxy_jump:
        options["ProxyJump"] = args.proxy_jump
        
    # Process extra key-value options if provided
    if args.option:
        for opt in args.option:
            if "=" in opt:
                k, v = opt.split("=", 1)
                options[k.strip()] = v.strip()
            else:
                print(f"Warning: Ignoring invalid extra option format: '{opt}'. Use Key=Value.")

    if not options:
        print("Error: No configuration options specified. Provide at least --host-name.")
        return False

    new_host = {"host": alias, "options": options}
    hosts.append(new_host)
    write_config(config_path, hosts)
    print(f"Successfully added host '{alias}' to configuration.")
    return True

def delete_host(alias, config_path):
    """Delete a host entry from the config file."""
    hosts = parse_config(config_path)
    initial_count = len(hosts)
    
    hosts = [h for h in hosts if h["host"] != alias]
    
    if len(hosts) == initial_count:
        print(f"Error: Host alias '{alias}' not found.")
        return False
        
    write_config(config_path, hosts)
    print(f"Successfully deleted host '{alias}' from configuration.")
    return True

def main():
    parser = argparse.ArgumentParser(description="SSH Configuration File Manager")
    parser.add_argument("-c", "--config", help="Path to SSH config file (defaults to ~/.ssh/config)", default=str(DEFAULT_SSH_CONFIG))
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # List command
    list_parser = subparsers.add_parser("list", help="List all configured hosts")
    list_parser.add_argument("-t", "--test", action="store_true", help="Test port availability for each host")
    
    # Add command
    add_parser = subparsers.add_parser("add", help="Add a new host configuration")
    add_parser.add_argument("alias", help="Host alias name (e.g. my-server)")
    add_parser.add_argument("-n", "--host-name", required=True, help="Host name or IP address (HostName)")
    add_parser.add_argument("-u", "--user", help="Username (User)")
    add_parser.add_argument("-p", "--port", help="Port number (Port)", default="22")
    add_parser.add_argument("-i", "--identity-file", help="Path to identity key file (IdentityFile)")
    add_parser.add_argument("-j", "--proxy-jump", help="Jump host server (ProxyJump)")
    add_parser.add_argument("-o", "--option", action="append", help="Extra custom options in Key=Value format")
    
    # Delete command
    del_parser = subparsers.add_parser("delete", help="Delete a host configuration")
    del_parser.add_argument("alias", help="Host alias name to delete")
    
    # Test command
    test_parser = subparsers.add_parser("test", help="Test connection to a host configuration")
    test_parser.add_argument("alias", help="Host alias name to test")
    
    args = parser.parse_args()
    
    config_path = Path(args.config)
    
    if args.command == "list":
        hosts = parse_config(config_path)
        list_hosts(hosts, test_conn=args.test)
    elif args.command == "add":
        add_host(args.alias, args, config_path)
    elif args.command == "delete":
        delete_host(args.alias, config_path)
    elif args.command == "test":
        test_host(args.alias, config_path)
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
