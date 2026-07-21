#!/usr/bin/env python3
"""
Command Benchmarker - Benchmark execution times of shell commands with detailed statistical reporting.
"""

import sys
import argparse
import subprocess
import time
import math
import json

def run_command(command, use_shell=True, show_output=False):
    """Executes the command once and returns the duration in seconds."""
    start_time = time.perf_counter()
    
    stdout_val = None if show_output else subprocess.PIPE
    stderr_val = None if show_output else subprocess.PIPE
    
    process = subprocess.run(
        command,
        shell=use_shell,
        stdout=stdout_val,
        stderr=stderr_val,
        text=True
    )
    
    duration = time.perf_counter() - start_time
    return duration, process.returncode

def calculate_stats(durations):
    """Calculates statistics for a list of numbers."""
    if not durations:
        return {}
        
    n = len(durations)
    total = sum(durations)
    mean = total / n
    
    sorted_durs = sorted(durations)
    if n % 2 == 1:
        median = sorted_durs[n // 2]
    else:
        median = (sorted_durs[n // 2 - 1] + sorted_durs[n // 2]) / 2.0
        
    minimum = sorted_durs[0]
    maximum = sorted_durs[-1]
    
    # Standard deviation
    variance = sum((x - mean) ** 2 for x in durations) / max(1, n - 1)
    stddev = math.sqrt(variance)
    
    return {
        "runs": n,
        "min": minimum,
        "max": maximum,
        "mean": mean,
        "median": median,
        "stddev": stddev,
        "total": total
    }

def print_table(stats):
    """Prints a styled ASCII table of results."""
    print("\nBenchmark Results:")
    print("+" + "-" * 22 + "+" + "-" * 18 + "+")
    print(f"| {'Metric':<20} | {'Value (seconds)':<16} |")
    print("+" + "-" * 22 + "+" + "-" * 18 + "+")
    print(f"| {'Total Runs':<20} | {stats['runs']:<16} |")
    print(f"| {'Minimum Time':<20} | {stats['min']:<16.5f} |")
    print(f"| {'Maximum Time':<20} | {stats['max']:<16.5f} |")
    print(f"| {'Mean (Average)':<20} | {stats['mean']:<16.5f} |")
    print(f"| {'Median':<20} | {stats['median']:<16.5f} |")
    print(f"| {'Std Dev':<20} | {stats['stddev']:<16.5f} |")
    print(f"| {'Total Time':<20} | {stats['total']:<16.5f} |")
    print("+" + "-" * 22 + "+" + "-" * 18 + "+")

def main():
    parser = argparse.ArgumentParser(
        description="Command Benchmarker - Benchmark execution times of shell commands."
    )
    parser.add_argument("command", help="The command line string to benchmark")
    parser.add_argument(
        "-r", "--runs", type=int, default=10,
        help="Number of benchmark runs (default: 10)"
    )
    parser.add_argument(
        "-w", "--warmup", type=int, default=2,
        help="Number of warmup runs before recording stats (default: 2)"
    )
    parser.add_argument(
        "--no-shell", action="store_true",
        help="Do not run the command inside a shell subprocess"
    )
    parser.add_argument(
        "--show-output", action="store_true",
        help="Show target command output (stdout/stderr)"
    )
    parser.add_argument(
        "--json", action="store_true",
        help="Output stats in raw JSON format"
    )
    
    args = parser.parse_args()
    
    use_shell = not args.no_shell
    
    if args.warmup > 0:
        if not args.json:
            print(f"Performing {args.warmup} warmup run(s)...")
        for i in range(args.warmup):
            _, code = run_command(args.command, use_shell, args.show_output)
            if code != 0 and not args.json:
                print(f"Warning: Warmup run {i+1} exited with non-zero code {code}")
                
    durations = []
    if not args.json:
        print(f"Running benchmark ({args.runs} runs)...")
        
    for i in range(args.runs):
        duration, code = run_command(args.command, use_shell, args.show_output)
        if code != 0 and not args.json:
            print(f"Warning: Run {i+1} exited with non-zero code {code}")
        durations.append(duration)
        if not args.json and not args.show_output:
            # Progress update
            sys.stdout.write(f"\rProgress: {i+1}/{args.runs} complete")
            sys.stdout.flush()
            
    if not args.json and not args.show_output:
        print() # New line after progress
        
    stats = calculate_stats(durations)
    
    if args.json:
        # Include raw durations in JSON output
        stats["durations"] = durations
        print(json.dumps(stats, indent=2))
    else:
        print(f"\nCommand: {args.command}")
        print_table(stats)

if __name__ == "__main__":
    main()
