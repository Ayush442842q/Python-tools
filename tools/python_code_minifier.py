#!/usr/bin/env python3
"""
Python Code Minifier

A standalone Python source code minifier. It uses Python's native `tokenize`
module to strip comments, docstrings, and unnecessary whitespace while preserving
valid syntax and indentation block structures.

Usage:
    python python_code_minifier.py input.py -o output.min.py
"""

import os
import sys
import argparse
import io
import tokenize


def minify_python_code(source_code, remove_docstrings=True, remove_comments=True):
    """
    Minifies Python source code by removing comments and docstrings, 
    and consolidating whitespaces using the standard tokenize module.
    """
    try:
        token_stream = tokenize.generate_tokens(io.StringIO(source_code).readline)
    except Exception as e:
        raise ValueError(f"Failed to generate tokens: {e}")

    result = []
    prev_toktype = None
    last_col = 0
    last_lineno = 1

    # Keep track of where docstrings could be
    # Docstrings can only occur as the first statement in a module, class, or function body.
    # We can detect standalone string expressions.
    # If a string token is on its own line (or is the first expression in a block), it's a docstring.
    
    tokens = list(token_stream)
    is_docstring = [False] * len(tokens)

    if remove_docstrings:
        for idx, tok in enumerate(tokens):
            if tok.type == tokenize.STRING:
                # Find the context of this string token
                # If it's a standalone expression statement, it will be followed by a NEWLINE or NL,
                # and preceded by either INDENT, NEWLINE, NL, or ':' (colon for one-liner body)
                # Let's inspect the surrounding tokens:
                
                # Check preceding tokens (skip NL/comments)
                prev_idx = idx - 1
                while prev_idx >= 0 and tokens[prev_idx].type in (tokenize.NL, tokenize.COMMENT):
                    prev_idx -= 1
                
                # Check succeeding tokens (skip NL/comments)
                next_idx = idx + 1
                while next_idx < len(tokens) and tokens[next_idx].type in (tokenize.NL, tokenize.COMMENT):
                    next_idx += 1
                
                # Preceding boundary conditions for a statement
                prec_ok = False
                if prev_idx < 0:
                    prec_ok = True  # Start of module
                else:
                    pt = tokens[prev_idx].type
                    pt_val = tokens[prev_idx].string
                    if pt in (tokenize.INDENT, tokenize.NEWLINE) or pt_val == ':':
                        prec_ok = True
                
                # Succeeding boundary conditions
                succ_ok = False
                if next_idx >= len(tokens):
                    succ_ok = True  # End of module
                else:
                    nt = tokens[next_idx].type
                    if nt in (tokenize.NEWLINE, tokenize.ENDMARKER):
                        succ_ok = True
                
                if prec_ok and succ_ok:
                    is_docstring[idx] = True

    for idx, tok in enumerate(tokens):
        tok_type = tok.type
        tok_string = tok.string
        start_line, start_col = tok.start
        end_line, end_col = tok.end

        # Handle comments
        if remove_comments and tok_type == tokenize.COMMENT:
            continue

        # Handle docstrings
        if remove_docstrings and is_docstring[idx]:
            # Keep the trailing token newline if the docstring was removed to avoid syntax break
            continue

        # Check line increments
        if start_line > last_lineno:
            last_col = 0
            # If the last token written was not a newline, add a newline
            if result and not result[-1].endswith('\n') and not result[-1].endswith('\r'):
                result.append('\n')

        # Insert spaces between name tokens or operators to prevent code run-together (e.g., 'import os' -> 'importos')
        if tok_type in (tokenize.NAME, tokenize.NUMBER, tokenize.OP) and prev_toktype in (tokenize.NAME, tokenize.NUMBER, tokenize.OP):
            # Check if whitespace exists between tokens in the original code, or if it's required
            # e.g., 'and' and 'not' require spacing. Operators usually do not except if they form invalid tokens (e.g. '+ +' -> '++')
            if start_col > last_col:
                # If they are names or numbers, we must keep at least one space
                if (tok_type in (tokenize.NAME, tokenize.NUMBER) and prev_toktype in (tokenize.NAME, tokenize.NUMBER)) or \
                   (tok_string in ('and', 'or', 'not', 'in', 'is', 'if', 'else', 'elif', 'for', 'while', 'def', 'class', 'import', 'from', 'as', 'return', 'yield', 'lambda', 'global', 'nonlocal', 'with', 'assert', 'del', 'pass', 'try', 'except', 'finally', 'raise')):
                    result.append(' ')
                elif tok_string == '=' and prev_toktype == tokenize.OP:
                    # In compound assignment operators like +=, we don't insert space
                    pass
                elif start_col - last_col > 0:
                    # If there was space in the original, keep a single space for readability if appropriate
                    # But minification can strip spacing around most operators
                    if tok_type == tokenize.OP or prev_toktype == tokenize.OP:
                        pass
                    else:
                        result.append(' ')

        # Insert actual token string
        if tok_type not in (tokenize.NL, tokenize.COMMENT):
            result.append(tok_string)
            last_col = end_col
            last_lineno = end_line
            prev_toktype = tok_type
        elif tok_type == tokenize.NL:
            # Token NL represents a newline inside a statement or expression block (e.g., inside parentheses)
            # We can strip these, replacing with a single space if it connects words
            if result and not result[-1].endswith('\n'):
                # Avoid inserting consecutive newlines
                pass

    # Assemble and do final pass cleanups
    minified_text = "".join(result)
    
    # Strip double empty lines
    minified_text = re.sub(r'\n{3,}', '\n\n', minified_text)
    
    # Strip any trailing whitespaces on lines
    lines = [line.rstrip() for line in minified_text.splitlines()]
    
    # Strip completely blank lines (leaving indent boundaries correct)
    cleaned_lines = []
    for line in lines:
        if line.strip():
            cleaned_lines.append(line)
        else:
            # If next line is indented, we don't necessarily need empty line in minified
            pass
            
    return "\n".join(cleaned_lines)


