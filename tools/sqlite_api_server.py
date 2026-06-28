#!/usr/bin/env python3
"""
SQLite REST API Server & Web Dashboard
Exposes a CRUD REST API and a responsive dark-themed web interface for any SQLite database.
Requires zero external dependencies (uses standard library only: sqlite3, http.server, json, etc.).
"""

import argparse
import http.server
import json
import os
import sqlite3
import sys
import urllib.parse
from typing import Dict, List, Any, Tuple, Optional

# Sample Database setup in case no DB exists
DEFAULT_DB = "sample_api_data.db"

def create_sample_db(db_path: str):
    """Creates a sample database with tables and mock data if it doesn't exist."""
    print(f"[*] Creating sample database at {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Create tables
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        completed INTEGER DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT NOT NULL UNIQUE,
        email TEXT NOT NULL,
        role TEXT DEFAULT 'user'
    )
    """)
    
    # Insert mock data if empty
    cursor.execute("SELECT COUNT(*) FROM tasks")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO tasks (title, description, completed) VALUES (?, ?, ?)",
            [
                ("Learn Python", "Build some cool scripts and utilities", 1),
                ("Deploy SQLite API Server", "Run this script on a test database", 0),
                ("Write clean code", "Write Python code with type hints and docstrings", 0),
            ]
        )
    
    cursor.execute("SELECT COUNT(*) FROM users")
    if cursor.fetchone()[0] == 0:
        cursor.executemany(
            "INSERT INTO users (username, email, role) VALUES (?, ?, ?)",
            [
                ("admin", "admin@example.com", "administrator"),
                ("johndoe", "john@example.com", "user"),
                ("janedoe", "jane@example.com", "user"),
            ]
        )
        
    conn.commit()
    conn.close()


class DatabaseManager:
    """Manages SQLite connections, schema reflections, and queries."""
    def __init__(self, db_path: str):
        self.db_path = db_path
        
    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_tables(self) -> List[str]:
        """Returns a list of all tables in the database."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")
        tables = [row['name'] for row in cursor.fetchall()]
        conn.close()
        return tables

    def get_table_schema(self, table: str) -> List[Dict[str, Any]]:
        """Returns details about table columns."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(f"PRAGMA table_info({table})")
            columns = []
            for row in cursor.fetchall():
                columns.append({
                    "name": row["name"],
                    "type": row["type"],
                    "notnull": bool(row["notnull"]),
                    "dflt_value": row["dflt_value"],
                    "pk": bool(row["pk"])
                })
            return columns
        except sqlite3.OperationalError:
            return []
        finally:
            conn.close()

    def get_primary_key(self, table: str) -> str:
        """Returns the primary key column name, falling back to 'rowid' if none exists."""
        schema = self.get_table_schema(table)
        for col in schema:
            if col["pk"]:
                return col["name"]
        return "rowid"

    def query_rows(self, table: str, filters: Dict[str, Any], sort_col: Optional[str] = None, 
                   sort_order: str = "ASC", limit: Optional[int] = None, offset: Optional[int] = None) -> Tuple[List[Dict[str, Any]], int]:
        """Queries rows in a table with filtering, sorting, and pagination. Returns (rows, total_count)."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # Build query
        where_clauses = []
        params = []
        
        # Simple exact filters, avoiding column injection by matching against known schema
        schema_cols = {col["name"] for col in self.get_table_schema(table)}
        for k, v in filters.items():
            if k in schema_cols:
                where_clauses.append(f"{k} = ?")
                params.append(v)
        
        where_str = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
        
        # Get total count first
        count_sql = f"SELECT COUNT(*) as count FROM {table} {where_str}"
        cursor.execute(count_sql, params)
        total_count = cursor.fetchone()["count"]
        
        # Build select SQL
        sql = f"SELECT *, {self.get_primary_key(table)} as _rowid FROM {table} {where_str}"
        
        if sort_col and sort_col in schema_cols:
            sql += f" ORDER BY {sort_col} {sort_order.upper()}"
            
        if limit is not None:
            sql += f" LIMIT {int(limit)}"
            if offset is not None:
                sql += f" OFFSET {int(offset)}"
                
        cursor.execute(sql, params)
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows, total_count

    def get_row(self, table: str, pk_val: Any) -> Optional[Dict[str, Any]]:
        """Fetch a single row by primary key or rowid."""
        conn = self._get_connection()
        cursor = conn.cursor()
        pk = self.get_primary_key(table)
        
        sql = f"SELECT *, {pk} as _rowid FROM {table} WHERE {pk} = ?"
        cursor.execute(sql, (pk_val,))
        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def insert_row(self, table: str, data: Dict[str, Any]) -> Any:
        """Insert a row and return the inserted primary key / rowid."""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        schema_cols = {col["name"] for col in self.get_table_schema(table)}
        # Filter input data to match schema
        insert_data = {k: v for k, v in data.items() if k in schema_cols}
        
        cols = ", ".join(insert_data.keys())
        placeholders = ", ".join(["?"] * len(insert_data))
        sql = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
        
        cursor.execute(sql, list(insert_data.values()))
        last_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return last_id

    def update_row(self, table: str, pk_val: Any, data: Dict[str, Any]) -> bool:
        """Update an existing row by primary key."""
        conn = self._get_connection()
        cursor = conn.cursor()
        pk = self.get_primary_key(table)
        
        schema_cols = {col["name"] for col in self.get_table_schema(table) if col["name"] != pk}
        update_data = {k: v for k, v in data.items() if k in schema_cols}
        
        if not update_data:
            conn.close()
            return False
            
        set_clause = ", ".join([f"{k} = ?" for k in update_data.keys()])
        sql = f"UPDATE {table} SET {set_clause} WHERE {pk} = ?"
        
        params = list(update_data.values()) + [pk_val]
        cursor.execute(sql, params)
        changes = conn.total_changes
        conn.commit()
        conn.close()
        return changes > 0

    def delete_row(self, table: str, pk_val: Any) -> bool:
        """Delete a row by primary key."""
        conn = self._get_connection()
        cursor = conn.cursor()
        pk = self.get_primary_key(table)
        
        sql = f"DELETE FROM {table} WHERE {pk} = ?"
        cursor.execute(sql, (pk_val,))
        changes = conn.total_changes
        conn.commit()
        conn.close()
        return changes > 0

    def execute_raw(self, sql: str, params: List[Any] = None) -> List[Dict[str, Any]]:
        """Executes raw SQL query (READ-only safety check suggested for public, but this is a local utility)."""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(sql, params or [])
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows


