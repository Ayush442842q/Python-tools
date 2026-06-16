#!/usr/bin/env python3
"""
Process Resource Profiler & ASCII Chart Maker

Profiles a command or monitors an existing PID, tracking its CPU and memory 
usage over time, and displays a summary and a beautiful terminal ASCII chart.

Usage:
    python tools/process_profiler.py --command "python tools/pomodoro_timer.py --work 1" --interval 0.5
    python tools/process_profiler.py --pid 1234 --duration 10 --interval 1.0
"""

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from typing import List, Dict, Any, Tuple, Optional

# Attempt to import psutil for high accuracy; fall back to system commands if missing
HAS_PSUTIL = False
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    pass

# ANSI Colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"

def supports_color() -> bool:
    """Checks if terminal supports colors."""
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform or is_a_tty

def color_text(text: str, color_code: str) -> str:
    """Wraps text in color codes if supported."""
    return f"{color_code}{text}{COLOR_RESET}" if supports_color() else text

def get_process_stats_fallback(pid: int) -> Tuple[float, float]:
    """Fallback method using system-level CLI tools when psutil is not available."""
    sys_type = platform.system()
    
    if sys_type == "Windows":
        # Querying CimInstance for CPU and working set (private bytes)
        cmd = ["powershell", "-NoProfile", "-Command", 
               f"Get-CimInstance Win32_PerfFormattedData_PerfProc_Process | Where-Object {{ $_.IDProcess -eq {pid} }} | Select-Object -Property PercentProcessorTime, WorkingSetPrivate | ConvertTo-Json"]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=2)
            if res.returncode == 0 and res.stdout.strip():
                data = json.loads(res.stdout)
                if isinstance(data, list) and len(data) > 0:
                    data = data[0]
                cpu = float(data.get("PercentProcessorTime", 0) or 0)
                mem_bytes = int(data.get("WorkingSetPrivate", 0) or 0)
                mem_mb = mem_bytes / (1024 * 1024)
                return cpu, mem_mb
        except Exception:
            pass
            
        # Hard fallback to tasklist (memory only)
        try:
            cmd2 = ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"]
            res2 = subprocess.run(cmd2, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res2.returncode == 0 and res2.stdout.strip():
                parts = res2.stdout.split(",")
                if len(parts) >= 5:
                    mem_str = parts[4].replace('"', '').replace(' K', '').replace(',', '').strip()
                    mem_mb = int(mem_str) / 1024.0
                    return 0.0, mem_mb
        except Exception:
            pass
            
    else:
        # Unix/macOS fallback using ps
        try:
            cmd = ["ps", "-p", str(pid), "-o", "%cpu,rss"]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            if res.returncode == 0:
                lines = res.stdout.strip().splitlines()
                if len(lines) > 1:
                    parts = lines[1].strip().split()
                    if len(parts) >= 2:
                        cpu = float(parts[0])
                        mem_mb = float(parts[1]) / 1024.0 # rss is in KB
                        return cpu, mem_mb
        except Exception:
            pass
            
    return 0.0, 0.0

def get_process_stats(pid: int) -> Tuple[float, float]:
    """Retrieves CPU percent and private memory usage (MB) for a PID."""
    if HAS_PSUTIL:
        try:
            p = psutil.Process(pid)
            cpu = p.cpu_percent(interval=None)
            mem_info = p.memory_info()
            mem_mb = mem_info.rss / (1024 * 1024)
            return cpu, mem_mb
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0.0, 0.0
    else:
        return get_process_stats_fallback(pid)

def draw_ascii_chart(data: List[float], title: str, unit: str, width: int = 50, height: int = 8) -> None:
    """Draws a beautiful text-based ASCII line chart for the collected stats."""
    if not data:
        print(f"No data available to plot {title}.")
        return
        
    min_val = min(data)
    max_val = max(data)
    val_range = max_val - min_val
    if val_range == 0:
        val_range = 1.0
        
    # Fit data to the chart width
    scaled_data = []
    if len(data) > width:
        for i in range(width):
            idx = int(i * len(data) / width)
            scaled_data.append(data[idx])
    else:
        scaled_data = data
        
    actual_width = len(scaled_data)
    grid = [[" " for _ in range(actual_width)] for _ in range(height)]
    
    # Plot points
    for x, val in enumerate(scaled_data):
        y = int((val - min_val) / val_range * (height - 1))
        y = max(0, min(height - 1, y))
        grid[height - 1 - y][x] = "█"
        
    print(color_text(f"\n--- {title} Chart ({unit}) ---", COLOR_BOLD))
    for row in range(height):
        # Calculate Y-axis value
        y_val = min_val + (height - 1 - row) / (height - 1) * val_range
        label = f"{y_val:6.1f} | "
        row_str = "".join(grid[row])
        # Colorize plot
        row_str = color_text(row_str, COLOR_GREEN if "cpu" in title.lower() else COLOR_CYAN)
        print(label + row_str)
        
    print(" " * 6 + "+" + "-" * actual_width)
    print(" " * 6 + f"Start{' ' * (actual_width - 9)}End")

def profile_process(
    pid: int,
    duration: Optional[float],
    interval: float,
    proc_handle: Optional[subprocess.Popen] = None
) -> Tuple[List[float], List[float]]:
    """Monitors the process resources until it exits or duration is exceeded."""
    cpu_samples = []
    mem_samples = []
    
    # Initialize CPU measurement (first call is often zero or inaccurate)
    get_process_stats(pid)
    time.sleep(0.1)
    
    start_time = time.time()
    
    print(color_text(f"Profiling PID {pid} (Interval: {interval}s)... Press Ctrl+C to stop.", COLOR_YELLOW))
    
    try:
        while True:
            # Check if subprocess has finished
            if proc_handle and proc_handle.poll() is not None:
                print(color_text("\nSubprocess completed.", COLOR_GREEN))
                break
                
            # Check if target PID is still alive
            if not proc_handle:
                # Simple check for active PID
                try:
                    if platform.system() == "Windows":
                        # Windows pid checks
                        res = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], stdout=subprocess.PIPE, text=True)
                        if f"{pid}" not in res.stdout:
                            print(color_text("\nTarget process stopped.", COLOR_GREEN))
                            break
                    else:
                        os.kill(pid, 0)
                except OSError:
                    print(color_text("\nTarget process stopped.", COLOR_GREEN))
                    break
                    
            cpu, mem = get_process_stats(pid)
            cpu_samples.append(cpu)
            mem_samples.append(mem)
            
            elapsed = time.time() - start_time
            print(f" Elapsed: {elapsed:5.1f}s | CPU: {cpu:5.1f}% | Mem: {mem:6.1f} MB", end="\r")
            
            if duration and elapsed >= duration:
                print(color_text("\nDuration threshold reached.", COLOR_GREEN))
                break
                
            time.sleep(interval)
    except KeyboardInterrupt:
        print(color_text("\nProfiling interrupted by user.", COLOR_RED))
        
    return cpu_samples, mem_samples

