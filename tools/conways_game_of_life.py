#!/usr/bin/env python3
"""
Conway's Game of Life
An interactive, cross-platform terminal-based simulator for Conway's Game of Life.
Allows real-time pause/resume, speed adjustment, drawing cells via a keyboard-controlled cursor,
random generation, and loading classic presets (Glider, Pulsar, Glider Gun, Beacon) using Unicode blocks.
"""

import argparse
import os
import random
import sys
import time

# Reconfigure stdout to UTF-8 on Windows for Unicode block character support
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

# Platform-specific non-blocking keyboard input
try:
    import msvcrt
    WINDOWS = True
except ImportError:
    WINDOWS = False
    import select
    import termios
    import tty


class KeyboardInput:
    """Handles cross-platform non-blocking keyboard input."""
    def __enter__(self):
        if not WINDOWS:
            self.old_settings = termios.tcgetattr(sys.stdin)
            tty.setcbreak(sys.stdin.fileno())
        return self

    def __exit__(self, type, value, traceback):
        if not WINDOWS:
            termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)

    def get_char(self) -> str:
        """Returns key pressed without blocking, or empty string if no key."""
        if WINDOWS:
            if msvcrt.kbhit():
                char = msvcrt.getch()
                # Handle arrow keys/special keys in Windows
                if char in (b"\x00", b"\xe0"):
                    next_char = msvcrt.getch()
                    if next_char == b"H": return "UP"
                    if next_char == b"P": return "DOWN"
                    if next_char == b"K": return "LEFT"
                    if next_char == b"M": return "RIGHT"
                try:
                    return char.decode("utf-8")
                except UnicodeDecodeError:
                    return ""
            return ""
        else:
            dr, dw, de = select.select([sys.stdin], [], [], 0)
            if dr:
                char = sys.stdin.read(1)
                # Handle escape sequences (like arrow keys)
                if char == "\x1b":
                    # Read rest of sequence
                    seq = sys.stdin.read(2)
                    if seq == "[A": return "UP"
                    if seq == "[B": return "DOWN"
                    if seq == "[D": return "LEFT"
                    if seq == "[C": return "RIGHT"
                return char
            return ""


