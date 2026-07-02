#!/usr/bin/env python3
"""
Python Dependency Harmonizer
A standalone utility to scan, merge, and harmonize multiple requirements.txt or pyproject.toml files,
resolving overlapping version constraints and highlighting conflicts.
"""

import argparse
import os
import re
import sys
from collections import defaultdict

# Simple version parser for zero-dependency comparisons
class SimpleVersion:
    def __init__(self, version_str):
        self.raw = version_str.strip()
        # Remove any environment markers or comments
        clean_ver = self.raw.split(';')[0].split('#')[0].strip()
        
        # Split by '.' and extract numbers
        parts = []
        for p in clean_ver.split('.'):
            digits = []
            for char in p:
                if char.isdigit():
                    digits.append(char)
                else:
                    break
            if digits:
                parts.append(int("".join(digits)))
            else:
                parts.append(0)
        self.parts = tuple(parts)

    def __lt__(self, other):
        return self.parts < other.parts
    def __le__(self, other):
        return self.parts <= other.parts
    def __gt__(self, other):
        return self.parts > other.parts
    def __ge__(self, other):
        return self.parts >= other.parts
    def __eq__(self, other):
        return self.parts == other.parts
    def __ne__(self, other):
        return self.parts != other.parts

    def __str__(self):
        return self.raw

    def __repr__(self):
        return f"SimpleVersion({self.raw})"


def parse_requirements_line(line):
    """
    Parses a requirements.txt line.
    Returns (package_name, specifiers, marker) or None
    """
    line = line.strip()
    if not line or line.startswith('#') or line.startswith('-r') or line.startswith('-e'):
        return None

    # Handle markers if present
    marker = None
    if ';' in line:
        line, marker = line.split(';', 1)
        marker = marker.strip()

    # Split name and specifiers
    # Matches package name followed by constraints
    match = re.match(r'^([a-zA-Z0-9_\-\[\]]+)\s*(.*)$', line)
    if not match:
        return None

    name = match.group(1).lower().replace('_', '-')
    specs_str = match.group(2).strip()

    specifiers = []
    if specs_str:
        # Split specs by comma
        for spec in specs_str.split(','):
            spec = spec.strip()
            spec_match = re.match(r'^(==|>=|<=|>|<|!=|~=)\s*([0-9a-zA-Z\.\-\*\+]+)$', spec)
            if spec_match:
                op, ver = spec_match.group(1), spec_match.group(2)
                specifiers.append((op, SimpleVersion(ver)))
            else:
                # E.g. no operator, just version or invalid
                if spec:
                    specifiers.append(('==', SimpleVersion(spec)))

    return name, specifiers, marker