def minify_file(input_path, output_path, remove_docstrings=True, remove_comments=True):
    if not os.path.exists(input_path):
        print(f"Error: Input file '{input_path}' does not exist.", file=sys.stderr)
        return 1

    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            source = f.read()
    except Exception as e:
        print(f"Error reading input file: {e}", file=sys.stderr)
        return 1

    try:
        minified = minify_python_code(
            source, 
            remove_docstrings=remove_docstrings, 
            remove_comments=remove_comments
        )
    except Exception as e:
        print(f"Minification Error: {e}", file=sys.stderr)
        return 1

    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(minified)
            
        original_size = os.path.getsize(input_path)
        minified_size = len(minified.encode('utf-8'))
        ratio = (1 - (minified_size / original_size)) * 100 if original_size > 0 else 0
        
        print(f"Python code minified successfully.")
        print(f"  Original Size: {original_size} bytes")
        print(f"  Minified Size: {minified_size} bytes")
        print(f"  Compression Ratio: {ratio:.2f}% reduction")
        return 0
    except Exception as e:
        print(f"Error writing output file: {e}", file=sys.stderr)
        return 1


def main():
    parser = argparse.ArgumentParser(
        description="Minify Python scripts by stripping comments, docstrings, and excess spaces/lines."
    )
    parser.add_argument("input_file", help="Path to the input Python script")
    parser.add_argument(
        "-o", "--output", 
        help="Path to output minified script. Defaults to <input_base>.min.py"
    )
    parser.add_argument(
        "--keep-docstrings", 
        action="store_false", 
        dest="remove_docstrings",
        help="Do not strip docstrings from the code"
    )
    parser.add_argument(
        "--keep-comments", 
        action="store_false", 
        dest="remove_comments",
        help="Do not strip code comments"
    )

    args = parser.parse_args()

    if not args.output:
        base, ext = os.path.splitext(args.input_file)
        args.output = base + ".min" + ext

    sys.exit(
        minify_file(
            args.input_file, 
            args.output, 
            args.remove_docstrings, 
            args.remove_comments
        )
    )


if __name__ == "__main__":
    main()
