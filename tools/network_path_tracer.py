#!/usr/bin/env python3
"""
CLI Network Hop Tracer & Path Visualizer
Author: Antigravity

Performs network route tracing to a target host and renders a detailed
terminal-based path graph, showing hop latency, IP, and reverse DNS.
Platform-independent, wraps native system commands so it doesn't require root.
"""

import argparse
import os
import platform
import re
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

def parse_windows_line(line: str) -> Optional[Dict[str, any]]:
    """
    Parses a single line of Windows 'tracert' output.
    Example: '  1    <1 ms    <1 ms    <1 ms  192.168.1.1'
    Example: '  3     *        *        *     Request timed out.'
    """
    line = line.strip()
    if not line or not line[0].isdigit():
        return None

    # Pattern to match: Hop times IP/Hostname
    # Group 1: Hop index
    # Group 2, 3, 4: Latencies or '*'
    # Group 5: Rest of the line (IP / Hostname)
    pattern = r'^(\d+)\s+([\d<>\s]+ms|\*)\s+([\d<>\s]+ms|\*)\s+([\d<>\s]+ms|\*)\s+(.+)$'
    match = re.match(pattern, line)
    if not match:
        return None

    hop_num = int(match.group(1))
    times = [match.group(2).strip(), match.group(3).strip(), match.group(4).strip()]
    host_ip = match.group(5).strip()

    # Determine status and parse IP/Host
    if host_ip == "Request timed out.":
        host = "Timed Out"
        ip = "*"
    else:
        # Check if there is an IP in brackets: 'name [1.2.3.4]'
        bracket_match = re.search(r'\[([a-fA-F0-9\.:]+)\]', host_ip)
        if bracket_match:
            ip = bracket_match.group(1)
            host = host_ip.split('[')[0].strip()
        else:
            ip = host_ip
            host = host_ip

    # Convert times to floats or keep as '*'
    numeric_times = []
    for t in times:
        if t == "*":
            numeric_times.append(None)
        else:
            # Extract number
            t_num = re.sub(r'[^\d]', '', t)
            numeric_times.append(float(t_num) if t_num else 0.0)

    # Calculate average latency
    valid_times = [v for v in numeric_times if v is not None]
    avg_latency = sum(valid_times) / len(valid_times) if valid_times else None

    return {
        "hop": hop_num,
        "host": host,
        "ip": ip,
        "latencies": numeric_times,
        "avg": avg_latency
    }

