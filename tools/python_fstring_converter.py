#!/usr/bin/env python3
"""
Python f-string Converter - A tool to automatically refactor old-style string formatting
(% and .format()) to modern Python f-strings using AST parsing and splicing.
"""

import argparse
import sys
import ast
import re
import difflib

def convert_percent_formatting(node):
    """
    Convert a % formatting BinOp to an ast.JoinedStr if possible.
    """
    # Must be a % operation where left is a string literal
    if not isinstance(node.op, ast.Mod):
        return None
    if not isinstance(node.left, ast.Constant) or not isinstance(node.left.value, str):
        return None
        
    fmt_str = node.left.value
    
    # Identify arguments
    if isinstance(node.right, ast.Tuple):
        args = node.right.elts
    elif isinstance(node.right, ast.Dict):
        args = {}
        for k, v in zip(node.right.keys, node.right.values):
            if k is not None and isinstance(k, ast.Constant) and isinstance(k.value, str):
                args[k.value] = v
    else:
        args = [node.right]
        
    # Match % specifiers: %[(name)][flags][width][.precision][type]
    pattern = re.compile(r'%(\(([^)]+)\))?([-+ 0#]*\d*(?:\.\d+)?)?([sdrxXocffgGdx%])')
    
    matches = list(pattern.finditer(fmt_str))
    if not matches:
        return None
        
    values = []
    last_idx = 0
    arg_idx = 0
    
    for match in matches:
        start, end = match.span()
        if start > last_idx:
            values.append(ast.Constant(value=fmt_str[last_idx:start]))
            
        named_group = match.group(2)
        flags = match.group(3)
        spec_char = match.group(4)
        
        if spec_char == '%':
            values.append(ast.Constant(value='%'))
            last_idx = end
            continue
            
        # Resolve expression
        if named_group:
            if isinstance(args, dict) and named_group in args:
                expr = args[named_group]
            else:
                return None  # Named argument not found
        else:
            if isinstance(args, list) and arg_idx < len(args):
                expr = args[arg_idx]
                arg_idx += 1
            else:
                return None  # Positional argument mismatch
                
        # Resolve conversion
        conversion = -1
        if spec_char == 'r':
            conversion = 114  # !r
        elif spec_char == 'a':
            conversion = 97   # !a
            
        # Resolve format specifier
        format_spec = None
        if flags:
            # Convert flags/width to format specification
            # e.g., '%02d' -> format spec is '02d'
            # We map type character to standard formatting equivalent
            typ = spec_char
            if typ == 's' and not flags.strip('0123456789.-+ '):
                # Simple string padding
                typ = ''
            format_spec = ast.JoinedStr(values=[ast.Constant(value=flags + typ)])
            
        values.append(ast.FormattedValue(
            value=expr,
            conversion=conversion,
            format_spec=format_spec
        ))
        
        last_idx = end
        
    if last_idx < len(fmt_str):
        values.append(ast.Constant(value=fmt_str[last_idx:]))
        
    return ast.JoinedStr(values=values)

def convert_format_call(node):
    """
    Convert a .format() call to an ast.JoinedStr if possible.
    """
    if not isinstance(node.func, ast.Attribute) or node.func.attr != 'format':
        return None
    if not isinstance(node.func.value, ast.Constant) or not isinstance(node.func.value.value, str):
        return None
        
    fmt_str = node.func.value.value
    args = node.args
    kwargs = {kw.arg: kw.value for kw in node.keywords if kw.arg}
    
    # Matches: { [name/index] [!conversion] [:spec] }
    pattern = re.compile(r'\{([a-zA-Z0-9_]*)(![ras])?(:[^}]+)?\}')
    
    matches = list(pattern.finditer(fmt_str))
    if not matches:
        return None
        
    values = []
    last_idx = 0
    arg_idx = 0
    
    for match in matches:
        start, end = match.span()
        if start > last_idx:
            values.append(ast.Constant(value=fmt_str[last_idx:start]))
            
        name = match.group(1)
        conv_str = match.group(2)
        spec_str = match.group(3)
        
        # Resolve expression
        if name == '':
            if arg_idx < len(args):
                expr = args[arg_idx]
                arg_idx += 1
            else:
                return None
        elif name.isdigit():
            idx = int(name)
            if idx < len(args):
                expr = args[idx]
            else:
                return None
        else:
            if name in kwargs:
                expr = kwargs[name]
            else:
                return None
                
        # Resolve conversion
        conversion = -1
        if conv_str == '!r':
            conversion = 114
        elif conv_str == '!s':
            conversion = 115
        elif conv_str == '!a':
            conversion = 97
            
        # Resolve format specifier
        format_spec = None
        if spec_str:
            format_spec = ast.JoinedStr(values=[ast.Constant(value=spec_str[1:])])
            
        values.append(ast.FormattedValue(
            value=expr,
            conversion=conversion,
            format_spec=format_spec
        ))
        
        last_idx = end
        
    if last_idx < len(fmt_str):
        values.append(ast.Constant(value=fmt_str[last_idx:]))
        
    return ast.JoinedStr(values=values)

