#!/usr/bin/env python3
"""
Jupyter Notebook Cell Execution Order Auditor
Statically inspects Jupyter notebooks (.ipynb) to verify if cells were run in a linear order,
and analyzes Python AST to detect variable dependencies that break sequential execution.
"""

import os
import sys
import json
import ast
import argparse

class VariableTracker(ast.NodeVisitor):
    def __init__(self):
        self.defined = set()
        self.used = set()
        self._local_scopes = []

    def visit_FunctionDef(self, node):
        self.defined.add(node.name)
        # Function arguments and body are local scope
        self._local_scopes.append(set())
        for arg in node.args.args:
            self._local_scopes[-1].add(arg.arg)
        if node.args.vararg:
            self._local_scopes[-1].add(node.args.vararg.arg)
        if node.args.kwarg:
            self._local_scopes[-1].add(node.args.kwarg.arg)
        
        # Visit children
        for child in node.body:
            self.visit(child)
        self._local_scopes.pop()

    def visit_ClassDef(self, node):
        self.defined.add(node.name)
        # Class definition is a new scope, but class body has special rules. 
        # For simplicity, we just traverse the body.
        for child in node.body:
            self.visit(child)

    def visit_Name(self, node):
        if isinstance(node.ctx, ast.Store):
            # Check if it's defined in a local scope (e.g. inside a function)
            if not self._local_scopes or all(node.id not in scope for scope in self._local_scopes):
                self.defined.add(node.id)
        elif isinstance(node.ctx, ast.Load):
            # Check if it's used and not defined in a local scope
            if not self._local_scopes or all(node.id not in scope for scope in self._local_scopes):
                self.used.add(node.id)

    def visit_Import(self, node):
        for alias in node.names:
            self.defined.add(alias.asname or alias.name)

    def visit_ImportFrom(self, node):
        for alias in node.names:
            self.defined.add(alias.asname or alias.name)

    def visit_For(self, node):
        # Gather target names
        self._visit_target(node.target)
        self.visit(node.iter)
        for child in node.body:
            self.visit(child)
        for child in node.orelse:
            self.visit(child)

    def visit_comprehension(self, node):
        self._visit_target(node.target)
        self.visit(node.iter)
        for cond in node.ifs:
            self.visit(cond)

    def _visit_target(self, node):
        if isinstance(node, ast.Name):
            self.defined.add(node.id)
        elif isinstance(node, (ast.Tuple, ast.List)):
            for elt in node.elts:
                self._visit_target(elt)

