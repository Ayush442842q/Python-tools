#!/usr/bin/env python3
"""
SQLite Static Web Exporter - Converts any SQLite database into a single, standalone,
highly interactive HTML file containing searchable, sortable, and paginated tables.
Features:
- Zero external dependencies or network CDNs needed for the exported HTML (fully self-contained).
- Modern responsive glassmorphism dark-themed design with smooth gradients.
- Global search across all fields of the selected table.
- Column header sorting (alphabetical/numeric auto-detection).
- Interactive pagination (10, 25, 50, 100 entries per page).
- Data export button in-page (CSV/JSON download direct from browser).
"""

import os
import sys
import json
import sqlite3
import argparse
from pathlib import Path

# ANSI colors
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

def print_color(text, color):
    print(f"{color}{text}{RESET}")

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SQLite Database Viewer - {db_name}</title>
    <style>
        :root {{
            --bg-color: #0f172a;
            --card-bg: rgba(30, 41, 59, 0.7);
            --border-color: rgba(255, 255, 255, 0.1);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-color: #3b82f6;
            --accent-hover: #2563eb;
            --danger-color: #ef4444;
            --success-color: #22c55e;
            --font-family: 'Inter', system-ui, -apple-system, sans-serif;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            background-color: var(--bg-color);
            background-image: radial-gradient(circle at 10% 20%, rgba(59, 130, 246, 0.1) 0%, transparent 40%),
                              radial-gradient(circle at 90% 80%, rgba(147, 51, 234, 0.1) 0%, transparent 40%);
            color: var(--text-primary);
            font-family: var(--font-family);
            min-height: 100vh;
            display: flex;
            flex-direction: column;
            padding: 20px;
        }}

        header {{
            margin-bottom: 24px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 16px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}

        .title-container h1 {{
            font-size: 1.8rem;
            font-weight: 700;
            letter-spacing: -0.025em;
            background: linear-gradient(to right, #60a5fa, #c084fc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .title-container p {{
            color: var(--text-secondary);
            font-size: 0.9rem;
            margin-top: 4px;
        }}

        .layout {{
            display: grid;
            grid-template-columns: 260px 1fr;
            gap: 24px;
            flex-grow: 1;
        }}

        @media (max-width: 768px) {{
            .layout {{
                grid-template-columns: 1fr;
            }}
        }}

        .sidebar {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 16px;
            backdrop-filter: blur(10px);
            max-height: calc(100vh - 120px);
            overflow-y: auto;
        }}

        .sidebar h2 {{
            font-size: 0.75rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: var(--text-secondary);
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid var(--border-color);
        }}

        .table-list {{
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}

        .table-btn {{
            width: 100%;
            background: transparent;
            border: none;
            color: var(--text-secondary);
            padding: 10px 12px;
            text-align: left;
            border-radius: 8px;
            cursor: pointer;
            font-size: 0.9rem;
            font-weight: 500;
            transition: all 0.2s ease;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }}

        .table-btn:hover {{
            background: rgba(255, 255, 255, 0.05);
            color: var(--text-primary);
        }}

        .table-btn.active {{
            background: rgba(59, 130, 246, 0.15);
            color: #60a5fa;
            border-left: 3px solid var(--accent-color);
        }}

        .row-count {{
            font-size: 0.75rem;
            background: rgba(255, 255, 255, 0.1);
            color: var(--text-secondary);
            padding: 2px 6px;
            border-radius: 9999px;
        }}

        .main-content {{
            display: flex;
            flex-direction: column;
            gap: 20px;
        }}

        .card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 12px;
            padding: 20px;
            backdrop-filter: blur(10px);
        }}

        .toolbar {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 16px;
            flex-wrap: wrap;
        }}

        .search-box {{
            position: relative;
            flex-grow: 1;
            max-width: 400px;
        }}

        .search-input {{
            width: 100%;
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            padding: 10px 16px;
            border-radius: 8px;
            font-size: 0.9rem;
            outline: none;
            transition: border-color 0.2s ease;
        }}

        .search-input:focus {{
            border-color: var(--accent-color);
        }}

        .export-actions {{
            display: flex;
            gap: 8px;
        }}

        .btn {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            padding: 8px 16px;
            border-radius: 8px;
            font-size: 0.85rem;
            font-weight: 500;
            cursor: pointer;
            transition: all 0.2s ease;
        }}

        .btn:hover {{
            background: rgba(255, 255, 255, 0.1);
        }}

        .btn-primary {{
            background: var(--accent-color);
            border: none;
        }}

        .btn-primary:hover {{
            background: var(--accent-hover);
        }}

        .table-container {{
            overflow-x: auto;
            border-radius: 8px;
            border: 1px solid var(--border-color);
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 0.875rem;
        }}

        th {{
            background: rgba(15, 23, 42, 0.8);
            padding: 12px 16px;
            color: var(--text-secondary);
            font-weight: 600;
            border-bottom: 1px solid var(--border-color);
            cursor: pointer;
            user-select: none;
            position: relative;
        }}

        th:hover {{
            color: var(--text-primary);
            background: rgba(15, 23, 42, 0.9);
        }}

        th.sort-asc::after {{
            content: ' ▲';
            font-size: 0.65rem;
            color: var(--accent-color);
        }}

        th.sort-desc::after {{
            content: ' ▼';
            font-size: 0.65rem;
            color: var(--accent-color);
        }}

        td {{
            padding: 12px 16px;
            border-bottom: 1px solid var(--border-color);
            color: var(--text-primary);
            max-width: 300px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}

        tr:last-child td {{
            border-bottom: none;
        }}

        tr:hover td {{
            background: rgba(255, 255, 255, 0.02);
        }}

        .no-data {{
            text-align: center;
            padding: 40px;
            color: var(--text-secondary);
            font-style: italic;
        }}

        .pagination-container {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-top: 16px;
            gap: 16px;
            flex-wrap: wrap;
        }}

        .page-info {{
            font-size: 0.85rem;
            color: var(--text-secondary);
        }}

        .page-size-selector {{
            background: rgba(15, 23, 42, 0.6);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 0.85rem;
            outline: none;
        }}

        .pagination-btns {{
            display: flex;
            gap: 4px;
        }}

        .page-btn {{
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            padding: 6px 12px;
            border-radius: 6px;
            font-size: 0.85rem;
            cursor: pointer;
            transition: all 0.2s ease;
        }}

        .page-btn:hover {{
            background: rgba(255, 255, 255, 0.1);
        }}

        .page-btn.active {{
            background: var(--accent-color);
            border-color: var(--accent-color);
        }}

        .page-btn:disabled {{
            opacity: 0.4;
            cursor: not-allowed;
        }}

        footer {{
            margin-top: 40px;
            text-align: center;
            font-size: 0.8rem;
            color: var(--text-secondary);
            padding: 16px 0;
            border-top: 1px solid var(--border-color);
        }}
    </style>
