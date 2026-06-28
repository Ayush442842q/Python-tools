#!/usr/bin/env python3
r"""
Regex Performance Tester & Optimizer
Benchmark regular expression compilation and match operations, statically analyze
patterns for catastrophic backtracking risks (ReDoS), and run empirical scaling tests.

Usage:
    python tools/regex_performance_tester.py -p "(\d+)+$" -t "1234567890"
    python tools/regex_performance_tester.py -p "(a+)+$" --redos-test
"""

import argparse
import re
import time
import timeit
import sys
from typing import List, Tuple


# ANSI Escape Codes for colorized output
COLOR_HEADER = "\033[95m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"
COLOR_GREEN = "\033[92m"
COLOR_WARNING = "\033[93m"
COLOR_FAIL = "\033[91m"
COLOR_END = "\033[0m"
COLOR_BOLD = "\033[1m"


def print_colored(text: str, color: str):
    """Print text with ANSI color codes if output is a TTY."""
    if sys.stdout.isatty():
        print(f"{color}{text}{COLOR_END}")
    else:
        print(text)


class RegexPerformanceTester:
    def __init__(self, patterns: List[str], test_string: str):
        self.patterns = patterns
        self.test_string = test_string

    def benchmark_compilation(self, iterations: int = 100000) -> List[Tuple[str, float]]:
        """Benchmark how fast the patterns compile."""
        results = []
        for p in self.patterns:
            # Measure compile time
            timer = timeit.Timer(lambda: re.compile(p))
            elapsed = timer.timeit(number=iterations)
            results.append((p, elapsed))
        return results

    def benchmark_matching(self, iterations: int = 10000) -> List[Tuple[str, float, bool]]:
        """Benchmark search operations for each pattern against the test string."""
        results = []
        for p in self.patterns:
            try:
                rx = re.compile(p)
                timer = timeit.Timer(lambda: rx.search(self.test_string))
                elapsed = timer.timeit(number=iterations)
                is_match = bool(rx.search(self.test_string))
                results.append((p, elapsed, is_match))
            except re.error as e:
                print_colored(f"[!] Invalid regex pattern '{p}': {e}", COLOR_FAIL)
        return results

    def analyze_redos_vulnerabilities(self, pattern: str) -> List[str]:
        """Statically inspect regex pattern syntax for common ReDoS vulnerability indicators."""
        warnings = []
        
        # 1. Nested quantifiers: e.g. (a+)+, (a*)*, (a+)*, (a*)+
        if re.search(r"\([^)]*[+*?]\)[+*?]", pattern):
            warnings.append("⚠️  NESTED QUANTIFIER: Found repetition of group that already has internal repetition (e.g. '(a+)+'). Potential ReDoS risk.")
            
        # 2. Overlapping adjacent optional elements followed by a multiplier: e.g. (a|a)+
        if re.search(r"\(([^|)]+)\|(\1)\)[+*?]", pattern):
            warnings.append("⚠️  DUPLICATE ALTERNATION: Identical branches in alternation under quantifier (e.g. '(a|a)+').")
            
        # 3. Star or plus quantifiers with wildcard/character classes: e.g. (.*a)*, ([a-z]+[0-9]+)*
        if re.search(r"\([^)]*(\.\*|\[[^\]]+\][+*])\)[+*?]", pattern):
            warnings.append("⚠️  NESTED WILDCARD/CLASS MULTIPLIER: Wildcards or broad classes inside quantified groups (e.g. '(.*a)*').")

        # 4. Multipliers without anchors inside groupings:
        if re.search(r"(\w+)\s+\1", pattern):
            pass # placeholder for backreference checks
            
        return warnings

    def run_empirical_scaling_test(self, pattern: str, max_length: int = 25, timeout_sec: float = 2.0):
        """Run matching operations against inputs of increasing lengths to observe exponential growth."""
        print_colored(f"\n[*] Running Empirical Scaling Test for pattern: '{pattern}'", COLOR_CYAN)
        print_colored("    Observing matching performance as input length increases (evaluating ReDoS risk)...", COLOR_BLUE)
        print("-" * 75)
        print(f"{'Input Length':<15} | {'Test String':<35} | {'Execution Time (sec)':<20}")
        print("-" * 75)

        try:
            rx = re.compile(pattern)
        except re.error as e:
            print_colored(f"[!] Error: Invalid regex: {e}", COLOR_FAIL)
            return

        # Base case character sequence. If pattern expects "a", construct strings of "a"s ending with "b" (force failure).
        # We try to infer a good character to repeat from the pattern.
        repeat_char = "a"
        char_match = re.search(r"([a-zA-Z0-9])", pattern)
        if char_match:
            repeat_char = char_match.group(1)
            
        suffix_char = "b" if repeat_char != "b" else "c"

        for length in range(5, max_length + 1, 2):
            payload = (repeat_char * length) + suffix_char
            
            # Run matching and measure elapsed time
            start = time.perf_counter()
            # We run it in a loop for a short period to get accurate measurements, or check if it times out
            try:
                # Use a watchdog trick or just straight run for a single call if we expect exponential delay
                rx.search(payload)
                elapsed = time.perf_counter() - start
                
                payload_disp = payload if len(payload) <= 30 else f"{payload[:12]}...{payload[-12:]}"
                print(f"{length:<15d} | {payload_disp:<35} | {elapsed:<20.8f}")
                
                if elapsed > timeout_sec:
                    print_colored(f"\n[!] ALERT: Matching took {elapsed:.4f} seconds with payload of length {length}!", COLOR_FAIL)
                    print_colored("    Vulnerability Confirmed: Execution time shows signs of exponential growth (Catastrophic Backtracking).", COLOR_FAIL + COLOR_BOLD)
                    break
            except Exception as e:
                print(f"Error during search: {e}")
                break
        print("-" * 75)


