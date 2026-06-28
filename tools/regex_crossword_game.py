#!/usr/bin/env python3
"""
Regex Crossword Terminal Game
An interactive terminal game to learn and practice regular expressions.
Users solve grid puzzles where rows and columns must match specific regex clues.
"""

import argparse
import re
import sys

# ANSI Colors for terminal output
COLOR_HEADER = "\033[95m"
COLOR_BLUE = "\033[94m"
COLOR_GREEN = "\033[92m"
COLOR_WARNING = "\033[93m"
COLOR_FAIL = "\033[91m"
COLOR_END = "\033[0m"
COLOR_BOLD = "\033[1m"


def print_banner():
    banner = f"""{COLOR_HEADER}{COLOR_BOLD}
  ██▀███  ▓█████   ▄████  ▓█████ ▒██   ██▒
 ▓██ ▒ ██▒▓█   ▀  ██▒ ▀█▒ ▓█   ▀ ▒▒ █ █ ▒░
 ▓██ ░▄█ ▒▒███   ▒██░▄▄▄░ ▒███    ░  █   ░
 ▒██▀▀█▄  ▒▓█  ▄ ░▓█  ██▓ ▒▓█  ▄  ░ █ █ ▒ 
 ░██▓ ▒██▒░▒████▒░▒▓███▀▒ ░▒████▒▒██▒ ▒██▒
 ░ ▒▓ ░▒▓░░░ ▒░ ░ ░▒   ▄  ░░ ▒░ ░▒▒ ░ ░▓ ░
   ░▒ ░ ▒░ ░ ░  ░  ░   █    ░ ░  ░░░   ░▒ ░
   ░░   ░    ░    ░   █        ░    ░    ░ 
    ░        ░  ░  ░   ░        ░  ░   ░   
                                           
{COLOR_END}{COLOR_BLUE}              Regular Expression Crossword & CLI Tutor Game{COLOR_END}
"""
    print(banner, file=sys.stderr)


# Define Level Puzzles
LEVELS = [
    {
        "level": 1,
        "title": "Welcome to Regex Crossword!",
        "description": "A warm up with simple literal matches and wildcards.",
        "rows": 2,
        "cols": 2,
        "row_clues": ["^HE$", "^LP$"],
        "col_clues": ["^HL$", "^EP$"],
        "solution": [
            ["H", "E"],
            ["L", "P"]
        ]
    },
    {
        "level": 2,
        "title": "Character Classes",
        "description": "Practicing digit character classes \\d and character ranges [A-Z].",
        "rows": 2,
        "cols": 2,
        "row_clues": ["^A[0-9]$", "^[C-D]\\d$"],
        "col_clues": ["^[AC]+$", "^\\d{2}$"],
        "solution": [
            ["A", "5"],
            ["C", "9"]
        ]
    },
    {
        "level": 3,
        "title": "Negation and Escaping",
        "description": "Watch out for negated sets [^...] and escaped literals like \\?.",
        "rows": 2,
        "cols": 2,
        "row_clues": ["^[^A-C]\\d$", "^[A-Z]\\?$"],
        "col_clues": ["^[D-Z]{2}$", "^\\d\\?$"],
        "solution": [
            ["D", "5"],
            ["X", "?"]
        ]
    },
    {
        "level": 4,
        "title": "The Animal Kingdom",
        "description": "Our first 3x3 puzzle. Combine wildcards, anchors, and sets to spell out words.",
        "rows": 3,
        "cols": 3,
        "row_clues": ["^C.T$", "^D[O-U]G$", "^B\\w{2}$"],
        "col_clues": ["^[C-D]{2}B$", "^[A-E]O[A-E]$", "^T[G-Z]E$"],
        "solution": [
            ["C", "A", "T"],
            ["D", "O", "G"],
            ["B", "E", "E"]
        ]
    },
    {
        "level": 5,
        "title": "The Qualifier Master",
        "description": "Using qualifiers (?, *, +) to match variable lengths.",
        "rows": 3,
        "cols": 3,
        "row_clues": ["^A?B+C$", "^D*E+F?$", "^G+H?I*$"],
        "col_clues": ["^[ADG]+$", "^B*E*H*$", "^C+F*I*$"],
        "solution": [
            ["B", "B", "C"],
            ["D", "E", "F"],
            ["G", "H", "I"]
        ]
    }
]


