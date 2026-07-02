#!/usr/bin/env python3
"""
API Shadow & Zombie Endpoint Detector
Statically extracts declared API endpoints (from OpenAPI specifications or source code)
and audits them against web server access logs to locate undocumented (shadow)
and unused (zombie) routes.
"""

import sys
import os
import re
import argparse
import json
from typing import List, Set, Dict, Tuple, Optional

# Color utilities for terminal formatting
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"

def print_colored(text: str, color: str, end: str = "\n"):
    if sys.stdout.isatty():
        print(f"{color}{text}{RESET}", end=end)
    else:
        print(text, end=end)

# Simple Nginx Combined Log parser
LOG_PATTERN = re.compile(
    r'^\S+ \S+ \S+ \[([^\]]+)\] "(?P<method>[A-Z]+) (?P<url>\S+)\s+\S+" (?P<status>\d+) (?P<bytes>\S+)'
)

def convert_route_to_regex(route: str) -> re.Pattern:
    """Converts routes like /api/v1/users/{id} or /api/v1/users/:id or /api/v1/users/<id> to regex."""
    # Normalize route separators
    pattern = route.strip()
    # Replace {param}
    pattern = re.sub(r'\{[^}]+\}', r'[^/]+', pattern)
    # Replace :param
    pattern = re.sub(r':[a-zA-Z0-9_]+', r'[^/]+', pattern)
    # Replace <param>
    pattern = re.sub(r'<[^>]+>', r'[^/]+', pattern)
    
    # Ensure it matches start/end boundaries and handles trailing slash
    return re.compile(f"^{pattern}/?$", re.IGNORECASE)

