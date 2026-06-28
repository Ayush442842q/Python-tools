#!/usr/bin/env python3
"""
Markdown Wiki & Note-Taking Server - A self-hosted personal wiki in a directory of Markdown files.

This tool hosts a local web server that reads Markdown files (.md) from a directory, 
renders them as HTML pages in a beautiful dark theme, supports client-side search, 
and provides a web-based editing interface to write, update, and delete notes directly.

Usage:
    python tools/markdown_wiki_server.py [--host HOST] [--port PORT] [--dir WIKI_DIR]

Example:
    python tools/markdown_wiki_server.py --port 8080 --dir ./my_wiki
"""

import argparse
import os
import sys
import re
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, Any, List, Set, Tuple

BASE_STYLE = """
:root {
    --bg-primary: #0d1117;
    --bg-secondary: #161b22;
    --bg-tertiary: #21262d;
    --text-primary: #c9d1d9;
    --text-secondary: #8b949e;
    --accent: #2ea44f;
    --accent-hover: #2c974b;
    --link-color: #58a6ff;
    --link-hover: #1f6feb;
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
    line-height: 1.6;
}
.container {
    max-width: 1100px;
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
    color: var(--text-primary);
    text-decoration: none;
    font-weight: 700;
}
.btn {
    background-color: var(--accent);
    color: white;
    border: 1px solid rgba(240,246,252,0.1);
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
    background-color: var(--bg-secondary);
    border: 1px solid var(--border);
    color: var(--danger);
}
.btn-danger:hover {
    background-color: var(--danger);
    color: white;
}
.btn-secondary {
    background-color: var(--bg-tertiary);
    border: 1px solid var(--border);
    color: var(--text-primary);
}
.btn-secondary:hover {
    background-color: var(--border);
}
.wiki-layout {
    display: grid;
    grid-template-columns: 280px 1fr;
    gap: 2rem;
}
@media (max-width: 768px) {
    .wiki-layout {
        grid-template-columns: 1fr;
    }
}
.sidebar {
    border-right: 1px solid var(--border);
    padding-right: 1.5rem;
}
@media (max-width: 768px) {
    .sidebar {
        border-right: none;
        padding-right: 0;
        border-bottom: 1px solid var(--border);
        padding-bottom: 1.5rem;
        margin-bottom: 1.5rem;
    }
}
.sidebar-title {
    font-size: 0.9rem;
    font-weight: 600;
    color: var(--text-secondary);
    text-transform: uppercase;
    margin-bottom: 0.75rem;
}
.sidebar-list {
    list-style: none;
    padding: 0;
    margin: 0 0 1.5rem 0;
}
.sidebar-list li {
    margin-bottom: 0.5rem;
}
.sidebar-link {
    color: var(--link-color);
    text-decoration: none;
}
.sidebar-link:hover {
    text-decoration: underline;
}
.card {
    background-color: var(--bg-secondary);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 1.5rem;
}
input, textarea {
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
input:focus, textarea:focus {
    border-color: var(--link-color);
    outline: none;
}
.form-group {
    margin-bottom: 1.25rem;
}
label {
    display: block;
    margin-bottom: 0.5rem;
    font-weight: 600;
    color: var(--text-secondary);
}
.tag-badge {
    background-color: var(--bg-tertiary);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 0.1rem 0.5rem;
    font-size: 0.75rem;
    color: var(--text-secondary);
    margin-right: 0.4rem;
    display: inline-block;
}
a {
    color: var(--link-color);
}
a:hover {
    color: var(--link-hover);
}
/* Markdown render specific styles */
.markdown-body h1, .markdown-body h2, .markdown-body h3 {
    border-bottom: 1px solid var(--border);
    padding-bottom: 0.3em;
}
.markdown-body code {
    background-color: var(--bg-tertiary);
    padding: 0.2em 0.4em;
    border-radius: 6px;
    font-family: monospace;
    font-size: 85%;
}
.markdown-body pre {
    background-color: var(--bg-secondary);
    border: 1px solid var(--border);
    padding: 1rem;
    border-radius: 6px;
    overflow-x: auto;
}
.markdown-body pre code {
    background-color: transparent;
    padding: 0;
}
.backlink-section {
    margin-top: 3rem;
    border-top: 1px solid var(--border);
    padding-top: 1.5rem;
}
"""

