#!/usr/bin/env python3
"""
Conventional Commit Builder with Gitmojis

An interactive CLI tool that guides the user to construct Conventional Commit messages.
Ensures commit standards compliance and optionally commits directly to Git.
"""

import argparse
import os
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

# Configure stdout/stderr encoding to UTF-8 to prevent charmap errors on Windows console redirection
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        try:
            stream.reconfigure(encoding='utf-8')
        except Exception:
            pass

# Conventional commit types with descriptions and matching Gitmojis
COMMIT_TYPES: Dict[str, Tuple[str, str, str]] = {
    "feat": ("A new feature", "✨", ":sparkles:"),
    "fix": ("A bug fix", "🐛", ":bug:"),
    "docs": ("Documentation only changes", "📝", ":memo:"),
    "style": ("Changes that do not affect the meaning of the code (formatting, white-space, etc.)", "🎨", ":art:"),
    "refactor": ("A code change that neither fixes a bug nor adds a feature", "♻️", ":recycle:"),
    "perf": ("A code change that improves performance", "⚡", ":zap:"),
    "test": ("Adding missing tests or correcting existing tests", "✅", ":white_check_mark:"),
    "build": ("Changes that affect the build system or external dependencies", "📦", ":package:"),
    "ci": ("Changes to our CI configuration files and scripts", "👷", ":construction_worker:"),
    "chore": ("Other changes that don't modify src or test files", "🔧", ":wrench:"),
    "revert": ("Reverts a previous commit", "⏪", ":rewind:"),
}

# ANSI colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"

def supports_color() -> bool:
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform or is_a_tty

def color_text(text: str, color_code: str) -> str:
    return f"{color_code}{text}{COLOR_RESET}" if supports_color() else text

def print_banner():
    banner = f"""{COLOR_CYAN}{COLOR_BOLD}
   ┌────────────────────────────────────────────────────────┐
   │             CONVENTIONAL COMMIT BUILDER                │
   │      Interactive Git Commit Formatter & Gitmoji        │
   └────────────────────────────────────────────────────────┘{COLOR_RESET}"""
    print(color_text(banner, COLOR_CYAN))

def get_input(prompt: str, default: str = "", required: bool = False) -> str:
    prompt_str = f"{COLOR_YELLOW}[?]{COLOR_RESET} {prompt}"
    if default:
        prompt_str += f" ({default})"
    prompt_str += ": "
    
    while True:
        try:
            val = input(color_text(prompt_str, COLOR_BOLD)).strip()
            if not val:
                val = default
            if required and not val:
                print(color_text("[-] This field is required.", COLOR_RED))
                continue
            return val
        except (KeyboardInterrupt, EOFError):
            print(color_text("\n[-] Operation cancelled.", COLOR_RED))
            sys.exit(1)

def select_type() -> str:
    print(color_text("\n--- Select Commit Type ---", COLOR_CYAN + COLOR_BOLD))
    types_list = list(COMMIT_TYPES.keys())
    for idx, t in enumerate(types_list):
        desc, emoji_char, _ = COMMIT_TYPES[t]
        name_str = f"{t:<10}"
        print(f"  {color_text(f'[{idx + 1}]', COLOR_GREEN)} {color_text(name_str, COLOR_BOLD)} {emoji_char}  {desc}")
        
    while True:
        choice = get_input("Select type (number or name)", required=True)
        if choice.isdigit():
            val = int(choice) - 1
            if 0 <= val < len(types_list):
                return types_list[val]
        elif choice in COMMIT_TYPES:
            return choice
        print(color_text("[-] Invalid selection.", COLOR_RED))

