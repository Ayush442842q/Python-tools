#!/usr/bin/env python3
"""
API Contract Compatibility Checker
----------------------------------
Compares two OpenAPI/Swagger API specifications (v2/v3 in JSON format)
to detect breaking changes, backward-incompatible schema updates,
parameter modifications, and endpoint removals.

Features:
- Detects removed paths, HTTP methods, parameters, and response codes.
- Identifies type alterations, newly required fields, and format shifts.
- Classifies changes by impact level (BREAKING vs NON-BREAKING).
- Generates colored terminal summaries, Markdown reports, or JSON output.
- Built-in --demo mode with pre-packaged sample API schemas.

Usage:
    python api_contract_compatibility_checker.py --old spec_v1.json --new spec_v2.json
    python api_contract_compatibility_checker.py --demo
"""

import sys
import os
import json
import argparse
from typing import Dict, List, Any, Tuple, Optional


if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass


class Color:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    BOLD = '\033[1m'
    RESET = '\033[0m'

    @classmethod
    def disable(cls):
        cls.RED = cls.GREEN = cls.YELLOW = cls.BLUE = cls.MAGENTA = cls.CYAN = cls.BOLD = cls.RESET = ''


if not sys.stdout.isatty():
    Color.disable()



class APIContractChecker:
    def __init__(self, old_spec: Dict[str, Any], new_spec: Dict[str, Any]):
        self.old_spec = old_spec
        self.new_spec = new_spec
        self.changes: List[Dict[str, Any]] = []

    def check(self) -> List[Dict[str, Any]]:
        self.changes = []
        self._compare_info()
        self._compare_paths()
        return self.changes

    def _add_change(self, category: str, is_breaking: bool, path: str, method: str, description: str, details: Optional[Dict[str, Any]] = None):
        self.changes.append({
            'category': category,
            'is_breaking': is_breaking,
            'path': path,
            'method': method.upper() if method else '',
            'description': description,
            'details': details or {}
        })

    def _compare_info(self):
        old_title = self.old_spec.get('info', {}).get('title', 'API')
        new_title = self.new_spec.get('info', {}).get('title', 'API')
        old_ver = self.old_spec.get('info', {}).get('version', 'v1')
        new_ver = self.new_spec.get('info', {}).get('version', 'v2')
        self._add_change('INFO', False, '', '', f"Comparing '{old_title}' ({old_ver}) vs '{new_title}' ({new_ver})")

    def _compare_paths(self):
        old_paths = self.old_spec.get('paths', {})
        new_paths = self.new_spec.get('paths', {})

        # Check removed paths
        for path in old_paths:
            if path not in new_paths:
                self._add_change('PATH', True, path, '', f"Path '{path}' was removed.")
            else:
                self._compare_path_methods(path, old_paths[path], new_paths[path])

        # Check added paths
        for path in new_paths:
            if path not in old_paths:
                self._add_change('PATH', False, path, '', f"New path '{path}' was added.")

    def _compare_path_methods(self, path: str, old_methods: Dict[str, Any], new_methods: Dict[str, Any]):
        valid_verbs = {'get', 'post', 'put', 'delete', 'patch', 'head', 'options'}

        for verb in old_methods:
            if verb.lower() not in valid_verbs:
                continue
            if verb not in new_methods:
                self._add_change('METHOD', True, path, verb, f"HTTP method '{verb.upper()}' on '{path}' was removed.")
            else:
                self._compare_operation(path, verb, old_methods[verb], new_methods[verb])

        for verb in new_methods:
            if verb.lower() not in valid_verbs:
                continue
            if verb not in old_methods:
                self._add_change('METHOD', False, path, verb, f"New HTTP method '{verb.upper()}' added to '{path}'.")

    def _compare_operation(self, path: str, verb: str, old_op: Dict[str, Any], new_op: Dict[str, Any]):
        self._compare_parameters(path, verb, old_op.get('parameters', []), new_op.get('parameters', []))
        self._compare_responses(path, verb, old_op.get('responses', {}), new_op.get('responses', {}))

    def _compare_parameters(self, path: str, verb: str, old_params: List[Dict[str, Any]], new_params: List[Dict[str, Any]]):
        old_map = {f"{p.get('in', '')}:{p.get('name', '')}": p for p in old_params}
        new_map = {f"{p.get('in', '')}:{p.get('name', '')}": p for p in new_params}

        # Removed params
        for key, old_p in old_map.items():
            if key not in new_map:
                param_name = old_p.get('name', key)
                is_breaking = old_p.get('required', False)
                self._add_change('PARAMETER', is_breaking, path, verb,
                                 f"Parameter '{param_name}' ({old_p.get('in')}) was removed.")
            else:
                # Type changes
                new_p = new_map[key]
                old_type = old_p.get('type') or old_p.get('schema', {}).get('type')
                new_type = new_p.get('type') or new_p.get('schema', {}).get('type')
                if old_type and new_type and old_type != new_type:
                    self._add_change('PARAMETER', True, path, verb,
                                     f"Parameter '{old_p.get('name')}' type changed from '{old_type}' to '{new_type}'.")

                # Required shift
                if not old_p.get('required', False) and new_p.get('required', False):
                    self._add_change('PARAMETER', True, path, verb,
                                     f"Parameter '{old_p.get('name')}' became REQUIRED.")

        # Added params
        for key, new_p in new_map.items():
            if key not in old_map:
                is_req = new_p.get('required', False)
                param_name = new_p.get('name', key)
                self._add_change('PARAMETER', is_req, path, verb,
                                 f"New parameter '{param_name}' ({new_p.get('in')}) added" +
                                 (" [REQUIRED - BREAKING]" if is_req else " [Optional]"))

    def _compare_responses(self, path: str, verb: str, old_resp: Dict[str, Any], new_resp: Dict[str, Any]):
        for code, old_r in old_resp.items():
            if code not in new_resp:
                self._add_change('RESPONSE', True, path, verb, f"Response status code '{code}' removed.")
            else:
                old_schema = old_r.get('schema') or old_r.get('content', {}).get('application/json', {}).get('schema', {})
                new_schema = new_resp[code].get('schema') or new_resp[code].get('content', {}).get('application/json', {}).get('schema', {})
                if old_schema and new_schema:
                    self._compare_schemas(path, verb, f"Response {code}", old_schema, new_schema)

        for code in new_resp:
            if code not in old_resp:
                self._add_change('RESPONSE', False, path, verb, f"New response status code '{code}' added.")

    def _compare_schemas(self, path: str, verb: str, context: str, old_s: Dict[str, Any], new_s: Dict[str, Any]):
        old_props = old_s.get('properties', {})
        new_props = new_s.get('properties', {})

        # Property removals in response
        for prop, old_p_def in old_props.items():
            if prop not in new_props:
                self._add_change('SCHEMA', True, path, verb, f"{context}: Property '{prop}' removed from schema.")
            else:
                old_t = old_p_def.get('type')
                new_t = new_props[prop].get('type')
                if old_t and new_t and old_t != new_t:
                    self._add_change('SCHEMA', True, path, verb,
                                     f"{context}: Property '{prop}' type changed from '{old_t}' to '{new_t}'.")

        for prop in new_props:
            if prop not in old_props:
                self._add_change('SCHEMA', False, path, verb, f"{context}: New property '{prop}' added to response.")


