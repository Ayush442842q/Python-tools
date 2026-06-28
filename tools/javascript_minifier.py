#!/usr/bin/env python3
"""
JavaScript Minifier

A pure Python JavaScript minifier that strips single-line (//) and multi-line (/* */) comments,
handles string literals (single, double, and backticks) and regular expressions safely,
and compresses whitespaces/newlines.

Usage:
    python tools/javascript_minifier.py -i script.js -o script.min.js
    python tools/javascript_minifier.py -i script.js --no-mangle-whitespace
    cat script.js | python tools/javascript_minifier.py
"""

import argparse
import os
import sys

class JSMinifier:
    def __init__(self, text):
        self.text = text
        self.length = len(text)
        self.index = 0
        self.output = []
        
    def peek(self, offset=1):
        pos = self.index + offset
        if pos < self.length:
            return self.text[pos]
        return None

    def minify(self, mangle_whitespace=True):
        # States: 'normal', 'string_single', 'string_double', 'template_literal', 'regex', 'line_comment', 'block_comment'
        state = 'normal'
        escaped = False
        
        while self.index < self.length:
            char = self.text[self.index]
            
            if state == 'normal':
                # Check for comment starts
                if char == '/' and self.peek() == '/':
                    state = 'line_comment'
                    self.index += 2
                    continue
                elif char == '/' and self.peek() == '*':
                    state = 'block_comment'
                    self.index += 2
                    continue
                # Check for string starts
                elif char == "'":
                    state = 'string_single'
                    self.output.append(char)
                elif char == '"':
                    state = 'string_double'
                    self.output.append(char)
                elif char == '`':
                    state = 'template_literal'
                    self.output.append(char)
                # Check for regex literal start
                # A slash is a regex if preceded by certain characters (like '=', '(', ',', ';', '[', ':', '?', '!', '&', '|')
                # or if it's the start of a statement. Since parsing complete JS is hard, we look at the last non-space character.
                elif char == '/':
                    is_regex = False
                    # Look back to check if it's likely a regex or division
                    last_chars = "".join(self.output[-15:]).strip()
                    if not last_chars:
                        is_regex = True
                    else:
                        last_non_space = last_chars[-1]
                        if last_non_space in ('=', '(', ',', ';', '[', ':', '?', '!', '&', '|', '{', '}', '\n', '\r'):
                            is_regex = True
                    
                    if is_regex:
                        state = 'regex'
                        self.output.append(char)
                    else:
                        self.output.append(char)
                else:
                    self.output.append(char)
                    
            elif state == 'line_comment':
                if char in ('\n', '\r'):
                    state = 'normal'
                    self.output.append(char) # Keep the newline for safety
                    
            elif state == 'block_comment':
                if char == '*' and self.peek() == '/':
                    state = 'normal'
                    self.index += 2
                    continue
                    
            elif state in ('string_single', 'string_double', 'template_literal', 'regex'):
                self.output.append(char)
                if escaped:
                    escaped = False
                elif char == '\\':
                    escaped = True
                else:
                    # Check for string/regex termination
                    if state == 'string_single' and char == "'":
                        state = 'normal'
                    elif state == 'string_double' and char == '"':
                        state = 'normal'
                    elif state == 'template_literal' and char == '`':
                        state = 'normal'
                    elif state == 'regex' and char == '/':
                        state = 'normal'
            
            self.index += 1

        stripped = "".join(self.output)
        
        if not mangle_whitespace:
            return stripped

        return self.compress_whitespace(stripped)

    def compress_whitespace(self, js_text):
        """
        Compresses whitespaces, removing unnecessary spaces/newlines around operators.
        """
        # Operators and boundary characters where spaces are safe to remove
        operators = set("+-*/%=&|^<>!?:,;{}()[]")
        
        # We need to run another token-like pass to avoid stripping spaces in string literals
        length = len(js_text)
        index = 0
        output = []
        state = 'normal'
        escaped = False
        
        while index < length:
            char = js_text[index]
            
            if state == 'normal':
                if char in ("'", '"', '`'):
                    state = char
                    output.append(char)
                elif char == '/' and (index + 1 < length) and js_text[index - 1] in ('=', '(', ',', ';', '[', ':', '?', '!', '&', '|', '{', '}'):
                    # Likely a regex
                    state = 'regex'
                    output.append(char)
                elif char.isspace():
                    # Replace multiple whitespaces/newlines with a single space
                    if output and not output[-1].isspace():
                        # Only add a space if the previous and next characters require a separator
                        # E.g. word boundary to word boundary
                        next_char = None
                        for offset in range(index + 1, length):
                            if not js_text[offset].isspace():
                                next_char = js_text[offset]
                                break
                        
                        prev_char = output[-1]
                        
                        # We need space between identifier/keywords.
                        # No space needed if either character is an operator.
                        if prev_char not in operators and next_char not in operators:
                            output.append(' ')
                else:
                    output.append(char)
                    
            elif state in ("'", '"', '`', 'regex'):
                output.append(char)
                if escaped:
                    escaped = False
                elif char == '\\':
                    escaped = True
                else:
                    if state == 'regex' and char == '/':
                        state = 'normal'
                    elif char == state:
                        state = 'normal'
                        
            index += 1
            
        # Join and strip leading/trailing spaces
        result = "".join(output).strip()
        
        # Clean up double newlines or dangling semicolons
        return result

