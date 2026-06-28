#!/usr/bin/env python3
"""
Environment Variable Validator
Validate .env files against a schema, check for missing/unused variables,
and ensure proper formatting and security best practices.
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class EnvValidator:
    """Validates environment variable files against schema and best practices."""
    
    # Patterns for common secret formats
    SECRET_PATTERNS = {
        'aws_access_key': r'AKIA[0-9A-Z]{16}',
        'aws_secret_key': r'[0-9a-zA-Z/+]{40}',
        'github_token': r'gh[pousr]_[A-Za-z0-9_]{36,}',
        'gitlab_token': r'glpat-[A-Za-z0-9\-]{20,}',
        'slack_token': r'xox[baprs]-[0-9A-Za-z\-]+',
        'stripe_key': r'sk_live_[0-9a-zA-Z]{24,}',
        'stripe_restricted': r'rk_live_[0-9a-zA-Z]{24,}',
        'google_api': r'AIza[0-9A-Za-z\-_]{35}',
        'private_key': r'-----BEGIN (RSA |EC )?PRIVATE KEY-----',
        'jwt_secret': r'[A-Za-z0-9\-_]{20,}\.[A-Za-z0-9\-_]{20,}\.[A-Za-z0-9\-_]{20,}',
        'password_in_env': r'(?i)(password|passwd|pwd)\s*=\s*[^\s]+',
        'api_key_generic': r'(?i)api[_-]?key\s*=\s*[^\s]+',
    }
    
    # Recommended patterns for variable names
    VALID_NAME_PATTERN = re.compile(r'^[A-Z][A-Z0-9_]*$')
    
    def __init__(self, env_file: str, schema_file: Optional[str] = None):
        self.env_file = Path(env_file)
        self.schema_file = Path(schema_file) if schema_file else None
        self.env_vars: Dict[str, str] = {}
        self.schema: Dict[str, dict] = {}
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.info: List[str] = []
    
    def parse_env_file(self) -> bool:
        """Parse the .env file and extract variables."""
        if not self.env_file.exists():
            self.errors.append(f"Error: File not found: {self.env_file}")
            return False
        
        try:
            with open(self.env_file, 'r', encoding='utf-8') as f:
                line_num = 0
                for line in f:
                    line_num += 1
                    line = line.strip()
                    
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                    
                    # Parse KEY=VALUE
                    if '=' in line:
                        key, _, value = line.partition('=')
                        key = key.strip()
                        value = value.strip()
                        
                        # Remove quotes if present
                        if (value.startswith('"') and value.endswith('"')) or \
                           (value.startswith("'") and value.endswith("'")):
                            value = value[1:-1]
                        
                        self.env_vars[key] = value
                    else:
                        self.warnings.append(f"Line {line_num}: Invalid format (no '='): {line[:50]}")
            
            return True
        except Exception as e:
            self.errors.append(f"Error reading file: {e}")
            return False
    
    def parse_schema_file(self) -> bool:
        """Parse schema file (JSON format) defining required variables."""
        if not self.schema_file:
            return True
        
        if not self.schema_file.exists():
            self.errors.append(f"Error: Schema file not found: {self.schema_file}")
            return False
        
        try:
            import json
            with open(self.schema_file, 'r', encoding='utf-8') as f:
                self.schema = json.load(f)
            return True
        except json.JSONDecodeError as e:
            self.errors.append(f"Error: Invalid JSON in schema file: {e}")
            return False
        except Exception as e:
            self.errors.append(f"Error reading schema: {e}")
            return False
    
    def validate_naming_conventions(self) -> None:
        """Check that variable names follow conventions."""
        for key in self.env_vars:
            if not self.VALID_NAME_PATTERN.match(key):
                if key.islower() or key[0].islower():
                    self.warnings.append(f"Naming convention: '{key}' should be UPPERCASE")
    
    def validate_required_variables(self) -> None:
        """Check for missing required variables from schema."""
        if not self.schema:
            return
        
        for var_name, var_config in self.schema.items():
            if var_name not in self.env_vars:
                if var_config.get('required', False):
                    self.errors.append(f"Missing required variable: {var_name}")
                else:
                    self.info.append(f"Optional variable not set: {var_name}")
    
    def validate_unused_variables(self) -> None:
        """Check for variables not defined in schema."""
        if not self.schema:
            return
        
        for key in self.env_vars:
            if key not in self.schema:
                self.info.append(f"Variable not in schema: {key}")
    
    def validate_value_formats(self) -> None:
        """Validate values against expected formats from schema."""
        for key, value in self.env_vars.items():
            if key in self.schema:
                var_config = self.schema[key]
                var_type = var_config.get('type', 'string')
                
                if var_type == 'integer':
                    try:
                        int(value)
                    except ValueError:
                        self.errors.append(f"Type error: '{key}' should be integer, got '{value}'")
                
                elif var_type == 'boolean':
                    if value.lower() not in ('true', 'false', '1', '0', 'yes', 'no'):
                        self.errors.append(f"Type error: '{key}' should be boolean, got '{value}'")
                
                elif var_type == 'url':
                    if not re.match(r'^https?://', value):
                        self.errors.append(f"Format error: '{key}' should be a URL starting with http:// or https://")
                
                elif var_type == 'email':
                    if not re.match(r'^[^@\s]+@[^@\s]+\.[^@\s]+', value):
                        self.errors.append(f"Format error: '{key}' should be a valid email address")
                
                elif var_type == 'port':
                    try:
                        port = int(value)
                        if port < 1 or port > 65535:
                            self.errors.append(f"Port error: '{key}' should be 1-65535, got {port}")
                    except ValueError:
                        self.errors.append(f"Port error: '{key}' should be a number")
    
    def validate_security(self) -> None:
        """Check for security issues like exposed secrets."""
        for key, value in self.env_vars.items():
            # Check for empty required-looking fields
            if 'PASSWORD' in key.upper() or 'SECRET' in key.upper() or 'TOKEN' in key.upper() or 'KEY' in key.upper():
                if not value:
                    self.warnings.append(f"Security: '{key}' is empty but appears to be sensitive")
                elif len(value) < 8:
                    self.warnings.append(f"Security: '{key}' appears too short for a secret")
            
            # Check for hardcoded secrets patterns
            for pattern_name, pattern in self.SECRET_PATTERNS.items():
                if re.search(pattern, value):
                    self.warnings.append(f"Security: '{key}' appears to contain a {pattern_name.replace('_', ' ')}")
            
            # Check for localhost/development URLs in production-looking vars
            if 'PROD' in key.upper() or 'LIVE' in key.upper():
                if 'localhost' in value.lower() or '127.0.0.1' in value:
                    self.warnings.append(f"Config: '{key}' uses localhost but name suggests production")
    
    def validate_empty_values(self) -> None:
        """Check for empty values that might be mistakes."""
        for key, value in self.env_vars.items():
            if not value:
                # Skip if it's intentionally empty
                if key not in self.schema or not self.schema[key].get('allow_empty', False):
                    self.info.append(f"Empty value: '{key}' has no value set")
    
    def duplicate_keys(self) -> None:
        """Check for duplicate keys (when file has them repeated)."""
        # This is handled during parsing - env_vars dict will have last value
        # We'd need to track during parsing, so skip for now
        pass
    
    def validate(self) -> bool:
        """Run all validations and return success status."""
        if not self.parse_env_file():
            return False
        
        if not self.parse_schema_file():
            return False
        
        self.validate_naming_conventions()
        self.validate_required_variables()
        self.validate_unused_variables()
        self.validate_value_formats()
        self.validate_security()
        self.validate_empty_values()
        
        return len(self.errors) == 0
    
    def report(self, verbose: bool = False) -> str:
        """Generate a validation report."""
        lines = []
        lines.append(f"Environment Validation Report")
        lines.append(f"{'=' * 50}")
        lines.append(f"File: {self.env_file}")
        lines.append(f"Variables found: {len(self.env_vars)}")
        lines.append("")
        
        if self.errors:
            lines.append(f"❌ ERRORS ({len(self.errors)}):")
            for error in self.errors:
                lines.append(f"   {error}")
            lines.append("")
        
        if self.warnings:
            lines.append(f"⚠️  WARNINGS ({len(self.warnings)}):")
            for warning in self.warnings:
                lines.append(f"   {warning}")
            lines.append("")
        
        if verbose and self.info:
            lines.append(f"ℹ️  INFO ({len(self.info)}):")
            for info in self.info:
                lines.append(f"   {info}")
            lines.append("")
        
        if not self.errors and not self.warnings:
            lines.append("✅ All validations passed!")
        
        status = "FAILED" if self.errors else ("PASSED WITH WARNINGS" if self.warnings else "PASSED")
        lines.append(f"\nStatus: {status}")
        
        return '\n'.join(lines)


def generate_schema_template(output_path: str) -> bool:
    """Generate a template schema file."""
    template = {
        "APP_NAME": {
            "required": True,
            "type": "string",
            "description": "Application name"
        },
        "APP_ENV": {
            "required": True,
            "type": "string",
            "allowed": ["development", "staging", "production"],
            "description": "Environment type"
        },
        "DEBUG": {
            "required": False,
            "type": "boolean",
            "default": "false",
            "description": "Enable debug mode"
        },
        "PORT": {
            "required": False,
            "type": "port",
            "default": "8080",
            "description": "Server port"
        },
        "DATABASE_URL": {
            "required": True,
            "type": "url",
            "description": "Database connection string"
        },
        "API_KEY": {
            "required": True,
            "type": "string",
            "min_length": 16,
            "description": "API key for external service"
        },
        "SECRET_KEY": {
            "required": True,
            "type": "string",
            "min_length": 32,
            "sensitive": True,
            "description": "Application secret key"
        },
        "ADMIN_EMAIL": {
            "required": False,
            "type": "email",
            "description": "Administrator email address"
        },
        "REDIS_HOST": {
            "required": False,
            "type": "string",
            "default": "localhost",
            "description": "Redis server hostname"
        },
        "REDIS_PORT": {
            "required": False,
            "type": "port",
            "default": "6379",
            "description": "Redis server port"
        }
    }
    
    import json
    try:
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(template, f, indent=2)
        return True
    except Exception as e:
        print(f"Error writing schema: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Validate .env files against schema and best practices',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s .env                      Validate .env file
  %(prog)s .env -s schema.json       Validate with schema
  %(prog)s .env --verbose            Show all info messages
  %(prog)s --generate-schema         Generate schema template
  %(prog)s --check-file .env.local   Check specific file
        """
    )
    
    parser.add_argument('env_file', nargs='?', default='.env',
                        help='.env file to validate (default: .env)')
    parser.add_argument('-s', '--schema', metavar='FILE',
                        help='JSON schema file defining required variables')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='Show informational messages')
    parser.add_argument('--generate-schema', metavar='OUTPUT',
                        help='Generate a schema template file')
    parser.add_argument('--check-file', metavar='FILE',
                        help='Check a specific .env file (alias for positional arg)')
    
    args = parser.parse_args()
    
    # Generate schema if requested
    if args.generate_schema:
        if generate_schema_template(args.generate_schema):
            print(f"✅ Schema template generated: {args.generate_schema}")
            sys.exit(0)
        else:
            sys.exit(1)
    
    # Determine file to check
    env_file = args.check_file or args.env_file
    
    # Run validation
    validator = EnvValidator(env_file, args.schema)
    success = validator.validate()
    report = validator.report(verbose=args.verbose)
    
    print(report)
    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()