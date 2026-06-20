#!/usr/bin/env python3
"""
Python Codebase Documentation Server
Parses Python modules recursively using AST, generates a modern responsive dark-themed 
documentation dashboard, and hosts it on a local HTTP server.
"""

import argparse
import ast
import html
import http.server
import os
import socketserver
import sys
import threading
import webbrowser
from typing import Any, Dict, List, Optional

class DocExtractor(ast.NodeVisitor):
    """AST Node Visitor to extract classes, functions, and docstrings from a module."""
    def __init__(self, filename: str):
        self.filename = filename
        self.module_doc = ""
        self.classes = []
        self.functions = []
        self.current_class = None

    def visit_Module(self, node: ast.Module):
        self.module_doc = ast.get_docstring(node) or "No module docstring available."
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef):
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)
            elif isinstance(base, ast.Attribute):
                bases.append(f"{self._get_attr_name(base.value)}.{base.attr}")
                
        cls_info = {
            "name": node.name,
            "bases": bases,
            "doc": ast.get_docstring(node) or "No class docstring available.",
            "methods": [],
            "properties": []
        }
        
        # Save context to track nested functions as methods
        old_class = self.current_class
        self.current_class = cls_info
        
        self.generic_visit(node)
        
        self.current_class = old_class
        self.classes.append(cls_info)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._parse_func(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._parse_func(node, is_async=True)

    def _parse_func(self, node: Union[ast.FunctionDef, ast.AsyncFunctionDef], is_async: bool = False):
        func_name = node.name
        
        # Skip private/internal methods if not desired, but let's parse everything
        doc = ast.get_docstring(node) or "No docstring available."
        
        # Extract arguments
        args = []
        # Positional-only args
        if hasattr(node.args, 'posonlyargs'):
            for arg in node.args.posonlyargs:
                args.append(self._get_arg_str(arg))
        # Standard args
        for arg in node.args.args:
            args.append(self._get_arg_str(arg))
        # Varargs (*args)
        if node.args.vararg:
            args.append(f"*{node.args.vararg.arg}")
        # Keyword-only args
        for arg in node.args.kwonlyargs:
            args.append(self._get_arg_str(arg))
        # Kwargs (**kwargs)
        if node.args.kwarg:
            args.append(f"**{node.args.kwarg.arg}")
            
        arg_str = ", ".join(args)
        
        # Return type annotation
        ret_annotation = ""
        if node.returns:
            ret_annotation = f" -> {self._get_annotation_str(node.returns)}"
            
        func_info = {
            "name": func_name,
            "doc": doc,
            "args": arg_str,
            "returns": ret_annotation,
            "is_async": is_async,
            "is_method": self.current_class is not None
        }
        
        if self.current_class:
            # Check decorators for property or staticmethod/classmethod classification
            decorators = [self._get_decorator_name(dec) for dec in node.decorator_list]
            func_info["decorators"] = decorators
            self.current_class["methods"].append(func_info)
        else:
            self.functions.append(func_info)

    def _get_arg_str(self, arg: ast.arg) -> str:
        name = arg.arg
        if arg.annotation:
            ann = self._get_annotation_str(arg.annotation)
            return f"{name}: {ann}"
        return name

    def _get_annotation_str(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Constant):
            return str(node.value)
        elif isinstance(node, ast.Attribute):
            return f"{self._get_annotation_str(node.value)}.{node.attr}"
        elif isinstance(node, ast.Subscript):
            return f"{self._get_annotation_str(node.value)}[{self._get_annotation_str(node.slice)}]"
        elif isinstance(node, ast.Tuple):
            return f"Tuple[{', '.join(self._get_annotation_str(elt) for elt in node.elts)}]"
        elif isinstance(node, ast.List):
            return f"List[{', '.join(self._get_annotation_str(elt) for elt in node.elts)}]"
        elif isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
            # Support modern union syntax: A | B
            return f"{self._get_annotation_str(node.left)} | {self._get_annotation_str(node.right)}"
        return "Any"

    def _get_decorator_name(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_attr_name(node.value)}.{node.attr}"
        elif isinstance(node, ast.Call):
            return self._get_decorator_name(node.func)
        return "decorator"

    def _get_attr_name(self, node: ast.AST) -> str:
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_attr_name(node.value)}.{node.attr}"
        return ""

