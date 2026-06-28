#!/usr/bin/env python3
"""
SQL Linter & Formatter - A pure-Python tool to check SQL queries for errors, anti-patterns, and formatting.

Usage:
    python tools/sql_linter.py -q "select * from users"
    python tools/sql_linter.py input.sql --format
"""

import sys
import os
import re
import argparse

# ANSI color codes
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

SQL_KEYWORDS = {
    "SELECT", "FROM", "WHERE", "JOIN", "INNER", "LEFT", "RIGHT", "OUTER", "ON",
    "GROUP", "ORDER", "BY", "HAVING", "LIMIT", "UPDATE", "SET", "DELETE", "INSERT",
    "INTO", "VALUES", "CREATE", "TABLE", "DROP", "ALTER", "AND", "OR", "AS", "IN",
    "EXISTS", "UNION", "ALL", "WITH", "CASE", "WHEN", "THEN", "ELSE", "END", "DISTINCT"
}

def parse_sql(sql):
    """
    Parse SQL into a list of tokens, identifying strings, comments, and code.
    Returns: (clean_sql_without_literals, list_of_tokens, errors)
    """
    errors = []
    length = len(sql)
    i = 0
    
    in_single_quote = False
    in_double_quote = False
    in_single_comment = False
    in_multi_comment = False
    
    parentheses_stack = []
    
    clean_parts = []
    
    while i < length:
        char = sql[i]
        
        # Handle single-line comment
        if in_single_comment:
            if char == '\n':
                in_single_comment = False
                clean_parts.append(char)
            i += 1
            continue
            
        # Handle multi-line comment
        if in_multi_comment:
            if char == '*' and i + 1 < length and sql[i+1] == '/':
                in_multi_comment = False
                i += 2
            else:
                i += 1
            continue
            
        # Handle single quote string
        if in_single_quote:
            if char == '\\' and i + 1 < length:
                i += 2
            elif char == "'":
                in_single_quote = False
                i += 1
            else:
                i += 1
            continue

        # Handle double quote string
        if in_double_quote:
            if char == '\\' and i + 1 < length:
                i += 2
            elif char == '"':
                in_double_quote = False
                i += 1
            else:
                i += 1
            continue

        # Check for comments start
        if char == '-' and i + 1 < length and sql[i+1] == '-':
            in_single_comment = True
            # Warn if comments don't have space: '--comment' instead of '-- comment'
            if i + 2 < length and sql[i+2] not in (' ', '\n', '\r'):
                errors.append(("WARNING", f"Comment starts without space: '--{sql[i+2:i+5]}...'", i))
            i += 2
            continue
            
        if char == '/' and i + 1 < length and sql[i+1] == '*':
            in_multi_comment = True
            i += 2
            continue

        # Check for quotes start
        if char == "'":
            in_single_quote = True
            i += 1
            continue
        if char == '"':
            in_double_quote = True
            i += 1
            continue

        # Handle parentheses
        if char == '(':
            parentheses_stack.append(('(', i))
            clean_parts.append(char)
        elif char == ')':
            if not parentheses_stack:
                errors.append(("ERROR", "Mismatched parentheses: excess closing parenthesis ')'", i))
            else:
                parentheses_stack.pop()
            clean_parts.append(char)
        else:
            clean_parts.append(char)
            
        i += 1

    # End of string checks
    if in_single_quote:
        errors.append(("ERROR", "Unclosed single quote string literal", length))
    if in_double_quote:
        errors.append(("ERROR", "Unclosed double quote string literal", length))
    if in_multi_comment:
        errors.append(("ERROR", "Unclosed multi-line comment block (/* ... */)", length))
    while parentheses_stack:
        _, pos = parentheses_stack.pop()
        errors.append(("ERROR", "Unclosed opening parenthesis '('", pos))

    clean_sql = "".join(clean_parts)
    return clean_sql, errors

def lint_sql(sql):
    """Analyze SQL for anti-patterns and formatting improvements"""
    clean_sql, errors = parse_sql(sql)
    
    # 1. Check for SELECT *
    # Match SELECT followed by * (ignoring whitespace/comments)
    # We use clean_sql to ignore string contents/comments
    if re.search(r'\bSELECT\s+\*', clean_sql, re.IGNORECASE):
        errors.append(("WARNING", "Avoid using SELECT *. Specify explicit column names for cleaner data contracts and optimization.", 0))

    # 2. Check for dangerous UPDATE/DELETE without WHERE
    # Check UPDATE statements
    update_matches = re.finditer(r'\bUPDATE\b', clean_sql, re.IGNORECASE)
    for m in update_matches:
        start_idx = m.start()
        # Find everything until next semicolon or end
        stmt = clean_sql[start_idx:]
        end_idx = stmt.find(';')
        if end_idx != -1:
            stmt = stmt[:end_idx]
        if not re.search(r'\bWHERE\b', stmt, re.IGNORECASE):
            errors.append(("ERROR", "UPDATE statement missing a WHERE clause. This will modify ALL rows in the table!", start_idx))

    # Check DELETE statements
    delete_matches = re.finditer(r'\bDELETE\b', clean_sql, re.IGNORECASE)
    for m in delete_matches:
        start_idx = m.start()
        stmt = clean_sql[start_idx:]
        end_idx = stmt.find(';')
        if end_idx != -1:
            stmt = stmt[:end_idx]
        if not re.search(r'\bWHERE\b', stmt, re.IGNORECASE):
            errors.append(("ERROR", "DELETE statement missing a WHERE clause. This will delete ALL rows in the table!", start_idx))

    # 3. Check keyword casing
    # Find all words in the clean SQL
    words = re.finditer(r'\b[a-zA-Z_]+\b', clean_sql)
    for w in words:
        word = w.group()
        word_upper = word.upper()
        if word_upper in SQL_KEYWORDS:
            if word != word_upper:
                # Inconsistent casing
                errors.append(("WARNING", f"Keyword '{word}' should be uppercase '{word_upper}'", w.start()))

    # 4. Check for trailing semicolon
    stripped = sql.strip()
    if stripped and not stripped.endswith(';'):
        errors.append(("WARNING", "SQL statement is missing a trailing semicolon ';'", len(sql) - 1))

    return errors

