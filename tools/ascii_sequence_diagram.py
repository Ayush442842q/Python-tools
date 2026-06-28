#!/usr/bin/env python3
"""
ASCII & Unicode Sequence Diagram Generator - Compile text specifications into terminal diagrams

This tool compiles simple sequence diagram text files (similar to PlantUML syntax)
into beautifully aligned Unicode or ASCII charts.

Usage:
    python tools/ascii_sequence_diagram.py [SPEC_FILE] [--style {unicode,ascii}] [--width SPACING]

Example spec format:
    participant Alice
    participant Bob
    Alice -> Bob: Get User Details
    Bob -> Database: Query record
    Database --> Bob: User info
    Bob --> Alice: User details profile
    Alice -> Alice: Update UI state

Example run:
    python tools/ascii_sequence_diagram.py spec.txt --style unicode
"""

import argparse
import sys
import re
from typing import List, Dict, Any, Tuple

# Constants for drawing styles
STYLES = {
    'unicode': {
        'line': '─',
        'dashed': '╌',
        'vertical': '│',
        'arrow_r': '➔',
        'arrow_l': '⇠',
        'self_top': '┌',
        'self_bottom': '└',
        'h_left': '├',
        'h_right': '┤',
        'h_center': '┼',
        'border_h': '═',
        'border_v': '║',
        'corner_tl': '╔',
        'corner_tr': '╗',
        'corner_bl': '╚',
        'corner_br': '╝',
    },
    'ascii': {
        'line': '-',
        'dashed': '-',
        'vertical': '|',
        'arrow_r': '>',
        'arrow_l': '<',
        'self_top': '+',
        'self_bottom': '+',
        'h_left': '+',
        'h_right': '+',
        'h_center': '+',
        'border_h': '-',
        'border_v': '|',
        'corner_tl': '+',
        'corner_tr': '+',
        'corner_bl': '+',
        'corner_br': '+',
    }
}

