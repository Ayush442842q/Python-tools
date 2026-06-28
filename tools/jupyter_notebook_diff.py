#!/usr/bin/env python3
"""
Jupyter Notebook Diff Tool

Performs a cell-by-cell structural comparison between two Jupyter Notebook (.ipynb) files.
It ignores noisy metadata changes by default and shows line-by-line colored code and markdown diffs
in the terminal.

Usage:
    python tools/jupyter_notebook_diff.py notebook1.ipynb notebook2.ipynb
"""

import argparse
import json
import os
import sys
import difflib

# Color codes for terminal output
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"
COLOR_RESET = "\033[0m"

def print_colored(text, color, use_color=True):
    if use_color and sys.stdout.isatty():
        print(f"{color}{text}{COLOR_RESET}")
    else:
        print(text)

def load_notebook(filepath):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading '{filepath}': {e}", file=sys.stderr)
        sys.exit(1)

def get_cells(notebook):
    return notebook.get("cells", [])

def format_cell_source(cell):
    source = cell.get("source", [])
    if isinstance(source, str):
        return source.splitlines()
    return [line.rstrip("\n") for line in source]

def format_cell_outputs(cell):
    outputs = cell.get("outputs", [])
    formatted = []
    for out in outputs:
        out_type = out.get("output_type")
        if out_type == "stream":
            text = out.get("text", [])
            formatted.extend(text if isinstance(text, list) else text.splitlines())
        elif out_type in ("execute_result", "display_data"):
            data = out.get("data", {})
            # Prefer plain text or JSON output representation
            if "text/plain" in data:
                text = data["text/plain"]
                formatted.extend(text if isinstance(text, list) else text.splitlines())
        elif out_type == "error":
            ename = out.get("ename", "Error")
            evalue = out.get("evalue", "")
            traceback = out.get("traceback", [])
            formatted.append(f"{ename}: {evalue}")
            formatted.extend(traceback)
    return [line.rstrip("\n") for line in formatted]

def diff_lines(lines1, lines2, use_color=True):
    diff = list(difflib.ndiff(lines1, lines2))
    has_changes = False
    diff_output = []
    
    for line in diff:
        if line.startswith("- "):
            has_changes = True
            diff_output.append((line, COLOR_RED))
        elif line.startswith("+ "):
            has_changes = True
            diff_output.append((line, COLOR_GREEN))
        elif line.startswith("? "):
            # Sub-line changes helper guidance
            diff_output.append((line, COLOR_YELLOW))
        else:
            diff_output.append((line, None))
            
    return has_changes, diff_output

