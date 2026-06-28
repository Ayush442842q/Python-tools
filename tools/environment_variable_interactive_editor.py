#!/usr/bin/env python3
"""
Environment Variable Interactive Editor

A terminal-based interactive editor for .env files with syntax highlighting,
validation, secret detection, and secure editing capabilities.

Features:
- Interactive TUI for editing environment variables
- Syntax highlighting for keys, values, and comments
- TYPE validation (string, int, bool, url, email, etc.)
- Secret detection and masking
- Duplicate key detection
- Export to various formats
- Backup before editing

Usage:
    python environment_variable_interactive_editor.py [path/to/.env]

Author: Python Tools Collection
License: MIT
"""

import os
import sys
import re
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Try to import optional dependencies
try:
    import readline
    HAS_READLINE = True
except ImportError:
    HAS_READLINE = False


class EnvVariable:
    """Represents a single environment variable."""
    
    def __init__(self, key: str = "", value: str = "", comment: str = "", 
                 line_number: int = 0, is_export: bool = False):
        self.key = key
        self.value = value
        self.comment = comment
        self.line_number = line_number
        self.is_export = is_export
        self.is_valid = True
        self.validation_errors: List[str] = []
        self.detected_type = self._detect_type()
        self.is_secret = self._check_if_secret()
    
    def _detect_type(self) -> str:
        """Detect the type of the value."""
        if not self.value:
            return "empty"
        
        # Boolean
        if self.value.lower() in ('true', 'false', 'yes', 'no', '1', '0'):
            return "boolean"
        
        # Integer
        if re.match(r'^-?\d+$', self.value):
            return "integer"
        
        # Float
        if re.match(r'^-?\d+\.\d+$', self.value):
            return "float"
        
        # URL
        if re.match(r'^https?://', self.value):
            return "url"
        
        # Email
        if re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', self.value):
            return "email"
        
        # Port number
        if re.match(r'^\d{1,5}$', self.value) and 0 < int(self.value) <= 65535:
            return "port"
        
        # Path
        if self.value.startswith('/') or self.value.startswith('./') or self.value.startswith('../'):
            return "path"
        
        # JSON
        if self.value.startswith('{') or self.value.startswith('['):
            try:
                json.loads(self.value)
                return "json"
            except json.JSONDecodeError:
                pass
        
        return "string"
    
    def _check_if_secret(self) -> bool:
        """Check if the variable looks like a secret."""
        secret_patterns = [
            r'(?i)password', r'(?i)passwd', r'(?i)pwd',
            r'(?i)secret', r'(?i)api[_-]?key', r'(?i)apikey',
            r'(?i)token', r'(?i)auth', r'(?i)credential',
            r'(?i)private[_-]?key', r'(?i)access[_-]?key',
            r'(?i)secret[_-]?key', r'(?i)encryption[_-]?key'
        ]
        
        for pattern in secret_patterns:
            if re.search(pattern, self.key):
                return True
        
        # Check for high entropy (possible API keys, tokens)
        if len(self.value) >= 16:
            # High entropy detection
            unique_chars = len(set(self.value))
            if unique_chars > 10 and re.match(r'^[A-Za-z0-9_-]+$', self.value):
                return True
        
        return False
    
    def validate(self) -> bool:
        """Validate the environment variable."""
        self.is_valid = True
        self.validation_errors = []
        
        if not self.key:
            self.is_valid = False
            self.validation_errors.append("Empty key")
            return False
        
        if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', self.key):
            self.is_valid = False
            self.validation_errors.append("Invalid key format (must start with letter/underscore, contain only alphanumeric and underscore)")
        
        # Type-specific validation
        if self.detected_type == "port":
            try:
                port = int(self.value)
                if not (0 < port <= 65535):
                    self.is_valid = False
                    self.validation_errors.append(f"Port must be between 1 and 65535, got {port}")
            except ValueError:
                pass
        
        if self.detected_type == "email":
            if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', self.value):
                self.is_valid = False
                self.validation_errors.append("Invalid email format")
        
        if self.detected_type == "url":
            if not re.match(r'^https?://[^\s]+$', self.value):
                self.is_valid = False
                self.validation_errors.append("Invalid URL format")
        
        if self.detected_type == "json":
            try:
                json.loads(self.value)
            except json.JSONDecodeError as e:
                self.is_valid = False
                self.validation_errors.append(f"Invalid JSON: {e}")
        
        return self.is_valid
    
    def __str__(self) -> str:
        """Return the string representation for the .env file."""
        prefix = "export " if self.is_export else ""
        line = f'{prefix}{self.key}="{self.value}"'
        if self.comment:
            line += f"  # {self.comment}"
        return line
    
    def mask_value(self) -> str:
        """Return masked value for secrets."""
        if not self.value:
            return ""
        if len(self.value) <= 4:
            return "*" * len(self.value)
        return self.value[:2] + "*" * (len(self.value) - 4) + self.value[-2:]


