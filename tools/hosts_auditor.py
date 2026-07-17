#!/usr/bin/env python3
"""
Hosts File Syntax Auditor & Prober

A standalone utility to validate system hosts files.
1. Auto-detects local hosts file based on OS (Windows/Linux/macOS).
2. Audits syntax: validates IPv4/IPv6 formatting and hostname RFC 1123 compliance.
3. Flags duplicate mappings: multiple IPs for one host, or repeated definitions.
4. Hostness Prober: optionally ping-probes mapped hostnames via socket connection
   on HTTP/HTTPS ports (80/443) to check if they are responsive.

Usage:
    python hosts_auditor.py
    python hosts_auditor.py --file path_to_custom_hosts --probe
"""

import sys
import os
import argparse
import re
import socket

# Regex for IPv4 and IPv6 validation
IPV4_REGEX = re.compile(
    r'^(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)$'
)
IPV6_REGEX = re.compile(
    r'^(([0-9a-fA-F]{1,4}:){7,7}[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,7}:|([0-9a-fA-F]{1,4}:){1,6}:[0-9a-fA-F]{1,4}|([0-9a-fA-F]{1,4}:){1,5}(:[0-9a-fA-F]{1,4}){1,2}|([0-9a-fA-F]{1,4}:){1,4}(:[0-9a-fA-F]{1,4}){1,3}|([0-9a-fA-F]{1,4}:){1,3}(:[0-9a-fA-F]{1,4}){1,4}|([0-9a-fA-F]{1,4}:){1,2}(:[0-9a-fA-F]{1,4}){1,5}|[0-9a-fA-F]{1,4}:((:[0-9a-fA-F]{1,4}){1,6})|:((:[0-9a-fA-F]{1,4}){1,7}|:)|fe80:(:[0-9a-fA-F]{0,4}){0,4}%[0-9a-zA-Z]{1,}|::(ffff(:0{1,4}){0,1}:){0,1}((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])|([0-9a-fA-F]{1,4}:){1,4}:((25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9])\.){3,3}(25[0-5]|(2[0-4]|1{0,1}[0-9]){0,1}[0-9]))$'
)

# RFC 1123 Hostname validation (letters, numbers, hyphens, dots, <= 255 chars)
HOSTNAME_REGEX = re.compile(
    r'^([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])(\.([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]{0,61}[a-zA-Z0-9]))*$'
)

def get_default_hosts_path():
    """Returns the default system path of the hosts configuration file."""
    if os.name == 'nt':
        return os.path.join(os.environ.get('SystemRoot', 'C:\\Windows'), 'System32', 'drivers', 'etc', 'hosts')
    return '/etc/hosts'

def validate_ip(ip_str):
    """Validates if the IP is a valid IPv4 or IPv6 address."""
    return IPV4_REGEX.match(ip_str) is not None or IPV6_REGEX.match(ip_str) is not None

def validate_hostname(host_str):
    """Validates if the hostname conforms to RFC 1123 constraints."""
    if len(host_str) > 255:
        return False
    # Localhost exception or shorthand
    if host_str == 'localhost':
        return True
    return HOSTNAME_REGEX.match(host_str) is not None

def probe_hostname(host_str, timeout=2.0):
    """Probes if host is responsive by initiating a basic TCP connection to port 80/443."""
    for port in (80, 443):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            sock.connect((host_str, port))
            sock.close()
            return True, port
        except Exception:
            pass
    return False, None

def audit_hosts(filepath, probe=False):
    """Reads and audits the hosts file."""
    if not os.path.exists(filepath):
        print(f"Error: Hosts file '{filepath}' does not exist.", file=sys.stderr)
        return None

    errors = []
    warnings = []
    
    # Store records to find duplicates
    # hostname -> list of IPs mapped to it
    host_to_ips = {}
    # ip -> list of hostnames mapped to it
    ip_to_hosts = {}
    
    total_lines = 0
    record_lines = 0

    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        for line_idx, line in enumerate(f, 1):
            total_lines += 1
            line = line.strip()
            # Ignore empty lines and lines starting with comments
            if not line or line.startswith('#'):
                continue
                
            record_lines += 1
            
            # Split off inline comments
            clean_line = line.split('#', 1)[0].strip()
            parts = clean_line.split()
            
            if len(parts) < 2:
                errors.append(f"Line {line_idx}: Invalid format. Expected IP followed by hostname.")
                continue
                
            ip = parts[0]
            mapped_hosts = parts[1:]
            
            # Validate IP
            if not validate_ip(ip):
                errors.append(f"Line {line_idx}: Invalid IP address format '{ip}'.")
                
            # Validate Hostnames
            for host in mapped_hosts:
                if not validate_hostname(host):
                    errors.append(f"Line {line_idx}: Hostname '{host}' violates RFC 1123 naming rules.")
                    
                # Track duplicate hostname mapping to different IPs
                if host in host_to_ips:
                    if ip not in host_to_ips[host]:
                        host_to_ips[host].append(ip)
                        warnings.append(f"Line {line_idx}: Hostname '{host}' is mapped to multiple IPs: {host_to_ips[host]}.")
                else:
                    host_to_ips[host] = [ip]
                    
                # Track IP mapping to hostnames
                if ip in ip_to_hosts:
                    if host not in ip_to_hosts[ip]:
                        ip_to_hosts[ip].append(host)
                else:
                    ip_to_hosts[ip] = [host]

    print("Hosts File Syntax Auditor")
    print("=" * 70)
    print(f"Hosts Path   : {filepath}")
    print(f"Total Lines  : {total_lines}")
    print(f"Active Rules : {record_lines}")
    print("=" * 70)

    # Output syntax errors
    if errors:
        print("\033[91m[-] Syntax Errors Identified:\033[0m")
        for err in errors:
            print(f"  [!] {err}")
    else:
        try:
            print("\033[92m[✓] Hosts file syntax is clean.\033[0m")
        except UnicodeEncodeError:
            print("\033[92m[ok] Hosts file syntax is clean.\033[0m")

    # Output duplicate warnings
    if warnings:
        print("\n\033[93m[!] Configuration Warnings:\033[0m")
        for warn in warnings:
            print(f"  [*] {warn}")
    else:
        print("  No duplicate mapping conflicts found.")

    # Probe mapped hosts if requested
    if probe and host_to_ips:
        print("\n[Hostname Probing (HTTP/HTTPS ports 80/443)]")
        print("-" * 70)
        # Avoid probing local targets
        locals_set = {'localhost', '127.0.0.1', '::1', '0.0.0.0'}
        
        for host in sorted(host_to_ips.keys()):
            if host in locals_set or any(ip in locals_set for ip in host_to_ips[host]):
                # Skip local lookups
                continue
                
            print(f"  Probing {host:<30} ... ", end="")
            sys.stdout.flush()
            responsive, port = probe_hostname(host)
            if responsive:
                print(f"\033[92mResponsive (Port {port})\033[0m")
            else:
                print("\033[91mNo response\033[0m")
                
    print("=" * 70)
    return len(errors) == 0

def main():
    parser = argparse.ArgumentParser(
        description="Verify system hosts configs, check loopbacks, and probe mapped hostnames.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "-f", "--file",
        default=None,
        help="Path to hosts file. If omitted, resolves automatically based on OS."
    )
    
    parser.add_argument(
        "-p", "--probe",
        action="store_true",
        help="Probe non-local hostnames via TCP socket to verify connectivity."
    )
    
    args = parser.parse_args()
    
    hosts_path = args.file if args.file else get_default_hosts_path()
    
    success = audit_hosts(hosts_path, args.probe)
    if not success:
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