class GameOfLife:
    # Classic presets
    PRESETS = {
        "glider": [(0, 1), (1, 2), (2, 0), (2, 1), (2, 2)],
        "beacon": [(0, 0), (0, 1), (1, 0), (1, 1), (2, 2), (2, 3), (3, 2), (3, 3)],
        "pulsar": [
            (2, 4), (2, 5), (2, 6), (2, 10), (2, 11), (2, 12),
            (7, 4), (7, 5), (7, 6), (7, 10), (7, 11), (7, 12),
            (9, 4), (9, 5), (9, 6), (9, 10), (9, 11), (9, 12),
            (14, 4), (14, 5), (14, 6), (14, 10), (14, 11), (14, 12),
            (4, 2), (5, 2), (6, 2), (10, 2), (11, 2), (12, 2),
            (4, 7), (5, 7), (6, 7), (10, 7), (11, 7), (12, 7),
            (4, 9), (5, 9), (6, 9), (10, 9), (11, 9), (12, 9),
            (4, 14), (5, 14), (6, 14), (10, 14), (11, 14), (12, 14)
        ],
        "glider_gun": [
            (5, 1), (5, 2), (6, 1), (6, 2),
            (5, 11), (6, 11), (7, 11), (4, 12), (8, 12), (3, 13), (9, 13), (3, 14), (9, 14),
            (6, 15), (4, 16), (8, 16), (5, 17), (6, 17), (7, 17), (6, 18),
            (3, 21), (4, 21), (5, 21), (3, 22), (4, 22), (5, 22), (2, 23), (6, 23),
            (1, 25), (2, 25), (6, 25), (7, 25),
            (3, 35), (4, 35), (3, 36), (4, 36)
        ]
    }

    def __init__(self, height: int, width: int, speed: float, wrap: bool):
        self.height = height
        self.width = width
        self.speed = speed  # Delay in seconds between steps
        self.wrap = wrap
        self.grid = [[0 for _ in range(width)] for _ in range(height)]
        self.paused = True
        self.generation = 0
        self.cursor_y = height // 2
        self.cursor_x = width // 2
        self.unicode_chars = self._check_unicode_support()

    def _check_unicode_support(self) -> bool:
        encoding = sys.stdout.encoding or "utf-8"
        try:
            "█".encode(encoding)
            "═".encode(encoding)
            return True
        except UnicodeEncodeError:
            return False

    def clear(self):
        self.grid = [[0 for _ in range(self.width)] for _ in range(self.height)]
        self.generation = 0

    def randomize(self, density: float = 0.2):
        self.clear()
        for y in range(self.height):
            for x in range(self.width):
                if random.random() < density:
                    self.grid[y][x] = 1

    def load_preset(self, name: str):
        self.clear()
        if name not in self.PRESETS:
            return
        cells = self.PRESETS[name]
        
        # Center the preset in the grid
        min_y = min(c[0] for c in cells)
        max_y = max(c[0] for c in cells)
        min_x = min(c[1] for c in cells)
        max_x = max(c[1] for c in cells)
        
        offset_y = (self.height - (max_y - min_y)) // 2 - min_y
        offset_x = (self.width - (max_x - min_x)) // 2 - min_x
        
        for y, x in cells:
            target_y = y + offset_y
            target_x = x + offset_x
            if 0 <= target_y < self.height and 0 <= target_x < self.width:
                self.grid[target_y][target_x] = 1

    def step(self):
        new_grid = [[0 for _ in range(self.width)] for _ in range(self.height)]
        active = False
        
        for y in range(self.height):
            for x in range(self.width):
                # Count neighbors
                neighbors = 0
                for dy in [-1, 0, 1]:
                    for dx in [-1, 0, 1]:
                        if dy == 0 and dx == 0:
                            continue
                        
                        ny, nx = y + dy, x + dx
                        
                        if self.wrap:
                            ny %= self.height
                            nx %= self.width
                            neighbors += self.grid[ny][nx]
                        else:
                            if 0 <= ny < self.height and 0 <= nx < self.width:
                                neighbors += self.grid[ny][nx]
                
                # Apply rules
                if self.grid[y][x] == 1:
                    if neighbors in [2, 3]:
                        new_grid[y][x] = 1
                        active = True
                else:
                    if neighbors == 3:
                        new_grid[y][x] = 1
                        active = True
                        
        self.grid = new_grid
        self.generation += 1
        return active

    def render(self):
        # ANSI Escape codes
        CLEAR_SCREEN = "\033[H\033[J"
        BOLD = "\033[1m"
        RESET = "\033[0m"
        BLUE = "\033[34m"
        GREEN = "\033[32m"
        CYAN = "\033[36m"
        YELLOW = "\033[33m"
        REVERSE = "\033[7m"

        cell_char = "█" if self.unicode_chars else "#"
        dead_char = " "
        
        border_top = "═" if self.unicode_chars else "-"
        border_side = "║" if self.unicode_chars else "|"
        corner_tl = "╔" if self.unicode_chars else "+"
        corner_tr = "╗" if self.unicode_chars else "+"
        corner_bl = "╚" if self.unicode_chars else "+"
        corner_br = "╝" if self.unicode_chars else "+"

        output = []
        
        # Header
        status_text = f"{GREEN}RUNNING{RESET}" if not self.paused else f"{YELLOW}PAUSED (Edit Mode){RESET}"
        output.append(f"{BOLD}Conway's Game of Life - Gen: {self.generation} | Status: {status_text} | Delay: {self.speed:.2f}s{RESET}\n")
        
        # Top border
        output.append(BLUE + corner_tl + border_top * self.width + corner_tr + RESET + "\n")
        
        # Grid cells
        for y in range(self.height):
            row = [BLUE + border_side + RESET]
            for x in range(self.width):
                is_cursor = (y == self.cursor_y and x == self.cursor_x and self.paused)
                cell = self.grid[y][x]
                
                if is_cursor:
                    if cell:
                        row.append(REVERSE + CYAN + cell_char + RESET)
                    else:
                        row.append(REVERSE + "░" + RESET)
                else:
                    if cell:
                        row.append(GREEN + cell_char + RESET)
                    else:
                        row.append(dead_char)
            row.append(BLUE + border_side + RESET + "\n")
            output.append("".join(row))
            
        # Bottom border
        output.append(BLUE + corner_bl + border_top * self.width + corner_br + RESET + "\n")
        
        # Instruction Dashboard
        output.append(f"{BOLD}Controls:{RESET}\n")
        output.append(f" [Space]  Pause/Resume   [S] Single Step     [R] Randomize     [C] Clear\n")
        output.append(f" [Arrows] Move Cursor    [Enter] Toggle Cell  [+/-] Speed Up/Down\n")
        output.append(f" [1-4]    Presets (1: Glider, 2: Beacon, 3: Pulsar, 4: Glider Gun)\n")
        output.append(f" [Q]      Quit\n")
        
        # Print all at once to minimize flicker
        sys.stdout.write(CLEAR_SCREEN + "".join(output))
        sys.stdout.flush()


