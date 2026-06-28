#!/usr/bin/env python3
"""
JSON Schema Interactive Form Collector
Generates a dynamic interactive CLI terminal questionnaire based on a JSON Schema (draft-07).
Collects, validates (types, ranges, patterns, enums), and exports user input as a conforming JSON document.
"""

import argparse
import json
import re
import sys

# ANSI Colors for terminal output
COLOR_HEADER = "\033[95m"
COLOR_BLUE = "\033[94m"
COLOR_GREEN = "\033[92m"
COLOR_WARNING = "\033[93m"
COLOR_FAIL = "\033[91m"
COLOR_END = "\033[0m"
COLOR_BOLD = "\033[1m"


def print_banner():
    banner = f"""{COLOR_HEADER}{COLOR_BOLD}
  ▒█████   █     █░ ███▄    █  ██████ 
 ▒██▒  ██▒▓█    █ ░ ██ ▀█   █ ▒██    ▒ 
 ▒██░  ██▒▒█    █ ░▓██  ▀█  █ ░ ▓██▄   
 ▒██   ██░░█    █ ░▓██▒  ▐░ █   ▒   ██▒
 ░ ████▓▒░░▓█▄▄█▓ ░▒██░   ░ █ ▒██████▒▒
 ░ ▒░▒░▒░  ░ ▒░▒░  ░ ▒░   ░ ░ ▒ ▒▓▒ ▒ ░
   ░ ▒ ▒░    ░▒░ ░   ░ ░   ░ ░ ░ ░▒▒ ░ ░
 ░ ░ ░ ▒     ░░      ░   ░ ░ ░  ░  ░   
     ░ ░      ░            ░       ░   
                                       
{COLOR_END}{COLOR_BLUE}    JSON Schema CLI Interactive Questionnaire & Validation Wizard{COLOR_END}
"""
    print(banner, file=sys.stderr)


# Example JSON Schema to use when none is provided
DEFAULT_SCHEMA = {
    "$schema": "http://json-schema.org/draft-07/schema#",
    "title": "Developer Profile Setup",
    "description": "Enter your profile details to configure your workstation.",
    "type": "object",
    "required": ["username", "email", "years_experience"],
    "properties": {
        "username": {
            "type": "string",
            "description": "Your workstation login handle",
            "minLength": 3,
            "maxLength": 15,
            "pattern": "^[a-z0-9_]+$"
        },
        "email": {
            "type": "string",
            "description": "Your primary contact email address",
            "pattern": "^[^@]+@[^@]+\\.[^@]+$"
        },
        "role": {
            "type": "string",
            "description": "Your engineering position",
            "enum": ["Frontend Developer", "Backend Developer", "DevOps Engineer", "Security Analyst"],
            "default": "Backend Developer"
        },
        "years_experience": {
            "type": "integer",
            "description": "Number of years working in technology",
            "minimum": 0,
            "maximum": 50
        },
        "opt_in_beta": {
            "type": "boolean",
            "description": "Participate in early access system features?",
            "default": True
        }
    }
}


def validate_input(val_str, prop_name, prop_def, is_required):
    """
    Validate raw string input against a single property schema definition.
    Returns (success, parsed_value, error_message).
    """
    # Clean whitespace
    val_str = val_str.strip()
    
    # 1. Handle Empty Input / Defaults
    if val_str == "":
        if "default" in prop_def:
            return True, prop_def["default"], None
        if is_required:
            return False, None, "This property is required."
        return True, None, None

    prop_type = prop_def.get("type", "string")

    # 2. Type Checking and Conversions
    if prop_type == "integer":
        try:
            parsed_val = int(val_str)
        except ValueError:
            return False, None, "Must be an integer."
    elif prop_type == "number":
        try:
            parsed_val = float(val_str)
        except ValueError:
            return False, None, "Must be a decimal number."
    elif prop_type == "boolean":
        normalized = val_str.lower()
        if normalized in ["y", "yes", "true", "t", "1"]:
            parsed_val = True
        elif normalized in ["n", "no", "false", "f", "0"]:
            parsed_val = False
        else:
            return False, None, "Must be a boolean (yes/no, true/false)."
    else:
        parsed_val = val_str

    # 3. Numeric Constraints (minimum, maximum)
    if prop_type in ["integer", "number"]:
        if "minimum" in prop_def and parsed_val < prop_def["minimum"]:
            return False, None, f"Value must be >= {prop_def['minimum']}."
        if "maximum" in prop_def and parsed_val > prop_def["maximum"]:
            return False, None, f"Value must be <= {prop_def['maximum']}."

    # 4. String Constraints (minLength, maxLength, pattern, enum)
    if prop_type == "string":
        if "minLength" in prop_def and len(parsed_val) < prop_def["minLength"]:
            return False, None, f"Length must be at least {prop_def['minLength']} characters."
        if "maxLength" in prop_def and len(parsed_val) > prop_def["maxLength"]:
            return False, None, f"Length must be at most {prop_def['maxLength']} characters."
        if "pattern" in prop_def:
            pattern = prop_def["pattern"]
            if not re.match(pattern, parsed_val):
                return False, None, f"Value does not match pattern: {pattern}"
        if "enum" in prop_def and parsed_val not in prop_def["enum"]:
            return False, None, f"Value must be one of: {', '.join(prop_def['enum'])}"

    return True, parsed_val, None


