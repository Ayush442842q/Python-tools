#!/usr/bin/env python3
"""
System Benchmark Tool

Runs performance benchmarks on CPU, memory, disk I/O, and network latency.
Produces a summary report with speed ratings without using third-party packages.

Usage:
    python tools/system_benchmark.py [--no-cpu] [--no-mem] [--no-disk] [--no-net]
"""

import argparse
import os
import platform
import socket
import sys
import time
import tempfile
import urllib.request
import math
import subprocess

# ANSI styling
CLR_CYAN = "\033[96m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_RED = "\033[91m"
CLR_BOLD = "\033[1m"
CLR_RESET = "\033[0m"

def print_section(title):
    print(f"\n{CLR_CYAN}{CLR_BOLD}=== {title} ==={CLR_RESET}")

def get_system_info():
    info = {
        "OS": f"{platform.system()} {platform.release()} ({platform.machine()})",
        "Processor": platform.processor() or "Unknown",
        "Python Version": platform.python_version(),
        "Host Name": socket.gethostname()
    }
    return info

def run_cpu_benchmark(duration=2.0):
    """Measures single-core floating-point and integer performance."""
    print("Running CPU Single-Core Benchmark (floating-point & math operations)...")
    
    start_time = time.perf_counter()
    ops = 0
    
    # Run loop for target duration
    while time.perf_counter() - start_time < duration:
        # Perform some math calculations
        for x in range(10000):
            # Float arithmetic, trigonometry, square root
            _ = math.sqrt(x) * math.sin(x) + math.cos(x)
        ops += 10000
        
    elapsed = time.perf_counter() - start_time
    ops_per_sec = ops / elapsed
    
    # Prime numbers calculation benchmark
    print("Running CPU Prime Number Search (up to 15,000)...")
    prime_start = time.perf_counter()
    primes_found = 0
    for num in range(2, 15000):
        is_prime = True
        for i in range(2, int(math.isqrt(num)) + 1):
            if num % i == 0:
                is_prime = False
                break
        if is_prime:
            primes_found += 1
    prime_elapsed = time.perf_counter() - prime_start
    
    return {
        "math_ops_per_sec": ops_per_sec,
        "prime_time_secs": prime_elapsed,
        "primes_found": primes_found
    }

def run_memory_benchmark(size_mb=64, passes=5):
    """Measures memory allocation, read, and write bandwidth."""
    print(f"Running Memory Benchmark (allocating & processing {size_mb} MB array)...")
    
    # 1 MB of integers (approx 131072 integers for 64-bit systems)
    # We will use bytes to be exact. 1MB = 1024 * 1024 bytes.
    data_size = size_mb * 1024 * 1024
    
    # Allocation & Write Speed
    write_times = []
    for _ in range(passes):
        t0 = time.perf_counter()
        # Allocate and write zeroes
        arr = bytearray(data_size)
        # Force writing to memory pages
        for i in range(0, data_size, 4096):
            arr[i] = 1
        write_times.append(time.perf_counter() - t0)
        
    avg_write_time = sum(write_times) / passes
    write_speed = size_mb / avg_write_time # MB/s
    
    # Read Speed
    read_times = []
    for _ in range(passes):
        t0 = time.perf_counter()
        # Perform read by summing steps
        _ = sum(arr[::4096])
        read_times.append(time.perf_counter() - t0)
        
    avg_read_time = sum(read_times) / passes
    # We read 1 byte every 4096 bytes, but practically we walked the whole array.
    # To represent realistic memory bandwidth, we estimate based on active access.
    # Let's do a fast copy test for more accurate memory read/write measurement.
    copy_times = []
    for _ in range(passes):
        t0 = time.perf_counter()
        arr_copy = arr[:] # full memory copy
        copy_times.append(time.perf_counter() - t0)
        
    avg_copy_time = sum(copy_times) / passes
    copy_speed = (size_mb * 2) / avg_copy_time # Reading from source, writing to dest
    
    return {
        "write_speed_mbs": write_speed,
        "copy_speed_mbs": copy_speed
    }

def run_disk_benchmark(file_size_mb=50, block_size_kb=64):
    """Measures disk write and read throughput using a temporary file."""
    print(f"Running Disk Benchmark (writing/reading {file_size_mb} MB file)...")
    
    data = os.urandom(block_size_kb * 1024)
    num_blocks = (file_size_mb * 1024) // block_size_kb
    
    # Create temp file
    temp_dir = tempfile.gettempdir()
    temp_filepath = os.path.join(temp_dir, f"speedtest_{int(time.time())}.tmp")
    
    # Write speed
    t0 = time.perf_counter()
    try:
        with open(temp_filepath, 'wb', buffering=0) as f:
            for _ in range(num_blocks):
                f.write(data)
            os.fsync(f.fileno())  # force flush to disk
        write_elapsed = time.perf_counter() - t0
        write_speed = file_size_mb / write_elapsed
    except Exception as e:
        print(f"{CLR_RED}Disk write error: {e}{CLR_RESET}")
        write_speed = 0.0
        write_elapsed = 0.0
        
    # Read speed
    t0 = time.perf_counter()
    try:
        with open(temp_filepath, 'rb', buffering=0) as f:
            while f.read(block_size_kb * 1024):
                pass
        read_elapsed = time.perf_counter() - t0
        read_speed = file_size_mb / read_elapsed
    except Exception as e:
        print(f"{CLR_RED}Disk read error: {e}{CLR_RESET}")
        read_speed = 0.0
        read_elapsed = 0.0
    finally:
        # Clean up
        if os.path.exists(temp_filepath):
            try:
                os.remove(temp_filepath)
            except OSError:
                pass
                
    return {
        "write_speed_mbs": write_speed,
        "read_speed_mbs": read_speed
    }

def run_network_benchmark():
    """Measures DNS resolution speed and ping/HTTP response latencies."""
    print("Running Network Benchmark (HTTP connection and ping latency)...")
    
    # HTTP latency check
    http_start = time.perf_counter()
    http_ok = False
    try:
        # Connect to google.com
        urllib.request.urlopen("https://www.google.com", timeout=3.0)
        http_elapsed = (time.perf_counter() - http_start) * 1000 # to ms
        http_ok = True
    except Exception:
        http_elapsed = 9999.0
        
    # ICMP ping (using OS terminal command since raw sockets require root/administrator)
    ping_elapsed = None
    host = "1.1.1.1" # Cloudflare DNS
    try:
        if platform.system().lower() == "windows":
            cmd = ["ping", "-n", "2", host]
        else:
            cmd = ["ping", "-c", "2", host]
            
        t0 = time.perf_counter()
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=4.0)
        t_tot = (time.perf_counter() - t0) * 1000 / 2 # average of 2 pings roughly
        
        # Try to parse exact latency from command output
        lines = res.stdout.splitlines()
        for line in lines:
            if "Average" in line or "avg" in line:
                # e.g., "Minimum = 14ms, Maximum = 16ms, Average = 15ms"
                # or "rtt min/avg/max/mdev = 13.9/14.8/15.2/0.4 ms"
                parts = line.replace("=", "/").split("/")
                for p in parts:
                    clean_p = p.strip().lower().replace("ms", "")
                    try:
                        # Try to extract numbers
                        float_val = float(''.join(c for c in clean_p if c.isdigit() or c == '.'))
                        if float_val > 0:
                            ping_elapsed = float_val
                            break
                    except ValueError:
                        continue
        if ping_elapsed is None and res.returncode == 0:
            ping_elapsed = t_tot
    except Exception:
        pass

    return {
        "http_ok": http_ok,
        "http_latency_ms": http_elapsed,
        "ping_latency_ms": ping_elapsed
    }