def main():
    parser = argparse.ArgumentParser(
        description="JavaScript Minifier - Strip comments and compress whitespace in JS files."
    )
    parser.add_argument(
        '-i', '--input',
        help='Path to the input JavaScript file. If omitted, reads from stdin.'
    )
    parser.add_argument(
        '-o', '--output',
        help='Path to save the minified JS output. If omitted, prints to console.'
    )
    parser.add_argument(
        '--no-mangle-whitespace',
        action='store_true',
        help='Only strip comments; do not compress whitespace/newlines'
    )
    parser.add_argument(
        '--encoding',
        default='utf-8',
        help='Character encoding for files (default: utf-8)'
    )

    args = parser.parse_args()

    # Read JS Input
    if args.input:
        if not os.path.exists(args.input):
            print(f"[ERROR] Input file '{args.input}' does not exist.", file=sys.stderr)
            return 1
        try:
            with open(args.input, 'r', encoding=args.encoding) as f:
                js_content = f.read()
        except Exception as e:
            print(f"[ERROR] Failed to read input file '{args.input}': {e}", file=sys.stderr)
            return 1
    else:
        if sys.stdin.isatty():
            print("[INFO] Waiting for input on stdin... (Ctrl+Z and Enter on Windows to end)", file=sys.stderr)
        try:
            js_content = sys.stdin.read()
        except Exception as e:
            print(f"[ERROR] Failed to read from stdin: {e}", file=sys.stderr)
            return 1

    if not js_content.strip():
        print("[ERROR] Input JavaScript content is empty.", file=sys.stderr)
        return 1

    minifier = JSMinifier(js_content)
    minified_js = minifier.minify(mangle_whitespace=not args.no_mangle-whitespace if 'no_mangle-whitespace' in args else not args.no_mangle_whitespace)

    # Output JS
    if args.output:
        try:
            with open(args.output, 'w', encoding=args.encoding) as f:
                f.write(minified_js + "\n")
            
            # Print stats
            orig_size = len(js_content)
            min_size = len(minified_js)
            savings = orig_size - min_size
            pct = (savings / orig_size * 100) if orig_size > 0 else 0
            print(f"[OK] Minified JS successfully written to '{args.output}'.")
            print(f"Original Size: {orig_size} bytes")
            print(f"Minified Size: {min_size} bytes")
            print(f"Reduction:     {savings} bytes ({pct:.2f}%)")
        except Exception as e:
            print(f"[ERROR] Failed to write output file '{args.output}': {e}", file=sys.stderr)
            return 1
    else:
        print(minified_js)

    return 0

if __name__ == '__main__':
    sys.exit(main())
