#!/usr/bin/env python3
"""
wifi_password_retriever - Retrieve saved Wi-Fi profiles and passwords

A cross-platform utility to view stored Wi-Fi connection configurations
and recover passwords for previously connected networks. Supports Windows,
macOS, and Linux (NetworkManager).

Usage:
    python tools/wifi_password_retriever.py [options]

Options:
    -h, --help            Show this help message and exit
    -s QUERY, --search QUERY
                          Search/filter profiles matching a query string
    -e FILE, --export FILE
                          Export profiles and credentials to a file (JSON or CSV format)
    -p, --no-passwords    List SSIDs/profile names only without fetching passwords
    -v, --verbose         Output detailed debugging info

Note:
    Depending on your OS settings, retrieving passwords may require running this
    tool from an elevated command prompt (Administrator on Windows, or sudo on macOS/Linux).
"""

import argparse
import csv
import json
import os
import re
import subprocess
import sys

def run_cmd(command):
    """Safely run a system command and return stdout/stderr."""
    try:
        # Use shell=True only on Windows if it is a list of commands, otherwise keep shell=False
        # Since we use simple string arrays, shell=False is safer.
        res = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8',
            errors='ignore',
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
        )
        return res.stdout, res.stderr, res.returncode
    except Exception as e:
        return "", str(e), -1

def get_windows_wifi():
    """Extract Wi-Fi passwords on Windows using netsh."""
    profiles = []
    
    # 1. Get profile names
    out, err, code = run_cmd(["netsh", "wlan", "show", "profiles"])
    if code != 0:
        return None, f"Failed to retrieve profiles. Error: {err or 'Unknown'}"
        
    names = re.findall(r"(?:All User Profile|User Profile)\s*:\s*(.*)", out)
    profile_names = [n.strip() for n in names]
    
    for name in profile_names:
        profile_info = {"ssid": name, "password": None, "auth": "Unknown"}
        
        # 2. Get profile details including key
        detail_out, _, _ = run_cmd(["netsh", "wlan", "show", "profile", f"name={name}", "key=clear"])
        
        # Parse security type
        auth_match = re.search(r"Authentication\s*:\s*(.*)", detail_out)
        if auth_match:
            profile_info["auth"] = auth_match.group(1).strip()
            
        # Parse password
        pass_match = re.search(r"Key Content\s*:\s*(.*)", detail_out)
        if pass_match:
            profile_info["password"] = pass_match.group(1).strip()
        else:
            # Check if security is none/open
            if "Present" not in re.findall(r"Security key\s*:\s*(.*)", detail_out):
                profile_info["password"] = "[Open/No Password]"
                
        profiles.append(profile_info)
        
    return profiles, None

def get_macos_wifi():
    """Extract Wi-Fi passwords on macOS using security tool and networksetup."""
    profiles = []
    
    # 1. Get hardware ports to confirm Wi-Fi device name (usually en0)
    out, err, code = run_cmd(["networksetup", "-listallhardwareports"])
    if code != 0:
        return None, f"Failed to list network hardware: {err}"
        
    wifi_device = None
    parts = out.split("Hardware Port: ")
    for part in parts:
        if "Wi-Fi" in part or "AirPort" in part:
            dev_match = re.search(r"Device:\s*(\w+)", part)
            if dev_match:
                wifi_device = dev_match.group(1)
                break
                
    if not wifi_device:
        wifi_device = "en0" # Fallback default
        
    # 2. Get preferred networks
    pref_out, _, _ = run_cmd(["networksetup", "-listpreferredwirelessnetworks", wifi_device])
    preferred = [line.strip() for line in pref_out.split('\n')[1:] if line.strip()]
    
    for ssid in preferred:
        profile_info = {"ssid": ssid, "password": None, "auth": "Unknown"}
        
        # 3. Retrieve security password from Keychain
        # macOS security tool will pop up a GUI prompt asking for root permissions unless run with sudo
        pass_out, pass_err, pass_code = run_cmd(["security", "find-generic-password", "-wa", ssid])
        if pass_code == 0:
            profile_info["password"] = pass_out.strip()
            profile_info["auth"] = "Keychain Saved"
        else:
            if "security: SecKeychainSearchCopyNext" in pass_err or "The specified item could not be found" in pass_err:
                profile_info["password"] = "[Not found or requires administrator access]"
            else:
                profile_info["password"] = "[Requires elevation (run with sudo)]"
                
        profiles.append(profile_info)
        
    return profiles, None