def main():
    if sys.platform == 'win32':
        os.system('')  # Enable ANSI color escape sequences on Windows
        
    parser = argparse.ArgumentParser(
        description="System Benchmark Tool - Test single-core CPU, memory, disk I/O, and network speeds."
    )
    parser.add_argument("--no-cpu", action="store_true", help="Skip CPU benchmarks")
    parser.add_argument("--no-mem", action="store_true", help="Skip Memory benchmarks")
    parser.add_argument("--no-disk", action="store_true", help="Skip Disk I/O benchmarks")
    parser.add_argument("--no-net", action="store_true", help="Skip Network benchmarks")
    args = parser.parse_args()

    print("=" * 60)
    print(f"{CLR_GREEN}{CLR_BOLD}SYSTEM BENCHMARK TOOL{CLR_RESET}")
    print("=" * 60)

    # 1. System Information
    print_section("SYSTEM SPECIFICATIONS")
    sys_info = get_system_info()
    for key, val in sys_info.items():
        print(f"  {CLR_YELLOW}{key:<16}:{CLR_RESET} {val}")
        
    # 2. CPU Benchmarks
    if not args.no_cpu:
        print_section("CPU PERFORMANCE")
        cpu_res = run_cpu_benchmark()
        print(f"  Math Operations Speed : {CLR_GREEN}{cpu_res['math_ops_per_sec']/1000000:.2f} Million Ops/sec{CLR_RESET}")
        print(f"  Prime Number Search   : {CLR_GREEN}{cpu_res['prime_time_secs']:.4f} seconds{CLR_RESET} (found {cpu_res['primes_found']} primes)")
        
        # Rating estimation
        rating = "Excellent" if cpu_res['prime_time_secs'] < 0.2 else "Very Good" if cpu_res['prime_time_secs'] < 0.4 else "Good" if cpu_res['prime_time_secs'] < 0.8 else "Moderate"
        print(f"  CPU Performance Rating: {CLR_BOLD}{CLR_CYAN}{rating}{CLR_RESET}")
        
    # 3. Memory Benchmarks
    if not args.no_mem:
        print_section("MEMORY BANDWIDTH")
        mem_res = run_memory_benchmark()
        print(f"  Allocation & Write    : {CLR_GREEN}{mem_res['write_speed_mbs']:.2f} MB/s{CLR_RESET}")
        print(f"  Memory Copy Speed     : {CLR_GREEN}{mem_res['copy_speed_mbs']:.2f} MB/s{CLR_RESET}")
        
        rating = "Ultra High Speed" if mem_res['copy_speed_mbs'] > 5000 else "High Speed" if mem_res['copy_speed_mbs'] > 2000 else "Standard Speed"
        print(f"  Memory Rating         : {CLR_BOLD}{CLR_CYAN}{rating}{CLR_RESET}")
        
    # 4. Disk Benchmarks
    if not args.no_disk:
        print_section("DISK I/O THROUGHPUT")
        disk_res = run_disk_benchmark()
        print(f"  Sequential Write      : {CLR_GREEN}{disk_res['write_speed_mbs']:.2f} MB/s{CLR_RESET}")
        print(f"  Sequential Read       : {CLR_GREEN}{disk_res['read_speed_mbs']:.2f} MB/s{CLR_RESET}")
        
        rating = "NVMe-grade SSD" if disk_res['read_speed_mbs'] > 1000 else "SATA SSD" if disk_res['read_speed_mbs'] > 250 else "HDD"
        print(f"  Disk Hardware Class   : {CLR_BOLD}{CLR_CYAN}{rating}{CLR_RESET}")
        
    # 5. Network Benchmarks
    if not args.no_net:
        print_section("NETWORK DIAGNOSTICS")
        net_res = run_network_benchmark()
        if net_res["http_ok"]:
            print(f"  HTTP Request Latency  : {CLR_GREEN}{net_res['http_latency_ms']:.1f} ms{CLR_RESET}")
        else:
            print(f"  HTTP Request Latency  : {CLR_RED}Failed to connect{CLR_RESET}")
            
        if net_res["ping_latency_ms"] is not None:
            print(f"  ICMP Ping Latency     : {CLR_GREEN}{net_res['ping_latency_ms']:.1f} ms{CLR_RESET}")
            rating = "Excellent (Low Latency)" if net_res['ping_latency_ms'] < 20 else "Good" if net_res['ping_latency_ms'] < 50 else "Average" if net_res['ping_latency_ms'] < 100 else "High Latency"
            print(f"  Connection Quality    : {CLR_BOLD}{CLR_CYAN}{rating}{CLR_RESET}")
        else:
            print(f"  ICMP Ping Latency     : {CLR_YELLOW}Request Timed Out / Blocked{CLR_RESET}")

    print("\n" + "=" * 60)
    print(f"{CLR_GREEN}{CLR_BOLD}BENCHMARK COMPLETED SUCCESSFULLY{CLR_RESET}")
    print("=" * 60)
    return 0

if __name__ == "__main__":
    sys.exit(main())
