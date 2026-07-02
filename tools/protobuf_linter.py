#!/usr/bin/env python3
"""
protobuf_linter - Protocol Buffer (.proto) Style Linter

Scans Protocol Buffer (.proto) files (supports proto2 and proto3) for syntax issues,
naming convention violations, duplicate field tags, missing package declarations,
and other style guide recommendations matching Google's Protobuf style guide.

Usage:
    python tools/protobuf_linter.py file.proto
    python tools/protobuf_linter.py path/to/protos/
"""

import argparse
import os
import re
import sys

# ANSI Colors
COLOR_RED = "\033[91m"
COLOR_YELLOW = "\033[93m"
COLOR_GREEN = "\033[92m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"
COLOR_RESET = "\033[0m"


class ProtoLinter:
    def __init__(self, filepath):
        self.filepath = filepath
        self.filename = os.path.basename(filepath)
        self.warnings = []
        self.high_severity = 0
        self.medium_severity = 0
        self.low_severity = 0

    def add_warning(self, severity, line_num, message, suggestion):
        self.warnings.append({
            "severity": severity,
            "line": line_num,
            "message": message,
            "suggestion": suggestion
        })
        if severity == "HIGH":
            self.high_severity += 1
        elif severity == "MEDIUM":
            self.medium_severity += 1
        else:
            self.low_severity += 1

    def lint(self):
        try:
            with open(self.filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except OSError as e:
            self.add_warning("HIGH", 0, f"Failed to read file: {e}", "Verify permissions and file path.")
            return

        lines = content.splitlines()

        # Check 1: Syntax specification
        has_syntax = False
        for idx, line in enumerate(lines[:5]):
            if re.match(r'^\s*syntax\s*=\s*["\']proto[23]["\']\s*;', line):
                has_syntax = True
                break
        if not has_syntax:
            self.add_warning("HIGH", 1, "Missing syntax specification.", "Add 'syntax = \"proto3\";' or 'syntax = \"proto2\";' at the beginning of the file.")

        # Check 2: Package declaration
        has_package = False
        for idx, line in enumerate(lines):
            if re.match(r'^\s*package\s+[\w\.]+\s*;', line):
                has_package = True
                break
        if not has_package:
            self.add_warning("MEDIUM", 1, "Missing package declaration.", "Define a package to prevent namespace collisions (e.g., 'package my.project;').")

        # Parsing states
        current_message = None
        current_message_fields = {}  # msg_name -> {tag_number -> field_name}
        current_enum = None
        current_enum_values = set()

        in_message = False
        in_enum = False
        brace_count = 0

        for line_num, raw_line in enumerate(lines, 1):
            line = re.sub(r'//.*$', '', raw_line).strip()  # Strip comments
            if not line:
                continue

            # Detect message definition start
            msg_match = re.match(r'^message\s+(\w+)\s*\{?', line)
            if msg_match:
                current_message = msg_match.group(1)
                in_message = True
                brace_count = 1
                current_message_fields[current_message] = {}
                
                # Check message name style: PascalCase
                if not re.match(r'^[A-Z][a-zA-Z0-9]*$', current_message):
                    self.add_warning(
                        "MEDIUM", 
                        line_num, 
                        f"Message name '{current_message}' is not PascalCase.", 
                        f"Rename to '{self.to_pascal_case(current_message)}'."
                    )
                continue

            # Detect enum definition start
            enum_match = re.match(r'^enum\s+(\w+)\s*\{?', line)
            if enum_match:
                current_enum = enum_match.group(1)
                in_enum = True
                brace_count = 1
                current_enum_values = set()
                
                # Check enum name style: PascalCase
                if not re.match(r'^[A-Z][a-zA-Z0-9]*$', current_enum):
                    self.add_warning(
                        "MEDIUM", 
                        line_num, 
                        f"Enum name '{current_enum}' is not PascalCase.", 
                        f"Rename to '{self.to_pascal_case(current_enum)}'."
                    )
                continue

            # Track block braces
            if '{' in line:
                brace_count += line.count('{')
            if '}' in line:
                brace_count -= line.count('}')
                if brace_count <= 0:
                    in_message = False
                    in_enum = False
                    current_message = None
                    current_enum = None
                    brace_count = 0
                    continue

            # Inside message checks
            if in_message and current_message:
                # Field definition pattern: type field_name = tag_number [options];
                # e.g., string first_name = 1;
                # e.g., repeated int32 user_ids = 2 [packed=true];
                field_match = re.match(r'^(?:required|optional|repeated)?\s*([\w\.]+)\s+(\w+)\s*=\s*(\d+)\s*(?:\[.*\])?\s*;', line)
                if field_match:
                    field_type, field_name, tag_str = field_match.groups()
                    tag = int(tag_str)

                    # Check field name style: snake_case
                    if not re.match(r'^[a-z][a-z0-9_]*$', field_name):
                        self.add_warning(
                            "MEDIUM", 
                            line_num, 
                            f"Field name '{field_name}' in message '{current_message}' is not snake_case.", 
                            f"Rename to '{self.to_snake_case(field_name)}'."
                        )

                    # Check for duplicate tags
                    field_map = current_message_fields[current_message]
                    if tag in field_map:
                        self.add_warning(
                            "HIGH", 
                            line_num, 
                            f"Duplicate tag number '{tag}' in message '{current_message}'. Used by '{field_name}' and '{field_map[tag]}'.", 
                            "Assign a unique tag number to this field."
                        )
                    else:
                        field_map[tag] = field_name

                    # Check tag numbers are in valid range
                    if tag < 1 or tag > 536870911:
                        self.add_warning(
                            "HIGH", 
                            line_num, 
                            f"Tag number '{tag}' is out of range (1 to 536,870,911).", 
                            "Change tag number to be within the allowed range."
                        )
                    elif 19000 <= tag <= 19999:
                        self.add_warning(
                            "HIGH", 
                            line_num, 
                            f"Tag number '{tag}' falls inside the reserved range (19000-19999) for Protobuf implementation.", 
                            "Choose a tag number outside of the range 19000 to 19999."
                        )

            # Inside enum checks
            if in_enum and current_enum:
                # Enum value pattern: VALUE_NAME = 0;
                enum_val_match = re.match(r'^(\w+)\s*=\s*(-?\d+)\s*(?:\[.*\])?\s*;', line)
                if enum_val_match:
                    val_name, val_num = enum_val_match.groups()
                    
                    # Check enum value style: UPPER_CASE_WITH_UNDERSCORES
                    if not re.match(r'^[A-Z][A-Z0-9_]*$', val_name):
                        self.add_warning(
                            "MEDIUM", 
                            line_num, 
                            f"Enum value '{val_name}' in enum '{current_enum}' is not UPPERCASE.", 
                            f"Rename to '{val_name.upper()}'."
                        )

                    # Check if enum value is prefixed with the enum name (recommended by Google Style Guide)
                    expected_prefix = self.to_snake_case(current_enum).upper() + "_"
                    if not val_name.startswith(expected_prefix):
                        self.add_warning(
                            "LOW", 
                            line_num, 
                            f"Enum value '{val_name}' should be prefixed with enum name '{expected_prefix}'.", 
                            f"Rename to '{expected_prefix}{val_name}'."
                        )

    @staticmethod
    def to_pascal_case(s):
        parts = re.split(r'[_-\s]+', s)
        return "".join(p.capitalize() for p in parts if p)

    @staticmethod
    def to_snake_case(s):
        s = re.sub(r'(.)([A-Z][a-z]+)', r'\1_\2', s)
        return re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', s).lower().replace('-', '_')

    def report(self):
        """Prints a colored diagnostic report to standard output."""
        print(f"\n{COLOR_BOLD}Proto Linter Diagnostics for: {self.filename}{COLOR_RESET}")
        print("=" * (30 + len(self.filename)))
        
        if not self.warnings:
            print(f"{COLOR_GREEN}✔ Perfect style! No warnings found.{COLOR_RESET}\n")
            return True

        # Sort warnings by line number
        self.warnings.sort(key=lambda x: x["line"])
        for w in self.warnings:
            sev_color = COLOR_RED if w["severity"] == "HIGH" else (COLOR_YELLOW if w["severity"] == "MEDIUM" else COLOR_CYAN)
            print(f"[{sev_color}{w['severity']}{COLOR_RESET}] Line {w['line']}: {w['message']}")
            print(f"    Suggestion: {w['suggestion']}")
        
        print("\nSummary:")
        print(f"  - High Severity warnings: {self.high_severity}")
        print(f"  - Medium Severity warnings: {self.medium_severity}")
        print(f"  - Low Severity warnings: {self.low_severity}")
        print()
        return self.high_severity == 0


def main():
    parser = argparse.ArgumentParser(description="Lint Protocol Buffer (.proto) files for style issues.")
    parser.add_argument("path", help="Path to a proto file or directory of proto files.")
    args = parser.parse_args()

    # Collect files
    files_to_scan = []
    if os.path.isdir(args.path):
        for root, _, files in os.walk(args.path):
            for file in files:
                if file.endswith(".proto"):
                    files_to_scan.append(os.path.join(root, file))
    elif os.path.isfile(args.path):
        if args.path.endswith(".proto"):
            files_to_scan.append(args.path)
        else:
            print(f"Error: '{args.path}' is not a .proto file.", file=sys.stderr)
            sys.exit(1)
    else:
        print(f"Error: Path '{args.path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    if not files_to_scan:
        print("No .proto files found to scan.")
        sys.exit(0)

    all_clean = True
    for file_path in files_to_scan:
        linter = ProtoLinter(file_path)
        linter.lint()
        success = linter.report()
        if not success:
            all_clean = False

    if not all_clean:
        sys.exit(1)


if __name__ == "__main__":
    main()