class SQLiteAPIRequestHandler(http.server.BaseHTTPRequestHandler):
    """Processes REST API and Dashboard HTTP requests."""
    db_manager: DatabaseManager = None

    def log_message(self, format_str, *args):
        # Override to suppress default stdout pollution, but print errors
        pass

    def send_json(self, data: Any, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode('utf-8'))

    def do_OPTIONS(self):
        """Handle CORS pre-flight."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path.strip('/')
        query_params = urllib.parse.parse_qs(parsed_url.query)
        
        # Route dashboard index
        if path == "" or path == "index.html":
            self.serve_dashboard()
            return
            
        # Route API queries
        if path.startswith("api/"):
            parts = path.split('/')
            
            # GET /api/tables
            if len(parts) == 2 and parts[1] == "tables":
                tables = self.db_manager.get_tables()
                self.send_json({"tables": tables})
                return
                
            # GET /api/execute (raw query)
            if len(parts) == 2 and parts[1] == "execute":
                sql = query_params.get("sql", [""])[0]
                if not sql:
                    self.send_json({"error": "Missing 'sql' query parameter"}, 400)
                    return
                try:
                    # Basic read-only safety check (can be bypassed, but warns user)
                    lower_sql = sql.strip().lower()
                    if not (lower_sql.startswith("select") or lower_sql.startswith("pragma") or lower_sql.startswith("explain")):
                        self.send_json({"error": "Only SELECT, PRAGMA, or EXPLAIN queries allowed via raw execution for safety"}, 403)
                        return
                    results = self.db_manager.execute_raw(sql)
                    self.send_json(results)
                except Exception as e:
                    self.send_json({"error": str(e)}, 500)
                return
                
            # GET /api/<table>/schema
            if len(parts) == 3 and parts[2] == "schema":
                table = parts[1]
                schema = self.db_manager.get_table_schema(table)
                if not schema:
                    self.send_json({"error": f"Table '{table}' not found"}, 404)
                    return
                self.send_json({
                    "table": table,
                    "primary_key": self.db_manager.get_primary_key(table),
                    "columns": schema
                })
                return
                
            # GET /api/<table> or GET /api/<table>/<id>
            if len(parts) >= 2:
                table = parts[1]
                if table not in self.db_manager.get_tables():
                    self.send_json({"error": f"Table '{table}' not found"}, 404)
                    return
                    
                # GET /api/<table>/<id>
                if len(parts) == 3:
                    pk_val = parts[2]
                    row = self.db_manager.get_row(table, pk_val)
                    if row:
                        self.send_json(row)
                    else:
                        self.send_json({"error": f"Record with ID '{pk_val}' not found"}, 404)
                    return
                    
                # GET /api/<table>
                if len(parts) == 2:
                    filters = {k: v[0] for k, v in query_params.items() if not k.startswith('_')}
                    sort_col = query_params.get("_sort", [None])[0]
                    sort_order = query_params.get("_order", ["ASC"])[0]
                    limit = query_params.get("_limit", [None])[0]
                    page = query_params.get("_page", [None])[0]
                    offset = query_params.get("_offset", [None])[0]
                    
                    if limit:
                        limit = int(limit)
                        if page:
                            offset = (int(page) - 1) * limit
                        elif offset:
                            offset = int(offset)
                            
                    try:
                        rows, total = self.db_manager.query_rows(
                            table, filters, sort_col, sort_order, limit, offset
                        )
                        self.send_json({
                            "data": rows,
                            "pagination": {
                                "total": total,
                                "limit": limit,
                                "offset": offset,
                                "page": int(page) if page else None
                            }
                        })
                    except Exception as e:
                        self.send_json({"error": str(e)}, 500)
                    return
                    
        self.send_json({"error": "Not Found"}, 404)

    def do_POST(self):
        path = self.path.strip('/')
        if not path.startswith("api/"):
            self.send_json({"error": "Not Found"}, 404)
            return
            
        parts = path.split('/')
        table = parts[1]
        
        if table not in self.db_manager.get_tables():
            self.send_json({"error": f"Table '{table}' not found"}, 404)
            return
            
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(post_data) if post_data else {}
            
            inserted_id = self.db_manager.insert_row(table, data)
            self.send_json({
                "success": True,
                "message": "Record inserted successfully",
                "id": inserted_id
            }, 201)
        except Exception as e:
            self.send_json({"error": str(e)}, 400)

    def do_PUT(self):
        path = self.path.strip('/')
        if not path.startswith("api/"):
            self.send_json({"error": "Not Found"}, 404)
            return
            
        parts = path.split('/')
        if len(parts) != 3:
            self.send_json({"error": "Invalid endpoint format. Expected /api/<table>/<id>"}, 400)
            return
            
        table, pk_val = parts[1], parts[2]
        if table not in self.db_manager.get_tables():
            self.send_json({"error": f"Table '{table}' not found"}, 404)
            return
            
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            data = json.loads(post_data) if post_data else {}
            
            success = self.db_manager.update_row(table, pk_val, data)
            if success:
                self.send_json({"success": True, "message": "Record updated successfully"})
            else:
                self.send_json({"error": f"Record with ID '{pk_val}' not found or no changes made"}, 404)
        except Exception as e:
            self.send_json({"error": str(e)}, 400)

    def do_DELETE(self):
        path = self.path.strip('/')
        if not path.startswith("api/"):
            self.send_json({"error": "Not Found"}, 404)
            return
            
        parts = path.split('/')
        if len(parts) != 3:
            self.send_json({"error": "Invalid endpoint format. Expected /api/<table>/<id>"}, 400)
            return
            
        table, pk_val = parts[1], parts[2]
        if table not in self.db_manager.get_tables():
            self.send_json({"error": f"Table '{table}' not found"}, 404)
            return
            
        try:
            success = self.db_manager.delete_row(table, pk_val)
            if success:
                self.send_json({"success": True, "message": "Record deleted successfully"})
            else:
                self.send_json({"error": f"Record with ID '{pk_val}' not found"}, 404)
        except Exception as e:
            self.send_json({"error": str(e)}, 400)

    def serve_dashboard(self):
        """Serves the Single Page Web Dashboard for browsing the database."""
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        
        db_name = os.path.basename(self.db_manager.db_path)
        
        html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SQLite REST API & Web Console - {db_name}</title>
    <style>
        :root {{
            --bg-color: #0f172a;
            --panel-bg: #1e293b;
            --text-color: #e2e8f0;
            --text-muted: #94a3b8;
            --accent: #38bdf8;
            --accent-hover: #0ea5e9;
            --border: #334155;
            --success: #10b981;
            --danger: #ef4444;
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
            line-height: 1.5;
            display: flex;
            height: 100vh;
            overflow: hidden;
        }}
        
        /* Sidebar Styles */
        aside {{
            width: 280px;
            background-color: var(--panel-bg);
            border-right: 1px solid var(--border);
            display: flex;
            flex-direction: column;
            flex-shrink: 0;
        }}
        .brand {{
            padding: 20px;
            border-bottom: 1px solid var(--border);
            font-weight: bold;
            font-size: 1.1rem;
            color: var(--accent);
            display: flex;
            flex-direction: column;
        }}
        .brand span {{
            font-size: 0.8rem;
            color: var(--text-muted);
            margin-top: 4px;
        }}
        .table-list {{
            list-style: none;
            overflow-y: auto;
            flex-grow: 1;
            padding: 10px 0;
        }}
        .table-item {{
            padding: 12px 20px;
            cursor: pointer;
            display: flex;
            align-items: center;
            color: var(--text-color);
            text-decoration: none;
            transition: background 0.2s;
            font-size: 0.95rem;
        }}
        .table-item:hover, .table-item.active {{
            background-color: var(--border);
            border-left: 4px solid var(--accent);
        }}
        .sidebar-footer {{
            padding: 15px 20px;
            border-top: 1px solid var(--border);
            font-size: 0.8rem;
            color: var(--text-muted);
        }}
        
        /* Main Workspace Styles */
        main {{
            flex-grow: 1;
            display: flex;
            flex-direction: column;
            overflow: hidden;
        }}
        header {{
            padding: 20px;
            border-bottom: 1px solid var(--border);
            background-color: var(--panel-bg);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        h1 {{
            font-size: 1.3rem;
            font-weight: 600;
        }}
        .badge {{
            background-color: var(--border);
            padding: 4px 10px;
            border-radius: 4px;
            font-size: 0.75rem;
            color: var(--accent);
            font-family: monospace;
        }}
        
        /* Content Area */
        .workspace-content {{
            padding: 20px;
            flex-grow: 1;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 20px;
        }}
        .card {{
            background-color: var(--panel-bg);
            border: 1px solid var(--border);
            border-radius: 8px;
            padding: 20px;
        }}
        .card-title {{
            font-size: 1rem;
            font-weight: bold;
            margin-bottom: 15px;
            color: var(--accent);
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        /* Query Builder Console */
        .query-console {{
            display: flex;
            gap: 10px;
        }}
        textarea {{
            flex-grow: 1;
            background-color: var(--bg-color);
            color: var(--text-color);
            border: 1px solid var(--border);
            border-radius: 6px;
            padding: 10px;
            font-family: monospace;
            font-size: 0.9rem;
            resize: vertical;
            min-height: 80px;
        }}
        button {{
            background-color: var(--accent);
            color: #000;
            border: none;
            border-radius: 6px;
            padding: 10px 20px;
            font-weight: bold;
            cursor: pointer;
            transition: background 0.2s;
            align-self: flex-end;
        }}
        button:hover {{
            background-color: var(--accent-hover);
        }}
        
        /* Table / Details styling */
        .table-responsive {{
            overflow-x: auto;
            border-radius: 6px;
            border: 1px solid var(--border);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
            text-align: left;
        }}
        th, td {{
            padding: 12px 15px;
            border-bottom: 1px solid var(--border);
        }}
        th {{
            background-color: var(--border);
            color: var(--text-color);
            font-weight: 600;
        }}
        tr:hover {{
            background-color: rgba(255, 255, 255, 0.02);
        }}
        
        /* JSON response viewer */
        pre {{
            background-color: var(--bg-color);
            border: 1px solid var(--border);
            padding: 15px;
            border-radius: 6px;
            overflow-x: auto;
            font-family: monospace;
            font-size: 0.85rem;
            max-height: 400px;
        }}
        
        /* Tabs */
        .tabs {{
            display: flex;
            border-bottom: 1px solid var(--border);
            margin-bottom: 15px;
        }}
        .tab {{
            padding: 10px 20px;
            cursor: pointer;
            border-bottom: 2px solid transparent;
            color: var(--text-muted);
        }}
        .tab.active {{
            color: var(--accent);
            border-bottom-color: var(--accent);
            font-weight: bold;
        }}
        .tab-content {{
            display: none;
        }}
        .tab-content.active {{
            display: block;
        }}
    </style>
</head>
<body>

    <aside>
        <div class="brand">
            SQLite REST API
            <span>Database: {db_name}</span>
        </div>
        <ul class="table-list" id="tablesList">
            <!-- Dynamically populated -->
        </ul>
        <div class="sidebar-footer">
            Zero-dependency Server
        </div>
    </aside>

    <main>
        <header>
            <h1 id="mainTitle">SQLite Dashboard</h1>
            <div id="apiEndpoints" style="display: flex; gap: 8px;">
                <!-- Dynamically populated API routes -->
            </div>
        </header>

        <div class="workspace-content">
            <!-- Raw Query Console Card -->
            <div class="card">
                <div class="card-title">SQL Query Console</div>
                <div class="query-console">
                    <textarea id="sqlQuery" placeholder="SELECT * FROM tasks LIMIT 10;"></textarea>
                    <button id="runQueryBtn">Run Query</button>
                </div>
            </div>

            <!-- Main view card -->
            <div class="card" id="tableViewCard" style="display: none;">
                <div class="tabs">
                    <div class="tab active" onclick="switchTab('dataTab')">Browse Data</div>
                    <div class="tab" onclick="switchTab('schemaTab')">Schema Info</div>
                    <div class="tab" onclick="switchTab('apiTab')">REST API Routes</div>
                </div>

                <div id="dataTab" class="tab-content active">
                    <div class="table-responsive">
                        <table id="dataTable">
                            <!-- Table rows -->
                        </table>
                    </div>
                </div>

                <div id="schemaTab" class="tab-content">
                    <div class="table-responsive">
                        <table id="schemaTable">
                            <thead>
                                <tr>
                                    <th>Column</th>
                                    <th>Type</th>
                                    <th>Not Null</th>
                                    <th>Default Value</th>
                                    <th>Primary Key</th>
                                </tr>
                            </thead>
                            <tbody id="schemaTableBody">
                                <!-- Schema fields -->
                            </tbody>
                        </table>
                    </div>
                </div>

                <div id="apiTab" class="tab-content">
                    <h3>Available Endpoints for this Table:</h3>
                    <div style="margin-top: 15px; display: flex; flex-direction: column; gap: 10px;">
                        <div>
                            <span class="badge" style="background-color: #10b981; color: #fff;">GET</span> 
                            <code>/api/<span class="tbl-name"></span></code> - Fetch rows (supports sorting, pagination, filtering)
                        </div>
                        <div>
                            <span class="badge" style="background-color: #10b981; color: #fff;">GET</span> 
                            <code>/api/<span class="tbl-name"></span>/&lt;id&gt;</code> - Retrieve single record by ID
                        </div>
                        <div>
                            <span class="badge" style="background-color: #f59e0b; color: #fff;">POST</span> 
                            <code>/api/<span class="tbl-name"></span></code> - Insert new row (JSON body)
                        </div>
                        <div>
                            <span class="badge" style="background-color: #3b82f6; color: #fff;">PUT</span> 
                            <code>/api/<span class="tbl-name"></span>/&lt;id&gt;</code> - Update existing row (JSON body)
                        </div>
                        <div>
                            <span class="badge" style="background-color: #ef4444; color: #fff;">DELETE</span> 
                            <code>/api/<span class="tbl-name"></span>/&lt;id&gt;</code> - Delete record by ID
                        </div>
                    </div>
                </div>
            </div>

            <!-- Query results card -->
            <div class="card" id="resultsCard" style="display: none;">
                <div class="card-title" id="resultsTitle">Query Results</div>
                <div id="resultsContent">
                    <!-- JSON or table representation -->
                </div>
            </div>
        </div>
    </main>

    <script>
        let currentTable = '';
        
        // Fetch list of tables on load
        async function fetchTables() {
            try {
                const response = await fetch('/api/tables');
                const data = await response.json();
                const list = document.getElementById('tablesList');
                list.innerHTML = '';
                
                data.tables.forEach(table => {
                    const li = document.createElement('li');
                    li.className = 'table-item';
                    li.innerText = table;
                    li.onclick = () => selectTable(table);
                    list.appendChild(li);
                });
                
                // Select first table if available
                if (data.tables.length > 0) {
                    selectTable(data.tables[0]);
                }
            } catch (err) {
                console.error('Error fetching tables:', err);
            }
        }

        async function selectTable(tableName) {
            currentTable = tableName;
            
            // Highlight sidebar item
            document.querySelectorAll('.table-item').forEach(item => {
                if (item.innerText === tableName) {
                    item.classList.add('active');
                } else {
                    item.classList.remove('active');
                }
            });
            
            document.getElementById('mainTitle').innerText = `Table: ${tableName}`;
            document.querySelectorAll('.tbl-name').forEach(el => el.innerText = tableName);
            
            // Set endpoints info in header
            document.getElementById('apiEndpoints').innerHTML = `
                <a href="/api/${tableName}" target="_blank" class="badge">GET JSON</a>
                <a href="/api/${tableName}/schema" target="_blank" class="badge">SCHEMA</a>
            `;
            
            // Load tables views
            document.getElementById('tableViewCard').style.display = 'block';
            switchTab('dataTab');
            
            await Promise.all([
                fetchTableData(tableName),
                fetchTableSchema(tableName)
            ]);
        }

        async function fetchTableData(tableName) {
            try {
                const response = await fetch(`/api/${tableName}?_limit=100`);
                const res = await response.json();
                const table = document.getElementById('dataTable');
                table.innerHTML = '';
                
                if (res.data.length === 0) {
                    table.innerHTML = '<tr><td style="color: var(--text-muted); text-align: center; padding: 20px;">No records found</td></tr>';
                    return;
                }
                
                // Headers
                const headers = Object.keys(res.data[0]).filter(k => k !== '_rowid');
                const thead = document.createElement('thead');
                const headerRow = document.createElement('tr');
                headers.forEach(h => {
                    const th = document.createElement('th');
                    th.innerText = h;
                    headerRow.appendChild(th);
                });
                thead.appendChild(headerRow);
                table.appendChild(thead);
                
                // Rows
                const tbody = document.createElement('tbody');
                res.data.forEach(row => {
                    const tr = document.createElement('tr');
                    headers.forEach(h => {
                        const td = document.createElement('td');
                        td.innerText = row[h] !== null ? row[h] : 'NULL';
                        if (row[h] === null) td.style.color = 'var(--text-muted)';
                        tr.appendChild(td);
                    });
                    tbody.appendChild(tr);
                });
                table.appendChild(tbody);
            } catch (err) {
                console.error('Error fetching table data:', err);
            }
        }

        async function fetchTableSchema(tableName) {
            try {
                const response = await fetch(`/api/${tableName}/schema`);
                const data = await response.json();
                const body = document.getElementById('schemaTableBody');
                body.innerHTML = '';
                
                data.columns.forEach(col => {
                    const tr = document.createElement('tr');
                    tr.innerHTML = `
                        <td style="font-family: monospace; font-weight: bold;">${col.name}</td>
                        <td style="color: var(--accent); font-family: monospace;">${col.type}</td>
                        <td>${col.notnull ? 'Yes' : 'No'}</td>
                        <td style="font-family: monospace;">${col.dflt_value !== null ? col.dflt_value : 'NULL'}</td>
                        <td style="font-weight: bold; color: ${col.pk ? 'var(--success)' : 'inherit'}">${col.pk ? 'Yes' : 'No'}</td>
                    `;
                    body.appendChild(tr);
                });
            } catch (err) {
                console.error('Error fetching table schema:', err);
            }
        }

        function switchTab(tabId) {
            document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
            
            // Find tab header by onclick event containing tabId
            const tabs = Array.from(document.querySelectorAll('.tab'));
            const targetTab = tabs.find(t => t.getAttribute('onclick').includes(tabId));
            if (targetTab) targetTab.classList.add('active');
            
            document.getElementById(tabId).classList.add('active');
        }

        // Run custom SQL query
        document.getElementById('runQueryBtn').onclick = async () => {
            const sql = document.getElementById('sqlQuery').value.trim();
            if (!sql) return;
            
            const resultsCard = document.getElementById('resultsCard');
            const resultsContent = document.getElementById('resultsContent');
            
            resultsCard.style.display = 'block';
            resultsContent.innerHTML = 'Running...';
            
            try {
                const response = await fetch(`/api/execute?sql=${encodeURIComponent(sql)}`);
                const data = await response.json();
                
                if (data.error) {
                    resultsContent.innerHTML = `<pre style="border-color: var(--danger); color: var(--danger);">${data.error}</pre>`;
                } else if (Array.isArray(data)) {
                    if (data.length === 0) {
                        resultsContent.innerHTML = '<div style="color: var(--text-muted);">Query executed successfully. Empty set returned.</div>';
                        return;
                    }
                    
                    // Render query output as table
                    let tableHtml = '<div class="table-responsive"><table><thead><tr>';
                    const headers = Object.keys(data[0]);
                    headers.forEach(h => tableHtml += `<th>${h}</th>`);
                    tableHtml += '</tr></thead><tbody>';
                    
                    data.forEach(row => {
                        tableHtml += 'tr';
                        headers.forEach(h => {
                            tableHtml += `<td>${row[h] !== null ? row[h] : 'NULL'}</td>`;
                        });
                        tableHtml += '</tr>';
                    });
                    tableHtml += '</tbody></table></div>';
                    resultsContent.innerHTML = tableHtml;
                } else {
                    resultsContent.innerHTML = `<pre>${JSON.stringify(data, null, 2)}</pre>`;
                }
            } catch (err) {
                resultsContent.innerHTML = `<pre style="border-color: var(--danger); color: var(--danger);">Network or Server Error: ${err.message}</pre>`;
            }
        };

        window.onload = fetchTables;
    </script>
</body>
</html>
"""
        html_replaced = html.replace('{db_name}', db_name)
        self.wfile.write(html_replaced.encode('utf-8'))


