#!/usr/bin/env python3
"""
Shell Script Command & Dependency Validator
Scans shell scripts (.sh, .bash, .bat, .ps1) recursively, extracts external commands invoked,
and verifies if they are available on the current system path.
"""

import os
import re
import sys
import shutil
import argparse
from typing import Set, Dict, List, Tuple

# ANSI Colors
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"

# Shell builtins and syntax keywords to ignore
BASH_IGNORES = {
    'if', 'then', 'else', 'elif', 'fi', 'for', 'in', 'do', 'done', 'while', 'until',
    'case', 'esac', 'function', 'return', 'exit', 'echo', 'printf', 'local', 'export',
    'read', 'set', 'shift', 'eval', 'alias', 'cd', 'pwd', 'test', 'true', 'false',
    'exec', 'trap', 'source', 'type', 'declare', 'readonly', 'let', 'getopts', 'history',
    'logout', 'umask', 'unalias', 'wait', 'jobs', 'fg', 'bg', 'kill', 'command', 'builtin',
    'time', 'times', 'select', 'dirs', 'pushd', 'popd', 'hash', 'bind', 'help', 'suspend'
}

BAT_IGNORES = {
    'echo', 'set', 'if', 'goto', 'call', 'pause', 'rem', 'exit', 'shift', 'for', 'in',
    'do', 'pushd', 'popd', 'color', 'title', 'cls', 'assoc', 'ftype', 'ver', 'vol',
    'dir', 'copy', 'del', 'erase', 'ren', 'rename', 'md', 'mkdir', 'rd', 'rmdir',
    'type', 'more', 'move', 'path', 'tree', 'pause', 'start', 'attrib', 'chcp', 'errorlevel',
    'defined', 'not', 'exist', 'error', 'nul', 'con', 'prn', 'lpt1', 'com1', 'goto'
}

PS_IGNORES = {
    'if', 'else', 'elseif', 'for', 'foreach', 'while', 'do', 'until', 'switch', 'function',
    'filter', 'workflow', 'class', 'enum', 'using', 'param', 'return', 'exit', 'break',
    'continue', 'throw', 'try', 'catch', 'finally', 'trap', 'in', 'process', 'begin', 'end',
    'write-host', 'write-output', 'write-error', 'write-warning', 'write-verbose',
    'write-debug', 'out-null', 'get-command', 'get-member', 'set-variable', 'get-variable',
    'new-object', 'select-object', 'where-object', 'foreach-object', 'import-module',
    'export-modulemember', 'get-module', 'remove-module', 'set-strictmode', 'start-sleep'
}

# Regex to find commands in lines
# Matches words after pipeline, delimiters, control operators, or subshells
BASH_CMD_PATTERN = re.compile(
    r'(?:^|[|&;$(]|\b(?:then|else|do)\b)\s*(?:sudo\s+)?(?P<cmd>[a-zA-Z0-9_\-\./]+)',
    re.MULTILINE
)

BAT_CMD_PATTERN = re.compile(
    r'(?:^|&|\||\b(?:do)\b)\s*(?:call\s+)?(?P<cmd>[a-zA-Z0-9_\-\./\\]+)',
    re.MULTILINE | re.IGNORECASE
)

PS_CMD_PATTERN = re.compile(
    r'(?:^|[|&;{$(])\s*(?P<cmd>[a-zA-Z0-9_\-\./\\]+)',
    re.MULTILINE
)

def parse_shell_commands(file_path: str) -> List[Tuple[str, int]]:
    """Parse commands and their line numbers from a shell script file."""
    ext = os.path.splitext(file_path)[1].lower()
    commands = []
    
    if ext in ('.sh', '.bash', ''):
        pattern = BASH_CMD_PATTERN
        ignores = BASH_IGNORES
    elif ext in ('.bat', '.cmd'):
        pattern = BAT_CMD_PATTERN
        ignores = BAT_IGNORES
    elif ext in ('.ps1', '.psm1'):
        pattern = PS_CMD_PATTERN
        ignores = PS_IGNORES
    else:
        return []

    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            for idx, line in enumerate(f, 1):
                # Clean comments
                if ext in ('.ps1', '.psm1'):
                    line = line.split('#')[0]
                elif ext in ('.bat', '.cmd'):
                    # Check for REM or :: comments
                    line_upper = line.upper().strip()
                    if line_upper.startswith('REM') or line_upper.startswith('::'):
                        continue
                    line = line.split('::')[0]
                else:
                    line = line.split('#')[0]
                    
                line = line.strip()
                if not line:
                    continue
                    
                for match in pattern.finditer(line):
                    cmd = match.group('cmd').strip()
                    
                    # Remove surrounding quotes if any
                    cmd = cmd.strip('\'"')
                    
                    if not cmd:
                        continue
                        
                    # Skip variables (like $VAR or %VAR%)
                    if cmd.startswith('$') or (cmd.startswith('%') and cmd.endswith('%')):
                        continue
                        
                    # Skip environment assignments (e.g. VAR=val)
                    if '=' in cmd:
                        continue
                        
                    # Extract command name from path if absolute/relative path is used
                    cmd_name = os.path.basename(cmd)
                    if not cmd_name:
                        continue
                        
                    # Skip common build tool options/parameters
                    if cmd_name.startswith('-'):
                        continue
                        
                    if cmd_name.lower() in ignores:
                        continue
                        
                    commands.append((cmd, idx))
    except Exception as e:
        print(f"{RED}Error reading {file_path}: {e}{RESET}", file=sys.stderr)
        
    return commands

