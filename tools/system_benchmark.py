#!/usr/bin/env python3
"""
System Benchmark - Test CPU, Memory, and Disk I/O performance

A lightweight hardware benchmarking utility that measures:
1. CPU speed (Single-core prime number calculation and matrix multiplication)
2. Memory bandwidth (Large array allocation, copying, and sorting)
3. Disk I/O speed (Sequential writing and reading of large block sizes)

Usage:
    python tools/system_benchmark.py [--disk-size MB] [--quick]

Example:
    python tools/system_benchmark.py --disk-size 20
"""

import argparse
import os
import sys
import time
import tempfile
from typing import Dict, Any

def run_cpu_test(duration_limit: float = 3.0) -> Dict[str, Any]:
    """Test CPU math processing performance."""
    print("Running CPU Benchmark...", end="", flush=True)
    
    # 1. Prime search
    start_time = time.time()
    count = 0
    num = 2
    primes = []
    # Trial division to find primes
    while time.time() - start_time < duration_limit / 2:
        is_prime = True
        for i in range(2, int(num ** 0.5) + 1):
            if num % i == 0:
                is_prime = False
                break
        if is_prime:
            primes.append(num)
            count += 1
        num += 1
    primes_duration = time.time() - start_time
    primes_per_sec = count / primes_duration if primes_duration > 0 else 0
    
    # 2. Matrix Multiplication (100x100 float matrix)
    size = 100
    matrix_a = [[float(i + j) for j in range(size)] for i in range(size)]
    matrix_b = [[float(i - j) for j in range(size)] for i in range(size)]
    
    start_time = time.time()
    matrix_ops = 0
    while time.time() - start_time < duration_limit / 2:
        # standard 100x100 matrix multiplication
        result = [[0.0 for _ in range(size)] for _ in range(size)]
        for i in range(size):
            for j in range(size):
                s = 0.0
                for k in range(size):
                    s += matrix_a[i][k] * matrix_b[k][j]
                result[i][j] = s
        matrix_ops += 1
    matrix_duration = time.time() - start_time
    matrix_ops_per_sec = matrix_ops / matrix_duration if matrix_duration > 0 else 0
    
    print(" Done!")
    return {
        "primes_per_sec": int(primes_per_sec),
        "matrix_ops_per_sec": int(matrix_ops_per_sec)
    }

def run_memory_test(duration_limit: float = 3.0) -> Dict[str, Any]:
    """Test Memory allocation, read, write, and sort performance."""
    print("Running Memory Benchmark...", end="", flush=True)
    
    start_time = time.time()
    iterations = 0
    array_size = 100000  # 100k items
    
    while time.time() - start_time < duration_limit:
        # Create
        lst = list(range(array_size))
        # Modify
        lst = [x * 2 for x in lst]
        # Reverse
        lst.reverse()
        # Sort
        lst.sort()
        iterations += 1
        
    duration = time.time() - start_time
    ops_per_sec = iterations / duration if duration > 0 else 0
    
    print(" Done!")
    return {
        "mem_ops_per_sec": int(ops_per_sec),
        "array_size": array_size
    }

def run_disk_test(file_size_mb: int) -> Dict[str, Any]:
    """Test Disk I/O write and read performance using a temporary file."""
    print(f"Running Disk Benchmark ({file_size_mb} MB)...", end="", flush=True)
    
    # Generate mock binary payload of 1MB
    chunk_size = 1024 * 1024  # 1MB
    payload = os.urandom(chunk_size)
    
    temp_dir = tempfile.gettempdir()
    temp_filepath = os.path.join(temp_dir, f"benchmark_{int(time.time())}.tmp")
    
    # Write speed
    start_time = time.time()
    try:
        with open(temp_filepath, "wb") as f:
            for _ in range(file_size_mb):
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())  # force write to storage media
        write_duration = time.time() - start_time
        write_speed = file_size_mb / write_duration if write_duration > 0 else 0
        
        # Read speed
        start_time = time.time()
        with open(temp_filepath, "rb") as f:
            while True:
                data = f.read(chunk_size)
                if not data:
                    break
        read_duration = time.time() - start_time
        read_speed = file_size_mb / read_duration if read_duration > 0 else 0
        
    finally:
        # Cleanup file
        if os.path.exists(temp_filepath):
            try:
                os.remove(temp_filepath)
            except Exception:
                pass
                
    print(" Done!")
    return {
        "write_speed_mbs": round(write_speed, 2),
        "read_speed_mbs": round(read_speed, 2)
    }

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Benchmark system CPU, Memory, and Disk I/O performance."
    )
    parser.add_argument(
        "--disk-size",
        type=int,
        default=25,
        help="Size of the test file in MB for disk benchmarking (default: 25)"
    )
    parser.add_argument(
        "--quick", "-q",
        action="store_true",
        help="Reduce test duration for quicker results"
    )
    
    args = parser.parse_args()
    duration = 1.5 if args.quick else 3.0
    
    print("=" * 60)
    print("System Benchmark Tool")
    print("=" * 60)
    
    cpu_res = run_cpu_test(duration)
    mem_res = run_memory_test(duration)
    disk_res = run_disk_test(args.disk_size)
    
    print("\n" + "=" * 60)
    print("Benchmark Results Summary")
    print("=" * 60)
    print(f"CPU - Prime Numbers Discovered/sec  : {cpu_res['primes_per_sec']:,}")
    print(f"CPU - 100x100 Matrix Multiplies/sec : {cpu_res['matrix_ops_per_sec']:,}")
    print(f"Memory - Operations/sec (100k array): {mem_res['mem_ops_per_sec']:,}")
    print(f"Disk Write Throughput (Sequential)  : {disk_res['write_speed_mbs']} MB/s")
    print(f"Disk Read Throughput (Sequential)   : {disk_res['read_speed_mbs']} MB/s")
    print("=" * 60)
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
