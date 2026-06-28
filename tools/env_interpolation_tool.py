#!/usr/bin/env python3
"""
Environment Variable Interpolation Tool - Handle .env file variable references.

This tool processes .env files and resolves variable interpolation/ References.

Features:
- Resolves ${VAR} and $VAR syntax in .env values
- Supports nested variable references
- Handles default values: ${VAR:-default}
- Detects circular references
- Validates all referenced variables exist
- Exports resolved environment to various formats

Usage:
    python env_interpolation_tool.py <.env file> [-o output] [--format json|shell|env]

Example:
    python env_interpolation_tool.py .env
    python env_interpolation_tool.py .env.development --format json -o config.json
"""

import os
import re
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple


class EnvInterpolator:
    """Process .env files with variable interpolation."""

    # Patterns for variable references
    VAR_BRACES = re.compile(r'\$\{([^}:]+)(?::-([^}]*))?\}')  # ${VAR} or ${VAR:-default}
    VAR_SIMPLE = re.compile(r'\$([A-Za-z_][A-Za-z0-9_]*)')  # $VAR

    def __init__(self, env_file: Path):
        self.env_file = env_file
        self.raw_vars: Dict[str, str] = {}
        self.resolved_vars: Dict[str, str] = {}
        self.errors: List[str] = []
        self.warnings: List[str] = []

    def load(self) -> bool:
        """Load and parse the .env file."""
        if not self.env_file.exists():
            self.errors.append(f"File not found: {self.env_file}")
            return False

        try:
            content = self.env_file.read_text(encoding='utf-8')
        except Exception as e:
            self.errors.append(f"Failed to read file: {e}")
            return False

        for line_num, line in enumerate(content.splitlines(), 1):
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith('#'):
                continue

            # Parse KEY=VALUE
            if '=' not in line:
                self.warnings.append(f"Line {line_num}: Skipping invalid format: {line}")
                continue

            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip()

            # Remove quotes if present
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]

            if not key:
                self.warnings.append(f"Line {line_num}: Empty key")
                continue

            self.raw_vars[key] = value

        return True

    def resolve(self) -> bool:
        """Resolve all variable references."""
        # Start with current environment
        self.resolved_vars = dict(os.environ)
        self.resolved_vars.update(self.raw_vars)

        # Resolve variables iteratively
        max_iterations = 100
        iteration = 0
        changed = True

        while changed and iteration < max_iterations:
            changed = False
            iteration += 1

            for key, value in list(self.raw_vars.items()):
                resolved = self._resolve_value(value, key, set())
                if resolved is not None and resolved != self.resolved_vars.get(key):
                    self.resolved_vars[key] = resolved
                    changed = True

        if iteration >= max_iterations:
            self.errors.append("Maximum iterations reached - possible circular reference")
            return False

        # Check for unresolved variables
        for key, value in self.raw_vars.items():
            unresolved = self._find_unresolved(value, self.resolved_vars)
            if unresolved:
                self.errors.append(f"Variable '{key}' references undefined: {unresolved}")

        return len(self.errors) == 0

    def _resolve_value(self, value: str, current_key: str, visiting: Set[str]) -> Optional[str]:
        """Resolve variable references in a value."""
        if current_key in visiting:
            self.errors.append(f"Circular reference detected for '{current_key}'")
            return None

        visiting = visiting | {current_key}

        def replace_braces(match):
            var_name = match.group(1)
            default = match.group(2)

            if var_name in self.resolved_vars:
                return self.resolved_vars[var_name]
            elif default is not None:
                return default
            else:
                return match.group(0)  # Keep unresolved

        def replace_simple(match):
            var_name = match.group(1)
            if var_name in self.resolved_vars:
                return self.resolved_vars[var_name]
            return match.group(0)

        # First resolve ${VAR} syntax
        result = self.VAR_BRACES.sub(replace_braces, value)
        # Then resolve $VAR syntax
        result = self.VAR_SIMPLE.sub(replace_simple, result)

        return result

    def _find_unresolved(self, value: str, resolved: Dict[str, str]) -> Optional[str]:
        """Find unresolved variable references."""
        # Check ${VAR} syntax
        for match in self.VAR_BRACES.finditer(value):
            var_name = match.group(1)
            default = match.group(2)
            if var_name not in resolved and default is None:
                return var_name

        # Check $VAR syntax
        for match in self.VAR_SIMPLE.finditer(value):
            var_name = match.group(1)
            if var_name not in resolved:
                return var_name

        return None

    def get_resolved(self) -> Dict[str, str]:
        """Get resolved environment variables."""
        return {k: v for k, v in self.resolved_vars.items() if k in self.raw_vars}

    def export_env(self) -> str:
        """Export as .env format."""
        lines = ["# Resolved environment variables", f"# Generated from: {self.env_file.name}"]
        for key, value in sorted(self.get_resolved().items()):
            # Quote values with spaces or special chars
            if ' ' in value or '=' in value or '"' in value:
                value = f'"{value}"'
            lines.append(f"{key}={value}")
        return '\n'.join(lines)

    def export_shell(self) -> str:
        """Export as shell export statements."""
        lines = ["#!/bin/bash", f"# Resolved environment from: {self.env_file.name}"]
        for key, value in sorted(self.get_resolved().items()):
            # Escape for shell
            value = value.replace('\\', '\\\\').replace('"', '\\"').replace('$', '\\$')
            lines.append(f'export {key}="{value}"')
        return '\n'.join(lines)

    def export_json(self) -> str:
        """Export as JSON."""
        import json
        resolved = self.get_resolved()
        return json.dumps(resolved, indent=2, sort_keys=True)

    def print_report(self) -> None:
        """Print a summary report."""
        print(f"\n{'='*60}")
        print(f"Environment Interpolation Report")
        print(f"{'='*60}")
        print(f"Source file: {self.env_file.absolute()}")
        print(f"Variables found: {len(self.raw_vars)}")
        print(f"Variables resolved: {len(self.get_resolved())}")

        if self.warnings:
            print(f"\nWarnings ({len(self.warnings)}):")
            for w in self.warnings[:5]:
                print(f"  ⚠ {w}")
            if len(self.warnings) > 5:
                print(f"  ... and {len(self.warnings) - 5} more")

        if self.errors:
            print(f"\nErrors ({len(self.errors)}):")
            for e in self.errors:
                print(f"  ✗ {e}")
            return

        print(f"\n✓ All variables resolved successfully")

        # Show resolved variables
        print(f"\nResolved Variables:")
        print(f"{'-'*60}")
        for key, value in sorted(self.get_resolved().items()):
            if len(value) > 50:
                value = value[:47] + '...'
            print(f"  {key}={value}")


def main():
    parser = argparse.ArgumentParser(
        description='Process .env files with variable interpolation'
    )
    parser.add_argument('env_file', type=Path,
                        help='.env file to process')
    parser.add_argument('-o', '--output',
                        help='Output file (default: stdout)')
    parser.add_argument('-f', '--format', choices=['env', 'shell', 'json'],
                        default='env', help='Output format (default: env)')
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='Suppress report output')

    args = parser.parse_args()

    interpolator = EnvInterpolator(args.env_file)

    if not interpolator.load():
        for error in interpolator.errors:
            print(f"Error: {error}", file=sys.stderr)
        return 1

    if not interpolator.resolve():
        interpolator.print_report()
        return 1

    if not args.quiet:
        interpolator.print_report()

    # Export
    if args.format == 'env':
        output = interpolator.export_env()
    elif args.format == 'shell':
        output = interpolator.export_shell()
    else:  # json
        output = interpolator.export_json()

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(output + '\n', encoding='utf-8')
        print(f"\nExported to: {output_path.absolute()}")
    else:
        print(f"\n{'='*60}")
        print("Resolved Output:")
        print(f"{'='*60}")
        print(output)

    return 0


if __name__ == '__main__':
    sys.exit(main())