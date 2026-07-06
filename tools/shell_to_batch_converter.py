#!/usr/bin/env python3
"""
Shell to Batch Converter - Transpiles basic Bash shell scripts (.sh) to Windows Command Prompt Batch files (.bat).
Translates file operations (mkdir, cp, mv, rm), variable declarations/access, comments, and simple if-conditions.
"""

import os
import re
import sys
import argparse

# ANSI color codes for TUI
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_BLUE = "\033[94m"
COLOR_RESET = "\033[0m"

def log_success(message):
    print(f"{COLOR_GREEN}[✓] {message}{COLOR_RESET}")

def log_warn(message):
    print(f"{COLOR_YELLOW}[!] {message}{COLOR_RESET}")

def log_error(message):
    print(f"{COLOR_RED}[✗] {message}{COLOR_RESET}", file=sys.stderr)

def log_info(message):
    print(f"{COLOR_BLUE}[i] {message}{COLOR_RESET}")

def convert_line(line, state):
    """Converts a single line of Bash syntax to Windows Batch syntax."""
    stripped = line.strip()
    
    # 1. Skip shebang or replace with batch setup
    if stripped.startswith("#!"):
        return "@echo off\nsetlocal enabledelayedexpansion"
        
    # 2. Comments: # comment -> :: comment
    if stripped.startswith("#"):
        # Keep empty comments intact
        if stripped == "#":
            return "::"
        return "::" + line[line.find("#")+1:]
        
    # 3. Handle Variable Assignments: VAR="val" or VAR=val -> set "VAR=val"
    var_assign_match = re.match(r'^([a-zA-Z_][a-zA-Z0-9_]*)=(.*)$', stripped)
    if var_assign_match:
        name = var_assign_match.group(1)
        val = var_assign_match.group(2).strip('"\'')
        # Translate variables inside the value (e.g. $OTHER_VAR -> %OTHER_VAR%)
        val = translate_vars(val)
        return f'set "{name}={val}"'
        
    # 4. Handle End of If: fi -> )
    if stripped == "fi":
        state["in_if"] = False
        return ")"
        
    # 5. Handle Else: else -> ) else (
    if stripped == "else":
        return ") else ("
        
    # 6. Handle If Conditions (Simple)
    # Pattern: if [ ... ]; then or if [[ ... ]]; then
    if stripped.startswith("if ") and stripped.endswith("then"):
        state["in_if"] = True
        # Extract condition content inside [ ] or [[ ]]
        cond_match = re.search(r'if\s+\[+([^\]]+)\]+\s*;\s*then', stripped)
        if cond_match:
            cond = cond_match.group(1).strip()
            return f"if {translate_condition(cond)} ("
        return "if ( :: Warning: complex condition, check manually ) ("
        
    # 7. Basic Command replacements
    translated = translate_commands(stripped)
    
    # Indent lines inside if blocks for readability
    if state["in_if"] and not stripped.startswith("if ") and stripped != "else":
        translated = "    " + translated
        
    return translated

def translate_vars(text):
    """Replaces $VAR and ${VAR} with %VAR%, and positional args $1, $2, $@ with %1, %2, %*."""
    # Positional args
    text = re.sub(r'\$(\d+)', r'%\1', text)
    text = text.replace("$@", "%*").replace("$*", "%*")
    
    # Named variables: ${VAR} -> %VAR%
    text = re.sub(r'\${([a-zA-Z_][a-zA-Z0-9_]*)}', r'%\1%', text)
    # Named variables: $VAR -> %VAR%
    text = re.sub(r'\$([a-zA-Z_][a-zA-Z0-9_]*)', r'%\1%', text)
    
    return text

def translate_condition(cond):
    """Translates simple Bash conditional tests to Batch if checks."""
    # Translate variables first
    cond = translate_vars(cond)
    
    # Directory check: -d "path" -> exist "path"\
    dir_match = re.match(r'-d\s+(.*)', cond)
    if dir_match:
        val = dir_match.group(1).strip('"\'')
        return f'exist "{val}"\\'
        
    # File check: -f "path" or -e "path" -> exist "path"
    file_match = re.match(r'-[fe]\s+(.*)', cond)
    if file_match:
        val = file_match.group(1).strip('"\'')
        return f'exist "{val}"'
        
    # String empty check: -z "str" -> "str"==""
    empty_match = re.match(r'-z\s+(.*)', cond)
    if empty_match:
        val = empty_match.group(1)
        return f'{val}==""'
        
    # String comparison: "a" = "b" or "a" == "b"
    comp_match = re.match(r'(.*?)\s*==?\s*(.*)', cond)
    if comp_match:
        left = comp_match.group(1).strip()
        right = comp_match.group(2).strip()
        return f'{left}=={right}'
        
    return cond

