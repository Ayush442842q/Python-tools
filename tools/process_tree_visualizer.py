#!/usr/bin/env python3
"""
process_tree_visualizer.py - Hierarchical System Process Tree Visualizer
Gathers running process data cross-platform (PowerShell/wmic on Windows, ps on Unix)
and prints a hierarchical parent-child process tree (pstree clone) with memory stats,
searching, filtering, and options to recursively kill process subtrees.
"""

import os
import sys
import subprocess
import argparse
import json
import re

# ANSI colors
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
CYAN = "\033[36m"
DIM = "\033[2m"

def is_windows():
    return sys.platform == "win32"

def get_processes_windows():
    """Gathers processes on Windows using PowerShell or wmic fallback."""
    processes = []
    
    # Try PowerShell first (modern, clean JSON output)
    try:
        ps_cmd = [
            "powershell", "-NoProfile", "-Command",
            "Get-CimInstance Win32_Process | "
            "Select-Object ParentProcessId, ProcessId, Name, WorkingSetSize | "
            "ConvertTo-Json -Compress"
        ]
        result = subprocess.run(ps_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        if result.stdout.strip():
            data = json.loads(result.stdout)
            # PowerShell ConvertTo-Json returns a dict if single item, or list of dicts
            items = data if isinstance(data, list) else [data]
            for item in items:
                ppid = item.get("ParentProcessId", 0)
                pid = item.get("ProcessId", 0)
                name = item.get("Name", "Unknown")
                mem_bytes = item.get("WorkingSetSize", 0) or 0
                mem_mb = mem_bytes / (1024 * 1024)
                processes.append({
                    "pid": int(pid),
                    "ppid": int(ppid),
                    "name": name,
                    "mem": mem_mb
                })
            return processes
    except Exception:
        pass  # Fall back to wmic if powershell fails or is restricted

    # WMIC fallback
    try:
        wmic_cmd = ["wmic", "process", "get", "ParentProcessId,ProcessId,Name,WorkingSetSize", "/format:csv"]
        result = subprocess.run(wmic_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        # Parse CSV lines
        lines = result.stdout.strip().splitlines()
        for line in lines:
            if not line.strip() or "ParentProcessId" in line:
                continue
            parts = [p.strip() for p in line.split(",") if p.strip()]
            if len(parts) >= 4:
                # Format: Node,Name,ParentProcessId,ProcessId,WorkingSetSize
                name = parts[1]
                ppid = parts[2]
                pid = parts[3]
                mem_bytes = parts[4] if len(parts) > 4 else "0"
                try:
                    mem_mb = int(mem_bytes) / (1024 * 1024) if mem_bytes.isdigit() else 0.0
                    processes.append({
                        "pid": int(pid),
                        "ppid": int(ppid),
                        "name": name,
                        "mem": mem_mb
                    })
                except ValueError:
                    continue
        return processes
    except Exception as e:
        print(f"Error gathering Windows processes: {e}", file=sys.stderr)
        return []

def get_processes_unix():
    """Gathers processes on Linux/macOS using standard ps."""
    processes = []
    try:
        # ps -ax -o ppid,pid,rss,comm
        # rss is in kilobytes
        cmd = ["ps", "-ax", "-o", "ppid,pid,rss,comm"]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        lines = result.stdout.strip().splitlines()
        
        for line in lines:
            parts = line.strip().split(None, 3)
            if not parts or parts[0] == "PPID":
                continue
            if len(parts) >= 4:
                ppid, pid, rss_kb, comm = parts
                try:
                    mem_mb = int(rss_kb) / 1024.0
                    # comm might contain path, take basename
                    name = os.path.basename(comm.strip())
                    processes.append({
                        "pid": int(pid),
                        "ppid": int(ppid),
                        "name": name,
                        "mem": mem_mb
                    })
                except ValueError:
                    continue
        return processes
    except Exception as e:
        print(f"Error gathering Unix processes: {e}", file=sys.stderr)
        return []

def get_processes():
    if is_windows():
        return get_processes_windows()
    else:
        return get_processes_unix()

def build_process_tree(processes):
    """
    Constructs a tree from the flat list of processes.
    Returns (roots, tree_map, process_by_pid)
    """
    tree_map = {}  # pid -> list of child pids
    proc_map = {}  # pid -> process dictionary
    
    # Initialize maps
    for p in processes:
        pid = p["pid"]
        proc_map[pid] = p
        tree_map[pid] = []
        
    roots = []
    for p in processes:
        pid = p["pid"]
        ppid = p["ppid"]
        
        # If parent exists in process list and is not itself, add to parent's children
        if ppid in proc_map and ppid != pid:
            tree_map[ppid].append(pid)
        else:
            roots.append(pid)
            
    return roots, tree_map, proc_map

def find_sub_pids(pid, tree_map):
    """Returns a list of all child and descendant PIDs of a given PID."""
    descendants = []
    queue = [pid]
    while queue:
        current = queue.pop(0)
        children = tree_map.get(current, [])
        descendants.extend(children)
        queue.extend(children)
    return descendants

def kill_process_tree(pid, tree_map, recursive=True):
    """Kills a process and optionally its descendants."""
    pids_to_kill = [pid]
    if recursive:
        pids_to_kill.extend(find_sub_pids(pid, tree_map))
        
    # Order descending so children die first
    pids_to_kill.sort(reverse=True)
    
    print(f"Attempting to terminate {len(pids_to_kill)} process(es)...")
    successes = 0
    for p in pids_to_kill:
        try:
            if is_windows():
                # taskkill
                subprocess.run(
                    ["taskkill", "/F", "/PID", str(p)], 
                    stdout=subprocess.DEVNULL, 
                    stderr=subprocess.DEVNULL, 
                    check=True
                )
            else:
                # kill
                os.kill(p, 9)
            print(f"  {GREEN}Killed PID {p}{RESET}")
            successes += 1
        except Exception:
            print(f"  {RED}Failed to kill PID {p} (may have already exited or requires admin privileges){RESET}")
            
    return successes

def render_tree(pid, tree_map, proc_map, prefix="", is_last=True, filter_regex=None, matches_filter=None):
    """
    Recursively renders the process tree using Unicode box-drawing characters.
    """
    p = proc_map.get(pid)
    if not p:
        return
        
    name = p["name"]
    mem = p["mem"]
    
    # Check filter matching
    is_match = False
    if filter_regex:
        is_match = bool(filter_regex.search(name)) or bool(filter_regex.search(str(pid)))
        
    # Check if any descendant matches the filter
    if filter_regex and not is_match:
        desc_pids = find_sub_pids(pid, tree_map)
        has_matching_desc = any(
            bool(filter_regex.search(proc_map[dp]["name"])) or bool(filter_regex.search(str(dp)))
            for dp in desc_pids if dp in proc_map
        )
        if not has_matching_desc:
            # Skip rendering if neither self nor descendants match the filter
            return
            
    # Highlight self if match
    name_str = f"{BOLD}{YELLOW}{name}{RESET}" if is_match else name
    pid_str = f"{CYAN}{pid}{RESET}"
    mem_str = f"{DIM}({mem:.1f}MB){RESET}" if mem > 0.1 else ""
    
    # Choose branch graphics
    connector = "└───" if is_last else "├───"
    
    print(f"{prefix}{connector}[{pid_str}] {name_str} {mem_str}")
    
    # Render children
    children = tree_map.get(pid, [])
    # Sort children by memory usage or name if desired (default by PID)
    children.sort()
    
    new_prefix = prefix + ("    " if is_last else "│   ")
    for i, child_pid in enumerate(children):
        child_is_last = (i == len(children) - 1)
        render_tree(child_pid, tree_map, proc_map, new_prefix, child_is_last, filter_regex)

def main():
    parser = argparse.ArgumentParser(
        description="Cross-platform Hierarchical Process Tree Visualizer."
    )
    parser.add_argument(
        "-f", "--filter",
        help="Filter process tree by name or PID (regular expression)."
    )
    parser.add_argument(
        "-k", "--kill",
        type=int,
        help="PID of process to terminate."
    )
    parser.add_argument(
        "-r", "--recursive",
        action="store_true",
        help="When killing a process, recursively kill all of its child processes as well."
    )
    parser.add_argument(
        "--roots-only",
        action="store_true",
        help="Only display process roots and their immediate children."
    )
    
    args = parser.parse_args()
    
    processes = get_processes()
    if not processes:
        print("Failed to gather system processes.")
        sys.exit(1)
        
    roots, tree_map, proc_map = build_process_tree(processes)
    
    # If kill requested, perform kill and exit
    if args.kill is not None:
        if args.kill not in proc_map:
            print(f"Error: Process with PID {args.kill} not found in current process list.")
            sys.exit(1)
        kill_process_tree(args.kill, tree_map, args.recursive)
        sys.exit(0)
        
    # Setup filter regex
    filter_regex = None
    if args.filter:
        try:
            filter_regex = re.compile(args.filter, re.IGNORECASE)
        except re.error as e:
            print(f"Invalid filter regex: {e}", file=sys.stderr)
            sys.exit(1)
            
    print(f"\n{BOLD}{CYAN}=== System Process Tree ==={RESET}")
    print(f"Total Running Processes: {len(processes)}\n")
    
    # Display tree
    roots.sort()
    for i, r in enumerate(roots):
        is_last = (i == len(roots) - 1)
        
        # In a real system, there can be thousands of processes.
        # If roots are system processes (like PID 0, 4, 1 on Windows) they root the entire system.
        # If --roots-only is set, we truncate depth.
        if args.roots_only:
            # Just print the root process info
            p = proc_map.get(r)
            if p:
                print(f"[{p['pid']}] {p['name']} ({p['mem']:.1f}MB)")
        else:
            render_tree(r, tree_map, proc_map, prefix="", is_last=is_last, filter_regex=filter_regex)

if __name__ == "__main__":
    main()
