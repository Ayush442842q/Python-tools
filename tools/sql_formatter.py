#!/usr/bin/env python3
"""
SQL Formatter - Standardize, format, and beautify SQL queries

This tool parses raw SQL strings, normalizes keywords to uppercase, 
and applies clean line breaks and indentation. It supports formatting SQL
inline or processing files in-place.

Usage:
    python tools/sql_formatter.py [-i INPUT_FILE] [-o OUTPUT_FILE] [-s SQL_STRING] [--in-place]

Example:
    python tools/sql_formatter.py -s "select a, b from users where id = 1 order by created_at desc"
"""

import argparse
import os
import re
import sys
from typing import List, Tuple, Set

SQL_KEYWORDS = {
    'select', 'from', 'where', 'group', 'by', 'order', 'having', 'limit', 'join',
    'left', 'right', 'inner', 'outer', 'cross', 'natural', 'on', 'and', 'or',
    'insert', 'into', 'values', 'update', 'set', 'delete', 'create', 'table',
    'drop', 'alter', 'index', 'view', 'with', 'as', 'in', 'is', 'null', 'not',
    'exists', 'any', 'all', 'union', 'intersect', 'except', 'distinct', 'offset',
    'returning', 'case', 'when', 'then', 'else', 'end', 'like', 'between', 'into',
    'using', 'join', 'as'
}

# Major clauses that should start on a new line
MAJOR_CLAUSES = {
    'SELECT', 'FROM', 'WHERE', 'GROUP BY', 'ORDER BY', 'HAVING', 'LIMIT',
    'JOIN', 'LEFT JOIN', 'RIGHT JOIN', 'INNER JOIN', 'OUTER JOIN', 'CROSS JOIN',
    'UNION', 'UNION ALL', 'VALUES', 'SET', 'UPDATE', 'INSERT INTO', 'DELETE FROM',
    'WITH', 'RETURNING', 'OFFSET'
}

# Functions after which opening parenthesis shouldn't cause a newline
SQL_FUNCTIONS = {
    'COUNT', 'SUM', 'AVG', 'MIN', 'MAX', 'COALESCE', 'CONCAT', 'NOW', 
    'SUBSTR', 'SUBSTRING', 'TRIM', 'LOWER', 'UPPER', 'REPLACE', 'CAST', 'ROUND'
}


def tokenize_sql(sql: str) -> List[Tuple[str, str]]:
    """Tokenizes SQL string into (token_type, token_value) pairs."""
    # Token regex covering:
    # 1. Block comments: /* ... */
    # 2. Line comments: -- ...
    # 3. String literals: '...' or "..."
    # 4. Backticks: `...`
    # 5. Words: [a-zA-Z_][a-zA-Z0-9_]*
    # 6. Operators/Punctuation: >=, <=, !=, <>, ::, or any non-space char
    token_pattern = re.compile(
        r'(/\*.*?\*/)|'                  # block comment
        r'(--[^\r\n]*)|'                 # line comment
        r'(\'(?:[^\']|\\\'|\'\')*\')|'  # single quote string
        r'("(?:[^"]|\\")*")|'            # double quote string
        r'(`[^`]*`)|'                    # backticks
        r'([a-zA-Z_][a-zA-Z0-9_]*)|'     # words
        r'(>=|<=|!=|<>|::|\S)',          # punctuation/operators
        re.DOTALL
    )

    tokens = []
    for match in token_pattern.finditer(sql):
        groups = match.groups()
        if groups[0]:
            tokens.append(('BLOCK_COMMENT', groups[0]))
        elif groups[1]:
            tokens.append(('LINE_COMMENT', groups[1]))
        elif groups[2]:
            tokens.append(('STRING', groups[2]))
        elif groups[3]:
            tokens.append(('STRING', groups[3]))
        elif groups[4]:
            tokens.append(('IDENTIFIER', groups[4]))
        elif groups[5]:
            word = groups[5]
            if word.lower() in SQL_KEYWORDS:
                tokens.append(('KEYWORD', word.upper()))
            else:
                tokens.append(('WORD', word))
        elif groups[6]:
            tokens.append(('PUNCTUATION', groups[6]))

    return tokens


