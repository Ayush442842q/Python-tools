#!/usr/bin/env python3
"""Markdown Task Progress Calculator

Scans Markdown (.md) files or directories for task list checkboxes (`- [ ]`, `- [x]`),
calculates completion statistics overall, per-file, and per-heading section, and renders
interactive terminal progress bars or outputs formatted reports.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[34m"
COLOR_CYAN = "\033[36m"
COLOR_GREY = "\033[90m"

TASK_PATTERN = re.compile(r"^\s*[-*+]\s+\[([ xX])\]\s+(.*)$")
HEADING_PATTERN = re.compile(r"^(#{1,6})\s+(.*)$")


class SectionTasks:
    def __init__(self, title: str, level: int):
        self.title = title
        self.level = level
        self.total = 0
        self.completed = 0
        self.tasks: List[Tuple[bool, str]] = []

    @property
    def percentage(self) -> float:
        return (self.completed / self.total * 100) if self.total > 0 else 0.0


class FileTasks:
    def __init__(self, path: Path):
        self.path = path
        self.total = 0
        self.completed = 0
        self.sections: List[SectionTasks] = []

    @property
    def percentage(self) -> float:
        return (self.completed / self.total * 100) if self.total > 0 else 0.0


def parse_markdown_tasks(file_path: Path) -> FileTasks:
    """Parses a single Markdown file into structured section and task progress statistics."""
    file_tasks = FileTasks(file_path)
    current_section = SectionTasks("Root Section", level=0)
    file_tasks.sections.append(current_section)

    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception as e:
        return file_tasks

    for line in lines:
        h_match = HEADING_PATTERN.match(line)
        if h_match:
            level = len(h_match.group(1))
            title = h_match.group(2).strip()
            current_section = SectionTasks(title, level)
            file_tasks.sections.append(current_section)
            continue

        t_match = TASK_PATTERN.match(line)
        if t_match:
            is_checked = t_match.group(1).lower() == "x"
            task_text = t_match.group(2).strip()
            current_section.total += 1
            file_tasks.total += 1
            if is_checked:
                current_section.completed += 1
                file_tasks.completed += 1
            current_section.tasks.append((is_checked, task_text))

    # Filter out empty sections
    file_tasks.sections = [s for s in file_tasks.sections if s.total > 0]
    return file_tasks


def render_progress_bar(completed: int, total: int, width: int = 20) -> str:
    """Renders a visual ASCII/Unicode progress bar."""
    if total == 0:
        return f"[{'░' * width}] 0.0%"
    ratio = completed / total
    filled_len = int(width * ratio)
    bar = "█" * filled_len + "░" * (width - filled_len)
    pct = ratio * 100
    color = COLOR_GREEN if ratio == 1.0 else (COLOR_YELLOW if ratio >= 0.5 else COLOR_RED)
    return f"[{color}{bar}{COLOR_RESET}] {pct:5.1f}% ({completed}/{total})"


def scan_directory(target_path: Path, recursive: bool = True) -> List[FileTasks]:
    """Scans target directory or single file for markdown task lists."""
    results: List[FileTasks] = []
    if target_path.is_file():
        if target_path.suffix.lower() in [".md", ".markdown"]:
            results.append(parse_markdown_tasks(target_path))
        return results

    pattern = "**/*.md" if recursive else "*.md"
    for md_file in target_path.glob(pattern):
        if ".git" in md_file.parts or "node_modules" in md_file.parts:
            continue
        ft = parse_markdown_tasks(md_file)
        if ft.total > 0:
            results.append(ft)

    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Calculate task list progress across Markdown files and sections."
    )
    parser.add_argument(
        "target",
        nargs="?",
        default=".",
        help="Target Markdown file or directory path (default: current directory).",
    )
    parser.add_argument(
        "-d", "--detail", action="store_true", help="Show section-by-section task breakdowns per file."
    )
    parser.add_argument(
        "-j", "--json", action="store_true", help="Output raw progress data as JSON."
    )
    parser.add_argument(
        "--no-recursive", action="store_true", help="Do not scan subdirectories recursively."
    )

    args = parser.parse_args()
    target_path = Path(args.target).resolve()

    if not target_path.exists():
        print(f"{COLOR_RED}Error: Path '{args.target}' does not exist.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)

    file_results = scan_directory(target_path, recursive=not args.no_recursive)

    total_tasks = sum(f.total for f in file_results)
    total_completed = sum(f.completed for f in file_results)

    if args.json:
        out_data = {
            "overall": {
                "total": total_tasks,
                "completed": total_completed,
                "percentage": (total_completed / total_tasks * 100) if total_tasks > 0 else 0.0,
            },
            "files": [
                {
                    "file": str(f.path),
                    "total": f.total,
                    "completed": f.completed,
                    "percentage": f.percentage,
                    "sections": [
                        {
                            "title": s.title,
                            "level": s.level,
                            "total": s.total,
                            "completed": s.completed,
                            "percentage": s.percentage,
                        }
                        for s in f.sections
                    ],
                }
                for f in file_results
            ],
        }
        print(json.dumps(out_data, indent=2))
        return

    print(f"\n{COLOR_BOLD}{COLOR_CYAN}📊 Markdown Task Progress Overview{COLOR_RESET}\n")
    print(f"Total Files Scanned with Tasks: {len(file_results)}")
    print(f"Overall Completion: {render_progress_bar(total_completed, total_tasks, width=30)}\n")

    if not file_results:
        print(f"{COLOR_GREY}No task checkboxes (- [ ] / - [x]) found.{COLOR_RESET}")
        return

    print(f"{COLOR_BOLD}File Breakdown:{COLOR_RESET}")
    for ft in sorted(file_results, key=lambda x: str(x.path)):
        rel_path = ft.path.relative_to(target_path) if target_path.is_dir() else ft.path.name
        print(f" • {COLOR_BOLD}{rel_path}{COLOR_RESET}")
        print(f"   {render_progress_bar(ft.completed, ft.total, width=20)}")

        if args.detail:
            for sec in ft.sections:
                indent = "     " + "  " * (sec.level - 1 if sec.level > 0 else 0)
                sec_title = sec.title if sec.level > 0 else "(Headerless)"
                print(f"{indent}└─ {COLOR_GREY}{sec_title}{COLOR_RESET}: {render_progress_bar(sec.completed, sec.total, width=12)}")

    print()


if __name__ == "__main__":
    main()