class EnvFileEditor:
    """Interactive editor for .env files."""
    
    COLORS = {
        'key': '\033[94m',      # Blue
        'value': '\033[92m',    # Green
        'comment': '\033[90m',  # Gray
        'error': '\033[91m',    # Red
        'warning': '\033[93m',  # Yellow
        'secret': '\033[95m',   # Magenta
        'reset': '\033[0m',
        'bold': '\033[1m'
    }
    
    def __init__(self, filepath: str):
        self.filepath = Path(filepath).expanduser().resolve()
        self.variables: List[EnvVariable] = []
        self.blank_lines: List[Tuple[int, str]] = []  # (line_number, content)
        self.original_content: str = ""
        self.backup_path: Optional[Path] = None
        self.color_support = sys.stdout.isatty()
    
    def load(self) -> bool:
        """Load the .env file."""
        try:
            if not self.filepath.exists():
                print(f"{self.COLORS['warning']}Warning: File does not exist, will create new.{self.COLORS['reset']}")
                return True
            
            self.original_content = self.filepath.read_text()
            lines = self.original_content.splitlines()
            
            for line_num, line in enumerate(lines, 1):
                stripped = line.strip()
                
                # Blank line
                if not stripped:
                    self.blank_lines.append((line_num, line))
                    continue
                
                # Comment line
                if stripped.startswith('#'):
                    comment = stripped[1:].strip()
                    self.blank_lines.append((line_num, f"# {comment}"))
                    continue
                
                # Parse variable
                self._parse_line(line, line_num)
            
            # Validate all variables
            for var in self.variables:
                var.validate()
            
            return True
            
        except Exception as e:
            print(f"{self.COLORS['error']}Error loading file: {e}{self.COLORS['reset']}")
            return False
    
    def _parse_line(self, line: str, line_num: int):
        """Parse a single line into an EnvVariable."""
        # Match export keyword
        is_export = False
        working_line = line.strip()
        
        if working_line.startswith('export '):
            is_export = True
            working_line = working_line[7:].strip()
        
        # Match key=value
        match = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$', working_line)
        if not match:
            # Try without quotes
            match = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=\s*["\']?([^"\']*)["\']?(.*)$', working_line)
        
        if match:
            key = match.group(1)
            value = match.group(2).strip()
            
            # Remove surrounding quotes
            if (value.startswith('"') and value.endswith('"')) or \
               (value.startswith("'") and value.endswith("'")):
                value = value[1:-1]
            
            # Extract inline comment
            comment = ""
            if '#' in value and not value.startswith('http'):
                parts = value.split('#', 1)
                value = parts[0].strip()
                comment = parts[1].strip()
            
            # Check for inline comment in original line
            if not comment and '#' in line:
                comment_part = line.split('#', 1)[1].strip()
                if comment_part:
                    comment = comment_part
            
            var = EnvVariable(key, value, comment, line_num, is_export)
            self.variables.append(var)
    
    def create_backup(self) -> bool:
        """Create a backup of the original file."""
        try:
            if self.filepath.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                self.backup_path = self.filepath.parent / f"{self.filepath.name}.backup_{timestamp}"
                self.filepath.copy(self.backup_path)
                print(f"{self.COLORS['warning']}Backup created: {self.backup_path}{self.COLORS['reset']}")
            return True
        except Exception as e:
            print(f"{self.COLORS['error']}Failed to create backup: {e}{self.COLORS['reset']}")
            return False
    
    def save(self) -> bool:
        """Save the .env file."""
        try:
            lines = []
            var_index = 0
            blank_index = 0
            
            # Merge variables and blank/comment lines preserving order
            all_items = []
            for var in self.variables:
                all_items.append((var.line_number, 'var', var))
            for line_num, content in self.blank_lines:
                all_items.append((line_num, 'blank', content))
            
            all_items.sort(key=lambda x: x[0])
            
            for _, item_type, item in all_items:
                if item_type == 'var':
                    lines.append(str(item))
                else:
                    lines.append(item)
            
            content = '\n'.join(lines)
            if content and not content.endswith('\n'):
                content += '\n'
            
            self.filepath.write_text(content)
            print(f"{self.COLORS['green']}File saved: {self.filepath}{self.COLORS['reset']}")
            return True
            
        except Exception as e:
            print(f"{self.COLORS['error']}Error saving file: {e}{self.COLORS['reset']}")
            return False
    
    def display(self, show_secrets: bool = False):
        """Display all variables with syntax highlighting."""
        print("\n" + "=" * 70)
        print(f"{self.COLORS['bold']}Environment Variables: {self.filepath}{self.COLORS['reset']}")
        print("=" * 70)
        
        if not self.variables:
            print(f"{self.COLORS['warning']}No variables found.{self.COLORS['reset']}")
            return
        
        # Count issues
        invalid_count = sum(1 for v in self.variables if not v.is_valid)
        secret_count = sum(1 for v in self.variables if v.is_secret)
        duplicate_keys = self._find_duplicates()
        
        # Summary
        if invalid_count > 0:
            print(f"{self.COLORS['error']}⚠ {invalid_count} invalid variable(s){self.COLORS['reset']}")
        if secret_count > 0:
            print(f"{self.COLORS['secret']}🔒 {secret_count} secret(s) detected{self.COLORS['reset']}")
        if duplicate_keys:
            print(f"{self.COLORS['warning']}⚠ Duplicate keys: {', '.join(duplicate_keys)}{self.COLORS['reset']}")
        
        print()
        
        # Display variables
        for i, var in enumerate(self.variables, 1):
            status = "✓" if var.is_valid else "✗"
            status_color = self.COLORS['error'] if not var.is_valid else self.COLORS['green']
            
            key_str = f"{self.COLORS['key']}{var.key}{self.COLORS['reset']}"
            value_str = var.mask_value() if var.is_secret and not show_secrets else var.value
            
            if var.is_secret:
                value_str = f"{self.COLORS['secret']}{value_str}{self.COLORS['reset']}"
            else:
                value_str = f"{self.COLORS['value']}{value_str}{self.COLORS['reset']}"
            
            type_str = f"[{var.detected_type}]"
            
            line = f"{status_color}{status}{self.COLORS['reset']} {i:3}. {key_str}={value_str} {type_str}"
            
            if var.comment:
                line += f" {self.COLORS['comment']}# {var.comment}{self.COLORS['reset']}"
            
            if not var.is_valid:
                line += f" {self.COLORS['error']}→ {', '.join(var.validation_errors)}{self.COLORS['reset']}"
            
            print(line)
    
    def _find_duplicates(self) -> List[str]:
        """Find duplicate keys."""
        keys = [var.key for var in self.variables]
        seen = set()
        duplicates = set()
        
        for key in keys:
            if key in seen:
                duplicates.add(key)
            seen.add(key)
        
        return list(duplicates)
    
    def add_variable(self, key: str = None, value: str = None, comment: str = ""):
        """Add a new variable interactively."""
        if not key:
            key = input(f"{self.COLORS['bold']}Variable key: {self.COLORS['reset']}").strip()
        
        if not value:
            value = input(f"{self.COLORS['bold']}Variable value: {self.COLORS['reset']}").strip()
        
        if not comment:
            comment = input(f"{self.COLORS['bold']}Comment (optional): {self.COLORS['reset']}").strip()
        
        var = EnvVariable(key, value, comment, len(self.variables) + 1)
        var.validate()
        self.variables.append(var)
        
        if var.is_valid:
            print(f"{self.COLORS['green']}✓ Added: {key}{self.COLORS['reset']}")
        else:
            print(f"{self.COLORS['error']}✗ Invalid: {', '.join(var.validation_errors)}{self.COLORS['reset']}")
    
    def edit_variable(self, index: int):
        """Edit a variable by index."""
        if index < 1 or index > len(self.variables):
            print(f"{self.COLORS['error']}Invalid index{self.COLORS['reset']}")
            return
        
        var = self.variables[index - 1]
        print(f"\nEditing: {var.key} = {var.mask_value() if var.is_secret else var.value}")
        
        new_value = input(f"New value (Enter to keep): {self.COLORS['bold']}").strip()
        if new_value:
            var.value = new_value
            var.validate()
            print(f"{self.COLORS['green']}✓ Updated{self.COLORS['reset']}")
    
    def delete_variable(self, index: int):
        """Delete a variable by index."""
        if index < 1 or index > len(self.variables):
            print(f"{self.COLORS['error']}Invalid index{self.COLORS['reset']}")
            return
        
        var = self.variables.pop(index - 1)
        print(f"{self.COLORS['warning']}Deleted: {var.key}{self.COLORS['reset']}")
    
    def export_json(self, output_path: str = None):
        """Export variables to JSON."""
        if not output_path:
            output_path = self.filepath.parent / f"{self.filepath.stem}.json"
        else:
            output_path = Path(output_path)
        
        data = {var.key: var.value for var in self.variables}
        output_path.write_text(json.dumps(data, indent=2))
        print(f"{self.COLORS['green']}Exported to: {output_path}{self.COLORS['reset']}")
    
    def export_shell(self, output_path: str = None):
        """Export as shell source file."""
        if not output_path:
            output_path = self.filepath.parent / f"{self.filepath.stem}.sh"
        else:
            output_path = Path(output_path)
        
        lines = ["#!/bin/bash", f"# Generated from {self.filepath.name}", ""]
        for var in self.variables:
            lines.append(f"export {var.key}=\"{var.value}\"")
        
        output_path.write_text('\n'.join(lines))
        output_path.chmod(0o755)
        print(f"{self.COLORS['green']}Exported to: {output_path}{self.COLORS['reset']}")
    
    def interactive_menu(self):
        """Run the interactive menu."""
        while True:
            print("\n" + "-" * 50)
            print("Commands:")
            print("  [d]isplay variables")
            print("  [a]dd variable")
            print("  [e]dit variable")
            print("  [del]ete variable")
            print("  [v]alidate all")
            print("  [s]ave")
            print("  [q]uit")
            print("  [j]son export")
            print("  [c]leanup duplicates")
            print("-" * 50)
            
            cmd = input(f"{self.COLORS['bold']}Command: {self.COLORS['reset']}").strip().lower()
            
            if cmd == 'd':
                self.display(show_secrets=False)
            elif cmd == 'a':
                self.add_variable()
            elif cmd == 'e':
                try:
                    idx = int(input("Variable number to edit: "))
                    self.edit_variable(idx)
                except ValueError:
                    print(f"{self.COLORS['error']}Invalid number{self.COLORS['reset']}")
            elif cmd == 'del':
                try:
                    idx = int(input("Variable number to delete: "))
                    self.delete_variable(idx)
                except ValueError:
                    print(f"{self.COLORS['error']}Invalid number{self.COLORS['reset']}")
            elif cmd == 'v':
                invalid = sum(1 for v in self.variables if not v.validate())
                print(f"{self.COLORS['green']}Validated: {len(self.variables)} variables, {invalid} invalid{self.COLORS['reset']}")
            elif cmd == 's':
                self.create_backup()
                self.save()
            elif cmd == 'j':
                self.export_json()
            elif cmd == 'c':
                self._cleanup_duplicates()
            elif cmd == 'q':
                confirm = input("Save before quitting? (y/n): ").strip().lower()
                if confirm == 'y':
                    self.create_backup()
                    self.save()
                print("Goodbye!")
                break
            else:
                print(f"{self.COLORS['warning']}Unknown command: {cmd}{self.COLORS['reset']}")
    
    def _cleanup_duplicates(self):
        """Remove duplicate keys, keeping the last occurrence."""
        seen = {}
        to_remove = []
        
        for i, var in enumerate(self.variables):
            if var.key in seen:
                to_remove.append(seen[var.key])
            seen[var.key] = i
        
        for idx in sorted(to_remove, reverse=True):
            var = self.variables.pop(idx)
            print(f"{self.COLORS['warning']}Removed duplicate: {var.key}{self.COLORS['reset']}")


def main():
    """Main entry point."""
    filepath = sys.argv[1] if len(sys.argv) > 1 else ".env"
    
    print(f"{'=' * 60}")
    print(f"  Environment Variable Interactive Editor")
    print(f"{'=' * 60}")
    
    editor = EnvFileEditor(filepath)
    
    if not editor.load():
        sys.exit(1)
    
    editor.display(show_secrets=False)
    editor.interactive_menu()


if __name__ == "__main__":
    main()