class RegexCrossword:
    def __init__(self, level_data):
        self.level = level_data["level"]
        self.title = level_data["title"]
        self.description = level_data["description"]
        self.rows = level_data["rows"]
        self.cols = level_data["cols"]
        self.row_clues = level_data["row_clues"]
        self.col_clues = level_data["col_clues"]
        self.solution = level_data["solution"]
        
        # User grid initialized to empty spaces
        self.grid = [[" " for _ in range(self.cols)] for _ in range(self.rows)]

    def display_grid(self):
        print(f"\n{COLOR_BOLD}Level {self.level}: {self.title}{COLOR_END}")
        print(f"{COLOR_BLUE}{self.description}{COLOR_END}\n")
        
        # Print column clues header
        # Find maximum length of column clues to align them vertically
        max_col_clue_len = max(len(c) for c in self.col_clues)
        
        # Print vertical column clues rotated or stacked
        for char_idx in range(max_col_clue_len):
            print(" " * 15, end="")
            for c_idx in range(self.cols):
                clue = self.col_clues[c_idx]
                if char_idx < len(clue):
                    print(f"  {clue[char_idx]}  ", end="")
                else:
                    print("     ", end="")
            print()
            
        # Top boundary line of grid
        print(" " * 15 + "+" + "-----+" * self.cols)
        
        # Print rows, their user values, and the row clues
        for r_idx in range(self.rows):
            # Print cell content row
            row_num_label = f"Row {r_idx + 1}"
            print(f"{row_num_label:<14}|", end="")
            for c_idx in range(self.cols):
                val = self.grid[r_idx][c_idx]
                col_letter = chr(65 + c_idx)
                cell_display = f"{COLOR_GREEN}{val}{COLOR_END}" if val != " " else f"{COLOR_BOLD}{col_letter}{r_idx + 1}{COLOR_END}"
                print(f"  {cell_display}  |", end="")
            print(f"  <- Clue: {COLOR_WARNING}{self.row_clues[r_idx]}{COLOR_END}")
            
            # Bottom boundary line of row
            print(" " * 15 + "+" + "-----+" * self.cols)

    def set_cell(self, cell_ref, val):
        """Set cell e.g. A1 to character val."""
        if len(cell_ref) != 2:
            return False, "Invalid coordinate. Use Letter+Number (e.g. A1)."
            
        col_letter, row_num_str = cell_ref[0].upper(), cell_ref[1]
        
        col_idx = ord(col_letter) - 65
        try:
            row_idx = int(row_num_str) - 1
        except ValueError:
            return False, "Invalid row index. Must be a digit."

        if row_idx < 0 or row_idx >= self.rows or col_idx < 0 or col_idx >= self.cols:
            return False, f"Coordinate {cell_ref} out of grid bounds."

        if len(val) != 1:
            return False, "Value must be a single character."

        self.grid[row_idx][col_idx] = val.upper()
        return True, f"Set {col_letter}{row_idx + 1} to '{val.upper()}'."

    def get_hint(self):
        """Find an empty cell and fill in the correct answer from the solution."""
        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c] == " ":
                    correct_val = self.solution[r][c]
                    self.grid[r][c] = correct_val
                    cell_ref = f"{chr(65 + c)}{r + 1}"
                    return f"Hint: Filled in {cell_ref} with '{correct_val}'."
        return "All cells are already filled! Use 'check' or 'submit' to verify."

    def check_grid(self, quiet=False):
        """Check if rows and columns match their regex constraints."""
        all_match = True
        wrong_rows = []
        wrong_cols = []

        # Check rows
        for r_idx in range(self.rows):
            row_str = "".join(self.grid[r_idx])
            # If there are empty spaces, we fail
            if " " in row_str:
                all_match = False
                continue
            if not re.match(self.row_clues[r_idx], row_str):
                all_match = False
                wrong_rows.append(r_idx + 1)

        # Check columns
        for c_idx in range(self.cols):
            col_str = "".join(self.grid[r][c_idx] for r in range(self.rows))
            if " " in col_str:
                all_match = False
                continue
            if not re.match(self.col_clues[c_idx], col_str):
                all_match = False
                wrong_cols.append(chr(65 + c_idx))

        # Check if identical to solution (as a safety fallback for multiple-matches)
        solution_match = True
        for r in range(self.rows):
            for c in range(self.cols):
                if self.grid[r][c] != self.solution[r][c]:
                    # Check if it still matches the regex (valid alternative solution)
                    pass

        if not quiet:
            if len(wrong_rows) == 0 and len(wrong_cols) == 0 and not all_match:
                print(f"{COLOR_WARNING}Grid is not fully filled yet!{COLOR_END}")
            elif len(wrong_rows) == 0 and len(wrong_cols) == 0 and all_match:
                print(f"{COLOR_GREEN}Success! All constraints matched perfectly!{COLOR_END}")
            else:
                if wrong_rows:
                    print(f"{COLOR_FAIL}Failed Row Clues: {', '.join(f'Row {r}' for r in wrong_rows)}{COLOR_END}")
                if wrong_cols:
                    print(f"{COLOR_FAIL}Failed Column Clues: {', '.join(wrong_cols)}{COLOR_END}")

        return all_match


