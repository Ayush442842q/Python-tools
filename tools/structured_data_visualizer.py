#!/usr/bin/env python3
"""
Structured Data Tree Visualizer

Renders hierarchical data formats (JSON, XML, TOML, YAML) as beautiful, 
color-coded, and expandable ASCII/Unicode terminal trees.

Usage:
    python tools/structured_data_visualizer.py <file_path> [options]

Example:
    python tools/structured_data_visualizer.py tools/mock_config.json --depth 3
"""

import argparse
import json
import os
import sys
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Tuple, Union

# Try to import tomllib (Python 3.11+) or toml/pyyaml for extra format support
try:
    import tomllib  # type: ignore
except ImportError:
    try:
        import toml as tomllib  # type: ignore
    except ImportError:
        tomllib = None  # type: ignore

try:
    import yaml
except ImportError:
    yaml = None

# ANSI colors for styling
COLOR_RESET = "\033[0m"
COLOR_KEY = "\033[94m"       # Blue
COLOR_VAL_STR = "\033[92m"   # Green
COLOR_VAL_NUM = "\033[93m"   # Yellow
COLOR_VAL_BOOL = "\033[95m"  # Magenta
COLOR_VAL_NONE = "\033[90m"  # Dark Gray
COLOR_TYPE = "\033[36m"      # Cyan
COLOR_BORDER = "\033[37m"    # Off-white

def colorize(text: str, color_code: str, use_color: bool = True) -> str:
    """Wraps text in ANSI color codes if use_color is True."""
    if use_color:
        return f"{color_code}{text}{COLOR_RESET}"
    return text

def parse_xml_to_dict(element: ET.Element) -> Dict[str, Any]:
    """Helper to convert XML ElementTree elements into a python dictionary structure."""
    result: Dict[str, Any] = {}
    
    # Process attributes
    if element.attrib:
        result["@attributes"] = element.attrib
        
    # Process text content
    if element.text and element.text.strip():
        text_val = element.text.strip()
        if not element.attrib and not len(element):
            return text_val  # type: ignore
        result["#text"] = text_val
        
    # Process children
    for child in element:
        child_dict = parse_xml_to_dict(child)
        child_tag = child.tag
        
        if child_tag in result:
            # If tag exists, convert to list or append to existing list
            if not isinstance(result[child_tag], list):
                result[child_tag] = [result[child_tag]]
            result[child_tag].append(child_dict)
        else:
            result[child_tag] = child_dict
            
    return result

