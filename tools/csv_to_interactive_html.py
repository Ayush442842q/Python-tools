#!/usr/bin/env python3
"""
CSV to Interactive HTML Compiler

Converts a CSV file into a beautiful, self-contained interactive HTML page.
The generated HTML includes client-side searching/filtering, pagination,
column sorting, theme toggling (dark/light), and CSV/JSON export buttons.
No external Javascript/CSS frameworks or internet connection are required
for the output page to work, keeping it fully offline-friendly.

Usage:
    python tools/csv_to_interactive_html.py -i data.csv -o report.html [options]

Options:
    -i, --input PATH      Path to the source CSV file
    -o, --output PATH     Path to save the generated HTML file
    -t, --title STR       Title of the generated document
    --theme STR           Default theme ('dark' or 'light', default: 'dark')
    --page-size INT       Default rows per page (default: 10)
"""

import argparse
import csv
import json
import os
import sys

# ANSI Colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"


def supports_color() -> bool:
    """Returns True if the terminal supports ANSI colors."""
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform or is_a_tty


def color_text(text: str, color_code: str) -> str:
    """Colors text for terminal output if supported."""
    return f"{color_code}{text}{COLOR_RESET}" if supports_color() else text


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en" data-theme="{default_theme}">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-body: #f8fafc;
            --bg-card: #ffffff;
            --text-main: #0f172a;
            --text-muted: #64748b;
            --border-color: #e2e8f0;
            --primary: #6366f1;
            --primary-hover: #4f46e5;
            --primary-light: #e0e7ff;
            --shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
            --font-main: 'Outfit', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
        }}

        [data-theme="dark"] {{
            --bg-body: #0b0f19;
            --bg-card: #151c2c;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --border-color: #243049;
            --primary: #818cf8;
            --primary-hover: #6366f1;
            --primary-light: #1e293b;
            --shadow: 0 4px 20px 0 rgb(0 0 0 / 0.3);
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            background-color: var(--bg-body);
            color: var(--text-main);
            font-family: var(--font-main);
            line-height: 1.5;
            padding: 2rem;
            transition: background-color 0.3s, color 0.3s;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}

        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 2rem;
            flex-wrap: wrap;
            gap: 1rem;
        }}

        h1 {{
            font-size: 1.85rem;
            font-weight: 700;
            background: linear-gradient(135deg, var(--primary), #ec4899);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .theme-btn {{
            background: var(--bg-card);
            border: 1px solid var(--border-color);
            color: var(--text-main);
            padding: 0.5rem 1rem;
            border-radius: 8px;
            cursor: pointer;
            font-family: var(--font-main);
            font-weight: 500;
            box-shadow: var(--shadow);
            transition: all 0.2s;
        }}

        .theme-btn:hover {{
            border-color: var(--primary);
        }}

        .card {{
            background-color: var(--bg-card);
            border-radius: 12px;
            border: 1px solid var(--border-color);
            box-shadow: var(--shadow);
            padding: 1.5rem;
            margin-bottom: 2rem;
        }}

        .toolbar {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.5rem;
            flex-wrap: wrap;
            gap: 1rem;
        }}

        .search-box {{
            position: relative;
            flex-grow: 1;
            max-width: 400px;
        }}

        .search-box input {{
            width: 100%;
            padding: 0.65rem 1rem;
            padding-left: 2.5rem;
            border-radius: 8px;
            border: 1px solid var(--border-color);
            background-color: var(--bg-body);
            color: var(--text-main);
            font-family: var(--font-main);
            font-size: 0.95rem;
            outline: none;
            transition: border-color 0.2s;
        }}

        .search-box input:focus {{
            border-color: var(--primary);
        }}

        .search-box::before {{
            content: "🔍";
            position: absolute;
            left: 0.85rem;
            top: 50%;
            transform: translateY(-50%);
            font-size: 0.9rem;
            opacity: 0.6;
        }}

        .export-actions {{
            display: flex;
            gap: 0.5rem;
        }}

        .btn {{
            background-color: var(--primary);
            color: #ffffff;
            border: none;
            padding: 0.5rem 1.0rem;
            border-radius: 8px;
            cursor: pointer;
            font-family: var(--font-main);
            font-weight: 500;
            font-size: 0.9rem;
            transition: background-color 0.2s;
        }}

        .btn:hover {{
            background-color: var(--primary-hover);
        }}

        .btn-outline {{
            background-color: transparent;
            border: 1px solid var(--border-color);
            color: var(--text-main);
        }}

        .btn-outline:hover {{
            background-color: var(--primary-light);
            border-color: var(--primary);
        }}

        .table-responsive {{
            overflow-x: auto;
            border-radius: 8px;
            border: 1px solid var(--border-color);
            margin-bottom: 1.5rem;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            font-size: 0.95rem;
        }}

        th, td {{
            padding: 10px 14px;
            border-bottom: 1px solid var(--border-color);
        }}

        th {{
            background-color: var(--primary-light);
            color: var(--text-main);
            font-weight: 600;
            cursor: pointer;
            user-select: none;
            position: relative;
            white-space: nowrap;
        }}

        th::after {{
            content: " ↕";
            font-size: 0.75rem;
            opacity: 0.4;
        }}

        th.sort-asc::after {{
            content: " ↑";
            opacity: 1;
            color: var(--primary);
        }}

        th.sort-desc::after {{
            content: " ↓";
            opacity: 1;
            color: var(--primary);
        }}

        tr:last-child td {{
            border-bottom: none;
        }}

        tr:hover {{
            background-color: var(--primary-light);
        }}

        .footer-nav {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            flex-wrap: wrap;
            gap: 1rem;
        }}

        .pagination {{
            display: flex;
            gap: 0.25rem;
            align-items: center;
        }}

        .page-item {{
            min-width: 32px;
            height: 32px;
            display: flex;
            align-items: center;
            justify-content: center;
            border-radius: 6px;
            border: 1px solid var(--border-color);
            cursor: pointer;
            font-size: 0.9rem;
            user-select: none;
            transition: all 0.2s;
        }}

        .page-item:hover:not(.disabled) {{
            border-color: var(--primary);
            color: var(--primary);
        }}

        .page-item.active {{
            background-color: var(--primary);
            border-color: var(--primary);
            color: #ffffff;
        }}

        .page-item.disabled {{
            opacity: 0.4;
            cursor: not-allowed;
        }}

        .stats-text {{
            font-size: 0.9rem;
            color: var(--text-muted);
        }}

        .page-size-selector {{
            display: flex;
            align-items: center;
            gap: 0.5rem;
            font-size: 0.9rem;
            color: var(--text-muted);
        }}

        .page-size-selector select {{
            padding: 0.25rem 0.5rem;
            border-radius: 6px;
            border: 1px solid var(--border-color);
            background-color: var(--bg-card);
            color: var(--text-main);
            outline: none;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>{title}</h1>
            <button class="theme-btn" id="themeToggle">🌓 Toggle Theme</button>
        </header>

        <div class="card">
            <div class="toolbar">
                <div class="search-box">
                    <input type="text" id="searchInput" placeholder="Search table...">
                </div>
                <div class="export-actions">
                    <button class="btn btn-outline" id="exportCsv">Export CSV</button>
                    <button class="btn btn-outline" id="exportJson">Export JSON</button>
                </div>
            </div>

            <div class="table-responsive">
                <table id="dataTable">
                    <thead>
                        <tr id="headerRow"></tr>
                    </thead>
                    <tbody id="tableBody"></tbody>
                </table>
            </div>

            <div class="footer-nav">
                <div class="stats-text" id="statsText"></div>
                <div style="display: flex; gap: 1.5rem; align-items: center; flex-wrap: wrap;">
                    <div class="page-size-selector">
                        <span>Show</span>
                        <select id="pageSizeSelect">
                            <option value="5">5</option>
                            <option value="10">10</option>
                            <option value="25">25</option>
                            <option value="50">50</option>
                            <option value="100">100</option>
                        </select>
                        <span>rows</span>
                    </div>
                    <div class="pagination" id="pagination"></div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Data injected from Python compiler
        const tableHeaders = {headers_json};
        const tableData = {data_json};

        let filteredData = [...tableData];
        let currentPage = 1;
        let pageSize = {default_page_size};
        let sortColIndex = -1;
        let sortAsc = true;

        // Theme Toggle Handler
        const themeToggle = document.getElementById('themeToggle');
        themeToggle.addEventListener('click', () => {{
            const currentTheme = document.documentElement.getAttribute('data-theme');
            const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
            document.documentElement.setAttribute('data-theme', newTheme);
        }});

        // Render Headers
        const headerRow = document.getElementById('headerRow');
        tableHeaders.forEach((header, idx) => {{
            const th = document.createElement('th');
            th.textContent = header;
            th.addEventListener('click', () => handleSort(idx));
            headerRow.appendChild(th);
        }});

        // Sort Handler
        function handleSort(colIdx) {{
            const headers = headerRow.querySelectorAll('th');
            
            if (sortColIndex === colIdx) {{
                sortAsc = !sortAsc;
            }} else {{
                sortColIndex = colIdx;
                sortAsc = true;
            }}

            // Update header class
            headers.forEach((th, idx) => {{
                th.className = '';
                if (idx === colIdx) {{
                    th.className = sortAsc ? 'sort-asc' : 'sort-desc';
                }}
            }});

            filteredData.sort((a, b) => {{
                let valA = a[colIdx];
                let valB = b[colIdx];
                
                // Attempt numerical sorting if possible
                const numA = Number(valA);
                const numB = Number(valB);
                if (!isNaN(numA) && !isNaN(numB)) {{
                    valA = numA;
                    valB = numB;
                }} else {{
                    valA = valA.toString().toLowerCase();
                    valB = valB.toString().toLowerCase();
                }}

                if (valA < valB) return sortAsc ? -1 : 1;
                if (valA > valB) return sortAsc ? 1 : -1;
                return 0;
            }});

            currentPage = 1;
            renderTable();
        }}

        // Search/Filter Handler
        const searchInput = document.getElementById('searchInput');
        searchInput.addEventListener('input', (e) => {{
            const term = e.target.value.toLowerCase().strip();
            if (!term) {{
                filteredData = [...tableData];
            }} else {{
                filteredData = tableData.filter(row => {{
                    return row.some(cell => cell.toString().toLowerCase().includes(term));
                }});
            }}
            currentPage = 1;
            renderTable();
        }});

        // Page Size Selector Handler
        const pageSizeSelect = document.getElementById('pageSizeSelect');
        pageSizeSelect.value = pageSize;
        pageSizeSelect.addEventListener('change', (e) => {{
            pageSize = parseInt(e.target.value, 10);
            currentPage = 1;
            renderTable();
        }});

        // Render Table Body & Pagination
        const tableBody = document.getElementById('tableBody');
        const statsText = document.getElementById('statsText');
        const pagination = document.getElementById('pagination');

        function renderTable() {{
            tableBody.innerHTML = '';
            
            const totalRows = filteredData.length;
            const totalPages = Math.ceil(totalRows / pageSize) || 1;
            if (currentPage > totalPages) currentPage = totalPages;

            const startIdx = (currentPage - 1) * pageSize;
            const endIdx = Math.min(startIdx + pageSize, totalRows);
            const pageData = filteredData.slice(startIdx, endIdx);

            if (pageData.length === 0) {{
                const tr = document.createElement('tr');
                const td = document.createElement('td');
                td.colSpan = tableHeaders.length;
                td.style.textAlign = 'center';
                td.style.padding = '2rem';
                td.style.color = 'var(--text-muted)';
                td.textContent = 'No matching records found';
                tr.appendChild(td);
                tableBody.appendChild(tr);
            }} else {{
                pageData.forEach(row => {{
                    const tr = document.createElement('tr');
                    row.forEach(cell => {{
                        const td = document.createElement('td');
                        td.textContent = cell;
                        tr.appendChild(td);
                    }});
                    tableBody.appendChild(tr);
                }});
            }}

            // Render stats text
            if (totalRows === 0) {{
                statsText.textContent = 'Showing 0 records';
            }} else {{
                statsText.textContent = `Showing ${{startIdx + 1}} to ${{endIdx}} of ${{totalRows}} records` + 
                    (totalRows < tableData.length ? ` (filtered from ${{tableData.length}} total)` : '');
            }}

            // Render Pagination
            pagination.innerHTML = '';
            
            // Prev Button
            const prevBtn = document.createElement('div');
            prevBtn.className = `page-item ${{currentPage === 1 ? 'disabled' : ''}}`;
            prevBtn.textContent = '«';
            prevBtn.addEventListener('click', () => {{
                if (currentPage > 1) {{
                    currentPage--;
                    renderTable();
                }}
            }});
            pagination.appendChild(prevBtn);

            // Page numbers (smart pagination, showing max 5 items)
            let startPage = Math.max(1, currentPage - 2);
            let endPage = Math.min(totalPages, startPage + 4);
            if (endPage - startPage < 4) {{
                startPage = Math.max(1, endPage - 4);
            }}

            for (let i = startPage; i <= endPage; i++) {{
                const pageItem = document.createElement('div');
                pageItem.className = `page-item ${{currentPage === i ? 'active' : ''}}`;
                pageItem.textContent = i;
                pageItem.addEventListener('click', () => {{
                    currentPage = i;
                    renderTable();
                }});
                pagination.appendChild(pageItem);
            }}

            // Next Button
            const nextBtn = document.createElement('div');
            nextBtn.className = `page-item ${{currentPage === totalPages ? 'disabled' : ''}}`;
            nextBtn.textContent = '»';
            nextBtn.addEventListener('click', () => {{
                if (currentPage < totalPages) {{
                    currentPage++;
                    renderTable();
                }}
            }});
            pagination.appendChild(nextBtn);
        }}

        // Helper to stringify row to CSV
        function arrayToCsvRow(arr) {{
            return arr.map(val => {{
                const stringVal = val.toString().replace(/"/g, '""');
                return `"${{stringVal}}"`;
            }}).join(',');
        }}

        // Export CSV Handler
        document.getElementById('exportCsv').addEventListener('click', () => {{
            const csvContent = [
                arrayToCsvRow(tableHeaders),
                ...filteredData.map(row => arrayToCsvRow(row))
            ].join('\\n');

            const blob = new Blob([csvContent], {{ type: 'text/csv;charset=utf-8;' }});
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.setAttribute('href', url);
            link.setAttribute('download', '{filename_base}_exported.csv');
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }});

        // Export JSON Handler
        document.getElementById('exportJson').addEventListener('click', () => {{
            const structuredData = filteredData.map(row => {{
                const obj = {{}};
                tableHeaders.forEach((header, idx) => {{
                    obj[header] = row[idx];
                }});
                return obj;
            }});

            const jsonContent = JSON.stringify(structuredData, null, 2);
            const blob = new Blob([jsonContent], {{ type: 'application/json;charset=utf-8;' }});
            const url = URL.createObjectURL(blob);
            const link = document.createElement('a');
            link.setAttribute('href', url);
            link.setAttribute('download', '{filename_base}_exported.json');
            link.style.visibility = 'hidden';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }});

        // Initial Draw
        renderTable();
    </script>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(
        description="CSV to Interactive HTML compiler - Renders CSVs as highly interactive, self-contained dashboard tables."
    )
    parser.add_argument("-i", "--input", required=True, help="Path to input CSV file")
    parser.add_argument("-o", "--output", required=True, help="Path to output HTML file")
    parser.add_argument("-t", "--title", help="Optional title of the webpage (default: CSV name)")
    parser.add_argument("--theme", default="dark", choices=["dark", "light"], help="Default visual theme")
    parser.add_argument("--page-size", type=int, default=10, help="Default items per page")

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(color_text(f"Error: CSV file does not exist at '{args.input}'", COLOR_RED), file=sys.stderr)
        sys.exit(1)

    title = args.title or os.path.splitext(os.path.basename(args.input))[0].replace("_", " ").title()
    filename_base = os.path.splitext(os.path.basename(args.input))[0]

    print(color_text("Parsing CSV data...", COLOR_CYAN))
    
    headers = []
    rows = []
    
    try:
        with open(args.input, mode="r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            # Sniff headers
            headers = next(reader)
            for row in reader:
                # Pad/trim row elements to match header count
                if len(row) < len(headers):
                    row.extend([""] * (len(headers) - len(row)))
                elif len(row) > len(headers):
                    row = row[:len(headers)]
                rows.append(row)
    except Exception as e:
        print(color_text(f"Failed to read CSV: {str(e)}", COLOR_RED), file=sys.stderr)
        sys.exit(1)

    print(color_text(f"  Parsed {len(headers)} columns, {len(rows)} rows.", COLOR_BOLD))
    print(color_text("Compiling interactive dashboard HTML content...", COLOR_CYAN))

    # Serialize variables to inject in javascript
    headers_json = json.dumps(headers)
    data_json = json.dumps(rows)

    compiled_html = HTML_TEMPLATE.format(
        title=title,
        default_theme=args.theme,
        headers_json=headers_json,
        data_json=data_json,
        default_page_size=args.page_size,
        filename_base=filename_base
    )

    try:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(compiled_html)
        print(color_text(f"Success! Interactive HTML page saved to: {args.output}", COLOR_GREEN))
    except Exception as e:
        print(color_text(f"Failed to write output file: {str(e)}", COLOR_RED), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
