#!/usr/bin/env python3
"""
Terminal Slideshow Player - Render Markdown files as interactive console slides.

This script parses a Markdown file, splits content by '---', and renders slides
directly in the terminal with colored headers, lists, code blocks, and keyboard navigation.
"""

import os
import sys
import argparse
import shutil

# Try to set up cross-platform key reading
try:
    import msvcrt
    def get_key():
        ch = msvcrt.getch()
        if ch in (b'\x00', b'\xe0'):  # Arrow keys prefix
            ch2 = msvcrt.getch()
            if ch2 == b'M': return 'right'
            if ch2 == b'K': return 'left'
            if ch2 == b'H': return 'up'
            if ch2 == b'P': return 'down'
        elif ch == b' ': return 'space'
        elif ch in (b'\r', b'\n'): return 'enter'
        elif ch in (b'q', b'Q'): return 'q'
        elif ch in (b'r', b'R'): return 'r'
        elif ch in (b'h', b'H'): return 'h'
        return ch.decode('utf-8', errors='ignore').lower()
except ImportError:
    # Unix-like key reader
    def get_key():
        import tty
        import termios
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setraw(sys.stdin.fileno())
            ch = sys.stdin.read(1)
            if ch == '\x1b':
                # Parse escape sequences for arrow keys
                ch2 = sys.stdin.read(2)
                if ch2 == '[C': return 'right'
                if ch2 == '[D': return 'left'
                if ch2 == '[A': return 'up'
                if ch2 == '[B': return 'down'
            elif ch == ' ': return 'space'
            elif ch in ('\r', '\n'): return 'enter'
            elif ch in ('q', 'Q'): return 'q'
            elif ch in ('r', b'R'): return 'r'
            elif ch in ('h', b'H'): return 'h'
            return ch.lower()
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

# ANSI escape codes for coloring
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"
UNDERLINE = "\033[4m"

# Foreground colors
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
CYAN = "\033[36m"
WHITE = "\033[37m"

DEMO_CONTENT = """# Terminal Slideshow Player 🎤
---
## Features ⚡
- **Zero Dependencies**: Pure Python 3.6+ standard library code.
- **Cross-Platform**: Smooth navigation on Windows, macOS, and Linux.
- **Markdown Parsing**: Supports headers, bullet lists, code blocks, and colors.
- **Dynamic Resizing**: Automatically adapts to terminal width/height changes.
---
## Navigation Guide 🧭
Use these keys during the presentation:
- `Right Arrow` or `Space` : Next Slide
- `Left Arrow` or `Backspace` : Previous Slide
- `R` : Refresh / Re-render current slide (helps after resizing)
- `H` : Jump to Home (First Slide)
- `Q` or `Esc` : Exit Slideshow
---
## Code Block Example 💻

```python
# A simple python snippet
def greet(name):
    print(f"Hello, {name}!")

if __name__ == "__main__":
    greet("Antigravity")
```

---
## The End 🎬
Thank you for trying out **Terminal Slideshow Player**!
Create your own slide decks using markdown files separated by `---` dividers.
"""

def parse_slides(text):
    """Split input text into slides by horizontal rules (---)"""
    raw_slides = text.split('\n---\n')
    slides = []
    for s in raw_slides:
        # Strip leading/trailing empty lines of slide content
        lines = s.split('\n')
        while lines and not lines[0].strip():
            lines.pop(0)
        while lines and not lines[-1].strip():
            lines.pop()
        if lines:
            slides.append(lines)
    return slides

