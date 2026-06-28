#!/usr/bin/env python3
"""
CLI Interactive System Dashboard

A real-time, terminal-based resource monitor that displays live-updating CPU usage,
memory footprint, disk space, and process list. Zero external dependencies (uses platform
built-ins with an optional psutil integration for higher resolution metrics).

Usage:
    python tools/cli_system_dashboard.py [options]
"""

import sys
import os
import time
import platform
import subprocess
import argparse

# Try importing psutil for high-fidelity metrics
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

# Terminal colors
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"

def clear_screen():
    # Move cursor to home and clear screen
    sys.stdout.write("\033[H\033[2J")
    sys.stdout.flush()

def get_cpu_usage():
    """Gets total CPU usage percentage."""
    if HAS_PSUTIL:
        return psutil.cpu_percent(interval=None)
    
    # Fallbacks
    system = platform.system()
    if system == "Windows":
        try:
            # Fast Powershell call
            cmd = ["powershell", "-NoProfile", "-Command", "Get-CimInstance Win32_Processor | Select-Object -ExpandProperty LoadPercentage"]
            out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode("utf-8").strip()
            # If loadpercentage lists multiple cores, return average
            vals = [int(v) for v in out.split() if v.isdigit()]
            return sum(vals) / len(vals) if vals else 0.0
        except Exception:
            return 0.0
    elif system == "Linux":
        try:
            # Calculate from /proc/stat
            with open("/proc/stat", "r") as f:
                line = f.readline()
            parts = line.split()
            # CPU fields: user, nice, system, idle, iowait, irq, softirq
            cpu_times = [float(x) for x in parts[1:8]]
            idle = cpu_times[3] + cpu_times[4]
            total = sum(cpu_times)
            time.sleep(0.1) # Brief sleep to measure delta
            with open("/proc/stat", "r") as f:
                line = f.readline()
            parts = line.split()
            cpu_times2 = [float(x) for x in parts[1:8]]
            idle2 = cpu_times2[3] + cpu_times2[4]
            total2 = sum(cpu_times2)
            
            diff_idle = idle2 - idle
            diff_total = total2 - total
            if diff_total > 0:
                return ((diff_total - diff_idle) / diff_total) * 100
            return 0.0
        except Exception:
            return 0.0
    elif system == "Darwin": # macOS
        try:
            cmd = "top -l 1 -n 0 | grep 'CPU usage'"
            out = subprocess.check_output(cmd, shell=True).decode("utf-8")
            # Sample: "CPU usage: 8.23% user, 10.34% sys, 81.43% idle"
            for p in out.split(","):
                if "user" in p:
                    user_pct = float(p.split("%")[0].split()[-1])
                if "sys" in p:
                    sys_pct = float(p.split("%")[0].split()[-1])
            return user_pct + sys_pct
        except Exception:
            return 0.0
    return 0.0

def get_memory_usage():
    """Gets memory details (total, used, percentage)."""
    if HAS_PSUTIL:
        mem = psutil.virtual_memory()
        return mem.total, mem.used, mem.percent
        
    system = platform.system()
    if system == "Windows":
        try:
            # Query wmic
            cmd = ["wmic", "OS", "get", "FreePhysicalMemory,TotalVisibleMemorySize", "/value"]
            out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode("utf-8")
            data = {}
            for line in out.splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    data[k.strip()] = int(v.strip())
            total_kb = data.get("TotalVisibleMemorySize", 0)
            free_kb = data.get("FreePhysicalMemory", 0)
            used_kb = total_kb - free_kb
            pct = (used_kb / total_kb) * 100 if total_kb > 0 else 0.0
            return total_kb * 1024, used_kb * 1024, pct
        except Exception:
            return 0, 0, 0.0
    elif system == "Linux":
        try:
            mem_info = {}
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        mem_info[parts[0].strip()] = int(parts[1].split()[0])
            total = mem_info.get("MemTotal", 0) * 1024
            free = mem_info.get("MemFree", 0) * 1024
            buffers = mem_info.get("Buffers", 0) * 1024
            cached = mem_info.get("Cached", 0) * 1024
            used = total - free - buffers - cached
            pct = (used / total) * 100 if total > 0 else 0.0
            return total, used, pct
        except Exception:
            return 0, 0, 0.0
    elif system == "Darwin":
        try:
            # Extract total memory using sysctl
            total = int(subprocess.check_output(["sysctl", "-n", "hw.memsize"]).decode("utf-8").strip())
            # Extract vm_stat details for usage calculation
            vm_stat = subprocess.check_output(["vm_stat"]).decode("utf-8")
            page_size = 4096  # Standard size
            free_pages = 0
            active_pages = 0
            for line in vm_stat.splitlines():
                if "page size of" in line:
                    page_size = int(line.split()[-2])
                if "Pages free" in line:
                    free_pages = int(line.split()[-1].strip("."))
                if "Pages active" in line:
                    active_pages = int(line.split()[-1].strip("."))
            free = free_pages * page_size
            used = total - free
            pct = (used / total) * 100 if total > 0 else 0.0
            return total, used, pct
        except Exception:
            return 0, 0, 0.0
    return 0, 0, 0.0

