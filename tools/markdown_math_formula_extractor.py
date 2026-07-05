#!/usr/bin/env python3
"""Markdown Math Formula Extractor

Scan Markdown files to extract, validate, and summarize embedded TeX/LaTeX math
formulas ($...$, $$...$$, and \\begin{...} environments), checking bracket matching
and rendering standalone LaTeX or JSON inventories.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any

# ANSI Colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[34m"
COLOR_CYAN = "\033[36m"
COLOR_GREY = "\033[90m"


class MathFormulaExtractor:
    def __init__(self):
        # Regex patterns
        self.code_block_pattern = re.compile(r'```[\s\S]*?```|`[^`\n]+`')
        self.block_math_pattern = re.compile(r'\$\$\s*([\s\S]*?)\s*\$\$|\\begin\{([a-zA-Z0-9\*]+)\}([\s\S]*?)\\end\{\2\}')
        self.inline_math_pattern = re.compile(r'(?<!\$)\$([^\$\n]+)\$(?!\$)')

    def strip_code_blocks(self, text: str) -> str:
        """Replace code blocks with empty spaces preserving line counts."""
        def replace_with_newlines(match):
            return "\n" * match.group(0).count("\n")
        return self.code_block_pattern.sub(replace_with_newlines, text)

    def validate_brackets(self, expression: str) -> List[str]:
        """Validate bracket balance and left/right symmetry."""
        errors = []
        stack = []
        pairs = {'{': '}', '[': ']', '(': ')'}

        in_escape = False
        for char in expression:
            if in_escape:
                in_escape = False
                continue
            if char == '\\':
                in_escape = True
                continue
            if char in pairs:
                stack.append(char)
            elif char in pairs.values():
                if not stack:
                    errors.append(f"Unmatched closing bracket '{char}'")
                    break
                top = stack.pop()
                if pairs[top] != char:
                    errors.append(f"Mismatched bracket pair: '{top}' and '{char}'")
                    break

        if stack and not errors:
            errors.append(f"Unclosed bracket '{stack[-1]}'")

        # Check \left vs \right counts
        left_count = len(re.findall(r'\\left\b', expression))
        right_count = len(re.findall(r'\\right\b', expression))
        if left_count != right_count:
            errors.append(f"Mismatched \\left ({left_count}) and \\right ({right_count}) commands")

        return errors

    def extract_from_file(self, filepath: Path) -> List[Dict[str, Any]]:
        try:
            raw_content = filepath.read_text(encoding="utf-8", errors="replace")
        except Exception as e:
            return [{
                "file": str(filepath),
                "line": 1,
                "type": "Error",
                "formula": "",
                "errors": [f"Could not read file: {e}"]
            }]

        clean_content = self.strip_code_blocks(raw_content)
        formulas: List[Dict[str, Any]] = []

        current_heading = "Preamble"
        lines = clean_content.splitlines()

        # Track line positions
        line_offsets = []
        acc = 0
        for l in lines:
            line_offsets.append(acc)
            acc += len(l) + 1

        def get_line_num(char_offset: int) -> int:
            for i, off in enumerate(line_offsets):
                if char_offset < off:
                    return max(1, i)
            return len(lines)

        # 1. Extract block math
        for m in self.block_math_pattern.finditer(clean_content):
            start_pos = m.start()
            line_num = get_line_num(start_pos)

            if m.group(1):
                expr = m.group(1).strip()
                kind = "display_block ($$)"
            else:
                env_name = m.group(2)
                body = m.group(3).strip()
                expr = f"\\begin{{{env_name}}}\n{body}\n\\end{{{env_name}}}"
                kind = f"environment ({env_name})"

            syntax_errors = self.validate_brackets(expr)
            formulas.append({
                "file": str(filepath),
                "line": line_num,
                "type": kind,
                "formula": expr,
                "errors": syntax_errors
            })

        # Temporarily mask block math before searching inline math
        masked_content = self.block_math_pattern.sub(lambda m: " " * len(m.group(0)), clean_content)

        # 2. Extract inline math
        for m in self.inline_math_pattern.finditer(masked_content):
            start_pos = m.start()
            line_num = get_line_num(start_pos)
            expr = m.group(1).strip()

            if not expr:
                continue

            syntax_errors = self.validate_brackets(expr)
            formulas.append({
                "file": str(filepath),
                "line": line_num,
                "type": "inline ($)",
                "formula": expr,
                "errors": syntax_errors
            })

        formulas.sort(key=lambda x: x["line"])
        return formulas


def generate_latex_doc(formulas: List[Dict[str, Any]]) -> str:
    lines = [
        "\\documentclass{article}",
        "\\usepackage{amsmath}",
        "\\usepackage{amssymb}",
        "\\usepackage{geometry}",
        "\\geometry{margin=1in}",
        "\\title{Extracted Markdown Formulas}",
        "\\date{\\today}",
        "\\begin{document}",
        "\\maketitle",
        ""
    ]

    by_file: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for f in formulas:
        by_file[f["file"]].append(f)

    for fname, items in by_file.items():
        clean_fname = fname.replace("_", "\\_")
        lines.append(f"\\section{{{clean_fname}}}")
        for item in items:
            lines.append(f"\\noindent \\textbf{{Line {item['line']} ({item['type']}):}}")
            if "inline" in item["type"]:
                lines.append(f"${item['formula']}$\n")
            else:
                lines.append(f"\\[\n{item['formula']}\n\\]\n")

    lines.append("\\end{document}")
    return "\n".join(lines)


def run_tests():
    """Self-test for markdown_math_formula_extractor."""
    sample_md = r"""# Sample Document