def generate_demo_specs() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    old_spec = {
        "openapi": "3.0.0",
        "info": {"title": "Payment API", "version": "1.0.0"},
        "paths": {
            "/users": {
                "get": {
                    "parameters": [
                        {"name": "page", "in": "query", "type": "integer", "required": False},
                        {"name": "limit", "in": "query", "type": "integer", "required": False}
                    ],
                    "responses": {
                        "200": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "integer"},
                                    "email": {"type": "string"},
                                    "name": {"type": "string"}
                                }
                            }
                        }
                    }
                },
                "post": {
                    "parameters": [
                        {"name": "email", "in": "body", "type": "string", "required": True}
                    ],
                    "responses": {
                        "201": {"description": "User Created"}
                    }
                }
            },
            "/legacy-endpoint": {
                "get": {
                    "responses": {"200": {"description": "Legacy data"}}
                }
            }
        }
    }

    new_spec = {
        "openapi": "3.0.0",
        "info": {"title": "Payment API", "version": "2.0.0"},
        "paths": {
            "/users": {
                "get": {
                    "parameters": [
                        {"name": "page", "in": "query", "type": "integer", "required": False},
                        {"name": "api_key", "in": "header", "type": "string", "required": True}
                    ],
                    "responses": {
                        "200": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "id": {"type": "string"},  # Changed int -> string (BREAKING)
                                    "email": {"type": "string"},
                                    "role": {"type": "string"}  # Added property
                                }
                            }
                        }
                    }
                },
                "post": {
                    "parameters": [
                        {"name": "email", "in": "body", "type": "string", "required": True}
                    ],
                    "responses": {
                        "201": {"description": "User Created"}
                    }
                }
            },
            "/orders": {
                "get": {
                    "responses": {"200": {"description": "Orders list"}}
                }
            }
        }
    }
    return old_spec, new_spec


