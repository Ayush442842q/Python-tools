#!/usr/bin/env python3
"""
System Info Reporter - A cross-platform tool to query and report system
specifications, OS version details, CPU/Memory hardware info, and paths.
"""

import argparse
import sys
import os
import platform
import json
import tempfile
import subprocess

def get_ram_info():
    """Gathers total and available RAM using platform-specific APIs without external dependencies."""
    total_bytes = 0
    avail_bytes = 0
    sys_type = platform.system()

    if sys_type == "Windows":
        try:
            import ctypes
            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_uint64),
                    ("ullAvailPhys", ctypes.c_uint64),
                    ("ullTotalPageFile", ctypes.c_uint64),
                    ("ullAvailPageFile", ctypes.c_uint64),
                    ("ullTotalVirtual", ctypes.c_uint64),
                    ("ullAvailVirtual", ctypes.c_uint64),
                    ("ullAvailExtendedVirtual", ctypes.c_uint64),
                ]
            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(stat)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                total_bytes = stat.ullTotalPhys
                avail_bytes = stat.ullAvailPhys
        except Exception:
            pass

    elif sys_type == "Linux":
        try:
            # Parse /proc/meminfo
            mem_info = {}
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    parts = line.split()
                    if len(parts) >= 2:
                        key = parts[0].rstrip(":")
                        val = int(parts[1]) * 1024 # KB to Bytes
                        mem_info[key] = val
            total_bytes = mem_info.get("MemTotal", 0)
            avail_bytes = mem_info.get("MemAvailable", mem_info.get("MemFree", 0))
        except Exception:
            pass

    elif sys_type == "Darwin": # macOS
        try:
            # Get total physical memory
            proc = subprocess.Popen(["sysctl", "-n", "hw.memsize"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, _ = proc.communicate()
            if proc.returncode == 0:
                total_bytes = int(stdout.strip())
                
            # Get page size
            proc = subprocess.Popen(["sysctl", "-n", "hw.pagesize"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, _ = proc.communicate()
            pagesize = int(stdout.strip()) if proc.returncode == 0 else 4096
            
            # Get vm_stat (page counts)
            proc = subprocess.Popen(["vm_stat"], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            stdout, _ = proc.communicate()
            if proc.returncode == 0:
                free_pages = 0
                inactive_pages = 0
                for line in stdout.decode("utf-8").splitlines():
                    if "Pages free" in line:
                        free_pages = int(line.split()[-1].strip("."))
                    elif "Pages inactive" in line:
                        inactive_pages = int(line.split()[-1].strip("."))
                # Available is approximately Free + Inactive
                avail_bytes = (free_pages + inactive_pages) * pagesize
        except Exception:
            pass

    return total_bytes, avail_bytes

def format_bytes(byte_count):
    """Formats raw bytes into a human-readable string (GB/MB)."""
    if byte_count <= 0:
        return "Unknown"
    gb = byte_count / (1024 ** 3)
    return f"{gb:.2f} GB"

def main():
    parser = argparse.ArgumentParser(
        description="System Info Reporter - Gather details on hardware, operating system, and system paths."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--os", action="store_true", help="Print OS/Kernel information only")
    group.add_argument("--hardware", action="store_true", help="Print CPU and Memory details only")
    group.add_argument("--paths", action="store_true", help="Print system paths and directories only")
    group.add_argument("-j", "--json", action="store_true", help="Output reports in JSON format")

    args = parser.parse_args()

    # Retrieve all info
    os_name = platform.system()
    os_release = platform.release()
    os_version = platform.version()
    hostname = platform.node()
    arch, _ = platform.architecture()
    machine = platform.machine()
    processor = platform.processor() or "Unknown Processor"
    
    cpu_cores = os.cpu_count() or 0
    total_ram, avail_ram = get_ram_info()
    
    home_dir = os.path.expanduser("~")
    temp_dir = tempfile.gettempdir()
    cwd = os.getcwd()
    python_path = sys.executable
    python_ver = platform.python_version()

    # Formulate structure
    report = {
        "os": {
            "system": os_name,
            "release": os_release,
            "version": os_version,
            "hostname": hostname,
            "architecture": arch,
            "machine": machine
        },
        "hardware": {
            "processor": processor,
            "logical_cores": cpu_cores,
            "total_ram_bytes": total_ram,
            "available_ram_bytes": avail_ram,
            "total_ram_formatted": format_bytes(total_ram),
            "available_ram_formatted": format_bytes(avail_ram)
        },
        "paths": {
            "current_working_directory": cwd,
            "home_directory": home_dir,
            "temp_directory": temp_dir,
            "python_executable": python_path,
            "python_version": python_ver
        }
    }

    if args.json:
        # JSON output
        if args.os:
            print(json.dumps(report["os"], indent=2))
        elif args.hardware:
            print(json.dumps(report["hardware"], indent=2))
        elif args.paths:
            print(json.dumps(report["paths"], indent=2))
        else:
            print(json.dumps(report, indent=2))
        sys.exit(0)

    # Format human-readable output
    if args.os or (not args.hardware and not args.paths):
        print("--- Operating System Info ---")
        print(f"OS/Kernel Name:     {report['os']['system']}")
        print(f"OS Release Version: {report['os']['release']}")
        print(f"OS Build Detail:    {report['os']['version']}")
        print(f"Hostname:           {report['os']['hostname']}")
        print(f"Architecture:       {report['os']['architecture']} ({report['os']['machine']})")
        print()

    if args.hardware or (not args.os and not args.paths):
        print("--- Hardware Specifications ---")
        print(f"Processor Name:     {report['hardware']['processor']}")
        print(f"Logical CPU Cores:  {report['hardware']['logical_cores']}")
        print(f"Total System RAM:   {report['hardware']['total_ram_formatted']}")
        print(f"Available RAM:      {report['hardware']['available_ram_formatted']}")
        print()

    if args.paths or (not args.os and not args.hardware):
        print("--- System Environment & Paths ---")
        print(f"Current Directory:  {report['paths']['current_working_directory']}")
        print(f"Home Directory:     {report['paths']['home_directory']}")
        print(f"Temp Directory:     {report['paths']['temp_directory']}")
        print(f"Python Executable:  {report['paths']['python_executable']}")
        print(f"Python Version:     {report['paths']['python_version']}")
        print()

if __name__ == "__main__":
    main()