</head>
<body>

    <header>
        <div class="title-container">
            <h1 id="dbName">SQLite Database: {db_name}</h1>
            <p id="tableCount">Loading tables...</p>
        </div>
        <div class="logo">
            <span style="font-weight: 800; color: #60a5fa;">SQLite</span> Viewer
        </div>
    </header>

    <div class="layout">
        <aside class="sidebar">
            <h2>Tables</h2>
            <ul class="table-list" id="tableList">
                <!-- Dynamically generated list -->
            </ul>
        </aside>

        <main class="main-content">
            <div class="card toolbar">
                <div class="search-box">
                    <input type="text" id="searchInput" class="search-input" placeholder="Search rows...">
                </div>
                <div class="export-actions">
                    <button class="btn" onclick="exportData('csv')">Export CSV</button>
                    <button class="btn" onclick="exportData('json')">Export JSON</button>
                </div>
            </div>

            <div class="card" style="padding: 0; overflow: hidden;">
                <div class="table-container">
                    <table id="dataTable">
                        <thead id="tableHead">
                            <!-- Columns headers -->
                        </thead>
                        <tbody id="tableBody">
                            <!-- Rows go here -->
                        </tbody>
                    </table>
                </div>
                <div class="no-data" id="noDataMessage" style="display: none;">
                    No matching records found.
                </div>
            </div>

            <div class="pagination-container">
                <div class="page-info" id="pageInfo">
                    Showing 0 to 0 of 0 entries
                </div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span class="page-info">Show</span>
                    <select class="page-size-selector" id="pageSize" onchange="changePageSize()">
                        <option value="10">10</option>
                        <option value="25" selected>25</option>
                        <option value="50">50</option>
                        <option value="100">100</option>
                    </select>
                    <span class="page-info">entries</span>
                </div>
                <div class="pagination-btns" id="paginationBtns">
                    <!-- Page buttons -->
                </div>
            </div>
        </main>
    </div>

    <footer>
        Standalone interactive HTML generated by SQLite Static Web Exporter
    </footer>

    <script>
        // Injected data
        const database = {db_data};

        let currentTable = null;
        let tableData = [];
        let filteredData = [];
        let sortColumn = null;
        let sortDirection = 'asc';
        let currentPage = 1;
        let pageSize = 25;

        // Initialization
        window.onload = function() {{
            const tableNames = Object.keys(database);
            document.getElementById('tableCount').innerText = `Contains ${{tableNames.length}} table(s)`;
            
            const listEl = document.getElementById('tableList');
            tableNames.forEach((name, index) => {{
                const li = document.createElement('li');
                const btn = document.createElement('button');
                btn.className = 'table-btn';
                if (index === 0) {{
                    btn.classList.add('active');
                    currentTable = name;
                }}
                btn.onclick = () => selectTable(name, btn);
                btn.innerHTML = `<span>${{name}}</span> <span class="row-count">${{database[name].rows.length}}</span>`;
                li.appendChild(btn);
                listEl.appendChild(li);
            }});

            if (currentTable) {{
                loadTable(currentTable);
            }}

            document.getElementById('searchInput').addEventListener('input', handleSearch);
        }};

        function selectTable(tableName, btnElement) {{
            // Update active states
            document.querySelectorAll('.table-btn').forEach(btn => btn.classList.remove('active'));
            btnElement.classList.add('active');
            
            currentTable = tableName;
            loadTable(tableName);
        }}

        function loadTable(tableName) {{
            tableData = database[tableName];
            filteredData = [...tableData.rows];
            sortColumn = null;
            sortDirection = 'asc';
            currentPage = 1;
            document.getElementById('searchInput').value = '';

            renderHeaders();
            renderRows();
        }}

        function renderHeaders() {{
            const headEl = document.getElementById('tableHead');
            headEl.innerHTML = '';
            const tr = document.createElement('tr');
            
            tableData.columns.forEach((col, idx) => {{
                const th = document.createElement('th');
                th.innerText = col;
                th.onclick = () => sortTable(idx);
                if (sortColumn === idx) {{
                    th.className = sortDirection === 'asc' ? 'sort-asc' : 'sort-desc';
                }}
                tr.appendChild(th);
            }});
            headEl.appendChild(tr);
        }}

        function renderRows() {{
            const bodyEl = document.getElementById('tableBody');
            const noDataEl = document.getElementById('noDataMessage');
            bodyEl.innerHTML = '';

            if (filteredData.length === 0) {{
                noDataEl.style.display = 'block';
                document.getElementById('pageInfo').innerText = 'Showing 0 to 0 of 0 entries';
                document.getElementById('paginationBtns').innerHTML = '';
                return;
            }}
            noDataEl.style.display = 'none';

            // Pagination indexes
            const startIdx = (currentPage - 1) * pageSize;
            const endIdx = Math.min(startIdx + pageSize, filteredData.length);
            const pageSlice = filteredData.slice(startIdx, endIdx);

            pageSlice.forEach(row => {{
                const tr = document.createElement('tr');
                row.forEach(val => {{
                    const td = document.createElement('td');
                    td.innerText = val !== null ? val.toString() : 'NULL';
                    if (val === null) td.style.color = 'var(--text-secondary)';
                    td.title = val !== null ? val.toString() : 'NULL';
                    tr.appendChild(td);
                }});
                bodyEl.appendChild(tr);
            }});

            document.getElementById('pageInfo').innerText = `Showing ${{startIdx + 1}} to ${{endIdx}} of ${{filteredData.length}} entries`;
            renderPaginationControls();
        }}

        function handleSearch() {{
            const query = this.value.toLowerCase().trim();
            if (!query) {{
                filteredData = [...tableData.rows];
            }} else {{
                filteredData = tableData.rows.filter(row => {{
                    return row.some(cell => cell !== null && cell.toString().toLowerCase().includes(query));
                }});
            }}
            currentPage = 1;
            renderRows();
        }}

        function sortTable(colIdx) {{
            if (sortColumn === colIdx) {{
                sortDirection = sortDirection === 'asc' ? 'desc' : 'asc';
            }} else {{
                sortColumn = colIdx;
                sortDirection = 'asc';
            }}

            filteredData.sort((a, b) => {{
                let valA = a[colIdx];
                let valB = b[colIdx];

                if (valA === null) valA = '';
                if (valB === null) valB = '';

                // Try numeric comparison
                const numA = Number(valA);
                const numB = Number(valB);
                if (!isNaN(numA) && !isNaN(numB) && valA !== '' && valB !== '') {{
                    return sortDirection === 'asc' ? numA - numB : numB - numA;
                }}

                // Default string comparison
                return sortDirection === 'asc' 
                    ? valA.toString().localeCompare(valB.toString())
                    : valB.toString().localeCompare(valA.toString());
            }});

            currentPage = 1;
            renderHeaders();
            renderRows();
        }}

        function changePageSize() {{
            pageSize = parseInt(document.getElementById('pageSize').value);
            currentPage = 1;
            renderRows();
        }}

        function renderPaginationControls() {{
            const btnsEl = document.getElementById('paginationBtns');
            btnsEl.innerHTML = '';

            const totalPages = Math.ceil(filteredData.length / pageSize);
            if (totalPages <= 1) return;

            // Previous button
            const prevBtn = document.createElement('button');
            prevBtn.className = 'page-btn';
            prevBtn.innerText = 'Prev';
            prevBtn.disabled = currentPage === 1;
            prevBtn.onclick = () => {{ currentPage--; renderRows(); }};
            btnsEl.appendChild(prevBtn);

            // Limited page button rendering (sliding window)
            const maxVisible = 5;
            let startPage = Math.max(1, currentPage - Math.floor(maxVisible / 2));
            let endPage = Math.min(totalPages, startPage + maxVisible - 1);
            
            if (endPage - startPage + 1 < maxVisible) {{
                startPage = Math.max(1, endPage - maxVisible + 1);
            }}

            for (let i = startPage; i <= endPage; i++) {{
                const btn = document.createElement('button');
                btn.className = `page-btn ${{i === currentPage ? 'active' : ''}}`;
                btn.innerText = i;
                btn.onclick = () => {{ currentPage = i; renderRows(); }};
                btnsEl.appendChild(btn);
            }}

            // Next button
            const nextBtn = document.createElement('button');
            nextBtn.className = 'page-btn';
            nextBtn.innerText = 'Next';
            nextBtn.disabled = currentPage === totalPages;
            nextBtn.onclick = () => {{ currentPage++; renderRows(); }};
            btnsEl.appendChild(nextBtn);
        }}

        function exportData(format) {{
            if (!currentTable || !tableData) return;

            let fileContent = '';
            let mimeType = 'text/plain';
            let extension = '';

            if (format === 'csv') {{
                extension = 'csv';
                mimeType = 'text/csv;charset=utf-8;';
                // Header
                fileContent += tableData.columns.map(col => `"${{col.replace(/"/g, '""')}}"`).join(',') + '\\n';
                // Rows
                filteredData.forEach(row => {{
                    fileContent += row.map(val => {{
                        if (val === null) return '""';
                        return `"${{val.toString().replace(/"/g, '""')}}"`;
                    }}).join(',') + '\\n';
                }});
            }} else if (format === 'json') {{
                extension = 'json';
                mimeType = 'application/json;charset=utf-8;';
                const formatted = filteredData.map(row => {{
                    const obj = {{}};
                    tableData.columns.forEach((col, idx) => {{
                        obj[col] = row[idx];
                    }});
                    return obj;
                }});
                fileContent = JSON.stringify(formatted, null, 2);
            }}

            const blob = new Blob([fileContent], {{ type: mimeType }});
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.setAttribute('href', url);
            link.setAttribute('download', `${{currentTable}}_export.${{extension}}`);
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }}
    </script>