def main():
    parser = argparse.ArgumentParser(description="Jupyter Notebook cell-by-cell diff tool")
    parser.add_argument("notebook1", help="Path to the original notebook (.ipynb)")
    parser.add_argument("notebook2", help="Path to the modified notebook (.ipynb)")
    parser.add_argument("--ignore-outputs", action="store_true", help="Do not diff cell execution outputs")
    parser.add_argument("--ignore-metadata", action="store_true", default=True, help="Ignore metadata differences (default: True)")
    parser.add_argument("--show-metadata", action="store_false", dest="ignore_metadata", help="Show metadata differences")
    parser.add_argument("--no-color", action="store_true", help="Disable terminal colors")

    args = parser.parse_args()
    use_color = not args.no_color

    if not os.path.exists(args.notebook1):
        print(f"Error: file '{args.notebook1}' does not exist.", file=sys.stderr)
        return 1
    if not os.path.exists(args.notebook2):
        print(f"Error: file '{args.notebook2}' does not exist.", file=sys.stderr)
        return 1

    nb1 = load_notebook(args.notebook1)
    nb2 = load_notebook(args.notebook2)

    cells1 = get_cells(nb1)
    cells2 = get_cells(nb2)

    print_colored(f"Comparing notebooks:", COLOR_BOLD, use_color)
    print_colored(f"  Notebook 1 (Base): {args.notebook1} ({len(cells1)} cells)", COLOR_CYAN, use_color)
    print_colored(f"  Notebook 2 (Head): {args.notebook2} ({len(cells2)} cells)", COLOR_CYAN, use_color)
    print("=" * 80)

    max_cells = max(len(cells1), len(cells2))
    any_differences = False

    for idx in range(max_cells):
        if idx >= len(cells1):
            # Cell added in notebook 2
            any_differences = True
            cell2 = cells2[idx]
            cell_type = cell2.get("cell_type", "unknown")
            print_colored(f"\n[Cell {idx + 1}] Added Cell ({cell_type.upper()})", COLOR_GREEN, use_color)
            print("-" * 40)
            source = format_cell_source(cell2)
            for line in source:
                print_colored(f"+ {line}", COLOR_GREEN, use_color)
            continue

        if idx >= len(cells2):
            # Cell deleted in notebook 2
            any_differences = True
            cell1 = cells1[idx]
            cell_type = cell1.get("cell_type", "unknown")
            print_colored(f"\n[Cell {idx + 1}] Deleted Cell ({cell_type.upper()})", COLOR_RED, use_color)
            print("-" * 40)
            source = format_cell_source(cell1)
            for line in source:
                print_colored(f"- {line}", COLOR_RED, use_color)
            continue

        cell1 = cells1[idx]
        cell2 = cells2[idx]

        type1 = cell1.get("cell_type", "")
        type2 = cell2.get("cell_type", "")

        # Check if cell type changed
        if type1 != type2:
            any_differences = True
            print_colored(f"\n[Cell {idx + 1}] Cell Type Changed: {type1.upper()} -> {type2.upper()}", COLOR_YELLOW, use_color)
            print("-" * 40)
            print_colored(f"- Type: {type1}", COLOR_RED, use_color)
            print_colored(f"+ Type: {type2}", COLOR_GREEN, use_color)
            continue

        # Diff source code / markdown content
        src1 = format_cell_source(cell1)
        src2 = format_cell_source(cell2)
        source_changed, source_diff = diff_lines(src1, src2, use_color)

        # Diff outputs if code cell and not ignored
        output_changed = False
        output_diff = []
        if type1 == "code" and not args.ignore_outputs:
            out1 = format_cell_outputs(cell1)
            out2 = format_cell_outputs(cell2)
            output_changed, output_diff = diff_lines(out1, out2, use_color)

        # Diff cell-level metadata if not ignored
        meta_changed = False
        meta_diff = []
        if not args.ignore_metadata:
            meta1 = json.dumps(cell1.get("metadata", {}), indent=2).splitlines()
            meta2 = json.dumps(cell2.get("metadata", {}), indent=2).splitlines()
            meta_changed, meta_diff = diff_lines(meta1, meta2, use_color)

        if source_changed or output_changed or meta_changed:
            any_differences = True
            print_colored(f"\n[Cell {idx + 1}] Modified ({type1.upper()})", COLOR_YELLOW, use_color)
            print("-" * 40)

            if source_changed:
                print_colored("--- Source changes ---", COLOR_CYAN, use_color)
                for line, color in source_diff:
                    if color:
                        print_colored(line, color, use_color)
                    else:
                        print(line)

            if output_changed:
                print_colored("--- Output changes ---", COLOR_CYAN, use_color)
                for line, color in output_diff:
                    if color:
                        print_colored(line, color, use_color)
                    else:
                        print(line)

            if meta_changed:
                print_colored("--- Metadata changes ---", COLOR_CYAN, use_color)
                for line, color in meta_diff:
                    if color:
                        print_colored(line, color, use_color)
                    else:
                        print(line)

    if not any_differences:
        print_colored("Notebooks are identical (excluding metadata if ignored).", COLOR_GREEN, use_color)
        return 0

    return 1

if __name__ == "__main__":
    sys.exit(main())
