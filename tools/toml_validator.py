#!/usr/bin/env python3
"""
TOML Validator & Formatter
Validate TOML files for syntax compliance, format them cleanly, and convert them to JSON.

Usage:
    python tools/toml_validator.py config.toml
    python tools/toml_validator.py config.toml --format
    python tools/toml_validator.py config.toml --json
"""

import argparse
import json
import os
import re
import sys
from typing import Any, Dict, List, Optional, Tuple


# ANSI Escape Codes for colorized output
COLOR_HEADER = "\033[95m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"
COLOR_GREEN = "\033[92m"
COLOR_WARNING = "\033[93m"
COLOR_FAIL = "\033[91m"
COLOR_END = "\033[0m"
COLOR_BOLD = "\033[1m"


def print_colored(text: str, color: str):
    """Print text with ANSI color codes if output is a TTY."""
    if sys.stdout.isatty():
        print(f"{color}{text}{COLOR_END}")
    else:
        print(text)


# Load a TOML parser depending on availability
toml_parser_type = None

try:
    import tomllib  # Python 3.11+
    toml_parser_type = "tomllib"
except ImportError:
    try:
        import toml  # third-party
        toml_parser_type = "toml"
    except ImportError:
        try:
            import tomli as tomllib  # third-party alternative
            toml_parser_type = "tomli"
        except ImportError:
            toml_parser_type = "fallback"


def parse_toml_standard(content: str) -> Tuple[bool, Optional[str], Optional[Dict]]:
    """Parse TOML using tomllib or toml packages."""
    if toml_parser_type == "tomllib" or toml_parser_type == "tomli":
        try:
            data = tomllib.loads(content)
            return True, None, data
        except Exception as e:
            return False, str(e), None
    elif toml_parser_type == "toml":
        try:
            data = toml.loads(content)
            return True, None, data
        except Exception as e:
            return False, str(e), None
    return False, "No parser", None


class FallbackTOMLParser:
    """A lightweight, pure-Python fallback TOML validator for basic syntax checking."""
    
    def __init__(self, content: str):
        self.content = content
        self.lines = content.splitlines()

    def validate(self) -> Tuple[bool, Optional[str], Optional[Dict]]:
        parsed_data = {}
        current_table = parsed_data
        
        # Regex definitions
        key_pattern = r'^[a-zA-Z0-9_-]+'
        string_pattern = r'^"[^"\\]*(?:\\.[^"\\]*)*"'
        number_pattern = r'^[+-]?(?:\d+(?:\.\d+)?|\.\d+)(?:[eE][+-]?\d+)?'
        bool_pattern = r'^(?:true|false)'
        date_pattern = r'^\d{4}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?)?'
        
        for line_idx, line in enumerate(self.lines, 1):
            line_strip = line.strip()
            # Skip empty lines and comments
            if not line_strip or line_strip.startswith("#"):
                continue

            # Check for standard table headers [table_name]
            if line_strip.startswith("[") and line_strip.endswith("]"):
                table_name = line_strip[1:-1].strip()
                if not table_name or "[" in table_name or "]" in table_name:
                    return False, f"Line {line_idx}: Invalid table header format", None
                
                # Setup nested dict path
                parts = table_name.split(".")
                curr = parsed_data
                for part in parts:
                    part_clean = part.strip()
                    if not part_clean:
                        return False, f"Line {line_idx}: Empty table name segments", None
                    if part_clean not in curr:
                        curr[part_clean] = {}
                    curr = curr[part_clean]
                current_table = curr
                continue

            # Check for key-value pairs
            if "=" in line_strip:
                parts = line_strip.split("=", 1)
                key = parts[0].strip()
                val_str = parts[1].strip()
                
                if not key:
                    return False, f"Line {line_idx}: Key is missing before '='", None
                
                # Basic key validation
                if not re.match(r'^[a-zA-Z0-9._"-]+$', key):
                    return False, f"Line {line_idx}: Invalid character in key '{key}'", None

                # Value validation
                # Strip inline comment if any (making sure not inside string)
                if "#" in val_str:
                    # Simple check: if # is not inside quotes
                    in_quotes = False
                    comment_idx = -1
                    for idx, char in enumerate(val_str):
                        if char == '"':
                            in_quotes = not in_quotes
                        elif char == '#' and not in_quotes:
                            comment_idx = idx
                            break
                    if comment_idx != -1:
                        val_str = val_str[:comment_idx].strip()

                if not val_str:
                    return False, f"Line {line_idx}: Missing value for key '{key}'", None

                # Validate value data types
                is_valid_val = (
                    re.match(string_pattern, val_str) or
                    re.match(number_pattern, val_str) or
                    re.match(bool_pattern, val_str) or
                    re.match(date_pattern, val_str) or
                    val_str.startswith("[") or  # Array placeholder
                    val_str.startswith("{")     # Inline table placeholder
                )
                if not is_valid_val:
                    return False, f"Line {line_idx}: Syntax error or unsupported value format: '{val_str}'", None

                current_table[key] = val_str
                continue

            # If line doesn't match comments, tables, or key-value
            return False, f"Line {line_idx}: Syntax error, unrecognized statement: '{line_strip}'", None

        return True, None, parsed_data