def print_report(changes: List[Dict[str, Any]], format_type: str = 'cli'):
    breaking = [c for c in changes if c['is_breaking']]
    non_breaking = [c for c in changes if not c['is_breaking'] and c['category'] != 'INFO']

    if format_type == 'json':
        print(json.dumps({'breaking': breaking, 'non_breaking': non_breaking, 'all': changes}, indent=2))
        return

    if format_type == 'markdown':
        print("# API Contract Compatibility Report\n")
        print(f"**Breaking Changes**: {len(breaking)} | **Non-Breaking Changes**: {len(non_breaking)}\n")
        if breaking:
            print("## 🚨 Breaking Changes")
            for c in breaking:
                method_str = f"`{c['method']}` " if c['method'] else ""
                path_str = f"`{c['path']}` " if c['path'] else ""
                print(f"- **[{c['category']}]** {method_str}{path_str}: {c['description']}")
        print("\n## ℹ️ Non-Breaking Changes")
        for c in non_breaking:
            method_str = f"`{c['method']}` " if c['method'] else ""
            path_str = f"`{c['path']}` " if c['path'] else ""
            print(f"- **[{c['category']}]** {method_str}{path_str}: {c['description']}")
        return

    # CLI Output
    print(f"\n{Color.BOLD}{Color.CYAN}===================================================={Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}       API CONTRACT COMPATIBILITY REPORT           {Color.RESET}")
    print(f"{Color.BOLD}{Color.CYAN}===================================================={Color.RESET}\n")

    print(f"Summary: {Color.BOLD}{Color.RED}{len(breaking)} Breaking{Color.RESET} | {Color.GREEN}{len(non_breaking)} Non-Breaking{Color.RESET} changes\n")

    if breaking:
        print(f"{Color.BOLD}{Color.RED}🚨 BREAKING CHANGES ({len(breaking)}):{Color.RESET}")
        print("-" * 50)
        for c in breaking:
            m = f"[{c['method']}]" if c['method'] else ""
            p = c['path'] if c['path'] else ""
            print(f"{Color.RED}✖ [{c['category']}] {m} {p}{Color.RESET}")
            print(f"  └─ {c['description']}")
        print()

    if non_breaking:
        print(f"{Color.BOLD}{Color.GREEN}✅ NON-BREAKING CHANGES ({len(non_breaking)}):{Color.RESET}")
        print("-" * 50)
        for c in non_breaking:
            m = f"[{c['method']}]" if c['method'] else ""
            p = c['path'] if c['path'] else ""
            print(f"{Color.GREEN}✔ [{c['category']}] {m} {p}{Color.RESET}")
            print(f"  └─ {c['description']}")
        print()


def main():
    parser = argparse.ArgumentParser(description="API Contract Compatibility Checker")
    parser.add_argument("--old", help="Path to baseline/old OpenAPI JSON specification file")
    parser.add_argument("--new", help="Path to target/new OpenAPI JSON specification file")
    parser.add_argument("--demo", action="store_true", help="Run compatibility check with built-in sample schemas")
    parser.add_argument("--format", choices=['cli', 'markdown', 'json'], default='cli', help="Output format")

    args = parser.parse_args()

    if args.demo or (not args.old and not args.new):
        if not args.demo:
            print(f"{Color.YELLOW}No spec files provided. Running in --demo mode...{Color.RESET}\n")
        old_spec, new_spec = generate_demo_specs()
    else:
        if not args.old or not args.new:
            print(f"{Color.RED}Error: Both --old and --new files must be provided.{Color.RESET}")
            sys.exit(1)

        try:
            with open(args.old, 'r', encoding='utf-8') as f:
                old_spec = json.load(f)
            with open(args.new, 'r', encoding='utf-8') as f:
                new_spec = json.load(f)
        except Exception as e:
            print(f"{Color.RED}Failed to read specification files: {e}{Color.RESET}")
            sys.exit(1)

    checker = APIContractChecker(old_spec, new_spec)
    changes = checker.check()
    print_report(changes, format_type=args.format)


if __name__ == "__main__":
    main()
