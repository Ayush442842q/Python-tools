#!/usr/bin/env python3
"""
Terminal Slideshow - Present markdown files in your terminal.

This tool parses markdown files, splits them into slides using '---', and
provides an interactive terminal-based slide presenter.

Usage:
    python tools/terminal_slideshow.py slides.md [options]
"""

import os
import sys
import argparse
import shutil
import textwrap
from typing import List

# Key codes for cross-platform navigation
KEY_QUIT = 'quit'
KEY_NEXT = 'next'
KEY_PREV = 'prev'


def parse_args():
    parser = argparse.ArgumentParser(
        description="Terminal Slideshow - Interactive Markdown slide presenter in the terminal."
    )
    parser.add_argument("file", help="Markdown file containing slides (separated by '---')")
    parser.add_argument(
        "-w", "--width", type=int, default=80, help="Maximum slide text width (default: 80)"
    )
    parser.add_argument(
        "--no-border", action="store_true", help="Disable drawing ASCII borders around slides"
    )
    return parser.parse_args()


def get_keypress() -> str:
    """Reads a single keypress from the terminal (cross-platform)."""
    # Windows implementation
    try:
        import msvcrt
        while True:
            if msvcrt.kbhit():
                ch = msvcrt.getch()
                if ch in (b'\x00', b'\xe0'):  # Arrow keys prefix
                    ch2 = msvcrt.getch()
                    if ch2 == b'K':  # Left arrow
                        return KEY_PREV
                    elif ch2 == b'M':  # Right arrow
                        return KEY_NEXT
                elif ch.lower() in (b'q', b'\x1b'):  # 'q' or Esc
                    return KEY_QUIT
                elif ch.lower() in (b'n', b' ', b'\r'):  # 'n', Space, or Enter
                    return KEY_NEXT
                elif ch.lower() in (b'p', b'\x08'):  # 'p' or Backspace
                    return KEY_PREV
    except ImportError:
        pass

    # Unix (macOS/Linux) implementation
    try:
        import termios
        import tty
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(fd)
            ch = sys.stdin.read(1)
            if ch == '\x1b':  # Escape sequence (e.g. arrow keys)
                # Read next two characters
                ch2 = sys.stdin.read(2)
                if ch2 == '[D':  # Left arrow
                    return KEY_PREV
                elif ch2 == '[C':  # Right arrow
                    return KEY_NEXT
            elif ch.lower() in ('q', '\x1b'):
                return KEY_QUIT
            elif ch.lower() in ('n', ' ', '\r', '\n'):
                return KEY_NEXT
            elif ch.lower() in ('p', '\x7f'):  # 'p' or backspace
                return KEY_PREV
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    except Exception:
        # Fallback to standard input if tty is not available
        try:
            inp = input().strip().lower()
            if inp in ('q', 'exit', 'quit'):
                return KEY_QUIT
            elif inp in ('p', 'prev', 'back'):
                return KEY_PREV
            else:
                return KEY_NEXT
        except (KeyboardInterrupt, EOFError):
            return KEY_QUIT

    return KEY_NEXT


def parse_slides(filepath: str) -> List[List[str]]:
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: File '{filepath}' not found.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)

    # Split content by markdown thematic breaks (lines containing only --- or *** or ___)
    raw_slides = re_split_slides(content)
    
    slides = []
    for raw in raw_slides:
        lines = [line.rstrip() for line in raw.strip('\n').splitlines()]
        # Remove leading/trailing empty lines per slide
        while lines and not lines[0]:
            lines.pop(0)
        while lines and not lines[-1]:
            lines.pop()
        if lines:
            slides.append(lines)
            
    if not slides:
        slides = [["# Empty Presentation", "Add content separated by '---'"]]
        
    return slides


def re_split_slides(text: str) -> List[str]:
    # Matches lines with 3 or more dashes, asterisks, or underscores (with optional spaces)
    import re
    pattern = re.compile(r'\n[ \t]*[-*_]{3,}[ \t]*\n')
    return pattern.split('\n' + text + '\n')