def load_data(file_path: str) -> Tuple[Any, str]:
    """Loads and parses data from a file, returning (parsed_data, format_name)."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File '{file_path}' does not exist.")
        
    ext = os.path.splitext(file_path)[1].lower()
    
    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
        
    if ext == '.json':
        return json.loads(content), "JSON"
    elif ext in ('.xml', '.xhtml'):
        root = ET.fromstring(content)
        return {root.tag: parse_xml_to_dict(root)}, "XML"
    elif ext in ('.yaml', '.yml'):
        if yaml is not None:
            return yaml.safe_load(content), "YAML"
        else:
            # Simple fallback parser for very basic YAML if yaml module is missing
            raise ImportError("PyYAML package is required to parse YAML files. Install with 'pip install pyyaml'.")
    elif ext == '.toml':
        if tomllib is not None:
            # tomllib accepts bytes or string depending on version, load standard
            try:
                return tomllib.loads(content), "TOML"
            except Exception:
                return tomllib.parse(content), "TOML"  # For older pip package
        else:
            raise ImportError("tomllib (Python 3.11+) or 'toml' package is required to parse TOML. Install with 'pip install toml'.")
    else:
        # Autodetect JSON, then XML
        try:
            return json.loads(content), "JSON (Autodetected)"
        except json.JSONDecodeError:
            try:
                root = ET.fromstring(content)
                return {root.tag: parse_xml_to_dict(root)}, "XML (Autodetected)"
            except ET.ParseError:
                raise ValueError("Could not autodetect file format (JSON/XML). Please specify a valid extension.")

def get_value_details(val: Any, use_color: bool) -> Tuple[str, str]:
    """Returns (formatted_value, type_indicator)."""
    if val is None:
        return colorize("null", COLOR_VAL_NONE, use_color), colorize("null", COLOR_TYPE, use_color)
    elif isinstance(val, bool):
        val_str = str(val).lower()
        return colorize(val_str, COLOR_VAL_BOOL, use_color), colorize("bool", COLOR_TYPE, use_color)
    elif isinstance(val, (int, float)):
        return colorize(str(val), COLOR_VAL_NUM, use_color), colorize(type(val).__name__, COLOR_TYPE, use_color)
    elif isinstance(val, str):
        # Escape newlines for neatness
        escaped = val.replace('\n', '\\n')
        if len(escaped) > 40:
            escaped = escaped[:37] + "..."
        return colorize(f'"{escaped}"', COLOR_VAL_STR, use_color), colorize("str", COLOR_TYPE, use_color)
    elif isinstance(val, dict):
        return "", colorize(f"object[{len(val)}]", COLOR_TYPE, use_color)
    elif isinstance(val, list):
        return "", colorize(f"array[{len(val)}]", COLOR_TYPE, use_color)
    else:
        return str(val), colorize(type(val).__name__, COLOR_TYPE, use_color)

def print_tree(
    data: Any,
    prefix: str = "",
    is_last: bool = True,
    max_depth: int = -1,
    current_depth: int = 0,
    use_color: bool = True,
    ascii_only: bool = False,
    key_name: str = ""
):
    """Recursively prints the data tree."""
    if max_depth != -1 and current_depth > max_depth:
        return

    # Set tree branch characters
    if ascii_only:
        branch = "`-- " if is_last else "|-- "
        next_prefix = prefix + ("    " if is_last else "|   ")
    else:
        branch = "└── " if is_last else "├── "
        next_prefix = prefix + ("    " if is_last else "│   ")

    # Format the line
    line = prefix + branch
    
    # 1. Print key
    if key_name:
        line += colorize(key_name, COLOR_KEY, use_color) + ": "
        
    # 2. Print value/type details
    val_str, type_str = get_value_details(data, use_color)
    if val_str:
        line += f"{val_str} {type_str}"
    else:
        line += f"{type_str}"
        
    try:
        print(line)
    except UnicodeEncodeError:
        # Fall back to ASCII characters for tree branches
        line_ascii = line.replace("├──", "|--").replace("└──", "`--").replace("│", "|")
        try:
            print(line_ascii)
        except UnicodeEncodeError:
            # Fall back to encoding with safe replacements if even color codes fail
            print(line.encode(sys.stdout.encoding, errors='replace').decode(sys.stdout.encoding))


    # 3. Recurse children
    if isinstance(data, dict) and (max_depth == -1 or current_depth < max_depth):
        keys = list(data.keys())
        for idx, k in enumerate(keys):
            print_tree(
                data=data[k],
                prefix=next_prefix,
                is_last=(idx == len(keys) - 1),
                max_depth=max_depth,
                current_depth=current_depth + 1,
                use_color=use_color,
                ascii_only=ascii_only,
                key_name=k
            )
    elif isinstance(data, list) and (max_depth == -1 or current_depth < max_depth):
        for idx, val in enumerate(data):
            # Print index
            idx_name = f"[{idx}]"
            print_tree(
                data=val,
                prefix=next_prefix,
                is_last=(idx == len(data) - 1),
                max_depth=max_depth,
                current_depth=current_depth + 1,
                use_color=use_color,
                ascii_only=ascii_only,
                key_name=idx_name
            )

def main() -> int:
    parser = argparse.ArgumentParser(description="Render JSON, XML, TOML, or YAML files as interactive-looking text trees.")
    parser.add_argument("file", help="Path to the file to visualize")
    parser.add_argument("-d", "--depth", type=int, default=-1, help="Max depth to display (default: all)")
    parser.add_argument("--no-color", action="store_true", help="Disable ANSI terminal colors")
    parser.add_argument("--ascii", action="store_true", help="Use standard ASCII characters instead of Unicode box drawing")
    
    args = parser.parse_args()
    
    use_color = not args.no_color
    # Disable color if stdout is redirected and not a tty
    if not sys.stdout.isatty():
        use_color = False
        
    try:
        data, format_name = load_data(args.file)
    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error reading/parsing file: {e}", file=sys.stderr)
        return 1
        
    print(colorize(f"Data Tree View of '{os.path.basename(args.file)}' [{format_name}]", COLOR_BORDER, use_color))
    print(colorize("=" * 60, COLOR_BORDER, use_color))
    
    # Start recursion from root
    if isinstance(data, dict):
        keys = list(data.keys())
        for idx, k in enumerate(keys):
            print_tree(
                data=data[k],
                prefix="",
                is_last=(idx == len(keys) - 1),
                max_depth=args.depth,
                current_depth=0,
                use_color=use_color,
                ascii_only=args.ascii,
                key_name=k
            )
    elif isinstance(data, list):
        for idx, val in enumerate(data):
            print_tree(
                data=val,
                prefix="",
                is_last=(idx == len(data) - 1),
                max_depth=args.depth,
                current_depth=0,
                use_color=use_color,
                ascii_only=args.ascii,
                key_name=f"[{idx}]"
            )
    else:
        # Simple scalar root
        print_tree(
            data=data,
            prefix="",
            is_last=True,
            max_depth=args.depth,
            current_depth=0,
            use_color=use_color,
            ascii_only=args.ascii,
            key_name="root"
        )
        
    print(colorize("=" * 60, COLOR_BORDER, use_color))
    return 0

if __name__ == "__main__":
    sys.exit(main())
