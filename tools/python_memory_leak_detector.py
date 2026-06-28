#!/usr/bin/env python3
"""
Python Memory Leak Detector & Analyzer
Executes a target Python function or code block repeatedly to detect memory growth,
unreleased references, and analyze memory allocating hotspots.
Uses built-in `tracemalloc` and `gc` modules (no external dependencies).
"""

import argparse
import gc
import importlib.util
import os
import sys
import tracemalloc
from collections import Counter

# ANSI Colors
CLR_RESET = "\033[0m"
CLR_RED = "\033[91m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_CYAN = "\033[96m"
CLR_BOLD = "\033[1m"

def print_banner():
    print(f"{CLR_BOLD}{CLR_CYAN}")
    print(" ┌────────────────────────────────────────────────────────┐")
    print(" │          Python Memory Leak Detector & Analyzer        │")
    print(" │    Monitor reference counts & memory block growth      │")
    print(" └────────────────────────────────────────────────────────┘")
    print(CLR_RESET)

def format_size(size_bytes):
    """Format bytes to human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"

def get_tracked_object_types():
    """Returns a count of all current objects grouped by their type name."""
    type_counts = Counter()
    for obj in gc.get_objects():
        type_counts[type(obj).__name__] += 1
    return type_counts

def load_module_from_path(module_path):
    """Dynamically loads a Python module from its path."""
    if not os.path.exists(module_path):
        print(f"Error: Path '{module_path}' not found.", file=sys.stderr)
        sys.exit(1)
        
    module_name = os.path.splitext(os.path.basename(module_path))[0]
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        print(f"Error: Could not load spec for '{module_path}'.", file=sys.stderr)
        sys.exit(1)
        
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as e:
        print(f"Error executing module '{module_path}': {e}", file=sys.stderr)
        sys.exit(1)
    return module

def run_leak_test(target_fn, iterations=50, warmups=5, show_tracebacks=3):
    """Executes target_fn repeatedly, monitoring memory and objects."""
    print(f"Starting memory leak test on target function...")
    print(f"Warmup runs: {warmups} | Test runs: {iterations}")
    print("-" * 65)

    # 1. Warmup phase (let Python initialize modules, caches, etc.)
    for _ in range(warmups):
        target_fn()
    
    # Force complete garbage collection
    gc.collect()
    
    # Start tracemalloc
    tracemalloc.start()
    
    # 2. Get baseline state
    baseline_objects = get_tracked_object_types()
    baseline_snapshot = tracemalloc.take_snapshot()
    baseline_count = len(gc.get_objects())
    
    print(f"Baseline tracked objects: {baseline_count}")
    print(f"Baseline memory allocated: {format_size(tracemalloc.get_traced_memory()[0])}")
    print("Running iterations...")
    
    # 3. Execution Phase
    for idx in range(1, iterations + 1):
        target_fn()
        if idx % max(1, iterations // 5) == 0 or idx == iterations:
            gc.collect()
            current_mem = tracemalloc.get_traced_memory()[0]
            print(f"  Iteration {idx:4d}/{iterations}: Mem = {format_size(current_mem)} | Tracked objects = {len(gc.get_objects())}")
            
    # Force final collection
    gc.collect()
    
    # 4. Analyze results
    final_objects = get_tracked_object_types()
    final_snapshot = tracemalloc.take_snapshot()
    final_count = len(gc.get_objects())
    final_mem = tracemalloc.get_traced_memory()[0]
    
    # Stop tracing
    tracemalloc.stop()
    
    print("\n" + "=" * 65)
    print(f"{CLR_BOLD}Memory Leak Assessment Report{CLR_RESET}")
    print("=" * 65)
    
    # Object counts diff
    object_diff = Counter()
    for k, v in final_objects.items():
        diff = v - baseline_objects.get(k, 0)
        if diff > 0:
            object_diff[k] = diff
            
    # Memory size diff
    stats = final_snapshot.compare_to(baseline_snapshot, 'lineno')
    total_leak_bytes = sum(stat.size_diff for stat in stats)
    
    leak_detected = False
    if total_leak_bytes > 1024 * 10:  # > 10 KB leak threshold
        leak_detected = True
        print(f"🚨 {CLR_RED}{CLR_BOLD}MEMORY LEAK DETECTED!{CLR_RESET}")
        print(f"   Net memory growth: {CLR_RED}{format_size(total_leak_bytes)}{CLR_RESET}")
        print(f"   Net object growth: {final_count - baseline_count} tracked objects")
    else:
        print(f"✅ {CLR_GREEN}{CLR_BOLD}NO CRITICAL MEMORY LEAK DETECTED.{CLR_RESET}")
        print(f"   Net memory growth: {CLR_GREEN}{format_size(total_leak_bytes)}{CLR_RESET}")
        print(f"   Net object growth: {final_count - baseline_count} tracked objects")
        
    print("-" * 65)
    
    # Top Leaking Object Types
    if object_diff:
        print(f"\n{CLR_BOLD}Top growing object types (by count):{CLR_RESET}")
        for type_name, count in object_diff.most_common(5):
            print(f"  • {type_name:<25} : +{count} objects")
            
    # Top Memory Allocation Sources (tracemalloc)
    top_stats = [s for s in stats if s.size_diff > 0][:show_tracebacks]
    if top_stats:
        print(f"\n{CLR_BOLD}Top memory allocation hotspots (by file/line):{CLR_RESET}")
        for idx, stat in enumerate(top_stats, 1):
            frame = stat.traceback[0]
            print(f"  {idx}. {frame.filename}:{frame.lineno}")
            print(f"     Growth: {CLR_YELLOW}{format_size(stat.size_diff)}{CLR_RESET} (+{stat.count_diff} allocations)")
            
            # Print code line if available
            try:
                import linecache
                line = linecache.getline(frame.filename, frame.lineno).strip()
                if line:
                    print(f"     Code:   {CLR_CYAN}{line}{CLR_RESET}")
            except Exception:
                pass
            print()
            
    print("=" * 65 + "\n")

def main():
    print_banner()
    parser = argparse.ArgumentParser(description="Python Memory Leak Detector & Analyzer")
    parser.add_argument("script", help="Path to Python script or module to test")
    parser.add_argument("-f", "--function", default="run", help="Function name in the script to call repeatedly (default: 'run')")
    parser.add_argument("-i", "--iterations", type=int, default=100, help="Number of test iterations to execute (default: 100)")
    parser.add_argument("-w", "--warmup", type=int, default=10, help="Number of warmup iterations to run before starting capture (default: 10)")
    parser.add_argument("-t", "--tracebacks", type=int, default=5, help="Number of top memory-allocating tracebacks to show (default: 5)")
    
    args = parser.parse_args()
    
    # Load module and get function
    print(f"Loading '{args.script}'...")
    module = load_module_from_path(args.script)
    
    if not hasattr(module, args.function):
        print(f"Error: Function '{args.function}' not found in '{args.script}'.", file=sys.stderr)
        # Search for callable functions as helper
        funcs = [name for name, val in vars(module).items() if callable(val) and not name.startswith("__")]
        if funcs:
            print(f"Available functions: {', '.join(funcs)}", file=sys.stderr)
        return 1
        
    target_fn = getattr(module, args.function)
    
    run_leak_test(
        target_fn=target_fn,
        iterations=args.iterations,
        warmups=args.warmup,
        show_tracebacks=args.tracebacks
    )
    return 0

if __name__ == "__main__":
    sys.exit(main())
