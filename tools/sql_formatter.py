#!/usr/bin/env python3
"""
SQL Query Formatter
Formats raw, unformatted SQL queries into clean, readable, indented SQL queries.
"""

import argparse
import sys
import re

KEYWORDS = {
    'SELECT', 'FROM', 'WHERE', 'GROUP', 'BY', 'HAVING', 'ORDER', 'LIMIT',
    'JOIN', 'LEFT', 'RIGHT', 'INNER', 'OUTER', 'CROSS', 'ON', 'USING',
    'AND', 'OR', 'NOT', 'IN', 'IS', 'NULL', 'LIKE', 'AS',
    'INSERT', 'INTO', 'VALUES', 'UPDATE', 'SET', 'DELETE',
    'CREATE', 'TABLE', 'DROP', 'INDEX', 'ALTER', 'ADD',
    'WITH', 'UNION', 'ALL', 'CASE', 'WHEN', 'THEN', 'ELSE', 'END',
    'EXISTS', 'ANY', 'BETWEEN', 'OVER', 'PARTITION', 'ROWS', 'DISTINCT',
    'DESC', 'ASC', 'ON', 'DUPLICATE', 'KEY'
}

def tokenize_sql(sql):
    tokens = []
    i = 0
    n = len(sql)
    while i < n:
        # Check whitespace
        if sql[i].isspace():
            j = i
            while j < n and sql[j].isspace():
                j += 1
            tokens.append(('WS', ' '))
            i = j
            continue
            
        # Check single-line comments
        if sql[i:i+2] == '--':
            j = sql.find('\n', i)
            if j == -1:
                j = n
            tokens.append(('COMMENT', sql[i:j]))
            i = j
            continue

        # Check multi-line comments
        if sql[i:i+2] == '/*':
            j = sql.find('*/', i+2)
            if j == -1:
                tokens.append(('COMMENT', sql[i:]))
                i = n
            else:
                tokens.append(('COMMENT', sql[i:j+2]))
                i = j + 2
            continue

        # Check strings (single quote)
        if sql[i] == "'":
            j = i + 1
            val = "'"
            while j < n:
                if sql[j] == "'" and j + 1 < n and sql[j+1] == "'":
                    val += "''"
                    j += 2
                elif sql[j] == "'":
                    val += "'"
                    j += 1
                    break
                else:
                    val += sql[j]
                    j += 1
            tokens.append(('STRING', val))
            i = j
            continue

        # Check double-quoted identifiers
        if sql[i] == '"':
            j = i + 1
            val = '"'
            while j < n:
                if sql[j] == '"' and j + 1 < n and sql[j+1] == '"':
                    val += '""'
                    j += 2
                elif sql[j] == '"':
                    val += '"'
                    j += 1
                    break
                else:
                    val += sql[j]
                    j += 1
            tokens.append(('IDENTIFIER_QUOTE', val))
            i = j
            continue

        # Check backticks
        if sql[i] == '`':
            j = i + 1
            val = '`'
            while j < n:
                if sql[j] == '`':
                    val += '`'
                    j += 1
                    break
                else:
                    val += sql[j]
                    j += 1
            tokens.append(('IDENTIFIER_QUOTE', val))
            i = j
            continue

        # Symbols / Operators
        if sql[i:i+2] in ('!=', '<=', '>=', '<>', '||', '&&'):
            tokens.append(('OPERATOR', sql[i:i+2]))
            i += 2
            continue

        if sql[i] in '(),;.*+-/=<>&|!%':
            tokens.append(('SYMBOL', sql[i]))
            i += 1
            continue

        # Words/Keywords
        if sql[i].isalnum() or sql[i] == '_':
            j = i
            while j < n and (sql[j].isalnum() or sql[j] == '_'):
                j += 1
            word = sql[i:j]
            tokens.append(('WORD', word))
            i = j
            continue

        # Fallback for anything else
        tokens.append(('CHAR', sql[i]))
        i += 1
    return tokens