def prompt_property(prop_name, prop_def, is_required):
    """Prompt the user for a single property and return the validated value."""
    prop_type = prop_def.get("type", "string")
    description = prop_def.get("description", "")
    default = prop_def.get("default")
    enum = prop_def.get("enum")
    
    # Compile prompt instruction label
    info = []
    if is_required:
        info.append("required")
    if prop_type:
        info.append(prop_type)
    if default is not None:
        info.append(f"default: {default}")
        
    info_str = f" ({', '.join(info)})"
    
    print(f"\n{COLOR_BOLD}{prop_name}{COLOR_END}{COLOR_BLUE}{info_str}{COLOR_END}")
    if description:
        print(f"  {description}")
    if enum:
        print(f"  Choices: {', '.join(enum)}")

    while True:
        try:
            user_input = input(f"  > ").strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{COLOR_WARNING}Interaction cancelled.{COLOR_END}", file=sys.stderr)
            sys.exit(1)
            
        success, parsed_val, error = validate_input(user_input, prop_name, prop_def, is_required)
        if success:
            return parsed_val
        else:
            print(f"  {COLOR_FAIL}✖ Invalid input: {error}{COLOR_END}")


def collect_schema_data(schema):
    """Walk through the schema properties and collect user input."""
    title = schema.get("title", "Data Collection")
    description = schema.get("description", "")
    
    print(f"\n{COLOR_BOLD}{title}{COLOR_END}")
    if description:
        print(f"{COLOR_BLUE}{description}{COLOR_END}")
    print("=" * len(title))

    properties = schema.get("properties", {})
    required_list = schema.get("required", [])
    
    result = {}
    
    for prop_name, prop_def in properties.items():
        is_required = prop_name in required_list
        val = prompt_property(prop_name, prop_def, is_required)
        if val is not None:
            result[prop_name] = val
            
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Build an interactive console questionnaire from a JSON Schema draft-07 file."
    )
    parser.add_argument(
        "schema_file",
        nargs="?",
        help="Path to the input JSON Schema file. If omitted, runs a built-in interactive demo schema."
    )
    parser.add_argument(
        "-o", "--output",
        help="Path to write the collected JSON output. If omitted, prints output to stdout."
    )
    parser.add_argument(
        "--no-banner",
        action="store_true",
        help="Suppress the CLI graphical banner."
    )

    args = parser.parse_args()

    if not args.no_banner:
        print_banner()

    # Load JSON Schema
    if args.schema_file:
        try:
            with open(args.schema_file, "r", encoding="utf-8") as f:
                schema = json.load(f)
        except Exception as e:
            print(f"{COLOR_FAIL}Error loading JSON Schema file '{args.schema_file}': {e}{COLOR_END}", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"{COLOR_WARNING}No JSON Schema file specified. Running demonstration schema mode.{COLOR_END}\n", file=sys.stderr)
        schema = DEFAULT_SCHEMA

    # Run collection
    collected_data = collect_schema_data(schema)

    # Output result
    json_output = json.dumps(collected_data, indent=2)
    
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(json_output)
            print(f"\n{COLOR_GREEN}Success! Data saved to '{args.output}'{COLOR_END}", file=sys.stderr)
        except Exception as e:
            print(f"\n{COLOR_FAIL}Error saving data file '{args.output}': {e}{COLOR_END}", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"\n{COLOR_GREEN}Collected JSON Data Output:{COLOR_END}")
        print(json_output)


if __name__ == "__main__":
    main()
