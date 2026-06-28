#!/usr/bin/env python3
"""
Interactive Terminal Paint & Drawing Utility
-------------------------------------------
An interactive CLI drawing tool using curses. Draw blocks or characters
on a grid, change colors, toggle brushes, and export to text or ANSI color files.

Controls:
  Arrow Keys / WASD - Move cursor
  Space             - Paint at cursor
  c / C             - Change paint character / custom character
  1 - 8             - Select Color (1: Red, 2: Green, 3: Yellow, 4: Blue, etc.)
  b / B             - Toggle background color (transparent/colored blocks)
  x / X             - Clear canvas
  s / S             - Save drawing to file
  l / L             - Load drawing from file
  q / Q             - Quit

Author: Antigravity
License: MIT
"""

import os
import sys
import argparse
from typing import List, Tuple, Dict

# Try importing curses safely
try:
    import curses
except ImportError:
    HAS_CURSES = False
else:
    HAS_CURSES = True

# Terminal colors map
COLOR_NAMES = {
    1: ("RED", curses.COLOR_RED if HAS_CURSES else 1),
    2: ("GREEN", curses.COLOR_GREEN if HAS_CURSES else 2),
    3: ("YELLOW", curses.COLOR_YELLOW if HAS_CURSES else 3),
    4: ("BLUE", curses.COLOR_BLUE if HAS_CURSES else 4),
    5: ("MAGENTA", curses.COLOR_MAGENTA if HAS_CURSES else 5),
    6: ("CYAN", curses.COLOR_CYAN if HAS_CURSES else 6),
    7: ("WHITE", curses.COLOR_WHITE if HAS_CURSES else 7),
    8: ("BLACK", curses.COLOR_BLACK if HAS_CURSES else 0),
}


