#!/usr/bin/env python3
"""
YAML/TOML Configuration Diff Tool
Compares two YAML or TOML files structurally and prints a colorized diff.
"""

import sys
import re
import argparse
from collections.abc import Mapping

# ANSI Colors
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"

def supports_color():
    """Checks if the terminal supports color output."""
    plat = sys.platform
    supported_platform = plat != 'win32' or 'ANSICON' in os.environ or ('TERM' in os.environ and os.environ['TERM'] != 'dumb')
    # Windows 10+ supports VT100 out of the box in cmd/powershell
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform and is_a_tty

# Simple custom YAML parser to make this tool zero-dependency if PyYAML isn't present
def parse_simple_yaml(text):
    """
    Very basic YAML parser that parses nested dictionaries and lists of primitives.
    Falls back to regex parsing line-by-line.
    """
    lines = text.splitlines()
    data = {}
    stack = [(-1, data)]  # list of (indent, dict_or_list)
    
    list_item_re = re.compile(r"^(\s*)-\s+(.*)$")
    key_val_re = re.compile(r"^(\s*)([\w\-\.]+)\s*:\s*(.*)$")
    
    for line_num, line in enumerate(lines):
        # Skip empty lines or comments
        if not line.strip() or line.strip().startswith('#'):
            continue
            
        # Detect indentation
        indent = len(line) - len(line.lstrip())
        
        # Pop from stack if current indent is less than or equal to stack top
        while len(stack) > 1 and indent <= stack[-1][0]:
            stack.pop()
            
        current_container = stack[-1][1]
        
        # Check if list item
        m_list = list_item_re.match(line)
        if m_list:
            item_indent, item_val = m_list.groups()
            item_indent_len = len(item_indent)
            
            # Clean item_val
            item_val = item_val.strip()
            if (item_val.startswith('"') and item_val.endswith('"')) or (item_val.startswith("'") and item_val.endswith("'")):
                item_val = item_val[1:-1]
                
            # If parent isn't a list, we might need to convert it or handle it
            if not isinstance(current_container, list):
                # This should be a list container
                # If we're under a key, we need to locate it or build a new list
                print(f"Warning: Unexpected list item at line {line_num+1}", file=sys.stderr)
                continue
                
            current_container.append(item_val)
            continue
            
        # Check if key-value pair
        m_kv = key_val_re.match(line)
        if m_kv:
            kv_indent, key, val = m_kv.groups()
            kv_indent_len = len(kv_indent)
            val = val.strip()
            
            # Clean quotes
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            elif val.lower() == 'true':
                val = True
            elif val.lower() == 'false':
                val = False
            elif val.lower() in ['null', '~']:
                val = None
            else:
                # Try integer/float
                try:
                    if '.' in val:
                        val = float(val)
                    else:
                        val = int(val)
                except ValueError:
                    pass # Keep as string
                    
            if val == "":
                # Nested structure starts on subsequent lines
                # We determine if it's a dict or list based on next lines, default to dict
                new_container = {}
                # Look ahead to see if the next line is a list item
                next_line_idx = line_num + 1
                while next_line_idx < len(lines):
                    next_l = lines[next_line_idx].strip()
                    if next_l and not next_l.startswith('#'):
                        if next_l.startswith('-'):
                            new_container = []
                        break
                    next_line_idx += 1
                    
                if isinstance(current_container, dict):
                    current_container[key] = new_container
                stack.append((kv_indent_len, new_container))
            else:
                if isinstance(current_container, dict):
                    current_container[key] = val
            continue
            
    return data

def load_yaml(filepath):
    """Loads a YAML file using PyYAML if available, else our basic custom parser."""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    try:
        import yaml
        return yaml.safe_load(content)
    except ImportError:
        # Fallback to simple parser
        return parse_simple_yaml(content)

