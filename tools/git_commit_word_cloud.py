#!/usr/bin/env python3
"""Git Commit Word Cloud Generator

Analyzes commit messages in a Git repository, filters out common stop words,
calculates term frequencies, and generates a visual 2D ASCII/Unicode word cloud
directly in the terminal, color-coded by word significance.
"""

import argparse
import collections
import math
import re
import subprocess
import sys
from typing import Dict, List, Set, Tuple

# ANSI Colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_YELLOW = "\033[33m"
COLOR_GREEN = "\033[32m"
COLOR_CYAN = "\033[36m"
COLOR_BLUE = "\033[34m"
COLOR_MAGENTA = "\033[35m"
COLOR_GREY = "\033[90m"

# Standard English stop words
STOP_WORDS = {
    "the", "and", "to", "of", "a", "for", "in", "on", "with", "is", "it",
    "that", "this", "as", "at", "by", "an", "be", "from", "or", "was", "but",
    "are", "your", "my", "we", "they", "he", "she", "you", "i", "not", "have",
    "has", "had", "do", "does", "did", "been", "being", "into", "than", "then",
    "their", "them", "there", "about", "which", "who", "whom", "whose", "up",
    "down", "out", "over", "under", "again", "further", "once", "here", "all",
    "any", "both", "each", "few", "more", "most", "other", "some", "such",
    "no", "nor", "too", "very", "can", "will", "just", "should", "now", "only"
}

# Conventional commit keywords to ignore optional / general noise
CONVENTIONAL_COMMITS = {
    "feat", "fix", "chore", "docs", "style", "refactor", "perf", "test",
    "build", "ci", "merge", "signed", "off", "by", "co", "authored",
    "signed-off-by", "co-authored-by", "branch", "pull", "request", "merge",
    "commit", "github", "gitlab", "into", "master", "main", "dev", "develop"
}


def run_git_log(limit: int) -> List[str]:
    """Fetch git commit messages using subprocess."""
    cmd = ["git", "log", "--format=%B"]
    if limit > 0:
        cmd.append(f"-n {limit}")
        
    try:
        res = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True
        )
        return res.stdout.splitlines()
    except (subprocess.SubprocessError, FileNotFoundError) as e:
        print(f"{COLOR_RED}Error running Git command: {e}{COLOR_RESET}", file=sys.stderr)
        return []


def tokenize_messages(messages: List[str], ignore_conventional: bool) -> List[str]:
    """Extract individual significant words from commit messages."""
    words = []
    
    # Regex to extract words/identifiers
    word_pattern = re.compile(r"\b[a-zA-Z]{3,15}\b")
    
    for msg in messages:
        msg_lower = msg.lower()
        for word in word_pattern.findall(msg_lower):
            if word in STOP_WORDS:
                continue
            if ignore_conventional and word in CONVENTIONAL_COMMITS:
                continue
            words.append(word)
            
    return words