def verify_command(cmd: str, script_dir: str) -> str:
    """
    Checks the status of a command.
    Returns: 'AVAILABLE', 'MISSING', 'LOCAL_FILE', or 'BUILTIN'
    """
    # Check if local file / path
    if '/' in cmd or '\\' in cmd:
        # Check absolute or relative to script directory
        resolved_path = os.path.abspath(os.path.join(script_dir, cmd))
        if os.path.exists(resolved_path) or os.path.exists(resolved_path + '.exe') or os.path.exists(resolved_path + '.bat') or os.path.exists(resolved_path + '.cmd'):
            return 'LOCAL_FILE'
        return 'MISSING'

    # Check path
    if shutil.which(cmd) is not None:
        return 'AVAILABLE'
        
    # Check common builtins that might not be in path
    if cmd.lower() in ('mkdir', 'rmdir', 'del', 'copy', 'move', 'cls', 'dir', 'type', 'echo'):
        return 'BUILTIN'
        
    return 'MISSING'

def check_dependencies(paths: List[str]) -> Dict[str, Dict[str, Any]]:
    """Scan and verify dependencies in paths."""
    results = {}
    
    # Resolve files
    target_files = []
    for path in paths:
        if os.path.isfile(path):
            target_files.append(path)
        elif os.path.isdir(path):
            for root, _, files in os.walk(path):
                # Exclude venv, node_modules, etc.
                if any(x in root for x in ('venv', '.venv', 'node_modules', '.git', '__pycache__')):
                    continue
                for file in files:
                    if file.endswith(('.sh', '.bash', '.bat', '.cmd', '.ps1')):
                        target_files.append(os.path.join(root, file))
                        
    if not target_files:
        return results

    print(f"{BOLD}{CYAN}Scanning {len(target_files)} scripts for dependencies...{RESET}\n")
    
    for file in target_files:
        script_dir = os.path.dirname(file)
        parsed_cmds = parse_shell_commands(file)
        
        if not parsed_cmds:
            continue
            
        file_rel = os.path.relpath(file)
        results[file_rel] = {}
        
        for cmd, line in parsed_cmds:
            status = verify_command(cmd, script_dir)
            if cmd not in results[file_rel]:
                results[file_rel][cmd] = {
                    'status': status,
                    'lines': [line]
                }
            else:
                if line not in results[file_rel][cmd]['lines']:
                    results[file_rel][cmd]['lines'].append(line)
                    
    return results

def main():
    parser = argparse.ArgumentParser(
        description="Scan shell scripts to extract and validate command dependencies.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/shell_dependency_checker.py script.sh
  python tools/shell_dependency_checker.py tools/
        """
    )
    parser.add_argument("paths", nargs="+", help="File or directory path(s) to scan")
    
    args = parser.parse_args()
    
    results = check_dependencies(args.paths)
    
    if not results:
        print(f"{YELLOW}No shell scripts or command dependencies found.{RESET}")
        sys.exit(0)
        
    has_missing = False
    
    for file, cmds in sorted(results.items()):
        print(f"{BOLD}{CYAN}Script: {file}{RESET}")
        print("-" * 60)
        
        for cmd, details in sorted(cmds.items()):
            status = details['status']
            lines_str = ", ".join(map(str, details['lines']))
            
            if status == 'AVAILABLE':
                status_colored = f"{GREEN}[AVAILABLE]{RESET}"
            elif status == 'LOCAL_FILE':
                status_colored = f"{CYAN}[LOCAL FILE]{RESET}"
            elif status == 'BUILTIN':
                status_colored = f"{GREEN}[SHELL BUILTIN]{RESET}"
            else:
                status_colored = f"{RED}[MISSING]{RESET}"
                has_missing = True
                
            print(f"  {status_colored:<25} {cmd:<20} (line {lines_str})")
        print()
        
    if has_missing:
        print(f"{BOLD}{RED}Verification failed: some script dependencies are missing on this system!{RESET}")
        sys.exit(1)
    else:
        print(f"{BOLD}{GREEN}Verification successful: all dependencies are resolved!{RESET}")
        sys.exit(0)

if __name__ == "__main__":
    main()
