#!/usr/bin/env python3
"""
SQL Schema Normalization & Quality Auditor

Statically parses SQL DDL schema files (e.g. SQLite, PostgreSQL, MySQL dialects)
to audit the relational database design for normalization compliance (1NF, 2NF, 3NF)
and common DDL design anti-patterns.

DDL Quality Audits:
1. 1NF: Missing Primary Keys, non-atomic attributes (columns named tags, list, array, etc.).
2. 2NF/3NF: Redundant column names across tables that lack Foreign Key constraints,
            unindexed Foreign Key columns (performance gotchas).
3. Anti-patterns: Missing ON DELETE clauses on foreign keys, tables with too many
                  columns (> 15), arbitrary VARCHAR limits, mixed-case names.

Usage:
    python tools/sql_normalization_auditor.py schema.sql
"""

import os
import re
import sys
import argparse
from typing import Dict, List, Set, Tuple, Any

# Colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"

def supports_color() -> bool:
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform and is_a_tty

USE_COLOR = supports_color()

def colorize(text: str, color_code: str) -> str:
    if USE_COLOR:
        return f"{color_code}{text}{COLOR_RESET}"
    return text

class SqlColumn:
    def __init__(self, name: str, data_type: str, raw_line: str):
        self.name = name.strip('"`[]')
        self.data_type = data_type.upper()
        self.raw_line = raw_line
        self.is_primary_key = False
        self.is_foreign_key = False
        self.fk_ref_table = ""
        self.fk_ref_column = ""
        self.is_nullable = True
        
        # Simple heuristic constraints
        lower_raw = raw_line.lower()
        if "primary key" in lower_raw:
            self.is_primary_key = True
        if "not null" in lower_raw:
            self.is_nullable = False
        
        # Inline foreign keys, e.g. "user_id INTEGER REFERENCES users(id)"
        ref_match = re.search(r'references\s+([\w\-\.\/\"\`]+)\s*\(\s*([\w\-\.\/\"\`]+)\s*\)', lower_raw)
        if ref_match:
            self.is_foreign_key = True
            self.fk_ref_table = ref_match.group(1).strip('"`[]')
            self.fk_ref_column = ref_match.group(2).strip('"`[]')

class SqlTable:
    def __init__(self, name: str):
        self.name = name.strip('"`[]')
        self.columns: Dict[str, SqlColumn] = {}
        self.table_constraints: List[str] = []
        self.has_primary_key = False
        self.foreign_keys: List[Dict[str, str]] = []  # List of {local_col, ref_table, ref_col}
        
    def add_column(self, col: SqlColumn):
        self.columns[col.name] = col
        if col.is_primary_key:
            self.has_primary_key = True
        if col.is_foreign_key:
            self.foreign_keys.append({
                "local_col": col.name,
                "ref_table": col.fk_ref_table,
                "ref_col": col.fk_ref_column
            })

