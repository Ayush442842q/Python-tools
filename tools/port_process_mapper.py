#!/usr/bin/env python3
"""
Port-to-Process Mapper
A cross-platform utility to map network ports to process IDs and names.
Allows searching, filtering, and interactively terminating processes occupying ports.
"""

import os
import sys
import subprocess
import platform
import argparse
import re
import socket
from typing import Dict, List, Optional, Tuple, Set

# Try importing psutil for enhanced capability, but support fallback to native utilities
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False

class PortProcessMapper:
    def __init__(self):
        self.system = platform.system()

    def get_process_connections(self) -> List[Dict]:
        """Get open ports and their matching processes."""
        connections = []

        if HAS_PSUTIL:
            connections = self._get_connections_psutil()
        else:
            if self.system == "Windows":
                connections = self._get_connections_windows()
            elif self.system in ("Linux", "Darwin"):
                connections = self._get_connections_unix()
            else:
                print(f"[-] Unsupported OS: {self.system}", file=sys.stderr)
        
        return connections

    def _get_connections_psutil(self) -> List[Dict]:
        connections_list = []
        # Get all net connections
        try:
            for conn in psutil.net_connections(kind='inet'):
                if not conn.laddr:
                    continue
                
                port = conn.laddr.port
                ip = conn.laddr.ip
                pid = conn.pid
                status = conn.status
                proto = "TCP" if conn.type == socket.SOCK_STREAM else "UDP"

                process_name = "N/A"
                if pid:
                    try:
                        p = psutil.Process(pid)
                        process_name = p.name()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        process_name = "Access Denied / Dead"

                connections_list.append({
                    "port": port,
                    "ip": ip,
                    "proto": proto,
                    "status": status or "N/A",
                    "pid": pid or "N/A",
                    "name": process_name
                })
        except Exception as e:
            print(f"[-] Error calling psutil: {e}. Falling back to system commands.", file=sys.stderr)
            # Fallback
            if self.system == "Windows":
                return self._get_connections_windows()
            else:
                return self._get_connections_unix()
        
        return connections_list

    def _get_connections_windows(self) -> List[Dict]:
        """Fall back to parsing netstat -ano on Windows."""
        connections_list = []
        try:
            # -a: displays all connections and listening ports
            # -n: displays addresses and port numbers in numerical form
            # -o: displays the associated process ID
            output = subprocess.check_output("netstat -ano", shell=True, text=True, errors="ignore")
            
            # Map PIDs to Process Names using tasklist
            pid_to_name = self._get_windows_tasks()

            for line in output.splitlines():
                line = line.strip()
                if not line or line.startswith("Active") or line.startswith("Proto"):
                    continue
                
                parts = re.split(r'\s+', line)
                if len(parts) >= 4:
                    proto = parts[0]
                    local_addr = parts[1]
                    
                    # Split IP and Port (Windows netstat output e.g. [::]:8080 or 127.0.0.1:8080)
                    if ']' in local_addr:  # IPv6
                        ip = local_addr.split(']')[0] + ']'
                        port_str = local_addr.split(']')[-1].replace(':', '')
                    else:
                        ip = local_addr.rsplit(':', 1)[0]
                        port_str = local_addr.rsplit(':', 1)[-1]
                    
                    try:
                        port = int(port_str)
                    except ValueError:
                        continue

                    # If TCP, the 4th element is State, 5th is PID. If UDP, 3rd is IP, 4th is PID.
                    if proto.upper() == "TCP":
                        status = parts[3]
                        pid_str = parts[4] if len(parts) > 4 else "0"
                    else:
                        status = "LISTENING"  # UDP is connectionless
                        pid_str = parts[3] if len(parts) > 3 else "0"
                    
                    try:
                        pid = int(pid_str)
                    except ValueError:
                        pid = 0

                    connections_list.append({
                        "port": port,
                        "ip": ip,
                        "proto": proto.upper(),
                        "status": status,
                        "pid": pid,
                        "name": pid_to_name.get(pid, "N/A")
                    })
        except Exception as e:
            print(f"[-] Error calling netstat: {e}", file=sys.stderr)
        
        return connections_list

    def _get_windows_tasks(self) -> Dict[int, str]:
        """Fetch a map of Windows PID to task names."""
        pid_map = {}
        try:
            output = subprocess.check_output("tasklist /NH /FO CSV", shell=True, text=True, errors="ignore")
            for line in output.splitlines():
                if not line.strip():
                    continue
                # Format: "taskname","pid","session name","session#","mem usage"
                parts = [p.strip('"') for p in line.split('","')]
                if len(parts) >= 2:
                    try:
                        name = parts[0]
                        pid = int(parts[1])
                        pid_map[pid] = name
                    except ValueError:
                        continue
        except Exception:
            pass
        return pid_map

    def _get_connections_unix(self) -> List[Dict]:
        """Fall back to parsing lsof or netstat on Unix/macOS."""
        connections_list = []
        
        # Try lsof -i -P -n first (which shows both macOS and Linux connections)
        try:
            output = subprocess.check_output("lsof -i -P -n -F nP", shell=True, text=True, errors="ignore")
            # lsof output formatted by field:
            # p<pid>
            # c<command>
            # t<type>
            # n<local address>:<port>
            current_pid = 0
            current_name = "N/A"
            
            for line in output.splitlines():
                if not line.strip():
                    continue
                field_type = line[0]
                value = line[1:]
                
                if field_type == 'p':
                    try:
                        current_pid = int(value)
                    except ValueError:
                        current_pid = 0
                elif field_type == 'c':
                    current_name = value
                elif field_type == 'n':
                    # Parse local address/port and remote
                    # Format can be: IP:Port or IP:Port->IP:Port
                    local_part = value.split('->')[0]
                    
                    proto = "TCP"  # lsof displays protocol if we parsed headers, but defaults to TCP/UDP
                    # Since we didn't specify protocol fields, let's extract
                    if ':' in local_part:
                        ip, port_str = local_part.rsplit(':', 1)
                        try:
                            # Try parsing port
                            port = int(port_str)
                            # Simple guess for protocol
                            connections_list.append({
                                "port": port,
                                "ip": ip,
                                "proto": "TCP/UDP",
                                "status": "ACTIVE",
                                "pid": current_pid,
                                "name": current_name
                            })
                        except ValueError:
                            pass
            if connections_list:
                return connections_list
        except Exception:
            pass

        # Fallback to netstat -an (Linux)
        try:
            output = subprocess.check_output("netstat -anp 2>/dev/null || netstat -an", shell=True, text=True, errors="ignore")
            for line in output.splitlines():
                line = line.strip()
                if not line or not (line.startswith("tcp") or line.startswith("udp")):
                    continue
                parts = re.split(r'\s+', line)
                if len(parts) >= 4:
                    proto = parts[0].upper()
                    local_addr = parts[3]
                    
                    if ':' in local_addr:
                        ip, port_str = local_addr.rsplit(':', 1)
                        try:
                            port = int(port_str)
                        except ValueError:
                            continue
                    elif '.' in local_addr:
                        ip, port_str = local_addr.rsplit('.', 1)
                        try:
                            port = int(port_str)
                        except ValueError:
                            continue
                    else:
                        continue

                    status = parts[5] if proto.startswith("TCP") and len(parts) > 5 else "LISTENING"
                    
                    # Extract PID/Program name if available (e.g. 1234/python)
                    pid = "N/A"
                    name = "N/A"
                    last_col = parts[-1]
                    if '/' in last_col:
                        pid_part, name_part = last_col.split('/', 1)
                        try:
                            pid = int(pid_part)
                            name = name_part
                        except ValueError:
                            pass

                    connections_list.append({
                        "port": port,
                        "ip": ip,
                        "proto": proto,
                        "status": status,
                        "pid": pid,
                        "name": name
                    })
        except Exception:
            pass

        return connections_list

    def kill_process(self, pid: int) -> bool:
        """Kill process by PID."""
        if HAS_PSUTIL:
            try:
                p = psutil.Process(pid)
                p.terminate()
                p.wait(timeout=3)
                return True
            except Exception:
                try:
                    p.kill()
                    return True
                except Exception as e:
                    print(f"[-] psutil failed to kill process {pid}: {e}", file=sys.stderr)
        
        # OS commands fallback
        try:
            if self.system == "Windows":
                subprocess.check_call(f"taskkill /F /PID {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.check_call(f"kill -9 {pid}", shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        except Exception as e:
            print(f"[-] Command failed to kill process {pid}: {e}", file=sys.stderr)
            return False

def print_table(connections: List[Dict]):
    """Print the connections in a beautiful ASCII table."""
    if not connections:
        print("[*] No active port connections found.")
        return

    # Header
    headers = ["Proto", "Local IP", "Port", "Status", "PID", "Process Name"]
    col_widths = [6, 20, 8, 15, 8, 25]
    
    # Print header border
    border = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
    print(border)
    
    # Print header text
    header_line = "| " + " | ".join(f"{h:<{w}}" for h, w in zip(headers, col_widths)) + " |"
    print(header_line)
    print(border)

    # Sort connections by Port number
    sorted_conns = sorted(connections, key=lambda x: (x["port"], x["proto"]))
    
    seen = set()
    for conn in sorted_conns:
        # Avoid exact duplicates
        key = (conn["proto"], conn["port"], conn["pid"])
        if key in seen:
            continue
        seen.add(key)

        proto = str(conn["proto"])[:col_widths[0]]
        ip = str(conn["ip"])[:col_widths[1]]
        port = str(conn["port"])[:col_widths[2]]
        status = str(conn["status"])[:col_widths[3]]
        pid = str(conn["pid"])[:col_widths[4]]
        name = str(conn["name"])[:col_widths[5]]
        
        row = "| " + " | ".join([
            f"{proto:<{col_widths[0]}}",
            f"{ip:<{col_widths[1]}}",
            f"{port:<{col_widths[2]}}",
            f"{status:<{col_widths[3]}}",
            f"{pid:<{col_widths[4]}}",
            f"{name:<{col_widths[5]}}"
        ]) + " |"
        print(row)
    
    print(border)

def main():
    parser = argparse.ArgumentParser(description="Port-to-Process Mapper")
    parser.add_argument("-l", "--list", action="store_true", help="List all ports and matching processes (default)")
    parser.add_argument("-p", "--port", type=int, help="Filter connections by a specific port")
    parser.add_argument("-n", "--name", type=str, help="Filter connections by process name (regex/substring)")
    parser.add_argument("-k", "--kill", type=int, metavar="PID", help="Kill a process by PID")
    parser.add_argument("-i", "--interactive", action="store_true", help="Start interactive menu to view and kill processes")
    args = parser.parse_args()

    mapper = PortProcessMapper()

    # Action: Kill direct
    if args.kill:
        print(f"[*] Attempting to terminate process with PID {args.kill}...")
        if mapper.kill_process(args.kill):
            print(f"[+] Process {args.kill} successfully terminated.")
        else:
            print(f"[-] Failed to terminate process {args.kill}.")
        return

    # Action: Interactive
    if args.interactive:
        run_interactive(mapper)
        return

    # Action: List (Default)
    connections = mapper.get_process_connections()
    
    if args.port:
        connections = [c for c in connections if c["port"] == args.port]
    
    if args.name:
        name_lower = args.name.lower()
        connections = [c for c in connections if name_lower in c["name"].lower()]

    print_table(connections)

def run_interactive(mapper: PortProcessMapper):
    """Run interactive text terminal menu."""
    while True:
        connections = mapper.get_process_connections()
        # Filter duplicates for visual simplicity in list
        unique_conns = []
        seen = set()
        for conn in sorted(connections, key=lambda x: x["port"]):
            key = (conn["port"], conn["proto"], conn["pid"])
            if key not in seen:
                seen.add(key)
                unique_conns.append(conn)

        print("\n--- Port-to-Process Mapper Interactive Menu ---")
        if not unique_conns:
            print("[*] No active port connections detected.")
        else:
            for idx, conn in enumerate(unique_conns):
                print(f"[{idx + 1:2d}] Port: {conn['port']:5d} | {conn['proto']:4s} | PID: {conn['pid']:6} | Proc: {conn['name']}")
        
        print("\nOptions:")
        print(" [N] Refresh list")
        print(" [K <index>] Kill process at index")
        print(" [Q] Quit")
        
        choice = input("\nEnter choice: ").strip().lower()
        if not choice:
            continue
        
        if choice == 'q':
            break
        elif choice == 'n':
            continue
        elif choice.startswith('k '):
            try:
                idx = int(choice.split(' ')[1]) - 1
                if 0 <= idx < len(unique_conns):
                    target = unique_conns[idx]
                    pid = target["pid"]
                    if pid == "N/A" or not pid:
                        print("[-] Process has no valid PID.")
                        continue
                    
                    confirm = input(f"Are you sure you want to kill PID {pid} ({target['name']})? [y/N]: ").strip().lower()
                    if confirm == 'y':
                        if mapper.kill_process(pid):
                            print(f"[+] Process {pid} terminated.")
                        else:
                            print(f"[-] Could not terminate process {pid}.")
                else:
                    print("[-] Invalid index choice.")
            except (ValueError, IndexError):
                print("[-] Command format: k <index_number>")
            input("\nPress Enter to continue...")
        else:
            print("[-] Unknown choice.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[!] Exited by user.")
        sys.exit(0)
