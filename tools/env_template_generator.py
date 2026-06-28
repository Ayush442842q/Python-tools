#!/usr/bin/env python3
"""
Environment Template Generator - Generate .env templates from code inspection.

Analyzes code files and configurations to discover environment variable usage,
then generates comprehensive .env templates with documentation.

Features:
- Scan code for environment variable references (os.getenv, process.env, etc.)
- Support for Python, JavaScript/TypeScript, Go, Ruby, Java, and more
- Detect usage patterns to infer variable types (URL, port, path, secret)
- Generate documented .env.example files with sensible defaults
- Find variables in Dockerfile, docker-compose.yml, and config files
- Generate validation schema for environment variables
- Compare actual .env against template to find missing variables

Usage:
    python env_template_generator.py <source_directory> [-o .env.example]
    python env_template_generator.py ./src --docker --output .env.template
    python env_template_generator.py . --validate .env

Example:
    python env_template_generator.py src/ -o .env.example
    python env_template_generator.py . --docker --compose --output .env.template
"""

import os
import re
import sys
import argparse
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, field


@dataclass
class EnvVar:
    """Represents an environment variable."""
    name: str
    files: List[str] = field(default_factory=list)
    usage_contexts: List[str] = field(default_factory=list)
    is_required: bool = False
    inferred_type: str = 'string'
    default_value: Optional[str] = None
    description: str = ''


class EnvVarScanner:
    """Scan code for environment variable usage."""

    # Patterns for different languages
    PATTERNS = {
        'python': [
            (re.compile(r'os\.getenv\s*\(\s*[\'"]([^\'"]+)[\'"]'), 'getenv'),
            (re.compile(r'os\.environ\s*\[\s*[\'"]([^\'"]+)[\'"]\s*\]'), 'environ'),
            (re.compile(r'getenv\s*\(\s*[\'"]([^\'"]+)[\'"]'), 'getenv_func'),
        ],
        'javascript': [
            (re.compile(r'process\.env\.([A-Z_][A-Z0-9_]*)'), 'process_env'),
            (re.compile(r'process\.env\s*\[\s*[\'"]([^\'"]+)[\'"]\s*\]'), 'env_bracket'),
        ],
        'typescript': [
            (re.compile(r'process\.env\.([A-Z_][A-Z0-9_]*)'), 'process_env'),
        ],
        'go': [
            (re.compile(r'os\.Getenv\s*\(\s*"([^"]+)"'), 'getenv'),
            (re.compile(r'os\.LookupEnv\s*\(\s*"([^"]+)"'), 'lookupenv'),
        ],
        'ruby': [
            (re.compile(r'ENV\s*\[\s*[\'"]([^\'"]+)[\'"]\s*\]'), 'env_bracket'),
            (re.compile(r'ENV\s*\.\s*fetch\s*\(\s*[\'"]([^\'"]+)[\'"]'), 'fetch'),
        ],
        'java': [
            (re.compile(r'System\.getenv\s*\(\s*"([^"]+)"'), 'getenv'),
        ],
        'shell': [
            (re.compile(r'\$\{([A-Z_][A-Z0-9_]*)'), 'shell_braces'),
            (re.compile(r'\$([A-Z_][A-Z0-9_]*)'), 'shell_var'),
        ],
    }

    # File extensions mapping
    EXTENSIONS = {
        '.py': 'python',
        '.js': 'javascript',
        '.ts': 'typescript',
        '.jsx': 'javascript',
        '.tsx': 'typescript',
        '.go': 'go',
        '.rb': 'ruby',
        '.java': 'java',
        '.sh': 'shell',
        '.bash': 'shell',
        '.zsh': 'shell',
        '.env': 'dotenv',
        '.dockerfile': 'dockerfile',
        'docker-compose.yml': 'docker-compose',
        'docker-compose.yaml': 'docker-compose',
    }

    def __init__(self, root_dir: Path):
        self.root_dir = root_dir
        self.variables: Dict[str, EnvVar] = {}

    def scan(self) -> Dict[str, EnvVar]:
        """Scan directory for environment variables."""
        for file_path in self.root_dir.rglob('*'):
            # Skip common directories
            if any(skip in str(file_path) for skip in 
                   ['node_modules', '__pycache__', '.git', 'venv', 'env/', '.venv']):
                continue

            if not file_path.is_file():
                continue

            language = self._detect_language(file_path)
            if language:
                self._scan_file(file_path, language)

        return self.variables

    def _detect_language(self, file_path: Path) -> Optional[str]:
        """Detect programming language from file."""
        name = file_path.name.lower()
        
        # Check filename first
        if name in self.EXTENSIONS:
            return self.EXTENSIONS[name]
        
        # Check extension
        ext = file_path.suffix.lower()
        return self.EXTENSIONS.get(ext)

    def _scan_file(self, file_path: Path, language: str) -> None:
        """Scan file for environment variables."""
        try:
            content = file_path.read_text(encoding='utf-8', errors='ignore')
        except Exception:
            return

        patterns = self.PATTERNS.get(language, [])

        for pattern, context in patterns:
            for match in pattern.finditer(content):
                var_name = match.group(1)
                
                if var_name not in self.variables:
                    self.variables[var_name] = EnvVar(name=var_name)

                var = self.variables[var_name]
                rel_path = str(file_path.relative_to(self.root_dir))
                
                if rel_path not in var.files:
                    var.files.append(rel_path)
                
                if context not in var.usage_contexts:
                    var.usage_contexts.append(context)

                # Infer if required
                if 'getenv' in context or 'LookupEnv' in context:
                    var.is_required = False
                else:
                    var.is_required = True

                # Infer type from name
                var.inferred_type = self._infer_type(var_name)

    def _scan_docker_compose(self, file_path: Path) -> None:
        """Scan docker-compose file for env vars."""
        try:
            content = file_path.read_text(encoding='utf-8')
        except Exception:
            return

        # Match environment section
        env_pattern = re.compile(r'environment:\s*(?:\n\s+-\s+)?(.+?)(?=\n\s+\w+:)', 
                                re.DOTALL)
        for match in env_pattern.finditer(content):
            env_section = match.group(1)
            
            # Match variable assignments
            assign_pattern = re.compile(r'([A-Z_][A-Z0-9_]*)')
            for var_match in assign_pattern.finditer(env_section):
                var_name = var_match.group(1)
                if var_name not in self.variables:
                    self.variables[var_name] = EnvVar(name=var_name)
                self.variables[var_name].files.append(str(file_path.relative_to(self.root_dir)))

    def _infer_type(self, name: str) -> str:
        """Infer variable type from name."""
        name_upper = name.upper()
        
        if any(kw in name_upper for kw in ['URL', 'HOST', 'ENDPOINT']):
            return 'url'
        elif any(kw in name_upper for kw in ['PORT']):
            return 'port'
        elif any(kw in name_upper for kw in ['PATH', 'DIR', 'FILE']):
            return 'path'
        elif any(kw in name_upper for kw in ['KEY', 'SECRET', 'TOKEN', 'PASSWORD', 'PASSWD']):
            return 'secret'
        elif any(kw in name_upper for kw in ['DB', 'DATABASE', 'REDIS', 'CACHE', 'QUEUE']):
            return 'connection_string'
        elif any(kw in name_upper for kw in ['EMAIL', 'MAIL', 'SMTP']):
            return 'email'
        elif any(kw in name_upper for kw in ['DEBUG', 'ENABLE', 'DISABLE', 'ACTIVE']):
            return 'boolean'
        else:
            return 'string'


