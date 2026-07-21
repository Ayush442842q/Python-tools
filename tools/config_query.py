#!/usr/bin/env python3
"""
Configuration Query Tool

Query and extract values from configuration files (JSON, YAML, TOML, XML, INI)
using standard dot-notation and index paths (e.g. 'database.hosts[0].ip').
"""

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Union

# Try loading optional libraries
YAML_SUPPORT = False
TOML_SUPPORT = False

try:
    import yaml
    YAML_SUPPORT = True
except ImportError:
    pass

try:
    if sys.version_info >= (3, 11):
        import tomllib as toml
        TOML_SUPPORT = True
    else:
        import toml
        TOML_SUPPORT = True
except ImportError:
    pass

# ANSI Colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"

def supports_color() -> bool:
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform or is_a_tty

def color_text(text: str, color_code: str) -> str:
    return f"{color_code}{text}{COLOR_RESET}" if supports_color() else text

def parse_ini(file_path: str) -> Dict[str, Any]:
    import configparser
    config = configparser.ConfigParser()
    config.read(file_path)
    # Convert ConfigParser to nested dict
    return {section: dict(config.items(section)) for section in config.sections()}

def parse_xml(file_path: str) -> Dict[str, Any]:
    import xml.etree.ElementTree as ET
    
    def xml_to_dict(element: ET.Element) -> Union[Dict[str, Any], str]:
        children = list(element)
        if not children:
            return element.text.strip() if element.text else ""
            
        res: Dict[str, Any] = {}
        # Parse attributes
        for key, val in element.attrib.items():
            res[f"@{key}"] = val
            
        # Parse children
        for child in children:
            child_val = xml_to_dict(child)
            tag = child.tag
            if tag in res:
                if isinstance(res[tag], list):
                    res[tag].append(child_val)
                else:
                    res[tag] = [res[tag], child_val]
            else:
                res[tag] = child_val
        return res

    tree = ET.parse(file_path)
    root = tree.getroot()
    return {root.tag: xml_to_dict(root)}

def load_config(file_path: str, file_type: str) -> Dict[str, Any]:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
        
    with open(file_path, 'r', encoding='utf-8') as f:
        if file_type == 'json':
            return json.load(f)
        elif file_type == 'yaml':
            if not YAML_SUPPORT:
                raise ImportError("YAML support is not available. Install PyYAML: pip install PyYAML")
            return yaml.safe_load(f)
        elif file_type == 'toml':
            if not TOML_SUPPORT:
                raise ImportError("TOML support is not available. Install toml: pip install toml (or use Python 3.11+)")
            if sys.version_info >= (3, 11):
                # tomllib expects bytes/binary mode or works with string in some setups
                with open(file_path, 'rb') as fb:
                    return toml.load(fb)
            return toml.load(f)
        elif file_type == 'ini':
            return parse_ini(file_path)
        elif file_type == 'xml':
            return parse_xml(file_path)
        else:
            raise ValueError(f"Unsupported config type: {file_type}")

def query_value(data: Any, path: str) -> Any:
    if not path:
        return data
        
    # Split path by dot or square brackets
    # e.g., "server.db.ports[0].host" -> ['server', 'db', 'ports', '[0]', 'host']
    parts = re.findall(r'[^.\[\]]+|\[\d+\]', path)
    current = data
    
    for part in parts:
        if part.startswith('[') and part.endswith(']'):
            idx = int(part[1:-1])
            if isinstance(current, list):
                if 0 <= idx < len(current):
                    current = current[idx]
                else:
                    raise IndexError(f"List index {idx} out of range (length {len(current)})")
            else:
                raise TypeError(f"Cannot apply list index {part} to non-list type: {type(current).__name__}")
        else:
            if isinstance(current, dict):
                if part in current:
                    current = current[part]
                else:
                    raise KeyError(f"Key '{part}' not found")
            else:
                raise TypeError(f"Cannot extract key '{part}' from non-dictionary type: {type(current).__name__}")
                
    return current

def format_output(value: Any, format_type: str) -> str:
    if format_type == 'json':
        return json.dumps(value, indent=2)
    elif format_type == 'yaml' and YAML_SUPPORT:
        return yaml.dump(value, default_flow_style=False)
    elif format_type == 'toml' and TOML_SUPPORT:
        if isinstance(value, dict):
            return toml.dumps(value)
        else:
            return str(value)
    elif format_type == 'pprint':
        import pprint
        return pprint.pformat(value)
    else:
        # Default 'raw' formatting
        if isinstance(value, (dict, list)):
            return json.dumps(value, indent=2)
        return str(value)

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Config Query Tool - Query values from configuration files using dot-notation.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("file", help="Path to the configuration file")
    parser.add_argument("query", nargs="?", default="", help="Dot-notation path query (e.g. database.host or connections[0].port)")
    parser.add_argument("-t", "--type", choices=['json', 'yaml', 'toml', 'ini', 'xml'], help="Force config parser type (otherwise inferred from file extension)")
    parser.add_argument("-f", "--format", choices=['raw', 'json', 'yaml', 'toml', 'pprint'], default='raw', help="Output format for nested structures")
    parser.add_argument("-s", "--silent", action="store_true", help="Suppress error messages on stdout and exit quietly with status codes")
    
    args = parser.parse_args()
    
    # Infer type from extension if not specified
    file_type = args.type
    if not file_type:
        _, ext = os.path.splitext(args.file.lower())
        if ext in ('.json',):
            file_type = 'json'
        elif ext in ('.yaml', '.yml'):
            file_type = 'yaml'
        elif ext in ('.toml',):
            file_type = 'toml'
        elif ext in ('.ini', '.conf', '.cfg'):
            file_type = 'ini'
        elif ext in ('.xml',):
            file_type = 'xml'
        else:
            if not args.silent:
                print(color_text(f"[-] Error: Could not infer file format for '{args.file}'. Please specify using -t/--type.", COLOR_RED), file=sys.stderr)
            return 1
            
    try:
        data = load_config(args.file, file_type)
        value = query_value(data, args.query)
        output = format_output(value, args.format)
        print(output)
        return 0
    except KeyError as e:
        if not args.silent:
            print(color_text(f"[-] Error: Query path not found. Missing key: {e}", COLOR_RED), file=sys.stderr)
        return 2
    except IndexError as e:
        if not args.silent:
            print(color_text(f"[-] Error: Query path out of bounds. {e}", COLOR_RED), file=sys.stderr)
        return 3
    except TypeError as e:
        if not args.silent:
            print(color_text(f"[-] Error: Invalid query path type match. {e}", COLOR_RED), file=sys.stderr)
        return 4
    except Exception as e:
        if not args.silent:
            print(color_text(f"[-] Error: {e}", COLOR_RED), file=sys.stderr)
        return 5

if __name__ == "__main__":
    sys.exit(main())
