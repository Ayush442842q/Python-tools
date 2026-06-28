#!/usr/bin/env python3
"""Terminal Gantt Chart Generator

A standalone CLI tool to visualize project schedules, timelines, and task dependencies
directly in the terminal using Unicode blocks. Supports JSON or simple text input and
exports beautiful responsive HTML/CSS or Markdown.
"""

import argparse
from datetime import datetime, timedelta
import json
import os
import re
import sys
from typing import List, Dict, Any, Tuple

# ANSI Colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[34m"
COLOR_MAGENTA = "\033[35m"
COLOR_CYAN = "\033[36m"
COLOR_GRAY = "\033[90m"

COLOR_THEMES = {
    "default": (COLOR_CYAN, COLOR_BLUE, COLOR_GRAY),
    "classic": (COLOR_GREEN, COLOR_YELLOW, COLOR_GRAY),
    "sunset": (COLOR_MAGENTA, COLOR_RED, COLOR_GRAY),
    "ocean": (COLOR_BLUE, COLOR_CYAN, COLOR_GRAY)
}


class GanttTask:
    def __init__(self, name: str, start: datetime, end: datetime, progress: float, dependencies: List[str] = None):
        self.name = name
        self.start = start
        self.end = end
        self.progress = progress  # 0.0 to 100.0
        self.dependencies = dependencies or []

    @property
    def duration_days(self) -> int:
        return (self.end - self.start).days + 1


def parse_text_input(filepath: str) -> List[GanttTask]:
    """Parse simple custom text format:
    Task Name: YYYY-MM-DD to YYYY-MM-DD, PROGRESS%, dep1, dep2
    """
    tasks = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            # Parse line: Name: Date to Date, Progress%, Deps
            match = re.match(r"^([^:]+):\s*([\d-]+)\s+to\s+([\d-]+)(?:\s*,\s*([\d\.]+)%)?(?:\s*,\s*(.+))?$", line)
            if not match:
                print(f"{COLOR_YELLOW}Warning: Skipping invalid line format: '{line}'{COLOR_RESET}", file=sys.stderr)
                continue

            name = match.group(1).strip()
            try:
                start = datetime.strptime(match.group(2).strip(), "%Y-%m-%d")
                end = datetime.strptime(match.group(3).strip(), "%Y-%m-%d")
            except ValueError as e:
                print(f"{COLOR_YELLOW}Warning: Invalid date in line '{line}': {e}{COLOR_RESET}", file=sys.stderr)
                continue

            progress_str = match.group(4)
            progress = float(progress_str) if progress_str else 0.0

            deps_str = match.group(5)
            dependencies = [d.strip() for d in deps_str.split(",")] if deps_str else []

            tasks.append(GanttTask(name, start, end, progress, dependencies))

    return tasks


def parse_json_input(filepath: str) -> List[GanttTask]:
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    tasks = []
    for item in data:
        name = item.get("name", "Unnamed Task")
        start = datetime.strptime(item["start"], "%Y-%m-%d")
        end = datetime.strptime(item["end"], "%Y-%m-%d")
        progress = float(item.get("progress", 0.0))
        dependencies = item.get("dependencies", [])
        tasks.append(GanttTask(name, start, end, progress, dependencies))
    
    return tasks