def combine_tokens(tokens):
    # Filter WS
    tokens = [t for t in tokens if t[0] != 'WS']
    
    combined = []
    i = 0
    n = len(tokens)
    while i < n:
        t = tokens[i]
        
        # Uppercase keywords
        if t[0] == 'WORD' and t[1].upper() in KEYWORDS:
            t = (t[0], t[1].upper())
            
        # Check compound tokens
        if i + 1 < n:
            next_t = tokens[i+1]
            if next_t[0] == 'WORD' and next_t[1].upper() in KEYWORDS:
                next_t = (next_t[0], next_t[1].upper())
            
            combined_pair = (t[1], next_t[1])
            if combined_pair in [
                ('GROUP', 'BY'), ('ORDER', 'BY'),
                ('LEFT', 'JOIN'), ('RIGHT', 'JOIN'), ('INNER', 'JOIN'),
                ('FULL', 'JOIN'), ('CROSS', 'JOIN'), ('UNION', 'ALL'),
                ('INSERT', 'INTO'), ('DELETE', 'FROM'), ('CREATE', 'TABLE'),
                ('DROP', 'TABLE'), ('ALTER', 'TABLE'), ('ON', 'DUPLICATE')
            ]:
                combined.append(('KEYWORD', f"{combined_pair[0]} {combined_pair[1]}"))
                i += 2
                continue
                
        if t[0] == 'WORD' and t[1] in KEYWORDS:
            combined.append(('KEYWORD', t[1]))
        else:
            combined.append(t)
        i += 1
    return combined

def format_sql(sql_text, indent_width=4, uppercase_keywords=True, logical_newline=False):
    tokens = tokenize_sql(sql_text)
    combined = combine_tokens(tokens)
    
    formatted = []
    indent_level = 0
    paren_stack = []  # Elements: True if subquery paren, False if regular paren
    in_select_list = False
    between_active = False
    
    def get_indent():
        return " " * (indent_level * indent_width)
    
    i = 0
    n = len(combined)
    
    def is_subquery_start(idx):
        if idx >= n or combined[idx][0] != 'SYMBOL' or combined[idx][1] != '(':
            return False
        j = idx + 1
        while j < n:
            tok_type, tok_val = combined[j]
            if tok_type == 'COMMENT':
                j += 1
                continue
            if tok_type == 'KEYWORD' and tok_val in ('SELECT', 'WITH'):
                return True
            break
        return False

    need_space = False
    
    while i < n:
        tok_type, tok_val = combined[i]
        
        # Track BETWEEN state
        if tok_type == 'KEYWORD' and tok_val == 'BETWEEN':
            between_active = True

        # Major clauses that start a new line
        if tok_type == 'KEYWORD' and tok_val in (
            'SELECT', 'FROM', 'WHERE', 'GROUP BY', 'ORDER BY', 'HAVING', 'LIMIT',
            'JOIN', 'LEFT JOIN', 'RIGHT JOIN', 'INNER JOIN', 'FULL JOIN', 'CROSS JOIN',
            'UNION', 'UNION ALL', 'SET', 'VALUES', 'INSERT INTO', 'DELETE FROM', 'UPDATE', 'WITH'
        ):
            if tok_val == 'FROM':
                in_select_list = False
            elif tok_val == 'SELECT':
                in_select_list = True
                
            if formatted:
                formatted[-1] = formatted[-1].rstrip()
                formatted.append('\n' + get_indent())
            
            formatted.append(tok_val)
            need_space = True
            i += 1
            continue
            
        # Logical operators (AND, OR)
        if logical_newline and tok_type == 'KEYWORD' and tok_val in ('AND', 'OR'):
            if tok_val == 'AND' and between_active:
                between_active = False
                # No newline for AND in BETWEEN
            else:
                # Put AND/OR on a new line, aligned
                if formatted:
                    formatted[-1] = formatted[-1].rstrip()
                    formatted.append('\n' + get_indent())
                formatted.append(tok_val)
                need_space = True
                i += 1
                continue

        # Opening parenthesis
        if tok_type == 'SYMBOL' and tok_val == '(':
            if is_subquery_start(i):
                paren_stack.append(True)
                if formatted:
                    formatted[-1] = formatted[-1].rstrip()
                    formatted.append('\n' + get_indent())
                formatted.append('(')
                indent_level += 1
                formatted.append('\n' + get_indent())
                need_space = False
            else:
                paren_stack.append(False)
                is_function = (i > 0 and combined[i-1][0] in ('WORD', 'KEYWORD'))
                if is_function:
                    if formatted and formatted[-1] == ' ':
                        formatted.pop()
                    elif formatted:
                        formatted[-1] = formatted[-1].rstrip()
                if need_space and not is_function:
                    if formatted and formatted[-1] != ' ':
                        formatted.append(' ')
                formatted.append('(')
                need_space = False
            i += 1
            continue
            
        # Closing parenthesis
        if tok_type == 'SYMBOL' and tok_val == ')':
            if paren_stack:
                is_sub = paren_stack.pop()
                if is_sub:
                    indent_level = max(0, indent_level - 1)
                    if formatted:
                        formatted[-1] = formatted[-1].rstrip()
                        formatted.append('\n' + get_indent())
                    formatted.append(')')
                    need_space = True
                else:
                    formatted.append(')')
                    need_space = True
            else:
                formatted.append(')')
                need_space = True
            i += 1
            continue
            
        # Comma formatting
        if tok_type == 'SYMBOL' and tok_val == ',':
            formatted.append(',')
            is_inside_function = paren_stack and not paren_stack[-1]
            
            if in_select_list and not is_inside_function:
                # Break to new line for select items
                formatted[-1] = formatted[-1].rstrip()
                formatted.append('\n' + get_indent() + ' ' * indent_width)
                need_space = False
            else:
                need_space = True
            i += 1
            continue
            
        # Comment formatting
        if tok_type == 'COMMENT':
            if formatted:
                formatted[-1] = formatted[-1].rstrip()
                formatted.append('\n' + get_indent())
            formatted.append(tok_val)
            formatted.append('\n' + get_indent())
            need_space = False
            i += 1
            continue
            
        # Dots/Period: no spaces around it
        if tok_val == '.':
            if formatted:
                formatted[-1] = formatted[-1].rstrip()
                if formatted and formatted[-1] == ' ':
                    formatted.pop()
            formatted.append('.')
            need_space = False
            i += 1
            continue

        # Semicolon: no space before
        if tok_val == ';':
            if formatted:
                formatted[-1] = formatted[-1].rstrip()
                if formatted and formatted[-1] == ' ':
                    formatted.pop()
            formatted.append(';')
            need_space = True
            i += 1
            continue

        # Add token to formatted list
        if need_space:
            formatted.append(' ')
            
        # Handle select columns starting after SELECT keyword
        if in_select_list and len(formatted) >= 2 and formatted[-2] == 'SELECT' and formatted[-1] == ' ':
            formatted.pop() # Remove space
            formatted.append('\n' + get_indent() + ' ' * indent_width)

        # Casing for words
        if tok_type == 'WORD':
            val_to_append = tok_val.upper() if (uppercase_keywords and tok_val.upper() in KEYWORDS) else tok_val
        elif tok_type == 'KEYWORD':
            val_to_append = tok_val if uppercase_keywords else tok_val.lower()
        else:
            val_to_append = tok_val
            
        formatted.append(val_to_append)
        
        # Operators, keywords, words, literals usually need a space after them
        if tok_type in ('WORD', 'KEYWORD', 'STRING', 'IDENTIFIER_QUOTE', 'OPERATOR', 'CHAR'):
            need_space = True
        elif tok_type == 'SYMBOL' and tok_val in ('=', '+', '-', '*', '/', '<', '>', '!'):
            need_space = True
        else:
            need_space = False
            
        i += 1
        
    return ''.join(formatted).strip()

