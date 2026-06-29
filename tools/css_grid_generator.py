#!/usr/bin/env python3
"""
CSS Grid Generator - An interactive CLI and HTML/CSS generator for grid layouts.
"""

import argparse
import sys
import os

# ANSI Colors
COLOR_HEADER = "\033[95m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"

def get_input(prompt, default_val, validator=None):
    """Prompt user for input with a default value and validation"""
    while True:
        try:
            val = input(f"{prompt} [{default_val}]: ").strip()
            if not val:
                return default_val
            if validator:
                if validator(val):
                    return val
                else:
                    print(f"{COLOR_RED}Invalid input. Please try again.{COLOR_RESET}")
            else:
                return val
        except (KeyboardInterrupt, EOFError):
            print("\nAborted.")
            sys.exit(0)

def is_int(val):
    try:
        int(val)
        return int(val) > 0
    except ValueError:
        return False

def draw_ascii_grid(cols, rows):
    """Draws a visual mockup of the grid in terminal using Unicode box-drawing characters"""
    cell_width = 8
    # Top border
    top = "┌" + "─" * cell_width + ("┬" + "─" * cell_width) * (cols - 1) + "┐"
    # Row separator
    mid = "├" + "─" * cell_width + ("┼" + "─" * cell_width) * (cols - 1) + "┤"
    # Bottom border
    bot = "└" + "─" * cell_width + ("┴" + "─" * cell_width) * (cols - 1) + "┘"

    print(top)
    for r in range(rows):
        cells = []
        for c in range(cols):
            # Label with coordinates (e.g. C1R1)
            cells.append(f" C{c+1}R{r+1} ".center(cell_width))
        print("│" + "│".join(cells) + "│")
        if r < rows - 1:
            print(mid)
    print(bot)

