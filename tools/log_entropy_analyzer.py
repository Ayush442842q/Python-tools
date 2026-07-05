#!/usr/bin/env python3
"""
Log File Shannon Entropy & Anomaly Analyzer
Measures information entropy across sliding windows of log entries to detect anomalies,
obfuscated payloads, base64 strings, stack traces, and security events.
"""

import argparse
import math
import os
import sys

# Ensure UTF-8 output encoding on Windows terminals
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

# ANSI Colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def calculate_shannon_entropy(text):
    if not text:
        return 0.0
    freq = {}
    for char in text:
        freq[char] = freq.get(char, 0) + 1
    
    entropy = 0.0
    text_len = len(text)
    for count in freq.values():
        p = count / text_len
        entropy -= p * math.log2(p)
    return entropy


def sparkline(values, steps=" ▂▃▄▅▆▇█"):
    if not values:
        return ""
    min_v = min(values)
    max_v = max(values)
    v_range = max_v - min_v if max_v != min_v else 1.0

    res = []
    for v in values:
        idx = int((v - min_v) / v_range * (len(steps) - 1))
        idx = max(0, min(len(steps) - 1, idx))
        res.append(steps[idx])
    return "".join(res)


def analyze_log_file(filepath, window_size=50, threshold=4.5):
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()

    line_entropies = []
    anomalies = []

    for idx, line in enumerate(lines, 1):
        stripped = line.rstrip()
        ent = calculate_shannon_entropy(stripped)
        line_entropies.append(ent)

        if ent >= threshold and len(stripped) > 10:
            anomalies.append({
                "line_no": idx,
                "entropy": ent,
                "content": stripped
            })

    # Windowed averages
    window_entropies = []
    for i in range(0, len(line_entropies), window_size):
        chunk = line_entropies[i:i + window_size]
        avg_ent = sum(chunk) / len(chunk)
        window_entropies.append(avg_ent)

    overall_avg = sum(line_entropies) / len(line_entropies) if line_entropies else 0.0

    return {
        "total_lines": len(lines),
        "overall_avg_entropy": overall_avg,
        "max_entropy": max(line_entropies) if line_entropies else 0.0,
        "window_entropies": window_entropies,
        "anomalies": anomalies
    }


def run_demo():
    sample_logs = [
        "2026-07-06 00:00:01 INFO [AuthService] User login success user=alice",
        "2026-07-06 00:00:02 INFO [AuthService] User login success user=bob",
        "2026-07-06 00:00:03 WARN [DBPool] Connection pool low: 2 connections remaining",
        "2026-07-06 00:00:04 ERROR [HTTP] Payload error: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c",
        "2026-07-06 00:00:05 INFO [AuthService] User logout user=alice",
        "2026-07-06 00:00:06 ERROR [Security] Malicious Obfuscated Shell: eval(base64_decode('aW1wb3J0IG9zO29zLnN5c3RlbSgnY2FsYycp'))",
        "2026-07-06 00:00:07 INFO [AuthService] User login success user=charlie"
    ]

    print(f"{BOLD}{CYAN}=== Log Entropy & Anomaly Analyzer Demo ==={RESET}\n")
    print(f"{BOLD}Analyzing Sample Log Entries:{RESET}\n")

    entropies = []
    anomalies = []

    for idx, line in enumerate(sample_logs, 1):
        ent = calculate_shannon_entropy(line)
        entropies.append(ent)
        is_high = ent >= 4.6
        status_color = RED if is_high else GREEN
        print(f"Line {idx} | Entropy: {status_color}{ent:.2f}{RESET} | {line[:65]}...")

        if is_high:
            anomalies.append((idx, ent, line))

    print(f"\n{BOLD}{YELLOW}Entropy Sparkline Trend:{RESET}")
    print(f"  [{sparkline(entropies)}]")

    print(f"\n{BOLD}{RED}High Entropy Anomalies Detected ({len(anomalies)}):{RESET}")
    for idx, ent, line in anomalies:
        print(f"  • Line {idx} (Entropy: {ent:.2f}): {line}")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze Shannon entropy distribution in log files to pinpoint obfuscated payloads and anomalies."
    )
    parser.add_argument("logfile", nargs="?", help="Log file path to analyze")
    parser.add_argument("--threshold", type=float, default=4.6, help="Entropy alert threshold (default: 4.6)")
    parser.add_argument("--window", type=int, default=50, help="Lines per window for trend graph (default: 50)")
    parser.add_argument("--demo", action="store_true", help="Run self-contained demo")

    args = parser.parse_args()

    if args.demo or not args.logfile:
        if not args.logfile and not args.demo:
            print(f"{YELLOW}Log file required. Running demo mode...{RESET}\n")
        run_demo()
        return

    if not os.path.isfile(args.logfile):
        print(f"{RED}Error: File '{args.logfile}' not found.{RESET}", file=sys.stderr)
        sys.exit(1)

    try:
        results = analyze_log_file(args.logfile, window_size=args.window, threshold=args.threshold)

        print(f"\n{BOLD}{CYAN}=== Log Entropy Analysis Report: {args.logfile} ==={RESET}\n")
        print(f"  • Total Lines        : {results['total_lines']}")
        print(f"  • Average Entropy    : {results['overall_avg_entropy']:.2f} bits/char")
        print(f"  • Maximum Entropy    : {results['max_entropy']:.2f} bits/char")
        print(f"  • Entropy Threshold  : {args.threshold} bits/char")

        print(f"\n{BOLD}{YELLOW}Windowed Entropy Trend:{RESET}")
        print(f"  [{sparkline(results['window_entropies'])}]")

        anomalies = results["anomalies"]
        print(f"\n{BOLD}{RED}Detected High-Entropy Anomalies ({len(anomalies)}):{RESET}")
        for a in anomalies[:20]:
            print(f"  Line {a['line_no']:<5} | Entropy: {RED}{a['entropy']:.2f}{RESET} | {a['content'][:80]}")

        if len(anomalies) > 20:
            print(f"  ... and {len(anomalies) - 20} more high-entropy lines.")

    except Exception as e:
        print(f"{RED}Error analyzing log file: {e}{RESET}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
