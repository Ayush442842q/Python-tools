#!/usr/bin/env python3
import os
import re
import argparse
import sys
from collections import defaultdict

# Simple ANSI colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[34m"
COLOR_CYAN = "\033[36m"

# Regex for extracting routes from Python codebase
# 1. FastAPI router style: @app.get("/path") or @router.post("/path/{id}")
FASTAPI_ROUTE_REGEX = re.compile(
    r'@(?:app|router)\.(get|post|put|delete|patch|options|head)\s*\(\s*["\']([^"\'\?]+)["\']',
    re.IGNORECASE
)

# 2. Flask style: @app.route("/path", methods=["GET", "POST"])
FLASK_ROUTE_REGEX = re.compile(
    r'@(?:app|blueprint)\.route\s*\(\s*["\']([^"\'\?]+)["\'](?:,\s*methods\s*=\s*\[([^\]]+)\])?',
    re.IGNORECASE
)

# Regex to detect API signatures in Markdown
# Typical pattern: "GET /api/v1/users" or "**POST** `/api/v2/items`" or inside list/table items
MARKDOWN_ROUTE_REGEX = re.compile(
    r'\b(GET|POST|PUT|DELETE|PATCH)\b[\s`*#_-]+(/[a-zA-Z0-9_\-\/\{\}]+)',
    re.IGNORECASE
)

def parse_python_routes(file_path):
    """
    Parses a python file to extract API endpoints.
    Returns set of tuples: (method, path)
    """
    routes = set()
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        print(f"{COLOR_RED}Error reading {file_path}: {e}{COLOR_RESET}")
        return routes

    # 1. Check FastAPI patterns
    for match in FASTAPI_ROUTE_REGEX.finditer(content):
        method = match.group(1).upper()
        path = normalize_path(match.group(2))
        routes.add((method, path))

    # 2. Check Flask patterns
    for match in FLASK_ROUTE_REGEX.finditer(content):
        path = normalize_path(match.group(1))
        methods_str = match.group(2)
        if methods_str:
            # Extract individual methods e.g. ["GET", "POST"] -> GET, POST
            methods = re.findall(r'["\'](\w+)["\']', methods_str)
            for m in methods:
                routes.add((m.upper(), path))
        else:
            # Default method in Flask is GET
            routes.add(("GET", path))

    return routes

def parse_markdown_routes(file_path):
    """
    Parses a markdown file to extract documented API routes.
    Returns set of tuples: (method, path)
    """
    routes = set()
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
    except Exception as e:
        print(f"{COLOR_RED}Error reading {file_path}: {e}{COLOR_RESET}")
        return routes

    for match in MARKDOWN_ROUTE_REGEX.finditer(content):
        method = match.group(1).upper()
        path = normalize_path(match.group(2))
        routes.add((method, path))

    return routes

def normalize_path(path):
    """
    Normalizes path formatting, e.g. /users/{id} vs /users/<id> vs /users/:id.
    We convert route parameters to a uniform {param} notation.
    """
    # Remove leading/trailing spaces and slashes
    path = path.strip()
    
    # Replace Flask syntax: <int:id> or <id> with {id}
    path = re.sub(r'<[^:>]+:([^>]+)>', r'{\1}', path)
    path = re.sub(r'<([^>]+)>', r'{\1}', path)
    
    # Replace Express style syntax: :id with {id}
    path = re.sub(r':([a-zA-Z0-9_]+)', r'{\1}', path)
    
    # Ensure it starts with a slash
    if not path.startswith('/'):
        path = '/' + path
        
    # Remove trailing slash unless it's just '/'
    if len(path) > 1 and path.endswith('/'):
        path = path[:-1]
        
    return path