def colorize_line(line, in_code_block):
    """Add ANSI escape codes to a single line based on simple markdown parsing"""
    if in_code_block:
        return YELLOW + line + RESET
    
    stripped = line.strip()
    if not stripped:
        return line
    
    # Headers
    if stripped.startswith('# '):
        return BOLD + CYAN + line + RESET
    elif stripped.startswith('## '):
        return BOLD + BLUE + line + RESET
    elif stripped.startswith('### '):
        return BOLD + GREEN + line + RESET
    elif stripped.startswith('#### '):
        return BOLD + MAGENTA + line + RESET
        
    # Bullet lists
    if stripped.startswith('- ') or stripped.startswith('* '):
        parts = line.split(stripped[0], 1)
        return parts[0] + GREEN + "•" + RESET + parts[1]
    
    # Inline formatting (bold, italic, code)
    # Simple replacement rules (non-nested)
    import re
    # Bold **text**
    line = re.sub(r'\*\*(.*?)\*\*', BOLD + r'\1' + RESET, line)
    # Italic *text*
    line = re.sub(r'\*(.*?)\*', ITALIC + r'\1' + RESET, line)
    # Code `inline`
    line = re.sub(r'`(.*?)`', MAGENTA + r'\1' + RESET, line)
    
    return line

def render_slide(slide_lines, current_index, total_slides):
    """Draw a single slide centered on the terminal screen"""
    term_width, term_height = shutil.get_terminal_size((80, 24))
    
    # Clear screen and move cursor to top-left
    if os.name == 'nt':
        os.system('cls')
    else:
        sys.stdout.write("\033[2J\033[H")
        sys.stdout.flush()
        
    content_lines = []
    in_code_block = False
    
    for line in slide_lines:
        if line.strip().startswith('```'):
            in_code_block = not in_code_block
            continue
        content_lines.append(colorize_line(line, in_code_block))
        
    # Calculate vertical padding
    # Reserve 3 lines for status bar/border
    padding_top = max(0, (term_height - len(content_lines) - 3) // 2)
    
    # Print top padding
    print('\n' * padding_top, end='')
    
    # Print slide content
    for line in content_lines:
        # Standard indent to prevent text hugging the left edge
        print("  " + line)
        
    # Fill remaining space
    padding_bottom = max(0, term_height - len(content_lines) - padding_top - 3)
    print('\n' * padding_bottom, end='')
    
    # Render Status Bar
    status_text = f" Slide {current_index + 1} of {total_slides} "
    nav_help = " [←/→ Navigate | R: Refresh | H: Home | Q: Exit] "
    
    # Pad to term_width
    space_between = max(1, term_width - len(status_text) - len(nav_help) - 4)
    status_bar = BOLD + BLUE + " " + "═" * (term_width - 2) + "\n " + RESET + \
                 BOLD + WHITE + status_text + RESET + \
                 " " * space_between + \
                 DIM + nav_help + RESET
    print(status_bar)

def run_slideshow(slides):
    if not slides:
        print("No slide content to display.")
        return
        
    current_slide = 0
    total = len(slides)
    
    # Enable terminal VT processing on Windows (if needed for ANSI colors)
    if os.name == 'nt':
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        
    while True:
        render_slide(slides[current_slide], current_slide, total)
        key = get_key()
        
        if key in ('right', 'space', 'n'):
            if current_slide < total - 1:
                current_slide += 1
        elif key in ('left', 'backspace', 'p'):
            if current_slide > 0:
                current_slide -= 1
        elif key == 'h':
            current_slide = 0
        elif key == 'r':
            # Re-render current slide
            continue
        elif key in ('q', 'exit', '\x1b'):
            break

def main():
    parser = argparse.ArgumentParser(
        description="Terminal Slideshow Player - Interactive Markdown presentations in the console."
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="Path to the Markdown file (.md). If omitted, a demo presentation runs."
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Run the built-in demo presentation"
    )
    
    args = parser.parse_args()
    
    if args.demo or not args.file:
        print("Starting demo presentation...")
        slides = parse_slides(DEMO_CONTENT)
    else:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                content = f.read()
            slides = parse_slides(content)
        except Exception as e:
            print(f"Error reading file '{args.file}': {e}", file=sys.stderr)
            sys.exit(1)
            
    try:
        run_slideshow(slides)
    except KeyboardInterrupt:
        pass
    finally:
        # Clear screen on exit
        if os.name == 'nt':
            os.system('cls')
        else:
            print("\033[2J\033[H", end="")
        print("Slideshow finished. Have a great day!")

if __name__ == "__main__":
    main()
