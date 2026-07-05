#!/usr/bin/env python3
"""
Log Sampling Filter & Rate Limiter Tool

Filters large log streams or log files using deterministic sampling, reservoir sampling,
stride sampling, or rate-limiting per log level. Useful for reducing log volume for analytical
processing while keeping critical error events intact.
"""

import os
import sys
import re
import random
import hashlib
import argparse
from typing import List, Dict, Any, Optional

# Standard ANSI Color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RED = "\033[91m"
RESET = "\033[0m"
BOLD = "\033[1m"

LOG_LEVEL_PATTERNS = {
    'CRITICAL': re.compile(r'\b(CRITICAL|FATAL|EMERGENCY)\b', re.IGNORECASE),
    'ERROR': re.compile(r'\b(ERROR|ERR|FAIL|FAILED|EXCEPTION)\b', re.IGNORECASE),
    'WARN': re.compile(r'\b(WARN|WARNING)\b', re.IGNORECASE),
    'INFO': re.compile(r'\b(INFO|NOTICE)\b', re.IGNORECASE),
    'DEBUG': re.compile(r'\b(DEBUG|TRACE)\b', re.IGNORECASE),
}


def detect_log_level(line: str) -> str:
    """Detect the log level of a log line."""
    for level, pattern in LOG_LEVEL_PATTERNS.items():
        if pattern.search(line):
            return level
    return 'UNKNOWN'


def hash_sample(line: str, sample_rate: float) -> bool:
    """Deterministically decide if a line should be included based on its MD5 hash."""
    if sample_rate >= 1.0:
        return True
    if sample_rate <= 0.0:
        return False
    digest = hashlib.md5(line.strip().encode('utf-8')).hexdigest()
    num = int(digest[:8], 16)
    max_num = 0xFFFFFFFF
    return (num / max_num) < sample_rate


class LogSampler:
    def __init__(self, mode: str, default_rate: float, level_rates: Dict[str, float], stride: int):
        self.mode = mode
        self.default_rate = default_rate
        self.level_rates = level_rates
        self.stride = stride
        self.count = 0
        self.passed_count = 0
        self.stats_by_level: Dict[str, Dict[str, int]] = {}

    def should_sample(self, line: str) -> bool:
        self.count += 1
        level = detect_log_level(line)
        
        if level not in self.stats_by_level:
            self.stats_by_level[level] = {'total': 0, 'passed': 0}
        self.stats_by_level[level]['total'] += 1

        rate = self.level_rates.get(level, self.default_rate)

        should_keep = False
        if rate >= 1.0:
            should_keep = True
        elif rate <= 0.0:
            should_keep = False
        elif self.mode == 'hash':
            should_keep = hash_sample(line, rate)
        elif self.mode == 'stride':
            should_keep = (self.count % self.stride == 0) or (rate >= 1.0)
        else: # random
            should_keep = random.random() < rate

        if should_keep:
            self.passed_count += 1
            self.stats_by_level[level]['passed'] += 1

        return should_keep


def process_logs(input_file: Optional[str], output_file: Optional[str], sampler: LogSampler) -> None:
    """Read lines from input file or stdin and write sampled lines to output file or stdout."""
    if input_file and input_file != '-':
        if not os.path.exists(input_file):
            print(f"{RED}Error: Input file '{input_file}' not found.{RESET}", file=sys.stderr)
            sys.exit(1)
        in_stream = open(input_file, 'r', encoding='utf-8', errors='replace')
    else:
        in_stream = sys.stdin

    out_stream = open(output_file, 'w', encoding='utf-8') if output_file else sys.stdout

    try:
        for line in in_stream:
            if sampler.should_sample(line):
                out_stream.write(line)
    finally:
        if in_stream is not sys.stdin:
            in_stream.close()
        if out_stream is not sys.stdout:
            out_stream.close()


def print_stats(sampler: LogSampler) -> None:
    """Print sampling statistical summary to stderr."""
    reduction = 0.0
    if sampler.count > 0:
        reduction = (1.0 - (sampler.passed_count / sampler.count)) * 100.0

    print(f"\n{BOLD}{CYAN}=== Log Sampling Summary ==={RESET}", file=sys.stderr)
    print(f"Total Lines Processed : {sampler.count}", file=sys.stderr)
    print(f"Lines Retained         : {sampler.passed_count}", file=sys.stderr)
    print(f"Volume Reduction       : {GREEN}{reduction:.2f}%{RESET}", file=sys.stderr)
    print(f"\n{BOLD}Distribution by Log Level:{RESET}", file=sys.stderr)
    
    for level, data in sorted(sampler.stats_by_level.items()):
        tot = data['total']
        pas = data['passed']
        pct = (pas / tot * 100.0) if tot > 0 else 0.0
        print(f"  {level:<10}: {pas:>7} / {tot:>7} kept ({pct:6.2f}%)", file=sys.stderr)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Filter and sample log files or streams based on log levels and sampling strategies."
    )
    parser.add_argument("input", nargs="?", help="Input log file path (reads from stdin if omitted or '-')")
    parser.add_argument("-o", "--output", help="Output file path (writes to stdout if omitted)")
    parser.add_argument("-m", "--mode", choices=["random", "hash", "stride"], default="hash",
                        help="Sampling method: 'hash' (deterministic), 'random', or 'stride'")
    parser.add_argument("-r", "--rate", type=float, default=0.1, help="Default sampling rate (0.0 to 1.0)")
    parser.add_argument("-s", "--stride", type=int, default=10, help="Stride interval when mode is 'stride'")
    parser.add_argument("--error-rate", type=float, default=1.0, help="Sampling rate for ERROR logs (default: 1.0)")
    parser.add_argument("--warn-rate", type=float, default=0.5, help="Sampling rate for WARN logs (default: 0.5)")
    parser.add_argument("--info-rate", type=float, default=0.1, help="Sampling rate for INFO logs (default: 0.1)")
    parser.add_argument("--debug-rate", type=float, default=0.01, help="Sampling rate for DEBUG logs (default: 0.01)")
    parser.add_argument("--quiet", action="store_true", help="Suppress summary report output on stderr")
    return parser.parse_args()


def main():
    args = parse_args()

    level_rates = {
        'CRITICAL': 1.0,
        'ERROR': args.error_rate,
        'WARN': args.warn_rate,
        'INFO': args.info_rate,
        'DEBUG': args.debug_rate
    }

    sampler = LogSampler(
        mode=args.mode,
        default_rate=args.rate,
        level_rates=level_rates,
        stride=args.stride
    )

    process_logs(args.input, args.output, sampler)

    if not args.quiet:
        print_stats(sampler)


if __name__ == '__main__':
    main()
