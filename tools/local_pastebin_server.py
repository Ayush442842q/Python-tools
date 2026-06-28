#!/usr/bin/env python3
"""
Local Pastebin & Code Snippet Server - Share code and text snippets on your local network.

This tool hosts a local web server with a responsive dark-themed user interface,
storing code snippets in a local SQLite database. It features dynamic client-side 
syntax highlighting (using Prism.js), search capabilities, one-click copy, and deletion.

Usage:
    python tools/local_pastebin_server.py [--host HOST] [--port PORT] [--db DATABASE]

Example:
    python tools/local_pastebin_server.py --port 9000
"""

import argparse
import os
import sqlite3
import sys
import urllib.parse
from datetime import datetime
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, List

# HTML templates
BASE_STYLE = """
:root {
    --bg-primary: #0d1117;
    --bg-secondary: #161b22;
    --bg-tertiary: #21262d;
    --text-primary: #c9d1d9;
    --text-secondary: #8b949e;
    --accent: #58a6ff;
    --accent-hover: #1f6feb;
    --danger: #f85149;
    --danger-hover: #da3633;
    --border: #30363d;
}
body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
    background-color: var(--bg-primary);
    color: var(--text-primary);
    margin: 0;
    padding: 0;
    line-height: 1.5;
}
.container {
    max-width: 1000px;
    margin: 0 auto;
    padding: 2rem 1rem;
}
header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid var(--border);
    padding-bottom: 1rem;
    margin-bottom: 2rem;
}
h1 a {
    color: var(--accent);
    text-decoration: none;
    font-weight: 700;
}
.btn {
    background-color: var(--accent);
    color: white;
    border: none;
    padding: 0.5rem 1rem;
    border-radius: 6px;
    cursor: pointer;
    font-weight: 600;
    text-decoration: none;
    display: inline-flex;
    align-items: center;
    transition: background-color 0.2s;
}
.btn:hover {
    background-color: var(--accent-hover);
}
.btn-danger {
    background-color: var(--danger);
}
.btn-danger:hover {
    background-color: var(--danger-hover);
}
.btn-secondary {
    background-color: var(--bg-tertiary);
    border: 1px solid var(--border);
    color: var(--text-primary);
}
.btn-secondary:hover {
    background-color: var(--border);
}
input, textarea, select {
    background-color: var(--bg-secondary);
    color: var(--text-primary);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 0.6rem;
    font-size: 1rem;
    width: 100%;
    box-sizing: border-box;
    font-family: inherit;
}
input:focus, textarea:focus, select:focus {
    border-color: var(--accent);
    outline: none;
}
.form-group {
    margin-bottom: 1.5rem;
}
label {
    display: block;
    margin-bottom: 0.5rem;
    font-weight: 600;
    color: var(--text-secondary);
}
.flex-row {
    display: flex;
    gap: 1rem;
}
.flex-row > .form-group {
    flex: 1;
}
.snippet-grid {
    display: grid;
    grid-template-columns: 2fr 1fr;
    gap: 2rem;
}
@media (max-width: 768px) {
    .snippet-grid {
        grid-template-columns: 1fr;
    }
}
.card {
    background-color: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 1.5rem;
    margin-bottom: 1.5rem;
}
.snippet-list {
    list-style: none;
    padding: 0;
    margin: 0;
}
.snippet-item {
    border-bottom: 1px solid var(--border);
    padding: 0.75rem 0;
    display: flex;
    justify-content: space-between;
    align-items: center;
}
.snippet-item:last-child {
    border-bottom: none;
}
.snippet-link {
    color: var(--text-primary);
    text-decoration: none;
    font-weight: 600;
}
.snippet-link:hover {
    color: var(--accent);
}
.meta {
    font-size: 0.8rem;
    color: var(--text-secondary);
}
.lang-badge {
    background-color: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 0.1rem 0.5rem;
    font-size: 0.75rem;
    color: var(--text-secondary);
    text-transform: uppercase;
}
pre {
    border-radius: 6px;
    padding: 1rem;
    overflow-x: auto;
    background-color: #1e1e1e !important;
}
code {
    font-family: "Fira Code", Consolas, Monaco, monospace;
}
"""

