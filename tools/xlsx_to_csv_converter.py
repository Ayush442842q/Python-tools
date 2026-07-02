#!/usr/bin/env python3
"""
Zero-Dependency Excel (.xlsx) to CSV Converter

Parses Microsoft Excel OpenXML spreadsheets (.xlsx) natively by unzipping 
and extracting worksheet data and shared string tables using Python standard libraries.
Supports sheet listings, metadata extraction, row previews, and exports to CSV, TSV, or JSON.
"""

import argparse
import csv
import json
import os
import sys
import zipfile
import xml.etree.ElementTree as ET
from typing import List, Tuple, Dict, Any, Optional

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

def log_success(msg: str):
    print(color_text("[+] " + msg, COLOR_GREEN))

def log_info(msg: str):
    print(color_text("[*] " + msg, COLOR_CYAN))

def log_warning(msg: str):
    print(color_text("[!] " + msg, COLOR_YELLOW))

def log_error(msg: str):
    print(color_text("[-] ERROR: " + msg, COLOR_RED), file=sys.stderr)

# --- Excel Sheet Helper Functions ---

def parse_cell_coordinate(coord: str) -> Tuple[int, int]:
    """Converts Excel cell coordinate (e.g., 'BC12') to 0-based (row_idx, col_idx)."""
    col_str = ""
    row_str = ""
    for char in coord:
        if char.isalpha():
            col_str += char
        else:
            row_str += char
            
    if not col_str or not row_str:
        raise ValueError(f"Invalid coordinate format: {coord}")
        
    row_idx = int(row_str) - 1
    
    col_idx = 0
    for char in col_str:
        col_idx = col_idx * 26 + (ord(char.upper()) - ord('A') + 1)
        
    return row_idx, col_idx - 1

def strip_namespaces(tag: str) -> str:
    """Strips namespace prefixes from XML tags (e.g., '{http://...}v' -> 'v')."""
    return tag.split('}')[-1] if '}' in tag else tag