class ASCIIWordCloud:
    """Arranges words in a 2D grid using a spiral layout algorithm to avoid collisions."""
    def __init__(self, width: int = 80, height: int = 24):
        self.width = width
        self.height = height
        # Grid stores (word_string, color_code) or None
        self.grid: List[List[Tuple[Optional[str], str]]] = [
            [(None, "")] * width for _ in range(height)
        ]

    def can_place(self, word: str, start_x: int, start_y: int) -> bool:
        """Check if a word fits in the grid without colliding with other words."""
        w_len = len(word)
        if start_x < 0 or start_x + w_len >= self.width:
            return False
        if start_y < 0 or start_y >= self.height:
            return False
            
        # Check buffer around the word for neatness
        for dy in [-1, 0, 1]:
            for dx in range(-1, w_len + 1):
                px = start_x + dx
                py = start_y + dy
                if 0 <= px < self.width and 0 <= py < self.height:
                    if self.grid[py][px][0] is not None:
                        return False
        return True

    def place_word(self, word: str, x: int, y: int, color: str):
        """Write word characters into the grid cells."""
        for idx, char in enumerate(word):
            self.grid[y][x + idx] = (char, color)

    def generate(self, word_freqs: List[Tuple[str, int]]):
        """Place words starting from center on an Archimedean spiral."""
        center_x = self.width // 2
        center_y = self.height // 2
        
        # Color spectrum for frequencies
        colors = [COLOR_RED, COLOR_YELLOW, COLOR_GREEN, COLOR_CYAN, COLOR_BLUE, COLOR_MAGENTA]
        max_freq = word_freqs[0][1] if word_freqs else 1

        for i, (word, freq) in enumerate(word_freqs):
            # Select color based on importance
            pct = freq / max_freq
            if pct > 0.8:
                color = COLOR_BOLD + COLOR_RED
            elif pct > 0.6:
                color = COLOR_BOLD + COLOR_YELLOW
            elif pct > 0.4:
                color = COLOR_BOLD + COLOR_GREEN
            elif pct > 0.2:
                color = COLOR_BOLD + COLOR_CYAN
            else:
                color = COLOR_GREY
                
            # Try placing word starting from center and spiraling out
            placed = False
            # Spiral configuration
            theta = 0.0
            radius = 0.0
            
            # Step size for spiral checks
            d_theta = 0.1
            d_radius = 0.05
            aspect_ratio = 2.0  # Characters are taller than they are wide
            
            # Limit search checks to avoid infinite loops
            max_attempts = 1500
            attempts = 0
            
            while not placed and attempts < max_attempts:
                # Polar coordinates to Cartesian offsets
                dx = int(radius * math.cos(theta) * aspect_ratio)
                dy = int(radius * math.sin(theta))
                
                # Check target coord
                tx = center_x + dx - (len(word) // 2)
                ty = center_y + dy
                
                if self.can_place(word, tx, ty):
                    self.place_word(word, tx, ty, color)
                    placed = True
                else:
                    theta += d_theta
                    radius += d_radius
                    attempts += 1

    def render(self) -> str:
        """Render the 2D grid as a terminal-printable string."""
        lines = []
        # Outer border
        border_top = "+" + "-" * self.width + "+"
        lines.append(f"{COLOR_GREY}{border_top}{COLOR_RESET}")
        
        for row in self.grid:
            line_chars = ["|"]
            in_word = False
            curr_color = ""
            
            for cell, color in row:
                if cell is not None:
                    if not in_word or curr_color != color:
                        line_chars.append(color)
                        in_word = True
                        curr_color = color
                    line_chars.append(cell)
                else:
                    if in_word:
                        line_chars.append(COLOR_RESET)
                        in_word = False
                    line_chars.append(" ")
            if in_word:
                line_chars.append(COLOR_RESET)
            line_chars.append(f"{COLOR_GREY}|{COLOR_RESET}")
            lines.append("".join(line_chars))
            
        lines.append(f"{COLOR_GREY}{border_top}{COLOR_RESET}")
        return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Git Commit Word Cloud Generator - Visualize common themes in commit logs."
    )
    parser.add_argument(
        "-n", "--limit",
        type=int,
        default=500,
        help="Limit analysis to the last N commits (default: 500, 0 for unlimited)"
    )
    parser.add_argument(
        "--width",
        type=int,
        default=80,
        help="Width of the rendered word cloud grid in characters (default: 80)"
    )
    parser.add_argument(
        "--height",
        type=int,
        default=22,
        help="Height of the rendered word cloud grid in characters (default: 22)"
    )
    parser.add_argument(
        "--include-conventional",
        action="store_true",
        help="Do NOT ignore conventional commit prefixes (feat, fix, docs, chore, etc.)"
    )
    parser.add_argument(
        "--list-size",
        type=int,
        default=15,
        help="Number of top words to show in the frequency summary list (default: 15)"
    )
    args = parser.parse_args()

    # Get commits
    messages = run_git_log(args.limit)
    if not messages:
        print(f"{COLOR_YELLOW}No commit messages found or not in a Git repository.{COLOR_RESET}")
        sys.exit(0)

    # Tokenize
    words = tokenize_messages(messages, ignore_conventional=not args.include_conventional)
    if not words:
        print(f"{COLOR_YELLOW}No significant words found in the analyzed commits.{COLOR_RESET}")
        sys.exit(0)

    # Frequency analysis
    counter = collections.Counter(words)
    # Get top 50 words to place in cloud
    cloud_size = 40
    top_for_cloud = counter.most_common(cloud_size)
    top_summary = counter.most_common(args.list_size)

    # Create and generate cloud
    cloud = ASCIIWordCloud(width=args.width, height=args.height)
    cloud.generate(top_for_cloud)

    # Print Report
    print(f"\n{COLOR_BOLD}{COLOR_CYAN}=== Git Commit Word Cloud ==={COLOR_RESET}\n")
    print(f"{COLOR_BOLD}Analyzed Commits:{COLOR_RESET} {len(messages)}")
    print(f"{COLOR_BOLD}Total Words Extracted:{COLOR_RESET} {len(words)}")
    print(f"{COLOR_BOLD}Unique Words Found:{COLOR_RESET} {len(counter)}\n")

    # Output cloud
    print(cloud.render())
    print()

    # Print word lists
    print(f"{COLOR_BOLD}{COLOR_BLUE}--- Top {args.list_size} Word Frequencies ---{COLOR_RESET}")
    print(f"{COLOR_BOLD}{'Word':<15} | {'Count':<6} | {'Frequency %':<12}{COLOR_RESET}")
    print("-" * 40)
    for word, count in top_summary:
        freq_pct = (count / len(words)) * 100
        print(f"{word:<15} | {count:<6} | {freq_pct:.2f}%")
    print()


if __name__ == "__main__":
    main()
