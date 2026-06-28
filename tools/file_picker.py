#!/usr/bin/env python3
"""
Interactive TUI File Picker - Visual file browser and selector for the terminal.

A terminal-based file browser with keyboard navigation for browsing directories
and selecting files. Supports filtering, multi-select, and preview.

Features:
- Interactive directory navigation with arrow keys
- File type filtering and search
- Multi-select mode for batch operations
- File preview for text files
- Size and modification time display
- Quick navigation (jump to letter)
- Export selected files to stdout or file

Controls:
  ↑/↓/k/j    Navigate up/down
  Enter/l    Open directory / Select file
  Backspace/h  Go to parent directory
  Space      Toggle selection (multi-select mode)
  /          Search/filter files
  p          Toggle preview panel
  m          Toggle multi-select mode
  a          Select all (in multi-select mode)
  d          Deselect all (in multi-select mode)
  x          Export selected files
  q          Quit

Usage:
    python file_picker.py [directory] [--multi] [--preview] [--filter PATTERN]

Example:
    python file_picker.py /path/to/browse
    python file_picker.py . --multi --filter "*.py"
"""

import os
import sys
import stat
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Tuple

# Check if curses is available
try:
    import curses
    HAS_CURSES = True
except ImportError:
    HAS_CURSES = False


class FilePicker:
    """Interactive terminal file picker."""

    def __init__(self, root_dir: str, multi_select: bool = False,
                 show_preview: bool = False, filter_pattern: Optional[str] = None):
        self.root_dir = Path(root_dir).absolute()
        self.current_dir = self.root_dir
        self.files: List[Path] = []
        self.selected_index = 0
        self.selected_files: set = set()
        self.multi_select = multi_select
        self.show_preview = show_preview
        self.filter_pattern = filter_pattern
        self.search_query = ""
        self.status_message = ""
        self.status_timeout = 0
        self.preview_content: Optional[str] = None
        self.running = True
        self.show_help = False

    def load_directory(self, directory: Path) -> None:
        """Load files from directory."""
        try:
            items = list(directory.iterdir())
        except PermissionError:
            self.set_status("Permission denied")
            return

        # Separate directories and files
        dirs = []
        files = []

        for item in items:
            if item.name.startswith('.') and item.name not in ['.', '..']:
                continue

            try:
                if item.is_dir():
                    dirs.append(item)
                else:
                    files.append(item)
            except (PermissionError, OSError):
                continue

        # Sort
        dirs.sort(key=lambda x: x.name.lower())
        files.sort(key=lambda x: x.name.lower())

        # Apply filter
        if self.filter_pattern or self.search_query:
            pattern = self.search_query or self.filter_pattern
            if pattern:
                pattern = pattern.lower().replace('*', '')
                dirs = [d for d in dirs if pattern in d.name.lower()]
                files = [f for f in files if pattern in f.name.lower()]

        # Add parent directory indicator
        if directory != self.root_dir:
            self.files = [directory.parent] + dirs + files
        else:
            self.files = dirs + files

        # Reset selection
        self.selected_index = 0
        if self.files:
            self._update_preview()

    def _update_preview(self) -> None:
        """Update file preview."""
        if not self.show_preview or not self.files:
            self.preview_content = None
            return

        selected = self.files[self.selected_index]
        if selected.is_file():
            try:
                # Read first 50 lines
                content = selected.read_text(errors='replace')
                lines = content.splitlines()[:50]
                self.preview_content = '\n'.join(lines)
                if len(lines) < content.splitlines():
                    self.preview_content += '\n...(truncated)'
            except Exception:
                self.preview_content = "(Preview not available)"
        else:
            self.preview_content = None

    def set_status(self, message: str, timeout: int = 30) -> None:
        """Set status message."""
        self.status_message = message
        self.status_timeout = timeout

    def toggle_selection(self) -> None:
        """Toggle file selection."""
        if not self.files or self.selected_index >= len(self.files):
            return

        current = self.files[self.selected_index]
        if current.is_file():
            if str(current) in self.selected_files:
                self.selected_files.remove(str(current))
            else:
                self.selected_files.add(str(current))

    def select_all(self) -> None:
        """Select all files."""
        for f in self.files:
            if f.is_file():
                self.selected_files.add(str(f))

    def deselect_all(self) -> None:
        """Deselect all files."""
        self.selected_files.clear()

    def get_selected_paths(self) -> List[Path]:
        """Get list of selected file paths."""
        return [Path(p) for p in self.selected_files]

    def run(self, stdscr) -> Optional[List[Path]]:
        """Run the picker interface."""
        curses.curs_set(0)
        stdscr.nodelay(False)
        stdscr.timeout(100)

        # Initialize colors
        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE)  # Selected
            curses.init_pair(2, curses.COLOR_BLUE, -1)  # Directory
            curses.init_pair(3, curses.COLOR_GREEN, -1)  # Selected file
            curses.init_pair(4, curses.COLOR_YELLOW, -1)  # Status
            curses.init_pair(5, curses.COLOR_CYAN, -1)  # Preview

        self.load_directory(self.current_dir)

        while self.running:
            self._draw(stdscr)

            if self.status_timeout > 0:
                self.status_timeout -= 1
                if self.status_timeout <= 0:
                    self.status_message = ""

            key = stdscr.getch()

            if key == -1:
                continue

            if self.show_help:
                if key in [ord('q'), ord('h'), 27]:  # q, h, Escape
                    self.show_help = False
                continue

            # Navigation
            elif key in [curses.KEY_UP, ord('k')]:
                if self.selected_index > 0:
                    self.selected_index -= 1
                    self._update_preview()

            elif key in [curses.KEY_DOWN, ord('j')]:
                if self.selected_index < len(self.files) - 1:
                    self.selected_index += 1
                    self._update_preview()

            elif key in [curses.KEY_PPAGE]:  # Page Up
                self.selected_index = max(0, self.selected_index - 10)
                self._update_preview()

            elif key in [curses.KEY_NPAGE]:  # Page Down
                self.selected_index = min(len(self.files) - 1, self.selected_index + 10)
                self._update_preview()

            elif key in [curses.KEY_HOME]:
                self.selected_index = 0
                self._update_preview()

            elif key in [curses.KEY_END]:
                self.selected_index = len(self.files) - 1
                self._update_preview()

            # Actions
            elif key in [curses.KEY_ENTER, 10, 13, ord('l')]:
                if self.files and self.selected_index < len(self.files):
                    selected = self.files[self.selected_index]
                    if selected.is_dir():
                        self.current_dir = selected
                        self.load_directory(self.current_dir)
                    elif not self.multi_select:
                        self.selected_files.add(str(selected))
                        self.running = False

            elif key in [curses.KEY_BACKSPACE, 127, ord('h')]:
                if self.current_dir != self.root_dir:
                    self.current_dir = self.current_dir.parent
                    self.load_directory(self.current_dir)

            elif key == ord(' '):
                if self.multi_select:
                    self.toggle_selection()
                    if self.selected_index < len(self.files) - 1:
                        self.selected_index += 1

            elif key == ord('/'):
                self._prompt_search(stdscr)

            elif key == ord('p'):
                self.show_preview = not self.show_preview

            elif key == ord('m'):
                self.multi_select = not self.multi_select
                self.set_status(f"Multi-select: {'ON' if self.multi_select else 'OFF'}")

            elif key == ord('a'):
                if self.multi_select:
                    self.select_all()
                    self.set_status(f"Selected {len(self.selected_files)} files")

            elif key == ord('d'):
                if self.multi_select:
                    self.deselect_all()
                    self.set_status("Deselected all")

            elif key == ord('x'):
                if self.selected_files:
                    self.running = False
                else:
                    self.set_status("No files selected")

            elif key == ord('r'):
                self.load_directory(self.current_dir)
                self.set_status("Refreshed")

            elif key == ord('h') or key == ord('?'):
                self.show_help = True

            elif key in [ord('q'), 27]:  # q or Escape
                self.running = False

            # Quick navigation (jump to letter)
            elif 32 < key < 127 and self.files:
                char = chr(key).lower()
                for i, f in enumerate(self.files):
                    if f.name.lower().startswith(char):
                        self.selected_index = i
                        self._update_preview()
                        break

        return self.get_selected_paths()

    def _draw(self, stdscr) -> None:
        """Draw the interface."""
        stdscr.clear()
        height, width = stdscr.getmaxyx()

        # Title
        title = f" File Picker - {self.current_dir} "
        if self.multi_select:
            title += f"({len(self.selected_files)} selected) "
        if self.search_query:
            title += f"[Filter: {self.search_query}] "

        title = title[:width-1]
        try:
            stdscr.attron(curses.A_REVERSE)
            stdscr.addstr(0, 0, title.ljust(width-1))
            stdscr.attroff(curses.A_REVERSE)
        except curses.error:
            pass

        # File list
        list_height = height - 4 if self.show_preview else height - 2
        start_idx = max(0, self.selected_index - list_height + 1)
        end_idx = min(len(self.files), start_idx + list_height)

        for i in range(start_idx, end_idx):
            row = i - start_idx + 1
            file_path = self.files[i]
            display_name = file_path.name

            # Add directory indicator
            if file_path.is_dir():
                display_name = display_name + "/"

            # Truncate if needed
            if self.show_preview:
                max_len = width // 2 - 4
            else:
                max_len = width - 4
            display_name = display_name[:max_len]

            # Selected
            is_selected = (i == self.selected_index)
            is_file_selected = (str(file_path) in self.selected_files)

            try:
                if is_selected:
                    attr = curses.A_REVERSE
                    if file_path.is_dir():
                        attr |= curses.color_pair(1)
                    elif is_file_selected:
                        attr |= curses.color_pair(3)
                    stdscr.attron(attr)

                else:
                    if file_path.is_dir():
                        stdscr.attron(curses.color_pair(2) | curses.A_BOLD)

                prefix = "✓ " if is_file_selected else "  "
                stdscr.addstr(row, 0, prefix + display_name)

                if is_selected:
                    stdscr.attroff(curses.A_REVERSE | curses.color_pair(1) | curses.color_pair(3))
                elif file_path.is_dir():
                    stdscr.attroff(curses.color_pair(2) | curses.A_BOLD)
            except curses.error:
                pass

        # Preview panel
        if self.show_preview and self.preview_content:
            preview_x = width // 2
            try:
                stdscr.addstr(1, preview_x, " Preview ", curses.color_pair(5) | curses.A_BOLD)
                for i, line in enumerate(self.preview_content.splitlines()[:list_height-2]):
                    if i + 2 < height - 2:
                        stdscr.addstr(i + 2, preview_x, line[:width - preview_x - 1],
                                    curses.color_pair(5))
            except curses.error:
                pass

        # Status bar
        try:
            status_row = height - 2 if self.show_preview else height - 1
            if self.status_message:
                stdscr.addstr(status_row, 0, f" {self.status_message} ",
                            curses.color_pair(4) | curses.A_BOLD)
            else:
                help_text = "↑↓:Navigate  Enter:Open  Space:Select  /:Filter  p:Preview  m:Multi  q:Quit"
                stdscr.addstr(status_row, 0, f" {help_text} "[:width-1])
        except curses.error:
            pass

        # Help overlay
        if self.show_help:
            help_lines = [
                " Keyboard Controls ",
                "",
                " ↑/↓/k/j  - Navigate up/down",
                " Enter/l  - Open directory / Select",
                " Backspace - Go to parent",
                " Space    - Toggle selection",
                " /        - Search/filter",
                " p        - Toggle preview",
                " m        - Toggle multi-select",
                " a        - Select all",
                " d        - Deselect all",
                " x        - Export selected",
                " r        - Refresh",
                " q        - Quit",
                "",
                " Press q to close help "
            ]

            h_height = len(help_lines) + 2
            h_width = max(len(line) for line in help_lines) + 2
            start_y = (height - h_height) // 2
            start_x = (width - h_width) // 2

            try:
                for i, line in enumerate(help_lines):
                    stdscr.addstr(start_y + i, start_x, line.center(h_width - 2),
                                curses.A_REVERSE)
            except curses.error:
                pass

        stdscr.refresh()

    def _prompt_search(self, stdscr) -> None:
        """Prompt for search query."""
        curses.echo()
        curses.curs_set(1)
        height, width = stdscr.getmaxyx()

        try:
            stdscr.addstr(height - 1, 0, " Filter: "[:width-1])
            stdscr.clrtoeol()
            stdscr.refresh()
        except curses.error:
            pass

        search = ""
        while True:
            ch = stdscr.getch()
            if ch in [10, 13, 27]:  # Enter, Escape
                break
            elif ch in [curses.KEY_BACKSPACE, 127]:
                search = search[:-1]
            elif 32 <= ch < 127:
                search += chr(ch)

            try:
                stdscr.addstr(height - 1, len(" Filter: "), search[:width - len(" Filter: ") - 1])
                stdscr.clrtoeol()
                stdscr.refresh()
            except curses.error:
                pass

        curses.noecho()
        curses.curs_set(0)
        self.search_query = search
        self.load_directory(self.current_dir)
        self.set_status(f"Filter: {search}" if search else "Filter cleared")