def extract_declared_routes_from_spec(spec_path: str) -> List[Tuple[str, str]]:
    """Parse JSON or basic YAML OpenAPI/Swagger specs to extract methods and paths."""
    declared = []
    
    if not os.path.exists(spec_path):
        print_colored(f"Error: Specification file not found at {spec_path}", RED)
        return []
        
    try:
        with open(spec_path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            
        if spec_path.endswith(".json") or content.startswith("{"):
            spec = json.loads(content)
            paths = spec.get("paths", {})
            for path, path_data in paths.items():
                for method, _ in path_data.items():
                    if method.upper() in ["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"]:
                        declared.append((method.upper(), path))
        else:
            # Very primitive yaml fallback line parser
            # Handles '  /api/v1/users:' followed by '    get:'
            curr_path = None
            for line in content.splitlines():
                # Matches paths
                path_match = re.match(r'^\s{2}(/[a-zA-Z0-9_\-\/{}:<>]+):', line)
                if path_match:
                    curr_path = path_match.group(1)
                elif curr_path:
                    # Matches methods
                    method_match = re.match(r'^\s{4}(get|post|put|delete|patch|options|head):', line)
                    if method_match:
                        declared.append((method_match.group(1).upper(), curr_path))
    except Exception as e:
        print_colored(f"Error reading spec file: {e}", RED)
        
    return declared

def extract_declared_routes_from_code(code_dir: str) -> List[Tuple[str, str]]:
    """Statically scans Python source code for Flask/FastAPI route decorators."""
    declared = []
    
    # regexes to extract decorators
    # e.g., @app.get("/api/v1/users") or @app.route("/api/v1/users", methods=["POST"])
    fastapi_pattern = re.compile(r'@\w+\.(get|post|put|delete|patch|route)\(\s*["\']([^"\']+)["\']')
    flask_pattern = re.compile(r'@\w+\.route\(\s*["\']([^"\']+)["\'](?:\s*,\s*methods\s*=\s*\[([^\]]+)\])?')
    
    for root, _, files in os.walk(code_dir):
        for file in files:
            if file.endswith(".py"):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                        for line in f:
                            # 1. Check FastAPI syntax
                            fa_match = fastapi_pattern.search(line)
                            if fa_match:
                                method = fa_match.group(1).upper()
                                path = fa_match.group(2)
                                if method == "ROUTE": # standard default
                                    method = "GET"
                                declared.append((method, path))
                                continue
                                
                            # 2. Check Flask syntax
                            fl_match = flask_pattern.search(line)
                            if fl_match:
                                path = fl_match.group(1)
                                methods_str = fl_match.group(2)
                                if methods_str:
                                    methods = [m.strip().replace('"', '').replace("'", '').upper() for m in methods_str.split(",")]
                                    for m in methods:
                                        declared.append((m, path))
                                else:
                                    declared.append(("GET", path))
                except Exception as e:
                    print_colored(f"Error scanning {filepath}: {e}", RED)
                    
    return list(set(declared))

def parse_access_logs(log_path: str) -> List[Tuple[str, str]]:
    """Parses access logs and yields tuples of (HTTP Method, URL Path)."""
    hits = []
    if not os.path.exists(log_path):
        print_colored(f"Error: Log file not found at {log_path}", RED)
        return []
        
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                match = LOG_PATTERN.match(line.strip())
                if match:
                    method = match.group("method").upper()
                    url = match.group("url")
                    # Clean up URL parameters/query string
                    path = url.split("?")[0]
                    # Clean trailing/multiple slashes
                    path = "/" + "/".join(filter(None, path.split("/")))
                    hits.append((method, path))
    except Exception as e:
        print_colored(f"Error parsing log file: {e}", RED)
        
    return hits

def main():
    parser = argparse.ArgumentParser(
        description="API Shadow & Zombie Endpoint Detector",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python api_endpoint_shadow_detector.py --spec openapi.json --logs access.log
  python api_endpoint_shadow_detector.py --code-dir ./src --logs /var/log/nginx/access.log
  python api_endpoint_shadow_detector.py --spec swagger.yaml --logs access.log --ignore-static
        """
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-s", "--spec", type=str, help="Path to OpenAPI/Swagger specification file")
    group.add_argument("-c", "--code-dir", type=str, help="Path to source code directory to scan statically")
    
    parser.add_argument("-l", "--logs", type=str, required=True, help="Path to web server access log file")
    parser.add_argument("--ignore-static", action="store_true", help="Ignore common static file extensions (css, js, png, etc.)")
    
    args = parser.parse_args()

    # 1. Load declared endpoints
    declared: List[Tuple[str, str]] = []
    if args.spec:
        print_colored(f"Scanning specification file: {args.spec}...", BOLD)
        declared = extract_declared_routes_from_spec(args.spec)
    elif args.code_dir:
        print_colored(f"Scanning codebase: {args.code_dir}...", BOLD)
        declared = extract_declared_routes_from_code(args.code_dir)
        
    if not declared:
        print_colored("No declared routes found.", YELLOW)
        sys.exit(1)
        
    print(f"Loaded {len(declared)} declared route-method combinations.")

    # Convert declared routes to compiled regex objects
    route_regexes: List[Tuple[str, str, re.Pattern]] = [
        (method, path, convert_route_to_regex(path)) for method, path in declared
    ]

    # 2. Parse logs
    print_colored(f"Parsing access logs: {args.logs}...", BOLD)
    log_hits = parse_access_logs(args.logs)
    if not log_hits:
        print_colored("No hits parsed from access logs.", YELLOW)
        sys.exit(1)
        
    print(f"Parsed {len(log_hits)} request lines from log file.")

    # 3. Audit endpoints
    shadow_endpoints: Set[Tuple[str, str]] = set()
    zombie_endpoints: Set[Tuple[str, str]] = set(declared)
    matched_counts: Dict[Tuple[str, str], int] = {route: 0 for route in declared}
    
    static_extensions = {".css", ".js", ".png", ".jpg", ".jpeg", ".gif", ".ico", ".svg", ".woff", ".woff2", ".txt"}

    for method, path in log_hits:
        # Ignore common static assets
        if args.ignore_static:
            _, ext = os.path.splitext(path)
            if ext.lower() in static_extensions:
                continue
                
        # Find matching declared route
        matched = False
        for decl_method, decl_path, regex in route_regexes:
            if method == decl_method and regex.match(path):
                matched = True
                route_key = (decl_method, decl_path)
                matched_counts[route_key] += 1
                if route_key in zombie_endpoints:
                    zombie_endpoints.remove(route_key)
                break
                
        if not matched:
            # It's a Shadow API (called in production but undocumented)
            shadow_endpoints.add((method, path))

    # 4. Print reports
    print("\n" + "=" * 80)
    print_colored(f"{BOLD}API AUDIT SUMMARY REPORT{RESET}", BOLD)
    print("=" * 80)

    # 4a. Zombie endpoints
    print_colored(f"\n[!] Zombie Endpoints ({len(zombie_endpoints)}) - Declared but NEVER hit in logs:", YELLOW)
    if zombie_endpoints:
        for method, path in sorted(zombie_endpoints):
            print(f"  - {method:<6} {path}")
    else:
        print_colored("  None! All declared endpoints were called at least once.", GREEN)

    # 4b. Shadow endpoints
    print_colored(f"\n[!] Shadow Endpoints ({len(shadow_endpoints)}) - Undocumented hits found in logs:", RED)
    if shadow_endpoints:
        for method, path in sorted(shadow_endpoints):
            print(f"  - {method:<6} {path}")
    else:
        print_colored("  None! No undocumented endpoints were called.", GREEN)

    # 4c. Route usage statistics
    print_colored(f"\n[+] Active Endpoints Usage Statistics:", GREEN)
    active_routes = {k: v for k, v in matched_counts.items() if v > 0}
    if active_routes:
        for (method, path), count in sorted(active_routes.items(), key=lambda x: x[1], reverse=True):
            print(f"  - {count:5d} hits: {method:<6} {path}")
    else:
        print("  No hits matched documented endpoints.")

if __name__ == "__main__":
    main()
