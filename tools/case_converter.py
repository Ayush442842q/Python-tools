#!/usr/bin/env python3
"""
Text Case Converter - Converts strings or text files into various casing formats.
Supports snake_case, camelCase, PascalCase, kebab-case, Title Case, Sentence Case,
SpongeBob (alternating) case, and slugify (URL-safe strings).
"""

import argparse
import re
import sys

def tokenize(text):
    """Splits text into list of individual words by detecting spaces, underscores, hyphens, and case transitions."""
    # Convert camel/Pascal cases to separated words first
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1 \2', text)
    s2 = re.sub('([a-z0-9])([A-Z])', r'\1 \2', s1)
    # Extract only word-like sequences (alphanumeric)
    words = re.findall(r'[a-zA-Z0-9]+', s2)
    return [w.lower() for w in words]

def to_snake_case(words):
    return '_'.join(words)

def to_kebab_case(words):
    return '-'.join(words)

def to_camel_case(words):
    if not words:
        return ""
    return words[0] + ''.join(w.capitalize() for w in words[1:])

def to_pascal_case(words):
    return ''.join(w.capitalize() for w in words)

def to_title_case(text):
    return text.title()

def to_sentence_case(text):
    # Capitalize the first letter of each sentence
    sentences = re.split(r'(\s*[\.\?\!]\s*)', text)
    result = []
    capitalize_next = True
    for segment in sentences:
        if re.match(r'^\s*[\.\?\!]\s*$', segment):
            result.append(segment)
            capitalize_next = True
        else:
            if capitalize_next:
                # Find first alphanumeric character and capitalize it
                match = re.search(r'[a-zA-Z0-9]', segment)
                if match:
                    idx = match.start()
                    segment = segment[:idx] + segment[idx].upper() + segment[idx+1:].lower()
                capitalize_next = False
            else:
                segment = segment.lower()
            result.append(segment)
    return ''.join(result)

def to_alternating_case(text):
    """SpongeBob case: AlTeRnAtInG CaSe."""
    result = []
    upper = True
    for char in text:
        if char.isalpha():
            result.append(char.upper() if upper else char.lower())
            upper = not upper
        else:
            result.append(char)
    return ''.join(result)

def to_slugify(words):
    return '-'.join(words)

def main():
    parser = argparse.ArgumentParser(
        description="Text Case Converter - Convert text casing between common programmer formats."
    )
    parser.add_argument("text", nargs="?", help="Direct text to convert")
    parser.add_argument("-t", "--text-arg", dest="text_arg", help="Direct text input")
    parser.add_argument("-f", "--file", help="Input file path (use '-' for stdin)")
    parser.add_argument("-o", "--output", help="Output file path")
    
    parser.add_argument(
        "-c", "--case",
        choices=['snake', 'kebab', 'camel', 'pascal', 'upper', 'lower', 'title', 'sentence', 'alternating', 'slug'],
        required=True,
        help="Target casing style"
    )

    args = parser.parse_args()

    # Determine input text
    input_text = ""
    if args.file:
        if args.file == '-':
            input_text = sys.stdin.read()
        else:
            try:
                with open(args.file, 'r', encoding='utf-8') as f:
                    input_text = f.read()
            except Exception as e:
                print(f"Error reading file: {e}", file=sys.stderr)
                return 1
    else:
        input_text = args.text_arg or args.text
        if not input_text:
            print("Error: No input text provided. Provide positional text or use --file/--text-arg.", file=sys.stderr)
            return 1

    input_text = input_text.strip()
    words = tokenize(input_text)

    # Convert to targeted case
    if args.case == 'snake':
        result = to_snake_case(words)
    elif args.case == 'kebab':
        result = to_kebab_case(words)
    elif args.case == 'camel':
        result = to_camel_case(words)
    elif args.case == 'pascal':
        result = to_pascal_case(words)
    elif args.case == 'upper':
        result = input_text.upper()
    elif args.case == 'lower':
        result = input_text.lower()
    elif args.case == 'title':
        result = to_title_case(input_text)
    elif args.case == 'sentence':
        result = to_sentence_case(input_text)
    elif args.case == 'alternating':
        result = to_alternating_case(input_text)
    elif args.case == 'slug':
        result = to_slugify(words)
    else:
        result = input_text

    # Print or save output
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(result + '\n')
            print(f"[+] Output written to: {args.output}")
        except Exception as e:
            print(f"Error writing to output: {e}", file=sys.stderr)
            return 1
    else:
        print(result)

    return 0

if __name__ == "__main__":
    sys.exit(main())
