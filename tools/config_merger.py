#!/usr/bin/env python3
"""
Config Merger - Recursively merges multiple configuration files (JSON, INI, XML, YAML, TOML)
with hierarchical overrides. Overrides can also be passed via dot-notation CLI arguments.
"""

import argparse
import configparser
import json
import os
import sys
import xml.etree.ElementTree as ET

# Optional YAML and TOML support
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
        import toml  # third-party
        HAS_TOML = True
    except ImportError:
        pass

def xml_to_dict(element):
    """Converts an XML element tree to a dictionary."""
    children = list(element)
    if not children:
        # Try converting string value to primitive types
        val = element.text or ""
        val_strip = val.strip()
        if val_strip.lower() == 'true': return True
        if val_strip.lower() == 'false': return False
        try:
            if '.' in val_strip: return float(val_strip)
            return int(val_strip)
        except ValueError:
            return val
    
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
        for k, v in d.items():
            child = dict_to_xml(k, v)
            elem.append(child)
    elif isinstance(d, list):
        for item in d:
            child = dict_to_xml('item', item)
            elem.append(child)
    else:
        elem.text = str(d)
    return elem

def load_ini(file_path):
    """Loads an INI file into a dictionary format."""
    config = configparser.ConfigParser()
    config.read(file_path)
    result = {}
    for section in config.sections():
        result[section] = {}
        for option in config.options(section):
            val = config.get(section, option)
            # Basic type coercion
            if val.lower() in ('true', 'yes', 'on'):
                result[section][option] = True
            elif val.lower() in ('false', 'no', 'off'):
                result[section][option] = False
            else:
                try:
                    if '.' in val:
                        result[section][option] = float(val)
                    else:
                        result[section][option] = int(val)
                except ValueError:
                    result[section][option] = val
    return result

def save_ini(d, file_path):
    """Saves a dictionary as INI configuration file."""
    config = configparser.ConfigParser()
    for section, options in d.items():
        if isinstance(options, dict):
            config.add_section(section)
            for k, v in options.items():
                config.set(section, k, str(v))
        else:
            # Flatten root keys into a DEFAULT section
            if 'DEFAULT' not in config:
                config.add_section('DEFAULT')
            config.set('DEFAULT', section, str(options))
    with open(file_path, 'w', encoding='utf-8') as f:
        config.write(f)

def load_config(file_path):
    """Loads a configuration file based on its extension."""
    _, ext = os.path.splitext(file_path.lower())
    
    if ext == '.json':
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
            
    elif ext in ('.yaml', '.yml'):
        if not HAS_YAML:
            raise ImportError("PyYAML is not installed. Cannot parse YAML.")
        with open(file_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
            
    elif ext == '.toml':
        if not HAS_TOML:
            raise ImportError("tomllib/toml package is not installed. Cannot parse TOML.")
        with open(file_path, 'rb' if 'tomllib' in sys.modules else 'r') as f:
            if 'tomllib' in sys.modules:
                return tomllib.load(f)
            else:
                return toml.load(f)
                
    elif ext in ('.ini', '.cfg', '.conf'):
        return load_ini(file_path)
        
    elif ext == '.xml':
        tree = ET.parse(file_path)
        return xml_to_dict(tree.getroot())
        
    else:
        # Try JSON parsing as default fallback
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            raise ValueError(f"Unsupported configuration format for file: {file_path}")

def deep_merge(dict1, dict2):
    """Recursively merges dict2 into dict1 (overwriting values)."""
    result = dict1.copy()
    for key, val in dict2.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = deep_merge(result[key], val)
        else:
            result[key] = val
    return result

def set_nested_value(d, key_path, value):
    """Sets a nested value in dictionary using dot-notation path: 'server.port'."""
    keys = key_path.split('.')
    current = d
    for key in keys[:-1]:
        if key not in current or not isinstance(current[key], dict):
            current[key] = {}
        current = current[key]
        
    # Attempt to parse value as JSON to preserve types
    try:
        parsed_val = json.loads(value)
    except ValueError:
        parsed_val = value
        
    current[keys[-1]] = parsed_val

def save_config(d, file_path, fmt):
    """Saves dictionary to configuration file format."""
    fmt = fmt.lower().strip('.')
    if fmt == 'json':
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(d, f, indent=2)
    elif fmt in ('yaml', 'yml'):
        if not HAS_YAML:
            raise ImportError("PyYAML is not installed. Cannot write YAML.")
        with open(file_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(d, f, default_flow_style=False)
    elif fmt == 'toml':
        if not HAS_TOML:
            raise ImportError("toml/tomli_w package is not installed. Cannot write TOML.")
        if 'tomli_w' in sys.modules:
            with open(file_path, 'wb') as f:
                tomli_w.dump(d, f)
        else:
            with open(file_path, 'w', encoding='utf-8') as f:
                toml.dump(d, f)
    elif fmt in ('ini', 'cfg', 'conf'):
        save_ini(d, file_path)
    elif fmt == 'xml':
        root_tag = 'config'
        root = dict_to_xml(root_tag, d)
        tree = ET.ElementTree(root)
        ET.indent(tree, space="  ")  # Pretty print
        tree.write(file_path, encoding='utf-8', xml_declaration=True)
    else:
        raise ValueError(f"Unsupported output format: {fmt}")

def main():
    parser = argparse.ArgumentParser(description="Deep merge config files with hierarchical overrides.")
    parser.add_argument("files", nargs="+", help="Config files to merge (ordered lowest to highest precedence)")
    parser.add_argument("-o", "--output", help="Output file path")
    parser.add_argument("-f", "--format", choices=["json", "yaml", "toml", "ini", "xml"], default="json",
                        help="Output format (default: json)")
    parser.add_argument("-d", "--set", action="append", metavar="KEY=VALUE",
                        help="Override specific keys via CLI dot notation (e.g., -d server.port=9000)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print the resolved configuration to stdout")
    
    args = parser.parse_args()
    
    resolved_config = {}
    
    for file_path in args.files:
        if not os.path.exists(file_path):
            print(f"Error: Configuration file not found: {file_path}", file=sys.stderr)
            sys.exit(1)
        try:
            config = load_config(file_path)
            resolved_config = deep_merge(resolved_config, config)
        except Exception as e:
            print(f"Error loading {file_path}: {e}", file=sys.stderr)
            sys.exit(1)
            
    # Apply CLI dot notation overrides
    if args.set:
        for override in args.set:
            if '=' not in override:
                print(f"Error: Invalid override format '{override}'. Expected KEY=VALUE.", file=sys.stderr)
                sys.exit(1)
            k_path, val = override.split('=', 1)
            set_nested_value(resolved_config, k_path.strip(), val.strip())
            
    if args.verbose or not args.output:
        print(json.dumps(resolved_config, indent=2))
        
    if args.output:
        try:
            save_config(resolved_config, args.output, args.format)
            print(f"Successfully saved resolved configuration to {args.output}")
        except Exception as e:
            print(f"Error saving output file: {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    main()