def generate_html_preview(cols_def, rows_def, col_gap, row_gap, justify_items, align_items, cols_count, rows_count):
    """Generates a premium standalone preview HTML file with styling and live code copy options"""
    items_html = ""
    for r in range(rows_count):
        for c in range(cols_count):
            items_html += f'      <div class="grid-item">Item {c+1},{r+1}</div>\n'

    css_code = f"""
.grid-container {{
  display: grid;
  grid-template-columns: {cols_def};
  grid-template-rows: {rows_def};
  column-gap: {col_gap};
  row-gap: {row_gap};
  justify-items: {justify_items};
  align-items: {align_items};
  background-color: #1e1e2e;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.2);
}}

.grid-item {{
  background: linear-gradient(135deg, #89b4fa 0%, #b4befe 100%);
  color: #11111b;
  font-family: 'Inter', sans-serif;
  font-weight: 600;
  padding: 30px;
  text-align: center;
  border-radius: 8px;
  display: flex;
  justify-content: center;
  align-items: center;
  border: 1px solid rgba(255,255,255,0.1);
  transition: transform 0.2s, box-shadow 0.2s;
}}

.grid-item:hover {{
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(137, 180, 250, 0.4);
}}
"""

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>CSS Grid Visualizer & Code Generator</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&family=Fira+Code:wght@400;500&display=swap" rel="stylesheet">
  <style>
    body {{
      font-family: 'Inter', sans-serif;
      background-color: #11111b;
      color: #cdd6f4;
      margin: 0;
      padding: 40px;
      display: flex;
      flex-direction: column;
      align-items: center;
    }}
    h1 {{
      font-size: 2.5rem;
      font-weight: 800;
      margin-bottom: 5px;
      background: linear-gradient(90deg, #89b4fa, #f5c2e7);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }}
    p {{
      color: #a6adc8;
      margin-bottom: 40px;
    }}
    .container {{
      width: 100%;
      max-width: 1200px;
      display: flex;
      flex-direction: column;
      gap: 30px;
    }}
    .card {{
      background-color: #181825;
      border: 1px solid #313244;
      border-radius: 16px;
      padding: 30px;
    }}
    .card-title {{
      font-size: 1.25rem;
      font-weight: 600;
      margin-top: 0;
      margin-bottom: 20px;
      color: #f5c2e7;
    }}
    {css_code}
    pre {{
      background-color: #11111b;
      padding: 20px;
      border-radius: 8px;
      border: 1px solid #313244;
      overflow-x: auto;
    }}
    code {{
      font-family: 'Fira Code', monospace;
      color: #a6e3a1;
    }}
    .btn {{
      background: linear-gradient(135deg, #f5c2e7 0%, #cba6f7 100%);
      color: #11111b;
      border: none;
      padding: 12px 24px;
      font-weight: 600;
      border-radius: 8px;
      cursor: pointer;
      font-family: inherit;
      transition: opacity 0.2s;
    }}
    .btn:hover {{
      opacity: 0.9;
    }}
  </style>
</head>
<body>
  <h1>CSS Grid Layout Preview</h1>
  <p>Standalone live grid mockup and exportable code snippet</p>

  <div class="container">
    <div class="card">
      <div class="card-title">Live Preview</div>
      <div class="grid-container">
{items_html}      </div>
    </div>

    <div class="card">
      <div class="card-title">Generated CSS Properties</div>
      <pre><code>.grid-container {{{css_code.split('.grid-container {')[1].split('}')[0]}
}}</code></pre>
      <button class="btn" onclick="navigator.clipboard.writeText(document.querySelector('code').innerText)">Copy CSS Code</button>
    </div>
  </div>
</body>
</html>
"""
    return html_content

def main():
    parser = argparse.ArgumentParser(
        description="CSS Grid Generator - Build and export customized grid layouts."
    )
    parser.add_argument("-o", "--output", default="grid_preview.html", help="HTML/CSS output file path")
    parser.add_argument("--non-interactive", action="store_true", help="Generate layout with default parameters")
    args = parser.parse_args()

    print("=" * 80)
    print(f"{COLOR_BOLD}{COLOR_HEADER}CSS GRID GENERATOR & LAYOUT BUILDER{COLOR_RESET}")
    print("=" * 80)

    if args.non_interactive:
        # Default options
        cols_count = 3
        rows_count = 2
        cols_def = "1fr 1fr 1fr"
        rows_def = "auto auto"
        col_gap = "15px"
        row_gap = "15px"
        justify_items = "stretch"
        align_items = "stretch"
    else:
        # Interactive prompts
        cols_count_str = get_input("Enter number of columns", "3", is_int)
        cols_count = int(cols_count_str)

        rows_count_str = get_input("Enter number of rows", "2", is_int)
        rows_count = int(rows_count_str)

        cols_def = get_input("Define columns sizing (space-separated, e.g. '1fr 200px 1fr')", " ".join(["1fr"] * cols_count))
        rows_def = get_input("Define rows sizing (space-separated, e.g. 'auto 150px')", " ".join(["auto"] * rows_count))

        col_gap = get_input("Column gap (e.g. '15px', '1rem', '0')", "15px")
        row_gap = get_input("Row gap (e.g. '15px', '1rem', '0')", "15px")

        justify_items = get_input("justify-items (stretch/start/end/center)", "stretch")
        align_items = get_input("align-items (stretch/start/end/center)", "stretch")

    print("\n" + "=" * 80)
    print(f"{COLOR_BOLD}Grid Layout Mockup:{COLOR_RESET}")
    draw_ascii_grid(cols_count, rows_count)
    print("=" * 80)

    # Generate HTML content
    html_out = generate_html_preview(cols_def, rows_def, col_gap, row_gap, justify_items, align_items, cols_count, rows_count)

    try:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(html_out)
        print(f"\n{COLOR_GREEN}✓ Standalone interactive layout preview successfully written to '{args.output}'{COLOR_RESET}")
        print(f"Open '{args.output}' in any browser to inspect and copy the CSS.")
    except Exception as e:
        print(f"{COLOR_RED}Error writing output file '{args.output}': {e}{COLOR_RESET}")

if __name__ == "__main__":
    main()