def main():
    parser = argparse.ArgumentParser(description="Terminal Conway's Game of Life Simulator")
    parser.add_argument("--height", type=int, default=20, help="Grid height (default: 20)")
    parser.add_argument("--width", type=int, default=50, help="Grid width (default: 50)")
    parser.add_argument("--speed", type=float, default=0.1, help="Simulation step delay in seconds (default: 0.1)")
    parser.add_argument("--density", type=float, default=0.2, help="Random density (default: 0.2)")
    parser.add_argument("--wrap", action="store_true", help="Wrap around grid edges (toroidal grid)")
    args = parser.parse_args()

    # Hide cursor in terminal
    sys.stdout.write("\033[?25l")
    sys.stdout.flush()

    game = GameOfLife(args.height, args.width, args.speed, args.wrap)
    game.randomize(args.density)

    try:
        with KeyboardInput() as key_in:
            while True:
                game.render()
                
                # Check for keyboard inputs
                char = key_in.get_char()
                if char.lower() == "q":
                    break
                elif char == " ":
                    game.paused = not game.paused
                elif char.lower() == "s":
                    if game.paused:
                        game.step()
                elif char.lower() == "r":
                    game.randomize(args.density)
                elif char.lower() == "c":
                    game.clear()
                elif char == "+":
                    game.speed = max(0.01, game.speed - 0.02)
                elif char == "-":
                    game.speed = min(2.0, game.speed + 0.02)
                elif char == "UP":
                    game.cursor_y = (game.cursor_y - 1) % game.height
                elif char == "DOWN":
                    game.cursor_y = (game.cursor_y + 1) % game.height
                elif char == "LEFT":
                    game.cursor_x = (game.cursor_x - 1) % game.width
                elif char == "RIGHT":
                    game.cursor_x = (game.cursor_x + 1) % game.width
                elif char == "\n" or char == "\r":
                    if game.paused:
                        game.grid[game.cursor_y][game.cursor_x] = 1 - game.grid[game.cursor_y][game.cursor_x]
                elif char == "1":
                    game.load_preset("glider")
                elif char == "2":
                    game.load_preset("beacon")
                elif char == "3":
                    game.load_preset("pulsar")
                elif char == "4":
                    game.load_preset("glider_gun")

                # Step the game if running
                if not game.paused:
                    game.step()
                    time.sleep(game.speed)
                else:
                    time.sleep(0.05)  # Idle loop sleep when paused
    finally:
        # Restore cursor in terminal
        sys.stdout.write("\033[?25h\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
