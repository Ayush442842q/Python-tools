#!/usr/bin/env python3
"""
Markdown Frontmatter Extractor

A command-line tool that recursively scans a directory of Markdown files,
extracts YAML frontmatter metadata (e.g. title, tags, author, date),
and outputs a summary, markdown table, JSON database, or CSV spreadsheet.

Usage:
    python tools/markdown_frontmatter_extractor.py path/to/md_folder [options]
"""

import argparse
import sys
import os
import re
import json
import csv

# ANSI Colors
COLORS = {
    "red": "\033[91m",
    "green": "\033[92m",
    "yellow": "\033[93m",
    "blue": "\033[94m",
    "cyan": "\033[96m",
    "bold": "\033[1m",
    "reset": "\033[0m"
}

def disable_colors():
    for key in COLORS:
        COLORS[key] = ""

def parse_simple_yaml(yaml_text):
    """
    Parses basic YAML frontmatter. Supports:
    - key: value
    - lists in square brackets [tag1, tag2]
    - lists in bulleted lines (starting with - )
    """
    metadata = {}
    lines = yaml_text.strip().split('\n')
    current_key = None
    
    for line in lines:
        line_stripped = line.strip()
        if not line_stripped:
            continue
            
        # Check if it is a list item for the current key
        if line_stripped.startswith('- ') and current_key is not None:
            val = line_stripped[2:].strip()
            # Remove wrapping quotes
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            if isinstance(metadata[current_key], list):
                metadata[current_key].append(val)
            else:
                metadata[current_key] = [val]
            continue
            
        # Match standard key: value
        match = re.match(r'^([A-Za-z0-9_\-]+)\s*:\s*(.*)$', line_stripped)
        if match:
            key, val = match.groups()
            val = val.strip()
            
            # Check for inline list [a, b, c]
            if val.startswith('[') and val.endswith(']'):
                items = [item.strip() for item in val[1:-1].split(',')]
                # Clean quotes
                cleaned_items = []
                for item in items:
                    if (item.startswith('"') and item.endswith('"')) or (item.startswith("'") and item.endswith("'")):
                        item = item[1:-1]
                    cleaned_items.append(item)
                metadata[key] = cleaned_items
                current_key = key
            else:
                # Remove quotes
                if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                    val = val[1:-1]
                
                # Check for boolean or numeric conversions
                if val.lower() == 'true':
                    val = True
                elif val.lower() == 'false':
                    val = False
                elif val.isdigit():
                    val = int(val)
                
                metadata[key] = val
                current_key = key
        else:
            # If it's a continuation of text
            if current_key and line_stripped:
                if isinstance(metadata[current_key], str):
                    metadata[current_key] += " " + line_stripped
    return metadata