def audit_notebook(filepath, verbose=False):
    """Audit a single Jupyter notebook file."""
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' not found.")
        return False

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            notebook = json.load(f)
    except json.JSONDecodeError as e:
        print(f"Error: '{filepath}' is not a valid JSON/Jupyter file. {e}")
        return False
    except Exception as e:
        print(f"Error reading file: {e}")
        return False

    cells = notebook.get("cells", [])
    code_cells = []
    
    # Extract code cells and trace execution count
    cell_idx = 0
    for cell in cells:
        cell_idx += 1
        if cell.get("cell_type") == "code":
            source = "".join(cell.get("source", []))
            exec_count = cell.get("execution_count")
            code_cells.append({
                "index": cell_idx,
                "source": source,
                "execution_count": exec_count
            })

    print(f"\nAuditing: {os.path.basename(filepath)}")
    print("=" * 60)
    print(f"Found {len(cells)} cells total ({len(code_cells)} code cells)")

    # 1. Audit Execution Order Linearality
    out_of_order = []
    unexecuted = []
    prev_count = 0
    execution_seq = []
    
    for c in code_cells:
        count = c["execution_count"]
        if count is None:
            unexecuted.append(c["index"])
        else:
            execution_seq.append((c["index"], count))
            if count <= prev_count:
                out_of_order.append((c["index"], count, prev_count))
            prev_count = count

    # 2. Dependency Audit via AST
    # Track which cell defines what
    cell_definitions = {}
    cell_usages = {}
    
    for c in code_cells:
        idx = c["index"]
        source = c["source"]
        if not source.strip():
            continue
            
        try:
            tree = ast.parse(source)
            tracker = VariableTracker()
            tracker.visit(tree)
            cell_definitions[idx] = tracker.defined
            cell_usages[idx] = tracker.used
        except SyntaxError as e:
            # Code might have Jupyter magics (e.g. %matplotlib, !pip)
            # Let's strip line magics and try again
            clean_lines = []
            for line in source.splitlines():
                if line.strip().startswith(('%', '!', '?')) or line.strip().endswith('?'):
                    clean_lines.append("# " + line)
                else:
                    clean_lines.append(line)
            try:
                tree = ast.parse("\n".join(clean_lines))
                tracker = VariableTracker()
                tracker.visit(tree)
                cell_definitions[idx] = tracker.defined
                cell_usages[idx] = tracker.used
            except SyntaxError:
                if verbose:
                    print(f"  [Cell {idx}] Warning: Could not parse syntax. Cell skipped from dependency analysis.")
                cell_definitions[idx] = set()
                cell_usages[idx] = set()

    # Find forward dependencies (uses variable defined in a cell below it)
    forward_deps = []
    never_defined = {}  # vars used but not defined anywhere, might be builtins or globals
    
    import builtins
    builtin_names = set(dir(builtins))
    # Common Jupyter/IPython globals/builtins
    builtin_names.update({"__file__", "get_ipython", "In", "Out", "_", "_i", "_ii", "_iii"})

    # Aggregate definitions from top to bottom
    defined_so_far = set(builtin_names)
    
    # We will also gather all variables defined in the whole notebook
    all_defined_vars = set(builtin_names)
    for defs in cell_definitions.values():
        all_defined_vars.update(defs)

    for i, c in enumerate(code_cells):
        idx = c["index"]
        usages = cell_usages.get(idx, set())
        definitions = cell_definitions.get(idx, set())
        
        # Check usages against what was defined above
        for var in usages:
            if var not in defined_so_far:
                # Is it defined in a cell below?
                defined_below = []
                for subsequent_c in code_cells[i+1:]:
                    sub_idx = subsequent_c["index"]
                    if var in cell_definitions.get(sub_idx, set()):
                        defined_below.append(sub_idx)
                
                if defined_below:
                    forward_deps.append({
                        "cell": idx,
                        "variable": var,
                        "defined_in_cells": defined_below
                    })
                elif var not in all_defined_vars:
                    if idx not in never_defined:
                        never_defined[idx] = []
                    never_defined[idx].append(var)
        
        # Update defined variables
        defined_so_far.update(definitions)

    # Output Results
    print("\n--- Execution Order Check ---")
    if out_of_order:
        print(f"✗ Found {len(out_of_order)} out-of-order cell executions:")
        for idx, count, prev in out_of_order:
            print(f"  • Cell {idx} was run as #{count} (previously ran #{prev})")
    else:
        print("✓ All executed cells were run in sequential linear order.")

    if unexecuted:
        print(f"ℹ {len(unexecuted)} cells have not been executed (no execution count).")

    print("\n--- Variable Dependency Check ---")
    if forward_deps:
        print(f"✗ Found {len(forward_deps)} out-of-order variable dependencies:")
        for dep in forward_deps:
            print(f"  • Cell {dep['cell']} uses '{dep['variable']}' which is defined below in Cell(s) {', '.join(map(str, dep['defined_in_cells']))}")
        print("  (This notebook will fail to run sequentially from scratch!)")
    else:
        print("✓ No forward dependencies detected. Notebook should run sequentially from scratch.")

    if verbose and never_defined:
        print("\n--- Undefined Variables (Potential Builtins or Undeclared Globals) ---")
        for idx, vars_list in never_defined.items():
            print(f"  • Cell {idx} references: {', '.join(vars_list)}")

    print("-" * 60)
    success = len(out_of_order) == 0 and len(forward_deps) == 0
    if success:
        print("Auditing Result: PASS (Linear & Clean)")
    else:
        print("Auditing Result: FAIL (Non-linear execution or broken dependency flow)")
    
    return success

def main():
    parser = argparse.ArgumentParser(description="Jupyter Notebook Execution Order Auditor")
    parser.add_argument("notebook", nargs="?", help="Path to the Jupyter Notebook file (.ipynb)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print verbose details (e.g. undefined variables)")
    
    args = parser.parse_args()
    
    if not args.notebook:
        # Scan current directory for any notebook files if none provided
        notebooks = [f for f in os.listdir('.') if f.endswith('.ipynb')]
        if notebooks:
            print(f"No notebook specified. Auditing all notebooks in current directory: {notebooks}")
            all_pass = True
            for nb in notebooks:
                if not audit_notebook(nb, args.verbose):
                    all_pass = False
            sys.exit(0 if all_pass else 1)
        else:
            parser.print_help()
            sys.exit(1)
    
    passed = audit_notebook(args.notebook, args.verbose)
    sys.exit(0 if passed else 1)

if __name__ == "__main__":
    main()