Here is inline math $E = mc^2$ and another $\frac{a}{b}$.

```python
# $not_math$ in python block
```

$$
\int_{0}^{\infty} e^{-x^2} dx = \frac{\sqrt{\pi}}{2}
$$

Broken formula: $\left( x + 1 \right$.
"""
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8") as f:
        f.write(sample_md)
        tmp_name = f.name

    try:
        extractor = MathFormulaExtractor()
        results = extractor.extract_from_file(Path(tmp_name))
        assert len(results) == 4, f"Expected 4 formulas, got {len(results)}"
        assert any(r["formula"] == "E = mc^2" for r in results), "Failed to find inline math E=mc^2"
        assert any("int_{0}" in r["formula"] for r in results), "Failed to find integral formula"
        assert any(len(r["errors"]) > 0 for r in results), "Failed to detect broken formula error"
        print(f"{COLOR_GREEN}All tests passed successfully!{COLOR_RESET}")
    finally:
        if os.path.exists(tmp_name):
            os.remove(tmp_name)


def main():
    parser = argparse.ArgumentParser(
        description="Extract and validate TeX/LaTeX formulas from Markdown files."
    )
    parser.add_argument("target", nargs="?", default=".", help="File or directory to scan (default: current directory)")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--export-tex", help="Save extracted formulas as a compiled LaTeX document (.tex)")
    parser.add_argument("--test", action="store_true", help="Run internal self-tests")

    args = parser.parse_args()

    if args.test:
        run_tests()
        return 0

    target_path = Path(args.target)
    if not target_path.exists():
        print(f"{COLOR_RED}Error: Path '{target_path}' does not exist.{COLOR_RESET}", file=sys.stderr)
        return 1

    md_files: List[Path] = []
    if target_path.is_file() and target_path.suffix.lower() in (".md", ".markdown"):
        md_files.append(target_path)
    elif target_path.is_dir():
        md_files = sorted([p for p in target_path.rglob("*") if p.suffix.lower() in (".md", ".markdown") and not any(part.startswith(".") for part in p.parts)])

    extractor = MathFormulaExtractor()
    all_formulas: List[Dict[str, Any]] = []
    for fpath in md_files:
        all_formulas.extend(extractor.extract_from_file(fpath))

    if args.export_tex:
        tex_content = generate_latex_doc(all_formulas)
        Path(args.export_tex).write_text(tex_content, encoding="utf-8")
        print(f"{COLOR_GREEN}Exported LaTeX document to '{args.export_tex}'{COLOR_RESET}")

    if args.json:
        print(json.dumps(all_formulas, indent=2))
        return 0

    print(f"\n{COLOR_BOLD}{COLOR_CYAN}=== Markdown Math Formula Extractor ==={COLOR_RESET}")
    print(f"Scanned {len(md_files)} file(s). Found {len(all_formulas)} formula(s).\n")

    if not all_formulas:
        print(f"{COLOR_YELLOW}No LaTeX formulas found.{COLOR_RESET}\n")
        return 0

    for item in all_formulas:
        err_badge = f" {COLOR_RED}[{len(item['errors'])} syntax error(s)]{COLOR_RESET}" if item["errors"] else ""
        print(f"{COLOR_BOLD}{item['file']}:{item['line']}{COLOR_RESET} [{COLOR_CYAN}{item['type']}{COLOR_RESET}]{err_badge}")
        print(f"  {COLOR_GREEN}{item['formula']}{COLOR_RESET}")
        for err in item["errors"]:
            print(f"    {COLOR_RED}⚠ {err}{COLOR_RESET}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
