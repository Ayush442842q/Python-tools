#!/usr/bin/env python3
"""
Terminal File Picker - Interactive fuzzy file finder for the terminal.

A fast, interactive file picker with fuzzy search, preview, and action
capabilities. Perfect for quickly finding and opening files in large projects.

Usage:
    python file_picker.py                    # Interactive mode
    python file_picker.py --open             # Open selected file
    python file_picker.py --copy             # Copy path to clipboard
    python file_picker.py --preview          # Show file preview
    python file_picker.py src/               # Search in specific directory
"""

import argparse
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import List, Optional, Tuple


# ANSI color codes
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    CYAN = '\033[36m'
    GREEN = '\033[32m'
    RED = '\033[31m'
    HIGHLIGHT = '\033[7m'


def clear_screen():
    """Clear the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def get_terminal_size() -> Tuple[int, int]:
    """Get terminal dimensions."""
    try:
        cols, rows = shutil.get_terminal_size()
        return cols, rows
    except:
        return 80, 24


def fuzzy_match(pattern: str, text: str) -> Tuple[bool, int]:
    """
    Check if pattern matches text using fuzzy matching.
    Returns (matches, score) where higher score is better.
    """
    if not pattern:
        return True, 0
    
    pattern = pattern.lower()
    text = text.lower()
    
    # Quick check: all chars must be present in order
    pattern_idx = 0
    score = 0
    matches = []
    
    for i, char in enumerate(text):
        if pattern_idx < len(pattern) and char == pattern[pattern_idx]:
            matches.append(i)
            # Bonus for consecutive matches
            if matches and i == matches[-1] + 1:
                score += 2
            # Bonus for word boundaries
            if i == 0 or text[i-1] in '/\\_-':
                score += 3
            pattern_idx += 1
    
    if pattern_idx == len(pattern):
        # Bonus for exact match
        if pattern == text:
            score += 100
        # Bonus for starting match
        if text.startswith(pattern):
            score += 50
        return True, score
    
    return False, 0


def find_files(directory: str = '.', exclude_patterns: List[str] = None) -> List[str]:
    """Find all files in directory."""
    if exclude_patterns is None:
        exclude_patterns = [
            '__pycache__',
            '.git',
            '.svn',
            '.hg',
            'node_modules',
            '.venv',
            'venv',
            'env',
            '.env',
            '*.pyc',
            '*.pyo',
            '*.so',
            '*.dll',
            '*.class',
            '.DS_Store',
            'Thumbs.db',
            '*.min.js',
            '*.min.css'
        ]
    
    files = []
    directory = Path(directory)
    
    if not directory.exists():
        return files
    
    def should_exclude(path: Path) -> bool:
        for pattern in exclude_patterns:
            if pattern.startswith('*'):
                if path.name.endswith(pattern[1:]):
                    return True
            elif pattern in str(path):
                return True
        return False
    
    try:
        for path in directory.rglob('*'):
            if path.is_file() and not should_exclude(path):
                try:
                    rel_path = path.relative_to(directory)
                    files.append(str(rel_path))
                except ValueError:
                    pass
    except PermissionError:
        pass
    
    return sorted(files)


def filter_files(files: List[str], pattern: str) -> List[Tuple[str, int]]:
    """Filter files by fuzzy pattern and return with scores."""
    if not pattern:
        return [(f, 0) for f in files[:100]]  # Limit for empty pattern
    
    results = []
    for file_path in files:
        matches, score = fuzzy_match(pattern, file_path)
        if matches:
            results.append((file_path, score))
    
    # Sort by score descending
    results.sort(key=lambda x: -x[1])
    return results


def highlight_match(text: str, pattern: str) -> str:
    """Highlight matched characters in text."""
    if not pattern:
        return text
    
    pattern_lower = pattern.lower()
    text_lower = text.lower()
    
    result = []
    pattern_idx = 0
    i = 0
    
    while i < len(text):
        if (pattern_idx < len(pattern) and 
            text_lower[i] == pattern_lower[pattern_idx]):
            result.append(f"{Colors.YELLOW}{text[i]}{Colors.RESET}")
            pattern_idx += 1
        else:
            result.append(text[i])
        i += 1
    
    return ''.join(result)


def preview_file(file_path: str, lines: int = 10) -> str:
    """Get preview of file content."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = ''
            for i, line in enumerate(f):
                if i >= lines:
                    break
                content += line
            return content.rstrip()
    except Exception as e:
        return f"[Error: {e}]"


