#!/usr/bin/env python3
"""
SQL Query Lineage Extractor
Parses SQL queries to extract data lineage: source tables, target tables, and column references.
"""

import argparse
import os
import re
import sys

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"

# SQL Keywords to ignore when looking for columns/tables
SQL_KEYWORDS = {
    "select", "from", "where", "join", "on", "and", "or", "group", "by", "having", 
    "order", "limit", "offset", "insert", "into", "values", "update", "set", "delete",
    "create", "table", "view", "index", "as", "inner", "left", "right", "outer", "cross",
    "full", "natural", "using", "distinct", "union", "all", "intersect", "except", "case",
    "when", "then", "else", "end", "is", "null", "not", "in", "like", "exists", "between",
    "count", "sum", "avg", "min", "max", "coalesce", "cast", "convert", "date", "time",
    "timestamp", "with", "recursive", "window", "partition", "over", "rank", "row_number"
}

# Regex to strip single line (--) and block (/* */) comments
COMMENT_RE = re.compile(r"(--.*?\n)|(/\*.*?\*/)", re.DOTALL)

# Target tables patterns
INSERT_RE = re.compile(r"\binsert\s+into\s+([a-zA-Z0-9_\.\"`\[\]]+)", re.IGNORECASE)
UPDATE_RE = re.compile(r"\bupdate\s+([a-zA-Z0-9_\.\"`\[\]]+)", re.IGNORECASE)
CREATE_RE = re.compile(r"\bcreate\s+(?:temp\s+|temporary\s+)?table\s+(?:if\s+not\s+exists\s+)?([a-zA-Z0-9_\.\"`\[\]]+)", re.IGNORECASE)
DELETE_RE = re.compile(r"\bdelete\s+from\s+([a-zA-Z0-9_\.\"`\[\]]+)", re.IGNORECASE)

# Source tables patterns (followed by optional alias)
FROM_JOIN_RE = re.compile(
    r"\b(?:from|join)\s+([a-zA-Z0-9_\.\"`\[\]]+)(?:\s+(?:as\s+)?([a-zA-Z0-9_]+))?", 
    re.IGNORECASE
)

# Column reference pattern (matches table_alias.col_name or just col_name)
COL_REF_RE = re.compile(r"\b([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)\b")
PLAIN_WORD_RE = re.compile(r"\b([a-zA-Z0-9_]+)\b")

def clean_sql(sql):
    """Strip comments and normalize whitespace."""
    sql = COMMENT_RE.sub(" ", sql)
    return " ".join(sql.split())

def clean_name(name):
    """Strip quotes/brackets from table/column names."""
    if not name:
        return ""
    return name.strip().replace("`", "").replace('"', "").replace("[", "").replace("]", "")

def extract_lineage(sql_content):
    sql = clean_sql(sql_content)
    
    # 1. Extract Target Tables
    targets = set()
    for m in INSERT_RE.finditer(sql):
        targets.add(clean_name(m.group(1)))
    for m in UPDATE_RE.finditer(sql):
        targets.add(clean_name(m.group(1)))
    for m in CREATE_RE.finditer(sql):
        targets.add(clean_name(m.group(1)))
    for m in DELETE_RE.finditer(sql):
        targets.add(clean_name(m.group(1)))

    # Remove subquery names if they ended up here
    targets = {t for t in targets if t.lower() not in SQL_KEYWORDS}

    # 2. Extract Source Tables and Aliases
    sources = set()
    aliases = {} # alias -> table_name
    
    for m in FROM_JOIN_RE.finditer(sql):
        table = clean_name(m.group(1))
        alias = m.group(2)
        
        # Skip if table name is actually an SQL keyword or subquery close syntax
        if table.lower() in SQL_KEYWORDS or table.startswith("("):
            continue
            
        sources.add(table)
        if alias and alias.lower() not in SQL_KEYWORDS:
            aliases[alias] = table

    # Clean up sources
    sources = sources - targets
    sources = {s for s in sources if s.lower() not in SQL_KEYWORDS}

    # 3. Extract Column References
    columns_by_table = {s: set() for s in sources}
    columns_by_table["[Unassociated]"] = set()

    # Find prefixed columns: alias.column or table.column
    for m in COL_REF_RE.finditer(sql):
        prefix, col = m.groups()
        if prefix.lower() in SQL_KEYWORDS or col.lower() in SQL_KEYWORDS:
            continue
            
        # Resolve prefix
        resolved_table = aliases.get(prefix, prefix)
        if resolved_table in sources:
            columns_by_table[resolved_table].add(col)
        else:
            # Might be an unassociated or target table column
            columns_by_table["[Unassociated]"].add(f"{prefix}.{col}")

    # Find plain column names
    for m in PLAIN_WORD_RE.finditer(sql):
        word = m.group(1)
        if word.lower() in SQL_KEYWORDS or word.isdigit():
            continue
        # If it's not a known table/alias, it could be a column
        if word not in sources and word not in targets and word not in aliases:
            # Check if it was already added as prefixed
            already_prefixed = False
            for table_cols in columns_by_table.values():
                if word in table_cols:
                    already_prefixed = True
                    break
            if not already_prefixed:
                columns_by_table["[Unassociated]"].add(word)

    # Clean empty lists
    if not columns_by_table["[Unassociated]"]:
        del columns_by_table["[Unassociated]"]

    return {
        "targets": sorted(list(targets)),
        "sources": sorted(list(sources)),
        "columns": {k: sorted(list(v)) for k, v in columns_by_table.items() if v}
    }

