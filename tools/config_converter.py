#!/usr/bin/env python3
"""
Config Format Converter

Converts configuration files between JSON, INI, and XML formats.
Supports YAML and TOML if their respective packages are installed.

Usage:
    python config_converter.py -i input.json -o output.ini
"""

import sys
import os
import json
import configparser
import xml.etree.ElementTree as ET
import argparse
from pathlib import Path

# Optional imports for YAML and TOML
HAS_YAML = False
try:
    import yaml
    HAS_YAML = True
except ImportError:
    pass

HAS_TOML = False
try:
    import tomllib  # Python 3.11+
    import tomli_w
    HAS_TOML = True
except ImportError:
    try:
        import toml  # third-party backup
        HAS_TOML = True
    except ImportError:
        pass

# --- XML Helper Functions ---
def xml_to_dict(element):
    """Converts an XML element tree to a dictionary."""
    children = list(element)
    if not children:
        return element.text or ""
    
    result = {}
    for child in children:
        child_data = xml_to_dict(child)
        tag = child.tag
        if tag in result:
            if not isinstance(result[tag], list):
                result[tag] = [result[tag]]
            result[tag].append(child_data)
        else:
            result[tag] = child_data
    return result

def dict_to_xml(tag, d):
    """Converts a dictionary to an XML element tree."""
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

# --- Config Format Parsers and Serializers ---
def parse_ini(file_path):
    """Parse INI file to dict."""
    config = configparser.ConfigParser()
    config.read(file_path)
    result = {}
    for section in config.sections():
        result[section] = {}
        for key, val in config.items(section):
            # Try to convert types where appropriate
            if val.lower() in ('true', 'yes', 'on'):
                result[section][key] = True
            elif val.lower() in ('false', 'no', 'off'):
                result[section][key] = False
            else:
                try:
                    if '.' in val:
                        result[section][key] = float(val)
                    else:
                        result[section][key] = int(val)
                except ValueError:
                    result[section][key] = val
    return result

def write_ini(data, file_path):
    """Write dict to INI file."""
    config = configparser.ConfigParser()
    
    # INI requires a 2-level nested dict (sections containing key-value pairs)
    # If the dict is flat, we create a default section.
    is_flat = not any(isinstance(v, dict) for v in data.values())
    
    if is_flat:
        config['settings'] = {k: str(v) for k, v in data.items()}
    else:
        for section, content in data.items():
            if isinstance(content, dict):
                config[str(section)] = {k: str(v) for k, v in content.items()}
            else:
                # If there's a mix of sections and flat keys
                if 'settings' not in config:
                    config['settings'] = {}
                config['settings'][str(section)] = str(content)
                
    with open(file_path, 'w', encoding='utf-8') as f:
        config.write(f)

def parse_xml(file_path):
    """Parse XML file to dict."""
    tree = ET.parse(file_path)
    root = tree.getroot()
    return {root.tag: xml_to_dict(root)}

def write_xml(data, file_path):
    """Write dict to XML file."""
    # Assume the root is the first key or default to 'root'
    root_tag = 'root'
    root_data = data
    
    if isinstance(data, dict) and len(data) == 1:
        root_tag = list(data.keys())[0]
        root_data = data[root_tag]
        
    root_elem = dict_to_xml(root_tag, root_data)
    tree = ET.ElementTree(root_elem)
    
    # Format and write XML
    # Using a simple indent on root element if supported in older python versions
    try:
        ET.indent(tree, space="  ", level=0)
    except AttributeError:
        pass  # indent added in Python 3.9
        
    tree.write(file_path, encoding='utf-8', xml_declaration=True)

