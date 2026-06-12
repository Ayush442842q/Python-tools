#!/usr/bin/env python3
"""
Config File Converter - Convert configuration files between formats.

Supports JSON, XML, INI (built-in) and YAML, TOML (via optional packages).

Usage:
    python tools/config_converter.py -i input.json -o output.yaml
"""

import sys
import os
import json
import argparse
import configparser
from xml.etree import ElementTree as ET
from typing import Any, Dict


def parse_args():
    parser = argparse.ArgumentParser(
        description="Config File Converter - Convert config files between JSON, INI, XML, YAML, and TOML."
    )
    parser.add_argument("-i", "--input", required=True, help="Input configuration file")
    parser.add_argument("-o", "--output", required=True, help="Output configuration file")
    parser.add_argument(
        "--from-format",
        choices=["json", "ini", "xml", "yaml", "toml"],
        help="Force input format (detected from extension if omitted)",
    )
    parser.add_argument(
        "--to-format",
        choices=["json", "ini", "xml", "yaml", "toml"],
        help="Force output format (detected from extension if omitted)",
    )
    parser.add_argument(
        "--indent", type=int, default=2, help="Indentation spaces for JSON/XML/YAML (default: 2)"
    )
    return parser.parse_args()


# Helpers for dict flattening and unflattening (needed for INI format)
def flatten_dict(d: Dict[str, Any], parent_key: str = "", sep: str = ".") -> Dict[str, Any]:
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def unflatten_dict(d: Dict[str, Any], sep: str = ".") -> Dict[str, Any]:
    result = {}
    for k, v in d.items():
        parts = k.split(sep)
        curr = result
        for part in parts[:-1]:
            if part not in curr or not isinstance(curr[part], dict):
                curr[part] = {}
            curr = curr[part]
        curr[parts[-1]] = v
    return result


# XML parser & generator helpers
def xml_to_dict(element: ET.Element) -> Any:
    if len(element) == 0:
        return element.text or ""
    result = {}
    for child in element:
        child_data = xml_to_dict(child)
        if child.tag in result:
            if not isinstance(result[child.tag], list):
                result[child.tag] = [result[child.tag]]
            result[child.tag].append(child_data)
        else:
            result[child.tag] = child_data
    return result


def dict_to_xml(tag: str, d: Any) -> ET.Element:
    elem = ET.Element(tag)
    if isinstance(d, dict):
        for key, val in d.items():
            if isinstance(val, list):
                for item in val:
                    elem.append(dict_to_xml(key, item))
            else:
                elem.append(dict_to_xml(key, val))
    else:
        elem.text = str(d)
    return elem


