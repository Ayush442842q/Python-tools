#!/usr/bin/env python3
"""
CSS Flexbox Layout Generator & Visualizer - Interactive terminal tool to configure
CSS Flexbox layout properties, visualize the layout in the terminal with ASCII art,
and export the corresponding HTML/CSS code.
"""

import argparse
import sys


def draw_layout(direction, justify, align, wrap, items_count):
    """Generates an ASCII representation of the flexbox layout container and items."""
    # Define sizes of items and the container
    container_width = 50
    container_height = 14
    
    # We will build a character buffer grid
    grid = [[" " for _ in range(container_width)] for _ in range(container_height)]
    
    # Item dimensions
    item_w = 7
    item_h = 3
    
    # List of items
    items = []
    for idx in range(1, items_count + 1):
        items.append({
            "id": idx,
            "label": f"[{idx}]"
        })
        
    # Layout rendering engine (simple representation of Flexbox logic in character coordinates)
    rows = []
    
    if direction == "row" or direction == "row-reverse":
        # Row layout flow
        current_row = []
        x_accum = 0
        for item in items:
            if wrap == "wrap" and x_accum + item_w > container_width - 4:
                rows.append(current_row)
                current_row = [item]
                x_accum = item_w + 1
            else:
                current_row.append(item)
                x_accum += item_w + 1
        if current_row:
            rows.append(current_row)
            
        if direction == "row-reverse":
            rows = [[item for item in reversed(r)] for r in rows]
            
    else:  # column or column-reverse
        # Column layout flow
        # In ASCII grid, we just stack items vertically or wrap them horizontally
        current_col = []
        y_accum = 0
        for item in items:
            if wrap == "wrap" and y_accum + item_h > container_height - 2:
                rows.append(current_col)  # each 'row' will represent a column
                current_col = [item]
                y_accum = item_h + 1
            else:
                current_col.append(item)
                y_accum += item_h + 1
        if current_col:
            rows.append(current_col)
            
        if direction == "column-reverse":
            rows = [[item for item in reversed(c)] for c in rows]

    # Render container borders into grid
    for x in range(container_width):
        grid[0][x] = "-"
        grid[container_height - 1][x] = "-"
    for y in range(container_height):
        grid[y][0] = "|"
        grid[y][container_width - 1] = "|"
        
    # Draw items on grid based on flow direction, justification, and alignment
    if direction in ("row", "row-reverse"):
        num_rows = len(rows)
        # Determine y distribution of rows (align-content / align-items simple mockup)
        row_y_coords = []
        if align == "center":
            start_y = (container_height - (num_rows * item_h + (num_rows - 1))) // 2
            row_y_coords = [start_y + r * (item_h + 1) for r in range(num_rows)]
        elif align == "flex-end":
            start_y = container_height - 1 - (num_rows * item_h + (num_rows - 1))
            row_y_coords = [start_y + r * (item_h + 1) for r in range(num_rows)]
        else:  # flex-start or stretch
            row_y_coords = [1 + r * (item_h + 1) for r in range(num_rows)]
            
        # Draw each row
        for r_idx, row_items in enumerate(rows):
            if r_idx >= len(row_y_coords):
                break
            y_pos = row_y_coords[r_idx]
            
            # Distribute items horizontally in the row (justify-content)
            num_items = len(row_items)
            total_items_w = num_items * item_w
            remaining_w = container_width - 2 - total_items_w
            
            x_coords = []
            if justify == "center":
                start_x = 1 + remaining_w // 2
                x_coords = [start_x + i * (item_w + 1) for i in range(num_items)]
            elif justify == "space-between":
                if num_items > 1:
                    gap = remaining_w // (num_items - 1)
                    x_coords = [1 + i * (item_w + gap) for i in range(num_items)]
                else:
                    x_coords = [1 + remaining_w // 2]
            elif justify == "space-around":
                gap = remaining_w // (num_items * 2)
                x_coords = [1 + gap + i * (item_w + gap * 2) for i in range(num_items)]
            elif justify == "flex-end":
                start_x = container_width - 1 - total_items_w - (num_items - 1)
                x_coords = [start_x + i * (item_w + 1) for i in range(num_items)]
            else:  # flex-start
                x_coords = [1 + i * (item_w + 2) for i in range(num_items)]
                
            # Render item blocks
            for i_idx, item in enumerate(row_items):
                if i_idx >= len(x_coords):
                    break
                x_pos = x_coords[i_idx]
                draw_item_box(grid, x_pos, y_pos, item_w, item_h, item["label"])
                
    else:  # column or column-reverse
        # rows represents a list of columns
        num_cols = len(rows)
        # Determine x distribution of columns
        col_x_coords = []
        if align == "center":
            start_x = (container_width - (num_cols * item_w + (num_cols - 1))) // 2
            col_x_coords = [start_x + c * (item_w + 1) for c in range(num_cols)]
        elif align == "flex-end":
            start_x = container_width - 1 - (num_cols * item_w + (num_cols - 1))
            col_x_coords = [start_x + c * (item_w + 1) for c in range(num_cols)]
        else:  # flex-start
            col_x_coords = [1 + c * (item_w + 2) for c in range(num_cols)]
            
        for c_idx, col_items in enumerate(rows):
            if c_idx >= len(col_x_coords):
                break
            x_pos = col_x_coords[c_idx]
            
            # Distribute items vertically in the column (justify-content)
            num_items = len(col_items)
            total_items_h = num_items * item_h
            remaining_h = container_height - 2 - total_items_h
            
            y_coords = []
            if justify == "center":
                start_y = 1 + remaining_h // 2
                y_coords = [start_y + i * (item_h + 1) for i in range(num_items)]
            elif justify == "space-between":
                if num_items > 1:
                    gap = remaining_h // (num_items - 1)
                    y_coords = [1 + i * (item_h + gap) for i in range(num_items)]
                else:
                    y_coords = [1 + remaining_h // 2]
            elif justify == "space-around":
                gap = remaining_h // (num_items * 2)
                y_coords = [1 + gap + i * (item_h + gap * 2) for i in range(num_items)]
            elif justify == "flex-end":
                start_y = container_height - 1 - total_items_h - (num_items - 1)
                y_coords = [start_y + i * (item_h + 1) for i in range(num_items)]
            else:  # flex-start
                y_coords = [1 + i * (item_h + 1) for i in range(num_items)]
                
            for i_idx, item in enumerate(col_items):
                if i_idx >= len(y_coords):
                    break
                y_pos = y_coords[i_idx]
                draw_item_box(grid, x_pos, y_pos, item_w, item_h, item["label"])

    # Convert grid to string
    out = []
    for r in grid:
        out.append("".join(r))
    return "\n".join(out)


def draw_item_box(grid, x, y, w, h, label):
    """Draws a single item box onto the grid buffer."""
    for dy in range(h):
        for dx in range(w):
            if y + dy >= len(grid) - 1 or x + dx >= len(grid[0]) - 1:
                continue
            if dy == 0 or dy == h - 1:
                grid[y + dy][x + dx] = "#"
            elif dx == 0 or dx == w - 1:
                grid[y + dy][x + dx] = "#"
            elif dy == h // 2 and dx == (w - len(label)) // 2:
                # Place label in the center of the item
                for l_idx, char in enumerate(label):
                    grid[y + dy][x + dx + l_idx] = char
                break


def generate_html_css(direction, justify, align, wrap, items_count):
    """Generates a complete standalone HTML/CSS file showing the flexbox layout."""
    item_html = ""
    for idx in range(1, items_count + 1):
        item_html += f"      <div class=\"flex-item\">{idx}</div>\n"
        
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=device-width, initial-scale=1.0">
  <title>CSS Flexbox Generated Layout</title>
  <style>
    body {{
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      background-color: #1e1e2e;
      color: #cdd6f4;
      display: flex;
      flex-direction: column;
      align-items: center;
      padding: 40px;
      margin: 0;
    }}
    
    h1 {{
      color: #89b4fa;
      margin-bottom: 5px;
    }}
    
    p {{
      color: #a6adc8;
      margin-bottom: 30px;
    }}
    
    .flex-container {{
      display: flex;
      flex-direction: {direction};
      justify-content: {justify};
      align-items: {align};
      flex-wrap: {wrap};
      
      background-color: #313244;
      border: 2px solid #45475a;
      border-radius: 12px;
      padding: 20px;
      width: 80%;
      max-width: 800px;
      min-height: 400px;
      box-shadow: 0 8px 24px rgba(0, 0, 0, 0.2);
    }}
    
    .flex-item {{
      background: linear-gradient(135deg, #b4befe, #89b4fa);
      color: #11111b;
      font-size: 24px;
      font-weight: bold;
      display: flex;
      align-items: center;
      justify-content: center;
      width: 80px;
      height: 80px;
      margin: 10px;
      border-radius: 8px;
      box-shadow: 0 4px 10px rgba(0, 0, 0, 0.15);
      transition: transform 0.2s;
    }}
    
    .flex-item:hover {{
      transform: scale(1.05);
    }}
    
    .code-box {{
      background-color: #11111b;
      border: 1px solid #45475a;
      border-radius: 8px;
      padding: 15px;
      margin-top: 30px;
      width: 80%;
      max-width: 800px;
      overflow-x: auto;
    }}
    
    pre {{
      margin: 0;
      color: #a6e3a1;
    }}
  </style>
</head>
<body>
  <h1>Flexbox Layout Preview</h1>
  <p>Properties: <code>flex-direction: {direction}; justify-content: {justify}; align-items: {align}; flex-wrap: {wrap};</code></p>
  
  <div class="flex-container">
{item_html}  </div>
  
  <div class="code-box">
    <pre>
/* CSS styles to reproduce this flex container */
.container {{
  display: flex;
  flex-direction: {direction};
  justify-content: {justify};
  align-items: {align};
  flex-wrap: {wrap};
}}
    </pre>
  </div>
</body>
</html>
"""
    return html_content


def interactive_mode():
    """Starts an interactive wizard to configure and visualize the flexbox properties."""
    print("=" * 60)
    print("          CSS FLEXBOX LAYOUT VISUALIZER & GENERATOR")
    print("=" * 60)
    
    # Defaults
    direction = "row"
    justify = "flex-start"
    align = "flex-start"
    wrap = "nowrap"
    items_count = 3
    
    while True:
        # Visual representation
        print("\nContainer Visual Preview:")
        print(draw_layout(direction, justify, align, wrap, items_count))
        print("-" * 60)
        print(f"Current Config: direction: {direction} | justify: {justify} | align: {align} | wrap: {wrap} | items: {items_count}")
        print("-" * 60)
        print("Choose property to configure:")
        print("1. flex-direction (row, row-reverse, column, column-reverse)")
        print("2. justify-content (flex-start, flex-end, center, space-between, space-around)")
        print("3. align-items (flex-start, center, flex-end)")
        print("4. flex-wrap (nowrap, wrap)")
        print("5. Number of items")
        print("6. Export HTML/CSS template")
        print("7. Exit")
        
        try:
            choice = input("\nSelect choice (1-7): ").strip()
            if choice == "1":
                dirs = ["row", "row-reverse", "column", "column-reverse"]
                print("\nChoose direction:")
                for idx, d in enumerate(dirs, 1):
                    print(f"{idx}. {d}")
                c_dir = int(input("> "))
                if 1 <= c_dir <= 4:
                    direction = dirs[c_dir - 1]
            elif choice == "2":
                j_opts = ["flex-start", "flex-end", "center", "space-between", "space-around"]
                print("\nChoose justify-content:")
                for idx, j in enumerate(j_opts, 1):
                    print(f"{idx}. {j}")
                c_j = int(input("> "))
                if 1 <= c_j <= 5:
                    justify = j_opts[c_j - 1]
            elif choice == "3":
                a_opts = ["flex-start", "center", "flex-end"]
                print("\nChoose align-items:")
                for idx, a in enumerate(a_opts, 1):
                    print(f"{idx}. {a}")
                c_a = int(input("> "))
                if 1 <= c_a <= 3:
                    align = a_opts[c_a - 1]
            elif choice == "4":
                w_opts = ["nowrap", "wrap"]
                print("\nChoose flex-wrap:")
                for idx, w in enumerate(w_opts, 1):
                    print(f"{idx}. {w}")
                c_w = int(input("> "))
                if 1 <= c_w <= 2:
                    wrap = w_opts[c_w - 1]
            elif choice == "5":
                count = int(input("\nEnter number of items (1-10): "))
                if 1 <= count <= 10:
                    items_count = count
            elif choice == "6":
                filename = input("\nEnter export filename (default: flexbox_layout.html): ").strip()
                if not filename:
                    filename = "flexbox_layout.html"
                html_content = generate_html_css(direction, justify, align, wrap, items_count)
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(html_content)
                print(f"[+] Flexbox template exported successfully to {filename}!")
            elif choice == "7":
                print("Goodbye!")
                break
            else:
                print("[-] Invalid selection.")
        except (ValueError, IndexError):
            print("[-] Invalid input. Please enter a valid number option.")
        except KeyboardInterrupt:
            print("\nExiting.")
            break


def main():
    parser = argparse.ArgumentParser(
        description="CSS Flexbox Layout Generator & Visualizer - Configure Flexbox and view ASCII previews."
    )
    parser.add_argument("-d", "--direction", default="row", choices=["row", "row-reverse", "column", "column-reverse"], help="flex-direction value")
    parser.add_argument("-j", "--justify", default="flex-start", choices=["flex-start", "flex-end", "center", "space-between", "space-around"], help="justify-content value")
    parser.add_argument("-a", "--align", default="flex-start", choices=["flex-start", "center", "flex-end"], help="align-items value")
    parser.add_argument("-w", "--wrap", default="nowrap", choices=["nowrap", "wrap"], help="flex-wrap value")
    parser.add_argument("-n", "--items", type=int, default=3, help="number of items to render")
    parser.add_argument("-o", "--output", help="output HTML file path")
    parser.add_argument("-i", "--interactive", action="store_true", help="launch interactive terminal visualizer wizard")
    
    args = parser.parse_args()
    
    if args.interactive or len(sys.argv) == 1:
        interactive_mode()
        return 0
        
    print(draw_layout(args.direction, args.justify, args.align, args.wrap, args.items))
    
    if args.output:
        html = generate_html_css(args.direction, args.justify, args.align, args.wrap, args.items)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"[+] HTML file exported to {args.output}")
        
    return 0


if __name__ == "__main__":
    sys.exit(main())