def extract_frontmatter(file_path):
    """Extracts frontmatter from a single markdown file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        return None, f"Error reading file: {e}"
        
    # Match frontmatter between --- at the very start of the file
    match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
    if match:
        yaml_text = match.group(1)
        try:
            metadata = parse_simple_yaml(yaml_text)
            return metadata, None
        except Exception as e:
            return None, f"Error parsing metadata: {e}"
    return {}, None

def scan_directory(directory):
    """Scans directory recursively for markdown files and extracts frontmatter."""
    results = []
    no_frontmatter = []
    errors = []
    
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.md'):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, directory)
                metadata, err = extract_frontmatter(full_path)
                
                if err:
                    errors.append((rel_path, err))
                elif metadata:
                    results.append({
                        "file_path": rel_path,
                        "metadata": metadata
                    })
                else:
                    no_frontmatter.append(rel_path)
                    
    return results, no_frontmatter, errors

def main():
    parser = argparse.ArgumentParser(description="Recursively extract frontmatter metadata from Markdown files.")
    parser.add_argument("directory", help="Directory to scan recursively")
    parser.add_argument("-f", "--format", choices=["summary", "table", "json", "csv"], default="summary",
                        help="Output format (default: summary)")
    parser.add_argument("-o", "--output", help="Write results to this file path instead of stdout")
    parser.add_argument("--no-color", action="store_true", help="Disable colored console output")
    
    args = parser.parse_args()
    
    if args.no_color or args.output:
        disable_colors()
        
    if not os.path.isdir(args.directory):
        print(f"{COLORS['red']}Error: '{args.directory}' is not a valid directory.{COLORS['reset']}", file=sys.stderr)
        sys.exit(1)
        
    results, no_frontmatter, errors = scan_directory(args.directory)
    
    # 1. Output JSON Format
    if args.format == "json":
        output_str = json.dumps(results, indent=2)
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output_str)
            print(f"Exported JSON to {args.output}")
        else:
            print(output_str)
            
    # 2. Output CSV Format
    elif args.format == "csv":
        # Identify all unique keys across all metadata
        all_keys = set()
        for r in results:
            all_keys.update(r["metadata"].keys())
        headers = ["file_path"] + sorted(list(all_keys))
        
        if args.output:
            with open(args.output, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=headers)
                writer.writeheader()
                for r in results:
                    row = {"file_path": r["file_path"]}
                    for k, v in r["metadata"].items():
                        # Serialize lists/dicts as JSON strings
                        if isinstance(v, (list, dict)):
                            row[k] = json.dumps(v)
                        else:
                            row[k] = v
                    writer.writerow(row)
            print(f"Exported CSV to {args.output}")
        else:
            writer = csv.DictWriter(sys.stdout, fieldnames=headers)
            writer.writeheader()
            for r in results:
                row = {"file_path": r["file_path"]}
                for k, v in r["metadata"].items():
                    if isinstance(v, (list, dict)):
                        row[k] = json.dumps(v)
                    else:
                        row[k] = v
                writer.writerow(row)
                
    # 3. Output Table Format
    elif args.format == "table":
        # Create a simple markdown table
        headers = ["File Path", "Title", "Date", "Tags"]
        table_lines = [
            f"| {' | '.join(headers)} |",
            f"| {' | '.join(['---' for _ in headers])} |"
        ]
        for r in results:
            m = r["metadata"]
            title = str(m.get("title", "N/A"))
            date = str(m.get("date", "N/A"))
            tags = m.get("tags", [])
            tags_str = ", ".join(tags) if isinstance(tags, list) else str(tags)
            
            table_lines.append(f"| {r['file_path']} | {title} | {date} | {tags_str} |")
            
        output_str = "\n".join(table_lines)
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output_str)
            print(f"Exported markdown table to {args.output}")
        else:
            print(output_str)
            
    # 4. Output Summary Format
    else:
        summary_lines = []
        summary_lines.append(f"{COLORS['bold']}Markdown Frontmatter Summary Report{COLORS['reset']}")
        summary_lines.append("=" * 50)
        summary_lines.append(f"Directory Scanned:     {args.directory}")
        summary_lines.append(f"Files with Metadata:    {COLORS['green']}{len(results)}{COLORS['reset']}")
        summary_lines.append(f"Files without Metadata: {COLORS['yellow']}{len(no_frontmatter)}{COLORS['reset']}")
        summary_lines.append(f"Files with Errors:      {COLORS['red']}{len(errors)}{COLORS['reset']}")
        summary_lines.append("")
        
        # Analyze tags
        tag_counts = {}
        for r in results:
            tags = r["metadata"].get("tags", [])
            if isinstance(tags, list):
                for t in tags:
                    tag_counts[t] = tag_counts.get(t, 0) + 1
            elif isinstance(tags, str):
                tag_counts[tags] = tag_counts.get(tags, 0) + 1
                
        if tag_counts:
            summary_lines.append(f"{COLORS['bold']}Top Tags:{COLORS['reset']}")
            sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
            for tag, count in sorted_tags:
                summary_lines.append(f"  - {tag}: {count}")
            summary_lines.append("")
            
        if errors:
            summary_lines.append(f"{COLORS['red']}{COLORS['bold']}Errors Encountered:{COLORS['reset']}")
            for rel_path, err in errors:
                summary_lines.append(f"  - {rel_path}: {err}")
            summary_lines.append("")
            
        if results:
            summary_lines.append(f"{COLORS['bold']}Scanned Articles List:{COLORS['reset']}")
            for r in results:
                title = r["metadata"].get("title", "No Title")
                summary_lines.append(f"  - {COLORS['cyan']}{r['file_path']}{COLORS['reset']} -> {COLORS['bold']}{title}{COLORS['reset']}")
                
        output_str = "\n".join(summary_lines)
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output_str)
            print(f"Exported summary report to {args.output}")
        else:
            print(output_str)

if __name__ == "__main__":
    main()