def check_inside_git_repo() -> bool:
    try:
        res = subprocess.run(
            ["git", "rev-parse", "--is-inside-work-tree"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False
        )
        return res.returncode == 0 and "true" in res.stdout.strip()
    except FileNotFoundError:
        return False

def build_commit_message(
    commit_type: str,
    scope: str,
    description: str,
    body: str,
    breaking: str,
    use_emoji: bool,
    emoji_mode: str
) -> str:
    # 1. Type and Scope
    type_part = commit_type
    if scope:
        type_part += f"({scope})"
    
    # 2. Breaking Change indicator in header
    breaking_indicator = "!" if breaking else ""
    
    # 3. Emoji selection
    emoji_part = ""
    if use_emoji and commit_type in COMMIT_TYPES:
        _, emoji_char, emoji_code = COMMIT_TYPES[commit_type]
        emoji_part = f"{emoji_char if emoji_mode == 'unicode' else emoji_code} "
        
    # Assemble header
    header = f"{type_part}{breaking_indicator}: {emoji_part}{description}"
    
    # Capitalize header description if conventional (some linters prefer lowercase, we keep user input)
    # Check max length (ideal is 50-72 chars)
    if len(header) > 72:
        print(color_text(f"\n[!] Warning: Commit header exceeds 72 characters ({len(header)} chars).", COLOR_YELLOW))
        
    message_parts = [header]
    
    # Assemble body
    if body:
        message_parts.append(f"\n{body}")
        
    # Assemble footer / breaking changes
    if breaking:
        breaking_footer = f"BREAKING CHANGE: {breaking}"
        message_parts.append(f"\n{breaking_footer}")
        
    return "\n".join(message_parts)

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Conventional Commit Builder - Build and execute standard, structured commit messages.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--type", help="Commit type (e.g. feat, fix, docs)")
    parser.add_argument("--scope", help="Optional commit scope")
    parser.add_argument("--desc", help="Short description of changes")
    parser.add_argument("--body", help="Longer body description")
    parser.add_argument("--breaking", help="Breaking change description")
    parser.add_argument("--no-emoji", action="store_true", help="Do not include gitmoji emojis")
    parser.add_argument("--emoji-mode", choices=["unicode", "shortcode"], default="unicode", help="Use unicode characters or markdown shortcodes (e.g., :sparkles:)")
    parser.add_argument("--dry-run", action="store_true", help="Print message and exit without committing")
    parser.add_argument("--commit", action="store_true", help="Run git commit automatically without prompting for confirmation")
    
    args = parser.parse_args()
    
    print_banner()
    
    is_git_repo = check_inside_git_repo()
    if not is_git_repo and not args.dry_run:
        print(color_text("[!] Warning: Current directory is not a Git repository. Defaulting to dry-run mode.", COLOR_YELLOW))
        args.dry_run = True

    # Interactive mode if arguments are missing
    if not args.type:
        commit_type = select_type()
    else:
        commit_type = args.type.lower()
        if commit_type not in COMMIT_TYPES:
            print(color_text(f"[!] Warning: '{commit_type}' is not a standard conventional commit type.", COLOR_YELLOW))

    scope = args.scope if args.scope is not None else get_input("Scope (optional, press Enter to skip)")
    
    if not args.desc:
        while True:
            desc = get_input("Short description (summary)", required=True)
            if len(desc) > 50:
                print(color_text(f"[!] Tip: A concise summary under 50 characters is recommended. (Current: {len(desc)})", COLOR_YELLOW))
            break
    else:
        desc = args.desc

    body = args.body if args.body is not None else get_input("Long body description (optional, press Enter to skip)")
    breaking = args.breaking if args.breaking is not None else get_input("Breaking changes details (optional, press Enter to skip)")
    
    use_emoji = not args.no_emoji
    
    commit_msg = build_commit_message(
        commit_type, scope, desc, body, breaking, use_emoji, args.emoji_mode
    )
    
    print(color_text("\n--- Proposed Commit Message ---", COLOR_CYAN + COLOR_BOLD))
    print(color_text("=" * 40, COLOR_CYAN))
    print(commit_msg)
    print(color_text("=" * 40, COLOR_CYAN))
    
    if args.dry_run:
        print(color_text("\n[i] Dry-run completed. Commit message generated above.", COLOR_CYAN))
        return 0
        
    # Execute Git Commit
    do_commit = args.commit
    if not do_commit:
        confirm = get_input("Do you want to commit these changes? [y/N]", default="n")
        do_commit = confirm.lower() in ("y", "yes")
        
    if do_commit:
        # Check if there are staged changes
        res_staged = subprocess.run(
            ["git", "diff", "--cached", "--quiet"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False
        )
        if res_staged.returncode == 0:
            print(color_text("\n[!] No staged changes found. Please stage files (git add) before committing.", COLOR_YELLOW))
            stage_all = get_input("Stage all modified files and commit? [y/N]", default="n")
            if stage_all.lower() in ("y", "yes"):
                subprocess.run(["git", "add", "."], check=True)
            else:
                print(color_text("[-] Commit aborted because no files are staged.", COLOR_RED))
                return 1
                
        # Write temporary file for git commit message to preserve newlines cleanly
        temp_file_path = ".git_commit_temp_msg.txt"
        try:
            with open(temp_file_path, "w", encoding="utf-8") as f:
                f.write(commit_msg)
            
            commit_res = subprocess.run(
                ["git", "commit", "-F", temp_file_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=False
            )
            
            if commit_res.returncode == 0:
                print(color_text(f"\n[+] Success! Changes committed successfully.", COLOR_GREEN))
                print(commit_res.stdout)
                return 0
            else:
                print(color_text(f"\n[-] Git commit failed:", COLOR_RED))
                print(commit_res.stderr, file=sys.stderr)
                return commit_res.returncode
        finally:
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
    else:
        print(color_text("\n[-] Commit aborted.", COLOR_RED))
        return 0

if __name__ == "__main__":
    sys.exit(main())
