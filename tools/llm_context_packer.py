#!/usr/bin/env python3
"""
LLM Context Packer
Recursively scans a directory, filters files by extension, respects exclusions,
and packages the entire codebase into a single formatted Markdown file.
Highly useful for providing source code context to LLMs.

Usage:
    python tools/llm_context_packer.py
    python tools/llm_context_packer.py /path/to/project -e .py,.json -o context.md
    python tools/llm_context_packer.py -c  # Package and copy directly to clipboard
"""

import argparse
import fnmatch
import os
import sys

# ANSI Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
CYAN = "\033[36m"
BOLD = "\033[1m"
RESET = "\033[0m"

DEFAULT_EXCLUDES = [
    '.git', '__pycache__', 'node_modules', '.venv', 'venv', 'env', 
    'dist', 'build', '.idea', '.vscode', '.pytest_cache', '.mypy_cache',
    '*.pyc', '*.pyo', '*.pyd', '*.db', '*.sqlite', '*.png', '*.jpg', 
    '*.jpeg', '*.gif', '*.ico', '*.pdf', '*.zip', '*.tar', '*.gz',
    'package-lock.json', 'yarn.lock', 'pnpm-lock.yaml'
]

def copy_to_clipboard(text):
    """Copies text to the clipboard across Windows, macOS, and Linux without external dependencies."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes
        
        # Define necessary Windows API elements
        OpenClipboard = ctypes.windll.user32.OpenClipboard
        EmptyClipboard = ctypes.windll.user32.EmptyClipboard
        SetClipboardData = ctypes.windll.user32.SetClipboardData
        CloseClipboard = ctypes.windll.user32.CloseClipboard
        
        GlobalAlloc = ctypes.windll.kernel32.GlobalAlloc
        GlobalLock = ctypes.windll.kernel32.GlobalLock
        GlobalUnlock = ctypes.windll.kernel32.GlobalUnlock
        memcpy = ctypes.cdll.msvcrt.memcpy
        
        GMEM_MOVEABLE = 0x0002
        CF_UNICODETEXT = 13
        
        # Convert to UTF-16
        text_utf16 = text.encode('utf-16le') + b'\x00\x00'
        
        if not OpenClipboard(None):
            return False
            
        try:
            EmptyClipboard()
            h_cd = GlobalAlloc(GMEM_MOVEABLE, len(text_utf16))
            if not h_cd:
                return False
            
            ptr = GlobalLock(h_cd)
            try:
                memcpy(ptr, text_utf16, len(text_utf16))
            finally:
                GlobalUnlock(h_cd)
                
            SetClipboardData(CF_UNICODETEXT, h_cd)
        finally:
            CloseClipboard()
        return True
    elif sys.platform == "darwin":
        import subprocess
        process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE)
        process.communicate(text.encode('utf-8'))
        return process.returncode == 0
    else:  # Linux / Unix
        import subprocess
        for cmd in [['xclip', '-selection', 'clipboard'], ['xsel', '-i', '-b']]:
            try:
                process = subprocess.Popen(cmd, stdin=subprocess.PIPE)
                process.communicate(text.encode('utf-8'))
                if process.returncode == 0:
                    return True
            except FileNotFoundError:
                continue
        return False

def build_tree_structure(root_dir, include_exts, exclude_patterns):
    """Generates a text representation of the directory tree."""
    tree_lines = []
    
    def _walk(directory, prefix=""):
        try:
            entries = sorted(os.listdir(directory))
        except PermissionError:
            return

        # Filter out excluded items
        filtered_entries = []
        for entry in entries:
            full_path = os.path.join(directory, entry)
            
            # Check exclusions
            is_excluded = False
            for pattern in exclude_patterns:
                if fnmatch.fnmatch(entry, pattern) or fnmatch.fnmatch(full_path, pattern):
                    is_excluded = True
                    break
            if is_excluded:
                continue
                
            if os.path.isdir(full_path):
                filtered_entries.append((entry, True))
            else:
                # Check extension filter
                ext = os.path.splitext(entry)[1].lower()
                if not include_exts or ext in include_exts:
                    filtered_entries.append((entry, False))

        for i, (name, is_dir) in enumerate(filtered_entries):
            is_last = (i == len(filtered_entries) - 1)
            connector = "└── " if is_last else "├── "
            
            if is_dir:
                tree_lines.append(f"{prefix}{connector}{name}/")
                new_prefix = prefix + ("    " if is_last else "│   ")
                _walk(os.path.join(directory, name), new_prefix)
            else:
                tree_lines.append(f"{prefix}{connector}{name}")

    tree_lines.append(f"{os.path.basename(os.path.abspath(root_dir))}/")
    _walk(root_dir)
    return "\n".join(tree_lines)

def main():
    parser = argparse.ArgumentParser(
        description="Package codebase files into a single structured Markdown file for LLM usage."
    )
    parser.add_argument("directory", nargs="?", default=".", help="Root directory to scan (default: current directory)")
    parser.add_argument("-e", "--extensions", help="Comma-separated file extensions to include (e.g. '.py,.js,.md')")
    parser.add_argument("-o", "--output", help="Output file path (saves format output to file).")
    parser.add_argument("-c", "--clipboard", action="store_true", help="Copy the generated context directly to clipboard.")
    parser.add_argument("--exclude", help="Additional comma-separated patterns to exclude.")
    
    args = parser.parse_args()

    root_dir = os.path.abspath(args.directory)
    if not os.path.isdir(root_dir):
        print(f"{RED}[ERROR] Directory '{root_dir}' does not exist.{RESET}", file=sys.stderr)
        sys.exit(1)

    # Parse extensions
    include_exts = set()
    if args.extensions:
        include_exts = {ext.strip().lower() for ext in args.extensions.split(',')}
        # Ensure they start with a dot
        include_exts = {ext if ext.startswith('.') else f".{ext}" for ext in include_exts}

    # Parse exclusions
    exclude_patterns = list(DEFAULT_EXCLUDES)
    if args.exclude:
        exclude_patterns.extend([p.strip() for p in args.exclude.split(',')])

    print(f"{BOLD}LLM Context Packer{RESET}")
    print(f"Scanning: {CYAN}{root_dir}{RESET}")
    if include_exts:
        print(f"Filtering extensions: {', '.join(include_exts)}")
    print("-" * 60)

    # Build the tree structure
    print("Building directory tree...")
    tree_text = build_tree_structure(root_dir, include_exts, exclude_patterns)
    
    # Gather code files contents
    output_parts = [
        "# Codebase Context Export",
        f"**Source Directory:** `{root_dir}`  ",
        f"**Filters:** Extensions: `{', '.join(include_exts) if include_exts else 'All text'}`  \n",
        "## Directory Structure",
        "```text",
        tree_text,
        "```\n",
        "## Source Code Contents",
        "---"
    ]

    total_files = 0
    total_chars = 0

    for root, dirs, files in os.walk(root_dir):
        # Exclude directories in-place to prevent os.walk from entering them
        dirs[:] = [
            d for d in dirs 
            if not any(fnmatch.fnmatch(d, p) or fnmatch.fnmatch(os.path.join(root, d), p) for p in exclude_patterns)
        ]

        for file in files:
            full_path = os.path.join(root, file)
            
            # Check file exclusion
            if any(fnmatch.fnmatch(file, p) or fnmatch.fnmatch(full_path, p) for p in exclude_patterns):
                continue

            # Check extension filter
            ext = os.path.splitext(file)[1].lower()
            if include_exts and ext not in include_exts:
                continue

            # Check if file is text and read its contents
            try:
                with open(full_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
                
                # Exclude binary files (e.g. check for NUL bytes)
                if '\x00' in content:
                    continue
                    
                rel_path = os.path.relpath(full_path, root_dir)
                print(f" Packing: {rel_path} ({len(content):,} chars)")
                
                # Determine language for markdown code blocks
                lang_map = {
                    '.py': 'python', '.js': 'javascript', '.ts': 'typescript', 
                    '.html': 'html', '.css': 'css', '.json': 'json', 
                    '.sh': 'bash', '.md': 'markdown', '.yml': 'yaml', 
                    '.yaml': 'yaml', '.toml': 'toml', '.xml': 'xml'
                }
                lang = lang_map.get(ext, '')

                output_parts.append(f"### File: `{rel_path}`")
                output_parts.append(f"```{lang}")
                output_parts.append(content)
                output_parts.append("```\n---\n")

                total_files += 1
                total_chars += len(content)

            except Exception as e:
                print(f" {YELLOW}[SKIP] Could not read {file}: {e}{RESET}")

    final_content = "\n".join(output_parts)
    # Estimate tokens: ~4 characters per token average
    est_tokens = int(total_chars / 4)

    print("-" * 60)
    print(f"{GREEN}[PASS] Packed {total_files} files.{RESET}")
    print(f"Total size: {total_chars:,} characters (~{est_tokens:,} estimated tokens)")

    # Output handling
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(final_content)
            print(f"{GREEN}[PASS] Saved output to: {args.output}{RESET}")
        except Exception as e:
            print(f"{RED}[ERROR] Failed to save output file: {e}{RESET}", file=sys.stderr)
            sys.exit(1)

    if args.clipboard:
        print("Copying package to clipboard...")
        if copy_to_clipboard(final_content):
            print(f"{GREEN}[PASS] Copied to clipboard successfully!{RESET}")
        else:
            print(f"{RED}[ERROR] Failed to copy to clipboard (missing CLI tool/error).{RESET}", file=sys.stderr)

    if not args.output and not args.clipboard:
        # Just write to stdout if neither is set
        print(final_content)

    return 0

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(1)
