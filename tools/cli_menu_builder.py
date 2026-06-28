#!/usr/bin/env python3
"""
Interactive CLI Menu and Prompt Builder
--------------------------------------
A utility to generate interactive command-line surveys, configuration wizards,
and menu selectors. Supports single-select lists, multi-select checkboxes,
text input with validations, hidden password entries, and binary confirmations.

Outputs responses as a formatted JSON structure or environment variable assignments (.env).
Uses native keyboard hooks (msvcrt on Windows, termios/tty on Unix) for smooth interactive controls.

Author: Antigravity
License: MIT
"""

import os
import sys
import json
import re
import argparse
from typing import List, Dict, Any, Optional

# Platform-specific character reading helpers
try:
    import msvcrt
    IS_WINDOWS = True
except ImportError:
    import tty
    import termios
    IS_WINDOWS = False


def get_key() -> str:
    """Read a single keyboard keypress portably."""
    if IS_WINDOWS:
        ch = msvcrt.getch()
        if ch in (b'\x00', b'\xe0'):  # Arrow keys prefix
            ch2 = msvcrt.getch()
            if ch2 == b'H': return "up"
            if ch2 == b'P': return "down"
            if ch2 == b'K': return "left"
            if ch2 == b'M': return "right"
        if ch == b'\r': return "enter"
        if ch == b'\x08': return "backspace"
        if ch == b' ': return "space"
        try:
            return ch.decode('utf-8')
        except UnicodeDecodeError:
            return ""
    else:
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == '\x1b':  # Escape sequence
                ch2 = sys.stdin.read(2)
                if ch2 == '[A': return "up"
                if ch2 == '[B': return "down"
                if ch2 == '[D': return "left"
                if ch2 == '[C': return "right"
            if ch in ('\r', '\n'): return "enter"
            if ch in ('\x7f', '\x08'): return "backspace"
            if ch == ' ': return "space"
            return ch
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


# Styling codes
class ANSI:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    HIDE_CURSOR = "\033[?25l"
    SHOW_CURSOR = "\033[?25h"


def print_prompt(message: str, current_val: str = "") -> None:
    """Prints the prompt line with formatting."""
    sys.stdout.write(f"\r{ANSI.GREEN}?{ANSI.RESET} {ANSI.BOLD}{message}{ANSI.RESET}")
    if current_val:
        sys.stdout.write(f" {ANSI.CYAN}{current_val}{ANSI.RESET}")
    sys.stdout.write("\033[K")
    sys.stdout.flush()


def run_confirm(question: Dict[str, Any]) -> bool:
    """Run a yes/no confirmation prompt."""
    msg = question.get("message", "Confirm?")
    default = question.get("default", True)
    default_str = " (Y/n)" if default else " (y/N)"
    
    print_prompt(msg + default_str)
    
    while True:
        key = get_key().lower()
        if key == "enter":
            res = default
            break
        elif key == "y":
            res = True
            break
        elif key == "n":
            res = False
            break
            
    # Final state print
    status = "Yes" if res else "No"
    sys.stdout.write(f"\r{ANSI.GREEN}✔{ANSI.RESET} {ANSI.BOLD}{msg}{ANSI.RESET} {ANSI.CYAN}{status}{ANSI.RESET}\n")
    return res


