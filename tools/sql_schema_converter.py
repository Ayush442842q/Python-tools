#!/usr/bin/env python3
"""
SQL DDL Dialect Translator
A standalone script to translate DDL (Data Definition Language) SQL scripts
between PostgreSQL, MySQL, SQLite, and Microsoft SQL Server dialects.
"""

import sys
import os
import argparse
import re

# Mapping of data types between dialects
# Structure: {source_type_regex: {target_dialect: replacement_string}}
TYPE_MAP = {
    # Auto-incrementing primary keys
    r'\bSERIAL\b': {
        'sqlite': 'INTEGER PRIMARY KEY AUTOINCREMENT',
        'mysql': 'INT AUTO_INCREMENT PRIMARY KEY',
        'sqlserver': 'INT IDENTITY(1,1) PRIMARY KEY',
        'postgresql': 'SERIAL'
    },
    r'\bBIGSERIAL\b': {
        'sqlite': 'INTEGER PRIMARY KEY AUTOINCREMENT',
        'mysql': 'BIGINT AUTO_INCREMENT PRIMARY KEY',
        'sqlserver': 'BIGINT IDENTITY(1,1) PRIMARY KEY',
        'postgresql': 'BIGSERIAL'
    },
    # Booleans
    r'\bBOOLEAN\b|\bBOOL\b': {
        'sqlite': 'INTEGER',  # SQLite stores booleans as 0 or 1
        'mysql': 'TINYINT(1)',
        'sqlserver': 'BIT',
        'postgresql': 'BOOLEAN'
    },
    # Binary data
    r'\bBYTEA\b': {
        'sqlite': 'BLOB',
        'mysql': 'LONGBLOB',
        'sqlserver': 'VARBINARY(MAX)',
        'postgresql': 'BYTEA'
    },
    r'\bLONGBLOB\b|\bMEDIUMBLOB\b': {
        'sqlite': 'BLOB',
        'mysql': 'LONGBLOB',
        'sqlserver': 'VARBINARY(MAX)',
        'postgresql': 'BYTEA'
    },
    # JSON strings
    r'\bJSONB\b|\bJSON\b': {
        'sqlite': 'TEXT',
        'mysql': 'JSON',
        'sqlserver': 'NVARCHAR(MAX)',
        'postgresql': 'JSONB'
    },
    # Text types
    r'\bTEXT\b': {
        'sqlite': 'TEXT',
        'mysql': 'LONGTEXT',
        'sqlserver': 'NVARCHAR(MAX)',
        'postgresql': 'TEXT'
    },
    # Time/Timestamps
    r'\bTIMESTAMPTZ\b|\bTIMESTAMP\s+WITH\s+TIME\s+ZONE\b': {
        'sqlite': 'TEXT',
        'mysql': 'DATETIME',
        'sqlserver': 'DATETIMEOFFSET',
        'postgresql': 'TIMESTAMP WITH TIME ZONE'
    },
    r'\bTIMESTAMP\s+WITHOUT\s+TIME\s+ZONE\b': {
        'sqlite': 'TEXT',
        'mysql': 'TIMESTAMP',
        'sqlserver': 'DATETIME2',
        'postgresql': 'TIMESTAMP'
    },
    # Doubles/floats
    r'\bDOUBLE\s+PRECISION\b': {
        'sqlite': 'REAL',
        'mysql': 'DOUBLE',
        'sqlserver': 'FLOAT(53)',
        'postgresql': 'DOUBLE PRECISION'
    }
}

def clean_sql(sql):
    """Strip SQL comments and blank lines."""
    # Remove block comments
    sql = re.sub(r'/\*.*?\*/', '', sql, flags=re.DOTALL)
    # Remove single line comments
    lines = sql.splitlines()
    clean_lines = []
    for line in lines:
        stripped = re.sub(r'--.*$', '', line).strip()
        if stripped:
            clean_lines.append(stripped)
    return " ".join(clean_lines)

def split_statements(sql):
    """Splits unified SQL script into individual statements by semicolon."""
    statements = []
    current = []
    in_quote = False
    quote_char = None
    
    for char in sql:
        if char in ("'", '"', '`') and (not in_quote or quote_char == char):
            in_quote = not in_quote
            quote_char = char if in_quote else None
        
        current.append(char)
        
        if char == ';' and not in_quote:
            statements.append("".join(current).strip())
            current = []
            
    remainder = "".join(current).strip()
    if remainder:
        statements.append(remainder)
    return statements

def translate_identifiers(statement, target):
    """Converts quotes around tables/columns to fit target dialect."""
    # MySQL uses backticks: `table_name`
    # T-SQL uses square brackets: [table_name]
    # PostgreSQL/SQLite use double quotes: "table_name"
    
    # Simple regex replacing to target identifier syntax
    if target == 'mysql':
        # Convert "id" or [id] to `id`
        statement = re.sub(r'"([^"]+)"', r'`\1`', statement)
        statement = re.sub(r'\[([^\]]+)\]', r'`\1`', statement)
    elif target == 'sqlserver':
        # Convert `id` or "id" to [id]
        statement = re.sub(r'`([^`]+)`', r'[\1]', statement)
        statement = re.sub(r'"([^"]+)"', r'[\1]', statement)
    else: # sqlite or postgresql
        # Convert `id` or [id] to "id"
        statement = re.sub(r'`([^`]+)`', r'"\1"', statement)
        statement = re.sub(r'\[([^\]]+)\]', r'"\1"', statement)
        
    return statement