def open_file(file_path: str):
    """Open file with default application."""
    if os.name == 'nt':
        os.startfile(file_path)
    elif os.name == 'darwin':
        subprocess.run(['open', file_path])
    else:
        subprocess.run(['xdg-open', file_path])


def copy_to_clipboard(text: str):
    """Copy text to clipboard."""
    try:
        if os.name == 'nt':
            subprocess.run(['clip'], input=text.encode(), check=True)
        elif subprocess.run(['which', 'xclip'], capture_output=True).returncode == 0:
            subprocess.run(['xclip', '-selection', 'clipboard'], input=text.encode(), check=True)
        elif subprocess.run(['which', 'wl-clipboard'], capture_output=True).returncode == 0:
            subprocess.run(['wl-copy'], input=text.encode(), check=True)
        else:
            print(f"Path: {text}")
    except Exception as e:
        print(f"Could not copy to clipboard: {e}")


class FilePicker:
    """Interactive file picker interface."""
    
    def __init__(self, directory: str = '.'):
        self.directory = Path(directory)
        self.pattern = ''
        self.files: List[str] = []
        self.filtered: List[Tuple[str, int]] = []
        self.selected = 0
        self.scroll_offset = 0
        self.running = True
        self.message = ''
        self.show_preview = False
    
    def load_files(self):
        """Load files from directory."""
        print(f"Scanning {self.directory}...")
        self.files = find_files(str(self.directory))
        print(f"Found {len(self.files)} files")
        self.apply_filter()
    
    def apply_filter(self):
        """Apply current filter pattern."""
        self.filtered = filter_files(self.files, self.pattern)
        self.selected = min(self.selected, max(0, len(self.filtered) - 1))
    
    def render(self):
        """Render the interface."""
        cols, rows = get_terminal_size()
        clear_screen()
        
        # Header
        print(f"{Colors.BOLD}{Colors.BLUE}Terminal File Picker{Colors.RESET}")
        print(f"Directory: {self.directory}")
        print(f"Pattern: {self.pattern}{Colors.DIM} (type to search){Colors.RESET}")
        print(f"Files: {len(self.filtered)}/{len(self.files)}")
        print("-" * cols)
        
        # File list
        list_height = rows - 10 if self.show_preview else rows - 4
        list_height = max(5, list_height)
        
        # Adjust scroll offset
        if self.selected < self.scroll_offset:
            self.scroll_offset = self.selected
        elif self.selected >= self.scroll_offset + list_height:
            self.scroll_offset = self.selected - list_height + 1
        
        for i in range(list_height):
            idx = self.scroll_offset + i
            if idx >= len(self.filtered):
                break
            
            file_path, score = self.filtered[idx]
            is_selected = idx == self.selected
            
            # Format line
            if is_selected:
                prefix = f"{Colors.GREEN}>{Colors.RESET} "
                display = f"{Colors.BOLD}{highlight_match(file_path, self.pattern)}{Colors.RESET}"
            else:
                prefix = "  "
                display = highlight_match(file_path, self.pattern)
            
            # Truncate to fit
            max_len = cols - len(prefix) - 10
            if len(display) > max_len:
                display = '...' + display[-(max_len-3):]
            
            print(f"{prefix}{display}")
        
        # Message
        if self.message:
            print(f"\n{Colors.CYAN}{self.message}{Colors.RESET}")
            self.message = ''
        
        # Preview
        if self.show_preview and self.filtered:
            file_path = self.filtered[self.selected][0]
            full_path = self.directory / file_path
            print(f"\n{Colors.BOLD}Preview: {file_path}{Colors.RESET}")
            preview = preview_file(str(full_path))
            preview_lines = preview.split('\n')[:5]
            for line in preview_lines:
                line = line.expandtabs(4)
                if len(line) > cols - 2:
                    line = line[:cols-5] + '...'
                print(f"{Colors.DIM}  {line}{Colors.RESET}")
        
        # Help
        print(f"\n{Colors.DIM}↑↓ navigate | Enter open | p preview | c copy path | o open | q quit{Colors.RESET}")
    
    def handle_input(self, key: str):
        """Handle keyboard input."""
        if key == 'q' or key == '\x03':  # q or Ctrl+C
            self.running = False
        
        elif key == '\x0d':  # Enter
            if self.filtered:
                file_path = self.filtered[self.selected][0]
                print(f"\nSelected: {file_path}")
                self.result = file_path
                self.running = False
        
        elif key == 'p':
            self.show_preview = not self.show_preview
        
        elif key == 'c':
            if self.filtered:
                file_path = self.filtered[self.selected][0]
                full_path = str((self.directory / file_path).absolute())
                copy_to_clipboard(full_path)
                self.message = f"Copied: {full_path}"
        
        elif key == 'o':
            if self.filtered:
                file_path = self.filtered[self.selected][0]
                full_path = str((self.directory / file_path).absolute())
                open_file(full_path)
                self.message = f"Opened: {file_path}"
        
        elif key == '\x1b[A' or key == 'up':  # Up arrow
            self.selected = max(0, self.selected - 1)
        
        elif key == '\x1b[B' or key == 'down':  # Down arrow
            self.selected = min(len(self.filtered) - 1, self.selected + 1)
        
        elif key == '\x08' or key == '\x7f':  # Backspace
            if self.pattern:
                self.pattern = self.pattern[:-1]
                self.apply_filter()
        
        elif key == '\x15':  # Ctrl+U (clear line)
            self.pattern = ''
            self.apply_filter()
        
        elif len(key) == 1 and key.isprintable():
            self.pattern += key
            self.apply_filter()
    
    def run(self) -> Optional[str]:
        """Run the interactive picker."""
        import tty
        import termios
        
        self.load_files()
        self.result = None
        
        # Save terminal settings
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        
        try:
            tty.setcbreak(fd)
            
            while self.running:
                self.render()
                
                # Read single character
                ch = sys.stdin.read(1)
                
                # Handle escape sequences
                if ch == '\x1b':
                    ch += sys.stdin.read(2)
                
                self.handle_input(ch)
            
            return self.result
        
        except KeyboardInterrupt:
            return None
        
        finally:
            # Restore terminal settings
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)