def play_game():
    print_banner()
    print("Welcome to the Regex Crossword Game!")
    print("Fill in each cell (e.g. A1, B2) with a single character so that")
    print("all row and column regular expression constraints are satisfied.")
    print("\nCommands:")
    print("  <Cell> <Char>  - Set cell value (e.g. 'A1 X')")
    print("  check          - Verify current rows and columns against constraints")
    print("  hint           - Reveal one correct cell")
    print("  reset          - Clear the current grid")
    print("  quit           - Exit the game")
    print("-------------------------------------------------------------")

    current_level_idx = 0
    score = 0

    while current_level_idx < len(LEVELS):
        crossword = RegexCrossword(LEVELS[current_level_idx])
        
        while True:
            crossword.display_grid()
            try:
                cmd_input = input(f"\n{COLOR_BOLD}Level {crossword.level} [Score: {score}] > {COLOR_END}").strip()
            except (KeyboardInterrupt, EOFError):
                print(f"\n{COLOR_WARNING}Thanks for playing! Final Score: {score}{COLOR_END}")
                sys.exit(0)

            if not cmd_input:
                continue

            parts = cmd_input.split()
            cmd = parts[0].lower()

            if cmd == "quit" or cmd == "exit":
                print(f"{COLOR_WARNING}Thanks for playing! Final Score: {score}{COLOR_END}")
                sys.exit(0)
            elif cmd == "check":
                crossword.check_grid()
            elif cmd == "hint":
                msg = crossword.get_hint()
                print(f"{COLOR_BLUE}{msg}{COLOR_END}")
                # Hints cost points
                score = max(0, score - 5)
            elif cmd == "reset":
                crossword.grid = [[" " for _ in range(crossword.cols)] for _ in range(crossword.rows)]
                print(f"{COLOR_WARNING}Grid reset.{COLOR_END}")
            elif len(parts) == 2 and len(parts[0]) == 2:
                # E.g. "A1 X"
                success, msg = crossword.set_cell(parts[0], parts[1])
                if success:
                    print(f"{COLOR_GREEN}{msg}{COLOR_END}")
                    # Auto check if filled
                    if crossword.check_grid(quiet=True):
                        print(f"\n{COLOR_GREEN}{COLOR_BOLD}★ CONGRATULATIONS! LEVEL {crossword.level} COMPLETED! ★{COLOR_END}")
                        score += crossword.level * 20
                        current_level_idx += 1
                        break
                else:
                    print(f"{COLOR_FAIL}{msg}{COLOR_END}")
            else:
                print(f"{COLOR_FAIL}Unknown command. Use format 'A1 X', 'check', 'hint', or 'quit'.{COLOR_END}")

    print(f"\n{COLOR_GREEN}{COLOR_BOLD}🎉 Amazing! You have solved all levels and completed the game! 🎉{COLOR_END}")
    print(f"{COLOR_BOLD}Final Score: {score}{COLOR_END}")


def main():
    parser = argparse.ArgumentParser(
        description="Run an interactive regular expression crossword game in the terminal."
    )
    parser.add_argument(
        "--no-banner",
        action="store_true",
        help="Suppress the CLI graphical banner."
    )
    args = parser.parse_args()
    play_game()


if __name__ == "__main__":
    main()
