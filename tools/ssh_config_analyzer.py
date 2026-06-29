#!/usr/bin/env python3
"""
SSH Configuration Analyzer & Auditor

A tool to parse, visualize, and audit local SSH client configuration files 
(e.g., ~/.ssh/config). It resolves host aliases, visualizes the config as a 
connection tree, lists parameters, and audits configurations for security 
risks (such as weak ciphers, loose permissions, or missing key files).

Usage:
    python tools/ssh_config_analyzer.py
    python tools/ssh_config_analyzer.py -f ~/.ssh/config --audit
    python tools/ssh_config_analyzer.py --search my-server
"""

import argparse
import os
import re
import sys
from typing import Dict, List, Any, Tuple

# ANSI Colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_GRAY = "\033[90m"

def supports_color() -> bool:
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform or is_a_tty

def color_text(text: str, color_code: str) -> str:
    return f"{color_code}{text}{COLOR_RESET}" if supports_color() else text

def get_default_config_path() -> str:
    """Returns default SSH config file path based on OS."""
    home = os.path.expanduser("~")
    return os.path.join(home, ".ssh", "config")

def check_file_permissions(filepath: str) -> List[str]:
    """Audits file permissions on Unix-like operating systems."""
    warnings = []
    if sys.platform == "win32":
        # Windows file permission checks can be complex; skip simple stat checks.
        return warnings
        
    try:
        st = os.stat(filepath)
        mode = st.st_mode & 0o777
        # Config file should be 0600 or at least not group/world writable
        if mode & 0o022:
            warnings.append(f"Security Warning: {filepath} has loose permissions ({oct(mode)[2:]}). It should be 600 (read/write only by owner).")
    except Exception as e:
        warnings.append(f"Permission Check Error on {filepath}: {e}")
        
    return warnings

def parse_ssh_config(filepath: str, processed_files: set = None) -> List[Dict[str, Any]]:
    """Recursively parses SSH config files including Include statements."""
    if processed_files is None:
        processed_files = set()
        
    filepath = os.path.abspath(os.path.expanduser(filepath))
    if filepath in processed_files:
        return []  # Prevent cyclic loops
        
    processed_files.add(filepath)
    
    if not os.path.exists(filepath):
        return []
        
    configs = []
    current_host = None
    
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        for line_num, line in enumerate(f, 1):
            line_strip = line.strip()
            # Ignore empty lines and comments
            if not line_strip or line_strip.startswith("#"):
                continue
                
            # Split line into keyword and value (handle both spaces and equals signs)
            match = re.match(r"^(\w+)(?:\s+|=)(.+)$", line_strip)
            if not match:
                continue
                
            keyword, value = match.groups()
            keyword = keyword.lower()
            value = value.strip('"\'') # Strip quotes
            
            if keyword == "host":
                if current_host:
                    configs.append(current_host)
                # Host statement can define multiple patterns separated by space
                patterns = value.split()
                current_host = {
                    "patterns": patterns,
                    "options": {},
                    "source_file": filepath,
                    "line_number": line_num
                }
            elif keyword == "include" and not current_host:
                # Include directive (expand globs)
                import glob
                base_dir = os.path.dirname(filepath)
                include_path = os.path.expanduser(value)
                if not os.path.isabs(include_path):
                    include_path = os.path.join(base_dir, include_path)
                    
                for matched_file in glob.glob(include_path):
                    if os.path.isfile(matched_file):
                        configs.extend(parse_ssh_config(matched_file, processed_files))
            else:
                if current_host:
                    # Append options (keys are lowercased, multiple items (like IdentityFile) gathered as list)
                    if keyword in ["identityfile", "localforward", "remotefoward", "sendenv"]:
                        current_host["options"].setdefault(keyword, []).append(value)
                    else:
                        current_host["options"][keyword] = value
                        
        if current_host:
            configs.append(current_host)
            
    return configs

def audit_config(configs: List[Dict[str, Any]], filepath: str) -> List[str]:
    """Audits configurations for security risks and missing files."""
    warnings = []
    
    # Check parent config file permissions
    warnings.extend(check_file_permissions(filepath))
    
    # Audit hosts configurations
    for host in configs:
        patterns_str = ", ".join(host["patterns"])
        options = host["options"]
        
        # 1. Check IdentityFiles existence and permissions
        if "identityfile" in options:
            identity_files = options["identityfile"]
            for id_file in identity_files:
                # Expand environments/home dir
                expanded_path = os.path.abspath(os.path.expanduser(id_file))
                if not os.path.exists(expanded_path):
                    warnings.append(
                        f"Host [{patterns_str}] -> Missing IdentityFile: {id_file} (Checked path: {expanded_path})"
                    )
                else:
                    # Check private key permissions
                    key_perms_warnings = check_file_permissions(expanded_path)
                    for k_warn in key_perms_warnings:
                        warnings.append(f"Host [{patterns_str}] -> {k_warn}")
                        
        # 2. Check for weak encryption/ciphers
        if "ciphers" in options:
            ciphers = options["ciphers"].lower()
            weak_ciphers = ["3des", "arcfour", "blowfish", "cast128", "cbc"]
            found_weak = [c for c in weak_ciphers if c in ciphers]
            if found_weak:
                warnings.append(
                    f"Host [{patterns_str}] -> Security Warning: Insecure cipher(s) configured: {', '.join(found_weak)}"
                )
                
        # 3. Check for StrictHostKeyChecking disabled
        if "stricthostkeychecking" in options:
            val = options["stricthostkeychecking"].lower()
            if val in ["no", "off"]:
                warnings.append(
                    f"Host [{patterns_str}] -> Security Warning: StrictHostKeyChecking is disabled. This exposes you to MITM attacks."
                )
                
        # 4. Check for UserKnownHostsFile redirection to null
        if "userknownhostsfile" in options:
            val = options["userknownhostsfile"].lower()
            if "null" in val or "zero" in val:
                warnings.append(
                    f"Host [{patterns_str}] -> Security Warning: UserKnownHostsFile is redirected to null. Host signatures won't be saved or verified."
                )
                
    return warnings