def main():
    parser = argparse.ArgumentParser(
        description="Interactive terminal file picker with fuzzy search"
    )
    parser.add_argument('directory', nargs='?', default='.',
                        help='Directory to search (default: current)')
    parser.add_argument('--open', '-o', action='store_true',
                        help='Open selected file with default application')
    parser.add_argument('--copy', '-c', action='store_true',
                        help='Copy file path to clipboard')
    parser.add_argument('--preview', '-p', action='store_true',
                        help='Show file preview after selection')
    parser.add_argument('--list', '-l', action='store_true',
                        help='List all files without interactive mode')
    
    args = parser.parse_args()
    
    # Non-interactive list mode
    if args.list:
        files = find_files(args.directory)
        for f in files:
            print(f)
        return
    
    # Interactive mode
    picker = FilePicker(args.directory)
    selected = picker.run()
    
    if selected:
        full_path = str((picker.directory / selected).absolute())
        
        if args.preview:
            print(f"\n{Colors.BOLD}Preview:{Colors.RESET}")
            print(preview_file(full_path))
        
        if args.copy:
            copy_to_clipboard(full_path)
            print(f"Copied to clipboard: {full_path}")
        
        if args.open:
            print(f"Opening: {full_path}")
            open_file(full_path)


if __name__ == '__main__':
    main()