def get_disk_usage():
    """Gets disk details for root/primary partition."""
    if HAS_PSUTIL:
        d = psutil.disk_usage("/")
        return d.total, d.used, d.percent
        
    system = platform.system()
    if system == "Windows":
        try:
            cmd = ["wmic", "logicaldisk", "where", "DeviceID='C:'", "get", "FreeSpace,Size", "/value"]
            out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode("utf-8")
            data = {}
            for line in out.splitlines():
                if "=" in line:
                    k, v = line.split("=", 1)
                    data[k.strip()] = int(v.strip())
            total = data.get("Size", 0)
            free = data.get("FreeSpace", 0)
            used = total - free
            pct = (used / total) * 100 if total > 0 else 0.0
            return total, used, pct
        except Exception:
            return 0, 0, 0.0
    else: # Unix
        try:
            st = os.statvfs("/")
            total = st.f_blocks * st.f_frsize
            free = st.f_bavail * st.f_frsize
            used = total - free
            pct = (used / total) * 100 if total > 0 else 0.0
            return total, used, pct
        except Exception:
            return 0, 0, 0.0

def get_processes():
    """Gets list of top resource-consuming processes (name, memory)."""
    processes = []
    if HAS_PSUTIL:
        # Get top 8 processes by memory
        for p in psutil.process_iter(["pid", "name", "memory_percent", "cpu_percent"]):
            try:
                processes.append({
                    "pid": p.info["pid"],
                    "name": p.info["name"],
                    "mem": p.info["memory_percent"] or 0.0,
                    "cpu": p.info["cpu_percent"] or 0.0
                })
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        processes.sort(key=lambda x: x["mem"], reverse=True)
        return processes[:8]

    # Fallback process listing
    system = platform.system()
    if system == "Windows":
        try:
            # Call tasklist
            out = subprocess.check_output(["tasklist", "/NH", "/FO", "CSV"]).decode("utf-8")
            for line in out.splitlines():
                if not line.strip():
                    continue
                # Row format: "Name","PID","SessionName","Session#","MemUsage"
                row = [r.strip('"') for r in line.split(",")]
                if len(row) >= 5:
                    name = row[0]
                    pid = int(row[1]) if row[1].isdigit() else 0
                    mem_str = row[4].replace(" K", "").replace(",", "")
                    mem_kb = int(mem_str) if mem_str.isdigit() else 0
                    processes.append({
                        "pid": pid,
                        "name": name,
                        "mem": mem_kb / 1024,  # Rough MB estimation
                        "cpu": 0.0
                    })
            processes.sort(key=lambda x: x["mem"], reverse=True)
            return processes[:8]
        except Exception:
            pass
    else: # Unix ps
        try:
            out = subprocess.check_output(["ps", "-eo", "pid,%mem,%cpu,comm", "-r"]).decode("utf-8")
            lines = out.splitlines()[1:]  # Skip header
            for line in lines:
                parts = line.split()
                if len(parts) >= 4:
                    pid = int(parts[0])
                    mem = float(parts[1])
                    cpu = float(parts[2])
                    name = " ".join(parts[3:])
                    processes.append({
                        "pid": pid,
                        "name": os.path.basename(name),
                        "mem": mem,
                        "cpu": cpu
                    })
            processes.sort(key=lambda x: x["mem"], reverse=True)
            return processes[:8]
        except Exception:
            pass
            
    return [{"pid": 0, "name": "N/A", "mem": 0.0, "cpu": 0.0}] * 8


