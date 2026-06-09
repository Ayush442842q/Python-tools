#!/usr/bin/env python3
"""
Ping Monitor & Latency Tracker

Monitors the latency and uptime of one or more hosts by executing periodic ping commands.
Displays real-time statistics (min, max, average latency, and packet loss).

Usage:
    python tools/ping_monitor.py google.com github.com [--interval 2] [--count 0]
"""

import argparse
import os
import platform
import re
import subprocess
import sys
import time

def parse_ping_output(output, system):
    """Extract round-trip time latency (ms) from ping stdout."""
    # Match latency patterns e.g. "time=23.4 ms" or "time<1ms" or "Average = 23ms"
    # Windows: Minimum = 11ms, Maximum = 12ms, Average = 11ms
    # Unix: rtt min/avg/max/mdev = 10.9/11.5/12.1/0.5 ms
    
    output = output.lower()
    
    if system == "windows":
        # Look for Average = Xms or time=Xms
        match = re.search(r'average\s*=\s*(\d+)ms', output)
        if match:
            return float(match.group(1))
        # Look for time=Xms or time<Xms
        match = re.search(r'time[=<]\s*(\d+)ms', output)
        if match:
            return float(match.group(1))
    else:
        # Unix/macOS
        # Look for time=X.Y ms or rtt min/avg/max/mdev = A/B/C/D
        match = re.search(r'time=(\d+\.?\d*)\s*ms', output)
        if match:
            return float(match.group(1))
        match = re.search(r'rtt\s+min/avg/max.*?=\s*\d+\.?\d*/(\d+\.?\d*)/', output)
        if match:
            return float(match.group(1))
            
    return None

def ping_host(host, system):
    """Executes a single ping command to the host."""
    # Use 1 request, timeout of 2 seconds
    if system == "windows":
        cmd = ["ping", "-n", "1", "-w", "2000", host]
    else:
        cmd = ["ping", "-c", "1", "-W", "2", host]

    try:
        startupinfo = None
        if system == "windows":
            # Prevent console window from popping up if run inside GUI apps
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            
        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            startupinfo=startupinfo,
            timeout=3
        )
        
        if proc.returncode == 0:
            latency = parse_ping_output(proc.stdout, system)
            if latency is not None:
                return True, latency
            # Fallback if return code was 0 but parse failed
            return True, 0.0
        return False, None
    except (subprocess.TimeoutExpired, Exception):
        return False, None

def print_status_table(hosts_data):
    """Prints a clean, formatted text table of the current stats."""
    # Clear screen (optional, let's just use carriage return or print block)
    # Using ansi escape to clean terminal could be noisy, so we print a clear block
    print("\n" + "=" * 80)
    print(f"{'HOST':<25} | {'SENT':<6} | {'RECV':<6} | {'LOSS':<6} | {'MIN (ms)':<8} | {'AVG (ms)':<8} | {'MAX (ms)':<8} | {'STATUS'}")
    print("-" * 80)
    
    for host, data in hosts_data.items():
        loss_pct = 0.0
        if data['sent'] > 0:
            loss_pct = ((data['sent'] - data['recv']) / data['sent']) * 100
            
        loss_str = f"{loss_pct:.1f}%"
        min_str = f"{data['min']:.1f}" if data['min'] != float('inf') else "-"
        max_str = f"{data['max']:.1f}" if data['max'] != 0.0 else "-"
        
        avg = 0.0
        if data['recv'] > 0:
            avg = data['sum_lat'] / data['recv']
        avg_str = f"{avg:.1f}" if data['recv'] > 0 else "-"
        
        status = "🟢 ONLINE" if data['last_ok'] else "🔴 OFFLINE"
        if data['sent'] == 0:
            status = "PENDING"
            
        print(f"{host:<25} | {data['sent']:<6} | {data['recv']:<6} | {loss_str:<6} | {min_str:<8} | {avg_str:<8} | {max_str:<8} | {status}")
    print("=" * 80)

def main():
    parser = argparse.ArgumentParser(description="Monitor latency and packet loss of multiple hosts in real-time.")
    parser.add_argument('hosts', nargs='+', help='One or more hostnames or IP addresses to monitor')
    parser.add_argument('-i', '--interval', type=float, default=2.0, help='Ping interval in seconds (default: 2.0)')
    parser.add_argument('-c', '--count', type=int, default=0, help='Number of ping cycles (0 for infinite, default: 0)')
    args = parser.parse_args()

    system = platform.system().lower()
    
    # Initialize stats dict for each host
    hosts_data = {}
    for host in args.hosts:
        hosts_data[host] = {
            'sent': 0,
            'recv': 0,
            'min': float('inf'),
            'max': 0.0,
            'sum_lat': 0.0,
            'last_ok': True
        }

    print(f"Ping Monitor started. Monitoring {len(args.hosts)} host(s)...")
    print("Press Ctrl+C to stop.")
    
    cycle = 0
    try:
        while True:
            cycle += 1
            for host in args.hosts:
                hosts_data[host]['sent'] += 1
                success, latency = ping_host(host, system)
                
                if success:
                    hosts_data[host]['recv'] += 1
                    hosts_data[host]['last_ok'] = True
                    hosts_data[host]['sum_lat'] += latency
                    if latency < hosts_data[host]['min']:
                        hosts_data[host]['min'] = latency
                    if latency > hosts_data[host]['max']:
                        hosts_data[host]['max'] = latency
                else:
                    hosts_data[host]['last_ok'] = False
                    
            print_status_table(hosts_data)
            
            if args.count > 0 and cycle >= args.count:
                break
                
            time.sleep(args.interval)
            
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user.")
        
    print("\nFinal statistics summary:")
    print_status_table(hosts_data)
    return 0

if __name__ == "__main__":
    sys.exit(main())
