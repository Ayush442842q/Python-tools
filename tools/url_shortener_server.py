#!/usr/bin/env python3
"""
Local URL Shortener Server - Zero-dependency URL shortener and analytics dashboard

This tool runs a local HTTP web server that acts as a URL shortener.
It provides a web interface where you can:
1. Shorten long URLs with random codes or custom aliases.
2. Redirect short URLs to long URLs.
3. Track click analytics, timestamps, and user agents in a local SQLite database.

Usage:
    python tools/url_shortener_server.py [--port PORT] [--db DB_PATH]
"""

import argparse
import http.server
import json
import os
import random
import re
import sqlite3
import string
import sys
import urllib.parse
from datetime import datetime

class URLShortenerDB:
    """Manages the SQLite database for URLs and redirection analytics."""
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.create_tables()

    def create_tables(self):
        with self.conn:
            # Table to store URL mapping
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS urls (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    short_code TEXT UNIQUE,
                    long_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            # Table to store redirect analytics
            self.conn.execute('''
                CREATE TABLE IF NOT EXISTS clicks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    short_code TEXT,
                    clicked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    user_agent TEXT,
                    referrer TEXT,
                    FOREIGN KEY (short_code) REFERENCES urls(short_code)
                )
            ''')

    def add_url(self, short_code: str, long_url: str) -> bool:
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO urls (short_code, long_url) VALUES (?, ?)",
                    (short_code, long_url)
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def get_long_url(self, short_code: str) -> str:
        cursor = self.conn.cursor()
        cursor.execute("SELECT long_url FROM urls WHERE short_code = ?", (short_code,))
        row = cursor.fetchone()
        return row[0] if row else None

    def record_click(self, short_code: str, user_agent: str, referrer: str):
        with self.conn:
            self.conn.execute(
                "INSERT INTO clicks (short_code, user_agent, referrer) VALUES (?, ?, ?)",
                (short_code, user_agent, referrer)
            )

    def get_all_urls_with_stats(self) -> list:
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT u.short_code, u.long_url, u.created_at, COUNT(c.id) as click_count
            FROM urls u
            LEFT JOIN clicks c ON u.short_code = c.short_code
            GROUP BY u.short_code
            ORDER BY u.created_at DESC
        ''')
        rows = cursor.fetchall()
        return [
            {
                "short_code": r[0],
                "long_url": r[1],
                "created_at": r[2],
                "click_count": r[3]
            } for r in rows
        ]

    def get_clicks_for_code(self, short_code: str) -> list:
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT clicked_at, user_agent, referrer
            FROM clicks
            WHERE short_code = ?
            ORDER BY clicked_at DESC
            LIMIT 50
        ''', (short_code,))
        rows = cursor.fetchall()
        return [
            {
                "clicked_at": r[0],
                "user_agent": r[1],
                "referrer": r[2]
            } for r in rows
        ]

