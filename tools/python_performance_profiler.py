#!/usr/bin/env python3
"""
Python Performance Profiler - Profile CPU execution and memory usage of a Python script.

This tool executes a target Python script and profiles it using standard library
cProfile (for CPU execution times) and tracemalloc (for memory allocations).
It prints structured tables highlighting execution hot-spots.
"""

import os
import sys
import cProfile
import pstats
import tracemalloc
import argparse


def profile_script(script_path, script_args, sort_by="cumulative", limit=20, track_memory=True):
    """Executes and profiles the specified Python script."""
    # Resolve absolute script path
    script_abs_path = os.path.abspath(script_path)
    if not os.path.exists(script_abs_path):
        print(f"Error: Script '{script_path}' not found.", file=sys.stderr)
        return False

    # Adjust sys.argv and sys.path to mimic running the script directly
    original_argv = sys.argv
    original_path = sys.path
    
    sys.argv = [script_abs_path] + script_args
    # Add script's directory to sys.path
    script_dir = os.path.dirname(script_abs_path)
    sys.path.insert(0, script_dir)

    # Read script content
    try:
        with open(script_abs_path, 'rb') as f:
            code = compile(f.read(), script_abs_path, 'exec')
    except Exception as e:
        print(f"Error compiling script: {e}", file=sys.stderr)
        sys.path = original_path
        sys.argv = original_argv
        return False

    # Define standard globals for execution
    global_dict = {
        "__name__": "__main__",
        "__file__": script_abs_path,
        "__package__": None,
        "__cached__": None,
    }

    # Start memory tracing if requested
    if track_memory:
        tracemalloc.start()

    # Create profiler
    profiler = cProfile.Profile()
    
    print(f"[*] Starting execution of: {script_abs_path}")
    print("=" * 80)
    
    try:
        profiler.enable()
        # Execute the code block in the context of global_dict
        exec(code, global_dict)
        profiler.disable()
    except SystemExit as se:
        # Script exited via sys.exit()
        profiler.disable()
    except Exception as e:
        profiler.disable()
        print("\n[!] Script crashed during execution:")
        import traceback
        traceback.print_exc()
    finally:
        print("=" * 80)
        print("[*] Execution completed.")

        # Get memory statistics
        memory_stats = None
        if track_memory:
            snapshot = tracemalloc.take_snapshot()
            current, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            memory_stats = {
                "current": current,
                "peak": peak,
                "top_allocations": snapshot.statistics('lineno')
            }

        # Restore system environment
        sys.argv = original_argv
        sys.path = original_path

        # Print reports
        print_cpu_report(profiler, sort_by, limit)
        if memory_stats:
            print_memory_report(memory_stats, limit)

    return True


def format_bytes(bytes_count):
    """Format bytes into readable unit strings."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if bytes_count < 1024.0:
            return f"{bytes_count:.2f} {unit}"
        bytes_count /= 1024.0
    return f"{bytes_count:.2f} TB"


def print_cpu_report(profiler, sort_by, limit):
    """Prints cProfile call and execution time statistics."""
    stats = pstats.Stats(profiler)
    stats.strip_dirs()
    
    # Map friendly sort keys to pstats keys
    sort_map = {
        "cumulative": "cumulative",
        "time": "tottime",
        "calls": "calls",
        "name": "name",
        "file": "file"
    }
    
    stats.sort_stats(sort_map.get(sort_by, "cumulative"))
    
    print("\n" + "=" * 80)
    print(f"{'CPU EXECUTION PROFILE SUMMARY':^80}")
    print("=" * 80)
    
    # We load stats and display them cleanly
    stats.print_stats(limit)


def print_memory_report(memory_stats, limit):
    """Prints tracemalloc memory usage stats and top lines."""
    print("\n" + "=" * 80)
    print(f"{'MEMORY ALLOCATION PROFILE SUMMARY':^80}")
    print("=" * 80)
    print(f"Current Memory Usage: {format_bytes(memory_stats['current'])}")
    print(f"Peak Memory Allocated: {format_bytes(memory_stats['peak'])}")
    print("-" * 80)
    print(f"Top {limit} Memory Allocation Locations:")
    print("-" * 80)
    
    top_stats = memory_stats["top_allocations"]
    for idx, stat in enumerate(top_stats[:limit]):
        # Format the file path to be shorter
        file_path = stat.traceback[0].filename
        line_num = stat.traceback[0].lineno
        size_str = format_bytes(stat.size)
        print(f"#{idx+1:<2} {file_path}:{line_num:<5}  |  Allocated: {size_str}")
        
    print("=" * 80 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Python Performance Profiler - Profile CPU and memory of a python script."
    )
    parser.add_argument(
        "script",
        help="Path to the Python script to profile"
    )
    parser.add_argument(
        "args",
        nargs=argparse.REMAINDER,
        help="Arguments to pass to the target script"
    )
    parser.add_argument(
        "-s", "--sort",
        choices=["cumulative", "time", "calls", "name", "file"],
        default="cumulative",
        help="Sort CPU statistics by (default: cumulative)"
    )
    parser.add_argument(
        "-l", "--limit",
        type=int,
        default=20,
        help="Limit number of function/memory lines printed (default: 20)"
    )
    parser.add_argument(
        "--no-memory",
        action="store_true",
        help="Disable memory profiling/allocation tracking"
    )

    args = parser.parse_args()

    profile_script(
        script_path=args.script,
        script_args=args.args,
        sort_by=args.sort,
        limit=args.limit,
        track_memory=not args.no_memory
    )


if __name__ == "__main__":
    main()