def parse_requirements_file(filepath):
    """Parses a requirements.txt file."""
    dependencies = {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            for i, line in enumerate(f, 1):
                parsed = parse_requirements_line(line)
                if parsed:
                    name, specs, marker = parsed
                    dependencies[name] = {
                        'specs': specs,
                        'marker': marker,
                        'line_num': i,
                        'raw': line.strip()
                    }
    except Exception as e:
        print(f"Error reading {filepath}: {e}", file=sys.stderr)
    return dependencies


def parse_pyproject_toml(filepath):
    """Parses dependencies from pyproject.toml using regex (no toml dependency)."""
    dependencies = {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()

        # Find dependencies block
        # Look for dependencies = [ ... ]
        dep_section_match = re.search(r'dependencies\s*=\s*\[(.*?)\]', content, re.DOTALL)
        if dep_section_match:
            deps_list = dep_section_match.group(1)
            # Find all strings in quotes
            deps = re.findall(r'"([^"]+)"|\'([^\']+)\'', deps_list)
            for d_tuple in deps:
                dep_str = d_tuple[0] or d_tuple[1]
                parsed = parse_requirements_line(dep_str)
                if parsed:
                    name, specs, marker = parsed
                    dependencies[name] = {
                        'specs': specs,
                        'marker': marker,
                        'line_num': 0,
                        'raw': dep_str
                    }
    except Exception as e:
        print(f"Error parsing {filepath}: {e}", file=sys.stderr)
    return dependencies


def scan_directory(path):
    """Scans directory recursively for requirements.txt and pyproject.toml."""
    files = []
    for root, _, filenames in os.walk(path):
        for f in filenames:
            if f == 'requirements.txt' or f == 'pyproject.toml':
                files.append(os.path.join(root, f))
    return files


def intersect_specifiers(specs_list):
    """
    Tries to merge list of specifiers for a package.
    Returns (merged_specs_str, conflicts_list)
    """
    # Combine all operators
    # Let's collect bounds
    min_val = None      # >=, >, ~=
    max_val = None      # <=, <
    exact_vals = set()  # ==
    exclude_vals = set() # !=

    conflicts = []

    for op, ver in specs_list:
        if op == '==':
            exact_vals.add(ver)
        elif op == '!=':
            exclude_vals.add(ver)
        elif op in ('>=', '>'):
            if min_val is None:
                min_val = (op, ver)
            else:
                # Take the stricter (higher) min
                if ver > min_val[1]:
                    min_val = (op, ver)
                elif ver == min_val[1] and op == '>':
                    min_val = (op, ver)
        elif op in ('<=', '<'):
            if max_val is None:
                max_val = (op, ver)
            else:
                # Take the stricter (lower) max
                if ver < max_val[1]:
                    max_val = (op, ver)
                elif ver == max_val[1] and op == '<':
                    max_val = (op, ver)
        elif op == '~=':
            # Compatible release: >= ver and < next major/minor release
            # Treat as >= ver for simplification, but note it
            if min_val is None or ver > min_val[1]:
                min_val = ('>=', ver)

    # Perform conflict resolution checks
    if exact_vals:
        if len(exact_vals) > 1:
            conflicts.append(f"Multiple exact versions requested: {', '.join(str(v) for v in exact_vals)}")
        else:
            val = list(exact_vals)[0]
            # Check if exact matches bounds
            if min_val:
                op_min, ver_min = min_val
                if op_min == '>=' and val < ver_min:
                    conflicts.append(f"Exact version {val} violates bound >= {ver_min}")
                elif op_min == '>' and val <= ver_min:
                    conflicts.append(f"Exact version {val} violates bound > {ver_min}")
            if max_val:
                op_max, ver_max = max_val
                if op_max == '<=' and val > ver_max:
                    conflicts.append(f"Exact version {val} violates bound <= {ver_max}")
                elif op_max == '<' and val >= ver_max:
                    conflicts.append(f"Exact version {val} violates bound < {ver_max}")
            if val in exclude_vals:
                conflicts.append(f"Exact version {val} is explicitly excluded in != rules")

    if min_val and max_val:
        op_min, ver_min = min_val
        op_max, ver_max = max_val
        if ver_min > ver_max:
            conflicts.append(f"Overlapping bounds are impossible: {op_min} {ver_min} and {op_max} {ver_max}")
        elif ver_min == ver_max and (op_min == '>' or op_max == '<'):
            conflicts.append(f"Exclusive bounds overlap on same version: {op_min} {ver_min} and {op_max} {ver_max}")

    # Build final string representation
    if conflicts:
        return None, conflicts

    merged_specs = []
    if exact_vals:
        merged_specs.append(f"=={list(exact_vals)[0]}")
    else:
        if min_val:
            merged_specs.append(f"{min_val[0]}{min_val[1]}")
        if max_val:
            merged_specs.append(f"{max_val[0]}{max_val[1]}")
        for excl in sorted(list(exclude_vals), key=lambda x: x.parts):
            merged_specs.append(f"!={excl}")

    return ",".join(merged_specs) if merged_specs else "", []


def main():
    parser = argparse.ArgumentParser(
        description="Scan, merge, and harmonize multiple requirements files and pyproject.toml dependencies."
    )
    parser.add_argument("inputs", nargs="+", help="Files, directories, or package lists to harmonize.")
    parser.add_argument("-o", "--output", help="Write harmonized requirements to this file.")
    parser.add_argument("--exclude", nargs="*", default=[], help="Folders or filenames to exclude from scan.")
    parser.add_argument("--ignore-conflicts", action="store_true", help="Print output even if conflicts exist.")
    
    args = parser.parse_args()

    all_files = []
    for inp in args.inputs:
        if os.path.isdir(inp):
            all_files.extend(scan_directory(inp))
        elif os.path.isfile(inp):
            all_files.append(inp)
        else:
            print(f"Warning: Input path '{inp}' does not exist or is not readable.", file=sys.stderr)

    # Filter exclusions
    filtered_files = []
    for f in all_files:
        should_exclude = False
        for excl in args.exclude:
            if excl in f:
                should_exclude = True
                break
        if not should_exclude:
            filtered_files.append(f)

    if not filtered_files:
        print("No dependency files found to harmonize.", file=sys.stderr)
        return 1

    print(f"Found {len(filtered_files)} files to harmonize:")
    for f in filtered_files:
        print(f"  - {f}")
    print()

    # Collect dependencies: pkg_name -> list of specs from files
    # Structure: pkg_name -> list of {'specs': [...], 'source': file_path, 'marker': ...}
    pkg_map = defaultdict(list)

    for filepath in filtered_files:
        if filepath.endswith('requirements.txt'):
            deps = parse_requirements_file(filepath)
        elif filepath.endswith('pyproject.toml'):
            deps = parse_pyproject_toml(filepath)
        else:
            continue

        for pkg, info in deps.items():
            pkg_map[pkg].append({
                'specs': info['specs'],
                'source': filepath,
                'marker': info['marker'],
                'raw': info['raw']
            })

    harmonized = {}
    conflicts_found = {}

    for pkg, occurrences in pkg_map.items():
        # Combine all specifiers across all files
        combined_specs = []
        markers = set()
        for occ in occurrences:
            combined_specs.extend(occ['specs'])
            if occ['marker']:
                markers.add(occ['marker'])

        merged, conflicts = intersect_specifiers(combined_specs)
        if conflicts:
            conflicts_found[pkg] = {
                'conflicts': conflicts,
                'sources': occurrences
            }
        else:
            harmonized[pkg] = {
                'specs': merged,
                'marker': "; " + " and ".join(markers) if markers else "",
                'sources': occurrences
            }

    # Print Report
    if conflicts_found:
        print("=== CONFLICTS DETECTED ===")
        for pkg, c_info in conflicts_found.items():
            print(f"\nPackage: {pkg}")
            for c in c_info['conflicts']:
                print(f"  [!] Conflict: {c}")
            print("  Sources:")
            for src in c_info['sources']:
                print(f"    - {src['source']}: '{src['raw']}'")
        print("\n==========================")
        if not args.ignore_conflicts:
            print("\nHarmonization failed due to conflicts. Resolve these conflicts or use --ignore-conflicts to output anyway.", file=sys.stderr)
            return 1
    else:
        print("Success! No conflicts detected.")

    # Format the harmonized requirements
    output_lines = ["# Harmonized dependencies generated by python_dependency_harmonizer.py\n"]
    for pkg in sorted(harmonized.keys()):
        h_info = harmonized[pkg]
        specs_str = h_info['specs']
        marker_str = h_info['marker']
        output_lines.append(f"{pkg}{specs_str}{marker_str}\n")

    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.writelines(output_lines)
            print(f"\nHarmonized dependencies written to {args.output}")
        except Exception as e:
            print(f"Error writing to output file {args.output}: {e}", file=sys.stderr)
            return 1
    else:
        print("\nHarmonized requirements output:")
        print("---------------------------------")
        for line in output_lines:
            sys.stdout.write(line)
        print("---------------------------------")

    return 0


if __name__ == "__main__":
    sys.exit(main())
