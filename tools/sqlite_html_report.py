#!/usr/bin/env python3
"""
SQLite Database to HTML Report Generator

A utility to connect to any SQLite database, analyze its schema, tables, indexes,
and sample rows, and generate a beautiful, responsive, dark-themed HTML report.

Usage:
    python tools/sqlite_html_report.py database.db -o report.html
"""

import os
import sys
import sqlite3
import argparse
from pathlib import Path

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SQLite Database Report: {db_name}</title>
    <style>
        :root {{
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --text-color: #e2e8f0;
            --text-muted: #94a3b8;
            --primary: #3b82f6;
            --primary-hover: #2563eb;
            --accent: #10b981;
            --border-color: #334155;
            --code-bg: #0f172a;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            line-height: 1.6;
            padding: 2rem;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        header {{
            margin-bottom: 2rem;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 1.5rem;
        }}

        h1 {{
            font-size: 2.5rem;
            color: #fff;
            margin-bottom: 0.5rem;
        }}

        .db-meta {{
            color: var(--text-muted);
            font-size: 0.95rem;
            display: flex;
            gap: 1.5rem;
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1.5rem;
            margin-bottom: 3rem;
        }}

        .stat-card {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            padding: 1.5rem;
            border-radius: 8px;
            text-align: center;
        }}

        .stat-val {{
            font-size: 2rem;
            font-weight: bold;
            color: var(--primary);
            margin-bottom: 0.5rem;
        }}

        .stat-label {{
            color: var(--text-muted);
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .section {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 2rem;
            margin-bottom: 2rem;
        }}

        h2 {{
            color: #fff;
            margin-bottom: 1.5rem;
            font-size: 1.5rem;
            border-left: 4px solid var(--primary);
            padding-left: 0.5rem;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 1.5rem;
            font-size: 0.9rem;
        }}

        th, td {{
            padding: 0.75rem 1rem;
            text-align: left;
            border-bottom: 1px solid var(--border-color);
        }}

        th {{
            background-color: rgba(255, 255, 255, 0.03);
            color: #fff;
            font-weight: 600;
        }}

        tr:hover td {{
            background-color: rgba(255, 255, 255, 0.01);
        }}

        code {{
            background-color: var(--code-bg);
            padding: 0.2rem 0.4rem;
            border-radius: 4px;
            font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
            font-size: 0.85rem;
            color: #ec4899;
        }}

        .sql-box {{
            background-color: var(--code-bg);
            border: 1px solid var(--border-color);
            border-radius: 6px;
            padding: 1rem;
            overflow-x: auto;
            margin-bottom: 1.5rem;
        }}

        .sql-box code {{
            color: var(--text-color);
            background: none;
            padding: 0;
        }}

        .badge {{
            display: inline-block;
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: 600;
            background-color: var(--border-color);
            color: var(--text-color);
        }}

        .badge-pk {{
            background-color: rgba(245, 158, 11, 0.2);
            color: #f59e0b;
            border: 1px solid rgba(245, 158, 11, 0.3);
        }}

        .badge-index {{
            background-color: rgba(16, 185, 129, 0.2);
            color: var(--accent);
            border: 1px solid rgba(16, 185, 129, 0.3);
        }}

        .table-toc {{
            list-style: none;
            display: flex;
            flex-wrap: wrap;
            gap: 0.75rem;
            margin-bottom: 2rem;
        }}

        .table-toc a {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            color: var(--text-color);
            text-decoration: none;
            padding: 0.5rem 1rem;
            border-radius: 6px;
            font-size: 0.9rem;
            transition: all 0.2s ease;
        }}

        .table-toc a:hover {{
            border-color: var(--primary);
            color: var(--primary);
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Database Report: {db_name}</h1>
            <div class="db-meta">
                <span><strong>File Path:</strong> {db_path}</span>
                <span><strong>File Size:</strong> {db_size_formatted}</span>
            </div>
        </header>

        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-val">{tables_count}</div>
                <div class="stat-label">Tables</div>
            </div>
            <div class="stat-card">
                <div class="stat-val">{views_count}</div>
                <div class="stat-label">Views</div>
            </div>
            <div class="stat-card">
                <div class="stat-val">{indexes_count}</div>
                <div class="stat-label">Indexes</div>
            </div>
            <div class="stat-card">
                <div class="stat-val">{total_rows_estimated}</div>
                <div class="stat-label">Estimated Total Rows</div>
            </div>
        </div>

        <h2>Database Tables</h2>
        <ul class="table-toc">
            {table_toc_links}
        </ul>

        {tables_detail_html}

    </div>
</body>
</html>
"""

def format_size(size_in_bytes):
    """Return file size in a human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.2f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.2f} TB"

def generate_report(db_path, output_report_path):
    path = Path(db_path)
    if not path.exists():
        print(f"Error: Database file '{db_path}' does not exist.")
        return False
        
    db_size = path.stat().st_size
    db_size_str = format_size(db_size)
    
    conn = sqlite3.connect(db_path)
    # Enable fetching dict-like records
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # 1. Fetch tables details
    cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = cursor.fetchall()
    
    # 2. Fetch views details
    cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='view';")
    views = cursor.fetchall()
    
    # 3. Fetch indexes details
    cursor.execute("SELECT name, tbl_name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%';")
    indexes = cursor.fetchall()
    
    tables_count = len(tables)
    views_count = len(views)
    indexes_count = len(indexes)
    
    table_toc_links = []
    tables_detail_html = []
    total_rows_est = 0
    
    for t in tables:
        table_name = t['name']
        create_sql = t['sql'] or ""
        
        # Link in Table TOC
        table_toc_links.append(f'<li><a href="#table_{table_name}">`{table_name}`</a></li>')
        
        # Fetch columns metadata
        cursor.execute(f"PRAGMA table_info(`{table_name}`);")
        cols = cursor.fetchall()
        
        # Fetch index list for this table
        cursor.execute(f"PRAGMA index_list(`{table_name}`);")
        tbl_indexes = cursor.fetchall()
        
        # Fetch actual row count
        try:
            cursor.execute(f"SELECT COUNT(*) FROM `{table_name}`;")
            row_count = cursor.fetchone()[0]
        except Exception:
            row_count = 0
        total_rows_est += row_count
        
        # Fetch sample rows (up to 10)
        try:
            cursor.execute(f"SELECT * FROM `{table_name}` LIMIT 10;")
            sample_rows = cursor.fetchall()
        except Exception as e:
            sample_rows = []
            
        # Build Table HTML
        table_html = []
        table_html.append(f'<div id="table_{table_name}" class="section">')
        table_html.append(f'  <h2>Table: `{table_name}` <span class="badge" style="background-color: var(--primary);">{row_count} rows</span></h2>')
        
        # Columns definition section
        table_html.append('  <h3>Schema Definition</h3>')
        table_html.append('  <table>')
        table_html.append('    <thead>')
        table_html.append('      <tr><th>CID</th><th>Column Name</th><th>Type</th><th>Not Null</th><th>Default Value</th><th>Primary Key</th></tr>')
        table_html.append('    </thead>')
        table_html.append('    <tbody>')
        for c in cols:
            pk_badge = '<span class="badge badge-pk">Primary Key</span>' if c['pk'] else '-'
            notnull_val = "Yes" if c['notnull'] else "No"
            default_val = c['dflt_value'] if c['dflt_value'] is not None else "-"
            table_html.append(f"      <tr><td>{c['cid']}</td><td><strong>{c['name']}</strong></td><td><code>{c['type']}</code></td><td>{notnull_val}</td><td>{default_val}</td><td>{pk_badge}</td></tr>")
        table_html.append('    </tbody>')
        table_html.append('  </table>')
        
        # Indexes section
        if tbl_indexes:
            table_html.append('  <h3>Indexes</h3>')
            table_html.append('  <table>')
            table_html.append('    <thead>')
            table_html.append('      <tr><th>Index Name</th><th>Unique</th><th>Origin</th><th>Partial</th></tr>')
            table_html.append('    </thead>')
            table_html.append('    <tbody>')
            for idx in tbl_indexes:
                uniq = "Yes" if idx['unique'] else "No"
                partial = "Yes" if idx['partial'] else "No"
                table_html.append(f"      <tr><td><span class=\"badge badge-index\">{idx['name']}</span></td><td>{uniq}</td><td>{idx['origin']}</td><td>{partial}</td></tr>")
            table_html.append('    </tbody>')
            table_html.append('  </table>')
            
        # DDL section
        if create_sql:
            table_html.append('  <h3>DDL Statement</h3>')
            table_html.append('  <div class="sql-box"><pre><code>' + create_sql + '</code></pre></div>')
            
        # Sample Data section
        table_html.append('  <h3>Sample Data (Top 10 rows)</h3>')
        if sample_rows:
            table_html.append('  <div style="overflow-x: auto;">')
            table_html.append('    <table>')
            table_html.append('      <thead>')
            table_html.append('        <tr>')
            for col in cols:
                table_html.append(f"<th>{col['name']}</th>")
            table_html.append('        </tr>')
            table_html.append('      </thead>')
            table_html.append('      <tbody>')
            for row in sample_rows:
                table_html.append('        <tr>')
                for col in cols:
                    val = row[col['name']]
                    val_str = str(val) if val is not None else "NULL"
                    table_html.append(f"<td>{val_str}</td>")
                table_html.append('        </tr>')
            table_html.append('      </tbody>')
            table_html.append('    </table>')
            table_html.append('  </div>')
        else:
            table_html.append('  <p style="color: var(--text-muted); font-style: italic;">No rows or unable to fetch sample data.</p>')
            
        table_html.append('</div>')
        tables_detail_html.append("\n".join(table_html))

    # Compile the final report
    html_content = HTML_TEMPLATE.format(
        db_name=path.name,
        db_path=str(path.resolve()),
        db_size_formatted=db_size_str,
        tables_count=tables_count,
        views_count=views_count,
        indexes_count=indexes_count,
        total_rows_estimated=total_rows_est,
        table_toc_links="\n".join(table_toc_links),
        tables_detail_html="\n".join(tables_detail_html)
    )
    
    conn.close()
    
    with open(output_report_path, "w", encoding="utf-8") as f:
        f.write(html_content)
        
    return True

def main():
    parser = argparse.ArgumentParser(description="SQLite database inspector and HTML report compiler")
    parser.add_argument("db_file", help="Path to SQLite database file")
    parser.add_argument("-o", "--output", help="Output HTML report path (defaults to <db_file>_report.html)")
    args = parser.parse_args()
    
    output_path = args.output
    if not output_path:
        db_name_stem = Path(args.db_file).stem
        output_path = f"{db_name_stem}_report.html"
        
    print(f"Analyzing database '{args.db_file}'...")
    if generate_report(args.db_file, output_path):
        print(f"✓ Beautiful HTML report generated successfully at '{output_path}'")
        return 0
    else:
        return 1

if __name__ == "__main__":
    sys.exit(main())