</body>
</html>
"""

def export_db_to_html(db_path, output_html):
    db_file = Path(db_path).resolve()
    if not db_file.exists():
        print_color(f"Error: SQLite database file '{db_path}' does not exist.", RED)
        return False

    output_path = Path(output_html).resolve() if output_html else db_file.with_suffix('.html')

    print_color(f"Connecting to SQLite database: {db_file}", BLUE)
    try:
        conn = sqlite3.connect(f"file:{db_file}?mode=ro", uri=True)
        cursor = conn.cursor()
    except Exception as e:
        print_color(f"Connection error: {e}", RED)
        return False

    # Fetch tables
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [row[0] for row in cursor.fetchall()]
    except Exception as e:
        print_color(f"Error reading database metadata: {e}", RED)
        conn.close()
        return False

    if not tables:
        print_color("Warning: No user tables found in database. Exiting.", YELLOW)
        conn.close()
        return False

    print(f"Found {len(tables)} tables: {', '.join(tables)}")

    db_data = {}

    for table in tables:
        # Fetch columns
        try:
            cursor.execute(f"PRAGMA table_info(\"{table}\");")
            columns = [col[1] for col in cursor.fetchall()]
        except Exception as e:
            print_color(f"Error fetching schema for '{table}': {e}", RED)
            continue

        # Fetch row data
        try:
            cursor.execute(f"SELECT * FROM \"{table}\";")
            rows = cursor.fetchall()
            db_data[table] = {
                "columns": columns,
                "rows": rows
            }
            print(f" - Loaded table '{table}' ({len(rows)} rows, {len(columns)} columns)")
        except Exception as e:
            print_color(f"Error loading records for table '{table}': {e}", RED)
            continue

    conn.close()

    # Generate html
    json_data_str = json.dumps(db_data, ensure_ascii=False)
    html_content = HTML_TEMPLATE.format(
        db_name=db_file.name,
        db_data=json_data_str
    )

    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print_color(f"\nSuccess: Standalone HTML viewer generated at: {output_path}", GREEN)
    except Exception as e:
        print_color(f"Error writing output HTML: {e}", RED)
        return False

    return True

def main():
    parser = argparse.ArgumentParser(
        description="SQLite Static Web Exporter - Compile a SQLite database into a standalone interactive HTML viewer page."
    )
    parser.add_argument("db_path", help="Path to the source SQLite database file (.db, .sqlite, .sqlite3)")
    parser.add_argument("-o", "--output", help="Output path for the HTML file (default: same name as DB with .html extension)")

    args = parser.parse_args()

    # Windows ANSI support
    if sys.platform == "win32":
        os.system("")

    export_db_to_html(args.db_path, args.output)

if __name__ == "__main__":
    main()
