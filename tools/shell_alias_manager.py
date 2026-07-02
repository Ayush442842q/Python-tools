#!/usr/bin/env python3
"""Shell Alias Manager

Parse, analyze, check, and optimize shell aliases and functions across
common shell configuration files (.bashrc, .zshrc, and PowerShell profiles).
"""

import argparse
import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional

# ANSI Colors for formatting
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[34m"
COLOR_CYAN = "\033[36m"
COLOR_GREY = "\033[90m"

# Regular expressions for parsing
RE_BASH_ALIAS = re.compile(r"^\s*alias\s+([a-zA-Z0-9_\-\.\:\+]+)\s*=\s*(['\"]?)(.*?)\2\s*(?:#.*)?$")
RE_BASH_FUNC = re.compile(r"^\s*(?:function\s+)?([a-zA-Z0-9_\-\.]+)\s*\(\s*\)\s*\{")
RE_BASH_FUNC_INLINE = re.compile(r"^\s*function\s+([a-zA-Z0-9_\-\.]+)\s*\{")
RE_PS_ALIAS = re.compile(
    r"^\s*(?:Set|New)-Alias\s+(?:-Name\s+)?([\w\-]+)\s+(?:-Value\s+)?([\w\-\.\\\/\:]+)", re.IGNORECASE
)


class AliasDefinition:
    def __init__(self, name: str, value: str, file_path: Path, line_no: int, is_function: bool = False):
        self.name = name
        self.value = value
        self.file_path = file_path
        self.line_no = line_no
        self.is_function = is_function


def get_default_profile_paths() -> List[Tuple[str, Path]]:
    """Get list of common profile paths on the system."""
    home = Path.home()
    paths = []

    if sys.platform == "win32":
        # PowerShell profiles
        documents = home / "Documents"
        onedrive_docs = home / "OneDrive" / "Documents"
        for doc_dir in [documents, onedrive_docs]:
            ps_profile = doc_dir / "PowerShell" / "Microsoft.PowerShell_profile.ps1"
            if ps_profile.exists():
                paths.append(("PowerShell", ps_profile))
            ps_legacy = doc_dir / "WindowsPowerShell" / "Microsoft.PowerShell_profile.ps1"
            if ps_legacy.exists():
                paths.append(("WindowsPowerShell", ps_legacy))
        
        # Git Bash profile
        git_bash = home / ".bash_profile"
        if git_bash.exists():
            paths.append(("GitBash Profile", git_bash))
        git_bash_rc = home / ".bashrc"
        if git_bash_rc.exists():
            paths.append(("GitBash RC", git_bash_rc))
    else:
        # Unix Shells
        profiles = [
            (".bashrc", "Bash RC"),
            (".bash_profile", "Bash Profile"),
            (".profile", "Profile"),
            (".zshrc", "Zsh RC"),
            (".zsh_profile", "Zsh Profile"),
            (".zshenv", "Zsh Env"),
            (".config/fish/config.fish", "Fish Config"),
        ]
        for rel_path, label in profiles:
            p = home / rel_path
            if p.exists():
                paths.append((label, p))

    return paths


def parse_bash_zsh(file_path: Path) -> List[AliasDefinition]:
    """Parse bash/zsh profile for aliases and function declarations."""
    defs = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for idx, line in enumerate(f, 1):
                # Clean line
                line_stripped = line.strip()
                if not line_stripped or line_stripped.startswith("#"):
                    continue

                # Parse alias
                m_alias = RE_BASH_ALIAS.match(line)
                if m_alias:
                    name, _, value = m_alias.groups()
                    defs.append(AliasDefinition(name, value, file_path, idx))
                    continue

                # Parse function
                m_func = RE_BASH_FUNC.match(line) or RE_BASH_FUNC_INLINE.match(line)
                if m_func:
                    name = m_func.group(1)
                    defs.append(AliasDefinition(name, "(Function block)", file_path, idx, is_function=True))
    except Exception as e:
        print(f"{COLOR_RED}Error reading {file_path}: {e}{COLOR_RESET}")
    return defs


def parse_powershell(file_path: Path) -> List[AliasDefinition]:
    """Parse PowerShell profile for Set-Alias or New-Alias calls."""
    defs = []
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            for idx, line in enumerate(f, 1):
                line_stripped = line.strip()
                if not line_stripped or line_stripped.startswith("#") or line_stripped.startswith("<#"):
                    continue

                m_alias = RE_PS_ALIAS.match(line)
                if m_alias:
                    name, value = m_alias.groups()
                    defs.append(AliasDefinition(name, value, file_path, idx))
    except Exception as e:
        print(f"{COLOR_RED}Error reading {file_path}: {e}{COLOR_RESET}")
    return defs


def parse_profile(file_path: Path, shell_type: str) -> List[AliasDefinition]:
    """Parse target file depending on its shell type."""
    if "powershell" in shell_type.lower():
        return parse_powershell(file_path)
    return parse_bash_zsh(file_path)


def which(cmd: str) -> bool:
    """Check if command exists in system PATH."""
    # Clean cmd (extract first word)
    cmd = cmd.strip().split()[0] if cmd.strip() else ""
    if not cmd:
        return False
        
    # Strip quotes if any
    cmd = cmd.replace('"', '').replace("'", "")
    
    # Handle absolute paths
    if os.path.isabs(cmd):
        return os.path.exists(cmd) and os.access(cmd, os.X_OK)

    # Search PATH
    path_exts = os.environ.get("PATHEXT", "").split(os.pathsep) if sys.platform == "win32" else [""]
    for path_dir in os.environ.get("PATH", "").split(os.pathsep):
        if not path_dir:
            continue
        p = Path(path_dir)
        for ext in path_exts:
            full_path = p / (cmd + ext)
            try:
                if full_path.is_file() and os.access(full_path, os.X_OK):
                    return True
            except PermissionError:
                continue
    return False


def find_cycles(aliases: Dict[str, str]) -> List[List[str]]:
    """Find circular dependencies in alias values."""
    cycles = []
    visited = {}  # name -> state (0 = visiting, 1 = visited)

    def dfs(node: str, path: List[str]):
        if node in visited:
            if visited[node] == 0:  # Back edge found
                cycle_start = path.index(node)
                cycles.append(path[cycle_start:] + [node])
            return

        # Simple extraction of the first token as the next link
        tokens = aliases[node].strip().split()
        if not tokens:
            return
            
        next_cmd = tokens[0].replace('"', '').replace("'", "")
        if next_cmd in aliases:
            visited[node] = 0
            path.append(node)
            dfs(next_cmd, path)
            path.pop()

        visited[node] = 1

    for name in aliases:
        if name not in visited:
            dfs(name, [])
    return cycles


def main():
    parser = argparse.ArgumentParser(
        description="Shell Alias Manager - Audits shell configuration file aliases and functions."
    )
    parser.add_argument(
        "-f", "--file",
        help="Specific shell configuration file to audit (defaults to auto-detected system profiles)"
    )
    parser.add_argument(
        "-t", "--type",
        choices=["bash", "zsh", "powershell"],
        help="Specify shell configuration file type when using -f (default: auto-detected)"
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Check if the targets of the aliases/functions are valid executables in PATH"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output the parsed and audited definitions as JSON"
    )
    args = parser.parse_args()

    # Determine files to audit
    targets = []
    if args.file:
        file_path = Path(args.file).resolve()
        if not file_path.exists():
            print(f"{COLOR_RED}Error: File '{file_path}' does not exist.{COLOR_RESET}", file=sys.stderr)
            sys.exit(1)
        
        # Determine shell type
        shell_type = args.type
        if not shell_type:
            if file_path.suffix == ".ps1" or "powershell" in file_path.name.lower():
                shell_type = "powershell"
            elif "zsh" in file_path.name:
                shell_type = "zsh"
            else:
                shell_type = "bash"
        targets.append((shell_type, file_path))
    else:
        targets = get_default_profile_paths()

    if not targets:
        print(f"{COLOR_YELLOW}No shell configuration files detected automatically.{COLOR_RESET}")
        print("Please specify a profile file using --file /path/to/profile")
        sys.exit(0)

    # Parse definitions
    all_defs: List[AliasDefinition] = []
    for label, path in targets:
        defs = parse_profile(path, label)
        all_defs.extend(defs)

    if not all_defs:
        print(f"{COLOR_YELLOW}No aliases or functions found in audited profiles.{COLOR_RESET}")
        sys.exit(0)

    # Pre-process for analysis
    alias_dict = {d.name: d.value for d in all_defs if not d.is_function}
    by_name = defaultdict(list)
    for d in all_defs:
        by_name[d.name].append(d)

    # Audit validation
    validated_results = {}
    if args.validate:
        for name, d_list in by_name.items():
            primary = d_list[0]
            if primary.is_function:
                validated_results[name] = True
            else:
                # Check target
                target = primary.value
                # If target is another alias, it's checked transitively
                visited = {name}
                while target.split()[0].replace('"', '').replace("'", "") in alias_dict:
                    next_target_name = target.split()[0].replace('"', '').replace("'", "")
                    if next_target_name in visited:
                        break
                    visited.add(next_target_name)
                    target = alias_dict[next_target_name]
                
                first_cmd = target.split()[0] if target.split() else ""
                # Some symbols or builtins are always valid
                builtins = {"cd", "echo", "pwd", "exit", "history", "set", "export", "unset", "source", "read", "local", "return"}
                if first_cmd in builtins:
                    validated_results[name] = True
                else:
                    validated_results[name] = which(first_cmd)

    # Detect cycles
    cycles = find_cycles(alias_dict)

    # Output JSON if requested
    if args.json:
        import json
        out_list = []
        for name, d_list in by_name.items():
            for d in d_list:
                out_list.append({
                    "name": d.name,
                    "value": d.value,
                    "file": str(d.file_path),
                    "line": d.line_no,
                    "is_function": d.is_function,
                    "is_valid": validated_results.get(name, None) if args.validate else None
                })
        print(json.dumps({
            "definitions": out_list,
            "cycles": cycles
        }, indent=4))
        sys.exit(0)

    # CLI Dashboard Output
    print(f"\n{COLOR_BOLD}{COLOR_CYAN}=== Shell Alias Manager Audit ==={COLOR_RESET}\n")
    print(f"{COLOR_BOLD}Profiles Scanned:{COLOR_RESET}")
    for label, path in targets:
        print(f"  - {COLOR_GREEN}{label}{COLOR_RESET}: {path}")
    print()

    print(f"{COLOR_BOLD}Found {len(all_defs)} definitions ({len(alias_dict)} aliases, {len(all_defs) - len(alias_dict)} functions).{COLOR_RESET}\n")

    # Grouped report
    duplicates = {name: d_list for name, d_list in by_name.items() if len(d_list) > 1}
    invalid_aliases = [name for name, valid in validated_results.items() if not valid] if args.validate else []

    # Print general definitions
    print(f"{COLOR_BOLD}{COLOR_BLUE}--- Definitions List ---{COLOR_RESET}")
    for name, d_list in sorted(by_name.items()):
        primary = d_list[0]
        type_str = f"{COLOR_CYAN}[Func]{COLOR_RESET}" if primary.is_function else f"{COLOR_GREEN}[Alias]{COLOR_RESET}"
        
        # Build file trace
        file_ref = f"{primary.file_path.name}:{primary.line_no}"
        
        valid_marker = ""
        if args.validate:
            if validated_results.get(name, False):
                valid_marker = f" {COLOR_GREEN}(ok){COLOR_RESET}"
            else:
                valid_marker = f" {COLOR_RED}(broken target: {primary.value.split()[0]}){COLOR_RESET}"
        
        print(f"  {type_str} {COLOR_BOLD}{name}{COLOR_RESET} = {primary.value}  {COLOR_GREY}({file_ref}){COLOR_RESET}{valid_marker}")
        if len(d_list) > 1:
            print(f"    {COLOR_YELLOW}! Overridden {len(d_list)-1} time(s) in:{COLOR_RESET}")
            for extra in d_list[1:]:
                print(f"      - {extra.file_path.name}:{extra.line_no} ({extra.value})")
    print()

    # Alerts & Issues Summary
    has_issues = False
    if duplicates or invalid_aliases or cycles:
        print(f"{COLOR_BOLD}{COLOR_RED}--- Found Issues/Warnings ---{COLOR_RESET}")
        has_issues = True

        if duplicates:
            print(f"\n  {COLOR_YELLOW}{COLOR_BOLD}Duplicate / Overridden Declarations:{COLOR_RESET}")
            for name, d_list in duplicates.items():
                print(f"    - '{name}' is defined {len(d_list)} times:")
                for d in d_list:
                    print(f"      * {d.file_path}:{d.line_no} -> {d.value}")

        if invalid_aliases:
            print(f"\n  {COLOR_RED}{COLOR_BOLD}Broken Targets (Executable not in PATH):{COLOR_RESET}")
            for name in invalid_aliases:
                val = alias_dict.get(name, "Function")
                print(f"    - '{name}' = {val}")

        if cycles:
            print(f"\n  {COLOR_RED}{COLOR_BOLD}Circular Dependencies Detected:{COLOR_RESET}")
            for cycle in cycles:
                print(f"    - {' -> '.join(cycle)}")
        print()

    if not has_issues and args.validate:
        print(f"{COLOR_GREEN}{COLOR_BOLD}✔ No duplicate, broken, or circular alias definitions found!{COLOR_RESET}\n")


if __name__ == "__main__":
    main()