class FormattingRefactorer(ast.NodeVisitor):
    def __init__(self):
        self.replacements = []
        
    def visit_BinOp(self, node):
        self.generic_visit(node)
        fstring_node = convert_percent_formatting(node)
        if fstring_node and hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
            try:
                # ast.unparse requires Python 3.9+
                new_code = ast.unparse(fstring_node)
                self.replacements.append((
                    node.lineno,
                    node.col_offset,
                    node.end_lineno,
                    node.end_col_offset,
                    new_code
                ))
            except Exception:
                pass
                
    def visit_Call(self, node):
        self.generic_visit(node)
        fstring_node = convert_format_call(node)
        if fstring_node and hasattr(node, 'lineno') and hasattr(node, 'end_lineno'):
            try:
                new_code = ast.unparse(fstring_node)
                self.replacements.append((
                    node.lineno,
                    node.col_offset,
                    node.end_lineno,
                    node.end_col_offset,
                    new_code
                ))
            except Exception:
                pass

def apply_replacements(source_lines, replacements):
    # Sort replacements in reverse order of line and column so indices remain valid
    replacements.sort(key=lambda r: (r[0], r[1]), reverse=True)
    
    for start_line, start_col, end_line, end_col, new_code in replacements:
        start_l = start_line - 1
        end_l = end_line - 1
        
        prefix = source_lines[start_l][:start_col]
        suffix = source_lines[end_l][end_col:]
        
        new_lines = (prefix + new_code + suffix).split('\n')
        source_lines[start_l:end_l+1] = new_lines
        
    return source_lines

def refactor_file(file_path, write=False):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            original_code = f.read()
    except Exception as e:
        print(f"Error reading file {file_path}: {e}", file=sys.stderr)
        return False

    try:
        tree = ast.parse(original_code, filename=file_path)
    except SyntaxError as e:
        print(f"Syntax error in file {file_path}: {e}", file=sys.stderr)
        return False

    refactorer = FormattingRefactorer()
    refactorer.visit(tree)
    
    if not refactorer.replacements:
        return False  # No changes made

    original_lines = original_code.split('\n')
    # Copy lines
    modified_lines = list(original_lines)
    
    modified_lines = apply_replacements(modified_lines, refactorer.replacements)
    modified_code = '\n'.join(modified_lines)
    
    # Print diff
    diff = list(difflib.unified_diff(
        original_lines,
        modified_lines,
        fromfile=f"a/{file_path}",
        tofile=f"b/{file_path}",
        lineterm=""
    ))
    
    if diff:
        print(f"\nRefactoring suggestions for {file_path}:")
        print("-" * 60)
        for line in diff:
            print(line)
        print("-" * 60)
        
        if write:
            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(modified_code)
                print(f"✓ Applied {len(refactorer.replacements)} refactoring(s) to {file_path}")
            except Exception as e:
                print(f"Error writing changes to {file_path}: {e}", file=sys.stderr)
        else:
            print(f"To apply these {len(refactorer.replacements)} changes, run with -w/--write flag.")
            
    return True

def main():
    parser = argparse.ArgumentParser(
        description="Python f-string Converter - Convert old string formatting (% and .format()) to modern f-strings."
    )
    parser.add_argument(
        "files",
        nargs="+",
        help="Python source files to refactor"
    )
    parser.add_argument(
        "-w", "--write",
        action="store_true",
        help="Write refactored changes back to the files"
    )
    
    args = parser.parse_args()
    
    changes_count = 0
    for file_path in args.files:
        if refactor_file(file_path, write=args.write):
            changes_count += 1
            
    if changes_count == 0:
        print("No string formatting candidates for conversion found.")

if __name__ == "__main__":
    main()