def run_text(question: Dict[str, Any]) -> str:
    """Run a freeform text input prompt with optional validation."""
    msg = question.get("message", "Input:")
    default = question.get("default", "")
    regex_str = question.get("regex", "")
    is_password = question.get("type") == "password"
    
    user_input = ""
    default_hint = f" ({default})" if default else ""
    
    # Enable cursor for text input
    sys.stdout.write(ANSI.SHOW_CURSOR)
    
    while True:
        display_val = "*" * len(user_input) if is_password else user_input
        print_prompt(msg + default_hint, display_val)
        
        key = get_key()
        if key == "enter":
            val = user_input.strip() or default
            # Check validation
            if regex_str:
                if not re.match(regex_str, val):
                    sys.stdout.write(f"\n{ANSI.RED}>> Input does not match validation pattern '{regex_str}'. Try again.{ANSI.RESET}\n")
                    user_input = ""
                    continue
            break
        elif key == "backspace":
            user_input = user_input[:-1]
        elif len(key) == 1 and key.isprintable():
            user_input += key
            
    # Final state print
    final_val = "*" * len(val) if is_password else val
    sys.stdout.write(f"\r{ANSI.GREEN}✔{ANSI.RESET} {ANSI.BOLD}{msg}{ANSI.RESET} {ANSI.CYAN}{final_val}{ANSI.RESET}\n")
    return val


def run_select(question: Dict[str, Any]) -> str:
    """Run a single-select list selector."""
    msg = question.get("message", "Choose:")
    choices = question.get("choices", [])
    if not choices:
        return ""
        
    index = 0
    sys.stdout.write(ANSI.HIDE_CURSOR)
    
    try:
        while True:
            # Reprint options
            print_prompt(msg)
            sys.stdout.write("\n")
            for i, choice in enumerate(choices):
                if i == index:
                    sys.stdout.write(f"  {ANSI.CYAN}❯ {choice}{ANSI.RESET}\n")
                else:
                    sys.stdout.write(f"    {choice}\n")
            sys.stdout.flush()
            
            key = get_key()
            
            # Clear previous options printed
            sys.stdout.write(f"\033[{len(choices) + 1}A")
            
            if key == "up":
                index = (index - 1) % len(choices)
            elif key == "down":
                index = (index + 1) % len(choices)
            elif key == "enter":
                selected = choices[index]
                break
    finally:
        sys.stdout.write(ANSI.SHOW_CURSOR)
        
    # Clear the options display fully
    for _ in range(len(choices) + 1):
        sys.stdout.write("\033[K\n")
    sys.stdout.write(f"\033[{len(choices) + 1}A")
    
    sys.stdout.write(f"\r{ANSI.GREEN}✔{ANSI.RESET} {ANSI.BOLD}{msg}{ANSI.RESET} {ANSI.CYAN}{selected}{ANSI.RESET}\n")
    return selected


def run_checkbox(question: Dict[str, Any]) -> List[str]:
    """Run a multi-select checkbox list selector."""
    msg = question.get("message", "Select features:")
    choices = question.get("choices", [])
    if not choices:
        return []
        
    checked = [False] * len(choices)
    index = 0
    
    sys.stdout.write(ANSI.HIDE_CURSOR)
    try:
        while True:
            print_prompt(msg + f" {ANSI.DIM}(Space: select, Enter: done){ANSI.RESET}")
            sys.stdout.write("\n")
            for i, choice in enumerate(choices):
                cursor = "❯" if i == index else " "
                chk = "☒" if checked[i] else "☐"
                color = ANSI.CYAN if i == index else ""
                sys.stdout.write(f"  {color}{cursor} {chk} {choice}{ANSI.RESET}\n")
            sys.stdout.flush()
            
            key = get_key()
            
            # Clear previous lines
            sys.stdout.write(f"\033[{len(choices) + 1}A")
            
            if key == "up":
                index = (index - 1) % len(choices)
            elif key == "down":
                index = (index + 1) % len(choices)
            elif key == "space":
                checked[index] = not checked[index]
            elif key == "enter":
                selected = [choices[i] for i, val in enumerate(checked) if val]
                break
    finally:
        sys.stdout.write(ANSI.SHOW_CURSOR)
        
    # Clear lines
    for _ in range(len(choices) + 1):
        sys.stdout.write("\033[K\n")
    sys.stdout.write(f"\033[{len(choices) + 1}A")
    
    sys.stdout.write(f"\r{ANSI.GREEN}✔{ANSI.RESET} {ANSI.BOLD}{msg}{ANSI.RESET} {ANSI.CYAN}{', '.join(selected)}{ANSI.RESET}\n")
    return selected