class URLShortenerHandler(http.server.BaseHTTPRequestHandler):
    """Handles HTTP requests for redirection and the admin dashboard."""
    db: URLShortenerDB = None
    server_host: str = "localhost"
    server_port: int = 8000

    def log_message(self, format, *args):
        # Override to suppress default stdout log clutter
        pass

    def send_html_response(self, html_content: str, status_code: int = 200):
        self.send_response(status_code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html_content.encode("utf-8"))

    def send_json_response(self, data: Any, status_code: int = 200):
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def generate_random_code(self, length: int = 6) -> str:
        chars = string.ascii_letters + string.digits
        return "".join(random.choice(chars) for _ in range(length))

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path.strip("/")

        # Root admin page
        if path == "" or path == "index.html":
            self.serve_dashboard()
            return

        # API to get all shortened URLs
        if path == "api/urls":
            urls = self.db.get_all_urls_with_stats()
            self.send_json_response(urls)
            return

        # API to get click history for a code
        match = re.match(r"^api/clicks/([a-zA-Z0-9_-]+)$", path)
        if match:
            short_code = match.group(1)
            clicks = self.db.get_clicks_for_code(short_code)
            self.send_json_response(clicks)
            return

        # Redirect logic
        long_url = self.db.get_long_url(path)
        if long_url:
            user_agent = self.headers.get("User-Agent", "Unknown")
            referrer = self.headers.get("Referer", "Direct")
            self.db.record_click(path, user_agent, referrer)
            
            # Send 302 redirect
            self.send_response(302)
            self.send_header("Location", long_url)
            self.end_headers()
            print(f"[Redirect] {self.headers.get('Host', '')}/{path} -> {long_url}")
        else:
            # 404 page
            self.serve_404(path)

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path.strip("/")

        if path == "api/shorten":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            try:
                data = json.loads(post_data.decode('utf-8'))
                long_url = data.get("long_url", "").strip()
                custom_alias = data.get("custom_alias", "").strip()

                if not long_url:
                    self.send_json_response({"error": "Long URL is required"}, 400)
                    return

                # Validate URL structure
                if not re.match(r"^https?://", long_url):
                    long_url = "http://" + long_url

                if custom_alias:
                    # Sanitize custom alias
                    custom_alias = re.sub(r"[^a-zA-Z0-9_-]", "", custom_alias)
                    if not custom_alias:
                        self.send_json_response({"error": "Invalid custom alias characters"}, 400)
                        return
                    short_code = custom_alias
                else:
                    short_code = self.generate_random_code()
                    # Ensure uniqueness
                    while self.db.get_long_url(short_code) is not None:
                        short_code = self.generate_random_code()

                success = self.db.add_url(short_code, long_url)
                if success:
                    short_url = f"http://{self.server_host}:{self.server_port}/{short_code}"
                    self.send_json_response({
                        "success": True,
                        "short_code": short_code,
                        "short_url": short_url,
                        "long_url": long_url
                    })
                else:
                    self.send_json_response({"error": "Short code or alias already exists"}, 400)
            except Exception as e:
                self.send_json_response({"error": f"Server error: {str(e)}"}, 500)

    def serve_dashboard(self):
        # A beautiful dark-themed dashboard matching web application guidelines
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Local URL Shortener & Analytics</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --accent-color: #6366f1;
            --accent-hover: #4f46e5;
            --text-main: #f8fafc;
            --text-sub: #94a3b8;
            --border-color: #334155;
            --success-color: #10b981;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            line-height: 1.5;
            padding: 2rem 1rem;
        }}
        .container {{
            max-width: 1000px;
            margin: 0 auto;
        }}
        header {{
            margin-bottom: 2.5rem;
            text-align: center;
        }}
        h1 {{
            font-size: 2.25rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
            background: linear-gradient(135deg, #818cf8, #a78bfa);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        p.subtitle {{
            color: var(--text-sub);
            font-size: 1rem;
        }}
        .card {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 0.75rem;
            padding: 2rem;
            margin-bottom: 2rem;
            box-shadow: 0 4px 6px -1px rgb(0 0 0 / 0.1), 0 2px 4px -2px rgb(0 0 0 / 0.1);
        }}
        .form-grid {{
            display: grid;
            grid-template-columns: 2fr 1fr auto;
            gap: 1rem;
            align-items: end;
        }}
        @media (max-width: 768px) {{
            .form-grid {{
                grid-template-columns: 1fr;
            }}
        }}
        .form-group {{
            display: flex;
            flex-direction: column;
            gap: 0.5rem;
        }}
        label {{
            font-size: 0.875rem;
            font-weight: 500;
            color: var(--text-sub);
        }}
        input {{
            background-color: var(--bg-color);
            border: 1px solid var(--border-color);
            border-radius: 0.375rem;
            padding: 0.75rem 1rem;
            color: var(--text-main);
            font-family: inherit;
            font-size: 1rem;
            outline: none;
            transition: border-color 0.2s;
        }}
        input:focus {{
            border-color: var(--accent-color);
        }}
        button {{
            background-color: var(--accent-color);
            color: white;
            border: none;
            border-radius: 0.375rem;
            padding: 0.75rem 1.5rem;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: background-color 0.2s;
            height: 100%;
        }}
        button:hover {{
            background-color: var(--accent-hover);
        }}
        .table-container {{
            overflow-x: auto;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
        }}
        th, td {{
            padding: 1rem;
            border-bottom: 1px solid var(--border-color);
        }}
        th {{
            color: var(--text-sub);
            font-weight: 600;
            font-size: 0.875rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        tr:hover td {{
            background-color: rgba(255, 255, 255, 0.02);
        }}
        .short-link {{
            color: #60a5fa;
            text-decoration: none;
            font-weight: 500;
        }}
        .short-link:hover {{
            text-decoration: underline;
        }}
        .long-link {{
            max-width: 300px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            color: var(--text-sub);
            display: inline-block;
        }}
        .click-badge {{
            background-color: rgba(99, 102, 241, 0.15);
            color: #a5b4fc;
            padding: 0.25rem 0.5rem;
            border-radius: 0.25rem;
            font-size: 0.875rem;
            font-weight: 600;
        }}
        .action-btn {{
            background-color: transparent;
            border: 1px solid var(--border-color);
            padding: 0.375rem 0.75rem;
            font-size: 0.875rem;
            color: var(--text-sub);
        }}
        .action-btn:hover {{
            background-color: var(--border-color);
            color: var(--text-main);
        }}
        /* Modal styling */
        .modal {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0, 0, 0, 0.6);
            align-items: center;
            justify-content: center;
            padding: 1rem;
            z-index: 100;
        }}
        .modal.active {{
            display: flex;
        }}
        .modal-content {{
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 0.5rem;
            width: 100%;
            max-width: 600px;
            padding: 2rem;
            max-height: 80vh;
            overflow-y: auto;
        }}
        .modal-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 1.5rem;
        }}
        .close-btn {{
            background: none;
            border: none;
            color: var(--text-sub);
            font-size: 1.5rem;
            cursor: pointer;
        }}
        .click-log {{
            list-style: none;
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }}
        .click-log-item {{
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 0.5rem;
        }}
        .click-log-time {{
            font-size: 0.875rem;
            color: var(--accent-color);
            font-weight: 500;
        }}
        .click-log-meta {{
            font-size: 0.875rem;
            color: var(--text-sub);
            word-break: break-all;
        }}
        .notification {{
            position: fixed;
            bottom: 2rem;
            right: 2rem;
            background-color: var(--success-color);
            color: white;
            padding: 1rem 1.5rem;
            border-radius: 0.375rem;
            font-weight: 500;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
            transform: translateY(150%);
            transition: transform 0.3s ease;
        }}
        .notification.show {{
            transform: translateY(0);
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>🔗 URL Shortener & Analytics</h1>
            <p class="subtitle">Create shortened URLs and track redirection details locally</p>
        </header>

        <section class="card">
            <form id="shortenForm" class="form-grid">
                <div class="form-group">
                    <label for="longUrl">Destination URL</label>
                    <input type="url" id="longUrl" placeholder="https://example.com/very/long/path/to/page" required>
                </div>
                <div class="form-group">
                    <label for="customAlias">Custom Alias (Optional)</label>
                    <input type="text" id="customAlias" placeholder="my-custom-link">
                </div>
                <button type="submit">Shorten</button>
            </form>
        </section>

        <section class="card">
            <h2 style="margin-bottom: 1.5rem; font-size: 1.25rem;">Shortened Links</h2>
            <div class="table-container">
                <table>
                    <thead>
                        <tr>
                            <th>Short URL</th>
                            <th>Original Destination</th>
                            <th>Created</th>
                            <th>Clicks</th>
                            <th>Actions</th>
                        </tr>
                    </thead>
                    <tbody id="urlTableBody">
                        <!-- Dynamic content -->
                    </tbody>
                </table>
            </div>
        </section>
    </div>

    <!-- Analytics Modal -->
    <div class="modal" id="analyticsModal">
        <div class="modal-content">
            <div class="modal-header">
                <h3 style="font-size: 1.25rem;">Redirect Click History (<span id="modalCode"></span>)</h3>
                <button class="close-btn" onclick="closeModal()">&times;</button>
            </div>
            <div id="modalBody">
                <!-- Click history loads here -->
            </div>
        </div>
    </div>

    <div class="notification" id="notification">Link copied to clipboard!</div>

    <script>
        document.getElementById("shortenForm").addEventListener("submit", async (e) => {{
            e.preventDefault();
            const longUrl = document.getElementById("longUrl").value;
            const customAlias = document.getElementById("customAlias").value;

            const res = await fetch("/api/shorten", {{
                method: "POST",
                headers: {{ "Content-Type": "application/json" }},
                body: JSON.stringify({{ long_url: longUrl, custom_alias: customAlias }})
            }});

            const result = await res.json();
            if (result.success) {{
                document.getElementById("shortenForm").reset();
                showNotification("Link created successfully!");
                loadUrls();
            }} else {{
                alert(result.error || "An error occurred");
            }}
        }});

        async function loadUrls() {{
            const res = await fetch("/api/urls");
            const urls = await res.json();
            const tbody = document.getElementById("urlTableBody");
            
            if (urls.length === 0) {{
                tbody.innerHTML = '<tr><td colspan="5" style="text-align: center; color: var(--text-sub);">No shortened URLs found yet.</td></tr>';
                return;
            }}

            tbody.innerHTML = urls.map(u => {{
                const shortUrl = `${{window.location.origin}}/${{u.short_code}}`;
                return `
                    <tr>
                        <td><a href="${{shortUrl}}" target="_blank" class="short-link">${{window.location.host}}/${{u.short_code}}</a></td>
                        <td><span class="long-link" title="${{u.long_url}}">${{u.long_url}}</span></td>
                        <td style="color: var(--text-sub); font-size: 0.875rem;">${{new Date(u.created_at).toLocaleString()}}</td>
                        <td><span class="click-badge">${{u.click_count}}</span></td>
                        <td>
                            <button class="action-btn" onclick="copyToClipboard('${{shortUrl}}')">Copy</button>
                            <button class="action-btn" onclick="viewAnalytics('${{u.short_code}}')">Stats</button>
                        </td>
                    </tr>
                `;
            }}).join('');
        }}

        function copyToClipboard(text) {{
            navigator.clipboard.writeText(text).then(() => {{
                showNotification("Copied to clipboard!");
            }});
        }}

        function showNotification(msg) {{
            const note = document.getElementById("notification");
            note.innerText = msg;
            note.classList.add("show");
            setTimeout(() => note.classList.remove("show"), 3000);
        }}

        async function viewAnalytics(code) {{
            document.getElementById("modalCode").innerText = code;
            const res = await fetch(`/api/clicks/${{code}}`);
            const clicks = await res.json();
            const modalBody = document.getElementById("modalBody");
            
            if (clicks.length === 0) {{
                modalBody.innerHTML = '<p style="color: var(--text-sub);">No clicks recorded yet.</p>';
            }} else {{
                modalBody.innerHTML = `
                    <ul class="click-log">
                        ${{clicks.map(c => `
                            <li class="click-log-item">
                                <div class="click-log-time">${{new Date(c.clicked_at).toLocaleString()}}</div>
                                <div class="click-log-meta"><strong>User Agent:</strong> ${{c.user_agent}}</div>
                                <div class="click-log-meta"><strong>Referrer:</strong> ${{c.referrer}}</div>
                            </li>
                        `).join('')}}
                    </ul>
                `;
            }}
            document.getElementById("analyticsModal").classList.add("active");
        }}

        function closeModal() {{
            document.getElementById("analyticsModal").classList.remove("active");
        }}

        // Load initially
        loadUrls();
    </script>
</body>
</html>
"""
        self.send_html_response(html)

    def serve_404(self, code: str):
        html = f"""<!DOCTYPE html>
<html>
<head>
    <title>404 - Not Found</title>
    <meta charset="utf-8">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap" rel="stylesheet">
    <style>
        body {{
            font-family: 'Inter', sans-serif;
            background-color: #0f172a;
            color: #f8fafc;
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100vh;
            margin: 0;
            text-align: center;
        }}
        .card {{
            background-color: #1e293b;
            border: 1px solid #334155;
            padding: 3rem;
            border-radius: 0.75rem;
            box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1);
        }}
        h1 {{ font-size: 3rem; color: #f43f5e; margin-bottom: 1rem; }}
        p {{ color: #94a3b8; margin-bottom: 2rem; }}
        a {{
            color: #6366f1;
            text-decoration: none;
            font-weight: 600;
            border: 1px solid #6366f1;
            padding: 0.5rem 1.5rem;
            border-radius: 0.25rem;
            transition: all 0.2s;
        }}
        a:hover {{
            background-color: #6366f1;
            color: white;
        }}
    </style>
</head>
<body>
    <div class="card">
        <h1>404</h1>
        <h2>Link Not Found</h2>
        <p>The shortened code <strong>{code}</strong> does not exist or has expired.</p>
        <a href="/">Go to Dashboard</a>
    </div>
</body>
</html>
"""
        self.send_html_response(html, 404)

def main():
    parser = argparse.ArgumentParser(description="Zero-dependency local URL Shortener server.")
    parser.add_argument('--port', type=int, default=8000, help='Port to run the server on (default: 8000)')
    parser.add_argument('--host', default='localhost', help='Hostname/IP to bind to (default: localhost)')
    parser.add_argument('--db', default='url_shortener.db', help='Path to sqlite database file (default: url_shortener.db)')
    
    args = parser.parse_args()
    
    print(f"Initializing database at: {args.db}")
    db = URLShortenerDB(args.db)
    
    # Configure request handler class properties
    URLShortenerHandler.db = db
    URLShortenerHandler.server_host = args.host
    URLShortenerHandler.server_port = args.port
    
    server_address = (args.host, args.port)
    try:
        httpd = http.server.HTTPServer(server_address, URLShortenerHandler)
        print(f"\033[92mURL Shortener Server running at http://{args.host}:{args.port}/\033[0m")
        print("Press Ctrl+C to terminate.")
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping server...")
        sys.exit(0)
    except Exception as e:
        print(f"Error starting server: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