# Loader and Saver functions
def load_yaml(filepath: str) -> Dict[str, Any]:
    try:
        import yaml
    except ImportError:
        print(
            "Error: 'pyyaml' package is required for YAML support. Install it with:\n"
            "  pip install pyyaml",
            file=sys.stderr,
        )
        sys.exit(1)
    with open(filepath, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def save_yaml(data: Dict[str, Any], filepath: str, indent: int):
    try:
        import yaml
    except ImportError:
        print(
            "Error: 'pyyaml' package is required for YAML support. Install it with:\n"
            "  pip install pyyaml",
            file=sys.stderr,
        )
        sys.exit(1)
    with open(filepath, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, indent=indent)


def load_toml(filepath: str) -> Dict[str, Any]:
    # Try built-in tomllib (Python 3.11+) first
    try:
        import tomllib
        with open(filepath, "rb") as f:
            return tomllib.load(f)
    except ImportError:
        pass
    
    # Try third-party toml package
    try:
        import toml
        with open(filepath, "r", encoding="utf-8") as f:
            return toml.load(f)
    except ImportError:
        print(
            "Error: 'toml' package is required for TOML support on Python < 3.11. Install it with:\n"
            "  pip install toml",
            file=sys.stderr,
        )
        sys.exit(1)


def save_toml(data: Dict[str, Any], filepath: str):
    try:
        import toml
    except ImportError:
        print(
            "Error: 'toml' package is required for writing TOML files. Install it with:\n"
            "  pip install toml",
            file=sys.stderr,
        )
        sys.exit(1)
    with open(filepath, "w", encoding="utf-8") as f:
        toml.dump(data, f)


def load_ini(filepath: str) -> Dict[str, Any]:
    config = configparser.ConfigParser()
    config.read(filepath, encoding="utf-8")
    
    result = {}
    for section in config.sections():
        result[section] = {}
        for key, val in config.items(section):
            # Parse numbers/booleans if possible
            if val.lower() == "true":
                val = True
            elif val.lower() == "false":
                val = False
            else:
                try:
                    if "." in val:
                        val = float(val)
                    else:
                        val = int(val)
                except ValueError:
                    pass
            result[section][key] = val
            
    # Unflatten if keys contain dots (since we flatten them on write)
    unflattened = {}
    for section, content in result.items():
        unflattened[section] = unflatten_dict(content)
    return unflattened


def save_ini(data: Dict[str, Any], filepath: str):
    config = configparser.ConfigParser()
    
    # INI files require a 2-level structure (sections containing key-values)
    # If the dict is deeper, we must flatten it
    for key, val in data.items():
        if isinstance(val, dict):
            config[key] = {}
            flat = flatten_dict(val)
            for fk, fv in flat.items():
                config[key][fk] = str(fv)
        else:
            # Default section for top-level non-dict items
            if "DEFAULT" not in config:
                config["DEFAULT"] = {}
            config["DEFAULT"][key] = str(val)
            
    with open(filepath, "w", encoding="utf-8") as f:
        config.write(f)


def load_xml(filepath: str) -> Dict[str, Any]:
    tree = ET.parse(filepath)
    root = tree.getroot()
    return {root.tag: xml_to_dict(root)}


def save_xml(data: Dict[str, Any], filepath: str, indent: int):
    if len(data) != 1:
        # XML needs a single root element. Wrap it if necessary.
        data = {"root": data}
        
    root_tag = list(data.keys())[0]
    root_elem = dict_to_xml(root_tag, data[root_tag])
    
    # Simple indent styling
    def indent_elem(elem, level=0):
        i = "\n" + level * (" " * indent)
        if len(elem):
            if not elem.text or not elem.text.strip():
                elem.text = i + " " * indent
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
            for elem in elem:
                indent_elem(elem, level + 1)
            if not elem.tail or not elem.tail.strip():
                elem.tail = i
        else:
            if level and (not elem.tail or not elem.tail.strip()):
                elem.tail = i

    indent_elem(root_elem)
    tree = ET.ElementTree(root_elem)
    tree.write(filepath, encoding="utf-8", xml_declaration=True)


def main():
    args = parse_args()

    # Detect formats from file extensions
    in_format = args.from_format or os.path.splitext(args.input)[1].lstrip(".").lower()
    out_format = args.to_format or os.path.splitext(args.output)[1].lstrip(".").lower()

    if not in_format or not out_format:
        print("Error: Could not auto-detect file formats. Use --from-format and --to-format.", file=sys.stderr)
        return 1

    # Load data
    try:
        if in_format == "json":
            with open(args.input, "r", encoding="utf-8") as f:
                data = json.load(f)
        elif in_format == "ini":
            data = load_ini(args.input)
        elif in_format == "xml":
            data = load_xml(args.input)
        elif in_format == "yaml" or in_format == "yml":
            data = load_yaml(args.input)
        elif in_format == "toml":
            data = load_toml(args.input)
        else:
            print(f"Error: Unsupported input format '{in_format}'", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"Error loading input file '{args.input}': {e}", file=sys.stderr)
        return 1

    # Save data
    try:
        if out_format == "json":
            with open(args.output, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=args.indent)
        elif out_format == "ini":
            save_ini(data, args.output)
        elif out_format == "xml":
            save_xml(data, args.output, args.indent)
        elif out_format in ("yaml", "yml"):
            save_yaml(data, args.output, args.indent)
        elif out_format == "toml":
            save_toml(data, args.output)
        else:
            print(f"Error: Unsupported output format '{out_format}'", file=sys.stderr)
            return 1
    except Exception as e:
        print(f"Error saving output file '{args.output}': {e}", file=sys.stderr)
        return 1

    print(f"✓ Successfully converted '{args.input}' ({in_format}) to '{args.output}' ({out_format}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
