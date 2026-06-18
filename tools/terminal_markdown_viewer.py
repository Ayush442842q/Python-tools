#!/usr/bin/env python3
"""
Terminal Markdown Viewer
Parses Markdown files and renders them beautifully inside the terminal with formatting,
colors, blockquotes, code-block syntax highlighting, and styled headers.

Usage:
    python tools/terminal_markdown_viewer.py path/to/file.md
    python tools/terminal_markdown_viewer.py -w 80 path/to/file.md
"""

import argparse
import os
import re
import sys

# ANSI Escape Sequences for formatting
RESET = "\033[0m"
BOLD = "\033[1m"
ITALIC = "\033[3m"
UNDERLINE = "\033[4m"
STRIKETHROUGH = "\033[9m"

# Foreground Colors
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
BLUE = "\033[34m"
GRAY = "\033[90m"
LIGHT_GRAY = "\033[37m"

# Background Colors
BG_DARK_GRAY = "\033[100m"

class TerminalMarkdownViewer:
    def __init__(self, width=80):
        self.width = width
        self.in_code_block = False
        self.code_block_lang = ""
        self.code_lines = []

    def clean_ansi(self, text):
        """Remove ANSI escape codes from text to measure its actual printed length."""
        return re.sub(r'\033\[[0-9;]*m', '', text)

    def colorize_inline(self, text):
        """Apply inline styling (bold, italic, code spans, links) using regex."""
        # Code spans `code`
        text = re.sub(r'`([^`\n]+)`', rf"{BG_DARK_GRAY}{YELLOW}\1{RESET}", text)
        
        # Bold-Italic ***text*** or ___text___
        text = re.sub(r'\*\*\*([^\*\n]+)\*\*\*', rf"{BOLD}{ITALIC}\1{RESET}", text)
        text = re.sub(r'___([^_\n]+)___', rf"{BOLD}{ITALIC}\1{RESET}", text)
        
        # Bold **text** or __text__
        text = re.sub(r'\*\*([^\*\n]+)\*\*', rf"{BOLD}\1{RESET}", text)
        text = re.sub(r'__([^_\n]+)__', rf"{BOLD}\1{RESET}", text)
        
        # Italic *text* or _text_
        text = re.sub(r'\*([^\*\n]+)\*', rf"{ITALIC}\1{RESET}", text)
        text = re.sub(r'_([^_\n]+)_', rf"{ITALIC}\1{RESET}", text)
        
        # Strikethrough ~~text~~
        text = re.sub(r'~~([^~\n]+)~~', rf"{STRIKETHROUGH}\1{RESET}", text)
        
        # Links [text](url) -> text (url in gray)
        text = re.sub(r'\[([^\]\n]+)\]\(([^)\n]+)\)', rf"{UNDERLINE}{CYAN}\1{RESET} {GRAY}(\2){RESET}", text)
        
        # Images ![alt](url) -> Image: alt (url in gray)
        text = re.sub(r'\!\[([^\]\n]+)\]\(([^)\n]+)\)', rf"{BOLD}{MAGENTA}Image: \1{RESET} {GRAY}(\2){RESET}", text)
        
        return text

    def wrap_text(self, text, indent=0):
        """Wrap text to the specified terminal width with support for indentation."""
        words = text.split(' ')
        lines = []
        current_line = []
        current_len = 0
        indent_str = " " * indent

        for word in words:
            word_clean = self.clean_ansi(word)
            if current_len + len(word_clean) + (1 if current_line else 0) > self.width - indent:
                lines.append(indent_str + " ".join(current_line))
                current_line = [word]
                current_len = len(word_clean)
            else:
                current_line.append(word)
                current_len += len(word_clean) + (1 if len(current_line) > 1 else 0)
        
        if current_line:
            lines.append(indent_str + " ".join(current_line))
            
        return "\n".join(lines)

    def colorize_code(self, code, lang):
        """Perform simple, regex-based syntax highlighting on code blocks."""
        lang = lang.lower()
        if lang in ('python', 'py'):
            # Keywords
            keywords = r'\b(def|class|return|if|elif|else|for|while|try|except|finally|import|from|as|with|in|is|not|and|or|lambda|pass|break|continue|None|True|False)\b'
            code = re.sub(keywords, rf"{MAGENTA}\1{RESET}", code)
            # Builtins
            builtins = r'\b(print|len|range|str|int|float|list|dict|set|tuple|open|enumerate|zip|sum|max|min|any|all|abs)\b'
            code = re.sub(builtins, rf"{CYAN}\1{RESET}", code)
            # Comments
            code = re.sub(r'(#[^\n]*)', rf"{GRAY}\1{RESET}", code)
            # Strings
            code = re.sub(r'(\"[^\"]*\"|\'[^\']*\')', rf"{GREEN}\1{RESET}", code)
        elif lang in ('javascript', 'js', 'json'):
            # Keywords
            keywords = r'\b(const|let|var|function|return|if|else|for|while|try|catch|finally|import|export|from|default|class|extends|new|this|null|true|false)\b'
            code = re.sub(keywords, rf"{MAGENTA}\1{RESET}", code)
            # Strings
            code = re.sub(r'(\"[^\"]*\"|\'[^\']*\'|`[^`]*`)', rf"{GREEN}\1{RESET}", code)
            # Comments
            code = re.sub(r'(//[^\n]*|/\*.*?\*/)', rf"{GRAY}\1{RESET}", code)
        elif lang in ('html', 'xml'):
            # Tags
            code = re.sub(r'(</?[a-zA-Z0-9:-]+>?)', rf"{CYAN}\1{RESET}", code)
            # Attributes
            code = re.sub(r'\b([a-zA-Z-]+)=', rf"{YELLOW}\1{RESET}=", code)
            # Strings
            code = re.sub(r'(\"[^\"]*\"|\'[^\']*\')', rf"{GREEN}\1{RESET}", code)
        
        # Add side borders to code block
        styled_lines = []
        for line in code.splitlines():
            styled_lines.append(f"{GRAY}│{RESET} {line}")
        return "\n".join(styled_lines)

    def process_line(self, line):
        """Processes a single line of markdown and outputs the formatted version."""
        stripped = line.rstrip()

        # Handle Code Block Toggles
        if stripped.startswith("```"):
            if self.in_code_block:
                # Close code block
                self.in_code_block = False
                code_content = "\n".join(self.code_lines)
                highlighted = self.colorize_code(code_content, self.code_block_lang)
                self.code_lines = []
                border = f"{GRAY}└" + "─" * (self.width - 2) + f"┘{RESET}"
                return f"{highlighted}\n{border}"
            else:
                # Open code block
                self.in_code_block = True
                self.code_block_lang = stripped[3:].strip()
                border = f"{GRAY}┌── Code: {BOLD}{YELLOW}{self.code_block_lang or 'text'}{RESET}{GRAY} " + "─" * (self.width - 12 - len(self.code_block_lang or 'text')) + f"┐{RESET}"
                return border

        if self.in_code_block:
            self.code_lines.append(line.rstrip('\n'))
            return None

        # Headers (#, ##, ###, etc.)
        header_match = re.match(r'^(#{1,6})\s+(.*)$', stripped)
        if header_match:
            level = len(header_match.group(1))
            content = self.colorize_inline(header_match.group(2))
            
            if level == 1:
                border = f"{BOLD}{CYAN}" + "=" * len(self.clean_ansi(content)) + f"{RESET}"
                return f"\n{BOLD}{CYAN}{content}{RESET}\n{border}"
            elif level == 2:
                border = f"{BOLD}{BLUE}" + "-" * len(self.clean_ansi(content)) + f"{RESET}"
                return f"\n{BOLD}{BLUE}{content}{RESET}\n{border}"
            elif level == 3:
                return f"\n{BOLD}{CYAN}### {content}{RESET}"
            else:
                return f"\n{BOLD}{LIGHT_GRAY}{'#' * level} {content}{RESET}"

        # Horizontal Rule (--- or ***)
        if re.match(r'^(?:-{3,}|\*{3,})$', stripped):
            return f"\n{GRAY}" + "─" * self.width + f"{RESET}\n"

        # Blockquote (>)
        blockquote_match = re.match(r'^>\s?(.*)$', stripped)
        if blockquote_match:
            content = self.colorize_inline(blockquote_match.group(1))
            wrapped = self.wrap_text(content, indent=4)
            # Add blockquote character to the beginning of wrapped lines
            styled_lines = [f" {GRAY}│{RESET} {line.strip()}" for line in wrapped.splitlines()]
            return "\n".join(styled_lines)

        # Unordered Lists (- or * or +)
        list_match = re.match(r'^(\s*)([-\*\+])\s+(.*)$', stripped)
        if list_match:
            indent = len(list_match.group(1))
            bullet = list_match.group(2)
            content = self.colorize_inline(list_match.group(3))
            
            # Map standard bullets to pretty characters
            pretty_bullet = f"{CYAN}•{RESET}" if indent == 0 else f"{YELLOW}◦{RESET}"
            
            wrapped = self.wrap_text(content, indent=indent + 3)
            # Reinsert the bullet at the correct spot
            lines = wrapped.splitlines()
            if lines:
                lines[0] = (" " * indent) + f"{pretty_bullet} " + lines[0][indent + 2:]
            return "\n".join(lines)

        # Ordered Lists (1., 2., etc.)
        ordered_list_match = re.match(r'^(\s*)(\d+\.)\s+(.*)$', stripped)
        if ordered_list_match:
            indent = len(ordered_list_match.group(1))
            num = ordered_list_match.group(2)
            content = self.colorize_inline(ordered_list_match.group(3))
            
            wrapped = self.wrap_text(content, indent=indent + len(num) + 1)
            lines = wrapped.splitlines()
            if lines:
                lines[0] = (" " * indent) + f"{YELLOW}{num}{RESET} " + lines[0][indent + len(num) + 1:]
            return "\n".join(lines)

        # Plain Paragraph / Text
        if stripped:
            content = self.colorize_inline(stripped)
            return self.wrap_text(content)
        else:
            return ""

    def render(self, md_text):
        """Splits markdown into lines, parses them, and yields formatted console output."""
        output = []
        lines = md_text.splitlines()
        for line in lines:
            res = self.process_line(line)
            if res is not None:
                output.append(res)
        return "\n".join(output)

def main():
    parser = argparse.ArgumentParser(
        description="A beautiful Markdown viewer for the terminal."
    )
    parser.add_argument("file", nargs="?", help="Path to the markdown file to view. If empty, reads from stdin.")
    parser.add_argument("-w", "--width", type=int, default=80, help="Formatting width limit (default: 80)")
    
    args = parser.parse_args()

    # Determine width based on terminal size if possible
    try:
        terminal_width = os.get_terminal_size().columns
        width = min(args.width, terminal_width - 2)
    except OSError:
        width = args.width

    viewer = TerminalMarkdownViewer(width=width)

    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                content = f.read()
        except FileNotFoundError:
            print(f"{RED}[ERROR] File '{args.file}' not found.{RESET}", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"{RED}[ERROR] Could not read file: {e}{RESET}", file=sys.stderr)
            sys.exit(1)
    else:
        # Read from stdin
        if sys.stdin.isatty():
            parser.print_help()
            sys.exit(0)
        content = sys.stdin.read()

    rendered = viewer.render(content)
    print(rendered)
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nExiting...")
        sys.exit(1)
