#!/usr/bin/env python3
"""
License Header Manager - Check, insert, update, or remove license headers in source files.
"""

import argparse
import os
import re
import sys
from datetime import datetime
from typing import Dict, List, Tuple

# Comment styles mapping: ext -> (start_comment, line_prefix, end_comment)
# If end_comment is empty, it's a line-by-line comment (e.g. # or //)
COMMENT_STYLES: Dict[str, Tuple[str, str, str]] = {
    ".py": ("", "# ", ""),
    ".sh": ("", "# ", ""),
    ".rb": ("", "# ", ""),
    ".pl": ("", "# ", ""),
    ".js": ("/*\n", " * ", "\n */"),
    ".ts": ("/*\n", " * ", "\n */"),
    ".tsx": ("/*\n", " * ", "\n */"),
    ".jsx": ("/*\n", " * ", "\n */"),
    ".css": ("/*\n", " * ", "\n */"),
    ".java": ("/*\n", " * ", "\n */"),
    ".cpp": ("", "// ", ""),
    ".c": ("/*\n", " * ", "\n */"),
    ".h": ("/*\n", " * ", "\n */"),
    ".cs": ("", "// ", ""),
    ".go": ("", "// ", ""),
    ".rs": ("", "// ", ""),
    ".php": ("/*\n", " * ", "\n */"),
    ".html": ("<!--\n", "  ", "\n-->"),
    ".xml": ("<!--\n", "  ", "\n-->"),
}

DEFAULT_TEMPLATE = """Copyright (c) {year} {owner}. All rights reserved.
Licensed under the MIT License. See LICENSE file in the project root for details."""

class LicenseManager:
    def __init__(self, directory: str, template: str, owner: str, year: str, extensions: List[str], dry_run: bool):
        self.directory = directory
        self.raw_template = template
        self.owner = owner
        self.year = year or str(datetime.now().year)
        self.extensions = extensions or list(COMMENT_STYLES.keys())
        self.dry_run = dry_run
        self.stats = {"checked": 0, "valid": 0, "missing": 0, "updated": 0, "added": 0, "removed": 0, "failed": 0}

    def get_license_text(self, ext: str) -> str:
        """Format raw template into file-specific comment style."""
        style = COMMENT_STYLES.get(ext)
        if not style:
            return ""

        formatted_body = self.raw_template.format(year=self.year, owner=self.owner)
        start, prefix, end = style

        lines = formatted_body.strip().split("\n")
        comment_lines = []
        if start:
            comment_lines.append(start.rstrip("\n"))
        for line in lines:
            comment_lines.append(f"{prefix}{line}".rstrip())
        if end:
            comment_lines.append(end.lstrip("\n"))

        return "\n".join(comment_lines) + "\n"

    def strip_shebang(self, content: str) -> Tuple[str, str]:
        """Separates shebang/encoding comments from the rest of the file content."""
        lines = content.splitlines(keepends=True)
        shebang_lines = []
        idx = 0
        while idx < len(lines):
            line = lines[idx]
            if line.startswith("#!") or (line.startswith("#") and ("coding:" in line or "coding=" in line)):
                shebang_lines.append(line)
                idx += 1
            elif not line.strip():
                shebang_lines.append(line)
                idx += 1
            else:
                break
        return "".join(shebang_lines), "".join(lines[idx:])

    def detect_header(self, content: str, ext: str) -> Tuple[bool, int]:
        """Detects if license header is present. Returns (has_header, header_length_chars)."""
        style = COMMENT_STYLES.get(ext)
        if not style:
            return False, 0

        start, prefix, end = style
        escaped_prefix = re.escape(prefix.strip())
        
        # Simple heuristic: Look for keywords like Copyright or License
        # inside comments at the beginning of the file (after shebang)
        lines = content.splitlines(keepends=True)
        header_lines = []
        
        in_multiline = False
        for idx, line in enumerate(lines):
            stripped = line.strip()
            
            if start and stripped.startswith(start.strip()):
                in_multiline = True
                header_lines.append(line)
                if end and stripped.endswith(end.strip()) and len(stripped) > len(start.strip()):
                    # single line multiline block
                    break
                continue
                
            if in_multiline:
                header_lines.append(line)
                if end and stripped.endswith(end.strip()):
                    break
                continue
                
            # Line by line comments
            if prefix and stripped.startswith(prefix.strip()):
                header_lines.append(line)
            else:
                break

        header_str = "".join(header_lines)
        if "Copyright" in header_str or "License" in header_str or "licensed" in header_str.lower():
            return True, len(header_str)
        return False, 0

    def process_file(self, filepath: str, action: str):
        ext = os.path.splitext(filepath)[1].lower()
        if ext not in self.extensions or ext not in COMMENT_STYLES:
            return

        self.stats["checked"] += 1
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            print(f"Error reading {filepath}: {e}")
            self.stats["failed"] += 1
            return

        shebang, main_content = self.strip_shebang(content)
        has_header, header_len = self.detect_header(main_content, ext)
        license_text = self.get_license_text(ext)

        new_content = None

        if action == "check":
            if has_header:
                self.stats["valid"] += 1
            else:
                print(f"[MISSING] {filepath}")
                self.stats["missing"] += 1

        elif action == "add":
            if has_header:
                self.stats["valid"] += 1
            else:
                new_content = shebang + license_text + "\n" + main_content
                self.stats["added"] += 1
                print(f"[ADDED] {filepath}")

        elif action == "remove":
            if has_header:
                new_content = shebang + main_content[header_len:].lstrip("\n")
                self.stats["removed"] += 1
                print(f"[REMOVED] {filepath}")
            else:
                self.stats["valid"] += 1

        elif action == "update":
            if has_header:
                # Remove old header and add new one
                new_content = shebang + license_text + "\n" + main_content[header_len:].lstrip("\n")
                self.stats["updated"] += 1
                print(f"[UPDATED] {filepath}")
            else:
                new_content = shebang + license_text + "\n" + main_content
                self.stats["added"] += 1
                print(f"[ADDED] {filepath}")

        if new_content is not None and not self.dry_run:
            try:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)
            except Exception as e:
                print(f"Error writing to {filepath}: {e}")
                self.stats["failed"] += 1

    def run(self, action: str):
        for root, _, files in os.walk(self.directory):
            # Ignore common directories
            if any(part in root.split(os.sep) for part in {".git", "node_modules", "__pycache__", "venv", ".venv", "build", "dist"}):
                continue
            for file in files:
                filepath = os.path.join(root, file)
                self.process_file(filepath, action)