def load_toml(filepath):
    """Loads a TOML file using standard tomllib or falls back to toml/tomli."""
    with open(filepath, 'rb') as f:
        # Python 3.11+ has tomllib built-in
        try:
            import tomllib
            return tomllib.load(f)
        except ImportError:
            try:
                import tomli
                return tomli.load(f)
            except ImportError:
                try:
                    import toml
                    return toml.load(filepath)
                except ImportError:
                    # Very simple fallback TOML parser for simple config key-value
                    f.seek(0)
                    text = f.read().decode('utf-8')
                    data = {}
                    current_table = data
                    for line in text.splitlines():
                        line = line.strip()
                        if not line or line.startswith('#'):
                            continue
                        if line.startswith('[') and line.endswith(']'):
                            table_name = line[1:-1].strip()
                            # Nested tables (simple handling)
                            parts = table_name.split('.')
                            curr = data
                            for part in parts:
                                part = part.strip()
                                if part not in curr:
                                    curr[part] = {}
                                curr = curr[part]
                            current_table = curr
                        elif '=' in line:
                            k, v = line.split('=', 1)
                            k = k.strip()
                            v = v.strip()
                            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                                v = v[1:-1]
                            elif v.lower() == 'true':
                                v = True
                            elif v.lower() == 'false':
                                v = False
                            else:
                                try:
                                    v = int(v)
                                except ValueError:
                                    try:
                                        v = float(v)
                                    except ValueError:
                                        pass
                            current_table[k] = v
                    return data

def deep_compare(d1, d2, path=""):
    """Recursively compares two dictionaries and returns a structured diff dictionary."""
    diff = {}
    
    # Check for removed keys
    for k in d1:
        current_path = f"{path}.{k}" if path else k
        if k not in d2:
            diff[current_path] = ("removed", d1[k], None)
        else:
            val1 = d1[k]
            val2 = d2[k]
            
            if isinstance(val1, Mapping) and isinstance(val2, Mapping):
                sub_diff = deep_compare(val1, val2, current_path)
                diff.update(sub_diff)
            elif val1 != val2:
                diff[current_path] = ("modified", val1, val2)
                
    # Check for added keys
    for k in d2:
        current_path = f"{path}.{k}" if path else k
        if k not in d1:
            diff[current_path] = ("added", None, d2[k])
            
    return diff

def format_value(val):
    """Format value for printing."""
    if isinstance(val, str):
        return f'"{val}"'
    return str(val)

def print_diff(diff, color_enabled=True):
    """Formats and prints the structural diff with optional ANSI colors."""
    if not diff:
        print("✅ Configurations are identical!")
        return

    c_red = RED if color_enabled else ""
    c_green = GREEN if color_enabled else ""
    c_yellow = YELLOW if color_enabled else ""
    c_blue = BLUE if color_enabled else ""
    c_reset = RESET if color_enabled else ""
    c_bold = BOLD if color_enabled else ""

    print(f"{c_bold}Configuration Differences Found:{c_reset}\n")
    
    # Sort keys for consistent output
    for path in sorted(diff.keys()):
        status, val1, val2 = diff[path]
        
        # Display nicely indented path
        parts = path.split('.')
        indent = "  " * (len(parts) - 1)
        key_label = parts[-1]
        
        if status == "added":
            print(f"{c_green}+ {indent}{key_label}: {format_value(val2)}{c_reset}")
        elif status == "removed":
            print(f"{c_red}- {indent}{key_label}: {format_value(val1)} (removed){c_reset}")
        elif status == "modified":
            print(f"{c_yellow}~ {indent}{key_label}: {format_value(val1)} -> {format_value(val2)}{c_reset}")

def main():
    parser = argparse.ArgumentParser(description="YAML/TOML Configuration Diff Tool")
    parser.add_argument("file1", help="First configuration file")
    parser.add_argument("file2", help="Second configuration file")
    parser.add_argument("-t", "--type", choices=["yaml", "toml", "auto"], default="auto",
                        help="Specify configuration format (default: auto-detect by extension)")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI color output")
    args = parser.parse_args()

    # Determine file types
    type1 = args.type
    type2 = args.type

    if args.type == "auto":
        ext1 = args.file1.split('.')[-1].lower()
        ext2 = args.file2.split('.')[-1].lower()
        
        type1 = "toml" if ext1 in ["toml", "tml"] else "yaml"
        type2 = "toml" if ext2 in ["toml", "tml"] else "yaml"

    try:
        # Load files
        if type1 == "toml":
            data1 = load_toml(args.file1)
        else:
            data1 = load_yaml(args.file1)
            
        if type2 == "toml":
            data2 = load_toml(args.file2)
        else:
            data2 = load_yaml(args.file2)
            
        if data1 is None or data2 is None:
            print("❌ Error: Failed to parse one or both configuration files.", file=sys.stderr)
            sys.exit(1)

        # Compare structures
        diff = deep_compare(data1, data2)
        
        color_enabled = supports_color() and not args.no_color
        print_diff(diff, color_enabled)
        
        sys.exit(1 if diff else 0)

    except FileNotFoundError as e:
        print(f"❌ Error: File not found - {e.filename}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    import os
    main()