class TerminalPaint:
    def __init__(self, width: int = 60, height: int = 20):
        self.width = width
        self.height = height
        # Canvas holds (char, color_pair_id, is_background_fill)
        self.canvas: List[List[Tuple[str, int, bool]]] = [
            [(" ", 7, False) for _ in range(self.width)] for _ in range(self.height)
        ]
        self.cursor_x = 0
        self.cursor_y = 0
        self.current_char = "█"
        self.current_color = 2  # Green default
        self.bg_fill = True     # Use background fill for colored blocks
        self.status = "Brush: █ | Color: GREEN | Use Arrows/WASD to move, Space to paint, S to save, Q to quit"

    def reset_canvas(self):
        """Clear the canvas."""
        self.canvas = [
            [(" ", 7, False) for _ in range(self.width)] for _ in range(self.height)
        ]
        self.status = "Canvas cleared."

    def save_drawing(self, filepath: str):
        """Save drawing data in a simple format."""
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                # Write header metadata
                f.write(f"# TERMINAL_PAINT {self.width} {self.height}\n")
                for y in range(self.height):
                    row_data = []
                    for x in range(self.width):
                        char, color, bg = self.canvas[y][x]
                        # Encode block securely
                        char_esc = char.replace(" ", "\\s")
                        row_data.append(f"{char_esc},{color},{1 if bg else 0}")
                    f.write(" ".join(row_data) + "\n")
            self.status = f"Saved successfully to {filepath}"
        except Exception as e:
            self.status = f"Save failed: {str(e)}"

    def load_drawing(self, filepath: str) -> bool:
        """Load drawing data from a file."""
        if not os.path.exists(filepath):
            self.status = f"File not found: {filepath}"
            return False
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                lines = f.readlines()
                if not lines or not lines[0].startswith("# TERMINAL_PAINT"):
                    self.status = "Invalid file format."
                    return False
                
                header = lines[0].strip().split()
                w = int(header[2])
                h = int(header[3])
                
                # Resize canvas if needed
                self.width = w
                self.height = h
                self.canvas = [
                    [(" ", 7, False) for _ in range(w)] for _ in range(h)
                ]
                
                for y in range(min(h, len(lines) - 1)):
                    row_data = lines[y + 1].strip().split(" ")
                    for x in range(min(w, len(row_data))):
                        parts = row_data[x].split(",")
                        char = parts[0].replace("\\s", " ")
                        color = int(parts[1])
                        bg = parts[2] == "1"
                        self.canvas[y][x] = (char, color, bg)
            self.status = f"Loaded successfully from {filepath}"
            return True
        except Exception as e:
            self.status = f"Load failed: {str(e)}"
            return False

    def export_ansi_art(self, filepath: str):
        """Export canvas as plain text with ANSI color codes."""
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                for y in range(self.height):
                    line = ""
                    for x in range(self.width):
                        char, color, bg = self.canvas[y][x]
                        if char == " ":
                            line += " "
                        else:
                            # Simple ANSI color escape codes (30-37 foreground, 40-47 background)
                            ansi_fg = 30 + (color % 8) if color != 8 else 30
                            if bg:
                                ansi_bg = 40 + (color % 8) if color != 8 else 40
                                line += f"\033[{ansi_fg};{ansi_bg}m{char}\033[0m"
                            else:
                                line += f"\033[{ansi_fg}m{char}\033[0m"
                    f.write(line + "\n")
            self.status = f"Exported ANSI Art to {filepath}"
        except Exception as e:
            self.status = f"Export failed: {str(e)}"

    def run(self, stdscr):
        """Main drawing loop inside curses."""
        # Initialize color pairs
        curses.start_color()
        curses.use_default_colors()
        
        # Define color pairs: foreground, background
        for color_id, (_, curses_color) in COLOR_NAMES.items():
            # Pair ID matching color ID. Foreground drawing mode
            curses.init_pair(color_id, curses_color, -1)
            # Background block fill pair: identical fore/back color
            curses.init_pair(color_id + 10, curses_color, curses_color)
            
        # Status bar color (yellow on dark background)
        curses.init_pair(99, curses.COLOR_YELLOW, curses.COLOR_BLACK)

        curses.curs_set(1)  # Show cursor
        stdscr.keypad(True)
        stdscr.clear()

        while True:
            height, width = stdscr.getmaxyx()
            
            # Ensure our drawing boundaries fit the terminal screen
            canvas_h = min(self.height, height - 4)
            canvas_w = min(self.width, width - 4)
            
            # Draw frame
            stdscr.attron(curses.color_pair(7))
            stdscr.border()
            stdscr.attroff(curses.color_pair(7))
            
            # Draw Title & Status
            stdscr.addstr(0, 2, " Terminal Paint Studio ", curses.A_BOLD)
            stdscr.addstr(height - 1, 2, f" {self.status[:width-6]} ", curses.color_pair(99))

            # Draw Canvas
            for y in range(canvas_h):
                for x in range(canvas_w):
                    char, color, bg = self.canvas[y][x]
                    # Select appropriate color pair
                    pair_id = color + 10 if (bg and char == "█") else color
                    
                    try:
                        stdscr.addstr(y + 2, x + 2, char, curses.color_pair(pair_id))
                    except curses.error:
                        pass
            
            # Move cursor to current position
            stdscr.move(self.cursor_y + 2, self.cursor_x + 2)
            stdscr.refresh()

            # Read user input
            try:
                ch = stdscr.getch()
            except KeyboardInterrupt:
                break

            # Process keys
            if ch in [ord('q'), ord('Q')]:
                break
            
            # Movement
            elif ch in [curses.KEY_UP, ord('w'), ord('W')]:
                if self.cursor_y > 0:
                    self.cursor_y -= 1
            elif ch in [curses.KEY_DOWN, ord('s'), ord('S')] and not (ch == ord('s') or ch == ord('S')): # Avoid collision with Save
                if self.cursor_y < canvas_h - 1:
                    self.cursor_y += 1
            elif ch in [ord('s'), ord('S')]: # Handle Save explicitly
                # Request filepath in status bar
                stdscr.addstr(height - 1, 2, " Enter Save Filepath: ".ljust(width-6), curses.color_pair(99))
                curses.echo()
                curses.curs_set(1)
                filepath_bytes = stdscr.getstr(height - 1, 24, 40)
                curses.noecho()
                filepath = filepath_bytes.decode("utf-8").strip()
                if filepath:
                    self.save_drawing(filepath)
                    # Also write an ANSI Art version automatically
                    ansi_path = filepath + ".ansi"
                    self.export_ansi_art(ansi_path)
                    self.status = f"Saved data to {filepath} and exported ANSI art to {ansi_path}"
                else:
                    self.status = "Save cancelled."
            elif ch in [ord('l'), ord('L')]: # Handle Load
                stdscr.addstr(height - 1, 2, " Enter Load Filepath: ".ljust(width-6), curses.color_pair(99))
                curses.echo()
                filepath_bytes = stdscr.getstr(height - 1, 24, 40)
                curses.noecho()
                filepath = filepath_bytes.decode("utf-8").strip()
                if filepath:
                    self.load_drawing(filepath)
                else:
                    self.status = "Load cancelled."
            elif ch in [curses.KEY_LEFT, ord('a'), ord('A')]:
                if self.cursor_x > 0:
                    self.cursor_x -= 1
            elif ch in [curses.KEY_RIGHT, ord('d'), ord('D')]:
                if self.cursor_x < canvas_w - 1:
                    self.cursor_x += 1
                    
            # Paint
            elif ch == ord(' '):
                self.canvas[self.cursor_y][self.cursor_x] = (self.current_char, self.current_color, self.bg_fill)
                
            # Erase / Backspace
            elif ch in [ord('e'), ord('E'), curses.KEY_DC, 127, 8]:
                self.canvas[self.cursor_y][self.cursor_x] = (" ", 7, False)
                
            # Change Brush Character
            elif ch in [ord('c'), ord('C')]:
                brush_options = ["█", "░", "▒", "▓", "*", "#", "@", "+", ".", "o", "x"]
                if self.current_char in brush_options:
                    idx = (brush_options.index(self.current_char) + 1) % len(brush_options)
                    self.current_char = brush_options[idx]
                else:
                    self.current_char = "█"
                self.status = f"Brush changed to: '{self.current_char}'"
                
            # Toggle Background Fill Mode
            elif ch in [ord('b'), ord('B')]:
                self.bg_fill = not self.bg_fill
                fill_mode = "Solid BG Fill" if self.bg_fill else "Standard Character"
                self.status = f"Brush mode: {fill_mode}"
                
            # Clear Canvas
            elif ch in [ord('x'), ord('X')]:
                self.reset_canvas()
                
            # Select colors (1-8 keys)
            elif ord('1') <= ch <= ord('8'):
                color_idx = ch - ord('0')
                self.current_color = color_idx
                self.status = f"Color set to: {COLOR_NAMES[color_idx][0]}"


def main():
    parser = argparse.ArgumentParser(
        description="Interactive ANSI/ASCII drawing program in the terminal using curses."
    )
    parser.add_argument("--width", type=int, default=80, help="Canvas width (default: 80)")
    parser.add_argument("--height", type=int, default=24, help="Canvas height (default: 24)")
    parser.add_argument("--load", help="Load an existing drawing file on startup")
    args = parser.parse_args()

    if not HAS_CURSES:
        print("Error: The 'curses' library is required to run this tool.", file=sys.stderr)
        print("On Windows, you can install it using: pip install windows-curses", file=sys.stderr)
        return 1

    app = TerminalPaint(width=args.width, height=args.height)
    if args.load:
        app.load_drawing(args.load)

    # Initialize curses window wrapper
    try:
        curses.wrapper(app.run)
    except Exception as e:
        print(f"Terminal Paint crashed: {e}", file=sys.stderr)
        return 1
    
    print("\nThanks for drawing with Terminal Paint Studio!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