HOME_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Local Pastebin & Snippet Manager</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>{style}</style>
</head>
<body>
    <div class="container">
        <header>
            <h1><a href="/">📋 Local Pastebin</a></h1>
            <span class="meta">Share snippets instantly across your local network</span>
        </header>

        <div class="snippet-grid">
            <div>
                <form action="/create" method="POST">
                    <div class="form-group">
                        <label for="title">Title</label>
                        <input type="text" id="title" name="title" placeholder="Untitled Snippet" required>
                    </div>
                    <div class="flex-row">
                        <div class="form-group">
                            <label for="language">Language</label>
                            <select id="language" name="language">
                                <option value="plaintext">Plain Text</option>
                                <option value="python">Python</option>
                                <option value="javascript">JavaScript</option>
                                <option value="html">HTML</option>
                                <option value="css">CSS</option>
                                <option value="sql">SQL</option>
                                <option value="bash">Bash / Shell</option>
                                <option value="json">JSON</option>
                                <option value="yaml">YAML</option>
                                <option value="markdown">Markdown</option>
                                <option value="c">C</option>
                                <option value="cpp">C++</option>
                                <option value="rust">Rust</option>
                                <option value="go">Go</option>
                                <option value="java">Java</option>
                            </select>
                        </div>
                    </div>
                    <div class="form-group">
                        <label for="content">Code / Content</label>
                        <textarea id="content" name="content" rows="18" placeholder="Paste your code or text here..." required style="font-family: monospace;"></textarea>
                    </div>
                    <button type="submit" class="btn">Create Paste</button>
                </form>
            </div>

            <div>
                <h2>Recent Pastes</h2>
                <div class="card">
                    <div class="form-group">
                        <input type="text" id="search" placeholder="Search snippets..." onkeyup="filterSnippets()">
                    </div>
                    <ul class="snippet-list" id="snippet-list">
                        {snippets}
                    </ul>
                </div>
            </div>
        </div>
    </div>
    <script>
        function filterSnippets() {{
            const filter = document.getElementById('search').value.toLowerCase();
            const items = document.querySelectorAll('.snippet-item');
            items.forEach(item => {{
                const title = item.querySelector('.snippet-link').textContent.toLowerCase();
                const lang = item.querySelector('.lang-badge').textContent.toLowerCase();
                if (title.includes(filter) || lang.includes(filter)) {{
                    item.style.display = '';
                }} else {{
                    item.style.display = 'none';
                }}
            }});
        }}
    </script>
</body>
</html>
"""

VIEW_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>{title} - Local Pastebin</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>{style}</style>
    <!-- Prism.js for syntax highlighting -->
    <link href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-tomorrow.min.css" rel="stylesheet" />
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1><a href="/">📋 Local Pastebin</a></h1>
                <span class="meta">Viewing Snippet: <strong>{title}</strong></span>
            </div>
            <div style="display: flex; gap: 0.5rem;">
                <a href="/" class="btn btn-secondary">← Create New</a>
                <button onclick="copySnippet()" class="btn" id="copy-btn">Copy Code</button>
                <form action="/delete/{id}" method="POST" style="margin: 0;" onsubmit="return confirm('Are you sure you want to delete this paste?');">
                    <button type="submit" class="btn btn-danger">Delete</button>
                </form>
            </div>
        </header>

        <div class="card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                <div class="meta">Created on: {created_at}</div>
                <span class="lang-badge">{language}</span>
            </div>
            <pre><code class="language-{language}">{content}</code></pre>
        </div>
    </div>

    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/components/prism-core.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/plugins/autoloader/prism-autoloader.min.js"></script>
    <script>
        function copySnippet() {{
            const code = document.querySelector('code').textContent;
            navigator.clipboard.writeText(code).then(() => {{
                const btn = document.getElementById('copy-btn');
                btn.textContent = 'Copied!';
                btn.style.backgroundColor = '#2ea44f';
                setTimeout(() => {{
                    btn.textContent = 'Copy Code';
                    btn.style.backgroundColor = '';
                }}, 2000);
            }}).catch(err => {{
                alert('Failed to copy text: ' + err);
            }});
        }}
    </script>
</body>
</html>
"""


class PastebinDatabase:
    """Helper to manage SQLite operations for Pastebin."""
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS snippets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT NOT NULL,
                    language TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def create_paste(self, title: str, language: str, content: str) -> int:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO snippets (title, language, content) VALUES (?, ?, ?)",
                (title, language, content)
            )
            conn.commit()
            return cursor.lastrowid

    def get_paste(self, snippet_id: int) -> Optional[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM snippets WHERE id = ?", (snippet_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_recent_pastes(self, limit: int = 50) -> List[Dict[str, Any]]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM snippets ORDER BY created_at DESC LIMIT ?", (limit,))
            return [dict(row) for row in cursor.fetchall()]

    def delete_paste(self, snippet_id: int):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM snippets WHERE id = ?", (snippet_id,))
            conn.commit()