def display_tree(configs: List[Dict[str, Any]]) -> None:
    """Prints a beautiful tree diagram of hosts."""
    print(color_text("SSH Configured Hosts Tree", COLOR_BOLD))
    print(color_text("=========================", COLOR_GRAY))
    
    if not configs:
        print("No hosts found.")
        return
        
    for host in configs:
        pattern_str = " | ".join(host["patterns"])
        options = host["options"]
        
        hostname = options.get("hostname", "N/A")
        user = options.get("user", "N/A")
        port = options.get("port", "22")
        
        print(f"├─ {color_text(pattern_str, COLOR_CYAN)}")
        print(f"│  ├─ HostName: {color_text(hostname, COLOR_GREEN)}")
        if user != "N/A":
            print(f"│  ├─ User:     {user}")
        if port != "22":
            print(f"│  ├─ Port:     {port}")
            
        for k, v in options.items():
            if k in ["hostname", "user", "port"]:
                continue
            if isinstance(v, list):
                for item in v:
                    print(f"│  ├─ {k}: {item}")
            else:
                print(f"│  ├─ {k}: {v}")
        print("│")
    print(color_text("└─ Done.", COLOR_GRAY))

def search_host(configs: List[Dict[str, Any]], query: str) -> None:
    """Searches for configs matching target query."""
    print(color_text(f"Searching for Host: {query}", COLOR_BOLD))
    print("--------------------------------------------------")
    
    found = False
    query = query.lower()
    
    for host in configs:
        # Check if query matches any pattern
        match = False
        for pattern in host["patterns"]:
            if query in pattern.lower():
                match = True
                break
                
        # Also check hostname
        hostname = host["options"].get("hostname", "").lower()
        if query in hostname:
            match = True
            
        if match:
            found = True
            pattern_str = ", ".join(host["patterns"])
            print(f"Found Host Pattern: {color_text(pattern_str, COLOR_CYAN)}")
            print(f"Defined in: {host['source_file']}:{host['line_number']}")
            for k, v in host["options"].items():
                if isinstance(v, list):
                    for item in v:
                        print(f"  {k:<20} {item}")
                else:
                    print(f"  {k:<20} {v}")
            print()
            
    if not found:
        print(color_text("No matching hosts found.", COLOR_RED))

def main() -> int:
    parser = argparse.ArgumentParser(description="SSH Client Configuration Auditor & Tree Visualizer.")
    parser.add_argument("-f", "--file", help="SSH Config file path (default: ~/.ssh/config)")
    parser.add_argument("-s", "--search", help="Find config options for a specific host by name/alias/pattern")
    parser.add_argument("-a", "--audit", action="store_true", help="Perform security audit and validation on configuration")
    parser.add_argument("-t", "--tree", action="store_true", help="Show configurations in a visual tree layout")
    
    args = parser.parse_args()
    
    config_file = args.file or get_default_config_path()
    if not os.path.exists(config_file):
        print(color_text(f"Error: SSH config file '{config_file}' not found.", COLOR_RED), file=sys.stderr)
        # Check if default path
        if not args.file:
            print(color_text("[*] Tips: Ensure OpenSSH is installed and you have defined a config file under ~/.ssh/config.", COLOR_CYAN))
        return 1
        
    print(color_text(f"[*] Parsing SSH Config: {config_file}", COLOR_YELLOW))
    configs = parse_ssh_config(config_file)
    
    if args.search:
        search_host(configs, args.search)
    elif args.audit:
        print(color_text("[*] Running Security and Link Audit...", COLOR_BOLD))
        warnings = audit_config(configs, config_file)
        if warnings:
            print(color_text(f"\n[!] Audit completed. Found {len(warnings)} issues:", COLOR_YELLOW))
            for warn in warnings:
                print(f"  - {color_text(warn, COLOR_RED)}")
            return 1
        else:
            print(color_text("\n[+] Audit completed. No configuration vulnerabilities or missing keys detected!", COLOR_GREEN))
    elif args.tree:
        display_tree(configs)
    else:
        # Default: print tree summary and brief audit check
        display_tree(configs)
        print()
        print(color_text("[*] Performing quick security audit check...", COLOR_BOLD))
        warnings = audit_config(configs, config_file)
        if warnings:
            print(color_text(f"[!] Warning: {len(warnings)} issues found. Run with --audit to inspect details.", COLOR_YELLOW))
        else:
            print(color_text("[+] Quick audit: No issues found.", COLOR_GREEN))
            
    return 0

if __name__ == "__main__":
    sys.exit(main())