def format_toml(content: str) -> str:
    """Format and clean a TOML content layout (pretty printer)."""
    lines = content.splitlines()
    formatted = []
    
    for line in lines:
        line_strip = line.strip()
        if not line_strip:
            formatted.append("")
            continue
            
        if line_strip.startswith("#"):
            formatted.append(line_strip)
            continue
            
        if line_strip.startswith("[") and line_strip.endswith("]"):
            formatted.append("")  # Add spacing before tables
            formatted.append(line_strip)
            continue
            
        if "=" in line_strip:
            parts = line_strip.split("=", 1)
            key = parts[0].strip()
            val = parts[1].strip()
            formatted.append(f"{key} = {val}")
            continue
            
        formatted.append(line_strip)
        
    # Clean up double empty lines
    result = "\n".join(formatted)
    result = re.sub(r"\n{3,}", "\n\n", result)
    return result.strip() + "\n"


def main():
    parser = argparse.ArgumentParser(
        description="TOML Validator & Formatter CLI utility.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("toml_file", help="Path to the TOML file to validate")
    parser.add_argument("--format", "-f", action="store_true", help="Format/beautify the TOML file and display output")
    parser.add_argument("--write", "-w", action="store_true", help="Write formatted changes back to the file (used with --format)")
    parser.add_argument("--json", "-j", action="store_true", help="Convert TOML structure to JSON format")

    args = parser.parse_args()

    if not os.path.exists(args.toml_file):
        print_colored(f"[!] File not found: {args.toml_file}", COLOR_FAIL)
        sys.exit(1)

    with open(args.toml_file, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()

    # Determine validation
    is_valid = False
    error_msg = None
    data = None
    
    if toml_parser_type != "fallback":
        is_valid, error_msg, data = parse_toml_standard(content)
        parser_used = f"Standard ({toml_parser_type})"
    else:
        fallback = FallbackTOMLParser(content)
        is_valid, error_msg, data = fallback.validate()
        parser_used = "Fallback (Pure Python)"

    if not is_valid:
        print_colored(f"\n❌ TOML Validation Failed! [Parser: {parser_used}]", COLOR_FAIL)
        print_colored(f"Error: {error_msg}", COLOR_BOLD + COLOR_FAIL)
        sys.exit(1)

    # If valid
    if args.json:
        # Print JSON representation
        print(json.dumps(data, indent=2))
    elif args.format:
        formatted_content = format_toml(content)
        if args.write:
            with open(args.toml_file, "w", encoding="utf-8") as f:
                f.write(formatted_content)
            print_colored(f"[+] Cleanly formatted and saved to '{args.toml_file}'", COLOR_GREEN)
        else:
            print(formatted_content)
    else:
        print_colored(f"\n✅ TOML Validation Succeeded! [Parser: {parser_used}]", COLOR_GREEN)
        print(f"File '{args.toml_file}' contains valid TOML structure.")


if __name__ == "__main__":
    main()
