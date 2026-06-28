#!/usr/bin/env python3
"""
Markdown & Jupyter Notebook Converter
Converts between Markdown (.md) and Jupyter Notebook (.ipynb) files.
Extracts code blocks into code cells and text into markdown cells (and vice versa).

License: MIT
"""

import os
import sys
import json
import argparse

# ANSI color codes for pretty CLI terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'

def print_success(msg):
    print(f"{Colors.GREEN}[✓] {msg}{Colors.ENDC}")

def print_info(msg):
    print(f"{Colors.BLUE}[i] {msg}{Colors.ENDC}")

def print_warning(msg):
    print(f"{Colors.YELLOW}[!] {msg}{Colors.ENDC}")

def print_error(msg):
    print(f"{Colors.RED}[✗] Error: {msg}{Colors.ENDC}", file=sys.stderr)

def markdown_to_ipynb(md_path, ipynb_path, default_lang="python"):
    """Converts a Markdown file to a Jupyter Notebook (.ipynb)."""
    if not os.path.exists(md_path):
        raise FileNotFoundError(f"Markdown file not found: {md_path}")

    print_info(f"Reading markdown file: {md_path}")
    with open(md_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    cells = []
    current_block = []
    in_code_block = False
    block_lang = default_lang

    for line in lines:
        if line.strip().startswith("```"):
            # Code block boundary detected
            if in_code_block:
                # Ending a code block
                cells.append({
                    "cell_type": "code",
                    "execution_count": None,
                    "metadata": {},
                    "outputs": [],
                    "source": current_block
                })
                current_block = []
                in_code_block = False
            else:
                # Starting a code block
                # Save previous markdown block if it has content
                if current_block:
                    cells.append({
                        "cell_type": "markdown",
                        "metadata": {},
                        "source": current_block
                    })
                    current_block = []
                
                in_code_block = True
                # Extract language if specified, e.g., ```python
                lang_spec = line.strip()[3:].strip()
                block_lang = lang_spec if lang_spec else default_lang
        else:
            current_block.append(line)

    # Append remaining markdown block if any
    if current_block:
        cells.append({
            "cell_type": "code" if in_code_block else "markdown",
            "execution_count": None if in_code_block else None,
            "metadata": {},
            "outputs": [] if in_code_block else None,
            "source": current_block
        } if in_code_block else {
            "cell_type": "markdown",
            "metadata": {},
            "source": current_block
        })

    # Clean up empty cells and ensure source arrays are list of strings
    valid_cells = []
    for cell in cells:
        # Check if cell has content
        if "".join(cell["source"]).strip():
            valid_cells.append(cell)

    # Build the notebook structure
    notebook = {
        "cells": valid_cells,
        "metadata": {
            "kernelspec": {
                "display_name": f"{default_lang.capitalize()} 3",
                "language": default_lang,
                "name": default_lang
            },
            "language_info": {
                "name": default_lang
            }
        },
        "nbformat": 4,
        "nbformat_minor": 2
    }

    print_info(f"Writing Jupyter Notebook with {len(valid_cells)} cells to: {ipynb_path}")
    with open(ipynb_path, 'w', encoding='utf-8') as f:
        json.dump(notebook, f, indent=2)
    
    print_success("Conversion completed successfully!")

def ipynb_to_markdown(ipynb_path, md_path):
    """Converts a Jupyter Notebook (.ipynb) to a Markdown file."""
    if not os.path.exists(ipynb_path):
        raise FileNotFoundError(f"Notebook file not found: {ipynb_path}")

    print_info(f"Reading notebook file: {ipynb_path}")
    with open(ipynb_path, 'r', encoding='utf-8') as f:
        notebook = json.load(f)

    cells = notebook.get("cells", [])
    md_lines = []

    # Get language from metadata
    lang_info = notebook.get("metadata", {}).get("language_info", {})
    nb_lang = lang_info.get("name", "python")

    print_info(f"Processing {len(cells)} cells...")
    for idx, cell in enumerate(cells):
        cell_type = cell.get("cell_type", "markdown")
        source = cell.get("source", [])
        
        # Ensure source is a list of strings
        if isinstance(source, str):
            source = source.splitlines(keepends=True)
            
        if not source:
            continue

        # Add newline separator between cells
        if md_lines:
            md_lines.append("\n")

        if cell_type == "markdown":
            # Add markdown text directly
            for line in source:
                md_lines.append(line)
        elif cell_type == "code":
            # Wrap code in markdown code blocks
            md_lines.append(f"```{nb_lang}\n")
            for line in source:
                # Make sure the line ends with a newline
                if not line.endswith("\n"):
                    line += "\n"
                md_lines.append(line)
            md_lines.append("```\n")

    print_info(f"Writing Markdown file to: {md_path}")
    with open(md_path, 'w', encoding='utf-8') as f:
        f.writelines(md_lines)

    print_success("Conversion completed successfully!")

def main():
    parser = argparse.ArgumentParser(
        description="Convert between Markdown (.md) and Jupyter Notebook (.ipynb) files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Convert markdown to a notebook
  python markdown_notebook_converter.py -i README.md -o notebook.ipynb
  
  # Convert a notebook back to markdown
  python markdown_notebook_converter.py -i notebook.ipynb -o output.md
        """
    )
    
    parser.add_argument("-i", "--input", required=True, help="Path to the input file (.md or .ipynb)")
    parser.add_argument("-o", "--output", help="Path to the output file (auto-generated if not specified)")
    parser.add_argument("-l", "--lang", default="python", help="Default language spec for code cells (default: python)")
    
    args = parser.parse_args()

    input_path = args.input
    output_path = args.output

    if not os.path.exists(input_path):
        print_error(f"Input file does not exist: {input_path}")
        sys.exit(1)

    # Determine conversion direction
    ext = os.path.splitext(input_path.lower())[1]
    
    try:
        if ext == '.md':
            if not output_path:
                output_path = os.path.splitext(input_path)[0] + '.ipynb'
            print_info(f"Mode: Markdown -> Jupyter Notebook")
            markdown_to_ipynb(input_path, output_path, args.lang)
        elif ext == '.ipynb':
            if not output_path:
                output_path = os.path.splitext(input_path)[0] + '.md'
            print_info(f"Mode: Jupyter Notebook -> Markdown")
            ipynb_to_markdown(input_path, output_path)
        else:
            print_error("Input file must have either .md or .ipynb extension.")
            sys.exit(1)
    except Exception as e:
        print_error(str(e))
        sys.exit(1)

if __name__ == "__main__":
    main()
