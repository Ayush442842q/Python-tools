#!/usr/bin/env python3
"""
Gitmoji Formatter
An interactive developer utility to format and lint git commit messages with Gitmojis.
Supports conventional commits and pre-commit/prepare-commit-msg hooks.
"""

import argparse
import os
import sys

# Core Gitmoji database
GITMOJIS = [
    {"emoji": "✨", "code": ":sparkles:", "prefix": "feat", "desc": "Introduce new features"},
    {"emoji": "🐛", "code": ":bug:", "prefix": "fix", "desc": "Fix a bug"},
    {"emoji": "📝", "code": ":memo:", "prefix": "docs", "desc": "Add or update documentation"},
    {"emoji": "🎨", "code": ":art:", "prefix": "style", "desc": "Improve structure / format of the code (formatting, CSS)"},
    {"emoji": "⚡️", "code": ":zap:", "prefix": "perf", "desc": "Improve performance"},
    {"emoji": "🔥", "code": ":fire:", "prefix": "remove", "desc": "Remove code or files"},
    {"emoji": "♻️", "code": ":recycle:", "prefix": "refactor", "desc": "Refactor code"},
    {"emoji": "✅", "code": ":white_check_mark:", "prefix": "test", "desc": "Add, update, or pass tests"},
    {"emoji": "🔒️", "code": ":lock:", "prefix": "security", "desc": "Fix security issues"},
    {"emoji": "🚀", "code": ":rocket:", "prefix": "deploy", "desc": "Deploy stuff"},
    {"emoji": "👷", "code": ":construction_worker:", "prefix": "ci", "desc": "CI build system / workflow changes"},
    {"emoji": "🔧", "code": ":wrench:", "prefix": "config", "desc": "Add or update configuration files"},
    {"emoji": "📦️", "code": ":package:", "prefix": "chore", "desc": "Add or update compiled files or packages"},
    {"emoji": "🏷️", "code": ":label:", "prefix": "types", "desc": "Add or update types / metadata"},
    {"emoji": "💥", "code": ":boom:", "prefix": "breaking", "desc": "Introduce breaking changes"},
    {"emoji": "⏪️", "code": ":rewind:", "prefix": "revert", "desc": "Revert changes"},
    {"emoji": "🚧", "code": ":construction:", "prefix": "wip", "desc": "Work in progress"},
]

def list_gitmojis(search_query=None):
    """Print the available Gitmojis matching an optional search query."""
    print(f"{'Emoji':5} | {'Code':18} | {'Prefix':10} | {'Description'}")
    print("-" * 80)
    for g in GITMOJIS:
        if search_query:
            q = search_query.lower()
            if q not in g["code"] and q not in g["prefix"] and q not in g["desc"].lower():
                continue
        print(f"{g['emoji']:5} | {g['code']:18} | {g['prefix']:10} | {g['desc']}")

def find_by_prefix(prefix):
    """Find the Gitmoji dictionary matching a conventional commit prefix."""
    prefix = prefix.lower().strip()
    for g in GITMOJIS:
        if g["prefix"] == prefix:
            return g
    return None

def format_message(msg, use_code=False):
    """
    Format a commit message. If it starts with a conventional commit pattern (e.g. 'feat(scope): ...'),
    insert the matching gitmoji at the front.
    """
    msg = msg.strip()
    # Check for prefix pattern: prefix(scope): or prefix:
    prefix = ""
    rest = ""
    
    if ":" in msg:
        header, rest = msg.split(":", 1)
        # Parse header
        if "(" in header and header.endswith(")"):
            # Format: prefix(scope)
            prefix = header.split("(", 1)[0].strip()
        else:
            prefix = header.strip()
            
    g = find_by_prefix(prefix)
    if g:
        emoji_str = g["code"] if use_code else g["emoji"]
        # Avoid prepending if it's already there
        if msg.startswith(g["emoji"]) or msg.startswith(g["code"]):
            return msg
        return f"{emoji_str} {msg}"
    
    return msg