def main():
    parser = argparse.ArgumentParser(
        description="Format raw, unformatted SQL queries into clean, readable, indented SQL queries."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-s", "--sql", help="Raw SQL query string to format")
    group.add_argument("-f", "--file", help="Path to a SQL file to format")
    
    parser.add_argument("-o", "--output", help="Path to write the formatted SQL (default: prints to stdout)")
    parser.add_argument("-i", "--indent", type=int, default=4, help="Indentation width in spaces (default: 4)")
    parser.add_argument("--logical-newline", action="store_true", help="Place AND/OR logical operators on new lines")
    parser.add_argument("--lowercase-keywords", action="store_true", help="Format keywords in lowercase instead of uppercase")

    args = parser.parse_args()

    sql_content = ""
    if args.sql:
        sql_content = args.sql
    elif args.file:
        if not os.path.exists(args.file):
            print(f"[ERROR] SQL file '{args.file}' does not exist.")
            sys.exit(1)
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                sql_content = f.read()
        except Exception as e:
            print(f"[ERROR] Failed to read file: {e}")
            sys.exit(1)

    if not sql_content.strip():
        print("[WARNING] Empty SQL input.")
        sys.exit(0)

    formatted_sql = format_sql(
        sql_content,
        indent_width=args.indent,
        uppercase_keywords=not args.lowercase_keywords,
        logical_newline=args.logical_newline
    )

    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(formatted_sql + '\n')
            print(f"[PASS] Formatted SQL written to '{args.output}'")
        except Exception as e:
            print(f"[ERROR] Failed to write formatted SQL to file: {e}")
            sys.exit(1)
    else:
        print(formatted_sql)

if __name__ == "__main__":
    main()