def main():
    parser = argparse.ArgumentParser(
        description="SQLite REST API & Dashboard Server - Expose SQLite DBs as REST APIs."
    )
    parser.add_argument(
        "db_path",
        nargs="?",
        default=DEFAULT_DB,
        help=f"Path to SQLite database file. Defaults to '{DEFAULT_DB}'"
    )
    parser.add_argument(
        "-p", "--port",
        type=int,
        default=8000,
        help="Server port number (default: 8000)"
    )
    parser.add_argument(
        "-b", "--bind",
        default="127.0.0.1",
        help="Interface address to bind to (default: 127.0.0.1)"
    )
    args = parser.parse_args()

    # Create default sample database if needed
    if args.db_path == DEFAULT_DB and not os.path.exists(DEFAULT_DB):
        create_sample_db(DEFAULT_DB)
    elif not os.path.exists(args.db_path):
        print(f"[-] Database file not found: {args.db_path}", file=sys.stderr)
        return 1

    print(f"[*] Connecting to database: {args.db_path}")
    db_manager = DatabaseManager(args.db_path)
    
    # Check tables
    tables = db_manager.get_tables()
    print(f"[*] Found {len(tables)} tables: {', '.join(tables) if tables else 'None'}")

    # Set up handler database
    class BoundHandler(SQLiteAPIRequestHandler):
        pass
    BoundHandler.db_manager = db_manager

    server_address = (args.bind, args.port)
    try:
        httpd = http.server.HTTPServer(server_address, BoundHandler)
        print(f"[+] SQLite REST API Server is running at http://{args.bind}:{args.port}/")
        print(f"[*] REST endpoints exposed under http://{args.bind}:{args.port}/api/")
        print("[*] Press Ctrl+C to terminate the server.")
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down server...")
    except Exception as e:
        print(f"[-] Server Error: {e}", file=sys.stderr)
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