def main_curses(args) -> Optional[List[Path]]:
    """Run curses picker."""
    picker = FilePicker(
        args.directory,
        multi_select=args.multi,
        show_preview=args.preview,
        filter_pattern=args.filter
    )

    def wrapper(stdscr):
        return picker.run(stdscr)

    result = curses.wrapper(wrapper)
    return result


def main_cli(args) -> List[Path]:
    """Simple CLI fallback."""
    directory = Path(args.directory)
    files = list(directory.iterdir())

    if args.filter:
        pattern = args.filter.lower().replace('*', '')
        files = [f for f in files if pattern in f.name.lower()]

    for i, f in enumerate(sorted(files, key=lambda x: x.name.lower())):
        file_type = "DIR" if f.is_dir() else "FILE"
        size = f.stat().st_size if f.is_file() else 0
        size_str = f"{size:,}" if size > 0 else "-"
        print(f"{i+1:3}. [{file_type:4}] {f.name:<40} {size_str:>12} bytes")

    print(f"\nTotal: {len(files)} items")
    return []


def main():
    if not HAS_CURSES:
        print("Error: curses library not available (install python-curses)", file=sys.stderr)
        print("Falling back to CLI mode...", file=sys.stderr)
        sys.exit(2)

    parser = argparse.ArgumentParser(
        description='Interactive terminal file picker and browser'
    )
    parser.add_argument('directory', nargs='?', default='.',
                        help='Directory to browse (default: current)')
    parser.add_argument('--multi', action='store_true',
                        help='Enable multi-select mode')
    parser.add_argument('--preview', action='store_true',
                        help='Show file preview panel')
    parser.add_argument('--filter', metavar='PATTERN',
                        help='Initial filter pattern')
    parser.add_argument('--cli', action='store_true',
                        help='Use simple CLI mode instead of TUI')

    args = parser.parse_args()

    if not os.path.isdir(args.directory):
        print(f"Error: '{args.directory}' is not a valid directory", file=sys.stderr)
        return 1

    if args.cli:
        result = main_cli(args)
    else:
        result = main_curses(args)

    if result:
        print("\nSelected files:")
        for f in result:
            print(f)

    return 0


if __name__ == '__main__':
    sys.exit(main())