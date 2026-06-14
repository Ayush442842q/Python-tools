#!/usr/bin/env python3
"""
Python Code Obfuscator

A command-line tool to obfuscate Python source scripts to protect intellectual property.
Supports comments/docstrings stripping (Level 1), string literal base64-encoding (Level 2),
and zlib + base64 packaging with dynamic executor (Level 3).

Usage:
    python tools/python_code_obfuscator.py script.py --level 2 --out script_obf.py
"""

import argparse
import sys
import os
import tokenize
import io
import base64
import zlib

def remove_comments_and_docstrings(source_code):
    """Safely removes comments and docstrings using Python's tokenize module."""
    try:
        token_stream = tokenize.generate_tokens(io.StringIO(source_code).readline)
    except Exception as e:
        print(f"Tokenization failed: {e}", file=sys.stderr)
        return source_code

    out = []
    last_lineno = 1
    last_col = 0
    
    # Track states to identify docstrings
    # Docstrings are STRING tokens that form a standalone statement.
    # We can approximate this by checking if the previous non-empty token was a newline, indent, or colon,
    # and the next non-empty token is a newline/NL or EOF.
    tokens = list(token_stream)
    docstring_indices = set()
    
    for idx, tok in enumerate(tokens):
        if tok.type == tokenize.STRING:
            # Check if it's a triple-quoted string
            is_triple = tok.string.startswith(('"""', "'''"))
            if is_triple:
                # Find previous non-whitespace/non-comment token
                prev_tok = None
                for p_idx in range(idx - 1, -1, -1):
                    t = tokens[p_idx]
                    if t.type not in (tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT, tokenize.INDENT, tokenize.DEDENT):
                        prev_tok = t
                        break
                
                # Find next non-whitespace/non-comment token
                next_tok = None
                for n_idx in range(idx + 1, len(tokens)):
                    t = tokens[n_idx]
                    if t.type not in (tokenize.NL, tokenize.NEWLINE, tokenize.COMMENT, tokenize.INDENT, tokenize.DEDENT):
                        next_tok = t
                        break
                
                # If it's preceded by a COLON (like inside def/class) or it's at the start of a block (prev_tok is None or INDENT/COLON)
                # and next_tok is not an operator (like assignment, formatting, etc.), it is highly likely a docstring
                if (prev_tok is None or prev_tok.string == ':') and (next_tok is None or next_tok.type in (tokenize.ENDMARKER, tokenize.DEDENT, tokenize.NAME)):
                    docstring_indices.add(idx)
                elif prev_tok is None and next_tok is None:
                    docstring_indices.add(idx)

    for idx, tok in enumerate(tokens):
        token_type = tok.type
        token_string = tok.string
        start_line, start_col = tok.start
        end_line, end_col = tok.end

        # Maintain exact line breaks
        if start_line > last_lineno:
            out.append('\n' * (start_line - last_lineno))
            last_col = 0
            
        # Maintain exact column indentation/spacing
        if start_col > last_col:
            out.append(' ' * (start_col - last_col))

        if token_type == tokenize.COMMENT:
            # Skip comments
            last_lineno = end_line
            last_col = end_col
            continue
            
        if idx in docstring_indices:
            # Skip docstrings
            last_lineno = end_line
            last_col = end_col
            continue

        out.append(token_string)
        last_lineno = end_line
        last_col = end_col

    return "".join(out)