def render_terminal(tasks: List[GanttTask], theme_name: str = "default"):
    if not tasks:
        print("No tasks to display.")
        return

    # Determine project boundaries
    proj_start = min(t.start for t in tasks)
    proj_end = max(t.end for t in tasks)
    total_days = (proj_end - proj_start).days + 1

    # Get colors from theme
    col_primary, col_sec, col_dim = COLOR_THEMES.get(theme_name, COLOR_THEMES["default"])

    # Determine terminal size
    try:
        term_cols = os.get_terminal_size().columns
    except OSError:
        term_cols = 80

    # Layout dimensions
    max_name_len = max(len(t.name) for t in tasks)
    max_name_len = min(max_name_len, 25)  # Cap name column width
    
    # Calculate timeline column width
    timeline_width = term_cols - max_name_len - 15  # Reserve space for names, progress and margins
    timeline_width = max(timeline_width, 20)  # Minimum grid size

    days_per_char = total_days / timeline_width

    # Print timeline header
    print(f"\n{COLOR_BOLD}Project Timeline: {proj_start.strftime('%Y-%m-%d')} to {proj_end.strftime('%Y-%m-%d')}{COLOR_RESET}")
    header_pad = " " * (max_name_len + 3)
    
    # Grid ticks (monthly or weekly ticks based on length)
    ticks = []
    tick_labels = []
    curr_date = proj_start
    last_tick_pos = -99

    for col in range(timeline_width):
        col_date = proj_start + timedelta(days=col * days_per_char)
        # Add monthly tick
        if col_date.month != curr_date.month or col == 0:
            if col - last_tick_pos > 8:  # Prevent overlapping ticks
                ticks.append("|")
                tick_labels.append((col, col_date.strftime("%b %y")))
                last_tick_pos = col
        curr_date = col_date

    # Print ticks
    tick_line = [" "] * timeline_width
    for pos, label in tick_labels:
        if pos < len(tick_line):
            tick_line[pos] = "|"
    print(header_pad + "".join(tick_line))

    # Print tick labels
    label_line = [" "] * (timeline_width + 10)
    for pos, label in tick_labels:
        for idx, char in enumerate(label):
            if pos + idx < len(label_line):
                label_line[pos + idx] = char
    print(header_pad + "".join(label_line).rstrip())

    # Print tasks
    print("-" * term_cols)
    for task in tasks:
        # Format task name
        disp_name = task.name[:max_name_len].ljust(max_name_len)
        
        # Calculate task span in character columns
        start_col = int((task.start - proj_start).days / days_per_char)
        end_col = int((task.end - proj_start).days / days_per_char)
        
        # Bound variables
        start_col = max(0, min(start_col, timeline_width - 1))
        end_col = max(start_col, min(end_col, timeline_width - 1))
        task_len = end_col - start_col + 1

        # Calculate progress span
        progress_len = int(task_len * (task.progress / 100.0))
        progress_len = max(0, min(progress_len, task_len))

        # Build chart bar
        bar_chars = []
        for i in range(timeline_width):
            if i < start_col:
                bar_chars.append(" ")
            elif i >= start_col and i <= end_col:
                idx_within_bar = i - start_col
                if idx_within_bar < progress_len:
                    # Completed section
                    bar_chars.append(f"{col_primary}█{COLOR_RESET}")
                else:
                    # Remaining section
                    bar_chars.append(f"{col_sec}▒{COLOR_RESET}")
            else:
                bar_chars.append(" ")

        bar_str = "".join(bar_chars)
        progress_text = f"{int(task.progress):>3}%"
        
        # Colorize task display depending on status
        if task.progress == 100:
            prog_col = COLOR_GREEN
        elif task.progress > 0:
            prog_col = COLOR_YELLOW
        else:
            prog_col = col_dim
            
        print(f"{COLOR_BOLD}{disp_name}{COLOR_RESET} | {bar_str} | {prog_col}{progress_text}{COLOR_RESET}")
    print("-" * term_cols + "\n")
    print(f"{col_primary}█{COLOR_RESET} Completed   {col_sec}▒{COLOR_RESET} Planned/Remaining")


def export_markdown(tasks: List[GanttTask], filepath: str):
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("# Gantt Chart Task Schedule\n\n")
        f.write("| Task Name | Start Date | End Date | Duration (Days) | Progress | Dependencies |\n")
        f.write("| --- | --- | --- | --- | --- | --- |\n")
        for task in tasks:
            deps = ", ".join(task.dependencies) if task.dependencies else "-"
            f.write(f"| {task.name} | {task.start.strftime('%Y-%m-%d')} | {task.end.strftime('%Y-%m-%d')} | {task.duration_days} | {task.progress}% | {deps} |\n")
    print(f"{COLOR_GREEN}Success: Exported Markdown table to '{filepath}'{COLOR_RESET}")


