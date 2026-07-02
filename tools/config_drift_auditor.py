#!/usr/bin/env python3
"""
Configuration Drift Auditor

Compares two configuration directories or files containing JSON, YAML, TOML, or .env
files to detect key/structural drift (e.g., comparing local development configs
against production configurations). It checks for missing keys, extra keys, and data
type mismatches, outputting a detailed drift scorecard.

Features:
- Decodes JSON, simple YAML, simple TOML, and .env files natively
- Traverses nested dictionary configurations recursively
- Highlights missing keys, extra keys, and type mismatches
- Returns non-zero exit status if drift is detected (CI friendly)
- Options to perform value comparison or strict structure-only comparison

Usage:
    # Compare staging vs production config file
    python config_drift_auditor.py config/staging.json config/production.json

    # Compare structure only (ignore value differences)
    python config_drift_auditor.py config/dev.env config/prod.env --structure-only
"""

import os
import sys
import json
import re
import argparse

# Simple parser for .env files
def parse_env_file(content):
    config = {}
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        if '=' in line:
            k, v = line.split('=', 1)
            # Remove inline comments and strip quotes
            v_clean = v.split('#')[0].strip().strip('"').strip("'")
            config[k.strip()] = v_clean
    return config

# Simple fallback parser for basic YAML key-value structures
def parse_yaml_simple(content):
    config = {}
    current_dict = config
    indent_stack = [(-1, config)]
    
    for line_num, line in enumerate(content.splitlines(), start=1):
        if not line.strip() or line.strip().startswith('#'):
            continue
            
        # Count leading spaces for indentation
        indent = len(line) - len(line.lstrip(' '))
        line_clean = line.strip()
        
        if ':' in line_clean:
            k, v = line_clean.split(':', 1)
            k = k.strip().strip('"').strip("'")
            v = v.strip()
            
            # Remove inline comments
            if v and '#' in v:
                v = v.split('#')[0].strip()
                
            # Strip quotes from value
            if v:
                v = v.strip('"').strip("'")
                # Try to parse simple types
                if v.lower() == 'true': v = True
                elif v.lower() == 'false': v = False
                elif v.lower() == 'null' or v.lower() == 'nil': v = None
                else:
                    try:
                        if '.' in v: v = float(v)
                        else: v = int(v)
                    except ValueError:
                        pass
            
            # Resolve parent dict by indentation
            while indent_stack and indent <= indent_stack[-1][0]:
                indent_stack.pop()
                
            parent_dict = indent_stack[-1][1] if indent_stack else config
            
            if not v:
                # Nested structure
                new_dict = {}
                parent_dict[k] = new_dict
                indent_stack.append((indent, new_dict))
            else:
                parent_dict[k] = v
                
    return config

# Simple fallback parser for basic TOML tables
def parse_toml_simple(content):
    config = {}
    current_table = config
    
    for line in content.splitlines():
        line_clean = line.strip()
        if not line_clean or line_clean.startswith('#') or line_clean.startswith(';'):
            continue
            
        # Table identifier e.g., [database]
        if line_clean.startswith('[') and line_clean.endswith(']'):
            table_name = line_clean[1:-1].strip()
            # Handle nested tables like [database.auth]
            parts = table_name.split('.')
            curr = config
            for p in parts:
                curr = curr.setdefault(p, {})
            current_table = curr
            continue
            
        if '=' in line_clean:
            k, v = line_clean.split('=', 1)
            k = k.strip().strip('"').strip("'")
            v = v.strip()
            
            # Remove comments
            if '#' in v:
                v = v.split('#')[0].strip()
                
            # Strip quotes and parse types
            v = v.strip('"').strip("'")
            if v.lower() == 'true': v = True
            elif v.lower() == 'false': v = False
            else:
                try:
                    if '.' in v: v = float(v)
                    else: v = int(v)
                except ValueError:
                    pass
            current_table[k] = v
            
    return config

def load_config_file(filepath):
    """Detects type by extension and parses config content into a dict."""
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"File not found: {filepath}")
        
    _, ext = os.path.splitext(filepath.lower())
    
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        raise ValueError(f"Could not read config file {filepath}: {e}")
        
    if ext == '.json':
        try:
            return json.loads(content)
        except Exception as e:
            raise ValueError(f"Failed to parse JSON: {e}")
            
    elif ext in ('.yaml', '.yml'):
        return parse_yaml_simple(content)
        
    elif ext == '.toml':
        # Try python's built-in tomllib if python >= 3.11
        try:
            import tomllib
            with open(filepath, 'rb') as f:
                return tomllib.load(f)
        except (ImportError, Exception):
            return parse_toml_simple(content)
            
    elif ext in ('.env', '.ini'):
        return parse_env_file(content)
        
    else:
        # Fallback to guessing JSON, then env
        try:
            return json.loads(content)
        except Exception:
            return parse_env_file(content)

