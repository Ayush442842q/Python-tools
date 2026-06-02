#!/usr/bin/env python3
"""
Random Name Generator

Generates a random full name.

Usage:
    python tools/random_name_generator.py [--count 5]
"""

import argparse
import sys
import random

FIRST_NAMES = ["Alice", "Bob", "Charlie", "Diana", "Ethan", "Fiona", "George", "Hannah", "Ivan", "Julia"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez"]

def main():
    parser = argparse.ArgumentParser(description="Generate random names")
    parser.add_argument('-c', '--count', type=int, default=1, help='Number of names to generate (default: 1)')
    args = parser.parse_args()

    for i in range(args.count):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        print(f"{first} {last}")
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