def print_stats(samples: List[float], name: str, unit: str) -> None:
    """Prints summary statistics of samples."""
    if not samples:
        return
    avg = sum(samples) / len(samples)
    print(f"  {color_text(name, COLOR_CYAN):<15} Min: {min(samples):6.2f} {unit} | Max: {max(samples):6.2f} {unit} | Avg: {avg:6.2f} {unit}")

def main() -> int:
    parser = argparse.ArgumentParser(description="Process Resource Profiler & ASCII Chart Maker")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--command', '-c', help="Command string to launch and profile (e.g. 'python tools/pomodoro_timer.py')")
    group.add_argument('--pid', '-p', type=int, help="Existing Process ID (PID) to monitor")
    
    parser.add_argument('--interval', '-i', type=float, default=1.0, help="Sampling interval in seconds (default: 1.0)")
    parser.add_argument('--duration', '-d', type=float, help="Max profiling duration in seconds")
    
    args = parser.parse_args()
    
    proc = None
    pid = None
    
    if args.command:
        try:
            # Launch command in subprocess
            # Use shell=True to parse complex commands correctly
            proc = subprocess.Popen(args.command, shell=True)
            pid = proc.pid
            print(f"Launched process with PID: {pid}")
        except Exception as e:
            print(f"Error launching command: {e}", file=sys.stderr)
            return 1
    else:
        pid = args.pid
        
    # Start profiling loop
    cpu_data, mem_data = profile_process(pid, args.duration, args.interval, proc)
    
    # Ensure subprocess is terminated if it was launched by us and is still running
    if proc and proc.poll() is None:
        print("Terminating monitored process...")
        proc.terminate()
        try:
            proc.wait(timeout=2)
        except subprocess.TimeoutExpired:
            proc.kill()
            
    # Print Results
    print(color_text("\n=== Profiling Summary ===", COLOR_BOLD))
    print_stats(cpu_data, "CPU Usage", "%")
    print_stats(mem_data, "Memory Usage", "MB")
    
    # Draw charts
    if len(cpu_data) > 1:
        draw_ascii_chart(cpu_data, "CPU Utilization", "%")
        draw_ascii_chart(mem_data, "Memory Working Set", "MB")
    else:
        print("\nNot enough data points collected to display charts.")
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