def translate_commands(cmd):
    """Translates individual Bash shell commands to Windows Batch commands."""
    # Translate variables in command line
    cmd = translate_vars(cmd)
    
    # Parse tokens to check command name
    tokens = cmd.split()
    if not tokens:
        return ""
        
    base_cmd = tokens[0]
    args = tokens[1:]
    
    # 1. mkdir -p dir -> if not exist dir mkdir dir
    if base_cmd == "mkdir":
        if args and args[0] == "-p":
            dir_path = " ".join(args[1:])
            return f'if not exist {dir_path} mkdir {dir_path}'
        return f'mkdir {" ".join(args)}'
        
    # 2. rm -rf target -> rmdir /s /q or del /f /q
    if base_cmd == "rm":
        has_rf = "-rf" in args or ("-r" in args and "-f" in args) or "-f" in args
        target_args = [a for a in args if not a.startswith("-")]
        target = " ".join(target_args)
        
        if has_rf:
            # Batch wrapper to handle directory or file deleting
            return f'if exist {target} ( if exist {target}\\ ( rmdir /s /q {target} ) else ( del /f /q {target} ) )'
        return f'del {" ".join(target_args)}'
        
    # 3. cp -r src dest -> xcopy /e /i /y src dest
    if base_cmd == "cp":
        is_recursive = "-r" in args or "-R" in args or "-a" in args
        clean_args = [a for a in args if not a.startswith("-")]
        if len(clean_args) >= 2:
            src, dest = clean_args[0], clean_args[1]
            if is_recursive:
                return f'xcopy /e /i /y {src} {dest}'
            return f'copy /y {src} {dest}'
        return f'copy {" ".join(clean_args)}'
        
    # 4. mv src dest -> move /y src dest
    if base_cmd == "mv":
        clean_args = [a for a in args if not a.startswith("-")]
        if len(clean_args) >= 2:
            return f'move /y {clean_args[0]} {clean_args[1]}'
        return f'move {" ".join(clean_args)}'
        
    # 5. pwd -> echo %cd%
    if base_cmd == "pwd":
        return "echo %cd%"
        
    # 6. ls -> dir
    if base_cmd == "ls":
        return "dir"
        
    # 7. cat file -> type file
    if base_cmd == "cat":
        return f'type {" ".join(args)}'
        
    # 8. touch file -> type null > file (or echo. > file)
    if base_cmd == "touch":
        return f'copy NUL {" ".join(args)} >nul 2>&1'
        
    # 9. grep pattern file -> findstr pattern file
    if base_cmd == "grep":
        return f'findstr {" ".join(args)}'
        
    # 10. clear -> cls
    if base_cmd == "clear":
        return "cls"
        
    # 11. exit 0 -> exit /b 0
    if base_cmd == "exit":
        code = args[0] if args else "0"
        return f"exit /b {code}"
        
    # 12. echo -> echo
    if base_cmd == "echo":
        # Remove -e parameter if exists
        clean_args = [a for a in args if a != "-e"]
        return f'echo {" ".join(clean_args)}'
        
    return cmd

def convert_sh_to_bat(sh_content):
    """Processes shell script content and outputs converted batch file content."""
    lines = sh_content.splitlines()
    bat_lines = []
    state = {"in_if": False}
    
    for line in lines:
        converted = convert_line(line, state)
        # Handle @echo off line spacing
        if "@echo off" in converted:
            bat_lines.extend(converted.split("\n"))
        else:
            bat_lines.append(converted)
            
    return "\n".join(bat_lines)

def main():
    parser = argparse.ArgumentParser(description="Convert Bash scripts (.sh) to Windows Command Prompt Batch scripts (.bat).")
    parser.add_argument("input", help="Path to input Bash script file.")
    parser.add_argument("-o", "--output", help="Path to save output Batch script. Defaults to input with .bat extension.")
    
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
        
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        log_error(f"Input file not found: {args.input}")
        sys.exit(1)
        
    try:
        with open(args.input, "r", encoding="utf-8") as f:
            sh_content = f.read()
    except Exception as e:
        log_error(f"Failed to read input file: {e}")
        sys.exit(1)
        
    log_info(f"Converting Shell script: {args.input}")
    
    bat_content = convert_sh_to_bat(sh_content)
    
    # Determine output path
    output_path = args.output
    if not output_path:
        base, _ = os.path.splitext(args.input)
        output_path = base + ".bat"
        
    try:
        with open(output_path, "w", encoding="utf-8", newline="\r\n") as f:
            f.write(bat_content)
        log_success(f"Successfully converted and saved to: {output_path}")
    except Exception as e:
        log_error(f"Failed to write output file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