def parse_yaml(file_path):
    """Parse YAML file to dict."""
    if not HAS_YAML:
        raise ImportError("YAML parser is not installed. Run 'pip install pyyaml'.")
    with open(file_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def write_yaml(data, file_path):
    """Write dict to YAML file."""
    if not HAS_YAML:
        raise ImportError("YAML serializer is not installed. Run 'pip install pyyaml'.")
    with open(file_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(data, f, default_flow_style=False, sort_keys=False)

def parse_toml(file_path):
    """Parse TOML file to dict."""
    if not HAS_TOML:
        raise ImportError("TOML parser is not installed. On Python <3.11 run 'pip install toml'.")
    with open(file_path, 'rb' if 'tomllib' in sys.modules else 'r', encoding=None if 'tomllib' in sys.modules else 'utf-8') as f:
        if 'tomllib' in sys.modules:
            return tomllib.load(f)
        elif 'toml' in sys.modules:
            return toml.load(f)

def write_toml(data, file_path):
    """Write dict to TOML file."""
    if not HAS_TOML:
        raise ImportError("TOML serializer is not installed. On Python <3.11 run 'pip install toml'.")
    if 'tomli_w' in sys.modules:
        with open(file_path, 'wb') as f:
            tomli_w.dump(data, f)
    elif 'toml' in sys.modules:
        with open(file_path, 'w', encoding='utf-8') as f:
            toml.dump(data, f)

# --- Main Logic ---
def get_format_from_extension(file_path):
    """Get lowercase format name from file extension."""
    ext = Path(file_path).suffix.lower()
    if ext == '.json':
        return 'json'
    elif ext in ('.ini', '.cfg', '.conf'):
        return 'ini'
    elif ext in ('.xml', '.xhtml'):
        return 'xml'
    elif ext in ('.yaml', '.yml'):
        return 'yaml'
    elif ext == '.toml':
        return 'toml'
    return None

def main():
    parser = argparse.ArgumentParser(
        description="Convert configuration files between different formats (JSON, INI, XML, YAML, TOML).",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to the input configuration file."
    )
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Path to save the converted configuration file."
    )
    parser.add_argument(
        "--from-format", "-f",
        choices=['json', 'ini', 'xml', 'yaml', 'toml'],
        help="Explicit input format (inferred from extension by default)."
    )
    parser.add_argument(
        "--to-format", "-t",
        choices=['json', 'ini', 'xml', 'yaml', 'toml'],
        help="Explicit output format (inferred from extension by default)."
    )
    
    args = parser.parse_args()
    
    # Check input file existence
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' does not exist.", file=sys.stderr)
        return 1
        
    # Infer formats
    in_format = args.from_format or get_format_from_extension(args.input)
    out_format = args.to_format or get_format_from_extension(args.output)
    
    if not in_format:
        print("Error: Could not determine input file format. Use --from-format.", file=sys.stderr)
        return 1
    if not out_format:
        print("Error: Could not determine output file format. Use --to-format.", file=sys.stderr)
        return 1
        
    print(f"Converting '{args.input}' ({in_format.upper()}) -> '{args.output}' ({out_format.upper()})...")
    
    # 1. Parse Input
    try:
        if in_format == 'json':
            with open(args.input, 'r', encoding='utf-8') as f:
                data = json.load(f)
        elif in_format == 'ini':
            data = parse_ini(args.input)
        elif in_format == 'xml':
            data = parse_xml(args.input)
        elif in_format == 'yaml':
            data = parse_yaml(args.input)
        elif in_format == 'toml':
            data = parse_toml(args.input)
    except ImportError as e:
        print(f"Dependency Error: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"Error reading/parsing input file: {e}", file=sys.stderr)
        return 1
        
    # 2. Write Output
    try:
        if out_format == 'json':
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4)
        elif out_format == 'ini':
            write_ini(data, args.output)
        elif out_format == 'xml':
            write_xml(data, args.output)
        elif out_format == 'yaml':
            write_yaml(data, args.output)
        elif out_format == 'toml':
            write_toml(data, args.output)
    except ImportError as e:
        print(f"Dependency Error: {e}", file=sys.stderr)
        # Cleanup incomplete output file if created
        if os.path.exists(args.output):
            os.remove(args.output)
        return 2
    except Exception as e:
        print(f"Error serializing/writing output file: {e}", file=sys.stderr)
        if os.path.exists(args.output):
            os.remove(args.output)
        return 1
        
    print("Conversion completed successfully!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
