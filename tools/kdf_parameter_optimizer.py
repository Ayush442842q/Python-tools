#!/usr/bin/env python3
"""
Cryptographic Key Derivation Function (KDF) Parameter Optimizer
Benchmarks PBKDF2 and Scrypt in the standard library to recommend safe,
hardware-tailored work factors targeting specific execution time budgets.

Features:
1. Benchmarks PBKDF2 (SHA-256) iterations vs execution time.
2. Benchmarks Scrypt parameter space (N, r, p) vs time and memory.
3. Automatically derives parameters required to hit 100ms, 250ms, and 500ms budgets.
4. Renders styled terminal comparison tables and provides OWASP/NIST configuration guidelines.
"""

import argparse
import hashlib
import os
import sys
import time
from typing import Dict, List, Tuple

# ANSI Colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"
COLOR_DIM = "\033[2m"

def supports_color() -> bool:
    platform_supports = sys.platform != "win32" or "ANSICON" in os.environ or "WT_SESSION" in os.environ
    is_a_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    return platform_supports and is_a_tty

if not supports_color():
    COLOR_RESET = ""
    COLOR_BOLD = ""
    COLOR_RED = ""
    COLOR_GREEN = ""
    COLOR_YELLOW = ""
    COLOR_BLUE = ""
    COLOR_CYAN = ""
    COLOR_DIM = ""


def benchmark_pbkdf2(password: bytes, salt: bytes, iterations: int) -> float:
    start = time.perf_counter()
    hashlib.pbkdf2_hmac("sha256", password, salt, iterations)
    return time.perf_counter() - start


def benchmark_scrypt(password: bytes, salt: bytes, n: int, r: int, p: int) -> Tuple[float, float]:
    # Calculate memory usage in MB
    # Scrypt memory = 128 * N * r bytes
    memory_mb = (128 * n * r) / (1024 * 1024)
    start = time.perf_counter()
    try:
        hashlib.scrypt(password, salt=salt, n=n, r=r, p=p)
        elapsed = time.perf_counter() - start
        return elapsed, memory_mb
    except (AttributeError, ValueError, OSError) as e:
        # scrypt might not be supported or error on certain system configurations/limits
        return -1.0, memory_mb


