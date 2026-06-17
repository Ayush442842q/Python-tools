#!/usr/bin/env python3
"""
CSV/JSON Template Renderer
A standalone template engine utility that merges JSON or CSV datasets
with template text files using custom variables, conditionals, loops, and filters.
"""

import os
import sys
import json
import csv
import re
import argparse

# Enable ANSI escape sequences on Windows if possible
if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        stdout_handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        if kernel32.GetConsoleMode(stdout_handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(stdout_handle, mode.value | 0x0004)
    except Exception:
        pass

# Template AST Nodes
class TextNode:
    def __init__(self, text):
        self.text = text
    def render(self, context):
        return self.text

class VarNode:
    def __init__(self, expr):
        self.expr = expr
    def render(self, context):
        res = resolve_var(self.expr, context)
        return str(res) if res is not None else ""

class IfNode:
    def __init__(self, condition, true_nodes, false_nodes):
        self.condition = condition
        self.true_nodes = true_nodes
        self.false_nodes = false_nodes
    def render(self, context):
        if eval_condition(self.condition, context):
            return "".join(n.render(context) for n in self.true_nodes)
        else:
            return "".join(n.render(context) for n in self.false_nodes)

class ForNode:
    def __init__(self, loop_var, iter_expr, loop_nodes):
        self.loop_var = loop_var
        self.iter_expr = iter_expr
        self.loop_nodes = loop_nodes
    def render(self, context):
        items = resolve_path(self.iter_expr, context)
        if not items:
            return ""
        # If it's a dictionary, iterate over its keys or key-value pairs
        if isinstance(items, dict):
            items = [{"key": k, "value": v} for k, v in items.items()]
        elif not isinstance(items, (list, tuple)):
            return ""
        
        output = []
        total = len(items)
        for index, item in enumerate(items):
            sub_context = context.copy()
            sub_context[self.loop_var] = item
            sub_context['loop'] = {
                'index0': index,
                'index': index + 1,
                'first': index == 0,
                'last': index == total - 1,
                'length': total
            }
            output.append("".join(n.render(sub_context) for n in self.loop_nodes))
        return "".join(output)

# Safe path resolution
def resolve_path(path, context):
    path = path.strip()
    if not path:
        return None
    if path == ".":
        return context
    
    # Check literals
    if (path.startswith('"') and path.endswith('"')) or (path.startswith("'") and path.endswith("'")):
        return path[1:-1]
    if path.isdigit():
        return int(path)
    if path.replace('.', '', 1).isdigit() and path.count('.') == 1:
        return float(path)
    if path.lower() == 'true':
        return True
    if path.lower() == 'false':
        return False
    if path.lower() in ('none', 'null'):
        return None
        
    parts = path.split('.')
    curr = context
    for p in parts:
        # Check array index like array[0]
        array_match = re.match(r'^(\w+)\[(\d+)\]$', p)
        if array_match:
            key = array_match.group(1)
            idx = int(array_match.group(2))
            if isinstance(curr, dict) and key in curr:
                curr = curr[key]
            else:
                return None
            if isinstance(curr, (list, tuple)) and 0 <= idx < len(curr):
                curr = curr[idx]
            else:
                return None
        else:
            if isinstance(curr, dict) and p in curr:
                curr = curr[p]
            elif hasattr(curr, p):
                curr = getattr(curr, p)
            else:
                return None
    return curr

def apply_filter(filter_str, val):
    filter_str = filter_str.strip()
    if not filter_str:
        return val
    
    if filter_str == 'upper':
        return str(val).upper()
    elif filter_str == 'lower':
        return str(val).lower()
    elif filter_str == 'title':
        return str(val).title()
    elif filter_str == 'reverse':
        if isinstance(val, list):
            return list(reversed(val))
        return str(val)[::-1]
    elif filter_str == 'length':
        try:
            return len(val)
        except Exception:
            return 0
    elif filter_str.startswith('default(') and filter_str.endswith(')'):
        arg = filter_str[8:-1].strip()
        if (arg.startswith('"') and arg.endswith('"')) or (arg.startswith("'") and arg.endswith("'")):
            arg = arg[1:-1]
        return val if (val is not None and val != "") else arg
    return val

def resolve_var(expr, context):
    if '|' in expr:
        parts = expr.split('|')
        base_expr = parts[0].strip()
        filters = [p.strip() for p in parts[1:]]
    else:
        base_expr = expr.strip()
        filters = []
        
    val = resolve_path(base_expr, context)
    for f in filters:
        val = apply_filter(f, val)
    return val

def eval_condition(condition, context):
    # Supports: ==, !=, >, <, >=, <=, in
    operators = ['==', '!=', '>=', '<=', '>', '<', ' in ']
    for op in operators:
        if op in condition:
            parts = condition.split(op, 1)
            left_val = resolve_path(parts[0], context)
            right_val = resolve_path(parts[1], context)
            
            # Type coerce for comparisons if necessary
            if op == '==':
                return str(left_val) == str(right_val) or left_val == right_val
            elif op == '!=':
                return str(left_val) != str(right_val) or left_val != right_val
            
            try:
                if op == '>':
                    return float(left_val) > float(right_val)
                elif op == '<':
                    return float(left_val) < float(right_val)
                elif op == '>=':
                    return float(left_val) >= float(right_val)
                elif op == '<=':
                    return float(left_val) <= float(right_val)
            except Exception:
                pass
            
            if op == ' in ':
                if isinstance(right_val, (list, tuple, dict, str)):
                    return left_val in right_val
                return False
                
    # Single term truthy check
    val = resolve_path(condition, context)
    return bool(val)

# Parser Implementation
class TemplateParser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0
    
    def parse(self, end_tokens=None):
        nodes = []
        while self.pos < len(self.tokens):
            t = self.tokens[self.pos]
            if not t:
                self.pos += 1
                continue
            
            if t.startswith('{%'):
                content = t[2:-2].strip()
                parts = content.split()
                if not parts:
                    self.pos += 1
                    continue
                cmd = parts[0]
                
                if end_tokens and cmd in end_tokens:
                    break
                
                self.pos += 1
                if cmd == 'if':
                    condition = " ".join(parts[1:])
                    true_nodes = self.parse(end_tokens={'else', 'endif'})
                    false_nodes = []
                    
                    if self.pos < len(self.tokens):
                        next_t = self.tokens[self.pos][2:-2].strip().split()
                        if next_t and next_t[0] == 'else':
                            self.pos += 1
                            false_nodes = self.parse(end_tokens={'endif'})
                    
                    if self.pos < len(self.tokens):
                        self.pos += 1  # consume endif
                    nodes.append(IfNode(condition, true_nodes, false_nodes))
                
                elif cmd == 'for':
                    if len(parts) >= 4 and parts[2] == 'in':
                        loop_var = parts[1]
                        iter_expr = parts[3]
                        loop_nodes = self.parse(end_tokens={'endfor'})
                        if self.pos < len(self.tokens):
                            self.pos += 1  # consume endfor
                        nodes.append(ForNode(loop_var, iter_expr, loop_nodes))
                    else:
                        raise ValueError(f"Syntax Error: Invalid for-loop declaration: '{t}'")
                else:
                    raise ValueError(f"Syntax Error: Unrecognized statement block: '{cmd}'")
            
            elif t.startswith('{{'):
                content = t[2:-2].strip()
                self.pos += 1
                nodes.append(VarNode(content))
            else:
                self.pos += 1
                nodes.append(TextNode(t))
        return nodes

def render_template(template_str, context):
    # Regex split to extract control structures and variables
    tokens = re.split(r'(\{\{.*?\}\}|\{\%.*?\%\})', template_str)
    parser = TemplateParser(tokens)
    nodes = parser.parse()
    return "".join(n.render(context) for n in nodes)

def load_data(file_path):
    ext = os.path.splitext(file_path)[1].lower()
    if ext == '.json':
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    elif ext in ('.csv', '.tsv'):
        delimiter = '\t' if ext == '.tsv' else ','
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter=delimiter)
            return list(reader)
    else:
        raise ValueError(f"Unsupported data format: {ext}. Use JSON, CSV, or TSV.")