def parse_posix_line(line: str) -> Optional[Dict[str, any]]:
    """
    Parses a single line of Linux/macOS 'traceroute' output.
    Example: ' 1  gateway (192.168.1.1)  0.345 ms  0.281 ms  0.260 ms'
    Example: ' 3  * * *'
    """
    line = line.strip()
    if not line or not line[0].isdigit():
        return None

    parts = line.split()
    if len(parts) < 2:
        return None

    try:
        hop_num = int(parts[0])
    except ValueError:
        return None

    # Handle fully timed out hops (e.g. '3  * * *' or similar)
    if all(p == "*" for p in parts[1:]):
        return {
            "hop": hop_num,
            "host": "Timed Out",
            "ip": "*",
            "latencies": [None, None, None],
            "avg": None
        }

    # Extract all latency figures (e.g. '0.345 ms')
    latencies = []
    # Find decimal floats followed by 'ms'
    time_matches = re.findall(r'(\d+(?:\.\d+)?)\s*ms', line)
    for m in time_matches:
        latencies.append(float(m))

    # Fill rest with None if less than 3
    while len(latencies) < 3:
        latencies.append(None)

    # Find IP/Hostnames in the line
    # Usually format is 'host (ip)' or just 'ip'
    host = "Unknown"
    ip = "*"
    
    # Exclude the hop number and look at the first few fields
    remaining_text = " ".join(parts[1:])
    ip_match = re.search(r'\(([^)]+)\)', remaining_text)
    
    if ip_match:
        ip = ip_match.group(1)
        host = remaining_text.split('(')[0].strip()
        # If host is just the IP, clean it up
        if host == ip:
            host = ""
    else:
        # Find anything that looks like an IP
        ip_candidates = re.findall(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b|\b[a-fA-F0-9:]+:[a-fA-F0-9:]+\b', remaining_text)
        if ip_candidates:
            ip = ip_candidates[0]
            host = parts[1] if parts[1] != ip else ""
        else:
            # Fallback
            if parts[1] != "*":
                host = parts[1]
                ip = parts[1]

    # Calculate average
    valid_times = [v for v in latencies if v is not None]
    avg_latency = sum(valid_times) / len(valid_times) if valid_times else None

    return {
        "hop": hop_num,
        "host": host or ip,
        "ip": ip,
        "latencies": latencies,
        "avg": avg_latency
    }

def print_hop_node(hop_info: Dict[str, any], is_last: bool = False):
    """Renders a beautiful ASCII node for the network path."""
    prefix = "└──" if is_last else "├──"
    
    hop_str = f"[{hop_info['hop']:2d}]"
    
    if hop_info["host"] == "Timed Out":
        node_str = "\033[91m* * * (Request Timed Out)\033[0m"
    else:
        host_part = f"\033[92m{hop_info['host']}\033[0m"
        ip_part = f"({hop_info['ip']})" if hop_info['ip'] != hop_info['host'] else ""
        
        # Format latency
        if hop_info["avg"] is not None:
            lat_color = "\033[94m" if hop_info["avg"] < 50 else "\033[93m" if hop_info["avg"] < 150 else "\033[91m"
            lat_part = f"{lat_color}{hop_info['avg']:.1f} ms\033[0m"
        else:
            lat_part = "\033[90mN/A\033[0m"
            
        node_str = f"{host_part} {ip_part} - {lat_part}"

    print(f" {prefix} {hop_str} {node_str}")

def run_traceroute(target: str, max_hops: int = 30):
    """Executes platform-specific traceroute and prints the visual tree output."""
    system = platform.system().lower()
    
    print(f"Tracing network route to: \033[1m{target}\033[0m (Max Hops: {max_hops})")
    print(f"Platform: {platform.system()} | Method: Wrapping native commands")
    print("\n[Start]")
    
    if system == "windows":
        cmd = ["tracert", "-d", "-h", str(max_hops), target]
        parser = parse_windows_line
    else:
        # Use -n to avoid DNS resolution delay inside traceroute; we can do resolving natively or keep it default
        cmd = ["traceroute", "-m", str(max_hops), target]
        parser = parse_posix_line
        
    try:
        # Start subprocess and pipe output
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        
        hops_logged = []
        
        for line in process.stdout:
            # Echo original line if verbose or debug (commented out by default)
            # print(f"DEBUG: {line.strip()}")
            
            hop_data = parser(line)
            if hop_data:
                hops_logged.append(hop_data)
                # Print real-time ASCII node
                print_hop_node(hop_data, is_last=False)
                
        process.wait()
        
        # Print final endpoint if traceroute completed
        if hops_logged:
            # Overwrite last line with endpoint terminator
            print(" [Done]")
        else:
            print("\nError: No hop data parsed. Please check if traceroute is installed and target is reachable.")
            
    except FileNotFoundError:
        print(f"\nError: Native command for route tracing not found on this system.", file=sys.stderr)
        if system == "windows":
            print("Make sure 'tracert' is in your PATH.", file=sys.stderr)
        else:
            print("Please install 'traceroute' (e.g. apt install traceroute / brew install traceroute).", file=sys.stderr)
    except Exception as e:
        print(f"\nAn error occurred: {e}", file=sys.stderr)

def main():
    # Force ANSI color codes on Windows Command Prompt if needed
    if platform.system().lower() == "windows":
        os.system("color")
        
    parser = argparse.ArgumentParser(
        description="CLI Network Hop Tracer & Path Visualizer - Trace network paths in a pretty tree format."
    )
    parser.add_argument("target", help="Target hostname or IP address (e.g. google.com, 8.8.8.8)")
    parser.add_argument("-m", "--max-hops", type=int, default=30, help="Maximum number of hops (default: 30)")
    
    args = parser.parse_args()
    
    run_traceroute(args.target, args.max_hops)

if __name__ == "__main__":
    main()
