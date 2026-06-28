#!/usr/bin/env python3
"""
Environment Variable Documentation Generator
Scans codebase directories recursively for environment variable references (Python, JavaScript/TypeScript, Go, Shell)
and generates a structured Markdown documentation file summarizing their usage, source files, and default values.
"""

import os
import re
import argparse
import sys
from collections import defaultdict

# Regex patterns for environment variables in different languages
PATTERNS = {
    'python': [
        # os.environ.get('VAR', 'default') or os.environ.get("VAR")
        r'os\.environ\.get\(\s*[\'"](?P<name>[A-Za-z0-9_]+)[\'"]\s*(?:,\s*(?P<default>[^\)]+))?\s*\)',
        # os.getenv('VAR', 'default') or os.getenv("VAR")
        r'os\.getenv\(\s*[\'"](?P<name>[A-Za-z0-9_]+)[\'"]\s*(?:,\s*(?P<default>[^\)]+))?\s*\)',
        # os.environ['VAR'] or os.environ["VAR"]
        r'os\.environ\[\s*[\'"](?P<name>[A-Za-z0-9_]+)[\'"]\s*\]'
    ],
    'javascript': [
        # process.env.VAR
        r'process\.env\.(?P<name>[A-Za-z0-9_]+)',
        # process.env['VAR'] or process.env["VAR"]
        r'process\.env\[\s*[\'"](?P<name>[A-Za-z0-9_]+)[\'"]\s*\]'
    ],
    'go': [
        # os.Getenv("VAR")
        r'os\.Getenv\(\s*[\'"](?P<name>[A-Za-z0-9_]+)[\'"]\s*\)'
    ],
    'shell': [
        # $VAR or ${VAR}
        r'\$(?P<name>[A-Z0-9_]{3,})\b',
        r'\$\{(?P<name>[A-Z0-9_]{3,})(?::?-(?P<default>[^}]+))?\}'
    ]
}

# File extensions mapped to languages
EXT_MAP = {
    '.py': 'python',
    '.js': 'javascript',
    '.ts': 'javascript',
    '.jsx': 'javascript',
    '.tsx': 'javascript',
    '.go': 'go',
    '.sh': 'shell',
    '.bash': 'shell'
}

def clean_default_val(val_str):
    if not val_str:
        return 'N/A'
    val_str = val_str.strip()
    # Strip quotes
    if (val_str.startswith("'") and val_str.endswith("'")) or (val_str.startswith('"') and val_str.endswith('"')):
        return val_str[1:-1]
    return val_str

def extract_env_vars(filepath, language):
    results = []
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except Exception as e:
        print(f"Warning: Could not read {filepath}: {e}", file=sys.stderr)
        return results

    for line_idx, line in enumerate(lines):
        for pattern in PATTERNS[language]:
            for match in re.finditer(pattern, line):
                groups = match.groupdict()
                var_name = groups.get('name')
                if not var_name:
                    continue
                
                # Exclude shell keywords/common false positives
                if language == 'shell' and var_name in ('PATH', 'HOME', 'USER', 'SHELL', 'PWD', 'LANG', 'LC_ALL'):
                    continue

                default_val = clean_default_val(groups.get('default'))
                
                # Try to find description in comments on current line or preceding 3 lines
                description = "No description provided."
                comment_lines = []
                
                # Check current line comment
                if '#' in line:
                    parts = line.split('#', 1)
                    if len(parts) > 1 and parts[1].strip():
                        comment_lines.append(parts[1].strip())
                elif '//' in line:
                    parts = line.split('//', 1)
                    if len(parts) > 1 and parts[1].strip():
                        comment_lines.append(parts[1].strip())

                # Check preceding lines
                for prev_idx in range(max(0, line_idx - 3), line_idx):
                    prev_line = lines[prev_idx].strip()
                    if language in ('python', 'shell') and prev_line.startswith('#'):
                        comment_lines.append(prev_line.lstrip('#').strip())
                    elif language in ('javascript', 'go') and prev_line.startswith('//'):
                        comment_lines.append(prev_line.lstrip('/').strip())
                    elif language in ('javascript', 'go') and prev_line.startswith('/*') and prev_line.endswith('*/'):
                        comment_lines.append(prev_line.strip('/*').strip('*/').strip())
                
                if comment_lines:
                    description = ' '.join(comment_lines).strip()
                
                results.append({
                    'name': var_name,
                    'file': filepath,
                    'line': line_idx + 1,
                    'default': default_val,
                    'description': description
                })
    return results

def main():
    parser = argparse.ArgumentParser(description="Scan a directory for environment variables and generate Markdown documentation.")
    parser.add_argument("directory", nargs="?", default=".", help="Directory to scan (default: current directory)")
    parser.add_argument("-o", "--output", help="Output file path (default: prints to stdout)")
    parser.add_argument("--exclude-dirs", nargs="+", default=["venv", "node_modules", ".git", "__pycache__", "build", "dist"],
                        help="Subdirectories to exclude from the scan")
    
    args = parser.parse_args()
    
    scan_dir = os.path.abspath(args.directory)
    if not os.path.exists(scan_dir):
        print(f"Error: Directory '{scan_dir}' does not exist.", file=sys.stderr)
        sys.exit(1)
        
    print(f"Scanning '{scan_dir}' recursively for environment variables...", file=sys.stderr)
    
    env_vars = defaultdict(list)
    
    for root, dirs, files in os.walk(scan_dir):
        # Exclude directories in-place
        dirs[:] = [d for d in dirs if d not in args.exclude_dirs]
        
        for file in files:
            ext = os.path.splitext(file)[1].lower()
            if ext in EXT_MAP:
                lang = EXT_MAP[ext]
                filepath = os.path.join(root, file)
                rel_path = os.path.relpath(filepath, scan_dir).replace('\\', '/')
                findings = extract_env_vars(filepath, lang)
                for f in findings:
                    f['rel_file'] = rel_path
                    env_vars[f['name']].append(f)
                    
    if not env_vars:
        print("No environment variables found.", file=sys.stderr)
        return

    # Generate Markdown documentation
    markdown_lines = []
    markdown_lines.append("# Environment Variables Documentation")
    markdown_lines.append("")
    markdown_lines.append(f"Auto-generated by scanning directory: `{os.path.basename(scan_dir)}`")
    markdown_lines.append("")
    markdown_lines.append("| Variable Name | Default Value | Usage Location(s) | Description |")
    markdown_lines.append("| --- | --- | --- | --- |")
    
    for var_name in sorted(env_vars.keys()):
        occurrences = env_vars[var_name]
        # Aggregate default values and descriptions
        defaults = list(set(o['default'] for o in occurrences if o['default'] != 'N/A'))
        default_str = ", ".join(defaults) if defaults else "N/A"
        
        descriptions = list(set(o['description'] for o in occurrences if o['description'] != "No description provided."))
        description_str = " ".join(descriptions) if descriptions else "No description provided."
        
        locations = ", ".join(f"`{o['rel_file']}:{o['line']}`" for o in occurrences)
        
        # Escape pipe symbols for markdown tables
        description_str = description_str.replace('|', '\\|')
        default_str = default_str.replace('|', '\\|')
        
        markdown_lines.append(f"| **{var_name}** | `{default_str}` | {locations} | {description_str} |")
        
    markdown_content = "\n".join(markdown_lines) + "\n"
    
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as out_f:
                out_f.write(markdown_content)
            print(f"Documentation successfully generated and saved to {args.output}", file=sys.stderr)
        except Exception as e:
            print(f"Error writing to output file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        sys.stdout.write(markdown_content)

if __name__ == "__main__":
    main()
