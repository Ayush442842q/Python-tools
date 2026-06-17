#!/usr/bin/env python3
"""
Copy-Paste / Duplicate Code Block Detector - Recursively scans directories to detect
duplicate blocks of code. Normalizes whitespace, comments, and blank lines.
Reports duplicate blocks, file names, line numbers, and matching code.
"""

import argparse
import hashlib
import os
import sys

# File types and comment delimiters to clean during normalization
LANGUAGE_CONFIGS = {
    '.py': {'single': '#', 'multi_start': '"""', 'multi_end': '"""'},
    '.js': {'single': '//', 'multi_start': '/*', 'multi_end': '*/'},
    '.ts': {'single': '//', 'multi_start': '/*', 'multi_end': '*/'},
    '.java': {'single': '//', 'multi_start': '/*', 'multi_end': '*/'},
    '.c': {'single': '//', 'multi_start': '/*', 'multi_end': '*/'},
    '.cpp': {'single': '//', 'multi_start': '/*', 'multi_end': '*/'},
    '.h': {'single': '//', 'multi_start': '/*', 'multi_end': '*/'},
    '.cs': {'single': '//', 'multi_start': '/*', 'multi_end': '*/'},
    '.go': {'single': '//', 'multi_start': '/*', 'multi_end': '*/'},
    '.rs': {'single': '//', 'multi_start': '/*', 'multi_end': '*/'},
    '.php': {'single': '//', 'multi_start': '/*', 'multi_end': '*/'},
    '.rb': {'single': '#', 'multi_start': '=begin', 'multi_end': '=end'},
}

def normalize_file(file_path):
    """
    Reads a file and returns:
    1. A list of normalized line strings (cleaned of comments and whitespaces)
    2. A mapping from normalized index to (original_line_number, original_raw_text)
    """
    _, ext = os.path.splitext(file_path.lower())
    config = LANGUAGE_CONFIGS.get(ext, {'single': None, 'multi_start': None, 'multi_end': None})
    
    single_comment = config['single']
    multi_start = config['multi_start']
    multi_end = config['multi_end']
    
    normalized_lines = []
    line_map = []
    
    in_multi_comment = False
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            for idx, line in enumerate(f, 1):
                clean_line = line.strip()
                
                # Handle multi-line comments
                if in_multi_comment:
                    if multi_end and multi_end in clean_line:
                        # Extract part after the multi-comment end
                        parts = clean_line.split(multi_end, 1)
                        clean_line = parts[1].strip()
                        in_multi_comment = False
                    else:
                        continue
                        
                if not in_multi_comment and multi_start and multi_start in clean_line:
                    # Check if multi-line comment starts and ends on same line
                    if multi_end and multi_end in clean_line[clean_line.find(multi_start) + len(multi_start):]:
                        # Strip the comment block
                        start_idx = clean_line.find(multi_start)
                        end_idx = clean_line.find(multi_end, start_idx + len(multi_start))
                        clean_line = (clean_line[:start_idx] + clean_line[end_idx + len(multi_end):]).strip()
                    else:
                        parts = clean_line.split(multi_start, 1)
                        clean_line = parts[0].strip()
                        in_multi_comment = True
                        
                # Handle single-line comments
                if single_comment and clean_line.startswith(single_comment):
                    continue
                elif single_comment and single_comment in clean_line:
                    # Very simple comment stripper
                    clean_line = clean_line.split(single_comment, 1)[0].strip()
                    
                # Ignore blank lines
                if not clean_line:
                    continue
                    
                # Normalize spaces inside the code line
                normalized_code = "".join(clean_line.split())
                
                normalized_lines.append(normalized_code)
                line_map.append((idx, line.rstrip()))
    except Exception:
        # Ignore files that can't be read
        pass
        
    return normalized_lines, line_map