class XLSXParser:
    def __init__(self, filepath: str):
        self.filepath = filepath
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"File not found: {filepath}")
        if not zipfile.is_zipfile(filepath):
            raise ValueError("Input file is not a valid zip archive (.xlsx format)")
            
        self.zip_ref = zipfile.ZipFile(filepath, 'r')
        self.shared_strings: List[str] = []
        self.sheets: List[Dict[str, str]] = []  # List of {'name': name, 'id': id, 'path': path}
        self.namespaces: Dict[str, str] = {}
        
        self._initialize()
        
    def close(self):
        self.zip_ref.close()
        
    def _read_xml_root(self, internal_path: str) -> ET.Element:
        """Reads and parses an XML file from the ZIP archive."""
        with self.zip_ref.open(internal_path) as xml_file:
            tree = ET.parse(xml_file)
            return tree.getroot()

    def _initialize(self):
        """Initializes sheets map and parses shared strings."""
        # 1. Parse Shared Strings
        if "xl/sharedStrings.xml" in self.zip_ref.namelist():
            root = self._read_xml_root("xl/sharedStrings.xml")
            for si in root:
                # Accumulate all <t> tags in this <si> block
                # Excel sometimes splits strings with rich formatting into multiple <r><t> tags
                text_parts = []
                for t in si.iter():
                    if strip_namespaces(t.tag) == 't':
                        if t.text:
                            text_parts.append(t.text)
                self.shared_strings.append("".join(text_parts))
                
        # 2. Parse relationships to worksheets
        rels: Dict[str, str] = {}
        if "xl/_rels/workbook.xml.rels" in self.zip_ref.namelist():
            root = self._read_xml_root("xl/_rels/workbook.xml.rels")
            for rel in root:
                tag = strip_namespaces(rel.tag)
                if tag == "Relationship":
                    rel_id = rel.attrib.get("Id")
                    rel_target = rel.attrib.get("Target")
                    # Relative to xl/
                    if rel_target and not rel_target.startswith("xl/"):
                        if rel_target.startswith("/xl/"):
                            rel_target = rel_target[1:]
                        else:
                            rel_target = f"xl/{rel_target}"
                    rels[rel_id] = rel_target
                    
        # 3. Parse workbook structure (sheet names & relation IDs)
        if "xl/workbook.xml" in self.zip_ref.namelist():
            root = self._read_xml_root("xl/workbook.xml")
            # Find the sheets element
            for child in root.iter():
                tag = strip_namespaces(child.tag)
                if tag == "sheet":
                    name = child.attrib.get("name")
                    sheet_id = child.attrib.get("sheetId")
                    # The link relationship ID
                    r_id = None
                    for key, val in child.attrib.items():
                        if strip_namespaces(key) == 'id':
                            r_id = val
                            break
                            
                    sheet_path = rels.get(r_id)
                    if sheet_path and sheet_path in self.zip_ref.namelist():
                        self.sheets.append({
                            'name': name,
                            'id': sheet_id,
                            'path': sheet_path
                        })

    def get_sheet_names(self) -> List[str]:
        return [sheet['name'] for sheet in self.sheets]

    def parse_sheet(self, sheet_name: str) -> List[List[str]]:
        """Parses sheet worksheet XML, returns list of lists of strings (grid)."""
        sheet_info = next((s for s in self.sheets if s['name'].lower() == sheet_name.lower()), None)
        if not sheet_info:
            raise ValueError(f"Sheet '{sheet_name}' not found in workbook")
            
        root = self._read_xml_root(sheet_info['path'])
        
        cells: Dict[Tuple[int, int], str] = {}
        max_row = -1
        max_col = -1
        
        for c in root.iter():
            tag = strip_namespaces(c.tag)
            if tag == 'c':
                r_coord = c.attrib.get('r')
                if not r_coord:
                    continue
                try:
                    row_idx, col_idx = parse_cell_coordinate(r_coord)
                except ValueError:
                    continue
                    
                cell_type = c.attrib.get('t', 'n')  # Default is numeric 'n'
                cell_val = ""
                
                # Extract value node
                v_node = None
                for child in c:
                    if strip_namespaces(child.tag) == 'v':
                        v_node = child
                        break
                        
                if v_node is not None and v_node.text is not None:
                    raw_val = v_node.text
                    if cell_type == 's':  # Shared string reference
                        idx = int(raw_val)
                        if 0 <= idx < len(self.shared_strings):
                            cell_val = self.shared_strings[idx]
                    elif cell_type == 'b':  # Boolean
                        cell_val = "TRUE" if raw_val == '1' else "FALSE"
                    elif cell_type == 'inlineStr':  # Inline string
                        cell_val = raw_val
                    else:
                        cell_val = raw_val
                        
                # Also handle inline string structures (<is><t>text</t></is>)
                is_node = None
                for child in c:
                    if strip_namespaces(child.tag) == 'is':
                        is_node = child
                        break
                if is_node is not None:
                    for child in is_node:
                        if strip_namespaces(child.tag) == 't' and child.text:
                            cell_val = child.text
                            
                cells[(row_idx, col_idx)] = cell_val
                max_row = max(max_row, row_idx)
                max_col = max(max_col, col_idx)
                
        # Build grid
        grid = [["" for _ in range(max_col + 1)] for _ in range(max_row + 1)]
        for (r, col), val in cells.items():
            grid[r][col] = val
            
        return grid

# --- CLI and Output Formatters ---

def write_to_csv(grid: List[List[str]], filepath: str):
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerows(grid)

def write_to_tsv(grid: List[List[str]], filepath: str):
    with open(filepath, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f, delimiter='\t')
        writer.writerows(grid)

def write_to_json(grid: List[List[str]], filepath: str, key_by_header: bool = True):
    if not grid:
        data = []
    elif len(grid) == 1 or not key_by_header:
        data = grid
    else:
        headers = grid[0]
        data = []
        for row in grid[1:]:
            row_dict = {}
            for col_idx, val in enumerate(row):
                header = headers[col_idx] if col_idx < len(headers) else f"Column_{col_idx}"
                # Handle duplicate header names gracefully
                if header in row_dict:
                    header = f"{header}_{col_idx}"
                row_dict[header] = val
            data.append(row_dict)
            
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def display_sheet_preview(grid: List[List[str]], limit: int = 10):
    if not grid:
        print("Empty sheet.")
        return
        
    print(color_text(f"--- SHEET PREVIEW (showing up to {limit} rows) ---", COLOR_BOLD))
    # Determine column widths for nice terminal output
    widths = []
    num_cols = len(grid[0])
    for col_idx in range(num_cols):
        max_w = 0
        for r_idx in range(min(len(grid), limit)):
            row = grid[r_idx]
            cell_w = len(row[col_idx]) if col_idx < len(row) else 0
            max_w = max(max_w, cell_w)
        widths.append(min(max(max_w, 3), 20))  # Min width 3, Max width 20 (truncated)
        
    for r_idx in range(min(len(grid), limit)):
        row = grid[r_idx]
        row_str_parts = []
        for col_idx, width in enumerate(widths):
            val = row[col_idx] if col_idx < len(row) else ""
            if len(val) > width:
                val = val[:width-3] + "..."
            row_str_parts.append(val.ljust(width))
            
        color = COLOR_CYAN if r_idx == 0 else COLOR_RESET
        print(color_text(" | ".join(row_str_parts), color))
        
    if len(grid) > limit:
        print(color_text(f"... and {len(grid) - limit} more rows ...", COLOR_YELLOW))
    print(color_text("-" * (sum(widths) + (len(widths) - 1) * 3), COLOR_BOLD))

