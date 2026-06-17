#!/usr/bin/env python3
"""
CPU & Memory Load Simulator
A utility to generate simulated CPU and Memory stress. Spawns multiprocessing workers
to saturate CPU cores and allocates requested memory amounts for a specified duration.
"""

import argparse
import multiprocessing
import os
import sys
import time


def cpu_stress_worker(stop_event):
    """Worker function that runs a busy loop to consume CPU."""
    # Run simple mathematical calculations continuously to keep CPU busy
    x = 0.0001
    while not stop_event.is_set():
        x = x * 1.000001
        if x > 1000.0:
            x = 0.0001


def parse_memory_string(mem_str):
    """Parse a memory string like '512M' or '2G' into bytes count."""
    if not mem_str:
        return 0
        
    mem_str = mem_str.upper().strip()
    try:
        if mem_str.endswith('G') or mem_str.endswith('GB'):
            num = float(mem_str.rstrip('GB').rstrip('G'))
            return int(num * 1024 * 1024 * 1024)
        elif mem_str.endswith('M') or mem_str.endswith('MB'):
            num = float(mem_str.rstrip('MB').rstrip('M'))
            return int(num * 1024 * 1024)
        elif mem_str.endswith('K') or mem_str.endswith('KB'):
            num = float(mem_str.rstrip('KB').rstrip('K'))
            return int(num * 1024)
        else:
            return int(mem_str)
    except ValueError:
        raise ValueError(f"Invalid memory format: '{mem_str}'. Use formats like '500M', '2G', or raw bytes.")


def main():
    parser = argparse.ArgumentParser(
        description="Simulate CPU and Memory loads for testing, diagnostics, and monitoring validation."
    )
    parser.add_argument("-c", "--cpu-cores", type=int, default=0,
                        help="Number of CPU cores to stress (default: 0). Use -1 to stress all cores.")
    parser.add_argument("-m", "--memory", default="0",
                        help="Amount of memory to allocate (e.g., '512M', '1.5G', '100000B')")
    parser.add_argument("-d", "--duration", type=int, default=10,
                        help="Duration of the load simulation in seconds (default: 10)")
    parser.add_argument("-i", "--interval", type=int, default=2,
                        help="Log updates interval in seconds (default: 2)")

    args = parser.parse_args()

    # Determine CPU Cores to stress
    total_cores = multiprocessing.cpu_count()
    target_cores = args.cpu_cores
    if target_cores == -1:
        target_cores = total_cores
    elif target_cores < 0:
        print(f"Error: Invalid CPU cores value '{args.cpu_cores}'", file=sys.stderr)
        return 1
    
    # Parse Memory limit
    try:
        mem_bytes = parse_memory_string(args.memory)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    if target_cores == 0 and mem_bytes == 0:
        print("Nothing to simulate. Please specify either --cpu-cores (-c) or --memory (-m).")
        parser.print_help()
        return 0

    print("==================================================")
    print("           System Load Generator                  ")
    print("==================================================")
    print(f"PID: {os.getpid()}")
    print(f"System Cores: {total_cores}")
    print(f"Stressing Cores: {target_cores}")
    if mem_bytes > 0:
        print(f"Allocating Memory: {args.memory} ({mem_bytes} bytes)")
    print(f"Duration: {args.duration} seconds")
    print("==================================================")

    # 1. Allocate Memory if requested
    holder = []
    if mem_bytes > 0:
        print("[*] Allocating memory...")
        try:
            # We allocate blocks of bytes. A single block of size mem_bytes
            # will reserve virtual memory. We touch pages by filling it with non-zero bytes.
            block_size = min(mem_bytes, 10 * 1024 * 1024) # 10MB blocks
            blocks_needed = mem_bytes // block_size
            remainder = mem_bytes % block_size
            
            for _ in range(blocks_needed):
                holder.append(bytearray(block_size))
            if remainder > 0:
                holder.append(bytearray(remainder))
                
            print(f"[+] Successfully allocated {args.memory} memory.")
        except MemoryError:
            print("[!] Error: Out of memory during allocation!", file=sys.stderr)
            return 1
            
    # 2. Stress CPU if requested
    cpu_processes = []
    stop_event = multiprocessing.Event()
    if target_cores > 0:
        print(f"[*] Spawning {target_cores} CPU stress worker process(es)...")
        for i in range(target_cores):
            p = multiprocessing.Process(
                target=cpu_stress_worker, 
                args=(stop_event,),
                name=f"CPUStressWorker-{i}"
            )
            p.daemon = True
            p.start()
            cpu_processes.append(p)
        print("[+] CPU workers active.")

    # 3. Wait/Monitor loop
    start_time = time.time()
    elapsed = 0.0
    print("[*] Simulation started. Press Ctrl+C to stop.")
    
    try:
        while elapsed < args.duration:
            sleep_time = min(args.interval, args.duration - elapsed)
            time.sleep(sleep_time)
            elapsed = time.time() - start_time
            print(f"  --> Elapsed: {elapsed:.1f}s / {args.duration}s")
            
        print("[*] Target duration reached.")
    except KeyboardInterrupt:
        print("\n[!] Simulation interrupted by user.")
    finally:
        # Clean up CPU workers
        if cpu_processes:
            print("[*] Stopping CPU stress workers...")
            stop_event.set()
            for p in cpu_processes:
                p.join(timeout=2)
                if p.is_alive():
                    p.terminate()
            print("[+] CPU workers stopped.")
            
        # Clean up Memory
        if holder:
            print("[*] Freeing allocated memory...")
            holder.clear()
            print("[+] Memory freed.")
            
    print("==================================================")
    print("        Simulation Completed Successfully         ")
    print("==================================================")
    return 0


if __name__ == "__main__":
    # On Windows, multiprocessing needs freeze_support or guard
    multiprocessing.freeze_support()
    sys.exit(main())
