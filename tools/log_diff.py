#!/usr/bin/env python3
"""
log_diff - Log Structural & Chronological Diff Tool

Compares two log files structurally and highlights additions, deletions,
and matches that have differing variable parameters (e.g., timestamps, IPs, IDs).
Optionally normalizes variable content (UUIDs, timestamps, numbers) using regex
to check if log patterns match even if their variables differ.

Usage:
    python tools/log_diff.py log1.log log2.log
    python tools/log_diff.py log1.log log2.log --mask-timestamps --mask-uuids
"""

import argparse
import difflib
import re
import sys

# Common regex patterns for masking variables in log messages
PATTERNS = {
    "timestamp": r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b|\b\d{2}:\d{2}:\d{2}(?:\.\d+)?\b",
    "uuid": r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b",
    "ipv4": r"\b(?:[0-9]{1,3}\.){3}[0-9]{1,3}\b",
    "hex": r"\b0x[0-9a-fA-F]+\b",
    "number": r"\b\d+\b"
}

# ANSI color codes
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"


def print_colored(text, color):
    """Utility to output colored logs when terminal supports it."""
    if sys.stdout.isatty():
        print(f"{color}{text}{COLOR_RESET}")
    else:
        print(text)


def mask_line(line, masks):
    """Replaces parts of the line matching specified masks with placeholder tokens."""
    masked = line
    for name, pattern in PATTERNS.items():
        if name in masks:
            masked = re.sub(pattern, f"<{name.upper()}>", masked)
    return masked


def main():
    parser = argparse.ArgumentParser(
        description="Compare two log files structurally and identify additions, deletions, or parameter changes."
    )
    parser.add_argument("file1", help="Path to the first (baseline) log file.")
    parser.add_argument("file2", help="Path to the second log file.")
    parser.add_argument(
        "--mask", 
        nargs="+", 
        choices=["timestamp", "uuid", "ipv4", "hex", "number"],
        default=["timestamp", "uuid", "ipv4"],
        help="Select variables to mask for matching (default: timestamp uuid ipv4)."
    )
    parser.add_argument(
        "--ratio", 
        type=float, 
        default=0.7, 
        help="Fuzzy match similarity threshold (0.0 to 1.0) for detecting parameter changes."
    )
    parser.add_argument(
        "--side-by-side",
        action="store_true",
        help="Display diff results side-by-side (truncated to fit terminal)."
    )

    args = parser.parse_args()

    try:
        with open(args.file1, "r", encoding="utf-8", errors="ignore") as f:
            lines1 = [line.rstrip("\n") for line in f]
        with open(args.file2, "r", encoding="utf-8", errors="ignore") as f:
            lines2 = [line.rstrip("\n") for line in f]
    except OSError as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)

    # Pre-process & mask lines
    masked1 = [mask_line(line, args.mask) for line in lines1]
    masked2 = [mask_line(line, args.mask) for line in lines2]

    # Perform sequence matching on masked representations
    matcher = difflib.SequenceMatcher(None, masked1, masked2)
    opcodes = matcher.get_opcodes()

    # Generate results
    results = []

    for tag, i1, i2, j1, j2 in opcodes:
        if tag == "equal":
            # Direct matches (masked structure is identical)
            for offset in range(i2 - i1):
                orig1 = lines1[i1 + offset]
                orig2 = lines2[j1 + offset]
                if orig1 == orig2:
                    results.append((" ", orig1, orig2))
                else:
                    # Parameter change (masked structures are equal, but original lines are not)
                    results.append(("~", orig1, orig2))
        elif tag == "delete":
            # Deletions from file1
            for offset in range(i2 - i1):
                results.append(("-", lines1[i1 + offset], ""))
        elif tag == "insert":
            # Additions in file2
            for offset in range(j2 - j1):
                results.append(("+", "", lines2[j1 + offset]))
        elif tag == "replace":
            # Structural replacement (could be parameter change if fuzzy threshold is met, or separate - and +)
            # Try fuzzy matching between the replaced blocks
            used_j = set()
            for idx1 in range(i1, i2):
                best_ratio = 0
                best_idx2 = -1
                for idx2 in range(j1, j2):
                    if idx2 in used_j:
                        continue
                    r = difflib.SequenceMatcher(None, masked1[idx1], masked2[idx2]).ratio()
                    if r > best_ratio:
                        best_ratio = r
                        best_idx2 = idx2
                
                if best_ratio >= args.ratio and best_idx2 != -1:
                    results.append(("~", lines1[idx1], lines2[best_idx2]))
                    used_j.add(best_idx2)
                else:
                    results.append(("-", lines1[idx1], ""))
            
            for idx2 in range(j1, j2):
                if idx2 not in used_j:
                    results.append(("+", "", lines2[idx2]))

    # Print output
    if args.side_by_side:
        # Determine terminal width (default 80 if cannot detect)
        try:
            terminal_width = os.get_terminal_size().columns
        except OSError:
            terminal_width = 80
            
        col_width = (terminal_width - 6) // 2
        header = f"{'BASELINE (FILE 1)':<{col_width}} | {'TARGET (FILE 2)':<{col_width}}"
        print(header)
        print("-" * len(header))
        
        for op, l1, l2 in results:
            l1_trunc = (l1[:col_width - 3] + "...") if len(l1) > col_width else l1
            l2_trunc = (l2[:col_width - 3] + "...") if len(l2) > col_width else l2
            
            if op == " ":
                print(f"{l1_trunc:<{col_width}} | {l2_trunc:<{col_width}}")
            elif op == "-":
                print_colored(f"{l1_trunc:<{col_width}} | {'[DELETED]':<{col_width}}", COLOR_RED)
            elif op == "+":
                print_colored(f"{'[ADDED]':<{col_width}} | {l2_trunc:<{col_width}}", COLOR_GREEN)
            elif op == "~":
                print_colored(f"{l1_trunc:<{col_width}} | {l2_trunc:<{col_width}}", COLOR_YELLOW)
    else:
        # Standard line-by-line diff format
        for op, l1, l2 in results:
            if op == " ":
                print(f"  {l1}")
            elif op == "-":
                print_colored(f"- {l1}", COLOR_RED)
            elif op == "+":
                print_colored(f"+ {l2}", COLOR_GREEN)
            elif op == "~":
                print_colored(f"~ {l1}", COLOR_CYAN)
                print_colored(f"  {l2}", COLOR_YELLOW)


if __name__ == "__main__":
    main()