def format_sql(sql):
    """Enforce formatting: uppercase keywords, spacing, clean line breaks"""
    # 1. Uppercase all keywords first
    def uppercase_kw(match):
        word = match.group(0)
        return word.upper()
    
    # We compile keyword pattern
    kw_pattern = re.compile(r'\b(' + '|'.join(SQL_KEYWORDS) + r')\b', re.IGNORECASE)
    formatted = kw_pattern.sub(uppercase_kw, sql)

    # 2. Cleanup excess spacing
    formatted = re.sub(r'[ \t]+', ' ', formatted)
    
    # 3. Break lines before major keywords
    line_break_keywords = ["FROM", "WHERE", "GROUP BY", "ORDER BY", "HAVING", "LIMIT", "LEFT JOIN", "RIGHT JOIN", "INNER JOIN", "JOIN", "UNION"]
    for kw in line_break_keywords:
        # Avoid double line breaks
        formatted = re.sub(r'\s*\b' + kw + r'\b\s*', f'\n{kw} ', formatted)

    # Clean up blank lines and trailing space
    lines = [line.strip() for line in formatted.splitlines() if line.strip()]
    
    # Indent elements inside SELECT or after line breaks for basic beauty
    final_lines = []
    for line in lines:
        if any(line.startswith(kw) for kw in line_break_keywords):
            final_lines.append(line)
        elif line.startswith("SELECT") or line.startswith("UPDATE") or line.startswith("DELETE") or line.startswith("INSERT"):
            final_lines.append(line)
        else:
            # indent nested lines
            final_lines.append("  " + line)

    # Rejoin and add final semicolon if missing
    res = "\n".join(final_lines)
    if not res.endswith(';'):
        res += ';'
        
    return res

def get_line_number(sql, pos):
    """Find line number of character index"""
    return sql[:pos].count('\n') + 1

def main():
    parser = argparse.ArgumentParser(
        description="SQL Linter & Formatter - Lint queries for syntax bugs/anti-patterns and auto-format."
    )
    parser.add_argument("file", nargs="?", help="SQL file path (reads from stdin if omitted).")
    parser.add_argument("-q", "--query", help="Direct SQL query string to lint.")
    parser.add_argument("--format", action="store_true", help="Auto-format and output formatted SQL.")
    
    args = parser.parse_args()

    # Enable Windows ANSI escape codes support
    if sys.platform == "win32":
        import os
        os.system("color")

    # Read SQL content
    sql_content = ""
    if args.query:
        sql_content = args.query
    elif args.file:
        if not os.path.exists(args.file):
            print(f"{RED}Error: File '{args.file}' not found.{RESET}", file=sys.stderr)
            return 1
        with open(args.file, "r", encoding="utf-8", errors="ignore") as f:
            sql_content = f.read()
    else:
        # Check if stdin is empty
        if sys.stdin.isatty():
            parser.print_help()
            return 0
        sql_content = sys.stdin.read()

    if not sql_content.strip():
        print(f"{YELLOW}Empty SQL query input.{RESET}")
        return 0

    if args.format:
        formatted = format_sql(sql_content)
        print(formatted)
        return 0

    print(f"{BOLD}{BLUE}Linting SQL Query...{RESET}\n")
    errors = lint_sql(sql_content)

    if not errors:
        print(f"{GREEN}✓ No issues found! SQL syntax looks clean and follows best practices.{RESET}")
        return 0

    # Sort issues by position/line
    errors_sorted = sorted(errors, key=lambda x: x[2])
    
    err_count = sum(1 for severity, _, _ in errors if severity == "ERROR")
    warn_count = sum(1 for severity, _, _ in errors if severity == "WARNING")

    for severity, msg, pos in errors_sorted:
        line_no = get_line_number(sql_content, pos) if pos > 0 else 1
        color = RED if severity == "ERROR" else YELLOW
        print(f"  {color}[{severity}]{RESET} Line {line_no}: {msg}")

    print(f"\nSummary: {RED if err_count else GREEN}{err_count} Errors{RESET}, {YELLOW if warn_count else GREEN}{warn_count} Warnings{RESET}\n")

    return 1 if err_count > 0 else 0

if __name__ == "__main__":
    sys.exit(main())
