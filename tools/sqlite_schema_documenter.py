#!/usr/bin/env python3
"""
SQLite Schema Documenter

A tool to read a SQLite database and generate markdown or interactive HTML 
documentation. It lists tables, columns, types, nullability, defaults, keys, 
indexes, triggers, views, and row count statistics.

Usage:
    python tools/sqlite_schema_documenter.py -d test.db -o schema.md
    python tools/sqlite_schema_documenter.py -d test.db -o schema.html
"""

import argparse
import os
import sqlite3
import sys
from typing import Dict, List, Any, Tuple

# ANSI Colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"

def supports_color() -> bool:
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform or is_a_tty

def color_text(text: str, color_code: str) -> str:
    return f"{color_code}{text}{COLOR_RESET}" if supports_color() else text

def get_db_stats(db_path: str) -> Tuple[int, str]:
    """Returns size of the database in bytes and human-readable format."""
    size_bytes = os.path.getsize(db_path)
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return size_bytes, f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return size_bytes, f"{size_bytes:.2f} TB"

def read_schema(db_path: str) -> Dict[str, Any]:
    """Reads schema information from the SQLite database."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    schema_info = {
        "tables": {},
        "views": {},
        "triggers": []
    }
    
    try:
        # Get list of all tables, views, and triggers
        cursor.execute("SELECT name, type, sql FROM sqlite_master WHERE name NOT LIKE 'sqlite_%'")
        master_items = cursor.fetchall()
        
        for name, item_type, sql_def in master_items:
            if item_type == 'table':
                # Get row count
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM `{name}`")
                    row_count = cursor.fetchone()[0]
                except sqlite3.Error:
                    row_count = 0
                
                # Get columns information
                cursor.execute(f"PRAGMA table_info(`{name}`)")
                columns = cursor.fetchall()
                # Pragma table_info columns: cid, name, type, notnull, dflt_value, pk
                
                column_list = []
                for cid, col_name, col_type, notnull, dflt_value, pk in columns:
                    column_list.append({
                        "name": col_name,
                        "type": col_type or "BLOB",
                        "nullable": notnull == 0,
                        "default": dflt_value,
                        "pk": pk > 0
                    })
                    
                # Get foreign keys information
                cursor.execute(f"PRAGMA foreign_key_list(`{name}`)")
                fkeys = cursor.fetchall()
                # Pragma foreign_key_list columns: id, seq, table, from, to, on_update, on_delete, match
                fk_list = []
                for _, _, to_table, from_col, to_col, _, _, _ in fkeys:
                    fk_list.append({
                        "from_col": from_col,
                        "to_table": to_table,
                        "to_col": to_col
                    })
                    
                # Get index list
                cursor.execute(f"PRAGMA index_list(`{name}`)")
                indexes = cursor.fetchall()
                # Pragma index_list columns: seq, name, unique, origin, partial
                idx_list = []
                for _, idx_name, unique, _, _ in indexes:
                    cursor.execute(f"PRAGMA index_info(`{idx_name}`)")
                    idx_cols = cursor.fetchall()
                    # Pragma index_info columns: seqno, cid, name
                    cols = [col[2] for col in idx_cols]
                    idx_list.append({
                        "name": idx_name,
                        "unique": unique == 1,
                        "columns": cols
                    })
                
                schema_info["tables"][name] = {
                    "row_count": row_count,
                    "columns": column_list,
                    "foreign_keys": fk_list,
                    "indexes": idx_list,
                    "sql": sql_def
                }
                
            elif item_type == 'view':
                # Get row count of view
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM `{name}`")
                    row_count = cursor.fetchone()[0]
                except sqlite3.Error:
                    row_count = 0
                    
                # Get columns for view
                cursor.execute(f"PRAGMA table_info(`{name}`)")
                columns = cursor.fetchall()
                column_list = []
                for _, col_name, col_type, _, _, _ in columns:
                    column_list.append({
                        "name": col_name,
                        "type": col_type or "ANY"
                    })
                    
                schema_info["views"][name] = {
                    "row_count": row_count,
                    "columns": column_list,
                    "sql": sql_def
                }
                
            elif item_type == 'trigger':
                schema_info["triggers"].append({
                    "name": name,
                    "sql": sql_def
                })
                
    finally:
        conn.close()
        
    return schema_info

def generate_markdown(db_name: str, db_size: str, schema: Dict[str, Any]) -> str:
    """Generates a Markdown document containing the schema info."""
    lines = []
    lines.append(f"# SQLite Database Schema: {db_name}")
    lines.append(f"- **Database File Size:** {db_size}")
    lines.append(f"- **Total Tables:** {len(schema['tables'])}")
    lines.append(f"- **Total Views:** {len(schema['views'])}")
    lines.append(f"- **Total Triggers:** {len(schema['triggers'])}")
    lines.append("\n---\n")
    
    # TOC
    lines.append("## Tables Summary")
    lines.append("| Table | Rows | Columns | Indexes | Foreign Keys |")
    lines.append("| :--- | :---: | :---: | :---: | :---: |")
    for name, data in sorted(schema["tables"].items()):
        lines.append(f"| [{name}](#table-{name.lower()}) | {data['row_count']} | {len(data['columns'])} | {len(data['indexes'])} | {len(data['foreign_keys'])} |")
    lines.append("\n---\n")
    
    # Tables details
    lines.append("## Table Schemas")
    for name, data in sorted(schema["tables"].items()):
        lines.append(f"### Table: {name}")
        lines.append(f"**Rows:** {data['row_count']}\n")
        
        # Columns Table
        lines.append("| Column | Type | Nullable | Default | Keys / Indexes |")
        lines.append("| :--- | :--- | :---: | :--- | :--- |")
        for col in data["columns"]:
            key_info = []
            if col["pk"]:
                key_info.append("🔑 PRIMARY KEY")
                
            # Check if this column is in foreign keys
            for fk in data["foreign_keys"]:
                if fk["from_col"] == col["name"]:
                    key_info.append(f"🔗 FK → {fk['to_table']}({fk['to_col']})")
                    
            # Check if column is in indexes
            for idx in data["indexes"]:
                if col["name"] in idx["columns"]:
                    idx_type = "UNIQUE " if idx["unique"] else ""
                    key_info.append(f"⚡ {idx_type}INDEX ({idx['name']})")
                    
            lines.append(f"| **{col['name']}** | `{col['type']}` | {'✅' if col['nullable'] else '❌'} | `{col['default'] if col['default'] is not None else 'NULL'}` | {', '.join(key_info)} |")
            
        if data["sql"]:
            lines.append("\n**SQL Definition:**")
            lines.append("```sql")
            lines.append(data["sql"].strip())
            lines.append("```")
        lines.append("\n---\n")
        
    # Views details
    if schema["views"]:
        lines.append("## Views")
        for name, data in sorted(schema["views"].items()):
            lines.append(f"### View: {name}")
            lines.append(f"**Estimated Rows:** {data['row_count']}\n")
            lines.append("| Column | Type |")
            lines.append("| :--- | :--- |")
            for col in data["columns"]:
                lines.append(f"| **{col['name']}** | `{col['type']}` |")
            lines.append("\n**SQL Definition:**")
            lines.append("```sql")
            lines.append(data["sql"].strip())
            lines.append("```")
            lines.append("\n---\n")
            
    # Triggers details
    if schema["triggers"]:
        lines.append("## Triggers")
        for trig in sorted(schema["triggers"], key=lambda x: x["name"]):
            lines.append(f"### Trigger: {trig['name']}")
            lines.append("```sql")
            lines.append(trig["sql"].strip())
            lines.append("```")
            lines.append("\n---\n")
            
    return "\n".join(lines)

def generate_html(db_name: str, db_size: str, schema: Dict[str, Any]) -> str:
    """Generates a responsive HTML page with style and search filter."""
    table_rows = ""
    for name, data in sorted(schema["tables"].items()):
        table_rows += f"""
        <tr>
            <td><a href="#table-{name}" class="text-info font-weight-bold">{name}</a></td>
            <td>{data['row_count']}</td>
            <td>{len(data['columns'])}</td>
            <td>{len(data['indexes'])}</td>
            <td>{len(data['foreign_keys'])}</td>
        </tr>
        """
        
    table_details = ""
    for name, data in sorted(schema["tables"].items()):
        col_rows = ""
        for col in data["columns"]:
            key_info = []
            if col["pk"]:
                key_info.append('<span class="badge badge-primary">🔑 PK</span>')
            for fk in data["foreign_keys"]:
                if fk["from_col"] == col["name"]:
                    key_info.append(f'<span class="badge badge-success">🔗 FK &rarr; {fk["to_table"]}({fk["to_col"]})</span>')
            for idx in data["indexes"]:
                if col["name"] in idx["columns"]:
                    badge_style = "badge-warning" if idx["unique"] else "badge-info"
                    idx_text = "UQ IDX" if idx["unique"] else "IDX"
                    key_info.append(f'<span class="badge {badge_style}">⚡ {idx_text} ({idx["name"]})</span>')
                    
            col_rows += f"""
            <tr>
                <td><strong>{col['name']}</strong></td>
                <td><code>{col['type']}</code></td>
                <td>{"✅" if col['nullable'] else "❌"}</td>
                <td><code>{col['default'] if col['default'] is not None else 'NULL'}</code></td>
                <td>{" ".join(key_info)}</td>
            </tr>
            """
            
        sql_block = f'<pre><code class="language-sql">{data["sql"].strip()}</code></pre>' if data["sql"] else ''
        table_details += f"""
        <div class="card mb-4" id="table-{name}">
            <div class="card-header bg-dark text-white d-flex justify-content-between align-items-center">
                <h4 class="m-0">{name}</h4>
                <span class="badge badge-light">{data['row_count']} rows</span>
            </div>
            <div class="card-body">
                <table class="table table-striped table-bordered">
                    <thead>
                        <tr>
                            <th>Column</th>
                            <th>Type</th>
                            <th>Nullable</th>
                            <th>Default</th>
                            <th>Keys / Constraints</th>
                        </tr>
                    </thead>
                    <tbody>
                        {col_rows}
                    </tbody>
                </table>
                {sql_block}
            </div>
        </div>
        """
        
    view_details = ""
    for name, data in sorted(schema["views"].items()):
        view_col_rows = ""
        for col in data["columns"]:
            view_col_rows += f"<tr><td><strong>{col['name']}</strong></td><td><code>{col['type']}</code></td></tr>"
        sql_block = f'<pre><code class="language-sql">{data["sql"].strip()}</code></pre>' if data["sql"] else ''
        view_details += f"""
        <div class="card mb-4" id="view-{name}">
            <div class="card-header bg-secondary text-white d-flex justify-content-between align-items-center">
                <h4 class="m-0">View: {name}</h4>
                <span class="badge badge-light">{data['row_count']} rows</span>
            </div>
            <div class="card-body">
                <table class="table table-striped table-bordered">
                    <thead><tr><th>Column</th><th>Type</th></tr></thead>
                    <tbody>{view_col_rows}</tbody>
                </table>
                {sql_block}
            </div>
        </div>
        """
        
    trigger_details = ""
    for trig in sorted(schema["triggers"], key=lambda x: x["name"]):
        trigger_details += f"""
        <div class="card mb-4" id="trigger-{trig['name']}">
            <div class="card-header bg-info text-white">
                <h4 class="m-0">Trigger: {trig['name']}</h4>
            </div>
            <div class="card-body">
                <pre><code class="language-sql">{trig['sql'].strip()}</code></pre>
            </div>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Schema Documentation - {db_name}</title>
    <link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/10.7.2/styles/vs2015.min.css">
    <style>
        body {{ background-color: #f8f9fa; padding: 20px; }}
        pre {{ background-color: #1e1e1e; padding: 15px; border-radius: 5px; }}
        .badge {{ margin-right: 5px; }}
    </style>
</head>
<body>
    <div class="container-fluid">
        <div class="jumbotron bg-dark text-white py-4">
            <h1 class="display-4">SQLite Database Schema</h1>
            <p class="lead">File: {db_name} | Size: {db_size}</p>
            <hr class="my-2 bg-light">
            <div class="row">
                <div class="col-md-3"><strong>Tables:</strong> {len(schema['tables'])}</div>
                <div class="col-md-3"><strong>Views:</strong> {len(schema['views'])}</div>
                <div class="col-md-3"><strong>Triggers:</strong> {len(schema['triggers'])}</div>
            </div>
        </div>

        <div class="row">
            <div class="col-md-3 mb-4">
                <div class="card sticky-top" style="top: 20px;">
                    <div class="card-header bg-primary text-white font-weight-bold">Database Index</div>
                    <div class="list-group list-group-flush" style="max-height: 70vh; overflow-y: auto;">
                        <a href="#tables-summary" class="list-group-item list-group-item-action font-weight-bold">Tables Summary</a>
                        {"".join(f'<a href="#table-{name}" class="list-group-item list-group-item-action pl-4">{name}</a>' for name in sorted(schema['tables']))}
                        {f'<a href="#views-header" class="list-group-item list-group-item-action font-weight-bold">Views</a>' if schema['views'] else ''}
                        {"".join(f'<a href="#view-{name}" class="list-group-item list-group-item-action pl-4">{name}</a>' for name in sorted(schema['views']))}
                        {f'<a href="#triggers-header" class="list-group-item list-group-item-action font-weight-bold">Triggers</a>' if schema['triggers'] else ''}
                        {"".join(f'<a href="#trigger-{trig["name"]}" class="list-group-item list-group-item-action pl-4">{trig["name"]}</a>' for trig in sorted(schema['triggers'], key=lambda x: x['name']))}
                    </div>
                </div>
            </div>

            <div class="col-md-9">
                <div class="card mb-4" id="tables-summary">
                    <div class="card-header bg-primary text-white font-weight-bold">Tables Summary</div>
                    <div class="card-body">
                        <table class="table table-hover">
                            <thead>
                                <tr>
                                    <th>Table Name</th>
                                    <th>Rows</th>
                                    <th>Columns</th>
                                    <th>Indexes</th>
                                    <th>Foreign Keys</th>
                                </tr>
                            </thead>
                            <tbody>
                                {table_rows}
                            </tbody>
                        </table>
                    </div>
                </div>

                <h2 class="mb-4">Tables Details</h2>
                {table_details}

                {f'<h2 id="views-header" class="mb-4">Views Details</h2>{view_details}' if schema['views'] else ''}
                {f'<h2 id="triggers-header" class="mb-4">Triggers Details</h2>{trigger_details}' if schema['triggers'] else ''}
            </div>
        </div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/10.7.2/highlight.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/highlight.js/10.7.2/languages/sql.min.js"></script>
    <script>hljs.highlightAll();</script>
</body>
</html>
"""
    return html

def main() -> int:
    parser = argparse.ArgumentParser(description="Generate schema documentation for a SQLite database.")
    parser.add_argument("-d", "--database", required=True, help="Path to the SQLite database file")
    parser.add_argument("-o", "--output", help="Output file path (.md for Markdown, .html for HTML; default: prints Markdown to stdout)")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.database):
        print(color_text(f"Error: Database file '{args.database}' not found.", COLOR_RED), file=sys.stderr)
        return 1
        
    db_name = os.path.basename(args.database)
    try:
        _, db_size = get_db_stats(args.database)
        schema = read_schema(args.database)
    except sqlite3.DatabaseError as e:
        print(color_text(f"Error: Specified file '{args.database}' is not a valid SQLite database or is encrypted: {e}", COLOR_RED), file=sys.stderr)
        return 1
    except Exception as e:
        print(color_text(f"Error reading schema: {e}", COLOR_RED), file=sys.stderr)
        return 1
        
    # Determine format
    if args.output:
        if args.output.endswith(".html"):
            content = generate_html(db_name, db_size, schema)
        else:
            content = generate_markdown(db_name, db_size, schema)
            
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(content)
            print(color_text(f"[+] Successfully generated documentation in {args.output}", COLOR_GREEN))
        except Exception as e:
            print(color_text(f"Error writing output file: {e}", COLOR_RED), file=sys.stderr)
            return 1
    else:
        # Print Markdown to console
        print(generate_markdown(db_name, db_size, schema))
        print(color_text("\n[*] Tip: Use '-o <filename>.html' to generate an interactive HTML schema documentation page.", COLOR_CYAN))
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