def export_html(tasks: List[GanttTask], filepath: str):
    if not tasks:
        return
    
    proj_start = min(t.start for t in tasks)
    proj_end = max(t.end for t in tasks)
    total_days = (proj_end - proj_start).days + 1

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Project Timeline Schedule</title>
    <style>
        :root {{
            --bg-color: #121824;
            --card-bg: #1e293b;
            --text-color: #f8fafc;
            --primary: #06b6d4;
            --primary-bg: rgba(6, 182, 212, 0.2);
            --border: #334155;
            --completed: #10b981;
            --planned: #f59e0b;
        }}
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 30px;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: var(--card-bg);
            border-radius: 12px;
            border: 1px solid var(--border);
            padding: 30px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
        }}
        h1 {{
            margin-top: 0;
            color: var(--primary);
            font-size: 24px;
            border-bottom: 2px solid var(--border);
            padding-bottom: 15px;
        }}
        .meta-info {{
            margin-bottom: 25px;
            font-size: 14px;
            color: #94a3b8;
        }}
        .gantt-chart {{
            display: grid;
            grid-template-columns: 200px 1fr;
            gap: 15px 20px;
            align-items: center;
            margin-top: 20px;
            overflow-x: auto;
            padding-bottom: 15px;
        }}
        .gantt-header-name {{
            font-weight: bold;
            color: #94a3b8;
            border-bottom: 1px solid var(--border);
            padding-bottom: 10px;
        }}
        .gantt-timeline-header {{
            position: relative;
            height: 35px;
            border-bottom: 1px solid var(--border);
        }}
        .gantt-task-name {{
            font-weight: 600;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .gantt-bar-container {{
            background: rgba(255, 255, 255, 0.03);
            border-radius: 6px;
            height: 32px;
            position: relative;
            border: 1px solid rgba(255,255,255,0.05);
        }}
        .gantt-bar {{
            height: 100%;
            border-radius: 5px;
            position: absolute;
            display: flex;
            align-items: center;
            padding-left: 10px;
            font-size: 11px;
            font-weight: bold;
            color: white;
            box-sizing: border-box;
        }}
        .gantt-bar.completed {{
            background: linear-gradient(90deg, var(--completed), #059669);
            box-shadow: 0 2px 8px rgba(16, 185, 129, 0.3);
        }}
        .gantt-bar.in-progress {{
            background: linear-gradient(90deg, var(--planned), #d97706);
            box-shadow: 0 2px 8px rgba(245, 158, 11, 0.3);
        }}
        .gantt-bar.not-started {{
            background: #475569;
        }}
        .progress-label {{
            position: absolute;
            right: 10px;
            font-size: 12px;
            color: #94a3b8;
        }}
        .grid-tick {{
            position: absolute;
            border-left: 1px dashed var(--border);
            height: 100%;
            top: 0;
            padding-left: 5px;
            font-size: 10px;
            color: #64748b;
        }}
        .legend {{
            display: flex;
            gap: 20px;
            margin-top: 30px;
            font-size: 13px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .legend-color {{
            width: 15px;
            height: 15px;
            border-radius: 3px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Project Timeline Roadmap</h1>
        <div class="meta-info">
            Project Duration: <strong>{proj_start.strftime('%B %d, %Y')}</strong> to <strong>{proj_end.strftime('%B %d, %Y')}</strong> ({total_days} Days)
        </div>

        <div class="gantt-chart">
            <!-- Headers -->
            <div class="gantt-header-name">Task Name</div>
            <div class="gantt-timeline-header">
    """

    # Add monthly background ticks
    months_added = []
    curr = proj_start
    while curr <= proj_end:
        month_label = curr.strftime("%b %y")
        if month_label not in months_added:
            days_offset = (curr - proj_start).days
            pct_offset = (days_offset / total_days) * 100
            html_content += f'<div class="grid-tick" style="left: {pct_offset}%">{month_label}</div>'
            months_added.append(month_label)
        curr += timedelta(days=7)

    html_content += """
            </div>
    """

    # Add tasks
    for task in tasks:
        start_offset = (task.start - proj_start).days
        duration = task.duration_days
        left_pct = (start_offset / total_days) * 100
        width_pct = (duration / total_days) * 100

        # Classes
        if task.progress == 100:
            bar_class = "completed"
        elif task.progress > 0:
            bar_class = "in-progress"
        else:
            bar_class = "not-started"

        html_content += f"""
            <div class="gantt-task-name" title="{task.name}">{task.name}</div>
            <div class="gantt-bar-container">
                <div class="gantt-bar {bar_class}" style="left: {left_pct}%; width: {width_pct}%;">
                    {task.progress}%
                </div>
            </div>
        """

    html_content += """
        </div>

        <div class="legend">
            <div class="legend-item">
                <div class="legend-color" style="background: var(--completed);"></div>
                <span>Completed (100%)</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: var(--planned);"></div>
                <span>In Progress (1-99%)</span>
            </div>
            <div class="legend-item">
                <div class="legend-color" style="background: #475569;"></div>
                <span>Not Started (0%)</span>
            </div>
        </div>
    </div>
</body>
</html>
    """

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"{COLOR_GREEN}Success: Exported HTML timeline to '{filepath}'{COLOR_RESET}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate beautiful terminal Gantt charts from JSON or simple text files."
    )
    parser.add_argument("file", help="Path to input task schedule file (.json or .txt)")
    parser.add_argument(
        "--theme", choices=list(COLOR_THEMES.keys()), default="default", help="Color theme for terminal render"
    )
    parser.add_argument("--export-md", help="Export task schedule as Markdown table to specified path")
    parser.add_argument("--export-html", help="Export roadmap as beautiful interactive HTML timeline to specified path")
    
    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"{COLOR_RED}Error: File '{args.file}' does not exist.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)

    try:
        if args.file.endswith(".json"):
            tasks = parse_json_input(args.file)
        else:
            tasks = parse_text_input(args.file)
    except Exception as e:
        print(f"{COLOR_RED}Error parsing file: {e}{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)

    if not tasks:
        print(f"{COLOR_YELLOW}No tasks found. Please ensure your file matches the required format.{COLOR_RESET}")
        sys.exit(0)

    # Sort tasks by start date
    tasks.sort(key=lambda x: x.start)

    # Render in terminal
    render_terminal(tasks, theme_name=args.theme)

    # Exports
    if args.export_md:
        export_markdown(tasks, args.export_md)
    if args.export_html:
        export_html(tasks, args.export_html)


if __name__ == "__main__":
    main()
