#!/usr/bin/env python3
"""
System Info & Diagnostics Reporter
Queries OS, CPU, memory, disk, network, and Python environment details without external dependencies.
"""

import sys
import os
import platform
import subprocess
import socket
import json
import shutil
import argparse
from datetime import datetime

def get_cmd_output(cmd):
    """Run a shell command and return its stdout stripped."""
    try:
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True, text=True, timeout=3.0)
        return result.stdout.strip() if result.returncode == 0 else None
    except Exception:
        return None

def format_bytes(bytes_num):
    """Format bytes into human readable units."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_num < 1024.0:
            return f"{bytes_num:.2f} {unit}"
        bytes_num /= 1024.0
    return f"{bytes_num:.2f} PB"

def get_windows_mem():
    """Get total physical memory in bytes on Windows."""
    out = get_cmd_output("wmic ComputerSystem get TotalPhysicalMemory /value")
    if out:
        for line in out.splitlines():
            if "TotalPhysicalMemory" in line:
                try:
                    return int(line.split("=")[1].strip())
                except ValueError:
                    pass
    return None

def get_linux_mem():
    """Get total physical memory in bytes on Linux."""
    try:
        with open("/proc/meminfo", "r") as f:
            for line in f:
                if "MemTotal" in line:
                    parts = line.split()
                    return int(parts[1]) * 1024 # KB to bytes
    except Exception:
        pass
    return None

def get_macos_mem():
    """Get total physical memory in bytes on macOS."""
    out = get_cmd_output("sysctl -n hw.memsize")
    if out:
        try:
            return int(out)
        except ValueError:
            pass
    return None

def get_cpu_info():
    """Get processor name/brand string."""
    cpu_name = platform.processor()
    system = platform.system()
    
    if system == "Windows":
        out = get_cmd_output("wmic cpu get Name /value")
        if out:
            for line in out.splitlines():
                if "Name=" in line:
                    return line.split("=")[1].strip()
    elif system == "Linux":
        out = get_cmd_output("grep -m 1 'model name' /proc/cpuinfo")
        if out:
            return out.split(":")[1].strip()
    elif system == "Darwin": # macOS
        out = get_cmd_output("sysctl -n machdep.cpu.brand_string")
        if out:
            return out
            
    return cpu_name or "Unknown Processor"

def get_external_ip():
    """Get external IP address with a short timeout."""
    # Try different public IP providers
    providers = ['https://api.ipify.org', 'https://ifconfig.me/ip', 'http://ipinfo.io/ip']
    
    # We will use python's standard urllib
    import urllib.request
    for url in providers:
        try:
            with urllib.request.urlopen(url, timeout=2.0) as response:
                return response.read().decode('utf-8').strip()
        except Exception:
            continue
    return "Unavailable/Offline"

def gather_diagnostics():
    """Compile all system diagnostic reports."""
    system = platform.system()
    
    # OS Info
    os_info = {
        'system': system,
        'release': platform.release(),
        'version': platform.version(),
        'architecture': platform.machine(),
        'platform_string': platform.platform()
    }
    
    # Python Info
    py_info = {
        'version': platform.python_version(),
        'implementation': platform.python_implementation(),
        'compiler': platform.python_compiler(),
        'build': ", ".join(platform.python_build())
    }
    
    # CPU Info
    cpu_count = os.cpu_count() or "Unknown"
    cpu_info = {
        'cores': cpu_count,
        'model': get_cpu_info()
    }
    
    # Memory Info
    total_mem = None
    if system == "Windows":
        total_mem = get_windows_mem()
    elif system == "Linux":
        total_mem = get_linux_mem()
    elif system == "Darwin":
        total_mem = get_macos_mem()
        
    mem_info = {
        'total_raw': total_mem,
        'total_formatted': format_bytes(total_mem) if total_mem else "Unknown"
    }
    
    # Disk Info
    total, used, free = shutil.disk_usage(os.path.abspath(os.sep))
    disk_info = {
        'total': format_bytes(total),
        'used': format_bytes(used),
        'free': format_bytes(free),
        'percent_used': f"{(used/total)*100:.2f}%"
    }
    
    # Network Info
    hostname = socket.gethostname()
    local_ip = "Unknown"
    try:
        # Standard hack to get local network IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
    except Exception:
        try:
            local_ip = socket.gethostbyname(hostname)
        except Exception:
            pass
            
    net_info = {
        'hostname': hostname,
        'local_ip': local_ip,
        'external_ip': get_external_ip()
    }
    
    return {
        'timestamp': datetime.now().isoformat(),
        'os': os_info,
        'cpu': cpu_info,
        'memory': mem_info,
        'disk': disk_info,
        'network': net_info,
        'python': py_info
    }

def format_text_report(data):
    """Generate plaintext output."""
    lines = []
    lines.append("=" * 50)
    lines.append(f"SYSTEM DIAGNOSTICS REPORT - {data['timestamp']}")
    lines.append("=" * 50)
    
    lines.append("\n[Operating System]")
    lines.append(f"  OS Name:      {data['os']['system']}")
    lines.append(f"  Release:      {data['os']['release']}")
    lines.append(f"  Version:      {data['os']['version']}")
    lines.append(f"  Architecture: {data['os']['architecture']}")
    lines.append(f"  Details:      {data['os']['platform_string']}")
    
    lines.append("\n[Hardware Details]")
    lines.append(f"  CPU Model:    {data['cpu']['model']}")
    lines.append(f"  CPU Cores:    {data['cpu']['cores']}")
    lines.append(f"  Physical Mem: {data['memory']['total_formatted']}")
    
    lines.append("\n[Storage Usage (Root)]")
    lines.append(f"  Total Space:  {data['disk']['total']}")
    lines.append(f"  Used Space:   {data['disk']['used']} ({data['disk']['percent_used']})")
    lines.append(f"  Free Space:   {data['disk']['free']}")
    
    lines.append("\n[Network Interface]")
    lines.append(f"  Hostname:     {data['network']['hostname']}")
    lines.append(f"  Local IP:     {data['network']['local_ip']}")
    lines.append(f"  External IP:  {data['network']['external_ip']}")
    
    lines.append("\n[Python Environment]")
    lines.append(f"  Version:      {data['python']['version']}")
    lines.append(f"  Impl:         {data['python']['implementation']}")
    lines.append(f"  Compiler:     {data['python']['compiler']}")
    lines.append(f"  Build:        {data['python']['build']}")
    lines.append("\n" + "=" * 50)
    return "\n".join(lines)

def format_markdown_report(data):
    """Generate Markdown output."""
    md = []
    md.append(f"# System Diagnostics Report")
    md.append(f"*Generated on: {data['timestamp']}*\n")
    
    md.append("## Operating System")
    md.append(f"- **OS:** {data['os']['system']}")
    md.append(f"- **Release:** {data['os']['release']}")
    md.append(f"- **Version:** {data['os']['version']}")
    md.append(f"- **Architecture:** {data['os']['architecture']}")
    md.append(f"- **Platform String:** `{data['os']['platform_string']}`\n")
    
    md.append("## Hardware Details")
    md.append(f"- **CPU Model:** {data['cpu']['model']}")
    md.append(f"- **CPU Cores:** {data['cpu']['cores']}")
    md.append(f"- **Physical Memory:** {data['memory']['total_formatted']}\n")
    
    md.append("## Storage Usage (Root)")
    md.append("| Property | Value |")
    md.append("| --- | --- |")
    md.append(f"| Total | {data['disk']['total']} |")
    md.append(f"| Used | {data['disk']['used']} ({data['disk']['percent_used']}) |")
    md.append(f"| Free | {data['disk']['free']} | \n")
    
    md.append("## Network Interface")
    md.append(f"- **Hostname:** `{data['network']['hostname']}`")
    md.append(f"- **Local IP:** `{data['network']['local_ip']}`")
    md.append(f"- **External IP:** `{data['network']['external_ip']}`\n")
    
    md.append("## Python Environment")
    md.append(f"- **Python Version:** `{data['python']['version']}`")
    md.append(f"- **Implementation:** {data['python']['implementation']}")
    md.append(f"- **Compiler:** `{data['python']['compiler']}`")
    md.append(f"- **Build info:** `{data['python']['build']}`")
    
    return "\n".join(md)

def main():
    parser = argparse.ArgumentParser(
        description="System Info & Diagnostics Reporter",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--format", "-f", default="text", choices=["text", "markdown", "json"], help="Output format (default: text)")
    parser.add_argument("--output", "-o", help="File path to write report to (otherwise stdout)")
    
    args = parser.parse_args()
    
    print("Collecting system diagnostics...", file=sys.stderr)
    report_data = gather_diagnostics()
    
    if args.format == "json":
        report_out = json.dumps(report_data, indent=4)
    elif args.format == "markdown":
        report_out = format_markdown_report(report_data)
    else:
        report_out = format_text_report(report_data)
        
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(report_out + "\n")
            print(f"Report saved to '{args.output}'")
        except Exception as e:
            print(f"Error saving report to file: {e}", file=sys.stderr)
            return 1
    else:
        print(report_out)
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
