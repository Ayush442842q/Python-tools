#!/usr/bin/env python3
"""
Windows Batch Script Linter & Advisor - Audit batch scripts (.bat/.cmd) for bugs and bad practices.

This tool parses Windows batch files and scans for common pitfalls including:
  - Missing @echo off and setlocal
  - Unquoted variable expansions in path-related operations (risk of space issues)
  - Dangerous ERRORLEVEL checking logic (e.g., 'if errorlevel 0' matches any positive exit code)
  - Variable mutation inside loops without delayed expansion
  - Unquoted IF comparison strings
  - Command fall-throughs due to missing exit /b in subroutines
  - Interactive commands (pause, timeout) running without non-interactive guards
"""

import os
import re
import sys
import argparse

# ANSI color codes
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"
COLOR_RESET = "\033[0m"

# Severity levels
SEV_ERROR = f"{COLOR_RED}[ERROR]{COLOR_RESET}"
SEV_WARNING = f"{COLOR_YELLOW}[WARNING]{COLOR_RESET}"
SEV_INFO = f"{COLOR_CYAN}[INFO]{COLOR_RESET}"

class BatchScriptLinter:
    def __init__(self, filepath, content=None):
        self.filepath = filepath
        self.content = content
        self.lines = []
        self.issues = []
        self.has_echo_off = False
        self.has_setlocal = False
        self.has_delayed_expansion = False

    def load_content(self):
        if self.content is not None:
            self.lines = self.content.splitlines()
            return True
        if not os.path.exists(self.filepath):
            print(f"Error: File '{self.filepath}' not found.", file=sys.stderr)
            return False
        try:
            with open(self.filepath, 'r', encoding='utf-8', errors='ignore') as f:
                self.lines = [line.rstrip('\r\n') for line in f]
            return True
        except Exception as e:
            print(f"Error reading file '{self.filepath}': {e}", file=sys.stderr)
            return False

    def report_issue(self, line_num, severity, code, message, tip=None):
        self.issues.append({
            "line": line_num,
            "severity": severity,
            "code": code,
            "message": message,
            "tip": tip
        })

    def analyze(self):
        if not self.lines:
            return

        # Pre-scan for environment settings
        for i, line in enumerate(self.lines):
            clean = line.strip().lower()
            # Ignore comments
            if clean.startswith("rem") or clean.startswith("::"):
                continue
            if "@echo off" in clean or "echo off" in clean:
                self.has_echo_off = True
            if "setlocal" in clean:
                self.has_setlocal = True
                if "enabledelayedexpansion" in clean:
                    self.has_delayed_expansion = True

        # Audit global settings
        if not self.has_echo_off:
            self.report_issue(1, SEV_INFO, "@echo off", "Missing '@echo off' at the beginning of the script.", "Add '@echo off' on the first line to suppress command echoing.")
        if not self.has_setlocal:
            self.report_issue(1, SEV_WARNING, "setlocal", "Script does not use 'setlocal'.", "Use 'setlocal' to avoid polluting the caller's environment with global variables.")

        in_parenthesized_block = 0
        in_subroutine = False
        subroutine_line = 0

        # Scan line by line
        for idx, line in enumerate(self.lines):
            line_num = idx + 1
            clean = line.strip()
            clean_lower = clean.lower()

            # Skip full comment lines
            if clean_lower.startswith("rem") or clean_lower.startswith("::"):
                continue

            # Track parenthesized blocks (simplistic check)
            in_parenthesized_block += clean.count("(") - clean.count(")")

            # Check for subroutine label definition
            if clean.startswith(":") and not clean.startswith("::"):
                label_name = clean[1:].split()[0] if clean[1:].split() else ""
                if label_name and label_name not in ("eof", ""):
                    # If we were already in a subroutine, check if it had a proper exit/goto
                    if in_subroutine:
                        # Check previous non-empty line
                        prev_idx = idx - 1
                        prev_clean = ""
                        while prev_idx >= 0:
                            prev_clean = self.lines[prev_idx].strip().lower()
                            if prev_clean and not prev_clean.startswith("rem") and not prev_clean.startswith("::"):
                                break
                            prev_idx -= 1
                        
                        if prev_clean and not any(x in prev_clean for x in ["exit /b", "goto :eof", "goto eof"]):
                            self.report_issue(
                                subroutine_line, 
                                SEV_WARNING, 
                                self.lines[subroutine_line - 1].strip(), 
                                "Subroutine does not appear to terminate with an exit/goto command.", 
                                f"Ensure the subroutine ends with 'exit /b' or 'goto :eof' to prevent falling through to '{clean}'."
                            )
                    in_subroutine = True
                    subroutine_line = line_num

            # 1. Check for bad errorlevel checking
            # e.g., "if errorlevel 0" is true for any errorlevel >= 0!
            # Often developers write "if errorlevel 0" intending "if errorlevel is exactly 0" or "no error".
            if "if errorlevel" in clean_lower:
                match = re.search(r"if\s+errorlevel\s+(\d+)", clean_lower)
                if match:
                    val = int(match.group(1))
                    if val == 0:
                        self.report_issue(
                            line_num,
                            SEV_ERROR,
                            clean,
                            "'if errorlevel 0' is ALWAYS true (matches any error code >= 0).",
                            "Use 'if %ERRORLEVEL% equ 0' or 'if not errorlevel 1' instead."
                        )
                    else:
                        self.report_issue(
                            line_num,
                            SEV_INFO,
                            clean,
                            f"'if errorlevel {val}' checks if error level is GREATER THAN OR EQUAL to {val}.",
                            "Use 'if %ERRORLEVEL% equ %value%' for an exact equality check."
                        )

            # 2. Check for unsafe variables in paths (missing quotes around variables)
            # Common commands: cd, del, copy, move, rd, rmdir, type, start, call, md, mkdir
            path_commands = [r"\bcd\b", r"\bdel\b", r"\bcopy\b", r"\bmove\b", r"\brd\b", r"\brmdir\b", r"\btype\b", r"\bmd\b", r"\bmkdir\b"]
            for cmd_pat in path_commands:
                if re.search(cmd_pat, clean_lower):
                    # Find unquoted variable expansions in the line, like %VAR%
                    # We look for %something% not surrounded by quotes on the line
                    # Simplistic check: Find all variables %VAR% on the line
                    vars_found = re.findall(r"%([^%]+)%", clean)
                    for var in vars_found:
                        # Skip special dynamic variables
                        if var.lower() in ("date", "time", "random", "cd", "cmdcmdline", "cmdextversion", "errorlevel", "highestnumanodenumber"):
                            continue
                        # Check if this variable is inside quotes on this line
                        # We do this by checking if the number of double quotes before %var% is odd.
                        pos = clean.find(f"%{var}%")
                        quotes_before = clean[:pos].count('"')
                        quotes_after = clean[pos:].count('"')
                        if quotes_before % 2 == 0:
                            # It's outside quotes! Check if it looks like it's used in path context
                            # For example, if it's preceded by a path command or is part of a path
                            self.report_issue(
                                line_num,
                                SEV_WARNING,
                                clean,
                                f"Unquoted variable expansion '%{var}%' in command. Risk of crash if path contains spaces.",
                                f"Wrap it in double quotes: \"%{var}%\""
                            )

            # 3. Check for delayed expansion issues inside parenthesized blocks (e.g. IF/FOR)
            # If they are assigning a variable `set VAR=...` inside a parenthesized block
            # and then reading it as `%VAR%` in the same block, it won't work without delayed expansion!
            if in_parenthesized_block > 0:
                if "set " in clean_lower and "=" in clean:
                    # Extract variable name being set
                    match = re.search(r"set\s+([a-zA-Z0-9_]+)\s*=", clean, re.IGNORECASE)
                    if match:
                        var_set = match.group(1)
                        # Scan subsequent lines in the same parenthesized block for %var_set%
                        # (until block ends or script ends)
                        block_depth = in_parenthesized_block
                        for scan_idx in range(idx + 1, len(self.lines)):
                            scan_line = self.lines[scan_idx].strip()
                            scan_lower = scan_line.lower()
                            # Track block changes
                            block_depth += scan_line.count("(") - scan_line.count(")")
                            if f"%{var_set.lower()}%" in scan_lower:
                                if not self.has_delayed_expansion:
                                    self.report_issue(
                                        scan_idx + 1,
                                        SEV_ERROR,
                                        scan_line,
                                        f"Variable '%{var_set}%' is read inside a parenthesized block after being set, but delayed expansion is disabled.",
                                        "Add 'setlocal enabledelayedexpansion' at the top and read the variable using exclamation marks: !"+var_set+"!"
                                    )
                                    break
                            if block_depth <= 0:
                                break

            # 4. Check for unquoted IF comparisons
            # e.g., "if %VAR%==value" will crash with syntax error if %VAR% is empty or has spaces.
            if clean_lower.startswith("if "):
                # Match comparisons like `if %VAR%==val` or `if %VAR% equ val`
                # Skip if it has double quotes around the operands
                # Check for "==" or "equ" etc.
                comparisons = ["==", "equ", "neq", "lss", "leq", "gtr", "geq"]
                for op in comparisons:
                    if op in clean_lower:
                        parts = clean.split(op)
                        if len(parts) >= 2:
                            lhs = parts[0].replace("if ", "").replace("not ", "").strip()
                            rhs = parts[1].split("(")[0].strip()  # split away block opening
                            
                            # Check if lhs or rhs contains variables but lacks wrapping quotes
                            if ("%" in lhs and not (lhs.startswith('"') and lhs.endswith('"'))) or \
                               ("%" in rhs and not (rhs.startswith('"') and rhs.endswith('"'))):
                                self.report_issue(
                                    line_num,
                                    SEV_WARNING,
                                    clean,
                                    "Unquoted comparison operands in IF statement.",
                                    "Use double quotes: if \"%VAR%\"==\"value\" or if /i \"%VAR%\"==\"value\""
                                )
                                break

            # 5. Interactive commands warning (potential hangs in automated environments)
            interactive_cmds = {"pause": "PAUSE pauses execution and prompts for keystroke.", 
                                "timeout": "TIMEOUT pauses execution for a set duration."}
            for icmd, desc in interactive_cmds.items():
                if f" {icmd}" in f" {clean_lower}":
                    # Check if there is some redirection or check that might bypass it, otherwise warn
                    if ">nul" not in clean_lower and "> nul" not in clean_lower:
                        self.report_issue(
                            line_num,
                            SEV_INFO,
                            clean,
                            f"Interactive command '{icmd}' detected.",
                            "Make sure it is bypassed in non-interactive/CI environments, e.g. using a command line flag check."
                        )

            # 6. Unsafe set /a
            if "set /a" in clean_lower:
                # set /a expressions containing special characters like ^, &, |, <, > must be quoted
                special_chars = ["^", "&", "|", "<", ">"]
                for char in special_chars:
                    if char in clean:
                        # Check if the line is quoted
                        if '"' not in clean:
                            self.report_issue(
                                line_num,
                                SEV_ERROR,
                                clean,
                                f"Arithmetic expression 'set /a' contains special redirection character '{char}' without quotes.",
                                "Quote the entire expression: set /a \"result=a & b\""
                            )
                            break

        # Check last subroutine at the end of file
        if in_subroutine:
            # Check last line
            last_clean = ""
            for prev_idx in range(len(self.lines) - 1, -1, -1):
                last_clean = self.lines[prev_idx].strip().lower()
                if last_clean and not last_clean.startswith("rem") and not last_clean.startswith("::"):
                    break
            if last_clean and not any(x in last_clean for x in ["exit /b", "goto :eof", "goto eof", "exit"]):
                self.report_issue(
                    subroutine_line,
                    SEV_WARNING,
                    self.lines[subroutine_line - 1].strip(),
                    "Subroutine at the end of the file does not terminate with an exit/goto command.",
                    "Ensure the subroutine ends with 'exit /b' or 'goto :eof' to prevent accidental fall-through."
                )

    def print_report(self):
        print(f"\n{COLOR_BOLD}=== Windows Batch Linter Report ==={COLOR_RESET}")
        print(f"File: {COLOR_CYAN}{self.filepath}{COLOR_RESET}\n")

        if not self.issues:
            print(f"{COLOR_GREEN}✓ No issues found!{COLOR_RESET}\n")
            return 0

        errors = sum(1 for iss in self.issues if SEV_ERROR in iss["severity"])
        warnings = sum(1 for iss in self.issues if SEV_WARNING in iss["severity"])
        infos = sum(1 for iss in self.issues if SEV_INFO in iss["severity"])

        for iss in self.issues:
            print(f"Line {iss['line']}: {iss['severity']}")
            print(f"  Code: {COLOR_BOLD}{iss['code']}{COLOR_RESET}")
            print(f"  Issue: {iss['message']}")
            if iss['tip']:
                print(f"  Tip:   {COLOR_GREEN}{iss['tip']}{COLOR_RESET}")
            print()

        print(f"Summary: Found {COLOR_RED}{errors} error(s){COLOR_RESET}, {COLOR_YELLOW}{warnings} warning(s){COLOR_RESET}, {COLOR_CYAN}{infos} info message(s){COLOR_RESET}.\n")
        return 1 if errors > 0 else 0

def main():
    parser = argparse.ArgumentParser(description="Audit Windows Batch files (.bat/.cmd) for issues and anti-patterns.")
    parser.add_argument("file", nargs="?", help="Path to the Windows batch file to audit")
    args = parser.parse_args()

    if not args.file:
        parser.print_help()
        sys.exit(0)

    linter = BatchScriptLinter(args.file)
    if not linter.load_content():
        sys.exit(1)

    linter.analyze()
    sys.exit(linter.print_report())

if __name__ == "__main__":
    main()