def run_interactive(use_code=False):
    """Interactively build a commit message."""
    print("=== Gitmoji Commit Builder ===")
    print("Select a commit type:")
    for idx, g in enumerate(GITMOJIS):
        print(f"[{idx+1:2d}] {g['emoji']} {g['prefix']:10} - {g['desc']}")
        
    try:
        choice = input(f"\nSelect type (1-{len(GITMOJIS)}): ").strip()
        if not choice:
            print("Cancelled.")
            return
        idx = int(choice) - 1
        if idx < 0 or idx >= len(GITMOJIS):
            print("Invalid selection.")
            return
    except (ValueError, KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        return
        
    g = GITMOJIS[idx]
    
    scope = input("Enter scope (optional, e.g. auth, api): ").strip()
    desc = input("Enter short description: ").strip()
    
    if not desc:
        print("Error: Description is required.")
        return
        
    # Build msg
    emoji_str = g["code"] if use_code else g["emoji"]
    if scope:
        commit_msg = f"{emoji_str} {g['prefix']}({scope}): {desc}"
    else:
        commit_msg = f"{emoji_str} {g['prefix']}: {desc}"
        
    print("\nGenerated Commit Message:")
    print("-" * 40)
    print(commit_msg)
    print("-" * 40)
    
    # Optional action to execute git commit
    confirm = input("Would you like to copy this to clipboard? (y/n): ").strip().lower()
    if confirm == 'y':
        try:
            import subprocess
            if sys.platform == 'win32':
                # Windows clip command
                process = subprocess.Popen('clip', stdin=subprocess.PIPE, shell=True)
                process.communicate(input=commit_msg.encode('utf-16'))
            elif sys.platform == 'darwin':
                # macOS pbcopy
                process = subprocess.Popen('pbcopy', stdin=subprocess.PIPE)
                process.communicate(input=commit_msg.encode('utf-8'))
            else:
                # Linux xclip
                process = subprocess.Popen(['xclip', '-selection', 'clipboard'], stdin=subprocess.PIPE)
                process.communicate(input=commit_msg.encode('utf-8'))
            print("✓ Copied to clipboard!")
        except Exception:
            print("Could not copy to clipboard automatically. Please copy the line manually.")

def run_hook(commit_msg_filepath, use_code=False):
    """
    Process a commit message file (for pre-commit/prepare-commit-msg hook).
    """
    if not os.path.exists(commit_msg_filepath):
        print(f"Error: Commit message file '{commit_msg_filepath}' not found.", file=sys.stderr)
        sys.exit(1)
        
    try:
        with open(commit_msg_filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()
            
        if not lines:
            return
            
        first_line = lines[0]
        # Ignore comments
        if first_line.strip().startswith("#"):
            return
            
        formatted_first_line = format_message(first_line, use_code)
        lines[0] = formatted_first_line
        
        with open(commit_msg_filepath, "w", encoding="utf-8") as f:
            f.writelines(lines)
            
        print("✓ Commit message formatted with Gitmoji.")
    except Exception as e:
        print(f"Error processing hook: {e}", file=sys.stderr)
        sys.exit(1)

def main():
    parser = argparse.ArgumentParser(description="Gitmoji Formatter - standardise git commit messages with emojis")
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-l", "--list", nargs="?", const="", help="List all available Gitmojis (optional search query)")
    group.add_argument("-i", "--interactive", action="store_true", help="Launch interactive commit message builder")
    group.add_argument("-k", "--hook", help="Path to a git COMMIT_EDITMSG file to run in hook mode")
    group.add_argument("-f", "--format", help="Directly format a commit message string")
    
    parser.add_argument("-c", "--use-code", action="store_true",
                        help="Use text codes like ':sparkles:' instead of unicode emojis like '✨'")

    args = parser.parse_args()

    if args.list is not None:
        list_gitmojis(args.list)
    elif args.interactive:
        run_interactive(args.use_code)
    elif args.hook:
        run_hook(args.hook, args.use_code)
    elif args.format:
        print(format_message(args.format, args.use_code))
    else:
        # If no arguments, default to interactive
        run_interactive(args.use_code)

if __name__ == "__main__":
    if sys.platform == 'win32':
        try:
            sys.stdout.reconfigure(encoding='utf-8')
            sys.stderr.reconfigure(encoding='utf-8')
        except AttributeError:
            pass
    main()
