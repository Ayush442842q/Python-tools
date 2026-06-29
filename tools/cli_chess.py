#!/usr/bin/env python3
"""
CLI Chess Game
A zero-dependency terminal-based Chess game.
Supports interactive PvP (Player vs Player) and PvE (Player vs Computer) modes.
Renders the board with ANSI colored squares and Unicode chess pieces.
"""

import argparse
import random
import sys

# Unicode chess pieces dictionary
UNICODE_PIECES = {
    'R': '♖', 'N': '♘', 'B': '♗', 'Q': '♕', 'K': '♔', 'P': '♙',  # White (Capital)
    'r': '♜', 'n': '♞', 'b': '♝', 'q': '♛', 'k': '♚', 'p': '♟',  # Black (Lowercase)
    '.': ' '
}

# Piece values for the simple computer evaluation
PIECE_VALUES = {
    'p': 10, 'n': 30, 'b': 30, 'r': 50, 'q': 90, 'k': 900,
    'P': 10, 'N': 30, 'B': 30, 'R': 50, 'Q': 90, 'K': 900,
    '.': 0
}

# ANSI Background Colors for board cells
BG_LIGHT = "\033[47m"  # Light gray / white
BG_DARK = "\033[46m"   # Cyan / darker blue-green
TEXT_BLACK = "\033[30m"
TEXT_WHITE = "\033[37m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"


