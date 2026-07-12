#!/usr/bin/env python3
"""
Markdown Link Healer
Recursively scans Markdown files for broken local file links. If a broken link is
detected, it searches the directory structure for files with matching or similar
names, calculates the correct relative path, and heals (updates) the links.
"""

import os
import re
import argparse
import urllib.parse
import difflib
from typing import Dict, List, Tuple, Set


# Regex to find Markdown links: [text](link)
# We want to catch local file links, excluding URLs (http://, mailto:, etc.) and anchors (#anchors)
LINK_RE = re.compile(r'\[([^\]]+)\]\(([^)]+)\)')


def is_local_file_link(link: str) -> bool:
    """Determine if a link is pointing to a local file."""
    # Decode URL-encoded characters (like %20 for spaces)
    link = urllib.parse.unquote(link)
    
    # Exclude web links, mail links, and page-local anchors
    if link.startswith(('http://', 'https://', 'mailto:', 'tel:', '#', 'ftp:')):
        return False
        
    # Check if it has a scheme (like file://, which we can parse, but general schemes are external)
    parsed = urllib.parse.urlparse(link)
    if parsed.scheme and parsed.scheme != 'file':
        return False
        
    return True


def find_all_files(root_dir: str) -> Dict[str, List[str]]:
    """Build a mapping of filename -> list of absolute paths in the workspace."""
    file_map: Dict[str, List[str]] = {}
    for root, dirs, files in os.walk(root_dir):
        # Skip git or build folders
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('node_modules', 'venv', 'dist', 'build')]
        for file in files:
            file_map.setdefault(file.lower(), []).append(os.path.join(root, file))
    return file_map


def get_relative_path(from_file: str, to_file: str) -> str:
    """Calculate the relative path from one file to another, formatted for Markdown."""
    from_dir = os.path.dirname(from_file)
    rel_path = os.path.relpath(to_file, from_dir)
    # Markdown links use forward slashes even on Windows
    return rel_path.replace(os.path.sep, '/')


def heal_markdown_file(
    filepath: str,
    file_map: Dict[str, List[str]],
    root_dir: str,
    interactive: bool,
    dry_run: bool
) -> Tuple[int, int]:
    """Audit and repair links in a single Markdown file."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"[-] Error reading file {filepath}: {e}")
        return 0, 0
        
    file_dir = os.path.dirname(filepath)
    modified = False
    healed_count = 0
    broken_count = 0
    
    new_content_lines = []
    lines = content.splitlines()
    
    for idx, line in enumerate(lines, 1):
        line_modified = False
        current_line = line
        
        # Search for links in current line
        for match in LINK_RE.finditer(line):
            link_text = match.group(1)
            link_target = match.group(2)
            
            # Split target in case it contains anchor or query: path/to/file.md#section
            target_clean = link_target.split('#')[0].split('?')[0]
            if not target_clean:
                continue
                
            if not is_local_file_link(target_clean):
                continue
                
            # Decode URL formatting
            target_path = urllib.parse.unquote(target_clean)
            
            # Form absolute target path
            abs_target_path = os.path.normpath(os.path.join(file_dir, target_path))
            
            # If target exists, the link is healthy
            if os.path.exists(abs_target_path):
                continue
                
            broken_count += 1
            filename = os.path.basename(target_path).lower()
            
            # Check if this file exists elsewhere in the workspace
            candidates = file_map.get(filename, [])
            
            # If no exact filename match, try fuzzy matching filename
            if not candidates:
                all_filenames = list(file_map.keys())
                close_matches = difflib.get_close_matches(filename, all_filenames, n=3, cutoff=0.7)
                for match_name in close_matches:
                    candidates.extend(file_map[match_name])
                    
            if not candidates:
                print(f"[!] Broken link in {os.path.basename(filepath)}:{idx} -> '{link_target}' (No candidate files found)")
                continue
                
            # We have candidates. Resolve or prompt
            chosen_target = None
            if len(candidates) == 1 and not interactive:
                chosen_target = candidates[0]
                print(f"[+] Auto-healed: {os.path.basename(filepath)}:{idx} -> '{link_target}' updated to '{get_relative_path(filepath, chosen_target)}'")
            elif len(candidates) > 0 and interactive:
                print(f"\n[!] Broken link in {filepath}:{idx} -> [{link_text}]({link_target})")
                print("    Candidate files found:")
                for c_idx, cand in enumerate(candidates, 1):
                    rel = os.path.relpath(cand, root_dir)
                    print(f"      [{c_idx}] {rel}")
                print("      [s] Skip / Do nothing")
                
                choice = input("    Choose option to repair link: ").strip().lower()
                if choice.isdigit() and 1 <= int(choice) <= len(candidates):
                    chosen_target = candidates[int(choice) - 1]
                    
            if chosen_target:
                # Keep anchor/query if original link had it
                anchor_suffix = ""
                if '#' in link_target:
                    anchor_suffix = '#' + link_target.split('#', 1)[1]
                elif '?' in link_target:
                    anchor_suffix = '?' + link_target.split('?', 1)[1]
                    
                new_rel_path = get_relative_path(filepath, chosen_target) + anchor_suffix
                # Escape spaces for URL format
                new_link_target = urllib.parse.quote(new_rel_path).replace('%23', '#').replace('%3F', '?')
                
                # Replace the link in the current line
                old_link_str = f"[{link_text}]({link_target})"
                new_link_str = f"[{link_text}]({new_link_target})"
                current_line = current_line.replace(old_link_str, new_link_str)
                line_modified = True
                healed_count += 1
                
        if line_modified:
            new_content_lines.append(current_line)
            modified = True
        else:
            new_content_lines.append(line)
            
    if modified and not dry_run:
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write('\n'.join(new_content_lines) + '\n')
        except Exception as e:
            print(f"[-] Error writing file {filepath}: {e}")
            
    return broken_count, healed_count


def main():
    parser = argparse.ArgumentParser(description="Audit and repair broken local file links in Markdown files.")
    parser.add_argument("path", nargs="?", default=".", help="Directory to scan (default: current directory)")
    parser.add_argument("-i", "--interactive", action="store_true", help="Prompt user interactively to select candidate links")
    parser.add_argument("--dry-run", action="store_true", help="Scan and identify broken links without making changes")
    
    args = parser.parse_args()
    
    root_dir = os.path.abspath(args.path)
    if not os.path.isdir(root_dir):
        print(f"Error: Path is not a directory: {root_dir}")
        sys.exit(1)
        
    print("[*] Indexing workspace files...")
    file_map = find_all_files(root_dir)
    
    markdown_files = []
    for root, dirs, files in os.walk(root_dir):
        dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('node_modules', 'venv', 'dist', 'build')]
        for file in files:
            if file.lower().endswith(('.md', '.markdown')):
                markdown_files.append(os.path.join(root, file))
                
    print(f"[*] Found {len(markdown_files)} Markdown file(s) to audit.\n")
    
    total_broken = 0
    total_healed = 0
    
    for filepath in markdown_files:
        broken, healed = heal_markdown_file(filepath, file_map, root_dir, args.interactive, args.dry_run)
        total_broken += broken
        total_healed += healed
        
    print("\n" + "=" * 50)
    print("                 SUMMARY                       ")
    print("=" * 50)
    print(f"  Files audited:   {len(markdown_files)}")
    print(f"  Broken links:    {total_broken}")
    if args.dry_run:
        print(f"  Healable links:  {total_healed} (dry-run, no files changed)")
    else:
        print(f"  Healed links:    {total_healed}")
    print("=" * 50)


if __name__ == "__main__":
    main()
