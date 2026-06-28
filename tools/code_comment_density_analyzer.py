#!/usr/bin/env python3
"""
Code Comment Density Analyzer

A CLI tool that recursively scans a directory for source code files, analyzes
the density of comments (distinguishing between code lines, blank lines, single-line
comments, block comments/docstrings, and mixed lines), and prints a tabular color
report grouped by programming language/file extension.

Usage:
    python tools/code_comment_density_analyzer.py -d ./src
    python tools/code_comment_density_analyzer.py -f main.py
"""

import argparse
import os
import re
import sys
from typing import Dict, Any, List, Set, Tuple

# ANSI Colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"

def supports_color() -> bool:
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform or is_a_tty

def color_text(text: str, color_code: str) -> str:
    return f"{color_code}{text}{COLOR_RESET}" if supports_color() else text

# Language mappings and comment styles
LANGUAGE_CONFIGS = {
    ".py": {
        "name": "Python",
        "single": [r"#"],
        "multi_starts": [r'"""', r"'''"],
        "multi_ends": [r'"""', r"'''"]
    },
    ".js": {
        "name": "JavaScript",
        "single": [r"//"],
        "multi_starts": [r"/\*"],
        "multi_ends": [r"\*/"]
    },
    ".ts": {
        "name": "TypeScript",
        "single": [r"//"],
        "multi_starts": [r"/\*"],
        "multi_ends": [r"\*/"]
    },
    ".tsx": {
        "name": "React TSX",
        "single": [r"//"],
        "multi_starts": [r"/\*"],
        "multi_ends": [r"\*/"]
    },
    ".jsx": {
        "name": "React JSX",
        "single": [r"//"],
        "multi_starts": [r"/\*"],
        "multi_ends": [r"\*/"]
    },
    ".go": {
        "name": "Go",
        "single": [r"//"],
        "multi_starts": [r"/\*"],
        "multi_ends": [r"\*/"]
    },
    ".rs": {
        "name": "Rust",
        "single": [r"//", r"///"],
        "multi_starts": [r"/\*"],
        "multi_ends": [r"\*/"]
    },
    ".c": {
        "name": "C",
        "single": [r"//"],
        "multi_starts": [r"/\*"],
        "multi_ends": [r"\*/"]
    },
    ".cpp": {
        "name": "C++",
        "single": [r"//"],
        "multi_starts": [r"/\*"],
        "multi_ends": [r"\*/"]
    },
    ".h": {
        "name": "C/C++ Header",
        "single": [r"//"],
        "multi_starts": [r"/\*"],
        "multi_ends": [r"\*/"]
    },
    ".java": {
        "name": "Java",
        "single": [r"//"],
        "multi_starts": [r"/\*"],
        "multi_ends": [r"\*/"]
    },
    ".cs": {
        "name": "C#",
        "single": [r"//"],
        "multi_starts": [r"/\*"],
        "multi_ends": [r"\*/"]
    },
    ".rb": {
        "name": "Ruby",
        "single": [r"#"],
        "multi_starts": [r"=begin"],
        "multi_ends": [r"=end"]
    },
    ".php": {
        "name": "PHP",
        "single": [r"//", r"#"],
        "multi_starts": [r"/\*"],
        "multi_ends": [r"\*/"]
    },
    ".css": {
        "name": "CSS",
        "single": [],
        "multi_starts": [r"/\*"],
        "multi_ends": [r"\*/"]
    },
    ".html": {
        "name": "HTML",
        "single": [],
        "multi_starts": [r"<!--"],
        "multi_ends": [r"-->"]
    }
}

class CommentDensityAnalyzer:
    def __init__(self):
        self.stats = {}

    def analyze_file(self, file_path: str) -> Dict[str, int]:
        _, ext = os.path.splitext(file_path.lower())
        if ext not in LANGUAGE_CONFIGS:
            return {}

        config = LANGUAGE_CONFIGS[ext]
        single_escapes = config["single"]
        multi_start_escapes = config["multi_starts"]
        multi_end_escapes = config["multi_ends"]

        # Compile regexes
        single_pattern = re.compile("|".join(f"({s})" for s in single_escapes)) if single_escapes else None
        
        multi_start_patterns = [re.compile(s) for s in multi_start_escapes]
        multi_end_patterns = [re.compile(e) for e in multi_end_escapes]

        total_lines = 0
        blank_lines = 0
        comment_lines = 0
        code_lines = 0
        mixed_lines = 0  # code + inline comment

        in_multiline = False
        multiline_type_idx = -1

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    total_lines += 1
                    stripped = line.strip()

                    if not stripped:
                        if in_multiline:
                            comment_lines += 1
                        else:
                            blank_lines += 1
                        continue

                    # If inside a multi-line comment block
                    if in_multiline:
                        comment_lines += 1
                        end_pattern = multi_end_patterns[multiline_type_idx]
                        if end_pattern.search(stripped):
                            # Check if block ends on this line
                            in_multiline = False
                            multiline_type_idx = -1
                        continue

                    # Check for start of multi-line comment block
                    found_multi_start = False
                    for idx, start_pattern in enumerate(multi_start_patterns):
                        if start_pattern.match(stripped):
                            in_multiline = True
                            multiline_type_idx = idx
                            comment_lines += 1
                            found_multi_start = True
                            # Check if it also ends on same line
                            end_pattern = multi_end_patterns[idx]
                            # Remove the matched start token before testing end
                            body_test = stripped[len(start_pattern.pattern.replace('\\', '')):]
                            if end_pattern.search(body_test):
                                in_multiline = False
                                multiline_type_idx = -1
                            break
                    
                    if found_multi_start:
                        continue

                    # Check for single-line comments
                    if single_pattern:
                        match = single_pattern.search(stripped)
                        if match:
                            start_pos = match.start()
                            if start_pos == 0:
                                comment_lines += 1
                            else:
                                # Mixed line (code followed by comment)
                                code_lines += 1
                                mixed_lines += 1
                            continue

                    # Must be plain code line
                    code_lines += 1

        except Exception as e:
            # Silently log errors or return empty
            return {}

        return {
            "total": total_lines,
            "blank": blank_lines,
            "comment": comment_lines,
            "code": code_lines,
            "mixed": mixed_lines
        }

    def scan_directory(self, dir_path: str) -> Dict[str, Dict[str, int]]:
        aggregated = {}

        for root, _, files in os.walk(dir_path):
            # Skip common junk dirs
            if any(p in root for p in ['.git', '__pycache__', 'node_modules', 'venv', '.venv', '.gemini']):
                continue
            
            for file in files:
                file_path = os.path.join(root, file)
                _, ext = os.path.splitext(file.lower())
                
                if ext in LANGUAGE_CONFIGS:
                    file_stats = self.analyze_file(file_path)
                    if not file_stats or file_stats.get("total", 0) == 0:
                        continue

                    lang_name = LANGUAGE_CONFIGS[ext]["name"]
                    if lang_name not in aggregated:
                        aggregated[lang_name] = {
                            "files": 0, "total": 0, "blank": 0, "comment": 0, "code": 0, "mixed": 0
                        }
                    
                    aggregated[lang_name]["files"] += 1
                    for key in ["total", "blank", "comment", "code", "mixed"]:
                        aggregated[lang_name][key] += file_stats[key]

        return aggregated