def translate_types(statement, target):
    """Replaces data types with target equivalents."""
    for pattern, mapping in TYPE_MAP.items():
        if target in mapping:
            replacement = mapping[target]
            # Match word boundary
            statement = re.sub(pattern, replacement, statement, flags=re.IGNORECASE)
    return statement

def clean_engine_clauses(statement, target):
    """Removes MySQL-specific engine parameters like ENGINE=InnoDB when not targeting MySQL."""
    if target != 'mysql':
        statement = re.sub(r'\bENGINE\s*=\s*\w+\b', '', statement, flags=re.IGNORECASE)
        statement = re.sub(r'\bDEFAULT\s+CHARSET\s*=\s*\w+\b', '', statement, flags=re.IGNORECASE)
        statement = re.sub(r'\bCOLLATE\s*=\s*\w+\b', '', statement, flags=re.IGNORECASE)
        statement = re.sub(r'\bAUTO_INCREMENT\s*=\s*\d+\b', '', statement, flags=re.IGNORECASE)
    return statement

def clean_sqlite_autoincrement(statement, target):
    """SQLite autoincrement adjustments when converting to other dialects."""
    if target != 'sqlite':
        # Remove sqlite specific AUTOINCREMENT keyword
        statement = re.sub(r'\bAUTOINCREMENT\b', '', statement, flags=re.IGNORECASE)
    return statement

def translate_statement(statement, target):
    """Translates a single SQL statement to the target dialect."""
    orig_statement = statement
    
    # Skip statements that are comments or empty
    if not statement or statement.startswith('--'):
        return statement

    # Normalize whitespace
    statement = re.sub(r'\s+', ' ', statement).strip()

    # Identify create table queries
    is_create_table = re.match(r'^CREATE TABLE', statement, re.IGNORECASE)

    # 1. Translate Identifier syntax
    statement = translate_identifiers(statement, target)

    # 2. Translate Types
    statement = translate_types(statement, target)

    # 3. Clean Engine statements (ENGINE=InnoDB, CHARSET=utf8mb4, etc.)
    statement = clean_engine_clauses(statement, target)

    # 4. Handle sqlite-specific cleanup
    statement = clean_sqlite_autoincrement(statement, target)

    # 5. SQLite specific: INTEGER PRIMARY KEY AUTOINCREMENT rewrite
    if target == 'sqlite' and is_create_table:
        # PostgreSQL/MySQL structures like "id" INT AUTO_INCREMENT PRIMARY KEY or SERIAL PRIMARY KEY
        # must be rewritten to "id" INTEGER PRIMARY KEY AUTOINCREMENT for SQLite.
        # Check for PRIMARY KEY and AUTO_INCREMENT/SERIAL equivalents
        statement = re.sub(
            r'\b(?:INT|BIGINT|SERIAL|BIGSERIAL)\s+PRIMARY\s+KEY\s+(?:AUTOINCREMENT|AUTO_INCREMENT)\b',
            'INTEGER PRIMARY KEY AUTOINCREMENT',
            statement,
            flags=re.IGNORECASE
        )
        statement = re.sub(
            r'\b(?:INT|BIGINT|SERIAL|BIGSERIAL)\s+(?:AUTOINCREMENT|AUTO_INCREMENT)\s+PRIMARY\s+KEY\b',
            'INTEGER PRIMARY KEY AUTOINCREMENT',
            statement,
            flags=re.IGNORECASE
        )

    # Clean double spaces or trailing trailing space before semicolons
    statement = re.sub(r'\s+,', ',', statement)
    statement = re.sub(r'\s+', ' ', statement).strip()
    
    # Ensure statement ends with semicolon
    if not statement.endswith(';'):
        statement += ';'

    return statement

def translate_ddl(sql_script, target_dialect):
    """Processes DDL script and returns translated SQL string."""
    cleaned = clean_sql(sql_script)
    statements = split_statements(cleaned)
    translated_statements = []
    
    for stmt in statements:
        translated_stmt = translate_statement(stmt, target_dialect)
        if translated_stmt.strip() and translated_stmt.strip() != ';':
            translated_statements.append(translated_stmt)
            
    return "\n\n".join(translated_statements)

def main():
    parser = argparse.ArgumentParser(description="SQL DDL Dialect Translator")
    parser.add_argument('input', nargs='?', help='Path to the input SQL file (reads from stdin if omitted)')
    parser.add_argument('-o', '--output', help='Path to write the output SQL file')
    parser.add_argument('-t', '--target', choices=['postgresql', 'mysql', 'sqlite', 'sqlserver'], required=True,
                        help='Target database dialect')

    args = parser.parse_args()

    # Read SQL input
    if args.input:
        if not os.path.exists(args.input):
            print(f"Error: Input file '{args.input}' does not exist.")
            sys.exit(1)
        with open(args.input, 'r', encoding='utf-8', errors='ignore') as f:
            sql_input = f.read()
    else:
        if sys.stdin.isatty():
            parser.print_help()
            sys.exit(0)
        sql_input = sys.stdin.read()

    if not sql_input.strip():
        print("Error: Input SQL DDL is empty.")
        sys.exit(1)

    try:
        translated_output = translate_ddl(sql_input, args.target)
    except Exception as e:
        print(f"Translation Error: {e}")
        sys.exit(1)

    # Write output
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(translated_output + '\n')
            print(f"Successfully translated DDL to {args.target} and wrote to {args.output}")
        except Exception as e:
            print(f"Error writing output file: {e}")
            sys.exit(1)
    else:
        print(translated_output)

if __name__ == '__main__':
    main()
