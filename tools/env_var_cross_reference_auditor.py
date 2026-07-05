#!/usr/bin/env python3
"""
Environment Variable Cross-Reference Auditor

Scans codebase files (.py, .js, .ts, .sh, Dockerfile, yaml) for environment variable
usages (os.environ, process.env, $VAR) and cross-references them against definition files
(.env, .env.example, etc.) to detect missing, unused, or insecure default variables.

Author: Python Tools Collection
License: MIT
"""

import os
import sys
import re
import json
import argparse
from pathlib import Path
from typing import Dict, Set, List, Tuple


# Regex patterns to catch env var usages in code
ENV_CODE_PATTERNS = [
    # Python: os.environ.get('VAR'), os.environ['VAR'], os.getenv('VAR')
    (r'os\.(?:environ\.get|getenv|environ\[)\s*\(\s*["\']([A-Z0-9_]+)["\']', 'Python'),
    # JS/TS: process.env.VAR, process.env['VAR']
    (r'process\.env\.(?:[A-Z0-9_]+)|process\.env\[["\']([A-Z0-9_]+)["\']\]', 'JavaScript/TypeScript'),
    # Shell / Docker / Compose: $VAR, ${VAR}
    (r'\$\{?([A-Z0-9_]{2,})\}?', 'Shell/Docker'),
]


def parse_env_file(file_path: Path) -> Dict[str, str]:
    env_vars = {}
    if not file_path.exists():
        return env_vars
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
        for line in content.splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                env_vars[key.strip()] = val.strip()
    except Exception:
        pass
    return env_vars


def scan_codebase_references(root_path: Path, ignore_dirs: Set[str]) -> Dict[str, Set[str]]:
    references = {}  # var_name -> set of file paths

    for path in root_path.rglob("*"):
        if path.is_file():
            if any(part in ignore_dirs or part.startswith(".") for part in path.parts[:-1]):
                continue
            if path.suffix.lower() in [".py", ".js", ".ts", ".jsx", ".tsx", ".sh", ".bash", ".yml", ".yaml"] or path.name in ["Dockerfile", "docker-compose.yml"]:
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                    rel_path = str(path.relative_to(root_path))

                    for pattern, lang in ENV_CODE_PATTERNS:
                        for match in re.finditer(pattern, text):
                            # Grab capture group
                            var_name = match.group(1) if match.lastindex else match.group(0)
                            if var_name:
                                # Strip process.env. if caught whole
                                if var_name.startswith("process.env."):
                                    var_name = var_name[12:]
                                var_name = var_name.strip("${}")
                                if len(var_name) >= 2 and var_name.isupper():
                                    references.setdefault(var_name, set()).add(rel_path)
                except Exception:
                    pass

    return references


def main():
    parser = argparse.ArgumentParser(
        description="Cross-reference codebase environment variable usage against .env definition files."
    )
    parser.add_argument("path", nargs="?", default=".", help="Path to project codebase root (default: current directory)")
    parser.add_argument("--env-file", default=".env", help="Primary environment file (default: .env)")
    parser.add_argument("--example-file", default=".env.example", help="Example environment template file (default: .env.example)")
    parser.add_argument("--ignore-dirs", default="node_modules,.git,venv,__pycache__,dist,build", help="Comma-separated directories to ignore")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--strict", action="store_true", help="Exit with non-zero status if missing variables are detected")

    args = parser.parse_args()
    root_path = Path(args.path).resolve()

    if not root_path.exists():
        print(f"Error: Path '{root_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    ignore_dirs = set(d.strip() for d in args.ignore_dirs.split(","))

    env_path = root_path / args.env_file
    example_path = root_path / args.example_file

    env_vars = parse_env_file(env_path)
    example_vars = parse_env_file(example_path)

    defined_vars = set(env_vars.keys()) | set(example_vars.keys())

    code_references = scan_codebase_references(root_path, ignore_dirs)
    used_vars = set(code_references.keys())

    missing_in_env = sorted(list(used_vars - defined_vars))
    unused_in_code = sorted(list(defined_vars - used_vars))
    missing_in_example = sorted(list(used_vars - set(example_vars.keys())))

    results = {
        "project_root": str(root_path),
        "env_file_found": env_path.exists(),
        "example_file_found": example_path.exists(),
        "total_referenced_in_code": len(used_vars),
        "total_defined_in_env": len(defined_vars),
        "missing_in_env_files": [
            {"var": var, "referenced_in": sorted(list(code_references[var]))}
            for var in missing_in_env
        ],
        "unused_in_codebase": unused_in_code,
        "missing_in_example_file": missing_in_example
    }

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print("=== Environment Variable Cross-Reference Audit ===")
        print(f"Project Path      : {root_path}")
        print(f"Primary Env File  : {args.env_file} ({'FOUND' if env_path.exists() else 'NOT FOUND'})")
        print(f"Example Env File  : {args.example_file} ({'FOUND' if example_path.exists() else 'NOT FOUND'})")
        print(f"Vars In Codebase  : {len(used_vars)}")
        print(f"Vars In Config    : {len(defined_vars)}")

        if missing_in_env:
            print(f"\n[!] MISSING VARIABLES ({len(missing_in_env)} referenced in code but absent from env files):")
            for var in missing_in_env:
                files = ", ".join(sorted(list(code_references[var]))[:3])
                print(f"  - {var:<25} (Used in: {files})")
        else:
            print("\n[✓] No missing environment variables detected.")

        if unused_in_code:
            print(f"\n[?] UNUSED VARIABLES ({len(unused_in_code)} defined in env files but never referenced):")
            for var in unused_in_code:
                print(f"  - {var}")

        if example_path.exists() and missing_in_example:
            print(f"\n[!] MISSING FROM {args.example_file} ({len(missing_in_example)}):")
            for var in missing_in_example:
                print(f"  - {var}")

    if args.strict and missing_in_env:
        sys.exit(1)


if __name__ == "__main__":
    main()
