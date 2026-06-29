#!/usr/bin/env python3
"""
Python Runtime Complexity Estimator
Estimates the Big-O asymptotic complexity of a Python function by measuring execution
runtimes over varying input sizes and fitting them to standard complexity models.
Renders an ASCII graph of results.
"""

import argparse
import math
import sys
import time
import random
from typing import Callable, List, Tuple, Dict

# Demo algorithms to test the tool
def bubble_sort(arr: List[int]) -> List[int]:
    n = len(arr)
    arr_copy = list(arr)
    for i in range(n):
        for j in range(0, n - i - 1):
            if arr_copy[j] > arr_copy[j + 1]:
                arr_copy[j], arr_copy[j + 1] = arr_copy[j + 1], arr_copy[j]
    return arr_copy

def quick_sort(arr: List[int]) -> List[int]:
    if len(arr) <= 1:
        return arr
    pivot = arr[len(arr) // 2]
    left = [x for x in arr if x < pivot]
    middle = [x for x in arr if x == pivot]
    right = [x for x in arr if x > pivot]
    return quick_sort(left) + middle + quick_sort(right)

def linear_search(arr: List[int], target: int) -> int:
    for i, x in enumerate(arr):
        if x == target:
            return i
    return -1

def binary_search(arr: List[int], target: int) -> int:
    low = 0
    high = len(arr) - 1
    while low <= high:
        mid = (low + high) // 2
        if arr[mid] < target:
            low = mid + 1
        elif arr[mid] > target:
            high = mid - 1
        else:
            return mid
    return -1

def recursive_fibonacci(n: int) -> int:
    if n <= 1:
        return n
    return recursive_fibonacci(n - 1) + recursive_fibonacci(n - 2)

# Models dictionary containing function f(N) and description
COMPLEXITY_MODELS = {
    "O(1)": {
        "func": lambda n: 1.0,
        "desc": "Constant Time",
        "expr": "c"
    },
    "O(log N)": {
        "func": lambda n: math.log2(n) if n > 1 else 0.0,
        "desc": "Logarithmic Time",
        "expr": "c * log2(N)"
    },
    "O(N)": {
        "func": lambda n: float(n),
        "desc": "Linear Time",
        "expr": "c * N"
    },
    "O(N log N)": {
        "func": lambda n: n * math.log2(n) if n > 1 else 0.0,
        "desc": "Linearithmic Time",
        "expr": "c * N * log2(N)"
    },
    "O(N^2)": {
        "func": lambda n: float(n ** 2),
        "desc": "Quadratic Time",
        "expr": "c * N^2"
    },
    "O(2^N)": {
        "func": lambda n: float(2 ** n) if n < 50 else float('inf'),
        "desc": "Exponential Time",
        "expr": "c * 2^N"
    }
}

def generate_demo_input(algo_name: str, size: int) -> tuple:
    """Generates appropriate inputs for different algorithms."""
    if algo_name in ["bubble_sort", "quick_sort"]:
        # Random list of integers
        return (list(range(size)),)
    elif algo_name == "linear_search":
        # Search for item not in list to trigger worst-case
        return (list(range(size)), -1)
    elif algo_name == "binary_search":
        # Search in a sorted list
        return (list(range(size)), -1)
    elif algo_name == "fibonacci":
        # Fibonacci grows exponentially, so size is scale index (N must be small)
        # N maps sizes to small numbers
        n_val = min(max(5, int(math.log2(size) * 2.5)), 30)
        return (n_val,)
    return (size,)

def measure_runtime(func: Callable, args_generator: Callable, sizes: List[int], repetitions: int = 3) -> List[float]:
    """Measures the execution time of a function across different sizes."""
    runtimes = []
    print(f"\n[*] Running performance benchmarks (repetitions={repetitions})...")
    print(f"{'Size (N)':<15}{'Measured Time (sec)':<25}")
    print("-" * 40)
    
    for size in sizes:
        times = []
        for _ in range(repetitions):
            args = args_generator(size)
            # Garbage collect before measurement to minimize noise
            import gc
            gc.collect()
            
            start_time = time.perf_counter()
            func(*args)
            end_time = time.perf_counter()
            times.append(end_time - start_time)
        
        # Take the minimum or average; minimum is usually more robust against CPU spikes
        avg_time = sum(times) / len(times)
        min_time = min(times)
        # Use minimum to represent the ideal execution time
        runtimes.append(min_time)
        print(f"{size:<15}{min_time:15.8f}s")
        
    return runtimes

def fit_complexity(sizes: List[int], runtimes: List[float]) -> Tuple[str, Dict[str, float]]:
    """Fits measured runtimes to complexity models using linear regression through the origin."""
    fits = {}
    best_r2 = -float('inf')
    best_model = "O(N)"
    
    # Calculate total sum of squares (about the mean runtime)
    mean_runtime = sum(runtimes) / len(runtimes)
    ss_tot = sum((y - mean_runtime) ** 2 for y in runtimes)
    
    # If all runtimes are identical, it's O(1)
    if ss_tot == 0:
        return "O(1)", {"O(1)": 1.0}
        
    for name, model in COMPLEXITY_MODELS.items():
        x_vals = [model["func"](n) for n in sizes]
        
        # Skip exponential if values got too large and became inf
        if any(math.isinf(x) or math.isnan(x) for x in x_vals):
            fits[name] = -1.0
            continue
            
        # Calculate slope 'c' using least squares regression through the origin: y = c * x
        # c = sum(x * y) / sum(x^2)
        sum_xy = sum(x * y for x, y in zip(x_vals, runtimes))
        sum_xx = sum(x * x for x in x_vals)
        
        if sum_xx == 0:
            c = 0.0
        else:
            c = sum_xy / sum_xx
            
        # Calculate residuals and sum of squared residuals
        # R2 = 1 - (SS_res / SS_tot)
        residuals = []
        for n, y in zip(sizes, runtimes):
            pred_y = c * model["func"](n)
            residuals.append(y - pred_y)
            
        ss_res = sum(r ** 2 for r in residuals)
        r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 0.0
        
        # Adjust R2 for constant models since ss_tot calculation might differ
        if name == "O(1)":
            # For O(1), fit y = mean_runtime
            ss_res_c = sum((y - mean_runtime) ** 2 for y in runtimes)
            r2 = 1.0 if ss_res_c == 0 else 0.0
            
        fits[name] = r2
        if r2 > best_r2:
            best_r2 = r2
            best_model = name
            
    return best_model, fits

def render_ascii_plot(sizes: List[int], runtimes: List[float], width: int = 60, height: int = 15):
    """Draws a beautiful ASCII plot of runtime vs size in the console."""
    min_x, max_x = min(sizes), max(sizes)
    min_y, max_y = min(runtimes), max(runtimes)
    
    # Avoid division by zero
    x_span = max_x - min_x if max_x != min_x else 1.0
    y_span = max_y - min_y if max_y != min_y else 1.0
    
    # Initialize grid
    grid = [[" " for _ in range(width)] for _ in range(height)]
    
    # Map points to grid
    for x, y in zip(sizes, runtimes):
        grid_x = int(((x - min_x) / x_span) * (width - 1))
        grid_y = int(((y - min_y) / y_span) * (height - 1))
        # Invert Y axis for terminal (top is index 0)
        grid_y_inverted = height - 1 - grid_y
        grid[grid_y_inverted][grid_x] = "o"

    print("\n" + "=" * (width + 10))
    print(f"{'RUNTIME PLOT':^{width + 10}}")
    print("=" * (width + 10))
    
    for r in range(height):
        # Y-axis label
        if r == 0:
            y_label = f"{max_y:8.4f}s |"
        elif r == height - 1:
            y_label = f"{min_y:8.4f}s |"
        else:
            y_label = "         |"
            
        row_content = "".join(grid[r])
        print(f"{y_label}{row_content}")
        
    # X-axis border
    print(" " * 9 + "+" + "-" * width)
    # X-axis label
    x_label_start = f"{min_x}"
    x_label_end = f"{max_x}"
    spacing = width - len(x_label_start) - len(x_label_end)
    print(" " * 10 + x_label_start + " " * spacing + x_label_end)
    print(f"{'Input Size (N)':^{width + 10}}\n")

def main():
    parser = argparse.ArgumentParser(
        description="Estimate the Big-O time complexity of Python functions."
    )
    parser.add_argument(
        "--demo", 
        choices=["bubble_sort", "quick_sort", "linear_search", "binary_search", "fibonacci"],
        default="bubble_sort", 
        help="Run a built-in algorithm demo (default: bubble_sort)"
    )
    parser.add_argument(
        "--sizes", 
        type=str, 
        default="100,200,400,800,1600,3200",
        help="Comma-separated list of input sizes N to test (default: 100,200,400,800,1600,3200)"
    )
    parser.add_argument(
        "--reps", 
        type=int, 
        default=3, 
        help="Number of repetitions to run for each size to filter noise (default: 3)"
    )
    args = parser.parse_args()
    
    # Parse sizes
    try:
        sizes = [int(s.strip()) for s in args.sizes.split(",")]
        sizes.sort()
        if len(sizes) < 3:
            raise ValueError("Please provide at least 3 sizes for estimation.")
    except Exception as e:
        print(f"[-] Error parsing sizes: {e}")
        sys.exit(1)
        
    # Map demo algorithms
    demo_functions = {
        "bubble_sort": (lambda arr: bubble_sort(arr), lambda s: generate_demo_input("bubble_sort", s)),
        "quick_sort": (lambda arr: quick_sort(arr), lambda s: generate_demo_input("quick_sort", s)),
        "linear_search": (linear_search, lambda s: generate_demo_input("linear_search", s)),
        "binary_search": (binary_search, lambda s: generate_demo_input("binary_search", s)),
        "fibonacci": (recursive_fibonacci, lambda s: generate_demo_input("fibonacci", s))
    }
    
    func, gen_args = demo_functions[args.demo]
    
    # Adjust default sizes for fibonacci to prevent long freezes
    if args.demo == "fibonacci":
        sizes = [5, 10, 15, 20, 25, 30]
        print(f"[*] Adjusted sizes for recursive fibonacci demo: {sizes}")
        
    print("=" * 60)
    print(f" Big-O Runtime Complexity Estimator - Demo: {args.demo.upper()}")
    print("=" * 60)
    
    try:
        # Measure times
        runtimes = measure_runtime(func, gen_args, sizes, repetitions=args.reps)
        
        # Fit complexity
        best_fit, fits = fit_complexity(sizes, runtimes)
        
        # Print results
        print("\n" + "=" * 40)
        print(f" ESTIMATED COMPLEXITY: {best_fit} - {COMPLEXITY_MODELS[best_fit]['desc']}")
        print("=" * 40)
        print(f"Formula: T(N) = {COMPLEXITY_MODELS[best_fit]['expr']}\n")
        
        print("Model goodness-of-fit (R^2 Coefficient, closer to 1.0 is better):")
        for model_name, r2 in sorted(fits.items(), key=lambda x: x[1], reverse=True):
            r2_str = f"{r2:.5f}" if r2 >= 0 else "N/A (Poor fit)"
            label = COMPLEXITY_MODELS[model_name]["desc"]
            highlight = " <-- BEST FIT" if model_name == best_fit else ""
            print(f"  - {model_name:<12} ({label:<20}): R^2 = {r2_str}{highlight}")
            
        # Draw ASCII plot
        render_ascii_plot(sizes, runtimes)
        
    except KeyboardInterrupt:
        print("\n[-] Benchmarking interrupted by user.")
    except Exception as e:
        print(f"\n[-] An error occurred during benchmarking: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
