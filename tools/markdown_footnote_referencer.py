#!/usr/bin/env python3
"""
Markdown Footnote Validator & Auto-Formatter
--------------------------------------------
Scans Markdown documents for footnote references (`[^label]`) and definitions (`[^label]: text`).
Validates missing or unreferenced footnotes, detects duplicate labels, auto-renumbers footnote
references sequentially (1, 2, 3...) based on document flow, and re-orders definitions neatly
at the end of the document.

Author: Antigravity
License: MIT
"""

import sys
import os
import re
import json
import argparse
from typing import List, Dict, Any, Tuple, Optional

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ANSI Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Regex patterns
FOOTNOTE_REF_PATTERN = re.compile(r'\[\^([^\]]+)\](?!:)')
FOOTNOTE_DEF_PATTERN = re.compile(r'^\[\^([^\]]+)\]:\s*(.*)$')


class FootnoteAuditResult:
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.references: List[Tuple[str, int]] = []  # (label, line_num)
        self.definitions: Dict[str, Tuple[str, int]] = {}  # label -> (content, line_num)
        self.missing_defs: List[Tuple[str, int]] = []
        self.unused_defs: List[Tuple[str, int]] = []
        self.duplicate_defs: List[Tuple[str, int]] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "filepath": self.filepath,
            "total_references": len(self.references),
            "total_definitions": len(self.definitions),
            "missing_definitions": [{"label": l, "line": line} for l, line in self.missing_defs],
            "unused_definitions": [{"label": l, "line": line} for l, line in self.unused_defs],
            "duplicate_definitions": [{"label": l, "line": line} for l, line in self.duplicate_defs],
        }


def audit_markdown_content(content: str, filepath: str = "document.md") -> Tuple[FootnoteAuditResult, str]:
    lines = content.splitlines()
    result = FootnoteAuditResult(filepath)

    def_lines_indices = set()
    ref_order = []

    # Step 1: Scan for definitions
    i = 0
    while i < len(lines):
        line = lines[i]
        def_match = FOOTNOTE_DEF_PATTERN.match(line)
        if def_match:
            label = def_match.group(1).strip()
            first_line_content = def_match.group(2)
            def_lines_indices.add(i)

            # Collect multi-line indented continuation
            content_parts = [first_line_content]
            j = i + 1
            while j < len(lines):
                next_line = lines[j]
                if next_line.startswith("    ") or next_line.startswith("\t") or (not next_line.strip() and j + 1 < len(lines) and (lines[j+1].startswith("    ") or lines[j+1].startswith("\t"))):
                    content_parts.append(next_line)
                    def_lines_indices.add(j)
                    j += 1
                else:
                    break

            if label in result.definitions:
                result.duplicate_defs.append((label, i + 1))
            else:
                result.definitions[label] = ('\n'.join(content_parts), i + 1)
            i = j
            continue
        i += 1

    # Step 2: Scan for references
    for idx, line in enumerate(lines):
        if idx in def_lines_indices:
            continue
        for ref_match in FOOTNOTE_REF_PATTERN.finditer(line):
            label = ref_match.group(1).strip()
            result.references.append((label, idx + 1))
            if label not in [r[0] for r in ref_order]:
                ref_order.append((label, idx + 1))

    # Step 3: Compare references and definitions
    ref_labels = {r[0] for r in result.references}
    def_labels = set(result.definitions.keys())

    for label, line in result.references:
        if label not in def_labels:
            if (label, line) not in result.missing_defs:
                result.missing_defs.append((label, line))

    for label, (content, line) in result.definitions.items():
        if label not in ref_labels:
            result.unused_defs.append((label, line))

    # Step 4: Generate Auto-Formatted Content
    # Replace inline references with 1-based sequential numbering
    label_to_new_num = {}
    new_num = 1
    for label, _ in ref_order:
        label_to_new_num[label] = str(new_num)
        new_num += 1

    non_def_lines = [line for idx, line in enumerate(lines) if idx not in def_lines_indices]
    body_text = '\n'.join(non_def_lines)

    def replace_ref(match):
        label = match.group(1).strip()
        new_id = label_to_new_num.get(label, label)
        return f"[^{new_id}]"

    formatted_body = FOOTNOTE_REF_PATTERN.sub(replace_ref, body_text)

    # Append ordered definitions
    formatted_defs = []
    for orig_label, _ in ref_order:
        if orig_label in result.definitions:
            new_id = label_to_new_num[orig_label]
            def_body = result.definitions[orig_label][0]
            formatted_defs.append(f"[^{new_id}]: {def_body}")

    # Append any unused definitions at the end
    for orig_label, line in result.unused_defs:
        def_body = result.definitions[orig_label][0]
        formatted_defs.append(f"[^{orig_label}]: {def_body}")

    final_content = formatted_body.strip()
    if formatted_defs:
        final_content += "\n\n" + "\n".join(formatted_defs) + "\n"

    return result, final_content


