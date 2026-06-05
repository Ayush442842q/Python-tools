#!/usr/bin/env python3
"""
Text Case Converter

Converts text between various programming and text casings, such as camelCase, snake_case, PascalCase, kebab-case, UPPERCASE, lowercase, and Title Case.

Usage:
    python tools/text_case_converter.py "hello world"
    python tools/text_case_converter.py "hello_world" --case camel
"""

import argparse
import re
import sys

def split_words(text):
    # Split text by spaces, underscores, hyphens, or camelCase boundaries
    # E.g., "camelCase" -> split to "camel" and "Case"
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1 \2', text)
    s2 = re.sub('([a-z0-9])([A-Z])', r'\1 \2', s1)
    # Replace symbols with spaces, then split
    clean = re.sub(r'[-_\s]+', ' ', s2)
    return [w.lower() for w in clean.split() if w]

def to_camel(words):
    if not words:
        return ""
    return words[0] + "".join(w.capitalize() for w in words[1:])

def to_pascal(words):
    return "".join(w.capitalize() for w in words)

def to_snake(words):
    return "_".join(words)

def to_kebab(words):
    return "-".join(words)

def to_title(words):
    return " ".join(w.capitalize() for w in words)

def to_sentence(words):
    if not words:
        return ""
    return words[0].capitalize() + " " + " ".join(words[1:])

def main():
    parser = argparse.ArgumentParser(description="Text Case Converter - Convert text between common programming casings")
    parser.add_argument('text', help='The text string to convert')
    parser.add_argument('-c', '--case', choices=['camel', 'pascal', 'snake', 'kebab', 'upper', 'lower', 'title', 'sentence', 'all'],
                        default='all', help='The target case format (default: all)')
    
    args = parser.parse_args()
    
    words = split_words(args.text)
    if not words:
        print("Error: No words found in input text.")
        return 1

    conversions = {
        'camel': to_camel(words),
        'pascal': to_pascal(words),
        'snake': to_snake(words),
        'kebab': to_kebab(words),
        'upper': " ".join(words).upper(),
        'lower': " ".join(words).lower(),
        'title': to_title(words),
        'sentence': to_sentence(words)
    }

    if args.case == 'all':
        print(f"Original: {args.text}\n")
        print(f"camelCase:   {conversions['camel']}")
        print(f"PascalCase:  {conversions['pascal']}")
        print(f"snake_case:  {conversions['snake']}")
        print(f"kebab-case:  {conversions['kebab']}")
        print(f"UPPERCASE:   {conversions['upper']}")
        print(f"lowercase:   {conversions['lower']}")
        print(f"Title Case:  {conversions['title']}")
        print(f"Sentence:    {conversions['sentence']}")
    else:
        print(conversions[args.case])

    return 0

if __name__ == "__main__":
    sys.exit(main())