def find_duplicates(file_paths, min_lines=6):
    """
    Finds duplicates using a sliding window algorithm.
    Returns a list of duplicate groups.
    """
    # Map from window hash -> list of (file_path, start_norm_idx, end_norm_idx)
    hashes = {}
    
    # Store normalized data for each file
    file_data = {}
    
    for file_path in file_paths:
        norm_lines, line_map = normalize_file(file_path)
        if len(norm_lines) < min_lines:
            continue
        file_data[file_path] = (norm_lines, line_map)
        
        # Calculate hashes for sliding windows
        for i in range(len(norm_lines) - min_lines + 1):
            window = norm_lines[i : i + min_lines]
            window_str = "".join(window)
            h = hashlib.md5(window_str.encode('utf-8')).hexdigest()
            
            if h not in hashes:
                hashes[h] = []
            hashes[h].append((file_path, i, i + min_lines))
            
    # Filter out hashes that only appeared once
    duplicate_windows = {h: locs for h, locs in hashes.items() if len(locs) > 1}
    
    # Group and merge adjacent windows to report longer duplicates
    visited = set()
    duplicate_groups = []
    
    for h, locs in sorted(duplicate_windows.items()):
        if h in visited:
            continue
            
        # Try to expand the duplicate match block
        expanded_group = []
        for loc in locs:
            file_path, start_idx, end_idx = loc
            norm_lines, line_map = file_data[file_path]
            
            # Find how far we can extend this match compared to other locations in the group
            expanded_group.append({
                'file_path': file_path,
                'start_idx': start_idx,
                'end_idx': end_idx,
                'line_map': line_map,
                'norm_lines': norm_lines
            })
            
        # We consolidate overlap and adjacent matches
        # For simplicity, we create groups of matching locations
        group_locations = []
        for idx, item in enumerate(expanded_group):
            start_orig_line = item['line_map'][item['start_idx']][0]
            end_orig_line = item['line_map'][item['end_idx'] - 1][0]
            
            # Extract raw lines
            raw_lines = [item['line_map'][k][1] for k in range(item['start_idx'], item['end_idx'])]
            
            group_locations.append({
                'file': item['file_path'],
                'start': start_orig_line,
                'end': end_orig_line,
                'lines': raw_lines
            })
            
        duplicate_groups.append(group_locations)
        visited.add(h)
        
    # De-duplicate groups that are subsets of larger duplicate blocks
    # (Simple consolidation of duplicate blocks)
    consolidated_groups = []
    for group in duplicate_groups:
        # Check if this group's files and line ranges are already covered
        is_subset = False
        for existing in consolidated_groups:
            # Check if all files in group are in existing, with overlapping/encompassed ranges
            matches = 0
            for g_item in group:
                for e_item in existing:
                    if g_item['file'] == e_item['file']:
                        # Check if g_item range is within e_item range
                        if e_item['start'] <= g_item['start'] and g_item['end'] <= e_item['end']:
                            matches += 1
                            break
            if matches == len(group):
                is_subset = True
                break
                
        if not is_subset:
            consolidated_groups.append(group)
            
    return consolidated_groups

def main():
    parser = argparse.ArgumentParser(description="Find duplicate/copied code blocks across directory.")
    parser.add_argument("path", help="Directory or file path to scan")
    parser.add_argument("-m", "--min-lines", type=int, default=6, help="Minimum matching lines (default: 6)")
    parser.add_argument("-e", "--extensions", help="Comma-separated file extensions to scan (e.g. .py,.js)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print actual duplicate code contents")
    
    args = parser.parse_args()
    
    # Determine target extensions
    exts = None
    if args.extensions:
        exts = [e.strip().lower() if e.startswith('.') else '.' + e.strip().lower() for e in args.extensions.split(',')]
    else:
        exts = list(LANGUAGE_CONFIGS.keys())
        
    file_paths = []
    if os.path.isfile(args.path):
        file_paths.append(args.path)
    elif os.path.isdir(args.path):
        for root, _, files in os.walk(args.path):
            for file in files:
                _, ext = os.path.splitext(file.lower())
                if ext in exts:
                    file_paths.append(os.path.join(root, file))
    else:
        print(f"Error: Path '{args.path}' does not exist.", file=sys.stderr)
        sys.exit(1)
        
    print(f"Scanning {len(file_paths)} files for duplicates (min lines: {args.min_lines})...")
    
    groups = find_duplicates(file_paths, args.min_lines)
    
    if not groups:
        print("No duplicate code blocks found.")
        sys.exit(0)
        
    print(f"Found {len(groups)} duplicate code blocks:\n")
    
    for idx, group in enumerate(groups, 1):
        print(f"Block #{idx} (Detected in {len(group)} locations):")
        for loc in group:
            print(f"  - {loc['file']} : Lines {loc['start']} - {loc['end']}")
            
        if args.verbose:
            print("  Code snippet:")
            print("  " + "-" * 40)
            # Print matching lines from first location
            snippet = loc['lines']
            for line in snippet[:15]: # Show first 15 lines max
                print(f"    {line}")
            if len(snippet) > 15:
                print("    ...")
            print("  " + "-" * 40)
        print()
        
    sys.exit(0)

if __name__ == "__main__":
    main()