def optimize_pbkdf2(target_seconds: float) -> int:
    password = b"benchmark_password_123!"
    salt = os.urandom(16)
    
    # Run a quick calibration of 10k iterations
    cal_iterations = 20000
    dur = benchmark_pbkdf2(password, salt, cal_iterations)
    
    if dur <= 0:
        return 100000
        
    # Extrapolate iterations
    iterations_per_sec = cal_iterations / dur
    target_iterations = int(iterations_per_sec * target_seconds)
    
    # Round to nearest 10,000 for clean numbers
    target_iterations = max(10000, (target_iterations // 10000) * 10000)
    
    # Validate target
    actual_dur = benchmark_pbkdf2(password, salt, target_iterations)
    # Adjust slightly if actual duration differs
    if actual_dur > 0:
        target_iterations = int(target_iterations * (target_seconds / actual_dur))
        target_iterations = max(10000, (target_iterations // 10000) * 10000)
        
    return target_iterations


def optimize_scrypt(target_seconds: float) -> Tuple[int, int, int, float]:
    password = b"benchmark_password_123!"
    salt = os.urandom(16)
    
    # Try different values of N (must be power of 2)
    # Start with N=1024, r=8, p=1
    best_n, best_r, best_p = 1024, 8, 1
    best_time, best_mem = 0.0, 0.0
    
    for power in range(10, 18): # N from 1024 to 131072
        n = 2 ** power
        dur, mem = benchmark_scrypt(password, salt, n, 8, 1)
        if dur < 0:
            break
        best_n, best_time, best_mem = n, dur, mem
        if dur >= target_seconds:
            break
            
    return best_n, 8, 1, best_mem


def main():
    parser = argparse.ArgumentParser(
        description="Benchmarks standard library KDFs and optimizes parameters for custom duration targets.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--budget", type=float, default=0.25, help="Target processing time budget in seconds (default: 0.25)")
    parser.add_argument("--skip-scrypt", action="store_true", help="Skip benchmarking Scrypt algorithm")
    
    args = parser.parse_args()
    
    print(f"{COLOR_BOLD}{COLOR_CYAN}=== CRYPTOGRAPHIC KDF PARAMETER OPTIMIZER ==={COLOR_RESET}")
    print(f"Target Budget: {COLOR_BOLD}{args.budget * 1000:.0f} ms{COLOR_RESET}\n")
    
    password = b"supersecretpassword!"
    salt = os.urandom(16)
    
    # 1. Benchmark PBKDF2
    print(f"{COLOR_BOLD}Benchmarking PBKDF2 (SHA-256)...{COLOR_RESET}")
    pb_results = []
    test_iters = [50000, 100000, 300000, 600000]
    for it in test_iters:
        dur = benchmark_pbkdf2(password, salt, it)
        pb_results.append((it, dur))
        print(f"  {it:7,} iterations: {COLOR_YELLOW}{dur * 1000:6.1f} ms{COLOR_RESET}")
    print()
    
    # 2. Benchmark Scrypt
    sc_results = []
    scrypt_available = hasattr(hashlib, "scrypt") and not args.skip_scrypt
    if scrypt_available:
        print(f"{COLOR_BOLD}Benchmarking Scrypt (r=8, p=1)...{COLOR_RESET}")
        test_n = [1024, 2048, 4096, 8192, 16384, 32768]
        for n in test_n:
            dur, mem = benchmark_scrypt(password, salt, n, 8, 1)
            if dur >= 0:
                sc_results.append((n, dur, mem))
                print(f"  N={n:5,}: {COLOR_YELLOW}{dur * 1000:6.1f} ms{COLOR_RESET} (Memory: {mem:.2f} MB)")
            else:
                print(f"  N={n:5,}: {COLOR_RED}Failed/Unsupported{COLOR_RESET}")
        print()
    else:
        print(f"{COLOR_YELLOW}Scrypt benchmark skipped or unsupported on this platform.{COLOR_RESET}\n")

    # 3. Optimize for Targets
    print(f"{COLOR_BOLD}{COLOR_GREEN}=== Recommended Parameters for Time Budgets ==={COLOR_RESET}")
    budgets = [0.1, 0.25, 0.5] # 100ms, 250ms, 500ms
    
    # Header
    print(f"┌───────────┬────────────────────────────────┬────────────────────────────────────────┐")
    print(f"│ Budget    │ PBKDF2 (SHA-256) Iterations    │ Scrypt (r=8, p=1)                      │")
    print(f"├───────────┼────────────────────────────────┼────────────────────────────────────────┤")
    
    for b in budgets:
        rec_pb = optimize_pbkdf2(b)
        
        if scrypt_available:
            n, r, p, mem = optimize_scrypt(b)
            sc_str = f"N={n:<6,} (Memory: {mem:4.1f} MB)"
        else:
            sc_str = "Unsupported"
            
        highlight = COLOR_GREEN if abs(b - args.budget) < 0.01 else ""
        reset = COLOR_RESET if highlight else ""
        
        print(f"│ {highlight}{b*1000:3.0f} ms{reset}    │ {highlight}{rec_pb:<30,}{reset} │ {highlight}{sc_str:<38}{reset} │")
        
    print(f"└───────────┴────────────────────────────────┴────────────────────────────────────────┘")
    print()
    
    # 4. Standards and Guidelines
    print(f"{COLOR_BOLD}OWASP / NIST Password Hashing Guidelines (2026):{COLOR_RESET}")
    print(f"  - {COLOR_BOLD}PBKDF2-HMAC-SHA256{COLOR_RESET}: Minimum recommendation is {COLOR_BOLD}600,000{COLOR_RESET} iterations (OWASP).")
    print(f"  - {COLOR_BOLD}Scrypt{COLOR_RESET}: Recommended parameters are N={COLOR_BOLD}65,536{COLOR_RESET}, r=8, p=1 (NIST SP 800-63B).")
    print(f"  - {COLOR_BOLD}Argon2id{COLOR_RESET}: Recommended default (if library available) is m=65536 (64MB), t=3, p=4.")
    print()
    print(f"{COLOR_DIM}Note: Parameters should be scaled up according to your server capacity and user authentication latency budget.{COLOR_RESET}")


if __name__ == "__main__":
    main()
