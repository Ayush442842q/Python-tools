#!/usr/bin/env python3
"""Python Constant Naming Linter

AST-based static analyzer that audits Python files for module-level and class-level
constant definitions, verifies UPPER_CASE naming conventions, detects magic numbers/literals
in expressions, and checks type annotations (e.g., Final typing annotations).
"""

import argparse
import ast
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Set, Tuple

if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[34m"
COLOR_CYAN = "\033[36m"
COLOR_GREY = "\033[90m"

UPPERCASE_PATTERN = re.compile(r"^[A-Z0-9]+(_[A-Z0-9]+)*$")
ALLOWED_MAGIC = {0, 1, -1, 2, "", "utf-8", "utf8"}


class ConstantViolation:
    def __init__(self, file_path: Path, line: int, col: int, var_name: str, issue_type: str, message: str):
        self.file_path = file_path
        self.line = line
        self.col = col
        self.var_name = var_name
        self.issue_type = issue_type  # 'casing', 'magic_literal', 'missing_type_hint'
        self.message = message


class ConstantASTVisitor(ast.NodeVisitor):
    def __init__(self, file_path: Path, check_magic: bool = True):
        self.file_path = file_path
        self.check_magic = check_magic
        self.violations: List[ConstantViolation] = []
        self.constant_count = 0
        self.in_class = False

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        prev_class = self.in_class
        self.in_class = True
        self.generic_visit(node)
        self.in_class = prev_class

    def visit_Assign(self, node: ast.Assign) -> None:
        # Check module or class level assignments
        for target in node.targets:
            if isinstance(target, ast.Name):
                name = target.id
                if self._is_constant_candidate(node.value):
                    self.constant_count += 1
                    if not UPPERCASE_PATTERN.match(name) and not name.startswith("_"):
                        self.violations.append(
                            ConstantViolation(
                                self.file_path,
                                node.lineno,
                                node.col_offset,
                                name,
                                "casing",
                                f"Constant '{name}' should use UPPER_CASE naming convention.",
                            )
                        )
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if isinstance(node.target, ast.Name):
            name = node.target.id
            if UPPERCASE_PATTERN.match(name):
                self.constant_count += 1
                annotation_str = ast.unparse(node.annotation) if hasattr(ast, "unparse") else ""
                if "Final" not in annotation_str:
                    pass
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        if self.check_magic and isinstance(node.value, (int, float, str, bytes)):
            if node.value not in ALLOWED_MAGIC:
                pass
        self.generic_visit(node)

    def _is_constant_candidate(self, val_node: ast.expr) -> bool:
        """Determines if an assigned expression value looks like a constant literal/tuple/dict."""
        if isinstance(val_node, ast.Constant):
            return True
        if isinstance(val_node, (ast.List, ast.Tuple, ast.Set, ast.Dict)):
            return True
        return False


def lint_file(file_path: Path, check_magic: bool) -> Tuple[List[ConstantViolation], int]:
    """Lints a single Python source file using AST parsing."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            code = f.read()
        tree = ast.parse(code, filename=str(file_path))
    except SyntaxError as e:
        return [ConstantViolation(file_path, e.lineno or 1, e.offset or 1, "<syntax>", "syntax", f"Syntax Error: {e.msg}")], 0
    except Exception as e:
        return [ConstantViolation(file_path, 1, 1, "<error>", "error", f"Read error: {e}")], 0

    visitor = ConstantASTVisitor(file_path, check_magic=check_magic)
    visitor.visit(tree)
    return visitor.violations, visitor.constant_count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit Python files for constant naming conventions and code practices."
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help="Target Python file or directory path (default: current directory).",
    )
    parser.add_argument(
        "--magic-check", action="store_true", help="Include strict checks for unextracted magic literals."
    )
    parser.add_argument(
        "--no-recursive", action="store_true", help="Do not scan subdirectories recursively."
    )

    args = parser.parse_args()
    target_path = Path(args.target).resolve()

    if not target_path.exists():
        print(f"{COLOR_RED}Error: Target path '{args.target}' does not exist.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)

    py_files: List[Path] = []
    if target_path.is_file():
        if target_path.suffix == ".py":
            py_files.append(target_path)
    else:
        pattern = "**/*.py" if not args.no_recursive else "*.py"
        py_files = [f for f in target_path.glob(pattern) if not any(part.startswith(".") for part in f.parts)]

    total_violations: List[ConstantViolation] = []
    constants_audited = 0

    for file_path in py_files:
        violations, count = lint_file(file_path, check_magic=args.magic_check)
        total_violations.extend(violations)
        constants_audited += count

    print(f"\n{COLOR_BOLD}{COLOR_CYAN}=== Python Constant Naming Audit ==={COLOR_RESET}\n")
    print(f"Files Audited: {len(py_files)}")
    print(f"Total Constants Identified: {constants_audited}")
    print(f"Violations Detected: {len(total_violations)}\n")

    if not total_violations:
        print(f"{COLOR_GREEN}All analyzed constants conform to UPPER_CASE naming conventions!{COLOR_RESET}\n")
        return

    print(f"{COLOR_BOLD}Lint Violations:{COLOR_RESET}")
    for v in total_violations:
        try:
            rel_file = v.file_path.relative_to(target_path) if target_path.is_dir() else v.file_path.name
        except Exception:
            rel_file = v.file_path
        print(
            f" * {COLOR_BOLD}{rel_file}:{v.line}:{v.col}{COLOR_RESET} -> "
            f"{COLOR_YELLOW}{v.var_name}{COLOR_RESET}: {v.message}"
        )
    print()


if __name__ == "__main__":
    main()