def parse_python_file(filepath: str) -> Optional[Dict[str, Any]]:
    """Parse a single Python file into a structured dictionary of docs."""
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            code = f.read()
        tree = ast.parse(code, filename=filepath)
        extractor = DocExtractor(filepath)
        extractor.visit(tree)
        return {
            "file_path": filepath,
            "module_doc": extractor.module_doc,
            "classes": extractor.classes,
            "functions": extractor.functions
        }
    except Exception as e:
        print(f"Warning: Failed to parse '{filepath}' - {e}", file=sys.stderr)
        return None

def build_docs_data(target_dir: str) -> Dict[str, Dict[str, Any]]:
    """Recursively search for Python files and parse their structures."""
    docs = {}
    target_dir = os.path.abspath(target_dir)
    for root, _, files in os.walk(target_dir):
        # Ignore common directories
        if any(ignored in root for ignored in [".git", "__pycache__", "venv", ".venv", ".mypy_cache", ".pytest_cache"]):
            continue
        for file in files:
            if file.endswith(".py"):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, target_dir)
                module_name = rel_path.replace(os.path.sep, ".").rstrip(".py")
                parsed = parse_python_file(full_path)
                if parsed:
                    docs[module_name] = parsed
    return docs

def generate_html(docs_data: Dict[str, Dict[str, Any]], title: str) -> str:
    """Build the final visual HTML/CSS documentation viewer page."""
    # Build JavaScript data representation of docs for sidebar search
    modules_json_parts = []
    for mod_name, mod_info in sorted(docs_data.items()):
        escaped_doc = html.escape(mod_info["module_doc"])
        modules_json_parts.append(f"'{html.escape(mod_name)}': {{ doc: `{escaped_doc}` }}")
    
    modules_list_html = ""
    content_html = ""
    
    for mod_name, mod_info in sorted(docs_data.items()):
        mod_id = html.escape(mod_name.replace(".", "_"))
        modules_list_html += f'<li><a href="#{mod_id}" class="sidebar-link">{html.escape(mod_name)}</a></li>'
        
        # Module block
        content_html += f'<section id="{mod_id}" class="module-card">'
        content_html += f'  <div class="module-header">'
        content_html += f'    <span class="badge">Module</span>'
        content_html += f'    <h2>{html.escape(mod_name)}</h2>'
        content_html += f'    <div class="file-path">{html.escape(mod_info["file_path"])}</div>'
        content_html += f'  </div>'
        content_html += f'  <div class="module-body">'
        content_html += f'    <p class="docstring module-desc">{html.escape(mod_info["module_doc"] or "").replace("\n", "<br>")}</p>'
        
        # Classes block
        if mod_info["classes"]:
            content_html += f'    <h3>Classes</h3>'
            for cls in mod_info["classes"]:
                bases_str = f"({', '.join(cls['bases'])})" if cls['bases'] else ""
                content_html += f'    <div class="class-block">'
                content_html += f'      <div class="class-title">class <strong>{html.escape(cls["name"])}</strong>{html.escape(bases_str)}:</div>'
                content_html += f'      <div class="class-body">'
                content_html += f'        <p class="docstring">{html.escape(cls["doc"] or "").replace("\n", "<br>")}</p>'
                
                if cls["methods"]:
                    content_html += f'        <div class="methods-section">'
                    content_html += f'          <h4>Methods</h4>'
                    for method in cls["methods"]:
                        decorator_str = ""
                        if "decorators" in method and method["decorators"]:
                            decorator_str = "".join(f'<div class="decorator">@{html.escape(d)}</div>' for d in method["decorators"])
                            
                        async_kw = "async " if method["is_async"] else ""
                        content_html += f'          <div class="method-card">'
                        content_html += f'            {decorator_str}'
                        content_html += f'            <div class="func-signature">{async_kw}def <strong class="method-name">{html.escape(method["name"])}</strong>({html.escape(method["args"])}){html.escape(method["returns"])}:</div>'
                        content_html += f'            <div class="func-body">'
                        content_html += f'              <p class="docstring method-doc">{html.escape(method["doc"] or "").replace("\n", "<br>")}</p>'
                        content_html += f'            </div>'
                        content_html += f'          </div>'
                    content_html += f'        </div>'
                    
                content_html += f'      </div>'
                content_html += f'    </div>'
                
        # Independent functions block
        if mod_info["functions"]:
            content_html += f'    <h3>Functions</h3>'
            for func in mod_info["functions"]:
                async_kw = "async " if func["is_async"] else ""
                content_html += f'    <div class="func-card">'
                content_html += f'      <div class="func-signature">{async_kw}def <strong class="func-name">{html.escape(func["name"])}</strong>({html.escape(func["args"])}){html.escape(func["returns"])}:</div>'
                content_html += f'      <div class="func-body">'
                content_html += f'        <p class="docstring">{html.escape(func["doc"] or "").replace("\n", "<br>")}</p>'
                content_html += f'      </div>'
                content_html += f'    </div>'
                
        content_html += f'  </div>'
        content_html += f'</section>'

    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(title)} - API Documentation</title>
    <style>
        :root {{
            --bg-color: #0f172a;
            --sidebar-bg: #1e293b;
            --card-bg: #1e293b;
            --text-color: #f1f5f9;
            --text-muted: #94a3b8;
            --accent-color: #38bdf8;
            --border-color: #334155;
            --class-border: #f59e0b;
            --func-border: #10b981;
            --code-font: 'Fira Code', 'Courier New', Courier, monospace;
        }}
        
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            display: flex;
            height: 100vh;
            overflow: hidden;
        }}
        
        /* Sidebar layout */
        aside {{
            width: 320px;
            background-color: var(--sidebar-bg);
            border-right: 1px solid var(--border-color);
            display: flex;
            flex-direction: column;
            height: 100%;
        }}
        
        .sidebar-header {{
            padding: 20px;
            border-bottom: 1px solid var(--border-color);
        }}
        
        .sidebar-header h1 {{
            font-size: 1.25rem;
            color: var(--accent-color);
            margin-bottom: 12px;
        }}
        
        .search-box {{
            width: 100%;
            padding: 8px 12px;
            background-color: #0f172a;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            color: var(--text-color);
            font-size: 0.875rem;
        }}
        
        .search-box:focus {{
            outline: none;
            border-color: var(--accent-color);
        }}
        
        .sidebar-list {{
            flex: 1;
            overflow-y: auto;
            list-style: none;
            padding: 20px 0;
        }}
        
        .sidebar-list li a {{
            display: block;
            padding: 8px 20px;
            color: var(--text-muted);
            text-decoration: none;
            font-size: 0.9rem;
            text-overflow: ellipsis;
            white-space: nowrap;
            overflow: hidden;
        }}
        
        .sidebar-list li a:hover, .sidebar-list li a.active {{
            background-color: #334155;
            color: var(--text-color);
            border-left: 3px solid var(--accent-color);
        }}
        
        /* Main content layout */
        main {{
            flex: 1;
            padding: 40px;
            overflow-y: auto;
            scroll-behavior: smooth;
        }}
        
        .module-card {{
            background-color: var(--card-bg);
            border-radius: 12px;
            border: 1px solid var(--border-color);
            margin-bottom: 40px;
            overflow: hidden;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -2px rgba(0, 0, 0, 0.1);
        }}
        
        .module-header {{
            background-color: #0f172a;
            padding: 20px 24px;
            border-bottom: 1px solid var(--border-color);
            display: flex;
            align-items: center;
            gap: 16px;
        }}
        
        .module-header h2 {{
            font-size: 1.5rem;
        }}
        
        .badge {{
            background-color: var(--accent-color);
            color: #0f172a;
            padding: 2px 8px;
            font-size: 0.75rem;
            font-weight: bold;
            border-radius: 4px;
        }}
        
        .file-path {{
            margin-left: auto;
            font-size: 0.8rem;
            color: var(--text-muted);
            font-family: var(--code-font);
        }}
        
        .module-body {{
            padding: 24px;
        }}
        
        .docstring {{
            background-color: #0f172a;
            padding: 16px;
            border-radius: 8px;
            border-left: 4px solid var(--border-color);
            font-family: var(--code-font);
            font-size: 0.9rem;
            line-height: 1.5;
            margin: 12px 0 24px 0;
            white-space: pre-wrap;
            color: var(--text-muted);
        }}
        
        h3 {{
            font-size: 1.2rem;
            margin-top: 28px;
            margin-bottom: 12px;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 8px;
            color: var(--accent-color);
        }}
        
        /* Class block */
        .class-block {{
            border-left: 3px solid var(--class-border);
            padding-left: 20px;
            margin-bottom: 30px;
            margin-top: 16px;
        }}
        
        .class-title {{
            font-family: var(--code-font);
            font-size: 1.1rem;
            font-weight: 500;
        }}
        
        .class-body {{
            padding-top: 10px;
        }}
        
        .methods-section {{
            margin-top: 16px;
        }}
        
        .methods-section h4 {{
            font-size: 0.95rem;
            color: var(--text-muted);
            margin-bottom: 8px;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        
        /* Function/Method blocks */
        .func-card, .method-card {{
            background-color: #0f172a;
            border: 1px solid var(--border-color);
            border-radius: 6px;
            margin-bottom: 16px;
            padding: 16px;
        }}
        
        .method-card {{
            border-left: 3px solid var(--func-border);
        }}
        
        .func-signature {{
            font-family: var(--code-font);
            font-size: 0.95rem;
            color: #10b981;
        }}
        
        .func-signature strong {{
            color: var(--text-color);
        }}
        
        .func-body {{
            margin-top: 10px;
        }}
        
        .docstring.method-doc {{
            margin: 8px 0 0 0;
            padding: 10px;
            font-size: 0.85rem;
            border-left: 2px solid var(--border-color);
        }}
        
        .decorator {{
            font-family: var(--code-font);
            font-size: 0.85rem;
            color: var(--class-border);
            margin-bottom: 4px;
        }}
        
    </style>
</head>
<body>
    <aside>
        <div class="sidebar-header">
            <h1>{html.escape(title)} Docs</h1>
            <input type="text" id="search" class="search-box" placeholder="Filter modules...">
        </div>
        <ul id="sidebar-list" class="sidebar-list">
            {modules_list_html}
        </ul>
    </aside>
    <main>
        {content_html}
    </main>
    <script>
        // Sidebar filtering
        const searchInput = document.getElementById('search');
        const sidebarLinks = document.querySelectorAll('#sidebar-list li');
        
        searchInput.addEventListener('input', (e) => {{
            const query = e.target.value.toLowerCase();
            sidebarLinks.forEach(link => {{
                const text = link.innerText.toLowerCase();
                if (text.includes(query)) {{
                    link.style.display = 'block';
                }} else {{
                    link.style.display = 'none';
                }}
            }});
        }});
        
        // Highlight active link on scroll
        const sections = document.querySelectorAll('section');
        const navLi = document.querySelectorAll('#sidebar-list li a');
        const mainContainer = document.querySelector('main');
        
        mainContainer.addEventListener('scroll', () => {{
            let current = '';
            sections.forEach(section => {{
                const sectionTop = section.offsetTop;
                if (mainContainer.scrollTop >= sectionTop - 150) {{
                    current = section.getAttribute('id');
                }}
            }});
            
            navLi.forEach(a => {{
                a.classList.remove('active');
                if (a.getAttribute('href') === '#' + current) {{
                    a.classList.add('active');
                }}
            }});
        }});
    </script>
</body>
</html>
"""
    return html_template

class ThreadedHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True

def run_server(html_content: str, port: int):
    """Custom HTTP request handler serving static HTML page directly from memory."""
    class MemoryHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/" or self.path == "":
                self.send_response(200)
                self.send_header("Content-type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(html_content.encode("utf-8"))
            else:
                self.send_error(404, "File not found")
                
        def log_message(self, format, *args):
            # Suppress normal logging output to console
            pass

    server = ThreadedHTTPServer(("127.0.0.1", port), MemoryHandler)
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    return server

def main():
    parser = argparse.ArgumentParser(
        description="Python Codebase AST Documentation Server"
    )
    parser.add_argument(
        "--dir", default=".", help="Directory of python packages/modules to document (default: current directory)"
    )
    parser.add_argument(
        "--port", type=int, default=8080, help="Local HTTP server port (default: 8080)"
    )
    parser.add_argument(
        "--title", default="Codebase", help="Documentation Project Title (default: Codebase)"
    )
    parser.add_argument(
        "--no-browser", action="store_true", help="Do not open local browser automatically"
    )
    args = parser.parse_args()

    target_dir = os.path.abspath(args.dir)
    if not os.path.isdir(target_dir):
        print(f"Error: Directory '{target_dir}' does not exist.", file=sys.stderr)
        sys.exit(1)

    print(f"Analyzing codebase and building AST map for: {target_dir}...")
    docs_data = build_docs_data(target_dir)
    
    if not docs_data:
        print("No Python (.py) files found or parsed in the target directory.")
        sys.exit(0)
        
    print(f"Parsed {len(docs_data)} module(s). Generating HTML dashboard...")
    html_content = generate_html(docs_data, args.title)

    print(f"Launching documentation server at http://127.0.0.1:{args.port} ...")
    server = run_server(html_content, args.port)
    
    if not args.no_browser:
        webbrowser.open(f"http://127.0.0.1:{args.port}")
        
    print("Documentation Server is active. Press Ctrl+C to terminate.")
    try:
        # Keep main thread alive
        import time
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping Documentation Server...")
        server.shutdown()
        server.server_close()
        print("Server shutdown complete.")

if __name__ == "__main__":
    main()