class SequenceDiagramGenerator:
    def __init__(self, style_name: str = 'unicode', col_width: int = 24):
        self.style = STYLES.get(style_name, STYLES['unicode'])
        self.col_width = col_width
        self.participants: List[str] = []
        self.events: List[Tuple[str, str, str, str, bool]] = [] # (type, from, to, label, is_dashed)

    def add_participant(self, name: str):
        name = name.strip()
        if name and name not in self.participants:
            self.participants.append(name)

    def parse_spec(self, text: str):
        lines = text.split('\n')
        
        # Regex matches:
        # 1. participant Name
        # 2. Name -> Name2: Label
        # 3. Name --> Name2: Label
        part_pattern = re.compile(r'^participant\s+(\w+)', re.I)
        msg_pattern = re.compile(r'^(\w+)\s*(-{1,2}>)\s*(\w+)\s*:\s*(.*)$')
        
        for line in lines:
            line = line.strip()
            if not line or line.startswith('#') or line.startswith('//'):
                continue
                
            # Check participant declaration
            part_match = part_pattern.match(line)
            if part_match:
                self.add_participant(part_match.group(1))
                continue
                
            # Check message event
            msg_match = msg_pattern.match(line)
            if msg_match:
                sender = msg_match.group(1)
                arrow = msg_match.group(2)
                receiver = msg_match.group(3)
                label = msg_match.group(4).strip()
                is_dashed = '--' in arrow
                
                # Auto-add participants if not declared
                self.add_participant(sender)
                self.add_participant(receiver)
                
                if sender == receiver:
                    self.events.append(('self', sender, receiver, label, is_dashed))
                else:
                    self.events.append(('message', sender, receiver, label, is_dashed))

    def render(self) -> str:
        if not self.participants:
            return "No participants found in diagram specifications."
            
        output = []
        num_parts = len(self.participants)
        
        # Calculate column centers
        # Column i is at index: padding + i * col_width
        # Each column header will be centered around this index
        half_width = self.col_width // 2
        
        # 1. Draw Participant Headers
        headers_line1 = []
        headers_line2 = []
        headers_line3 = []
        
        for p in self.participants:
            # Format header box
            p_len = len(p)
            box_width = max(p_len + 4, 10)
            if box_width % 2 != 0:
                box_width += 1
                
            pad = (self.col_width - box_width) // 2
            
            top_border = self.style['corner_tl'] + self.style['border_h'] * (box_width - 2) + self.style['corner_tr']
            mid_border = self.style['border_v'] + p.center(box_width - 2) + self.style['border_v']
            bot_border = self.style['corner_bl'] + self.style['border_h'] * (box_width - 2) + self.style['corner_br']
            
            headers_line1.append(" " * pad + top_border + " " * (self.col_width - pad - box_width))
            headers_line2.append(" " * pad + mid_border + " " * (self.col_width - pad - box_width))
            headers_line3.append(" " * pad + bot_border + " " * (self.col_width - pad - box_width))
            
        output.append("".join(headers_line1))
        output.append("".join(headers_line2))
        output.append("".join(headers_line3))
        
        # Helper to get horizontal index of a participant's vertical line
        def get_col_idx(part_idx: int) -> int:
            return part_idx * self.col_width + half_width

        # Helper to construct a blank line with vertical participant lines
        def make_lifelines() -> List[str]:
            line = [" "] * (num_parts * self.col_width)
            for j in range(num_parts):
                line[get_col_idx(j)] = self.style['vertical']
            return line

        # 2. Draw Events
        for ev_type, sender, receiver, label, is_dashed in self.events:
            idx_s = self.participants.index(sender)
            idx_r = self.participants.index(receiver)
            
            col_s = get_col_idx(idx_s)
            col_r = get_col_idx(idx_r)
            
            if ev_type == 'self':
                # Self call requires multiple lines
                # Line 1: empty lifelines with connection trigger
                # Line 2: label text offset to the right
                # Line 3: return connection
                # Line 1 (top connection)
                line1 = make_lifelines()
                line1[col_s] = self.style['h_left']
                # Draw small horizontal spur
                line1[col_s + 1] = self.style['line']
                line1[col_s + 2] = self.style['line']
                line1[col_s + 3] = self.style['self_top']
                output.append("".join(line1))
                
                # Line 2 (text and loop side-border)
                line2 = make_lifelines()
                line2[col_s + 3] = self.style['vertical']
                line2_str = "".join(line2)
                # Overlay label text
                label_offset = col_s + 5
                line2_str = line2_str[:label_offset] + label + line2_str[label_offset + len(label):]
                output.append(line2_str)
                
                # Line 3 (bottom connection with arrow pointing back)
                line3 = make_lifelines()
                line3[col_s] = self.style['h_left']
                line3[col_s + 1] = self.style['arrow_l'] if self.style['arrow_l'] != '⇠' else '<'
                line3[col_s + 2] = self.style['line']
                line3[col_s + 3] = self.style['self_bottom']
                output.append("".join(line3))
                
            else: # Standard message
                left_col = min(col_s, col_r)
                right_col = max(col_s, col_r)
                
                # Line 1: print label centered between the columns
                lbl_line = make_lifelines()
                lbl_center = (left_col + right_col) // 2
                lbl_start = lbl_center - (len(label) // 2)
                lbl_start = max(lbl_start, left_col + 2)
                
                lbl_str = "".join(lbl_line)
                # Overwrite lifelines inside the label bounds but keep active vertical lines if they are not spanned
                lbl_str = lbl_str[:lbl_start] + label + lbl_str[lbl_start + len(label):]
                output.append(lbl_str)
                
                # Line 2: draw arrow line
                arrow_line = make_lifelines()
                fill_char = self.style['dashed'] if is_dashed else self.style['line']
                
                for col in range(left_col + 1, right_col):
                    arrow_line[col] = fill_char
                    
                # Add cross intersections for other participants in between
                for j in range(num_parts):
                    c_idx = get_col_idx(j)
                    if left_col < c_idx < right_col:
                        arrow_line[c_idx] = self.style['h_center']
                        
                if col_s < col_r:
                    # Going right
                    arrow_line[col_s] = self.style['h_left']
                    arrow_line[col_r] = self.style['arrow_r']
                else:
                    # Going left
                    arrow_line[col_s] = self.style['h_right']
                    arrow_line[col_r] = self.style['arrow_l']
                    
                output.append("".join(arrow_line))
                
            # Add small vertical spacer after each event
            output.append("".join(make_lifelines()))
            
        # 3. Draw Participant Footers (mirrors header structure)
        output.append("".join(headers_line3))
        output.append("".join(headers_line2))
        output.append("".join(headers_line1))
        
        return "\n".join(output)

def main():
    parser = argparse.ArgumentParser(
        description="Compile a sequence diagram specification text file into a formatted console chart."
    )
    parser.add_argument(
        'spec_file',
        nargs='?',
        help='Path to diagram specification file. Reads from standard input if omitted.'
    )
    parser.add_argument(
        '--style',
        choices=['unicode', 'ascii'],
        default='unicode',
        help='Rendering style for lines and symbols (default: unicode)'
    )
    parser.add_argument(
        '--width',
        type=int,
        default=24,
        help='Spacing width between participant lines (default: 24)'
    )
    parser.add_argument(
        '--output',
        help='File path to save the output diagram text (prints to stdout if omitted)'
    )
    
    args = parser.parse_args()
    
    if args.width < 10:
        print("Error: Width spacing must be at least 10.", file=sys.stderr)
        return 1
        
    try:
        if args.spec_file:
            with open(args.spec_file, 'r', encoding='utf-8', errors='ignore') as f:
                spec_content = f.read()
        else:
            # Check if stdin has content
            if sys.stdin.isatty():
                parser.print_help()
                print("\nError: Please supply a spec file or pipe/redirect specs to standard input.", file=sys.stderr)
                return 1
            spec_content = sys.stdin.read()
            
        generator = SequenceDiagramGenerator(args.style, args.width)
        generator.parse_spec(spec_content)
        diagram = generator.render()
        
        if args.output:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(diagram + "\n")
            print(f"Diagram successfully saved to {args.output}", file=sys.stderr)
        else:
            print(diagram)
            
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
