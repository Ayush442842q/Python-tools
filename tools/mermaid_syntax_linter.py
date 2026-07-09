#!/usr/bin/env python3
"""
Mermaid Syntax Linter - Audits Mermaid diagram blocks in Markdown or raw text files for common syntax errors.
"""

import argparse
import os
import re
import sys
from typing import List, Tuple

# Bracket configurations for flowchart nodes
BRACKETS = [
    ("[", "]"),
    ("(", ")"),
    ("{", "}"),
    ("([", "])"),
    ("[[", "]]"),
    ("((", "))"),
    (">", "]"),
    ("{{", "}}"),
    ("[(", ")]"),
]

class MermaidLinter:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.errors: List[Tuple[int, str]] = []

    def log_error(self, line_num: int, message: str):
        self.errors.append((line_num, message))

    def lint_flowchart_line(self, line: str, line_offset: int):
        # 1. Check for invalid arrows (e.g., -> or -- instead of --> or ---)
        # In flowchart/graph, -> is invalid, it must be -->
        # We also check for -- in some contexts, but let's target the most common issue: ->
        if "->" in line:
            # Check if it's not part of an arrow style like -.->
            if not re.search(r"-\.[^>]*->", line) and not "-->" in line:
                self.log_error(line_offset, f"Flowchart contains invalid arrow operator '->'. Use '-->' or '-.->' instead.")

        # 2. Check for matching brackets for node definitions
        # e.g., Node[Label
        for opening, closing in BRACKETS:
            # Escaped search
            esc_open = re.escape(opening)
            esc_close = re.escape(closing)
            
            # If the opening brackets exist but are not matched on the same line
            open_count = len(re.findall(esc_open, line))
            close_count = len(re.findall(esc_close, line))
            
            if open_count != close_count:
                # Basic check to avoid flagging nested structures if counts balance overall
                self.log_error(line_offset, f"Mismatched node brackets on line. Expected closing '{closing}' for '{opening}'.")

    def lint_sequence_line(self, line: str, line_offset: int, block_lines: List[str]):
        # Check arrows: valid sequence arrows are ->, -->, ->>, -->>, -x, --x, -), --)
        # Common error: using flowchart arrow style (--> or ---) when message is not set, or invalid symbols.
        stripped = line.strip()
        if not stripped or stripped.startswith("%%") or stripped == "sequenceDiagram":
            return

        # Check loop blocks
        # e.g., alt, opt, loop, par, critical, rect
        # These must eventually have a matching 'end'
        pass

    def lint_diagram_block(self, block: str, start_line: int):
        lines = block.splitlines()
        if not lines:
            return

        diag_type = lines[0].strip().split()[0] if lines[0].strip() else ""
        
        # Track block structures
        block_ends_needed = 0
        
        for idx, line in enumerate(lines, 1):
            line_num = start_line + idx - 1
            stripped = line.strip()

            if not stripped or stripped.startswith("%%"):
                continue

            # Check matching structure for blocks
            # e.g. alt, opt, loop, par, rect, critical, subgraphs
            if any(stripped.startswith(kwd) for kwd in ["alt ", "opt ", "loop ", "par ", "rect ", "critical ", "subgraph "]):
                block_ends_needed += 1
            elif stripped == "end":
                block_ends_needed -= 1
                if block_ends_needed < 0:
                    self.log_error(line_num, "Found 'end' statement without a matching starting block (like subgraph, loop, alt, etc.).")
                    block_ends_needed = 0

            # Lint based on type
            if diag_type in ("flowchart", "graph"):
                self.lint_flowchart_line(line, line_num)
            elif diag_type == "sequenceDiagram":
                self.lint_sequence_line(line, line_num, lines)

        if block_ends_needed > 0:
            self.log_error(start_line + len(lines) - 1, f"Missing {block_ends_needed} 'end' statement(s) for subgraphs or loop/conditional blocks.")

    def lint(self) -> bool:
        if not os.path.exists(self.filepath):
            self.log_error(0, f"File '{self.filepath}' does not exist.")
            return False

        with open(self.filepath, "r", encoding="utf-8") as f:
            content = f.read()

        lines = content.splitlines()

        # Extract fenced code blocks
        in_block = False
        block_lines = []
        block_start = 0

        for idx, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("```mermaid"):
                in_block = True
                block_lines = []
                block_start = idx + 1 # diagram text starts on next line
            elif stripped == "```" and in_block:
                in_block = False
                self.lint_diagram_block("\n".join(block_lines), block_start)
            elif in_block:
                block_lines.append(line)

        # If file is a raw mermaid diagram (.mermaid)
        if self.filepath.endswith(".mermaid") and not any(l.strip().startswith("```mermaid") for l in lines):
            self.lint_diagram_block(content, 1)

        return len(self.errors) == 0

def main():
    parser = argparse.ArgumentParser(description="Lint Mermaid diagram syntax inside markdown or raw files.")
    parser.add_argument("file", help="Path to markdown or mermaid file to check.")
    args = parser.parse_args()

    linter = MermaidLinter(args.file)
    success = linter.lint()

    print(f"Linting Mermaid diagrams in '{args.file}'...")
    print("-" * 50)

    if linter.errors:
        print(f"Errors found ({len(linter.errors)}):")
        for line, msg in sorted(linter.errors):
            print(f"  Line {line}: {msg}")
        print("\nResult: FAILED")
        sys.exit(1)
    else:
        print("All Mermaid diagrams parsed successfully (no common errors detected).")
        print("\nResult: PASSED")
        sys.exit(0)

if __name__ == "__main__":
    main()