def main():
    parser = argparse.ArgumentParser(description="Manage license/copyright headers in source files.")
    parser.add_argument("dir", nargs="?", default=".", help="Root directory to scan (default: current directory)")
    parser.add_argument("--action", choices=["check", "add", "remove", "update"], default="check",
                        help="Action to perform: check (default), add headers, remove headers, or update headers.")
    parser.add_argument("--owner", default="Ayush", help="Copyright owner name.")
    parser.add_argument("--year", help="Copyright year (default: current year).")
    parser.add_argument("--template-file", help="Path to a text file containing the license template.")
    parser.add_argument("--ext", help="Comma-separated file extensions to target (e.g. .py,.js,.java).")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without modifying files.")
    args = parser.parse_args()

    # Load template
    template = DEFAULT_TEMPLATE
    if args.template_file:
        try:
            with open(args.template_file, "r", encoding="utf-8") as f:
                template = f.read()
        except Exception as e:
            print(f"Failed to read template file: {e}")
            sys.exit(1)

    extensions = None
    if args.ext:
        extensions = [e.strip() if e.strip().startswith(".") else f".{e.strip()}" for e in args.ext.split(",")]

    manager = LicenseManager(
        directory=args.dir,
        template=template,
        owner=args.owner,
        year=args.year,
        extensions=extensions,
        dry_run=args.dry_run
    )

    print(f"Running '{args.action}' action on '{args.dir}'...")
    if args.dry_run:
        print("[DRY RUN MODE] No files will be modified.")
    print("-" * 50)

    manager.run(args.action)

    print("-" * 50)
    print("Execution Summary:")
    for key, val in manager.stats.items():
        print(f"  {key.capitalize()}: {val}")

    if args.action == "check" and manager.stats["missing"] > 0:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