def main():
    parser = argparse.ArgumentParser(
        description="Statically audit Python web route coverage against Markdown documentation."
    )
    parser.add_argument("code_dir", help="Path to Python codebase directory/file")
    parser.add_argument("docs_dir", help="Path to Markdown documentation directory/file")
    args = parser.parse_args()

    if not os.path.exists(args.code_dir):
        print(f"{COLOR_RED}Error: Code path '{args.code_dir}' does not exist.{COLOR_RESET}")
        sys.exit(1)
        
    if not os.path.exists(args.docs_dir):
        print(f"{COLOR_RED}Error: Docs path '{args.docs_dir}' does not exist.{COLOR_RESET}")
        sys.exit(1)

    print(f"{COLOR_BOLD}{COLOR_GREEN}Starting API Specification & Sync Auditor...{COLOR_RESET}")
    print("-" * 70)

    # 1. Discover all backend routes
    backend_routes = set()
    if os.path.isfile(args.code_dir):
        if args.code_dir.endswith(".py"):
            backend_routes.update(parse_python_routes(args.code_dir))
    else:
        for root, _, files in os.walk(args.code_dir):
            if "node_modules" in root or ".git" in root or "venv" in root or "__pycache__" in root:
                continue
            for file in files:
                if file.endswith(".py"):
                    backend_routes.update(parse_python_routes(os.path.join(root, file)))

    # 2. Discover all documented routes
    doc_routes = set()
    if os.path.isfile(args.docs_dir):
        if args.docs_dir.endswith(".md"):
            doc_routes.update(parse_markdown_routes(args.docs_dir))
    else:
        for root, _, files in os.walk(args.docs_dir):
            if "node_modules" in root or ".git" in root:
                continue
            for file in files:
                if file.lower().endswith(".md"):
                    doc_routes.update(parse_markdown_routes(os.path.join(root, file)))

    # 3. Analyze sync differences
    undocumented_routes = backend_routes - doc_routes
    obsolete_docs = doc_routes - backend_routes
    
    # Find matching paths with mismatching methods
    backend_paths = {path: method for method, path in backend_routes}
    doc_paths = {path: method for method, path in doc_routes}
    
    mismatched_methods = []
    # If path exists in both, but method pairs are different
    for method, path in backend_routes:
        for d_method, d_path in doc_routes:
            if path == d_path and method != d_method:
                # Make sure we don't have this method supported (e.g. if endpoint supports multiple methods)
                # If backend supports GET but docs have POST, check if backend also supports POST
                if (d_method, path) not in backend_routes:
                    mismatched_methods.append((path, method, d_method))

    # Remove duplicates from mismatches
    mismatched_methods = list(set(mismatched_methods))

    # Print results
    print(f"{COLOR_BOLD}Analysis Summary:{COLOR_RESET}")
    print(f"  Backend routes found: {len(backend_routes)}")
    print(f"  Documented routes found: {len(doc_routes)}")
    print("-" * 70)

    has_errors = False

    if undocumented_routes:
        has_errors = True
        print(f"{COLOR_RED}{COLOR_BOLD}Undocumented Backend Endpoints (Found in code, missing in docs):{COLOR_RESET}")
        for method, path in sorted(undocumented_routes):
            print(f"  - {COLOR_RED}{method.upper():<6}{COLOR_RESET} {path}")
            
    if obsolete_docs:
        has_errors = True
        print(f"\n{COLOR_YELLOW}{COLOR_BOLD}Obsolete / Non-Existent Documented Endpoints (Found in docs, missing in code):{COLOR_RESET}")
        for method, path in sorted(obsolete_docs):
            print(f"  - {COLOR_YELLOW}{method.upper():<6}{COLOR_RESET} {path}")

    if mismatched_methods:
        has_errors = True
        print(f"\n{COLOR_RED}{COLOR_BOLD}Method Mismatches:{COLOR_RESET}")
        for path, b_method, d_method in sorted(mismatched_methods):
            print(f"  - {path}: Backend has {COLOR_RED}{b_method}{COLOR_RESET}, but Docs specify {COLOR_YELLOW}{d_method}{COLOR_RESET}")

    if not has_errors:
        print(f"{COLOR_GREEN}Success: API documentation and backend code are perfectly in sync!{COLOR_RESET}")
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