def compare_dicts(dict_ref, dict_target, path="", structure_only=False):
    """Recursively compares two dictionaries for structure, type, and value drift."""
    drift_report = {
        "missing_keys": [],  # exists in ref, missing in target
        "extra_keys": [],    # exists in target, missing in ref
        "type_mismatches": [],
        "value_drift": []
    }
    
    # 1. Check for missing keys and types/values in target
    for k, v_ref in dict_ref.items():
        curr_path = f"{path}.{k}" if path else k
        
        if k not in dict_target:
            drift_report["missing_keys"].append({
                "path": curr_path,
                "ref_value": v_ref,
                "ref_type": type(v_ref).__name__
            })
            continue
            
        v_tar = dict_target[k]
        
        # Check types
        if type(v_ref) != type(v_tar):
            # Soft type mismatch check: ignore int/float conversions if close
            if isinstance(v_ref, (int, float)) and isinstance(v_tar, (int, float)):
                pass
            else:
                drift_report["type_mismatches"].append({
                    "path": curr_path,
                    "ref_type": type(v_ref).__name__,
                    "target_type": type(v_tar).__name__
                })
                continue
                
        # Recursive comparison for nested dicts
        if isinstance(v_ref, dict) and isinstance(v_tar, dict):
            nested_report = compare_dicts(v_ref, v_tar, curr_path, structure_only)
            # Merge reports
            for key in drift_report:
                drift_report[key].extend(nested_report[key])
        else:
            # Value comparison
            if not structure_only and v_ref != v_tar:
                drift_report["value_drift"].append({
                    "path": curr_path,
                    "ref_value": v_ref,
                    "target_value": v_tar
                })
                
    # 2. Check for extra keys in target
    for k, v_tar in dict_target.items():
        curr_path = f"{path}.{k}" if path else k
        if k not in dict_ref:
            drift_report["extra_keys"].append({
                "path": curr_path,
                "target_value": v_tar,
                "target_type": type(v_tar).__name__
            })
            
    return drift_report

def main():
    parser = argparse.ArgumentParser(
        description="Audit structural and value drift between two configuration files."
    )
    parser.add_argument('reference', help="Path to reference config file (golden config)")
    parser.add_argument('target', help="Path to target config file (comparison config)")
    parser.add_argument(
        '--structure-only', action='store_true',
        help="Only check keys and data types, ignoring actual value differences"
    )
    parser.add_argument('--no-color', action='store_true', help="Disable terminal ANSI colors")
    args = parser.parse_args()

    # ANSI color checking
    use_color = not args.no_color and sys.stdout.isatty() and os.name != 'nt'
    COLOR_RED = "\033[91m" if use_color else ""
    COLOR_YELLOW = "\033[93m" if use_color else ""
    COLOR_GREEN = "\033[92m" if use_color else ""
    COLOR_CYAN = "\033[96m" if use_color else ""
    COLOR_RESET = "\033[0m" if use_color else ""

    print(f"{COLOR_CYAN}=== Configuration Drift Auditor ==={COLOR_RESET}")
    print(f"Reference (Golden): {args.reference}")
    print(f"Target (Comparison): {args.target}\n")

    try:
        ref_config = load_config_file(args.reference)
    except Exception as e:
        print(f"{COLOR_RED}Error loading Reference config: {e}{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)
        
    try:
        target_config = load_config_file(args.target)
    except Exception as e:
        print(f"{COLOR_RED}Error loading Target config: {e}{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)

    # Perform structural comparison
    report = compare_dicts(ref_config, target_config, structure_only=args.structure_only)

    drift_detected = False
    
    # 1. Output Missing Keys
    if report["missing_keys"]:
        drift_detected = True
        print(f"{COLOR_RED}✘ Missing Keys in Target Config ({len(report['missing_keys'])}){COLOR_RESET}")
        for item in report["missing_keys"]:
            print(f"  - {COLOR_YELLOW}{item['path']}{COLOR_RESET} (Type: {item['ref_type']}, Expected default: {item['ref_value']})")
        print()
        
    # 2. Output Type Mismatches
    if report["type_mismatches"]:
        drift_detected = True
        print(f"{COLOR_RED}✘ Type Mismatches ({len(report['type_mismatches'])}){COLOR_RESET}")
        for item in report["type_mismatches"]:
            print(f"  - {COLOR_YELLOW}{item['path']}{COLOR_RESET} (Expected Type: {item['ref_type']}, Got: {item['target_type']})")
        print()
        
    # 3. Output Value Drift (if checked)
    if not args.structure_only and report["value_drift"]:
        drift_detected = True
        print(f"{COLOR_YELLOW}⚠ Value Differences ({len(report['value_drift'])}){COLOR_RESET}")
        for item in report["value_drift"]:
            print(f"  - {COLOR_CYAN}{item['path']}{COLOR_RESET}")
            print(f"    Expected value: {item['ref_value']}")
            print(f"    Target value:   {item['target_value']}")
        print()
        
    # 4. Output Extra Keys in Target
    if report["extra_keys"]:
        # Do not strictly count extra keys as failing drift unless requested, but report them
        print(f"{COLOR_CYAN}ℹ Extra Keys present in Target Config ({len(report['extra_keys'])}){COLOR_RESET}")
        for item in report["extra_keys"]:
            print(f"  + {item['path']} (Type: {item['target_type']}, Value: {item['target_value']})")
        print()

    print(f"{COLOR_CYAN}--- Summary Scorecard ---{COLOR_RESET}")
    print(f"Missing Keys:    {COLOR_RED if report['missing_keys'] else COLOR_GREEN}{len(report['missing_keys'])}{COLOR_RESET}")
    print(f"Type Mismatches: {COLOR_RED if report['type_mismatches'] else COLOR_GREEN}{len(report['type_mismatches'])}{COLOR_RESET}")
    if not args.structure_only:
        print(f"Value Drifts:    {COLOR_YELLOW if report['value_drift'] else COLOR_GREEN}{len(report['value_drift'])}{COLOR_RESET}")
    print(f"Extra Keys:      {len(report['extra_keys'])}")

    if drift_detected:
        print(f"\n{COLOR_RED}✘ Drift detected! Configuration files are out of sync.{COLOR_RESET}")
        sys.exit(1)
    else:
        print(f"\n{COLOR_GREEN}✔ Perfect! Target configuration is in sync with Reference.{COLOR_RESET}")
        sys.exit(0)

if __name__ == '__main__':
    main()