def get_linux_wifi():
    """Extract Wi-Fi passwords on Linux by parsing NetworkManager connection files."""
    profiles = []
    conn_dir = "/etc/NetworkManager/system-connections"
    
    if not os.path.exists(conn_dir):
        # Fallback to nmcli
        out, err, code = run_cmd(["nmcli", "-t", "-f", "NAME,UUID,TYPE", "connection", "show"])
        if code != 0:
            return None, "NetworkManager config directory not found and nmcli is unavailable."
            
        ssids = []
        for line in out.split('\n'):
            if not line.strip():
                continue
            parts = line.split(':')
            if len(parts) >= 3 and 'wifi' in parts[2]:
                ssids.append(parts[0])
                
        for ssid in ssids:
            profile_info = {"ssid": ssid, "password": None, "auth": "Unknown"}
            pass_out, _, pass_code = run_cmd(["nmcli", "-s", "-g", "802-11-wireless-security.psk", "connection", "show", ssid])
            if pass_code == 0 and pass_out.strip():
                profile_info["password"] = pass_out.strip()
                profile_info["auth"] = "WPA/WPA2"
            else:
                profile_info["password"] = "[Requires elevation (run with sudo)]"
            profiles.append(profile_info)
            
        return profiles, None

    # Parsing system-connections directory directly (requires root privileges)
    try:
        files = os.listdir(conn_dir)
    except PermissionError:
        return None, "Permission denied accessing connection files. Please re-run with sudo."
    except Exception as e:
        return None, f"Error accessing system-connections: {e}"

    for f_name in files:
        f_path = os.path.join(conn_dir, f_name)
        if not os.path.isfile(f_path):
            continue
            
        try:
            with open(f_path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
        except PermissionError:
            return None, "Permission denied reading connection files. Please re-run with sudo."
            
        ssid_match = re.search(r"id=(.*)", content)
        if not ssid_match:
            continue
            
        ssid = ssid_match.group(1).strip()
        profile_info = {"ssid": ssid, "password": None, "auth": "Unknown"}
        
        # Read security type
        sec_match = re.search(r"key-mgmt=(.*)", content)
        if sec_match:
            profile_info["auth"] = sec_match.group(1).strip()
            
        # Read password
        pass_match = re.search(r"psk=(.*)", content)
        if pass_match:
            profile_info["password"] = pass_match.group(1).strip()
        else:
            # Check if there is a password under [wifi-security]
            pass_match2 = re.search(r"password=(.*)", content)
            if pass_match2:
                profile_info["password"] = pass_match2.group(1).strip()
            elif "wep" in profile_info["auth"]:
                wep_match = re.search(r"wep-key0=(.*)", content)
                if wep_match:
                    profile_info["password"] = wep_match.group(1).strip()
            else:
                profile_info["password"] = "[Open/No Password]"
                
        profiles.append(profile_info)
        
    return profiles, None

def print_table(profiles):
    """Print profiles in a formatted terminal table."""
    if not profiles:
        print("No profiles found.")
        return
        
    # Calculate widths
    w_ssid = max(len(p["ssid"]) for p in profiles)
    w_ssid = max(w_ssid, 15)
    w_auth = max(len(p["auth"]) for p in profiles)
    w_auth = max(w_auth, 10)
    w_pass = max(len(str(p["password"] or '')) for p in profiles)
    w_pass = max(w_pass, 12)
    
    # Header
    print(f"+-{'-'*w_ssid}-+-{'-'*w_auth}-+-{'-'*w_pass}-+")
    print(f"| {'SSID/Network name':<{w_ssid}} | {'Security':<{w_auth}} | {'Password':<{w_pass}} |")
    print(f"+-{'-'*w_ssid}-+-{'-'*w_auth}-+-{'-'*w_pass}-+")
    
    for p in profiles:
        pwd = p["password"] or "[None]"
        print(f"| {p['ssid']:<{w_ssid}} | {p['auth']:<{w_auth}} | {pwd:<{w_pass}} |")
        
    print(f"+-{'-'*w_ssid}-+-{'-'*w_auth}-+-{'-'*w_pass}-+")

def main():
    parser = argparse.ArgumentParser(
        description="Retrieve saved Wi-Fi profiles and passwords. Supports Windows, macOS, and Linux."
    )
    parser.add_argument('-s', '--search', help='Search for a specific SSID pattern')
    parser.add_argument('-e', '--export', help='Export credentials into a file (ends in .json or .csv)')
    parser.add_argument('-p', '--no-passwords', action='store_true', help='Only list profiles, skip password fetching')
    parser.add_argument('-v', '--verbose', action='store_true', help='Enable verbose output')
    
    args = parser.parse_args()
    
    # Detect platform
    platform = sys.platform
    if args.verbose:
        print(f"Detected OS platform: {platform}")
        
    profiles = None
    err = None
    
    if platform.startswith("win"):
        profiles, err = get_windows_wifi()
    elif platform.startswith("darwin"):
        profiles, err = get_macos_wifi()
    elif platform.startswith("linux"):
        profiles, err = get_linux_wifi()
    else:
        print(f"Unsupported OS: {platform}. This tool only supports Windows, macOS, and Linux.", file=sys.stderr)
        return 1
        
    if err:
        print(f"Error: {err}", file=sys.stderr)
        if "Permission denied" in err or "sudo" in err:
            print("Tip: Run this command with administrator/sudo rights to read password files.", file=sys.stderr)
        return 1
        
    if not profiles:
        print("No Wi-Fi profiles found.", file=sys.stderr)
        return 0
        
    # Apply filters
    if args.search:
        pattern = re.compile(args.search, re.IGNORECASE)
        profiles = [p for p in profiles if pattern.search(p["ssid"])]
        if args.verbose:
            print(f"Filtered to {len(profiles)} profiles matching '{args.search}'")
            
    # Apply no-passwords option
    if args.no-passwords:
        for p in profiles:
            p["password"] = "[Hidden]"
            
    # Export
    if args.export:
        ext = os.path.splitext(args.export)[1].lower()
        try:
            write_mode = 'w'
            if ext == '.json':
                with open(args.export, write_mode, encoding='utf-8') as f:
                    json.dump(profiles, f, indent=4)
                print(f"Successfully exported data to {args.export}")
            elif ext == '.csv':
                with open(args.export, write_mode, newline='', encoding='utf-8') as f:
                    writer = csv.writer(f)
                    writer.writerow(["SSID", "Security Type", "Password"])
                    for p in profiles:
                        writer.writerow([p["ssid"], p["auth"], p["password"]])
                print(f"Successfully exported data to {args.export}")
            else:
                print(f"Error: Unsupported export extension '{ext}'. Use .json or .csv", file=sys.stderr)
                return 1
        except Exception as e:
            print(f"Error exporting file: {e}", file=sys.stderr)
            return 1
    else:
        # Print results
        print_table(profiles)
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