def main():
    parser = argparse.ArgumentParser(
        description="CSV/JSON Template Renderer: Render template text files using JSON or CSV data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example Template Content (template.txt):
  Welcome {{ user.name | title }}!
  {% if user.is_admin %}
  Admin Console:
  {% for tool in tools %}
    - {{ tool.name }} (Status: {{ tool.status | upper }})
  {% endfor %}
  {% else %}
  Standard Access.
  {% endif %}

Examples:
  python tools/template_renderer.py --template doc_template.txt --data data.json
  python tools/template_renderer.py -t email.html -d users.csv -o output/
"""
    )
    parser.add_argument("--template", "-t", required=True, help="Path to the template text file")
    parser.add_argument("--data", "-d", required=True, help="Path to the JSON, CSV, or TSV data file")
    parser.add_argument("--output", "-o", help="Path to output file or directory (if rendering multiple entries from CSV)")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.template):
        print(f"\033[31mError: Template file '{args.template}' not found.\033[0m", file=sys.stderr)
        sys.exit(1)
        
    if not os.path.exists(args.data):
        print(f"\033[31mError: Data file '{args.data}' not found.\033[0m", file=sys.stderr)
        sys.exit(1)
        
    try:
        data = load_data(args.data)
        with open(args.template, 'r', encoding='utf-8') as f:
            template_str = f.read()
    except Exception as e:
        print(f"\033[31mError loading files: {e}\033[0m", file=sys.stderr)
        sys.exit(1)

    try:
        # If data is a list (e.g. from CSV or a JSON array), and output directory is specified,
        # we can render one file per item. Otherwise, pass the whole list as 'items' context.
        if isinstance(data, list):
            if args.output and os.path.isdir(args.output):
                print(f"Detected list of {len(data)} items. Rendering files to directory: {args.output}")
                for i, row in enumerate(data):
                    rendered = render_template(template_str, row)
                    filename = f"render_{i+1}.txt"
                    # Try to use row fields to name output file if 'id' or 'name' exists
                    for field in ['id', 'name', 'username', 'key']:
                        if field in row and row[field]:
                            clean_val = re.sub(r'[\\/*?:"<>|]', "", str(row[field]))
                            filename = f"render_{clean_val}.txt"
                            break
                    out_path = os.path.join(args.output, filename)
                    with open(out_path, 'w', encoding='utf-8') as out_f:
                        out_f.write(rendered)
                print(f"\033[32mSuccessfully rendered {len(data)} files.\033[0m")
            else:
                # Render once with full list inside a container context
                context = {"items": data, "rows": data}
                rendered = render_template(template_str, context)
                if args.output:
                    with open(args.output, 'w', encoding='utf-8') as out_f:
                        out_f.write(rendered)
                    print(f"\033[32mSuccessfully rendered template to '{args.output}'.\033[0m")
                else:
                    sys.stdout.write(rendered)
        else:
            # Data is a dictionary (JSON object)
            rendered = render_template(template_str, data)
            if args.output:
                # Make parent directories if needed
                out_dir = os.path.dirname(args.output)
                if out_dir and not os.path.exists(out_dir):
                    os.makedirs(out_dir, exist_ok=True)
                with open(args.output, 'w', encoding='utf-8') as out_f:
                    out_f.write(rendered)
                print(f"\033[32mSuccessfully rendered template to '{args.output}'.\033[0m")
            else:
                sys.stdout.write(rendered)
    except Exception as e:
        print(f"\033[31mTemplate rendering failed: {e}\033[0m", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
