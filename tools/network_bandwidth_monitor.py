#!/usr/bin/env python3
"""
Network Bandwidth Monitor
A real-time terminal utility to monitor network traffic speed (upload/download)
and display a live ASCII bar chart and bandwidth usage statistics.
"""

import os
import sys
import time
import argparse
import platform
import subprocess
import re
from typing import Dict, Tuple, Optional

# Try importing psutil, but provide fallbacks
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

class BandwidthMonitor:
    def __init__(self):
        self.system = platform.system()
        self.last_time = time.time()
        self.last_in = 0
        self.last_out = 0
        self._initialize_counters()

    def _initialize_counters(self):
        """Get the initial bytes sent/received count."""
        in_bytes, out_bytes = self._get_io_bytes()
        self.last_in = in_bytes
        self.last_out = out_bytes
        self.last_time = time.time()

    def _get_io_bytes(self) -> Tuple[int, int]:
        """Fetch total bytes (received, sent) using the best available method."""
        if HAS_PSUTIL:
            try:
                io = psutil.net_io_counters()
                return io.bytes_recv, io.bytes_sent
            except Exception:
                pass
        
        # Fallback 1: Linux /proc/net/dev
        if self.system == "Linux":
            try:
                with open("/proc/net/dev", "r") as f:
                    lines = f.readlines()
                total_recv = 0
                total_sent = 0
                for line in lines[2:]:  # Skip headers
                    if ":" not in line:
                        continue
                    parts = line.split(":")[-1].split()
                    # index 0 is receive bytes, index 8 is transmit bytes
                    total_recv += int(parts[0])
                    total_sent += int(parts[8])
                return total_recv, total_sent
            except Exception:
                pass

        # Fallback 2: Windows netstat -e parsing
        if self.system == "Windows":
            try:
                # netstat -e displays Ethernet statistics (Received, Sent)
                output = subprocess.check_output("netstat -e", shell=True, text=True, errors="ignore")
                for line in output.splitlines():
                    line = line.strip().lower()
                    if line.startswith("bytes"):
                        parts = re.findall(r'\d+', line)
                        if len(parts) >= 2:
                            # parts[0] is Received, parts[1] is Sent
                            return int(parts[0]), int(parts[1])
            except Exception:
                pass

        # Fallback 3: macOS netstat -ib parsing
        if self.system == "Darwin":
            try:
                # netstat -ib displays interface statistics in bytes
                output = subprocess.check_output("netstat -ib", shell=True, text=True, errors="ignore")
                total_recv = 0
                total_sent = 0
                # Match fields from table columns
                for line in output.splitlines():
                    parts = line.split()
                    if len(parts) >= 10 and not line.startswith("Name"):
                        # In macOS netstat -ib: 
                        # columns generally have: Name, Mtu, Network, Address, Ipkts, Ierrs, Ibytes, Opkts, Oerrs, Obytes
                        try:
                            # Ibytes is usually index 6, Obytes is index 9
                            total_recv += int(parts[6])
                            total_sent += int(parts[9])
                        except ValueError:
                            continue
                if total_recv > 0:
                    return total_recv, total_sent
            except Exception:
                pass

        return 0, 0

    def get_speed(self) -> Tuple[float, float, float]:
        """Compute speed in bytes per second. Returns (download_speed, upload_speed, delta_time)."""
        current_time = time.time()
        curr_in, curr_out = self._get_io_bytes()
        
        dt = current_time - self.last_time
        if dt <= 0:
            dt = 0.1

        # Calculate bytes per second
        speed_in = (curr_in - self.last_in) / dt
        speed_out = (curr_out - self.last_out) / dt

        # Guard against system restarts or counter rollbacks
        if speed_in < 0: speed_in = 0
        if speed_out < 0: speed_out = 0

        self.last_in = curr_in
        self.last_out = curr_out
        self.last_time = current_time

        return speed_in, speed_out, dt

def format_speed(bytes_per_sec: float) -> str:
    """Format speed to a human-readable string."""
    kb = 1024
    mb = kb * 1024
    gb = mb * 1024
    
    if bytes_per_sec >= gb:
        return f"{bytes_per_sec / gb:.2f} GB/s"
    elif bytes_per_sec >= mb:
        return f"{bytes_per_sec / mb:.2f} MB/s"
    elif bytes_per_sec >= kb:
        return f"{bytes_per_sec / kb:.2f} KB/s"
    else:
        return f"{bytes_per_sec:.2f} B/s"

def make_bar(value: float, max_value: float, width: int = 25) -> str:
    """Generate an ASCII progress bar for live visual output."""
    if max_value <= 0:
        return "[" + " " * width + "]"
    
    fraction = min(value / max_value, 1.0)
    filled_len = int(width * fraction)
    bar = "=" * filled_len + " " * (width - filled_len)
    return f"[{bar}]"

def main():
    parser = argparse.ArgumentParser(description="Real-Time Network Bandwidth Monitor")
    parser.add_argument("-d", "--delay", type=float, default=1.0, help="Refresh interval in seconds (default: 1.0)")
    parser.add_argument("-c", "--count", type=int, default=0, help="Number of iterations to run (0 for infinite)")
    parser.add_argument("-m", "--max-scale", type=float, default=10.0, help="Max graph scale in MB/s (default: 10.0)")
    args = parser.parse_args()

    print("[*] Initializing Bandwidth Monitor...")
    if not HAS_PSUTIL:
        print("[!] Warning: 'psutil' module not found. Falling back to native OS utilities.")
        print("[i] To install psutil for better accuracy, run: pip install psutil\n")
    
    monitor = BandwidthMonitor()
    
    # Warm up
    time.sleep(0.5)
    monitor.get_speed()

    # Scaling for graphs
    max_scale_bytes = args.max_scale * 1024 * 1024
    
    peak_down = 0.0
    peak_up = 0.0
    total_down_bytes = 0.0
    total_up_bytes = 0.0
    
    iteration = 0
    
    print("\nPress Ctrl+C to stop.")
    print("=" * 60)
    print(f"{'DOWNLOAD':<28} | {'UPLOAD':<28}")
    print("=" * 60)

    try:
        while True:
            speed_down, speed_up, dt = monitor.get_speed()
            
            # Update stats
            if speed_down > peak_down: peak_down = speed_down
            if speed_up > peak_up: peak_up = speed_up
            
            total_down_bytes += speed_down * dt
            total_up_bytes += speed_up * dt

            # Format speeds
            down_str = format_speed(speed_down)
            up_str = format_speed(speed_up)
            
            # Build ASCII bar charts
            down_bar = make_bar(speed_down, max_scale_bytes)
            up_bar = make_bar(speed_up, max_scale_bytes)

            # Clear line and print dashboard
            # Using carriage return \r to overwrite lines in terminal
            sys.stdout.write("\r\033[K")  # Clear line ANSI escape code
            sys.stdout.write(f"▼ {down_str:<9} {down_bar} | ▲ {up_str:<9} {up_bar}")
            sys.stdout.flush()

            iteration += 1
            if args.count > 0 and iteration >= args.count:
                break
                
            time.sleep(args.delay)
    except KeyboardInterrupt:
        pass
    
    print("\n" + "=" * 60)
    print("--- Session Statistics Summary ---")
    print(f"Peak Download Speed:   {format_speed(peak_down)}")
    print(f"Peak Upload Speed:     {format_speed(peak_up)}")
    print(f"Total Downloaded:      {format_speed(total_down_bytes).replace('/s', '')}")
    print(f"Total Uploaded:        {format_speed(total_up_bytes).replace('/s', '')}")
    print("=" * 60)

if __name__ == "__main__":
    main()