class ChessBoard:
    def __init__(self):
        # Initial board state: 8x8 list of lists
        # White on bottom (ranks 6,7), Black on top (ranks 0,1)
        self.grid = [
            ['r', 'n', 'b', 'q', 'k', 'b', 'n', 'r'],
            ['p', 'p', 'p', 'p', 'p', 'p', 'p', 'p'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['.', '.', '.', '.', '.', '.', '.', '.'],
            ['P', 'P', 'P', 'P', 'P', 'P', 'P', 'P'],
            ['R', 'N', 'B', 'Q', 'K', 'B', 'N', 'R']
        ]
        self.turn = 'W'  # 'W' for White, 'B' for Black
        self.move_history = []
        self.captured_pieces = {'W': [], 'B': []}

    def print_board(self):
        """Prints the board cleanly with coordinate headers and colored cells."""
        print("\n   a  b  c  d  e  f  g  h")
        for r in range(8):
            row_str = f"{8 - r} "
            for c in range(8):
                piece = self.grid[r][c]
                symbol = UNICODE_PIECES[piece]
                
                # Determine cell color based on coordinates
                bg_color = BG_LIGHT if (r + c) % 2 == 0 else BG_DARK
                
                # Determine piece text color
                if piece.isupper():
                    text_color = TEXT_WHITE
                else:
                    text_color = TEXT_BLACK
                    
                row_str += f"{bg_color}{text_color} {symbol} {COLOR_RESET}"
            row_str += f" {8 - r}"
            print(row_str)
        print("   a  b  c  d  e  f  g  h\n")
        
        # Print Captured Pieces info
        white_captures = " ".join([UNICODE_PIECES[p] for p in self.captured_pieces['W']])
        black_captures = " ".join([UNICODE_PIECES[p] for p in self.captured_pieces['B']])
        print(f"Captured by White: {white_captures}")
        print(f"Captured by Black: {black_captures}\n")

    def parse_coordinates(self, move_str):
        """
        Parses notation like 'e2e4' or 'e2-e4' to indices: (start_row, start_col, end_row, end_col).
        Returns None if format is invalid.
        """
        move_str = move_str.replace("-", "").replace(" ", "").lower()
        if len(move_str) != 4:
            return None
            
        files = 'abcdefgh'
        ranks = '87654321'
        
        if move_str[0] not in files or move_str[2] not in files:
            return None
        if move_str[1] not in ranks or move_str[3] not in ranks:
            return None
            
        start_col = files.index(move_str[0])
        start_row = ranks.index(move_str[1])
        end_col = files.index(move_str[2])
        end_row = ranks.index(move_str[3])
        
        return start_row, start_col, end_row, end_col

    def is_valid_move(self, sr, sc, er, ec):
        """
        Performs move validation checks for all pieces.
        This is a basic validator to enforce movement paths, obstacles, and turn logic.
        """
        # Out of bounds check
        if not (0 <= sr < 8 and 0 <= sc < 8 and 0 <= er < 8 and 0 <= ec < 8):
            return False
            
        # Can't move to the same square
        if sr == er and sc == ec:
            return False
            
        piece = self.grid[sr][sc]
        target = self.grid[er][ec]
        
        # Must select a piece
        if piece == '.':
            return False
            
        # Must move own color
        if self.turn == 'W' and not piece.isupper():
            return False
        if self.turn == 'B' and not piece.islower():
            return False
            
        # Can't capture own piece
        if target != '.':
            if (piece.isupper() and target.isupper()) or (piece.islower() and target.islower()):
                return False
                
        # Piece-specific rules
        piece_type = piece.upper()
        
        if piece_type == 'P':  # Pawn
            direction = -1 if piece.isupper() else 1
            start_rank = 6 if piece.isupper() else 1
            
            # Forward move (no capture)
            if sc == ec:
                # 1 square forward
                if er == sr + direction and target == '.':
                    return True
                # 2 squares forward from start rank
                if sr == start_rank and er == sr + 2 * direction and target == '.':
                    # Intermediate square must be empty
                    if self.grid[sr + direction][sc] == '.':
                        return True
            # Diagonal capture
            elif abs(sc - ec) == 1 and er == sr + direction:
                if target != '.':
                    return True
            return False
            
        elif piece_type == 'R':  # Rook
            if sr != er and sc != ec:
                return False
            # Check for blockages
            return self._is_path_clear(sr, sc, er, ec)
            
        elif piece_type == 'B':  # Bishop
            if abs(sr - er) != abs(sc - ec):
                return False
            return self._is_path_clear(sr, sc, er, ec)
            
        elif piece_type == 'Q':  # Queen
            if sr != er and sc != ec and abs(sr - er) != abs(sc - ec):
                return False
            return self._is_path_clear(sr, sc, er, ec)
            
        elif piece_type == 'N':  # Knight
            row_diff = abs(sr - er)
            col_diff = abs(sc - ec)
            return (row_diff == 2 and col_diff == 1) or (row_diff == 1 and col_diff == 2)
            
        elif piece_type == 'K':  # King
            return abs(sr - er) <= 1 and abs(sc - ec) <= 1
            
        return False

    def _is_path_clear(self, sr, sc, er, ec):
        """Helper to check if straight/diagonal path between cells is clear of other pieces."""
        row_step = 0 if sr == er else (1 if er > sr else -1)
        col_step = 0 if sc == ec else (1 if ec > sc else -1)
        
        curr_r, curr_c = sr + row_step, sc + col_step
        while curr_r != er or curr_c != ec:
            if self.grid[curr_r][curr_c] != '.':
                return False
            curr_r += row_step
            curr_c += col_step
        return True

    def make_move(self, sr, sc, er, ec):
        """Executes a move, updates turn, captures, and handles pawn promotion."""
        piece = self.grid[sr][sc]
        target = self.grid[er][ec]
        
        if target != '.':
            # Add to capture list (capturing player's list gets the piece)
            capturing_player = 'W' if piece.isupper() else 'B'
            self.captured_pieces[capturing_player].append(target)
            
        # Move piece
        self.grid[er][ec] = piece
        self.grid[sr][sc] = '.'
        
        # Pawn Promotion: auto promote to Queen for simplicity
        if piece == 'P' and er == 0:
            self.grid[er][ec] = 'Q'
        elif piece == 'p' and er == 7:
            self.grid[er][ec] = 'q'
            
        self.move_history.append((self.turn, f"{sr},{sc}->{er},{ec}"))
        self.turn = 'B' if self.turn == 'W' else 'W'

    def get_all_valid_moves(self, color):
        """Gathers all possible valid moves for a player's color ('W' or 'B')."""
        valid_moves = []
        for r in range(8):
            for c in range(8):
                piece = self.grid[r][c]
                if piece == '.':
                    continue
                if (color == 'W' and piece.isupper()) or (color == 'B' and piece.islower()):
                    # Scan entire board for valid destinations
                    for er in range(8):
                        for ec in range(8):
                            if self.is_valid_move(r, c, er, ec):
                                valid_moves.append((r, c, er, ec))
        return valid_moves


def play_game(mode="pvp"):
    board = ChessBoard()
    print("\n" + "=" * 40)
    print(COLOR_BOLD + COLOR_GREEN + "           TERMINAL CHESS GAME" + COLOR_RESET)
    print("=" * 40)
    print("Input moves in Coordinate Notation (e.g., e2e4 or e7e5).")
    print("Enter 'exit' or 'quit' to end the game.\n")

    while True:
        board.print_board()
        
        # Game status check
        all_moves = board.get_all_valid_moves(board.turn)
        if not all_moves:
            # Game ends in draw or loss (simplification: no checkmate detection logic)
            print(COLOR_BOLD + COLOR_YELLOW + f"No valid moves left for {board.turn}. Game over!" + COLOR_RESET)
            break
            
        # Check if King was captured
        kings = [board.grid[r][c] for r in range(8) for c in range(8) if board.grid[r][c].upper() == 'K']
        if len(kings) < 2:
            winner = "White" if any(k.isupper() for k in kings) else "Black"
            print(COLOR_BOLD + COLOR_GREEN + f"King captured! {winner} wins!" + COLOR_RESET)
            break

        if mode == "pve" and board.turn == 'B':
            # Computer turn
            print("Computer thinking...")
            # Simple evaluation: select move that captures highest value piece, or random
            best_move = None
            best_score = -9999
            
            # Simple heuristic
            for move in all_moves:
                sr, sc, er, ec = move
                target = board.grid[er][ec]
                val = PIECE_VALUES[target]
                # Slightly favor moving forward or taking center
                val += (7 - er if board.turn == 'B' else er) * 0.1
                
                if val > best_score:
                    best_score = val
                    best_move = move
                    
            if best_move:
                sr, sc, er, ec = best_move
                files = 'abcdefgh'
                ranks = '87654321'
                move_str = f"{files[sc]}{ranks[sr]}{files[ec]}{ranks[er]}"
                print(f"Computer played: {COLOR_BOLD}{move_str}{COLOR_RESET}")
                board.make_move(sr, sc, er, ec)
            continue

        # Player turn
        try:
            player_color = "White" if board.turn == 'W' else "Black"
            move_input = input(f"{player_color} turn (e.g. e2e4): ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break
            
        if move_input.lower() in ['exit', 'quit']:
            print("Game exited.")
            break
            
        coords = board.parse_coordinates(move_input)
        if not coords:
            print(COLOR_BOLD + COLOR_YELLOW + "Invalid syntax! Please use coordinates like 'e2e4'." + COLOR_RESET)
            continue
            
        sr, sc, er, ec = coords
        if not board.is_valid_move(sr, sc, er, ec):
            print(COLOR_BOLD + COLOR_YELLOW + "Illegal Move! Verify chess rules and try again." + COLOR_RESET)
            continue
            
        board.make_move(sr, sc, er, ec)


def main():
    parser = argparse.ArgumentParser(description="CLI Chess Game")
    parser.add_argument("--mode", choices=["pvp", "pve"], default="pvp",
                        help="Choose PvP (Player vs Player) or PvE (Player vs Computer)")
    args = parser.parse_args()

    # If no mode argument explicitly provided, let user choose interactively
    mode = args.mode
    if len(sys.argv) == 1:
        print("Welcome to Terminal Chess!")
        print("1. Player vs Player (Local)")
        print("2. Player vs Computer")
        try:
            choice = input("Select mode (1/2): ").strip()
            if choice == "1":
                mode = "pvp"
            elif choice == "2":
                mode = "pve"
            else:
                print("Defaulting to PvP.")
                mode = "pvp"
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            sys.exit(0)

    play_game(mode)


if __name__ == "__main__":
    main()