def execute_survey(schema: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Runs a series of prompts defined by the schema."""
    answers = {}
    print(f"\n{ANSI.BOLD}{ANSI.CYAN}--- CLI Questionnaire Wizard ---{ANSI.RESET}\n")
    
    for question in schema:
        q_type = question.get("type", "text")
        name = question.get("name")
        if not name:
            continue
            
        # Optional conditional execution depending on previous answers
        when = question.get("when")
        if when:
            try:
                # Simple evaluation helper
                # e.g., "when": "language == 'Python'"
                for key, val in answers.items():
                    locals()[key] = val
                if not eval(when):
                    continue
            except Exception:
                pass  # Skip if eval fails
                
        if q_type == "confirm":
            answers[name] = run_confirm(question)
        elif q_type in ["text", "password"]:
            answers[name] = run_text(question)
        elif q_type == "select":
            answers[name] = run_select(question)
        elif q_type == "checkbox":
            answers[name] = run_checkbox(question)
            
    return answers


def write_env_file(data: Dict[str, Any], filepath: str) -> None:
    """Format dictionary as environment variables (.env)."""
    with open(filepath, "w", encoding="utf-8") as f:
        for k, v in data.items():
            key = k.upper().replace(" ", "_")
            if isinstance(v, list):
                val = ",".join(v)
            else:
                val = str(v)
            f.write(f'{key}="{val}"\n')


def main():
    parser = argparse.ArgumentParser(
        description="Build interactive CLI menus, prompts, and config wizards from JSON schemas."
    )
    parser.add_argument("--schema", help="Path to JSON schema file defining questions")
    parser.add_argument("--output", help="Output filename for responses (JSON or .env format)")
    parser.add_argument("--format", choices=["json", "env"], default="json", help="Output file formatting")
    
    args = parser.parse_args()

    # Default questions if schema isn't provided
    default_schema = [
        {
            "type": "text",
            "name": "project_name",
            "message": "Enter project name:",
            "default": "python-project",
            "regex": "^[a-zA-Z0-9_-]+$"
        },
        {
            "type": "select",
            "name": "language_flavor",
            "message": "Select project template language flavor:",
            "choices": ["Standard Python 3.9+", "Flask Web Server", "FastAPI Core Services", "Command Line Tool"]
        },
        {
            "type": "checkbox",
            "name": "components",
            "message": "Select dev packages to preinstall:",
            "choices": ["pytest", "black/flake8", "sphinx-docs", "dockerfile", "mypy-types"]
        },
        {
            "type": "confirm",
            "name": "git_init",
            "message": "Initialize new Git repository?",
            "default": True
        },
        {
            "type": "password",
            "name": "api_secret",
            "message": "Enter default local API Encryption Secret:",
            "when": "'dockerfile' in components"
        }
    ]

    schema = default_schema
    if args.schema:
        if not os.path.exists(args.schema):
            print(f"Error: Schema file not found: {args.schema}", file=sys.stderr)
            return 1
        try:
            with open(args.schema, "r", encoding="utf-8") as f:
                schema = json.load(f)
        except Exception as e:
            print(f"Error parsing schema file: {e}", file=sys.stderr)
            return 1

    try:
        answers = execute_survey(schema)
    except Exception as e:
        print(f"\nSurvey interrupted or failed: {e}", file=sys.stderr)
        return 1

    # Output responses
    print(f"\n{ANSI.BOLD}{ANSI.GREEN}Responses Gathered:{ANSI.RESET}")
    print(json.dumps(answers, indent=2))

    if args.output:
        try:
            if args.format == "env":
                write_env_file(answers, args.output)
            else:
                with open(args.output, "w", encoding="utf-8") as f:
                    json.dump(answers, f, indent=2)
            print(f"\nSaved answers to {args.output}")
        except Exception as e:
            print(f"Failed to save output to {args.output}: {e}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
