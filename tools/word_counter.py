#!/usr/bin/env python3
"""
Word Counter - A tool to analyze text files or text inputs.
Counts words, characters, lines, sentences, and calculates average word length.
"""

import argparse
import os
import sys
import re

def analyze_text(text):
    """
    Analyzes the given text and returns a dictionary of metrics.
    """
    # Character count (including whitespace)
    char_count = len(text)
    
    # Line count
    line_count = len(text.splitlines()) if text else 0
    
    # Word list (finding all alphanumeric words/sequences)
    # We can use regex to find words, ignoring punctuation
    words = re.findall(r'\b\w+\b', text)
    word_count = len(words)
    
    # Sentence count
    # Sentence boundaries: . ! ? followed by space or end of text
    sentences = re.findall(r'[^.!?]+(?:[.!?]+|$)', text)
    # Filter sentences that actually contain alphanumeric characters
    sentence_count = sum(1 for s in sentences if re.search(r'\w', s))
    
    # Average word length
    if word_count > 0:
        avg_word_len = sum(len(w) for w in words) / word_count
    else:
        avg_word_len = 0.0
        
    return {
        "characters": char_count,
        "words": word_count,
        "lines": line_count,
        "sentences": sentence_count,
        "average_word_length": avg_word_len
    }

def main():
    parser = argparse.ArgumentParser(
        description="Word Counter - Analyze files or text to count words, characters, lines, sentences, and average word length."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("file", nargs="?", help="Path to the file to analyze")
    group.add_argument("-t", "--text", help="Direct text input to analyze")
    
    parser.add_argument("-c", "--chars", action="store_true", help="Print character count only")
    parser.add_argument("-w", "--words", action="store_true", help="Print word count only")
    parser.add_argument("-l", "--lines", action="store_true", help="Print line count only")
    parser.add_argument("-s", "--sentences", action="store_true", help="Print sentence count only")
    parser.add_argument("-a", "--average", action="store_true", help="Print average word length only")

    args = parser.parse_args()

    text = None
    source = ""

    if args.text is not None:
        text = args.text
        source = "Direct Text Input"
    elif args.file is not None:
        if not os.path.isfile(args.file):
            print(f"[ERROR] File not found: {args.file}", file=sys.stderr)
            sys.exit(1)
        try:
            with open(args.file, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
            source = f"File: {args.file}"
        except Exception as e:
            print(f"[ERROR] Could not read file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Check if data is piped into stdin
        if not sys.stdin.isatty():
            try:
                text = sys.stdin.read()
                source = "Standard Input (stdin)"
            except Exception as e:
                print(f"[ERROR] Could not read from stdin: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            parser.print_help()
            sys.exit(0)

    # Analyze the retrieved text
    metrics = analyze_text(text)

    # Determine if a specific metric is requested (instead of all)
    specific_requested = any([args.chars, args.words, args.lines, args.sentences, args.average])

    if specific_requested:
        # Print only the requested metrics
        results = []
        if args.lines:
            results.append(str(metrics["lines"]))
        if args.words:
            results.append(str(metrics["words"]))
        if args.chars:
            results.append(str(metrics["characters"]))
        if args.sentences:
            results.append(str(metrics["sentences"]))
        if args.average:
            results.append(f"{metrics['average_word_length']:.2f}")
        print(" ".join(results))
    else:
        # Print all metrics formatted
        print(f"--- Analysis Report: {source} ---")
        print(f"Lines:               {metrics['lines']}")
        print(f"Words:               {metrics['words']}")
        print(f"Characters:          {metrics['characters']}")
        print(f"Sentences:           {metrics['sentences']}")
        print(f"Avg Word Length:     {metrics['average_word_length']:.2f} chars")
        print("-" * (len(source) + 26))

if __name__ == "__main__":
    main()