def main():
    parser = argparse.ArgumentParser(description="Analyze Code Comment Density")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-d", "--directory", help="Directory to scan recursively")
    group.add_argument("-f", "--file", help="Single file to analyze")
    
    args = parser.parse_args()
    analyzer = CommentDensityAnalyzer()

    if args.file:
        if not os.path.isfile(args.file):
            print(color_text(f"Error: {args.file} is not a valid file.", COLOR_RED))
            sys.exit(1)
        
        _, ext = os.path.splitext(args.file.lower())
        if ext not in LANGUAGE_CONFIGS:
            print(color_text(f"Error: File extension '{ext}' is not supported.", COLOR_RED))
            sys.exit(1)
            
        stats = analyzer.analyze_file(args.file)
        if not stats:
            print(color_text("Error: Could not parse file.", COLOR_RED))
            sys.exit(1)

        lang_name = LANGUAGE_CONFIGS[ext]["name"]
        aggregated = {lang_name: {**stats, "files": 1}}
    else:
        if not os.path.isdir(args.directory):
            print(color_text(f"Error: {args.directory} is not a valid directory.", COLOR_RED))
            sys.exit(1)
        aggregated = analyzer.scan_directory(args.directory)

    if not aggregated:
        print(color_text("No supported source files found to analyze.", COLOR_YELLOW))
        sys.exit(0)

    # Print Report
    print(color_text(f"\n{COLOR_BOLD}=== Code Comment Density Report ==={COLOR_RESET}", COLOR_CYAN))
    
    header = f"{'Language':<18} | {'Files':<5} | {'Total Lines':<11} | {'Code Lines':<11} | {'Comments':<9} | {'Blanks':<8} | {'Density':<7}"
    print(header)
    print("-" * len(header))

    total_files = 0
    total_total = 0
    total_code = 0
    total_comment = 0
    total_blank = 0

    for lang, metrics in sorted(aggregated.items()):
        files = metrics["files"]
        total = metrics["total"]
        code = metrics["code"]
        comment = metrics["comment"]
        blank = metrics["blank"]
        mixed = metrics["mixed"]

        total_files += files
        total_total += total
        total_code += code
        total_comment += comment
        total_blank += blank

        # Comment density calculation: comments / (code + comments)
        # We can also do comments / total lines. Let's use standard: comment_lines / (code_lines + comment_lines - mixed_lines) or simply comment / total.
        # Let's do: (comment_only + mixed) / total
        density_pct = ((comment + mixed) / total * 100) if total > 0 else 0.0
        
        # Color coding density
        # Low < 10% (Red/Yellow), Healthy 15-40% (Green), Very high > 50% (Cyan)
        if density_pct < 10.0:
            density_str = color_text(f"{density_pct:>6.1f}%", COLOR_RED)
        elif density_pct > 40.0:
            density_str = color_text(f"{density_pct:>6.1f}%", COLOR_CYAN)
        else:
            density_str = color_text(f"{density_pct:>6.1f}%", COLOR_GREEN)

        print(f"{lang:<18} | {files:<5} | {total:<11} | {code:<11} | {comment:<9} | {blank:<8} | {density_str}")

    print("-" * len(header))
    overall_density = ((total_comment) / total_total * 100) if total_total > 0 else 0.0
    overall_density_str = color_text(f"{overall_density:>6.1f}%", COLOR_BOLD + COLOR_GREEN if 10 <= overall_density <= 40 else COLOR_BOLD + COLOR_RED)
    
    print(f"{color_text('OVERALL TOTAL', COLOR_BOLD):<18} | {total_files:<5} | {total_total:<11} | {total_code:<11} | {total_comment:<9} | {total_blank:<8} | {overall_density_str}")
    print()

if __name__ == "__main__":
    main()