def obfuscate_strings(source_code):
    """Encrypts all string literals in the code and replaces them with a decoder call."""
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source_code).readline))
    except Exception as e:
        print(f"Tokenization failed: {e}", file=sys.stderr)
        return source_code

    # We need a unique helper function name that won't conflict with existing names
    helper_name = "_obf_str_dec"
    while helper_name in source_code:
        helper_name += "_"
        
    out = []
    last_lineno = 1
    last_col = 0
    string_replaced = False

    for tok in tokens:
        token_type = tok.type
        token_string = tok.string
        start_line, start_col = tok.start
        end_line, end_col = tok.end

        if start_line > last_lineno:
            out.append('\n' * (start_line - last_lineno))
            last_col = 0
        if start_col > last_col:
            out.append(' ' * (start_col - last_col))

        # We obfuscate strings, excluding f-strings (start with f/F) and format-specifiers inside f-strings
        # Safe to evaluate normal string tokens using eval to extract the python string content
        is_string = token_type == tokenize.STRING
        is_fstring = is_string and token_string.lower().startswith('f')
        
        if is_string and not is_fstring:
            try:
                # Resolve escaped characters by evaluating the token string
                actual_val = eval(token_string)
                if isinstance(actual_val, str):
                    # Convert string to UTF-8 bytes and base64 encode it
                    encoded_b64 = base64.b64encode(actual_val.encode('utf-8')).decode('ascii')
                    replacement = f"{helper_name}(b'{encoded_b64}')"
                    out.append(replacement)
                    string_replaced = True
                elif isinstance(actual_val, bytes):
                    # For byte strings, base64 encode them too
                    encoded_b64 = base64.b64encode(actual_val).decode('ascii')
                    replacement = f"{helper_name}(b'{encoded_b64}', True)"
                    out.append(replacement)
                    string_replaced = True
                else:
                    out.append(token_string)
            except Exception:
                # If eval fails (e.g. triple quotes with complex characters), fall back to original
                out.append(token_string)
        else:
            out.append(token_string)

        last_lineno = end_line
        last_col = end_col

    # Inject the helper decoder function at the top if any strings were replaced
    if string_replaced:
        helper_def = (
            f"def {helper_name}(data, is_bytes=False):\n"
            f"    import base64\n"
            f"    decoded = base64.b64decode(data)\n"
            f"    return decoded if is_bytes else decoded.decode('utf-8', errors='ignore')\n"
        )
        return helper_def + "".join(out)
        
    return "".join(out)

def pack_code(source_code):
    """Compresses and packages code into an executable base64 string."""
    encoded_payload = base64.b64encode(zlib.compress(source_code.encode('utf-8'))).decode('ascii')
    packed = (
        f"# -*- coding: utf-8 -*-\n"
        f"import base64, zlib\n"
        f"exec(zlib.decompress(base64.b64decode(b'{encoded_payload}')).decode('utf-8'))\n"
    )
    return packed

def main():
    parser = argparse.ArgumentParser(description="Obfuscate Python scripts for distribution.")
    parser.add_argument("input_file", help="Path to the Python file to obfuscate")
    parser.add_argument("--level", type=int, choices=[1, 2, 3], default=2,
                        help="Obfuscation level: 1 (strip comments/docstrings), 2 (encrypt strings + Level 1), 3 (full compression + Level 2)")
    parser.add_argument("--out", help="Output file path (default: prints to stdout)")
    
    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        print(f"Error: Input file '{args.input_file}' not found.", file=sys.stderr)
        return 1

    try:
        with open(args.input_file, 'r', encoding='utf-8', errors='ignore') as f:
            code = f.read()
    except Exception as e:
        print(f"Error reading input file: {e}", file=sys.stderr)
        return 1

    # Level 1: Strip comments and docstrings
    print("Stripping comments and docstrings...", file=sys.stderr)
    processed_code = remove_comments_and_docstrings(code)

    # Level 2: Obfuscate strings (includes Level 1)
    if args.level >= 2:
        print("Obfuscating string literals...", file=sys.stderr)
        processed_code = obfuscate_strings(processed_code)

    # Level 3: Pack with zlib/base64 (includes Level 1 & 2)
    if args.level >= 3:
        print("Packing code into compressed executable...", file=sys.stderr)
        processed_code = pack_code(processed_code)

    # Verify syntax validity of obfuscated code using compile()
    try:
        compile(processed_code, '<obfuscated>', 'exec')
        print("Syntax check: PASSED", file=sys.stderr)
    except SyntaxError as e:
        print(f"Warning: Obfuscated code contains syntax errors: {e}", file=sys.stderr)
        print("Aborting to prevent writing non-executable code.", file=sys.stderr)
        return 1

    if args.out:
        try:
            with open(args.out, 'w', encoding='utf-8') as f:
                f.write(processed_code)
            print(f"Successfully wrote obfuscated script to: {args.out}", file=sys.stderr)
        except Exception as e:
            print(f"Error writing output file: {e}", file=sys.stderr)
            return 1
    else:
        sys.stdout.write(processed_code)

    return 0

if __name__ == "__main__":
    sys.exit(main())
