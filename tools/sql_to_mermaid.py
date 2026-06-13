#!/usr/bin/env python3
"""
SQL to Mermaid & Markdown Schema Documenter
Parses SQL DDL files (CREATE TABLE statements, primary keys, foreign keys)
and generates:
1. Mermaid.js Entity Relationship Diagram (ERD) syntax
2. Clean, detailed Markdown documentation of the database schema
"""

import argparse
import sys
import os
import re


class SQLParser:
    def __init__(self):
        self.tables = {}        # table_name -> {columns: [], pk: [], fk: []}
        self.relationships = [] # list of {child_table: x, child_cols: [], parent_table: y, parent_cols: []}

    def parse_sql(self, sql_text):
        """Simple regex-based parsing of CREATE TABLE and ALTER TABLE statements."""
        # 1. Clean comments
        sql_text = re.sub(r'--.*?\n', '\n', sql_text)
        sql_text = re.sub(r'/\*.*?\*/', '', sql_text, flags=re.DOTALL)
        
        # 2. Extract CREATE TABLE blocks
        # Finds: CREATE TABLE [IF NOT EXISTS] name ( content );
        create_table_matches = re.finditer(
            r'CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?([a-zA-Z0-9_`"\.]+)\s*\((.*?)\)\s*;', 
            sql_text, 
            re.IGNORECASE | re.DOTALL
        )
        
        for match in create_table_matches:
            raw_table_name = match.group(1).strip('`"[]')
            table_name = raw_table_name.split('.')[-1] # Remove schema if present
            content = match.group(2)
            
            self.tables[table_name] = {
                'columns': [],
                'pk': set(),
                'fk': {} # col -> (parent_table, parent_col)
            }
            
            # Split fields by comma, but ignore commas inside parentheses (e.g. DECIMAL(10,2))
            fields = []
            bracket_level = 0
            current_field = []
            for char in content:
                if char == '(':
                    bracket_level += 1
                elif char == ')':
                    bracket_level -= 1
                
                if char == ',' and bracket_level == 0:
                    fields.append("".join(current_field).strip())
                    current_field = []
                else:
                    current_field.append(char)
            if current_field:
                fields.append("".join(current_field).strip())
                
            for field in fields:
                if not field:
                    continue
                
                field_upper = field.upper()
                
                # Check inline/explicit constraints
                if field_upper.startswith('PRIMARY KEY'):
                    # PRIMARY KEY (col1, col2)
                    pk_cols = re.search(r'PRIMARY\s+KEY\s*\((.*?)\)', field, re.IGNORECASE)
                    if pk_cols:
                        cols = [c.strip('`"[] ') for c in pk_cols.group(1).split(',')]
                        self.tables[table_name]['pk'].update(cols)
                    continue
                    
                if field_upper.startswith('CONSTRAINT') and 'FOREIGN KEY' in field_upper:
                    # CONSTRAINT constraint_name FOREIGN KEY (col) REFERENCES parent(col)
                    fk_match = re.search(r'FOREIGN\s+KEY\s*\((.*?)\)\s*REFERENCES\s+([a-zA-Z0-9_`"\.]+)\s*\((.*?)\)', field, re.IGNORECASE)
                    if fk_match:
                        child_cols = [c.strip('`"[] ') for c in fk_match.group(1).split(',')]
                        parent_table = fk_match.group(2).strip('`"[]').split('.')[-1]
                        parent_cols = [c.strip('`"[] ') for c in fk_match.group(3).split(',')]
                        
                        for cc, pc in zip(child_cols, parent_cols):
                            self.tables[table_name]['fk'][cc] = (parent_table, pc)
                            self.relationships.append({
                                'child_table': table_name,
                                'child_col': cc,
                                'parent_table': parent_table,
                                'parent_col': pc
                            })
                    continue
                    
                if field_upper.startswith('FOREIGN KEY'):
                    # FOREIGN KEY (col) REFERENCES parent(col)
                    fk_match = re.search(r'FOREIGN\s+KEY\s*\((.*?)\)\s*REFERENCES\s+([a-zA-Z0-9_`"\.]+)\s*\((.*?)\)', field, re.IGNORECASE)
                    if fk_match:
                        child_cols = [c.strip('`"[] ') for c in fk_match.group(1).split(',')]
                        parent_table = fk_match.group(2).strip('`"[]').split('.')[-1]
                        parent_cols = [c.strip('`"[] ') for c in fk_match.group(3).split(',')]
                        
                        for cc, pc in zip(child_cols, parent_cols):
                            self.tables[table_name]['fk'][cc] = (parent_table, pc)
                            self.relationships.append({
                                'child_table': table_name,
                                'child_col': cc,
                                'parent_table': parent_table,
                                'parent_col': pc
                            })
                    continue

                if field_upper.startswith('KEY') or field_upper.startswith('UNIQUE') or field_upper.startswith('INDEX'):
                    # Ignore regular indices or unique indices for basic ERD
                    continue
                
                # It's a column definition
                # Format: name type [constraints...]
                parts = field.split(None, 2)
                if len(parts) >= 2:
                    col_name = parts[0].strip('`"[]')
                    col_type = parts[1].strip()
                    rest = parts[2].strip() if len(parts) > 2 else ""
                    rest_upper = rest.upper()
                    
                    is_pk = False
                    is_null = True
                    
                    if 'PRIMARY KEY' in rest_upper:
                        is_pk = True
                        self.tables[table_name]['pk'].add(col_name)
                        
                    if 'NOT NULL' in rest_upper:
                        is_null = False
                        
                    self.tables[table_name]['columns'].append({
                        'name': col_name,
                        'type': col_type,
                        'nullable': is_null,
                        'constraints': rest
                    })

        # 3. Extract ALTER TABLE constraints (specifically Foreign Keys additions)
        # ALTER TABLE child ADD CONSTRAINT cname FOREIGN KEY (ccol) REFERENCES parent(pcol);
        alter_matches = re.finditer(
            r'ALTER\s+TABLE\s+([a-zA-Z0-9_`"\.]+)\s+ADD\s+(?:CONSTRAINT\s+\S+\s+)?FOREIGN\s+KEY\s*\((.*?)\)\s*REFERENCES\s+([a-zA-Z0-9_`"\.]+)\s*\((.*?)\)\s*;',
            sql_text,
            re.IGNORECASE
        )
        for match in alter_matches:
            child_table = match.group(1).strip('`"[]').split('.')[-1]
            child_cols = [c.strip('`"[] ') for c in match.group(2).split(',')]
            parent_table = match.group(3).strip('`"[]').split('.')[-1]
            parent_cols = [c.strip('`"[] ') for c in match.group(4).split(',')]
            
            if child_table in self.tables:
                for cc, pc in zip(child_cols, parent_cols):
                    self.tables[child_table]['fk'][cc] = (parent_table, pc)
                    self.relationships.append({
                        'child_table': child_table,
                        'child_col': cc,
                        'parent_table': parent_table,
                        'parent_col': pc
                    })

    def generate_mermaid(self):
        """Generates Mermaid.js ERD syntax."""
        lines = ["erDiagram"]
        
        # Output relationships
        # Standard: parent_table ||--o{ child_table : "foreign_key"
        # We can simplify this to: Parent ||--o{ Child : references
        for rel in self.relationships:
            p_table = rel['parent_table']
            c_table = rel['child_table']
            # Using standard zero-to-many relationship
            lines.append(f"    {p_table} ||--o{{ {c_table} : \"{rel['child_col']} -> {rel['parent_col']}\"")
            
        # Output tables and columns
        for t_name, t_data in self.tables.items():
            lines.append(f"    {t_name} {{")
            for col in t_data['columns']:
                c_name = col['name']
                # Replace brackets or spaces in types for Mermaid compatibility
                c_type = col['type'].replace('(', '_').replace(')', '').replace(',', '_')
                
                # Check labels
                labels = []
                if c_name in t_data['pk']:
                    labels.append("PK")
                if c_name in t_data['fk']:
                    labels.append("FK")
                    
                label_str = " ".join(labels)
                lines.append(f"        {c_type} {c_name} {label_str}")
            lines.append("    }")
            
        return "\n".join(lines)

    def generate_markdown(self):
        """Generates structured Markdown documentation."""
        lines = ["# Database Schema Documentation\n"]
        
        # Table of contents
        lines.append("## Tables Summary\n")
        for t_name in sorted(self.tables.keys()):
            cols_count = len(self.tables[t_name]['columns'])
            lines.append(f"- [{t_name}](#{t_name.lower()}) ({cols_count} columns)")
        lines.append("\n---\n")
        
        # Table details
        for t_name in sorted(self.tables.keys()):
            t_data = self.tables[t_name]
            lines.append(f"### {t_name}")
            lines.append("\n**Columns:**\n")
            lines.append("| Name | Type | Nullable | Key | References | Description / Constraints |")
            lines.append("| --- | --- | --- | --- | --- | --- |")
            
            for col in t_data['columns']:
                c_name = col['name']
                c_type = col['type']
                nullable = "Yes" if col['nullable'] else "No"
                
                # Key classification
                key_type = ""
                is_pk = c_name in t_data['pk']
                is_fk = c_name in t_data['fk']
                if is_pk and is_fk:
                    key_type = "PK, FK"
                elif is_pk:
                    key_type = "PK"
                elif is_fk:
                    key_type = "FK"
                    
                # References
                ref = ""
                if is_fk:
                    p_table, p_col = t_data['fk'][c_name]
                    ref = f"[{p_table}.{p_col}](#{p_table.lower()})"
                    
                # Clean up constraints description
                constraints = col['constraints']
                # Strip out redundent primary key / not null info
                constraints = re.sub(r'PRIMARY\s+KEY', '', constraints, flags=re.IGNORECASE)
                constraints = re.sub(r'NOT\s+NULL', '', constraints, flags=re.IGNORECASE)
                constraints = re.sub(r'NULL', '', constraints, flags=re.IGNORECASE)
                constraints = constraints.strip(', ')
                
                lines.append(f"| `{c_name}` | `{c_type}` | {nullable} | **{key_type}** | {ref} | {constraints} |")
            lines.append("\n")
            
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="SQL to Mermaid & Markdown Schema Documenter."
    )
    parser.add_argument(
        'sql_file',
        help="Path to SQL DDL script file containing CREATE TABLE statements"
    )
    parser.add_argument(
        '--format', '-f',
        choices=['mermaid', 'markdown', 'both'],
        default='both',
        help="Output format: mermaid, markdown, or both (default: both)"
    )
    parser.add_argument(
        '--output-dir', '-o',
        help="Directory to save output files. If omitted, outputs are printed to stdout."
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.sql_file):
        print(f"Error: SQL file '{args.sql_file}' not found.", file=sys.stderr)
        return 1

    try:
        with open(args.sql_file, 'r', encoding='utf-8') as f:
            sql_content = f.read()
    except Exception as e:
        print(f"Error reading SQL file: {e}", file=sys.stderr)
        return 1

    parser_obj = SQLParser()
    parser_obj.parse_sql(sql_content)

    if not parser_obj.tables:
        print("Warning: No CREATE TABLE statements found or parsed.", file=sys.stderr)

    mermaid_out = parser_obj.generate_mermaid()
    markdown_out = parser_obj.generate_markdown()

    # Determine save path or print
    if args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)
        base_name = os.path.splitext(os.path.basename(args.sql_file))[0]
        
        if args.format in ('mermaid', 'both'):
            m_path = os.path.join(args.output_dir, f"{base_name}_schema.mmd")
            with open(m_path, 'w', encoding='utf-8') as f:
                f.write(mermaid_out)
            print(f"Mermaid ERD saved to '{m_path}'")
            
        if args.format in ('markdown', 'both'):
            md_path = os.path.join(args.output_dir, f"{base_name}_schema.md")
            with open(md_path, 'w', encoding='utf-8') as f:
                f.write(markdown_out)
            print(f"Markdown documentation saved to '{md_path}'")
    else:
        if args.format == 'mermaid':
            print(mermaid_out)
        elif args.format == 'markdown':
            print(markdown_out)
        else:
            print("=== MERMAID ERD ===")
            print(mermaid_out)
            print("\n=== MARKDOWN SCHEMA DOCUMENTATION ===")
            print(markdown_out)

    return 0


if __name__ == "__main__":
    sys.exit(main())
