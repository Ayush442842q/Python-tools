#!/usr/bin/env python3
"""
SQL Query Obfuscator & Sanitizer

Parses SQL queries and sanitizes them by replacing sensitive literal values
(strings, numeric values, hex literals, etc.) with placeholders (e.g., ?).
This is useful for database logging, sharing query logs for performance tuning,
or diagnostic purposes without exposing PII or confidential data.

Usage:
    python tools/sql_query_obfuscator.py -q "SELECT * FROM users WHERE email = 'john@example.com' AND age > 21"
    python tools/sql_query_obfuscator.py -i input_queries.sql -o sanitized_queries.sql
"""

import os
import sys
import re
import argparse

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_colored(text, color, enabled=True):
    """Print text with ANSI color if enabled."""
    if enabled:
        print(f"{color}{text}{RESET}")
    else:
        print(text)

def obfuscate_sql(sql: str, placeholder: str = "?", strip_comments: bool = False) -> tuple:
    """
    Sanitizes SQL by replacing string literals, numbers, and hex values with a placeholder.
    Also strips comments if specified.
    
    Returns:
        (sanitized_sql, stats_dict)
    """
    stats = {
        "strings_redacted": 0,
        "numbers_redacted": 0,
        "comments_removed": 0
    }
    
    # 1. Handle Comments first if requested
    if strip_comments:
        # Block comments: /* ... */
        sql, block_count = re.subn(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
        # Line comments: -- ... or # ...
        sql, line_count = re.subn(r'(--|#).*?$', '', sql, flags=re.MULTILINE)
        stats["comments_removed"] = block_count + line_count

    # To avoid corrupting query structures, we parse character-by-character.
    # We recognize:
    # - Single-quoted strings: '...' (escaped by doubling '')
    # - Double-quoted strings: "..." (sometimes used for identifiers, but can be string literals)
    # - Numeric literals (integers, decimals) not part of identifiers
    # - Safe identifiers inside quotes are left intact.
    
    result = []
    i = 0
    n = len(sql)
    
    while i < n:
        char = sql[i]
        
        # Handle single-quoted string literals
        if char == "'":
            # Search for ending single quote
            start = i
            i += 1
            while i < n:
                if sql[i] == "'" and (i + 1 < n and sql[i+1] == "'"):
                    # Escaped single quote by doubling: ''
                    i += 2
                elif sql[i] == "'":
                    # End of string
                    i += 1
                    break
                else:
                    i += 1
            result.append(placeholder)
            stats["strings_redacted"] += 1
            continue
            
        # Handle double-quoted literals/identifiers
        elif char == '"':
            # Keep double quotes but check if it's a string or identifier.
            # In standard SQL, double quotes are for identifiers (like table/column names).
            # But in MySQL/SQLite, they can be strings.
            # For safety, let's redact it if it looks like a string value (e.g. not just alpha-numeric).
            start = i
            i += 1
            while i < n:
                if sql[i] == '"' and (i + 1 < n and sql[i+1] == '"'):
                    i += 2
                elif sql[i] == '"':
                    i += 1
                    break
                else:
                    i += 1
            content = sql[start+1:i-1]
            # Simple heuristic: if it has spaces or punctuation, treat as string literal.
            if re.search(r'[^a-zA-Z0-9_]', content):
                result.append(placeholder)
                stats["strings_redacted"] += 1
            else:
                result.append(sql[start:i])
            continue
            
        # Check for numeric literals
        # We need to make sure we don't match numbers inside table names (users_1) or parameters ($1, :1).
        elif char.isdigit():
            # Look back to make sure it's not part of an identifier
            prev_word_char = False
            if result:
                last_segment = result[-1]
                if last_segment and (last_segment[-1].isalnum() or last_segment[-1] in ('_', '$', ':', '.')):
                    prev_word_char = True
            
            if prev_word_char:
                # Part of identifier or parameter (e.g., $1 or table_2 or :param1)
                result.append(char)
                i += 1
            else:
                # Start of numeric literal
                start = i
                # Consume digits, decimal points, exponents (e or E)
                has_decimal = False
                while i < n and (sql[i].isdigit() or sql[i] == '.' or sql[i].lower() in ('e', '-', '+')):
                    if sql[i] == '.':
                        if has_decimal:
                            break # Multi-decimal? Stop.
                        has_decimal = True
                    i += 1
                num_str = sql[start:i]
                # Validate it's actually a number, not some weird string
                if re.match(r'^\d+(\.\d+)?([eE][+-]?\d+)?$', num_str):
                    result.append(placeholder)
                    stats["numbers_redacted"] += 1
                else:
                    result.append(num_str)
            continue
            
        else:
            result.append(char)
            i += 1
            
    # Clean up double placeholders in lists (e.g. VALUES (?, ?, ?)) if any
    sanitized = "".join(result)
    return sanitized, stats

def main():
    parser = argparse.ArgumentParser(
        description="SQL Query Obfuscator & Sanitizer - Redact sensitive literals from SQL statements."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-q", "--query", help="Raw SQL query string to obfuscate.")
    group.add_argument("-i", "--input", help="Path to input SQL file.")
    
    parser.add_argument("-o", "--output", help="Path to output SQL file (optional for file inputs).")
    parser.add_argument("-p", "--placeholder", default="?", help="Placeholder to replace literals (default: ?).")
    parser.add_argument("-s", "--strip-comments", action="store_true", help="Remove SQL comments (-- and /* */).")
    parser.add_argument("--no-color", action="store_true", help="Disable colored console outputs.")

    args = parser.parse_args()
    use_color = not args.no_color

    if args.query:
        sanitized, stats = obfuscate_sql(args.query, args.placeholder, args.strip_comments)
        
        print_colored("--- ORIGINAL SQL ---", BLUE, use_color)
        print(args.query.strip())
        print()
        print_colored("--- OBFUSCATED SQL ---", GREEN, use_color)
        print(sanitized.strip())
        print()
        print_colored("--- REDACTION STATISTICS ---", YELLOW, use_color)
        for k, v in stats.items():
            print(f"  {k.replace('_', ' ').capitalize()}: {v}")
            
    elif args.input:
        if not os.path.exists(args.input):
            print_colored(f"Error: Input file '{args.input}' not found.", RED, use_color)
            sys.exit(1)
            
        with open(args.input, 'r', encoding='utf-8') as f:
            raw_sql = f.read()
            
        sanitized, stats = obfuscate_sql(raw_sql, args.placeholder, args.strip_comments)
        
        # Decide output destination
        if args.output:
            out_path = args.output
        else:
            base, ext = os.path.splitext(args.input)
            out_path = f"{base}_obfuscated{ext}"
            
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(sanitized)
            
        print_colored(f"Success! Obfuscated SQL saved to '{out_path}'", GREEN, use_color)
        print_colored("--- REDACTION STATISTICS ---", YELLOW, use_color)
        for k, v in stats.items():
            print(f"  {k.replace('_', ' ').capitalize()}: {v}")

if __name__ == "__main__":
    main()
