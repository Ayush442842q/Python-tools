#!/usr/bin/env python3
"""
Jupyter Notebook Linter
A static analyzer for Jupyter Notebook (.ipynb) files to identify syntax errors,
out-of-order execution, unused imports, empty cells, and code structure issues.
"""

import os
import sys
import json
import ast
import argparse

class ImportVisitor(ast.NodeVisitor):
    def __init__(self):
        self.imports = set()
        self.names = set()

    def visit_Import(self, node):
        for name in node.names:
            alias = name.asname or name.name
            # Keep track of top level module name or alias
            self.imports.add((alias, node.lineno))
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        for name in node.names:
            alias = name.asname or name.name
            self.imports.add((alias, node.lineno))
        self.generic_visit(node)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Load):
            self.names.add(node.id)
        self.generic_visit(node)

def lint_notebook(notebook_path):
    try:
        with open(notebook_path, 'r', encoding='utf-8') as f:
            nb = json.load(f)
    except Exception as e:
        print(f"Error: Unable to parse JSON in '{notebook_path}': {e}")
        return False

    cells = nb.get('cells', [])
    if not cells:
        print("Warning: Notebook contains no cells.")
        return True

    errors = []
    warnings = []
    
    execution_sequence = []
    all_code = ""
    imported_names = []  # List of tuples: (name, cell_index, line_no)
    used_names = set()
    
    code_cells_count = 0
    markdown_cells_count = 0
    
    for idx, cell in enumerate(cells):
        cell_type = cell.get('cell_type')
        source = "".join(cell.get('source', []))
        
        if cell_type == 'markdown':
            markdown_cells_count += 1
            
        elif cell_type == 'code':
            code_cells_count += 1
            exec_count = cell.get('execution_count')
            
            # 1. Out of order execution check
            if exec_count is not None:
                execution_sequence.append((idx, exec_count))
                
            # 2. Empty cell check
            if not source.strip():
                warnings.append(f"Cell #{idx} (Code) is empty.")
                continue
                
            # 3. Cell size check
            lines = source.splitlines()
            if len(lines) > 60:
                warnings.append(f"Cell #{idx} has too many lines ({len(lines)} lines). Consider splitting it.")
                
            # 4. Syntax & AST parsing check
            try:
                tree = ast.parse(source)
                
                # Extract imports and usage
                visitor = ImportVisitor()
                visitor.visit(tree)
                for imp_name, line in visitor.imports:
                    imported_names.append((imp_name, idx, line))
                used_names.update(visitor.names)
                
            except SyntaxError as se:
                errors.append(f"Cell #{idx} has Syntax Error: {se.msg} (Line {se.lineno}, Col {se.offset})")
                
    # 5. Analyze execution counts for regressions
    last_val = -1
    for cell_idx, count in execution_sequence:
        if count is not None:
            if count < last_val:
                warnings.append(
                    f"Out-of-order execution detected: Cell #{cell_idx} was run as execution #{count} "
                    f"which is lower than a previous cell's execution count (#{last_val})."
                )
            last_val = count
            
    # 6. Check for unused imports (simple heuristic: name defined in imports but never loaded in any cell)
    # Filter out imports that are used
    for imp_name, cell_idx, line in imported_names:
        if imp_name not in used_names:
            warnings.append(f"Cell #{cell_idx}: Import '{imp_name}' appears to be unused.")

    # 7. Overall stats
    print("=" * 60)
    print(f" LINT REPORT: {os.path.basename(notebook_path)}")
    print("=" * 60)
    print(f"Total Cells:     {len(cells)}")
    print(f"Code Cells:      {code_cells_count}")
    print(f"Markdown Cells:  {markdown_cells_count}")
    
    if code_cells_count > 0:
        ratio = markdown_cells_count / code_cells_count
        print(f"Doc/Code Ratio:  {ratio:.2f}")
        if ratio < 0.15:
            warnings.append("Notebook has low documentation-to-code ratio. Consider adding markdown cells.")
    else:
        print("Doc/Code Ratio:  N/A (No code cells)")
        
    print("-" * 60)
    
    if errors:
        print(f"Syntax Errors ({len(errors)}):")
        for err in errors:
            print(f"  [ERROR] {err}")
        print()
    else:
        print("Syntax: Well-formed. No syntax errors detected.\n")

    if warnings:
        print(f"Lint Warnings ({len(warnings)}):")
        for warn in warnings:
            print(f"  [WARN]  {warn}")
    else:
        print("Lint: No warnings. Code style and execution sequence look clean.")
        
    print("=" * 60)
    
    return len(errors) == 0

def main():
    parser = argparse.ArgumentParser(description="Jupyter Notebook Linter")
    parser.add_argument("notebook", help="Path to the .ipynb file to lint")
    args = parser.parse_args()

    if not os.path.exists(args.notebook):
        print(f"Error: File '{args.notebook}' does not exist.")
        sys.exit(1)

    if not args.notebook.endswith('.ipynb'):
        print("Warning: File does not have a .ipynb extension, but attempting to parse anyway.")

    success = lint_notebook(args.notebook)
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
