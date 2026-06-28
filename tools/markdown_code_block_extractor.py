#!/usr/bin/env python3
"""
Markdown Code Block Extractor
Scans Markdown files and extracts all code blocks, optionally filtering by language.
Saves them into an output directory or prints them to the terminal.
"""

import os
import re
import sys
import argparse
from typing import List, Dict, Tuple

# ANSI Colors
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"

# Map of common markdown languages to file extensions
LANGUAGE_EXTENSIONS = {
    'python': 'py',
    'py': 'py',
    'javascript': 'js',
    'js': 'js',
    'typescript': 'ts',
    'ts': 'ts',
    'bash': 'sh',
    'sh': 'sh',
    'shell': 'sh',
    'powershell': 'ps1',
    'ps1': 'ps1',
    'sql': 'sql',
    'html': 'html',
    'css': 'css',
    'json': 'json',
    'yaml': 'yml',
    'yml': 'yml',
    'xml': 'xml',
    'rust': 'rs',
    'rs': 'rs',
    'go': 'go',
    'c': 'c',
    'cpp': 'cpp',
    'java': 'java',
    'ruby': 'rb',
    'rb': 'rb',
    'php': 'php',
    'markdown': 'md',
    'md': 'md',
    'ini': 'ini',
    'toml': 'toml',
    'dockerfile': 'Dockerfile',
    'docker': 'Dockerfile',
    'makefile': 'Makefile',
}

def get_extension(lang: str) -> str:
    """Get the appropriate file extension for a markdown language identifier."""
    lang_lower = lang.lower().strip()
    return LANGUAGE_EXTENSIONS.get(lang_lower, lang_lower if lang_lower else 'txt')

def extract_code_blocks(content: str) -> List[Tuple[str, str]]:
    """
    Extracts code blocks from markdown content.
    Returns:
        List of tuples: (language, code_content)
    """
    # Regex to match code blocks fenced with three or more backticks
    # Group 1: language identifier (optional)
    # Group 2: code contents
    pattern = re.compile(r'^```(\w+)?\s*\n(.*?)^```\s*$', re.MULTILINE | re.DOTALL)
    blocks = []
    for match in pattern.finditer(content):
        lang = match.group(1) or ""
        code = match.group(2)
        blocks.append((lang.strip(), code))
    return blocks

def process_file(
    file_path: str,
    target_lang: str = None,
    output_dir: str = None,
    dry_run: bool = False,
    list_only: bool = False
) -> Dict[str, int]:
    """Process a single markdown file, returning statistics of extracted blocks."""
    stats = {}
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"{RED}Error reading {file_path}: {e}{RESET}", file=sys.stderr)
        return stats

    blocks = extract_code_blocks(content)
    if not blocks:
        return stats

    base_name = os.path.splitext(os.path.basename(file_path))[0]

    for idx, (lang, code) in enumerate(blocks, 1):
        # Update stats
        lang_key = lang if lang else "unspecified"
        stats[lang_key] = stats.get(lang_key, 0) + 1
        
        if list_only:
            continue
            
        # Filter by language if requested
        if target_lang and lang.lower() != target_lang.lower():
            continue
            
        if output_dir:
            ext = get_extension(lang)
            out_filename = f"{base_name}_block_{idx}.{ext}" if ext != 'Dockerfile' and ext != 'Makefile' else f"{ext}_{base_name}_{idx}"
            out_path = os.path.join(output_dir, out_filename)
            
            print(f"  {GREEN}→{RESET} {out_path} ({len(code.encode('utf-8'))} bytes)")
            if not dry_run:
                try:
                    with open(out_path, 'w', encoding='utf-8') as out_f:
                        out_f.write(code)
                except Exception as e:
                    print(f"  {RED}Error writing file: {e}{RESET}", file=sys.stderr)
        else:
            # Print to stdout
            print(f"\n{BOLD}{CYAN}--- Code Block {idx} ({lang_key}) from {file_path} ---{RESET}")
            print(code.strip())
            print(f"{BOLD}{CYAN}-------------------------------------------------{RESET}")

    return stats

def main():
    parser = argparse.ArgumentParser(
        description="Extract code blocks from Markdown files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python markdown_code_block_extractor.py README.md
  python markdown_code_block_extractor.py README.md -l python
  python markdown_code_block_extractor.py README.md -o ./extracted_code -l bash
  python markdown_code_block_extractor.py --dir docs/ --list-languages
        """
    )
    parser.add_argument(
        "files",
        nargs="*",
        help="Markdown file(s) to scan"
    )
    parser.add_argument(
        "-d", "--dir",
        help="Directory to scan recursively for Markdown files"
    )
    parser.add_argument(
        "-l", "--lang",
        help="Filter extraction by language identifier (e.g. python, bash, sql)"
    )
    parser.add_argument(
        "-o", "--output-dir",
        help="Output directory to save extracted code blocks. If omitted, prints to terminal."
    )
    parser.add_argument(
        "--list-languages",
        action="store_true",
        help="Scan files and list all found languages and counts without extracting"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what files would be generated without writing them"
    )

    args = parser.parse_args()

    # Gather target files
    md_files = []
    if args.files:
        for f in args.files:
            if os.path.isfile(f):
                md_files.append(f)
            else:
                print(f"{RED}Warning: File not found: {f}{RESET}", file=sys.stderr)
                
    if args.dir:
        if not os.path.isdir(args.dir):
            print(f"{RED}Error: Directory not found: {args.dir}{RESET}", file=sys.stderr)
            sys.exit(1)
        for root, _, filenames in os.walk(args.dir):
            for filename in filenames:
                if filename.endswith(('.md', '.markdown')):
                    md_files.append(os.path.join(root, filename))

    if not md_files:
        if not args.files and not args.dir:
            parser.print_help()
        else:
            print(f"{RED}No markdown files found to process.{RESET}")
        sys.exit(1)

    # Initialize output directory if specified
    if args.output_dir and not args.list_languages and not args.dry_run:
        os.makedirs(args.output_dir, exist_ok=True)

    print(f"{BOLD}{CYAN}Scanning {len(md_files)} file(s)...{RESET}")
    
    total_stats = {}
    for md_file in md_files:
        if not args.list_languages:
            print(f"\n{BOLD}Processing {md_file}...{RESET}")
        stats = process_file(
            file_path=md_file,
            target_lang=args.lang,
            output_dir=args.output_dir,
            dry_run=args.dry_run,
            list_only=args.list_languages
        )
        for lang, count in stats.items():
            total_stats[lang] = total_stats.get(lang, 0) + count

    # Report results
    if args.list_languages:
        print(f"\n{BOLD}{YELLOW}Languages found across files:{RESET}")
        if not total_stats:
            print("  No code blocks found.")
        for lang, count in sorted(total_stats.items(), key=lambda x: x[1], reverse=True):
            print(f"  - {lang:15} : {count} blocks")
    else:
        grand_total = sum(total_stats.values())
        print(f"\n{BOLD}{GREEN}Extraction completed!{RESET}")
        print(f"Total blocks discovered: {grand_total}")
        if args.lang:
            print(f"Filtered for language:  {args.lang}")

if __name__ == "__main__":
    main()