def main():
    parser = argparse.ArgumentParser(
        description="Parse SQL query files or text to extract data lineage (sources, targets, and column usages)."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-f", "--file", help="Path to SQL file to scan")
    group.add_argument("-q", "--query", help="Raw SQL query string")

    args = parser.parse_args()

    if args.file:
        if not os.path.exists(args.file):
            print(f"{RED}Error: File '{args.file}' does not exist.{RESET}", file=sys.stderr)
            sys.exit(1)
        try:
            with open(args.file, "r", encoding="utf-8", errors="ignore") as f:
                sql_content = f.read()
        except Exception as e:
            print(f"{RED}Error reading file: {e}{RESET}", file=sys.stderr)
            sys.exit(1)
    else:
        sql_content = args.query

    lineage = extract_lineage(sql_content)

    print("\n" + "=" * 60)
    print(f"{BOLD}SQL DATA LINEAGE ANALYSIS{RESET}")
    print("=" * 60)

    # Print Targets
    print(f"\n{RED}{BOLD}Target Table(s) (Outputs):{RESET}")
    if lineage["targets"]:
        for t in lineage["targets"]:
            print(f"  {RED}■ {t}{RESET}")
    else:
        print("  (None detected - e.g. a pure SELECT query)")

    # Print Sources & Columns
    print(f"\n{GREEN}{BOLD}Source Table(s) (Inputs) & Column Usage:{RESET}")
    if lineage["sources"]:
        for s in lineage["sources"]:
            cols = lineage["columns"].get(s, [])
            cols_str = ", ".join(cols) if cols else "No specific columns mapped"
            print(f"  {GREEN}■ {s}{RESET}")
            print(f"    Columns: {BLUE}{cols_str}{RESET}")
    else:
        print("  (No source tables detected)")

    # Print Unassociated Columns
    if "[Unassociated]" in lineage["columns"]:
        unassociated = lineage["columns"]["[Unassociated]"]
        print(f"\n{YELLOW}{BOLD}Unassociated / General Column References:{RESET}")
        print(f"  Columns: {YELLOW}{', '.join(unassociated)}{RESET}")

    # Visual Flow Diagram
    print("\n" + "=" * 60)
    print(f"{BOLD}LINEAGE VISUALIZATION{RESET}")
    print("=" * 60)
    
    source_block = " + ".join([f"[{s}]" for s in lineage["sources"]]) if lineage["sources"] else "[Dual/None]"
    target_block = " + ".join([f"[{t}]" for t in lineage["targets"]]) if lineage["targets"] else "[Standard Output]"
    
    print(f"\n  {GREEN}{source_block}{RESET}  ===>  {RED}{target_block}{RESET}\n")
    print("=" * 60)

if __name__ == "__main__":
    main()