def main():
    parser = argparse.ArgumentParser(
        description="Zero-Dependency Excel (.xlsx) converter to CSV, TSV, or JSON"
    )
    parser.add_argument("file", help="Path to the Excel .xlsx file")
    parser.add_argument("-l", "--list", action="store_true", help="List all worksheets in the file")
    parser.add_argument("-s", "--sheet", help="Worksheet to process (defaults to the first sheet)")
    parser.add_argument("-o", "--output", help="Output file path")
    parser.add_argument("-f", "--format", choices=["csv", "tsv", "json"], default="csv", help="Output format (csv, tsv, json)")
    parser.add_argument("-p", "--preview", action="store_true", help="Print a preview of sheet rows in the terminal")
    parser.add_argument("--raw-json", action="store_true", help="For JSON output, export as grid list of lists instead of object records mapping headers")
    
    args = parser.parse_args()
    
    try:
        parser_obj = XLSXParser(args.file)
    except Exception as e:
        log_error(f"Failed to open/parse workbook: {e}")
        sys.exit(1)
        
    sheets = parser_obj.get_sheet_names()
    
    if args.list:
        log_info(f"Worksheets in '{args.file}':")
        for idx, s in enumerate(sheets, start=1):
            print(f" {idx}. {color_text(s, COLOR_GREEN)}")
        parser_obj.close()
        sys.exit(0)
        
    if not sheets:
        log_error("Workbook contains no valid worksheets.")
        parser_obj.close()
        sys.exit(1)
        
    # Select sheet
    selected_sheet = args.sheet
    if not selected_sheet:
        selected_sheet = sheets[0]
        
    if selected_sheet.lower() not in [s.lower() for s in sheets]:
        log_error(f"Sheet '{selected_sheet}' not found in workbook. Available sheets:")
        for s in sheets:
            print(f" - {s}")
        parser_obj.close()
        sys.exit(1)
        
    # Resolve exact casing of sheet name
    exact_sheet_name = next(s for s in sheets if s.lower() == selected_sheet.lower())
    
    log_info(f"Parsing worksheet: '{exact_sheet_name}'...")
    try:
        grid = parser_obj.parse_sheet(exact_sheet_name)
    except Exception as e:
        log_error(f"Failed to parse sheet '{exact_sheet_name}': {e}")
        parser_obj.close()
        sys.exit(1)
        
    parser_obj.close()
    
    row_count = len(grid)
    col_count = len(grid[0]) if grid else 0
    log_success(f"Parsed {row_count} rows, {col_count} columns.")
    
    if args.preview or not args.output:
        display_sheet_preview(grid)
        
    if args.output:
        fmt = args.format.lower()
        # Auto-detect format from extension if not explicitly specified
        if not args.format:
            _, ext = os.path.splitext(args.output.lower())
            if ext == '.tsv':
                fmt = 'tsv'
            elif ext == '.json':
                fmt = 'json'
            else:
                fmt = 'csv'
                
        log_info(f"Writing output as {fmt.upper()} to: {args.output}...")
        try:
            if fmt == 'csv':
                write_to_csv(grid, args.output)
            elif fmt == 'tsv':
                write_to_tsv(grid, args.output)
            elif fmt == 'json':
                write_to_json(grid, args.output, key_by_header=not args.raw_json)
            log_success("Write completed successfully.")
        except Exception as e:
            log_error(f"Failed to write output file: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