class PastebinRequestHandler(BaseHTTPRequestHandler):
    db: PastebinDatabase = None

    def log_message(self, format: str, *args: Any) -> None:
        sys.stdout.write(f"[{self.log_date_time_string()}] {format % args}\n")

    def do_GET(self):
        # Home page routing
        if self.path == "/":
            self.serve_home()
        # View specific snippet routing
        elif self.path.startswith("/snippet/"):
            try:
                snippet_id = int(self.path.split("/")[-1])
                self.serve_snippet(snippet_id)
            except ValueError:
                self.send_error_response(400, "Invalid Snippet ID")
        else:
            self.send_error_response(404, "Page Not Found")

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        params = urllib.parse.parse_qs(post_data)

        # Create snippet routing
        if self.path == "/create":
            title = params.get("title", ["Untitled Snippet"])[0]
            language = params.get("language", ["plaintext"])[0]
            content = params.get("content", [""])[0]

            if not content.strip():
                self.send_error_response(400, "Content cannot be empty")
                return

            snippet_id = self.db.create_paste(title, language, content)
            self.send_redirect(f"/snippet/{snippet_id}")

        # Delete snippet routing
        elif self.path.startswith("/delete/"):
            try:
                snippet_id = int(self.path.split("/")[-1])
                self.db.delete_paste(snippet_id)
                self.send_redirect("/")
            except ValueError:
                self.send_error_response(400, "Invalid Snippet ID")
        else:
            self.send_error_response(404, "Endpoint Not Found")

    def serve_home(self):
        snippets_data = self.db.get_recent_pastes()
        snippets_html_list = []
        
        for s in snippets_data:
            created = datetime.strptime(s['created_at'], "%Y-%m-%d %H:%M:%S").strftime("%b %d, %Y %H:%M")
            snippets_html_list.append(f"""
                <li class="snippet-item">
                    <div>
                        <a href="/snippet/{s['id']}" class="snippet-link">{self.escape_html(s['title'])}</a>
                        <div class="meta">{created}</div>
                    </div>
                    <span class="lang-badge">{s['language']}</span>
                </li>
            """)

        snippets_html = "\\n".join(snippets_html_list) if snippets_html_list else "<li class='meta'>No pastes found.</li>"
        
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(HOME_HTML.format(style=BASE_STYLE, snippets=snippets_html).encode("utf-8"))

    def serve_snippet(self, snippet_id: int):
        snippet = self.db.get_paste(snippet_id)
        if not snippet:
            self.send_error_response(404, "Snippet Not Found")
            return

        created = datetime.strptime(snippet['created_at'], "%Y-%m-%d %H:%M:%S").strftime("%b %d, %Y %H:%M")
        
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(VIEW_HTML.format(
            style=BASE_STYLE,
            title=self.escape_html(snippet['title']),
            id=snippet['id'],
            language=snippet['language'],
            content=self.escape_html(snippet['content']),
            created_at=created
        ).encode("utf-8"))

    def send_redirect(self, location: str):
        self.send_response(303)
        self.send_header("Location", location)
        self.end_headers()

    def send_error_response(self, code: int, message: str):
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        error_html = f"""
        <!DOCTYPE html>
        <html>
        <head><title>Error {code}</title><style>{BASE_STYLE}</style></head>
        <body style="display:flex; justify-content:center; align-items:center; height:100vh; margin:0;">
            <div class="card" style="text-align:center; max-width:400px; width:100%;">
                <h1 style="color:var(--danger); font-size:3rem; margin:0;">{code}</h1>
                <p style="margin:1rem 0 2rem 0;">{self.escape_html(message)}</p>
                <a href="/" class="btn">Go Home</a>
            </div>
        </body>
        </html>
        """
        self.wfile.write(error_html.encode("utf-8"))

    @staticmethod
    def escape_html(text: str) -> str:
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;").replace("'", "&#x27;")


def main():
    parser = argparse.ArgumentParser(description="Start the local Pastebin & Code Snippet web server.")
    parser.add_argument("--host", default="0.0.0.0", help="Binding address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port to host server on (default: 8000)")
    parser.add_argument("--db", default="local_pastebin.db", help="SQLite database path (default: local_pastebin.db)")
    args = parser.parse_args()

    # Initialize DB
    PastebinRequestHandler.db = PastebinDatabase(args.db)

    server = HTTPServer((args.host, args.port), PastebinRequestHandler)
    print(f"Pastebin Server running on http://{'localhost' if args.host == '0.0.0.0' else args.host}:{args.port}")
    print(f"Database file: {os.path.abspath(args.db)}")
    print("Press Ctrl+C to terminate.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\\nShutting down server...")
        server.server_close()
        sys.exit(0)


if __name__ == "__main__":
    main()