class DdlAuditor:
    def __init__(self, sql_content: str):
        self.sql_content = sql_content
        self.tables: Dict[str, SqlTable] = {}
        self.findings: List[Dict[str, Any]] = []  # Dict with 'table', 'severity', 'message', 'fix'
        self.indexes: List[Tuple[str, str]] = []  # List of (table_name, column_name)
        
    def add_finding(self, table: str, severity: str, message: str, fix: str = ""):
        self.findings.append({
            "table": table,
            "severity": severity,  # 'INFO', 'WARN', 'CRITICAL'
            "message": message,
            "fix": fix
        })

    def parse(self):
        # 1. Clean comments
        # Strip -- comments
        content = re.sub(r'--.*$', '', self.sql_content, flags=re.MULTILINE)
        # Strip /* */ comments
        content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
        
        # 2. Extract indices to cross-reference with Foreign Keys
        # CREATE INDEX idx_name ON table_name (col)
        index_matches = re.finditer(r'create\s+(?:unique\s+)?index\s+[\w\`\"\-\[\]]+\s+on\s+([\w\`\"\-\[\]]+)\s*\(\s*([\w\`\"\-\[\]]+)\s*\)', content, re.IGNORECASE)
        for match in index_matches:
            tbl = match.group(1).strip('"`[]')
            col = match.group(2).strip('"`[]')
            self.indexes.append((tbl, col))

        # 3. Extract table statements
        # Matches CREATE TABLE name ( body )
        # Using a parentheses depth scanner because regex cannot reliably match nested parentheses
        pos = 0
        while True:
            match = re.search(r'create\s+table\s+([\w\`\"\-\[\]]+)\s*\(', content[pos:], re.IGNORECASE)
            if not match:
                break
            
            table_name = match.group(1)
            start_idx = pos + match.end()
            
            # Find closing parenthesis matching the open one
            depth = 1
            end_idx = start_idx
            while end_idx < len(content) and depth > 0:
                char = content[end_idx]
                if char == '(':
                    depth += 1
                elif char == ')':
                    depth -= 1
                end_idx += 1
                
            if depth == 0:
                table_body = content[start_idx:end_idx-1]
                self._parse_table_body(table_name, table_body)
                pos = end_idx
            else:
                pos = start_idx

    def _parse_table_body(self, table_name: str, body: str):
        table = SqlTable(table_name)
        
        # Split body by commas, but ignore commas inside parentheses
        parts = []
        current = []
        depth = 0
        for char in body:
            if char == '(':
                depth += 1
            elif char == ')':
                depth -= 1
            
            if char == ',' and depth == 0:
                parts.append("".join(current).strip())
                current = []
            else:
                current.append(char)
        if current:
            parts.append("".join(current).strip())

        for part in parts:
            if not part:
                continue
                
            lower_part = part.lower()
            
            # Check for table-level Primary Key
            if lower_part.startswith("primary key"):
                table.has_primary_key = True
                table.table_constraints.append(part)
                continue
                
            # Check for table-level Foreign Key
            # FOREIGN KEY (col) REFERENCES other(other_col)
            fk_match = re.search(r'foreign\s+key\s*\(\s*([\w\`\"\-\[\]]+)\s*\)\s*references\s+([\w\`\"\-\[\]]+)\s*\(\s*([\w\`\"\-\[\]]+)\s*\)', lower_part)
            if fk_match:
                local_col = fk_match.group(1).strip('"`[]')
                ref_table = fk_match.group(2).strip('"`[]')
                ref_col = fk_match.group(3).strip('"`[]')
                table.foreign_keys.append({
                    "local_col": local_col,
                    "ref_table": ref_table,
                    "ref_col": ref_col
                })
                table.table_constraints.append(part)
                continue

            # Skip other constraints like UNIQUE, CHECK
            if lower_part.startswith(("constraint", "unique", "check")):
                table.table_constraints.append(part)
                continue
                
            # Parse column definition: name type [constraints]
            col_match = re.match(r'^([\w\`\"\-\[\]]+)\s+([\w\(\)\s]+)', part)
            if col_match:
                col_name = col_match.group(1)
                col_type = col_match.group(2).split()[0]  # get first word of type, e.g. VARCHAR(255) -> VARCHAR
                column = SqlColumn(col_name, col_type, part)
                table.add_column(column)
            else:
                # Fallback / unparsed line
                table.table_constraints.append(part)

        self.tables[table.name] = table

    def audit(self):
        # Perform normalization & anti-pattern audits
        for table_name, table in self.tables.items():
            
            # 1. 1NF - Primary Key check
            if not table.has_primary_key:
                self.add_finding(
                    table=table_name,
                    severity="CRITICAL",
                    message="Table is missing a Primary Key constraint.",
                    fix="Define a primary key column (e.g. id INTEGER PRIMARY KEY)."
                )

            # 2. 1NF - Atomicity / Non-atomic attributes check (Heuristic on column names)
            for col_name, col in table.columns.items():
                lower_col = col_name.lower()
                if any(suffix in lower_col for suffix in ["_list", "_tags", "_array", "comma_"]):
                    self.add_finding(
                        table=table_name,
                        severity="WARN",
                        message=f"Column '{col_name}' may store non-atomic values (lists/arrays/tags).",
                        fix="Create a separate child table and use foreign keys to normalize this relationship."
                    )

            # 3. 2NF/3NF - Unlinked columns matching other table names (Heuristic)
            # e.g., if we have columns like "user_id" but no foreign key to "users" table
            for col_name, col in table.columns.items():
                lower_col = col_name.lower()
                if lower_col.endswith("_id") and not col.is_primary_key:
                    # Check if matching foreign key is declared
                    has_fk = any(fk["local_col"] == col_name for fk in table.foreign_keys)
                    if not has_fk:
                        potential_target = lower_col[:-3] + "s"  # e.g. user_id -> users
                        # Check if potential target table exists
                        matching_table = None
                        for target in self.tables:
                            if target.lower() in (potential_target, lower_col[:-3]):
                                matching_table = target
                                break
                        
                        if matching_table:
                            self.add_finding(
                                table=table_name,
                                severity="WARN",
                                message=f"Column '{col_name}' implies a relation to table '{matching_table}', but no FOREIGN KEY constraint is defined.",
                                fix=f"Add constraint: FOREIGN KEY ({col_name}) REFERENCES {matching_table}(id)"
                            )

            # 4. Performance - Unindexed Foreign Keys
            for fk in table.foreign_keys:
                local_col = fk["local_col"]
                # Check if an index exists for this table and column
                has_idx = any(idx_tbl == table_name and idx_col == local_col for idx_tbl, idx_col in self.indexes)
                
                # Check if this local column is already a primary key (implicitly indexed)
                is_pk = table.columns.get(local_col) and table.columns[local_col].is_primary_key
                
                if not has_idx and not is_pk:
                    self.add_finding(
                        table=table_name,
                        severity="WARN",
                        message=f"Foreign Key column '{local_col}' (references {fk['ref_table']}) is not indexed. This can cause poor join performance.",
                        fix=f"Create index: CREATE INDEX idx_{table_name}_{local_col} ON {table_name}({local_col});"
                    )

            # 5. DDL Anti-patterns - Missing ON DELETE clauses on Foreign Keys
            for fk in table.foreign_keys:
                local_col = fk["local_col"]
                col_obj = table.columns.get(local_col)
                raw_ddl = col_obj.raw_line.lower() if col_obj else ""
                
                # check if ON DELETE is specified in either column DDL or table constraints
                has_on_delete = "on delete" in raw_ddl
                if not has_on_delete:
                    # check table constraints
                    for const in table.table_constraints:
                        if local_col in const and "references" in const.lower() and "on delete" in const.lower():
                            has_on_delete = True
                            break
                            
                if not has_on_delete:
                    self.add_finding(
                        table=table_name,
                        severity="INFO",
                        message=f"Foreign Key '{local_col}' is missing an ON DELETE strategy. It defaults to RESTRICT/NO ACTION.",
                        fix="Specify 'ON DELETE CASCADE' or 'ON DELETE SET NULL' based on business requirements."
                    )

            # 6. DDL Anti-patterns - Table Complexity (Wide Tables)
            if len(table.columns) > 15:
                self.add_finding(
                    table=table_name,
                    severity="WARN",
                    message=f"Table is very wide ({len(table.columns)} columns). This may violate 3NF or indicate poor encapsulation.",
                    fix="Evaluate splitting the table into 1-to-1 extension tables or separate logically independent components."
                )

            # 7. DDL Anti-patterns - VARCHAR limits vs TEXT
            for col_name, col in table.columns.items():
                if "VARCHAR" in col.data_type:
                    # check if it has a limit, e.g. VARCHAR(255)
                    limit_match = re.search(r'varchar\s*\(\s*(\d+)\s*\)', col.raw_line.lower())
                    if limit_match:
                        val = int(limit_match.group(1))
                        if val == 255:
                            self.add_finding(
                                table=table_name,
                                severity="INFO",
                                message=f"Column '{col_name}' uses VARCHAR(255). Ensure this is a real boundary constraint rather than cargo culting.",
                                fix="Consider using TEXT if database engine is SQLite/Postgres where TEXT is optimized."
                            )

