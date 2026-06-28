#!/usr/bin/env python3
"""
Python Micro-Benchmarker
Compare the performance of multiple Python code snippets side-by-side.
Provides statistical analysis (mean, median, standard deviation) and renders
a clean terminal ASCII bar chart of execution speeds and speedup factors.
"""

import argparse
import math
import statistics
import sys
import timeit
from typing import Dict, List, Tuple

# ANSI colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_CYAN = "\033[36m"
COLOR_MAGENTA = "\033[35m"

def auto_determine_number(snippet: str, setup: str, target_time: float = 0.1) -> int:
    """Finds an appropriate iteration count so the snippet runs for about `target_time` seconds."""
    number = 1
    while True:
        try:
            t = timeit.timeit(snippet, setup=setup, number=number)
            if t >= target_time:
                return number
            # Scale up rapidly
            if t == 0:
                number *= 10
            else:
                number = int(number * (target_time / t) * 1.5)
                # Keep it at least double
                number = max(number, 10)
        except Exception as e:
            print(f"{COLOR_RED}Error running snippet: {e}{COLOR_RESET}", file=sys.stderr)
            sys.exit(1)
        if number > 10_000_000:
            return 10_000_000

def run_benchmark(
    name: str, 
    snippet: str, 
    setup: str, 
    number: int, 
    repeats: int
) -> List[float]:
    """Runs a benchmark repeating it `repeats` times, returning execution times per single run."""
    # timeit.repeat returns total time for `number` iterations
    raw_times = timeit.repeat(snippet, setup=setup, number=number, repeat=repeats)
    # Convert to time per single execution (in microseconds)
    single_run_micros = [(t / number) * 1_000_000 for t in raw_times]
    return single_run_micros

def render_ascii_bars(results: List[Tuple[str, Dict[str, float]]], width: int = 30) -> None:
    """Renders visual ASCII bar charts comparing mean execution times."""
    if not results:
        return
        
    # Find max mean time to scale the bars
    max_mean = max(r[1]['mean'] for r in results)
    
    print(f"\n{COLOR_BOLD}=== Performance Comparison (Lower is Better) ==={COLOR_RESET}")
    for name, stats in results:
        mean = stats['mean']
        bar_len = int((mean / max_mean) * width)
        # Prevent division by zero or extremely small length
        bar_len = max(bar_len, 1)
        
        # Color fastest green, slowest red, others yellow
        if mean == min(r[1]['mean'] for r in results):
            color = COLOR_GREEN
            tag = " [FASTEST]"
        elif mean == max_mean:
            color = COLOR_RED
            tag = " [SLOWEST]"
        else:
            color = COLOR_YELLOW
            tag = ""
            
        bar = "█" * bar_len
        print(f"  {name:<25} : {mean:>10.4f} µs/op {color}{bar:<{width}}{COLOR_RESET}{tag}")

def main():
    parser = argparse.ArgumentParser(
        description="Compare execution times and stats of multiple Python snippets."
    )
    parser.add_argument(
        "-s", "--snippet", 
        action="append", 
        required=True, 
        help="Python code snippet to benchmark (can specify multiple times)"
    )
    parser.add_argument(
        "--setup", 
        default="pass", 
        help="Setup code run before the benchmarked snippets (default: 'pass')"
    )
    parser.add_argument(
        "-r", "--repeat", 
        type=int, 
        default=5, 
        help="Number of times to repeat the benchmark run (default: 5)"
    )
    parser.add_argument(
        "-n", "--number", 
        type=int, 
        help="Number of loop iterations per repeat. If omitted, it is auto-determined."
    )
    
    args = parser.parse_args()
    
    if len(args.snippet) < 2:
        print(f"{COLOR_RED}Error: You must specify at least two snippets to compare.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)
        
    snippets = {}
    for idx, code in enumerate(args.snippet, 1):
        # Allow labels like "label:code_content"
        if ":" in code and "\n" not in code.split(":", 1)[0] and len(code.split(":", 1)[0]) < 30:
            name, snip = code.split(":", 1)
            snippets[name.strip()] = snip.strip()
        else:
            snippets[f"Snippet {idx}"] = code
            
    print(f"{COLOR_CYAN}Initializing micro-benchmarks...{COLOR_RESET}")
    print(f"Setup code: {COLOR_MAGENTA}{args.setup}{COLOR_RESET}\n")
    
    results = []
    
    for name, snippet in snippets.items():
        print(f"Benchmarking '{COLOR_BOLD}{name}{COLOR_RESET}'...")
        
        # Determine number of iterations
        if args.number:
            num = args.number
        else:
            num = auto_determine_number(snippet, args.setup)
            print(f"  Auto-selected iterations: {num:,}")
            
        times = run_benchmark(name, snippet, args.setup, num, args.repeat)
        
        mean_val = statistics.mean(times)
        median_val = statistics.median(times)
        std_dev = statistics.stdev(times) if len(times) > 1 else 0.0
        
        results.append((name, {
            'mean': mean_val,
            'median': median_val,
            'stddev': std_dev,
            'min': min(times),
            'max': max(times)
        }))
        
        print(f"  Mean: {mean_val:.4f} µs | Median: {median_val:.4f} µs | StdDev: {std_dev:.4f} µs")
        
    # Sort results from fastest to slowest
    results.sort(key=lambda x: x[1]['mean'])
    
    # Render comparison chart
    render_ascii_bars(results)
    
    # Calculate speedup factors relative to the fastest
    fastest_name, fastest_stats = results[0]
    fastest_mean = fastest_stats['mean']
    
    print(f"\n{COLOR_BOLD}=== Speedup Analysis ==={COLOR_RESET}")
    print(f"  Fastest: {COLOR_GREEN}{fastest_name}{COLOR_RESET}")
    for name, stats in results[1:]:
        factor = stats['mean'] / fastest_mean
        print(f"  {COLOR_GREEN}{fastest_name}{COLOR_RESET} is {COLOR_BOLD}{factor:.2f}x{COLOR_RESET} faster than {COLOR_RED}{name}{COLOR_RESET}")

if __name__ == "__main__":
    main()