LAYOUT_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>{page_title} - Wiki</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>{style}</style>
    <!-- Marked JS to parse Markdown client-side -->
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
</head>
<body>
    <div class="container">
        <header>
            <h1><a href="/">📖 Personal Wiki</a></h1>
            <div style="display: flex; gap: 0.5rem;">
                <a href="/new" class="btn">New Note</a>
            </div>
        </header>

        <div class="wiki-layout">
            <div class="sidebar">
                <div class="form-group">
                    <input type="text" id="wiki-search" placeholder="Search notes..." onkeyup="searchWiki()">
                </div>
                <div class="sidebar-title">Notes</div>
                <ul class="sidebar-list" id="sidebar-list">
                    {sidebar_notes}
                </ul>
            </div>
            <div>
                {main_content}
            </div>
        </div>
    </div>
    <script>
        function searchWiki() {{
            const filter = document.getElementById('wiki-search').value.toLowerCase();
            const items = document.querySelectorAll('.sidebar-list li');
            items.forEach(item => {{
                const text = item.querySelector('a').textContent.toLowerCase();
                if (text.includes(filter)) {{
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


class WikiRequestHandler(BaseHTTPRequestHandler):
    wiki_dir: str = ""

    def log_message(self, format: str, *args: Any) -> None:
        sys.stdout.write(f"[{self.log_date_time_string()}] {format % args}\n")

    def get_sidebar_notes(self) -> str:
        """Scan directory and build sidebar notes list."""
        if not os.path.exists(self.wiki_dir):
            return "<li>No notes found</li>"
        
        files = sorted([f for f in os.listdir(self.wiki_dir) if f.endswith(".md")])
        if not files:
            return "<li>No notes found</li>"

        sidebar_html = []
        for f in files:
            name = f[:-3]
            display_name = name.replace("_", " ").title()
            sidebar_html.append(f'<li><a href="/view/{name}" class="sidebar-link">{display_name}</a></li>')
        return "\\n".join(sidebar_html)

    def calculate_backlinks(self, note_name: str) -> List[str]:
        """Find other notes that link to the current note."""
        backlinks = []
        target_link_pattern = re.compile(rf"\\[.*?\\]\\((?:/view/)?{re.escape(note_name)}\\)", re.IGNORECASE)
        
        for f in os.listdir(self.wiki_dir):
            if f.endswith(".md") and f[:-3].lower() != note_name.lower():
                path = os.path.join(self.wiki_dir, f)
                try:
                    with open(path, "r", encoding="utf-8") as file:
                        content = file.read()
                        if target_link_pattern.search(content):
                            backlinks.append(f[:-3])
                except Exception:
                    pass
        return backlinks

    def do_GET(self):
        # Decode path
        path = urllib.parse.unquote(self.path)
        
        # Homepage redirect to Index or listing
        if path == "/" or path == "":
            index_path = os.path.join(self.wiki_dir, "index.md")
            if os.path.exists(index_path):
                self.send_redirect("/view/index")
            else:
                self.serve_wiki_listing()
        # View note
        elif path.startswith("/view/"):
            note_name = path[6:]
            self.serve_view_note(note_name)
        # Edit note
        elif path.startswith("/edit/"):
            note_name = path[6:]
            self.serve_edit_note(note_name)
        # Create new note
        elif path == "/new":
            self.serve_new_note()
        else:
            self.send_error_response(404, "Page Not Found")

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length).decode('utf-8')
        params = urllib.parse.parse_qs(post_data)

        # Save note
        if self.path == "/save":
            original_title = params.get("original_title", [""])[0]
            title = params.get("title", ["Untitled"])[0]
            content = params.get("content", [""])[0]

            # Standardize filename
            filename = title.strip().replace(" ", "_").lower()
            filename = "".join([c for c in filename if c.isalnum() or c in ("-", "_")])
            
            if not filename:
                self.send_error_response(400, "Invalid note title")
                return

            # Delete old file if renamed
            if original_title and original_title != filename:
                old_path = os.path.join(self.wiki_dir, f"{original_title}.md")
                if os.path.exists(old_path):
                    os.remove(old_path)

            # Write file
            file_path = os.path.join(self.wiki_dir, f"{filename}.md")
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)
                self.send_redirect(f"/view/{filename}")
            except Exception as e:
                self.send_error_response(500, f"Failed to save note: {e}")

        # Delete note
        elif self.path.startswith("/delete/"):
            note_name = self.path[8:]
            file_path = os.path.join(self.wiki_dir, f"{note_name}.md")
            if os.path.exists(file_path):
                try:
                    os.remove(file_path)
                    self.send_redirect("/")
                except Exception as e:
                    self.send_error_response(500, f"Failed to delete note: {e}")
            else:
                self.send_error_response(404, "Note not found")
        else:
            self.send_error_response(404, "Endpoint not found")

    def serve_wiki_listing(self):
        sidebar = self.get_sidebar_notes()
        
        main_content = """
        <div class="card">
            <h2>Welcome to your Personal Wiki</h2>
            <p>Select a note from the sidebar or click below to create a new one.</p>
            <div style="margin-top: 1.5rem;">
                <a href="/new" class="btn">Create Index / First Note</a>
            </div>
        </div>
        """
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        
        html = LAYOUT_HTML.format(
            page_title="Wiki Home",
            style=BASE_STYLE,
            sidebar_notes=sidebar,
            main_content=main_content
        )
        self.wfile.write(html.encode("utf-8"))

    def serve_view_note(self, note_name: str):
        file_path = os.path.join(self.wiki_dir, f"{note_name}.md")
        if not os.path.exists(file_path):
            # Offer to create it if it doesn't exist
            self.send_redirect(f"/edit/{note_name}")
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_markdown = f.read()
        except Exception as e:
            self.send_error_response(500, f"Error reading note: {e}")
            return

        sidebar = self.get_sidebar_notes()
        display_title = note_name.replace("_", " ").title()

        # Parse tags from frontmatter or hashtags (simple regex)
        tags = re.findall(r"#(\w+)", raw_markdown)
        tags_html = "".join([f'<span class="tag-badge">#{t}</span>' for t in set(tags)])

        # Calculate backlinks
        backlinks = self.calculate_backlinks(note_name)
        backlinks_html_list = []
        for bl in backlinks:
            bl_display = bl.replace("_", " ").title()
            backlinks_html_list.append(f'<li><a href="/view/{bl}">{bl_display}</a></li>')
        
        backlinks_section = ""
        if backlinks_html_list:
            backlinks_section = f"""
            <div class="backlink-section">
                <h3>Backlinks</h3>
                <ul class="sidebar-list">
                    {"".join(backlinks_html_list)}
                </ul>
            </div>
            """

        main_content = f"""
        <div class="card">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:1.5rem; border-bottom:1px solid var(--border); padding-bottom:1rem;">
                <div>
                    <h2 style="margin:0;">{display_title}</h2>
                    <div style="margin-top: 0.5rem;">{tags_html}</div>
                </div>
                <div style="display:flex; gap:0.5rem;">
                    <a href="/edit/{note_name}" class="btn btn-secondary">Edit</a>
                    <form action="/delete/{note_name}" method="POST" style="margin:0;" onsubmit="return confirm('Are you sure you want to delete this note?');">
                        <button type="submit" class="btn btn-danger">Delete</button>
                    </form>
                </div>
            </div>
            <div id="content" class="markdown-body"></div>
        </div>
        {backlinks_section}

        <script>
            // Safely injection of raw markdown into client side marked JS
            const rawMarkdown = {repr(raw_markdown)};
            document.getElementById('content').innerHTML = marked.parse(rawMarkdown);
        </script>
        """

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        
        html = LAYOUT_HTML.format(
            page_title=display_title,
            style=BASE_STYLE,
            sidebar_notes=sidebar,
            main_content=main_content
        )
        self.wfile.write(html.encode("utf-8"))

    def serve_edit_note(self, note_name: str):
        file_path = os.path.join(self.wiki_dir, f"{note_name}.md")
        raw_markdown = ""
        if os.path.exists(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    raw_markdown = f.read()
            except Exception:
                pass

        sidebar = self.get_sidebar_notes()
        display_title = note_name.replace("_", " ").title()

        main_content = f"""
        <div class="card">
            <h2>Editing: {display_title}</h2>
            <form action="/save" method="POST">
                <input type="hidden" name="original_title" value="{note_name}">
                <div class="form-group">
                    <label for="title">Title</label>
                    <input type="text" id="title" name="title" value="{display_title}" required>
                </div>
                <div class="form-group">
                    <label for="content">Markdown Content</label>
                    <textarea id="content" name="content" rows="22" required style="font-family:monospace;">{self.escape_html(raw_markdown)}</textarea>
                </div>
                <div style="display:flex; gap:0.5rem;">
                    <button type="submit" class="btn">Save Note</button>
                    <a href="/view/{note_name}" class="btn btn-secondary">Cancel</a>
                </div>
            </form>
        </div>
        """

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        html = LAYOUT_HTML.format(
            page_title=f"Edit {display_title}",
            style=BASE_STYLE,
            sidebar_notes=sidebar,
            main_content=main_content
        )
        self.wfile.write(html.encode("utf-8"))

    def serve_new_note(self):
        sidebar = self.get_sidebar_notes()
        
        main_content = """
        <div class="card">
            <h2>New Wiki Note</h2>
            <form action="/save" method="POST">
                <input type="hidden" name="original_title" value="">
                <div class="form-group">
                    <label for="title">Title</label>
                    <input type="text" id="title" name="title" placeholder="New Note Title" required>
                </div>
                <div class="form-group">
                    <label for="content">Markdown Content</label>
                    <textarea id="content" name="content" rows="22" placeholder="# New Note\\n\\nWrite markdown text here... Use hashtags like #tag to categorize." required style="font-family:monospace;"></textarea>
                </div>
                <div style="display:flex; gap:0.5rem;">
                    <button type="submit" class="btn">Save Note</button>
                    <a href="/" class="btn btn-secondary">Cancel</a>
                </div>
            </form>
        </div>
        """

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        html = LAYOUT_HTML.format(
            page_title="New Note",
            style=BASE_STYLE,
            sidebar_notes=sidebar,
            main_content=main_content
        )
        self.wfile.write(html.encode("utf-8"))

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
    parser = argparse.ArgumentParser(description="Start the local Markdown Wiki and Note-taking web server.")
    parser.add_argument("--host", default="0.0.0.0", help="Binding address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8080, help="Port to host server on (default: 8080)")
    parser.add_argument("--dir", default="wiki", help="Directory storing markdown files (default: ./wiki)")
    args = parser.parse_args()

    # Create wiki dir if it doesn't exist
    os.makedirs(args.dir, exist_ok=True)
    
    # Initialize index.md if wiki directory is completely empty
    index_file = os.path.join(args.dir, "index.md")
    if not os.path.exists(index_file) and not os.listdir(args.dir):
        with open(index_file, "w", encoding="utf-8") as f:
            f.write("# Personal Wiki Home\\n\\nWelcome to your self-hosted **Markdown Wiki**!\\n\\n- Click **New Note** to add a new document.\\n- Use double brackets or standard links to link notes together (e.g. `[Index](/view/index)`).\\n- Add hashtags like `#welcome` or `#todo` to see tags list.\\n")

    WikiRequestHandler.wiki_dir = args.dir

    server = HTTPServer((args.host, args.port), WikiRequestHandler)
    print(f"Markdown Wiki Server running on http://{'localhost' if args.host == '0.0.0.0' else args.host}:{args.port}")
    print(f"Notes directory: {os.path.abspath(args.dir)}")
    print("Press Ctrl+C to terminate.")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\\nShutting down server...")
        server.server_close()
        sys.exit(0)


if __name__ == "__main__":
    main()