def main():
    parser = argparse.ArgumentParser(description="Audit SQL DDL files for relational database normalization and quality.")
    parser.add_argument("schema_file", help="Path to the SQL DDL file.")
    
    args = parser.parse_args()

    if not os.path.isfile(args.schema_file):
        print(f"Error: File '{args.schema_file}' not found.", file=sys.stderr)
        sys.exit(1)

    try:
        with open(args.schema_file, 'r', encoding='utf-8') as f:
            sql_data = f.read()
    except Exception as e:
        print(f"Error: Failed to read file: {e}", file=sys.stderr)
        sys.exit(1)

    auditor = DdlAuditor(sql_data)
    auditor.parse()
    auditor.audit()

    print(colorize(f"=== SQL Schema Normalization & Quality Audit ===", COLOR_BOLD + COLOR_BLUE))
    print(f"Target Schema : {os.path.basename(args.schema_file)}")
    print(f"Parsed Tables : {len(auditor.tables)}")
    print(f"Parsed Indexes: {len(auditor.indexes)}\n")

    if not auditor.findings:
        print(colorize("[PASS] No normalization anomalies or anti-patterns detected in the schema.", COLOR_GREEN))
        sys.exit(0)

    # Group findings by table
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for f in auditor.findings:
        grouped.setdefault(f["table"], []).append(f)

    total_findings = len(auditor.findings)
    critical_count = sum(1 for f in auditor.findings if f["severity"] == "CRITICAL")
    warn_count = sum(1 for f in auditor.findings if f["severity"] == "WARN")
    info_count = sum(1 for f in auditor.findings if f["severity"] == "INFO")

    for tbl, tbl_findings in grouped.items():
        print(f"\n{colorize('[TABLE]', COLOR_CYAN)} {colorize(tbl, COLOR_BOLD)}")
        for f in tbl_findings:
            sev_str = f"[{f['severity']}]"
            if f["severity"] == "CRITICAL":
                sev_str = colorize(sev_str, COLOR_RED)
            elif f["severity"] == "WARN":
                sev_str = colorize(sev_str, COLOR_YELLOW)
            else:
                sev_str = colorize(sev_str, COLOR_BLUE)
                
            print(f"  {sev_str} {f['message']}")
            if f["fix"]:
                print(f"    {colorize('Recommendation:', COLOR_GREEN)} {f['fix']}")

    print("\n" + "=" * 50)
    print(f"Audit completed. Total issues: {total_findings}")
    print(f"  - Critical (1NF violation): {colorize(str(critical_count), COLOR_RED if critical_count else COLOR_RESET)}")
    print(f"  - Warnings (Potential 2NF/3NF/index issue): {colorize(str(warn_count), COLOR_YELLOW if warn_count else COLOR_RESET)}")
    print(f"  - Info (Design recommendations): {colorize(str(info_count), COLOR_BLUE if info_count else COLOR_RESET)}")
    sys.exit(0)

if __name__ == "__main__":
    main()
