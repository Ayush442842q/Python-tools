#!/usr/bin/env python3
"""
Python Import Overhead Profiler

Profiles startup time overhead caused by slow Python imports. Uses the native
'-X importtime' flag in Python 3.7+ to capture import durations, parses the hierarchical
durations, and displays a clean visual tree highlight of import bottlenecks.

Usage:
    python tools/python_import_overhead_profiler.py [module_name_or_script_path] [options]
"""

import re
import os
import sys
import argparse
import subprocess
from pathlib import Path

# ANSI Colors
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"

def print_colored(text: str, color: str, end: str = "\n"):
    if sys.stdout.isatty():
        print(f"{color}{text}{RESET}", end=end)
    else:
        print(text, end=end)

def parse_import_time_output(stderr_content: str) -> list:
    """Parses Python's '-X importtime' output lines."""
    records = []
    # Lines look like: "import time: self [us] |  cumulative [us] | area"
    # followed by: "import time:       101 |           101 |   sys"
    lines = stderr_content.splitlines()
    
    for line in lines:
        if not line.startswith("import time:"):
            continue
        
        # Split fields
        body = line[len("import time:"):].strip()
        if "self [us]" in body or "cumulative [us]" in body:
            continue
            
        parts = body.split("|")
        if len(parts) < 3:
            continue
            
        try:
            self_us = int(parts[0].strip())
            cum_us = int(parts[1].strip())
            
            # The name field has leading spaces indicating hierarchical nesting depth
            name_field = parts[2]
            stripped_name = name_field.lstrip()
            # Every level of import nesting adds spaces (usually 2 spaces per depth level)
            leading_spaces = len(name_field) - len(stripped_name)
            depth_level = max(0, leading_spaces // 2)
            
            records.append({
                'name': stripped_name.strip(),
                'self_ms': self_us / 1000.0,
                'cum_ms': cum_us / 1000.0,
                'depth': depth_level
            })
        except Exception:
            # Skip invalid lines gracefully
            continue
            
    return records

def render_import_tree(records: list, threshold_ms: float):
    """Renders the hierarchical import tree with timing statistics."""
    if not records:
        print_colored("No import records captured.", YELLOW)
        return
        
    print_colored(f"\nImport Nesting Tree (cumulative / self time in ms):", BOLD + CYAN)
    print_colored(f"Highlighting imports taking cumulative time >= {threshold_ms}ms", BOLD)
    print("-" * 80)
    
    # We can render the tree using depth indicators
    for idx, r in enumerate(records):
        indent = "  " * r['depth']
        
        # Format string
        time_info = f"({r['cum_ms']:.2f}ms / {r['self_ms']:.2f}ms)"
        
        # Determine highlighting color based on cumulative time
        if r['cum_ms'] >= threshold_ms * 2:
            color = RED + BOLD
        elif r['cum_ms'] >= threshold_ms:
            color = YELLOW
        else:
            color = RESET
            
        # Draw connector
        connector = "|- " if r['depth'] > 0 else ""
        
        # Print indent + connector + name + time info
        line_text = f"{indent}{connector}{r['name']}"
        print(f"{line_text:<55} ", end="")
        print_colored(time_info, color)
        
    print("-" * 80)

def main():
    parser = argparse.ArgumentParser(
        description="Profile Python module/script startup import overhead using -X importtime."
    )
    parser.add_argument(
        "target",
        help="Python module to import (e.g. 'json', 'urllib.request') OR path to a local .py script"
    )
    parser.add_argument(
        "--threshold", "-t",
        type=float,
        default=5.0,
        help="Highlight threshold for cumulative import time in milliseconds (default: 5.0ms)"
    )
    parser.add_argument(
        "--top", "-n",
        type=int,
        default=5,
        help="Show top N slowest self-time imports (default: 5)"
    )
    
    args = parser.parse_args()
    
    target = args.target.strip()
    
    # Check if target is a file or a module name
    target_path = Path(target)
    
    if target_path.exists() and target_path.suffix == '.py':
        # Execute script with -X importtime
        cmd = [sys.executable, "-X", "importtime", str(target_path)]
        print_colored(f"Profiling script import times: {' '.join(cmd)}...", BOLD)
    else:
        # Import as a module via command line
        cmd = [sys.executable, "-X", "importtime", "-c", f"import {target}"]
        print_colored(f"Profiling module import times: {' '.join(cmd)}...", BOLD)
        
    try:
        # Run subprocess and capture outputs
        # -X importtime writes output to stderr
        result = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=15
        )
    except subprocess.TimeoutExpired:
        print_colored("Error: Profiling command timed out after 15 seconds.", RED)
        return 1
    except Exception as e:
        print_colored(f"Error running subprocess: {e}", RED)
        return 1
        
    # parse stderr containing importtime output
    records = parse_import_time_output(result.stderr)
    
    if not records:
        print_colored("Failed to extract any import timings. Make sure target imports successfully.", RED)
        if result.stderr:
            print_colored("\nSubprocess Stderr:", BOLD)
            print(result.stderr)
        return 1
        
    # Render tree
    render_import_tree(records, args.threshold)
    
    # Sort and display top slowest self-time imports
    top_slowest = sorted(records, key=lambda x: x['self_ms'], reverse=True)[:args.top]
    
    print_colored(f"\nTop {args.top} Slowest Individual Imports (Self-Time):", BOLD + CYAN)
    print(f"  {'Module Name':<40} | {'Self Time':<12} | {'Cumulative Time':<15}")
    print("  " + "-" * 73)
    for idx, r in enumerate(top_slowest):
        print(f"  {r['name']:<40} | {r['self_ms']:>8.2f} ms | {r['cum_ms']:>10.2f} ms")
        
    # Summary of total startup cost
    # The last record of depth 0 represents the entry point module imports finishing
    # Or we can sum self_ms of all records (which equals cumulative of the roots)
    roots = [r for r in records if r['depth'] == 0]
    total_duration = sum(r['cum_ms'] for r in roots)
    print("\n" + "=" * 80)
    print_colored(f"Total Startup Import Duration: {total_duration:.2f} ms", BOLD + GREEN)
    print("=" * 80)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