def main():
    parser = argparse.ArgumentParser(
        description="Regex Performance Tester & ReDoS Vulnerability Optimizer.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--pattern", "-p", action="append", help="Regex pattern(s) to benchmark (can specify multiple)")
    parser.add_argument("--string", "-t", default="Lorem ipsum dolor sit amet, consectetur adipiscing elit 123456.", help="Test string for match operations")
    parser.add_argument("--redos-test", action="store_true", help="Run empirical scaling test for ReDoS validation")
    parser.add_argument("--iterations", "-i", type=int, default=10000, help="Number of matching iterations for benchmarking (default: 10000)")

    args = parser.parse_args()

    if not args.pattern:
        # Default showcase patterns
        args.pattern = [
            r"(\w+)\s+(\w+)",
            r"(\w+)+$",  # Dangerous pattern
            r"\d{3}-\d{3}-\d{4}"
        ]

    tester = RegexPerformanceTester(args.pattern, args.string)

    # 1. Static Analysis
    print_colored(f"{COLOR_BOLD}--- Static Vulnerability Analysis ---{COLOR_END}", COLOR_CYAN)
    for p in args.pattern:
        print(f"Pattern: '{p}'")
        warnings = tester.analyze_redos_vulnerabilities(p)
        if warnings:
            for w in warnings:
                print_colored(f"  {w}", COLOR_WARNING)
        else:
            print_colored("  ✅ No typical ReDoS patterns detected in static checks.", COLOR_GREEN)
        print()

    # 2. Compile Benchmarking
    print_colored(f"{COLOR_BOLD}--- Compilation Benchmark ({args.iterations} iterations) ---{COLOR_END}", COLOR_CYAN)
    comp_results = tester.benchmark_compilation(args.iterations)
    for p, elapsed in comp_results:
        print(f"  Pattern: '{p:<30}' | Compilation Time: {elapsed:.6f} seconds")
    print()

    # 3. Matching Benchmarking
    print_colored(f"{COLOR_BOLD}--- Matching Benchmark ({args.iterations} iterations) ---{COLOR_END}", COLOR_CYAN)
    print(f"Test String: \"{args.string}\"")
    match_results = tester.benchmark_matching(args.iterations)
    for p, elapsed, is_match in match_results:
        match_status = "Match" if is_match else "No Match"
        print(f"  Pattern: '{p:<30}' | Matching Time: {elapsed:.6f} seconds | Status: {match_status}")
    print()

    # 4. ReDoS empirical scaling test
    if args.redos_test:
        for p in args.pattern:
            tester.run_empirical_scaling_test(p)


if __name__ == "__main__":
    main()