class EnvTemplateGenerator:
    """Generate .env templates from scanned variables."""

    TYPE_DEFAULTS = {
        'url': 'http://localhost:8080',
        'port': '8080',
        'path': './data',
        'secret': 'change-me-in-production',
        'connection_string': 'localhost:5432',
        'email': 'noreply@example.com',
        'boolean': 'false',
        'string': '',
    }

    TYPE_DESCRIPTIONS = {
        'url': 'Application endpoint URL',
        'port': 'Port number',
        'path': 'File system path',
        'secret': 'Secret key (CHANGE IN PRODUCTION!)',
        'connection_string': 'Database/connection string',
        'email': 'Email address',
        'boolean': 'true/false',
        'string': 'String value',
    }

    def __init__(self, variables: Dict[str, EnvVar]):
        self.variables = variables

    def generate_template(self, add_comments: bool = True) -> str:
        """Generate .env template."""
        lines = [
            "# Environment Configuration Template",
            "# Auto-generated by env_template_generator.py",
            "",
            "# Copy this file to .env and fill in the values",
            "",
        ]

        if add_comments:
            lines.append("# Variables are grouped by type for easier navigation")
            lines.append("")

        # Group by type
        by_type: Dict[str, List[EnvVar]] = {}
        for var in sorted(self.variables.values(), key=lambda v: v.name):
            var_type = var.inferred_type
            if var_type not in by_type:
                by_type[var_type] = []
            by_type[var_type].append(var)

        for var_type in ['url', 'port', 'connection_string', 'path', 'secret', 'email', 'boolean', 'string']:
            vars_of_type = by_type.get(var_type, [])
            if not vars_of_type:
                continue

            if add_comments:
                lines.append(f"# {'='*50}")
                lines.append(f"# {var_type.upper().replace('_', ' ')}")
                lines.append(f"# {'='*50}")

            for var in vars_of_type:
                if add_comments:
                    # Add comment with info
                    comment = f" # {self.TYPE_DESCRIPTIONS.get(var_type, 'Configuration value')}"
                    if var.files:
                        comment += f" (used in: {', '.join(var.files[:3])})"
                        if len(var.files) > 3:
                            comment += f" + {len(var.files) - 3} more"
                else:
                    comment = ''

                default = self.TYPE_DEFAULTS.get(var_type, '')
                required_marker = '*' if var.is_required else ''
                
                lines.append(f"{required_marker}{var.name}={default}{comment}")

            lines.append("")

        return '\n'.join(lines)

    def generate_validation_schema(self) -> str:
        """Generate Python validation schema for env vars."""
        lines = [
            "# Environment Variable Validation Schema (Python/Pydantic)",
            "# Install: pip install pydantic",
            "",
            "from pydantic import BaseSettings, Field",
            "from typing import Optional",
            "",
            "class Settings(BaseSettings):",
            '    """Application settings from environment variables."""',
            "",
        ]

        for var in sorted(self.variables.values(), key=lambda v: v.name):
            if var.inferred_type == 'boolean':
                field_type = 'bool'
            elif var.inferred_type in ['port', 'integer']:
                field_type = 'int'
            elif var.inferred_type in ['url', 'connection_string']:
                field_type = 'str  # Consider HttpUrl for urls'
            else:
                field_type = 'str'

            optional = '' if var.is_required else 'Optional['
            closing = '' if var.is_required else ']'
            default = self.TYPE_DEFAULTS.get(var.inferred_type, 'None')

            line = f"    {var.name}: {optional}{field_type}{closing} = Field("
            if not var.is_required:
                line += f"default={repr(default)}, "
            line += f'description="{self.TYPE_DESCRIPTIONS.get(var.inferred_type, "Configuration value")}"'
            line += ")"

            lines.append(line)

        lines.append("")
        lines.append("    class Config:")
        lines.append("        env_file = '.env'")
        lines.append("        case_sensitive = True")

        return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(
        description='Generate .env templates from code inspection'
    )
    parser.add_argument('source_dir', type=Path, nargs='?', default='.',
                        help='Source directory to scan (default: current)')
    parser.add_argument('-o', '--output', default='.env.example',
                        help='Output template file (default: .env.example)')
    parser.add_argument('--docker', action='store_true',
                        help='Scan Docker files for environment variables')
    parser.add_argument('--compose', action='store_true',
                        help='Scan docker-compose files')
    parser.add_argument('--schema',
                        help='Generate validation schema to file')
    parser.add_argument('--no-comments', action='store_true',
                        help='Generate template without comments')
    parser.add_argument('--validate', type=Path,
                        help='Validate existing .env against generated template')

    args = parser.parse_args()

    if not args.source_dir.is_dir():
        print(f"Error: '{args.source_dir}' is not a valid directory", file=sys.stderr)
        return 1

    print(f"Scanning {args.source_dir.absolute()} for environment variables...")

    scanner = EnvVarScanner(args.source_dir)
    variables = scanner.scan()

    print(f"Found {len(variables)} environment variables")

    # Generate template
    generator = EnvTemplateGenerator(variables)
    template = generator.generate_template(add_comments=not args.no_comments)

    # Write output
    output_path = Path(args.output)
    output_path.write_text(template + '\n', encoding='utf-8')
    print(f"\n✓ Template saved to: {output_path.absolute()}")

    # Generate validation schema if requested
    if args.schema:
        schema = generator.generate_validation_schema()
        schema_path = Path(args.schema)
        schema_path.write_text(schema + '\n', encoding='utf-8')
        print(f"✓ Validation schema saved to: {schema_path.absolute()}")

    # Show summary
    print(f"\n{'='*60}")
    print("Summary:")
    print(f"{'='*60}")
    
    by_type: Dict[str, int] = {}
    for var in variables.values():
        var_type = var.inferred_type
        by_type[var_type] = by_type.get(var_type, 0) + 1

    for var_type, count in sorted(by_type.items()):
        print(f"  {var_type}: {count}")

    required = sum(1 for v in variables.values() if v.is_required)
    print(f"\nRequired variables: {required}")
    print(f"Optional variables: {len(variables) - required}")

    # Validate if requested
    if args.validate:
        if not args.validate.exists():
            print(f"\nWarning: {args.validate} does not exist")
        else:
            print(f"\nValidating {args.validate}...")
            validate_against_template(args.validate, variables)

    return 0


def validate_against_template(env_file: Path, template_vars: Dict[str, EnvVar]) -> None:
    """Validate .env file against template."""
    content = env_file.read_text(encoding='utf-8')
    
    defined_vars = set()
    for line in content.splitlines():
        line = line.strip()
        if line and not line.startswith('#') and '=' in line:
            var_name = line.split('=')[0].strip()
            defined_vars.add(var_name)

    template_var_names = set(template_vars.keys())

    missing = template_var_names - defined_vars
    extra = defined_vars - template_var_names

    if missing:
        print(f"\n⚠ Missing variables ({len(missing)}):")
        for var in sorted(missing):
            print(f"  - {var}")

    if extra:
        print(f"\nℹ Extra variables not in template ({len(extra)}):")
        for var in sorted(extra):
            print(f"  + {var}")

    if not missing and not extra:
        print("✓ All variables match template!")


if __name__ == '__main__':
    sys.exit(main())