def render_slide(slide_lines: List[str], current: int, total: int, max_width: int, draw_border: bool):
    # Clear terminal screen
    os.system('cls' if os.name == 'nt' else 'clear')

    # Get actual console size
    console_cols, console_rows = shutil.get_terminal_size((80, 24))
    
    # Calculate rendering width (clamped to terminal width and max_width)
    width = min(max_width, console_cols - 6)
    if width < 20:
        width = 20

    # Wrap and format slide content
    formatted_lines = []
    for line in slide_lines:
        if line.startswith('#'):
            # Heading formatting
            level = len(line) - len(line.lstrip('#'))
            title = line.lstrip('#').strip()
            # Double line divider for main heading, single line for subheadings
            if level == 1:
                formatted_lines.append("")
                formatted_lines.extend(textwrap.wrap(f"★ {title.upper()} ★", width=width))
                formatted_lines.append("=" * len(title.upper()))
                formatted_lines.append("")
            else:
                formatted_lines.append("")
                formatted_lines.extend(textwrap.wrap(title, width=width))
                formatted_lines.append("-" * len(title))
        elif line.startswith('- ') or line.startswith('* '):
            # Bullet items
            bullet_indent = "  • "
            wrapped = textwrap.wrap(line[2:], width=width - len(bullet_indent))
            if wrapped:
                formatted_lines.append(bullet_indent + wrapped[0])
                for w in wrapped[1:]:
                    formatted_lines.append("    " + w)
        else:
            # Standard paragraphs
            if not line:
                formatted_lines.append("")
            else:
                formatted_lines.extend(textwrap.wrap(line, width=width))

    # Add spacing to center vertically if terminal is tall enough
    content_height = len(formatted_lines)
    max_content_rows = console_rows - 6  # Reserve rows for margins, status, border
    top_margin = max(1, (max_content_rows - content_height) // 2) if content_height < max_content_rows else 1

    # Render with/without ASCII borders
    if draw_border:
        # Top border
        print("┌" + "─" * (width + 4) + "┐")
        for _ in range(top_margin):
            print("│" + " " * (width + 4) + "│")
            
        for line in formatted_lines:
            # Crop line if it exceeds width somehow
            line_str = line[:width]
            padding = " " * (width - len(line_str))
            print(f"│  {line_str}{padding}  │")
            
        # Fill remaining vertical space
        remaining_rows = max(1, max_content_rows - content_height - top_margin)
        for _ in range(remaining_rows):
            print("│" + " " * (width + 4) + "│")
            
        # Footer inside border
        footer = f"Slide {current}/{total}"
        controls = "[←] Prev  [→] Next  [Q] Quit"
        space_len = (width + 4) - len(footer) - len(controls) - 4
        space = " " * max(1, space_len)
        print(f"│  {footer}{space}{controls}  │")
        
        # Bottom border
        print("└" + "─" * (width + 4) + "┘")
    else:
        # Borderless rendering
        for _ in range(top_margin):
            print()
        for line in formatted_lines:
            print("  " + line)
        remaining_rows = max(1, max_content_rows - content_height - top_margin)
        for _ in range(remaining_rows):
            print()
        footer = f"Slide {current}/{total}"
        controls = "[P] Prev  [N] Next  [Q] Quit"
        space = " " * max(1, (width - len(footer) - len(controls)))
        print(f"  {footer}{space}{controls}")
        print()


def main():
    args = parse_args()
    slides = parse_slides(args.file)
    total_slides = len(slides)
    current_index = 0

    while True:
        render_slide(
            slides[current_index],
            current_index + 1,
            total_slides,
            args.width,
            not args.no_border
        )
        
        key = get_keypress()
        if key == KEY_QUIT:
            break
        elif key == KEY_NEXT:
            if current_index < total_slides - 1:
                current_index += 1
        elif key == KEY_PREV:
            if current_index > 0:
                current_index -= 1

    # Clear terminal when exiting
    os.system('cls' if os.name == 'nt' else 'clear')
    print("Presentation finished.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
