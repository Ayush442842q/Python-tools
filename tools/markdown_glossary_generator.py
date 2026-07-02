#!/usr/bin/env python3
"""
Markdown Glossary Generator & Indexer

Scans a directory of Markdown documents for terms defined in a central glossary,
generates a master GLOSSARY.md file with back-references, and optionally links term
occurrences in documents directly to their glossary definitions.

Usage:
    python tools/markdown_glossary_generator.py [options]
"""

import os
import re
import sys
import json
import argparse
from pathlib import Path
from collections import defaultdict

# ANSI Colors
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

def load_glossary(glossary_path: Path) -> dict:
    """Loads terms and descriptions from a JSON glossary file or parses a text-based definition file."""
    glossary = {}
    if not glossary_path.exists():
        print_colored(f"Glossary file not found: {glossary_path}", RED)
        return glossary
        
    if glossary_path.suffix.lower() == '.json':
        try:
            with open(glossary_path, 'r', encoding='utf-8') as f:
                glossary = json.load(f)
        except Exception as e:
            print_colored(f"Error reading JSON glossary: {e}", RED)
    else:
        # Parse plain text file format:
        # TERM: Definition
        # OR
        # **TERM** - Definition
        try:
            with open(glossary_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    # Try splitting on ': ' or ' - '
                    term = None
                    definition = None
                    if ': ' in line:
                        term, definition = line.split(': ', 1)
                    elif ' - ' in line:
                        term, definition = line.split(' - ', 1)
                        
                    if term:
                        # Clean markdown formatting from term name
                        term = re.sub(r'^\**|\**$', '', term.strip())
                        glossary[term] = definition.strip()
        except Exception as e:
            print_colored(f"Error parsing text glossary: {e}", RED)
            
    # Normalize keys to lowercase for matching, keeping original casing
    normalized = {}
    for term, definition in glossary.items():
        normalized[term.strip()] = definition.strip()
        
    return normalized

def scan_markdown_file(filepath: Path, terms: dict) -> dict:
    """Scans a markdown file for occurrences of terms, ignoring code blocks, links, and headings."""
    occurrences = defaultdict(list)
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
    except Exception as e:
        print_colored(f"Error reading {filepath}: {e}", RED)
        return occurrences

    in_code_block = False
    
    # Sort terms by length in descending order to avoid partial matches on nested terms
    sorted_terms = sorted(terms.keys(), key=len, reverse=True)
    
    for idx, line in enumerate(lines):
        line_num = idx + 1
        
        # Track fenced code blocks
        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            continue
            
        if in_code_block:
            continue
            
        # Ignore headers
        if line.strip().startswith('#'):
            continue
            
        # Strip out markdown links and inline code before search to avoid false positives
        clean_line = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', line)  # links
        clean_line = re.sub(r'`[^`]+`', '', clean_line)              # inline code
        
        for term in sorted_terms:
            # Word boundary regex matching, case-insensitive
            pattern = re.compile(rf'\b{re.escape(term)}\b', re.IGNORECASE)
            matches = list(pattern.finditer(clean_line))
            if matches:
                occurrences[term].append({
                    'line_num': line_num,
                    'line_text': line.strip()
                })
                
    return occurrences

def linkify_document(filepath: Path, terms: dict, glossary_filename: str) -> bool:
    """Updates a markdown document, adding hyperlink anchors for occurrences of glossary terms."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        print_colored(f"Error reading {filepath}: {e}", RED)
        return False

    in_code_block = False
    lines = content.splitlines()
    modified = False
    new_lines = []
    
    sorted_terms = sorted(terms.keys(), key=len, reverse=True)
    
    for line in lines:
        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            new_lines.append(line)
            continue
            
        if in_code_block or line.strip().startswith('#'):
            new_lines.append(line)
            continue
            
        # Linkify terms, avoiding text inside existing Markdown links: [term](...) or inside inline code `term`
        # Also avoid modifying HTML tags.
        original_line = line
        
        # Build tokenized segments to skip matches inside backticks/links
        # Split line by markdown links and inline code segments
        parts = re.split(r'(\`[^\`]+\`|\[[^\]]+\]\([^\)]+\))', line)
        
        for i in range(len(parts)):
            # Only replace in odd indexes (if they are not links or inline code)
            # wait, split on a group includes the matched group in parts.
            # Even indexes are normal text, odd indexes are matched groups.
            if i % 2 == 0:
                segment = parts[i]
                for term in sorted_terms:
                    # Case-insensitive word boundary replacement
                    term_slug = term.lower().replace(' ', '-')
                    pattern = re.compile(rf'\b({re.escape(term)})\b', re.IGNORECASE)
                    
                    # We will replace term with [term](glossary_filename#term-slug)
                    # but only if it's not already linkified inside this segment.
                    segment = pattern.sub(f'[\\1]({glossary_filename}#{term_slug})', segment)
                parts[i] = segment
                
        new_line = "".join(parts)
        if new_line != original_line:
            modified = True
            new_lines.append(new_line)
        else:
            new_lines.append(original_line)
            
    if modified:
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("\n".join(new_lines) + "\n")
            return True
        except Exception as e:
            print_colored(f"Error writing updates to {filepath}: {e}", RED)
            
    return False

def generate_master_glossary_file(output_path: Path, glossary: dict, references: dict, root_dir: Path):
    """Generates the final GLOSSARY.md file."""
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write("# Project Glossary\n\n")
            f.write("A master collection of terms, definitions, and document cross-references.\n\n")
            f.write("## Terms Index\n\n")
            
            # Write a quick index
            sorted_terms = sorted(glossary.keys())
            index_items = []
            for term in sorted_terms:
                term_slug = term.lower().replace(' ', '-')
                index_items.append(f"[{term}](#{term_slug})")
            f.write(" | ".join(index_items) + "\n\n")
            
            f.write("---\n\n")
            
            # Write descriptions and back-links
            for term in sorted_terms:
                term_slug = term.lower().replace(' ', '-')
                definition = glossary[term]
                f.write(f"### <a name=\"{term_slug}\"></a>{term}\n")
                f.write(f"{definition}\n\n")
                
                # Back-references
                refs = references.get(term, {})
                if refs:
                    f.write("**Referenced in:**\n")
                    for file_path, occurrences in refs.items():
                        rel_path = os.path.relpath(file_path, root_dir.absolute()).replace('\\', '/')
                        links = []
                        for occ in occurrences:
                            links.append(f"[Line {occ['line_num']}]({rel_path}#L{occ['line_num']})")
                        f.write(f"- `{rel_path}`: {', '.join(links)}\n")
                else:
                    f.write("*No direct references found in scanned files.*\n")
                f.write("\n---\n")
                
        print_colored(f"Successfully generated master glossary at: {output_path}", GREEN)
        return True
    except Exception as e:
        print_colored(f"Error writing master glossary: {e}", RED)
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Scans files for glossary terms, generates GLOSSARY.md index, and optionally adds links."
    )
    parser.add_argument(
        "--path", "-p",
        default=".",
        help="Path to directory containing Markdown files (default: current directory)"
    )
    parser.add_argument(
        "--glossary", "-g",
        default="glossary.json",
        help="Path to glossary definitions file (JSON format or txt format: TERM: DEF) (default: glossary.json)"
    )
    parser.add_argument(
        "--output", "-o",
        default="GLOSSARY.md",
        help="Filename for the generated master glossary file (default: GLOSSARY.md)"
    )
    parser.add_argument(
        "--link", "-l",
        action="store_true",
        help="Modify scanned files to inject links referencing the master glossary definitions"
    )
    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="Run analysis and report matches without updating files or writing GLOSSARY.md"
    )
    
    args = parser.parse_args()
    
    root_dir = Path(args.path)
    glossary_file = Path(args.glossary)
    
    if not root_dir.exists():
        print_colored(f"Error: path '{root_dir}' does not exist.", RED)
        return 1
        
    # Attempt to load glossary
    glossary = load_glossary(glossary_file)
    if not glossary:
        print_colored("Glossary definitions list is empty. Creating a template glossary.json...", YELLOW)
        template = {
            "API": "Application Programming Interface, a set of protocols to build application software.",
            "Database": "An organized collection of structured data or information, stored electronically.",
            "Git": "A distributed version control system to track changes in source code."
        }
        try:
            with open(glossary_file, 'w', encoding='utf-8') as f:
                json.dump(template, f, indent=2)
            print_colored(f"Created template glossary file at '{glossary_file}'. Add your terms and re-run.", GREEN)
            glossary = template
        except Exception as e:
            print_colored(f"Failed to create template glossary file: {e}", RED)
            return 1

    # Scan for markdown files
    md_files = []
    output_filename = Path(args.output).name
    
    for root, _, files in os.walk(root_dir):
        for file in files:
            if file.endswith('.md') and file != output_filename and file != glossary_file.name:
                md_files.append(Path(root) / file)
                
    if not md_files:
        print_colored("No markdown files found to scan.", YELLOW)
        return 0
        
    print_colored(f"Scanning {len(md_files)} markdown file(s) for {len(glossary)} glossary terms...", BOLD)
    
    # Store references: term -> filepath -> [occurrences]
    references = defaultdict(lambda: defaultdict(list))
    
    for file in md_files:
        file_occurrences = scan_markdown_file(file, glossary)
        for term, occurrences in file_occurrences.items():
            references[term][str(file.absolute())].extend(occurrences)
            
    # Print scan report
    print_colored("\nTerm Occurrence Summary:", BOLD + CYAN)
    total_references = 0
    for term in sorted(glossary.keys()):
        refs = references.get(term, {})
        occurrences_count = sum(len(o) for o in refs.values())
        total_references += occurrences_count
        status = f"{occurrences_count} match(es) in {len(refs)} file(s)"
        print(f"  - {term:<20} : {status}")
        
    if args.dry_run:
        print_colored("\nDry run: skipped writing output files.", CYAN)
        return 0
        
    # Write master glossary file
    output_path = root_dir / args.output
    generate_master_glossary_file(output_path, glossary, references, root_dir)
    
    # Optionally linkify files
    if args.link:
        print_colored(f"\nLinkifying term occurrences in documents...", BOLD)
        updated_count = 0
        for file in md_files:
            if linkify_document(file, glossary, args.output):
                print_colored(f"  Linkified: {file}", GREEN)
                updated_count += 1
        print_colored(f"Linkification complete. Updated {updated_count}/{len(md_files)} files.", BOLD)
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