def merge_keywords(tokens: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
    """Merges consecutive keyword tokens like 'GROUP', 'BY' into 'GROUP BY'."""
    merged = []
    i = 0
    n = len(tokens)
    while i < n:
        t_type, t_val = tokens[i]
        
        if i + 1 < n:
            next_type, next_val = tokens[i + 1]
            pair = f"{t_val} {next_val}"
            if t_type == 'KEYWORD' and next_type == 'KEYWORD' and pair in MAJOR_CLAUSES:
                merged.append(('KEYWORD', pair))
                i += 2
                continue
            # Special case for "UNION ALL"
            if t_val == 'UNION' and next_val == 'ALL':
                merged.append(('KEYWORD', 'UNION ALL'))
                i += 2
                continue
        
        merged.append((t_type, t_val))
        i += 1
        
    return merged


def format_sql(raw_sql: str, indent_spaces: int = 4) -> str:
    """Formats and beautifies SQL input."""
    # Strip comments/whitespace to make scanning clean
    tokens = tokenize_sql(raw_sql)
    tokens = merge_keywords(tokens)

    indent_str = " " * indent_spaces
    indent_level = 0
    formatted = []
    
    # Track the state of the line to prevent duplicate newlines or extra spaces
    is_line_start = True
    
    # Helper to append with proper spacing
    def append_token(val: str, prefix_space: bool = True, suffix_space: bool = False, force_newline: bool = False):
        nonlocal is_line_start
        
        if force_newline:
            formatted.append("\n" + (indent_str * indent_level) + val)
            is_line_start = False
            return

        if is_line_start:
            formatted.append(indent_str * indent_level + val)
            is_line_start = False
        else:
            if prefix_space:
                formatted.append(" " + val)
            else:
                formatted.append(val)
        
        if suffix_space:
            formatted.append(" ")

    i = 0
    n = len(tokens)
    while i < n:
        t_type, t_val = tokens[i]
        
        # Check next token preview (ignoring comments)
        next_non_comment = None
        for j in range(i + 1, n):
            if tokens[j][0] not in ('BLOCK_COMMENT', 'LINE_COMMENT'):
                next_non_comment = tokens[j]
                break

        if t_type == 'KEYWORD' and t_val in MAJOR_CLAUSES:
            # Force newline before major clause
            if not is_line_start and formatted:
                formatted.append("\n")
                is_line_start = True
            append_token(t_val, prefix_space=False)
            
        elif t_val == '(':
            # Determine if this is a subquery or a function argument
            prev_token = tokens[i - 1] if i > 0 else None
            is_function = prev_token and (
                prev_token[0] in ('WORD', 'KEYWORD') and 
                prev_token[1].upper() in SQL_FUNCTIONS
            )
            
            is_subquery = next_non_comment and next_non_comment[1] == 'SELECT'
            
            if is_subquery:
                # Subquery starts on a new line and increments indent
                if not is_line_start:
                    formatted.append("\n")
                    is_line_start = True
                append_token("(", prefix_space=False)
                indent_level += 1
                formatted.append("\n")
                is_line_start = True
            elif is_function:
                # Call functions without spaces: e.g. COUNT(id)
                # Trim trailing space of previous token
                if formatted and formatted[-1] == " ":
                    formatted.pop()
                append_token("(", prefix_space=False)
            else:
                append_token("(", prefix_space=True)
                
        elif t_val == ')':
            # Check if matching parenthesis was a subquery
            # For simplicity, we just decrement indent if indent_level > 0
            # and check if the previous formatted lines ended with newline / indentations
            prev_token = tokens[i - 1] if i > 0 else None
            
            # Walk backwards in tokens to see if there's a SELECT in this parenthesis group
            # (simple heuristic)
            depth = 1
            is_subquery_close = False
            for j in range(i - 1, -1, -1):
                if tokens[j][1] == ')':
                    depth += 1
                elif tokens[j][1] == '(':
                    depth -= 1
                    if depth == 0:
                        # Found matching open paren. Was it a subquery?
                        next_to_open = tokens[j + 1] if j + 1 < n else None
                        if next_to_open and next_to_open[1] == 'SELECT':
                            is_subquery_close = True
                        break
            
            if is_subquery_close and indent_level > 0:
                indent_level -= 1
                if not is_line_start:
                    formatted.append("\n")
                    is_line_start = True
                append_token(")", prefix_space=False)
            else:
                append_token(")", prefix_space=False)
                
        elif t_val == ',':
            # Commas stick to the left, space on the right
            if formatted and formatted[-1] == " ":
                formatted.pop()
            append_token(",", prefix_space=False, suffix_space=True)
            
        elif t_type == 'LINE_COMMENT':
            # Print line comment and trigger newline
            append_token(t_val, prefix_space=True)
            formatted.append("\n")
            is_line_start = True
            
        elif t_type == 'BLOCK_COMMENT':
            # If block comment is long, place on its own line
            if '\n' in t_val and not is_line_start:
                formatted.append("\n")
                is_line_start = True
            append_token(t_val, prefix_space=True)
            if '\n' in t_val:
                formatted.append("\n")
                is_line_start = True
                
        elif t_val in ('.', ';'):
            # Remove space before periods or semicolons
            if formatted and formatted[-1] == " ":
                formatted.pop()
            append_token(t_val, prefix_space=False)
            if t_val == ';':
                formatted.append("\n")
                is_line_start = True
                
        else:
            # General word, identifier, operator, or string
            # Check if we need space before this token
            prefix_space = True
            if is_line_start:
                prefix_space = False
            else:
                last_char = formatted[-1] if formatted else ""
                # Avoid space after certain tokens
                if last_char in ("(", ".", " "):
                    prefix_space = False
            
            # Handle keywords (non-clauses like AND, OR, ON, AS, etc.)
            val_to_append = t_val
            if t_type == 'KEYWORD':
                val_to_append = t_val.upper()
                
            append_token(val_to_append, prefix_space=prefix_space)

        i += 1

    # Final cleanup of string representation
    result = "".join(formatted).strip()
    
    # Ensure it ends with exactly one newline if there are multiple lines
    if "\n" in result:
        result += "\n"
        
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="SQL Formatter & Beautifier")
    parser.add_argument('-i', '--input', help='Input file containing raw SQL queries')
    parser.add_argument('-o', '--output', help='Output file to write formatted SQL (default: stdout)')
    parser.add_argument('-s', '--sql', help='SQL query string to format directly')
    parser.add_argument('--in-place', action='store_true', help='Overwrite the input file in-place')
    parser.add_argument('--indent', type=int, default=4, help='Indentation space count (default: 4)')
    
    args = parser.parse_args()

    sql_content = ""
    if args.sql:
        sql_content = args.sql
    elif args.input:
        try:
            with open(args.input, 'r', encoding='utf-8') as f:
                sql_content = f.read()
        except Exception as e:
            print(f"Error reading input file: {e}", file=sys.stderr)
            return 1
    else:
        # Check standard input
        if not sys.stdin.isatty():
            sql_content = sys.stdin.read()
        else:
            parser.print_help()
            return 0

    if not sql_content.strip():
        print("Error: No SQL content provided.", file=sys.stderr)
        return 1

    formatted_sql = format_sql(sql_content, args.indent)

    # Output selection
    if args.in_place:
        if not args.input:
            print("Error: --in-place requires an input file (-i/--input).", file=sys.stderr)
            return 1
        try:
            with open(args.input, 'w', encoding='utf-8') as f:
                f.write(formatted_sql)
            print(f"File formatted in-place: {args.input}")
        except Exception as e:
            print(f"Error writing to file in-place: {e}", file=sys.stderr)
            return 1
    elif args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(formatted_sql)
            print(f"Formatted SQL written to: {args.output}")
        except Exception as e:
            print(f"Error writing to output file: {e}", file=sys.stderr)
            return 1
    else:
        # Standard stdout output
        # Add a visual separator if it's an interactive terminal
        if sys.stdout.isatty() and not args.sql:
            print("=" * 60)
            print("Formatted SQL Output:")
            print("-" * 60)
            print(formatted_sql)
            print("=" * 60)
        else:
            print(formatted_sql)

    return 0


if __name__ == "__main__":
    sys.exit(main())
