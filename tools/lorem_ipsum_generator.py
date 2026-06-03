#!/usr/bin/env python3
"""
Lorem Ipsum Generator

Generates dummy text (Lorem Ipsum).

Usage:
    python tools/lorem_ipsum_generator.py [--words 20]
"""

import argparse
import sys
import random

LOREM_WORDS = [
    "lorem", "ipsum", "dolor", "sit", "amet", "consectetur", "adipiscing", "elit",
    "sed", "do", "eiusmod", "tempor", "incididunt", "ut", "labore", "et", "dolore", "magna", "aliqua"
]

def main():
    parser = argparse.ArgumentParser(description="Generate Lorem Ipsum dummy text")
    parser.add_argument('-w', '--words', type=int, default=10, help='Number of words to generate (default: 10)')
    args = parser.parse_args()

    generated = random.choices(LOREM_WORDS, k=args.words)
    generated[0] = generated[0].capitalize()
    text = " ".join(generated) + "."
    print(text)
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