def render_progress_bar(percentage, width=25):
    """Draws a visual colored block bar based on percentage."""
    filled_len = int(percentage / (100 / width))
    bar = "█" * filled_len + "░" * (width - filled_len)
    
    if percentage > 85:
        color = RED
    elif percentage > 60:
        color = YELLOW
    else:
        color = GREEN
        
    return f"[{color}{bar}{RESET}] {percentage:>5.1f}%"


def format_bytes(n):
    """Converts bytes to human readable format."""
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if n < 1024.0:
            return f"{n:.1f} {unit}"
        n /= 1024.0
    return f"{n:.1f} PB"


def draw_dashboard(cpu_pct, total_mem, used_mem, mem_pct, total_disk, used_disk, disk_pct, proc_list):
    """Prints the dashboard layout."""
    clear_screen()
    
    print(f"{CYAN}{BOLD}================================================================={RESET}")
    print(f"      📈  CLI REAL-TIME SYSTEM MONITOR & DASHBOARD  📊")
    print(f"{CYAN}================================================================={RESET}")
    print(f"  OS: {platform.system()} {platform.release()} ({platform.machine()}) | Refreshes: 2.0s")
    print(f"  Engine Mode: {GREEN}{'PSUTIL (High Precision)' if HAS_PSUTIL else 'PLATFORM CLI FALLBACKS'}{RESET}")
    print("-" * 65)

    # Resource section
    print(f"  {BOLD}CPU Usage:{RESET}    {render_progress_bar(cpu_pct)}")
    
    mem_details = f"({format_bytes(used_mem)} / {format_bytes(total_mem)})"
    print(f"  {BOLD}Memory Usage:{RESET} {render_progress_bar(mem_pct)} {mem_details}")
    
    disk_details = f"({format_bytes(used_disk)} / {format_bytes(total_disk)})"
    print(f"  {BOLD}Disk Usage (Root):{RESET}   {render_progress_bar(disk_pct)} {disk_details}")
    
    print("-" * 65)
    
    # Process section
    print(f"  {BOLD}{MAGENTA}Top Resource-Consuming Processes:{RESET}")
    print(f"    {'PID':<8} | {'Process Name':<28} | {'Memory (MB/%)':<14} | {'CPU %'}")
    print(f"    {'-'*61}")
    
    for proc in proc_list:
        mem_str = f"{proc['mem']:.1f}%" if HAS_PSUTIL else f"{proc['mem']:.1f} MB"
        print(f"    {proc['pid']:<8} | {proc['name'][:28]:<28} | {mem_str:<14} | {proc['cpu']:.1f}%")
        
    print(f"{CYAN}================================================================={RESET}")
    print(f"  Press {BOLD}Ctrl+C{RESET} to exit the dashboard monitor.")


def main():
    parser = argparse.ArgumentParser(
        description="Launch real-time system dashboard",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("-d", "--duration", type=int, default=0,
                        help="Duration in seconds to run (0 for infinite)")
    parser.add_argument("-r", "--rate", type=float, default=2.0,
                        help="Screen refresh rate in seconds (default: 2.0)")

    args = parser.parse_args()

    # Hide cursor
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

    elapsed = 0.0
    try:
        while True:
            # Fetch resources
            cpu_pct = get_cpu_usage()
            total_mem, used_mem, mem_pct = get_memory_usage()
            total_disk, used_disk, disk_pct = get_disk_usage()
            proc_list = get_processes()
            
            # Print dashboard
            draw_dashboard(cpu_pct, total_mem, used_mem, mem_pct, total_disk, used_disk, disk_pct, proc_list)
            
            time.sleep(args.rate)
            elapsed += args.rate
            if args.duration > 0 and elapsed >= args.duration:
                break
    except KeyboardInterrupt:
        pass
    finally:
        # Restore cursor
        sys.stdout.write("\033[?25h")
        sys.stdout.flush()
        print("\nDashboard closed.")
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
