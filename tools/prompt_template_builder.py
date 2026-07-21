#!/usr/bin/env python3
"""
LLM Prompt Template Builder & Variable Interpolator
A CLI utility to manage, inspect, validate, and render LLM prompt templates with placeholder variable substitution.

Features:
- Placeholders supported: {{variable_name}} or {{variable_name:default_value}}.
- Extract and list all placeholder variables from a prompt template file.
- Generate JSON schema of required template variables for API payloads.
- Interpolate prompt templates using CLI arguments (--var key=value) or JSON variable files.
"""

import sys
import os
import re
import json
import argparse
from typing import Dict, List, Tuple, Any

# Configure stdout/stderr encoding to UTF-8
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        try:
            stream.reconfigure(encoding='utf-8')
        except Exception:
            pass


VARIABLE_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)(?::([^}]*))?\s*\}\}")


def extract_variables(template: str) -> List[Tuple[str, str]]:
    """
    Extracts unique variables and their optional default values from template text.
    Returns list of tuples (var_name, default_value).
    """
    vars_found: Dict[str, str] = {}
    for match in VARIABLE_PATTERN.finditer(template):
        var_name = match.group(1).strip()
        default_val = match.group(2).strip() if match.group(2) is not None else ""
        if var_name not in vars_found:
            vars_found[var_name] = default_val
    return list(vars_found.items())


def render_template(template: str, variables: Dict[str, Any], strict: bool = False) -> Tuple[str, List[str]]:
    """
    Renders template replacing placeholders with variable values.
    Returns (rendered_string, list_of_missing_variables).
    """
    missing_vars: List[str] = []

    def replace_var(match: re.Match) -> str:
        var_name = match.group(1).strip()
        default_val = match.group(2).strip() if match.group(2) is not None else None

        if var_name in variables:
            return str(variables[var_name])
        elif default_val is not None:
            return default_val
        else:
            missing_vars.append(var_name)
            return f"{{{{{var_name}}}}}" if not strict else ""

    rendered = VARIABLE_PATTERN.sub(replace_var, template)
    return rendered, list(set(missing_vars))


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage, inspect, and render LLM prompt templates.")
    parser.add_argument("template", help="Path to prompt template file or template string.")
    parser.add_argument("--list-vars", action="store_true", help="List all variables and default values in template.")
    parser.add_argument("--schema", action="store_true", help="Generate JSON Schema for template variables.")
    parser.add_argument("--var", action="append", help="Variable substitution in key=value format (can be specified multiple times).")
    parser.add_argument("--vars-file", type=str, help="Path to JSON file containing variable values.")
    parser.add_argument("-o", "--output", type=str, help="Output file path for rendered prompt.")

    args = parser.parse_args()

    if os.path.exists(args.template):
        with open(args.template, "r", encoding="utf-8") as f:
            template_text = f.read()
    else:
        template_text = args.template

    if args.list_vars:
        vars_list = extract_variables(template_text)
        print("Template Variables:")
        for name, default in vars_list:
            def_info = f" (default: '{default}')" if default else " (required)"
            print(f"  - {name}{def_info}")
        sys.exit(0)

    if args.schema:
        vars_list = extract_variables(template_text)
        properties = {}
        required = []
        for name, default in vars_list:
            properties[name] = {
                "type": "string",
                "description": f"Variable {name}",
            }
            if default:
                properties[name]["default"] = default
            else:
                required.append(name)

        schema = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "properties": properties,
            "required": required,
        }
        print(json.dumps(schema, indent=2))
        sys.exit(0)

    # Collect variables
    var_values: Dict[str, Any] = {}

    if args.vars_file and os.path.exists(args.vars_file):
        with open(args.vars_file, "r", encoding="utf-8") as f:
            var_values.update(json.load(f))

    if args.var:
        for v in args.var:
            if "=" in v:
                k, val = v.split("=", 1)
                var_values[k.strip()] = val.strip()

    rendered, missing = render_template(template_text, var_values)

    if missing:
        print(f"Warning: Missing required variables without defaults: {', '.join(missing)}", file=sys.stderr)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(rendered + "\n")
        print(f"Successfully rendered prompt to {args.output}")
    else:
        print(rendered)


if __name__ == "__main__":
    main()