def main():
    parser = argparse.ArgumentParser(description="Markdown Footnote Validator & Auto-Formatter")
    parser.add_argument("file", nargs="?", help="Markdown file to audit/format")
    parser.add_argument("--in-place", "-i", action="store_true", help="Overwrite file with auto-numbered and re-ordered footnotes")
    parser.add_argument("--out", "-o", help="Write formatted markdown to specified output file")
    parser.add_argument("--json", action="store_true", help="Output audit results in JSON format")

    args = parser.parse_args()

    if not args.file:
        print(f"{YELLOW}No file specified. Running demonstration with sample Markdown file:{RESET}\n")
        sample_md = (
            "# Document with Footnotes\n\n"
            "This is the first sentence with a footnote reference[^note-alpha].\n"
            "Here is another concept requiring explanation[^beta-ref].\n"
            "And here we reference the first note again[^note-alpha].\n\n"
            "Here is an unreferenced footnote reference[^missing-def].\n\n"
            "[^beta-ref]: Explanation of the second concept.\n"
            "[^note-alpha]: Detailed explanation of alpha.\n"
            "[^orphan]: An unused footnote definition that has no inline reference.\n"
        )
        print(f"{CYAN}{BOLD}Sample Input Markdown:{RESET}")
        print(sample_md)

        result, formatted = audit_markdown_content(sample_md, "sample.md")

        print(f"\n{BOLD}{BLUE}=== Audit Summary ==={RESET}")
        print(f"Total References: {len(result.references)} | Total Definitions: {len(result.definitions)}")
        if result.missing_defs:
            print(f"{RED}Missing Definitions ({len(result.missing_defs)}):{RESET}")
            for l, line in result.missing_defs:
                print(f"  {RED}✖ Reference [^{l}] on line {line} has no definition.{RESET}")
        if result.unused_defs:
            print(f"{YELLOW}Unused Definitions ({len(result.unused_defs)}):{RESET}")
            for l, line in result.unused_defs:
                print(f"  {YELLOW}⚠ Definition [^{l}] on line {line} is never referenced.{RESET}")

        print(f"\n{GREEN}{BOLD}Auto-Numbered & Formatted Markdown Output:{RESET}\n")
        print(formatted)
        return

    if not os.path.exists(args.file):
        print(f"{RED}Error: File '{args.file}' not found.{RESET}", file=sys.stderr)
        sys.exit(1)

    with open(args.file, "r", encoding="utf-8", errors="replace") as f:
        content = f.read()

    result, formatted = audit_markdown_content(content, args.file)

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
        return

    print(f"\n{BOLD}{BLUE}=== Footnote Audit Report: {args.file} ==={RESET}\n")
    print(f"Total References Found: {BOLD}{len(result.references)}{RESET}")
    print(f"Total Definitions Found: {BOLD}{len(result.definitions)}{RESET}\n")

    if result.missing_defs:
        print(f"{RED}{BOLD}Missing Definitions ({len(result.missing_defs)}):{RESET}")
        for l, line in result.missing_defs:
            print(f"  {RED}✖ Reference [^{l}] on line {line} is missing a definition!{RESET}")

    if result.unused_defs:
        print(f"\n{YELLOW}{BOLD}Unused Definitions ({len(result.unused_defs)}):{RESET}")
        for l, line in result.unused_defs:
            print(f"  {YELLOW}⚠ Definition [^{l}] on line {line} is defined but never referenced.{RESET}")

    if result.duplicate_defs:
        print(f"\n{RED}{BOLD}Duplicate Definitions ({len(result.duplicate_defs)}):{RESET}")
        for l, line in result.duplicate_defs:
            print(f"  {RED}✖ Duplicate definition for [^{l}] on line {line}.{RESET}")

    if not result.missing_defs and not result.unused_defs and not result.duplicate_defs:
        print(f"{GREEN}{BOLD}✔ All footnote references and definitions match perfectly!{RESET}")

    if args.in_place:
        with open(args.file, "w", encoding="utf-8") as f:
            f.write(formatted)
        print(f"\n{GREEN}✔ Updated '{args.file}' in-place with auto-numbered footnotes.{RESET}")

    elif args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(formatted)
        print(f"\n{GREEN}✔ Wrote auto-formatted Markdown to '{args.out}'.{RESET}")


if __name__ == "__main__":
    main()
