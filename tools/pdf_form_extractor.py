#!/usr/bin/env python3
"""PDF Form Extractor

A zero-dependency PDF parser to extract interactive form fields (Text inputs,
Checkboxes, Radio buttons, Dropdowns, and Signatures) from PDF files.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# ANSI Colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[34m"
COLOR_CYAN = "\033[36m"
COLOR_GREY = "\033[90m"


class PDFParser:
    """A basic zero-dependency PDF object parser."""
    def __init__(self, data: bytes):
        self.data = data
        self.objects: Dict[Tuple[int, int], Dict[str, Any]] = {}
        self.catalog_ref: Optional[Tuple[int, int]] = None
        self._parse_all_objects()

    def _parse_all_objects(self):
        """Scan the bytes for PDF objects."""
        # Find all patterns of "N M obj"
        obj_matches = list(re.finditer(rb"(\d+)\s+(\d+)\s+obj", self.data))
        
        for i, match in enumerate(obj_matches):
            obj_id = int(match.group(1))
            obj_gen = int(match.group(2))
            start_pos = match.end()
            
            # The object ends before the next "obj" start or at the end of data.
            # We look for "endobj" in this range.
            end_pos = obj_matches[i+1].start() if i + 1 < len(obj_matches) else len(self.data)
            obj_bytes = self.data[start_pos:end_pos]
            
            endobj_idx = obj_bytes.find(b"endobj")
            if endobj_idx != -1:
                obj_bytes = obj_bytes[:endobj_idx]
                
            obj_bytes = obj_bytes.strip()
            
            # Parse the dictionary or content
            parsed_obj = self._parse_object_value(obj_bytes)
            if parsed_obj is not None:
                self.objects[(obj_id, obj_gen)] = parsed_obj
                
                # Check if it's the Catalog
                if isinstance(parsed_obj, dict) and parsed_obj.get("/Type") == "/Catalog":
                    self.catalog_ref = (obj_id, obj_gen)

    def _parse_object_value(self, b: bytes) -> Any:
        """Parse object bytes into Python structures (dicts, lists, strings)."""
        b = b.strip()
        if b.startswith(b"<<") and b.endswith(b">>"):
            return self._parse_dict(b[2:-2].strip())
        elif b.startswith(b"<<"):
            # Could have stream data after dictionary
            dict_end = b.find(b">>")
            if dict_end != -1:
                return self._parse_dict(b[2:dict_end].strip())
        return None

    def _parse_dict(self, b: bytes) -> Dict[str, Any]:
        """Parse a PDF dictionary << /Key Value >>."""
        d = {}
        # Tokenize keys and values
        # Keys start with / followed by characters
        # Values can be names (/Name), strings ((str)), hex (<hex>), dicts (<<>>), arrays ([]), refs (N M R)
        pos = 0
        n = len(b)
        
        def skip_whitespace():
            nonlocal pos
            while pos < n and b[pos:pos+1].isspace():
                pos += 1

        def next_token() -> Optional[bytes]:
            nonlocal pos
            skip_whitespace()
            if pos >= n:
                return None
                
            char = b[pos:pos+1]
            
            # Dictionary
            if b[pos:pos+2] == b"<<":
                start = pos
                depth = 0
                while pos < n:
                    if b[pos:pos+2] == b"<<":
                        depth += 1
                        pos += 2
                    elif b[pos:pos+2] == b">>":
                        depth -= 1
                        pos += 2
                        if depth == 0:
                            break
                    else:
                        pos += 1
                return b[start:pos]
                
            # Array
            if char == b"[":
                start = pos
                depth = 0
                while pos < n:
                    if b[pos:pos+1] == b"[":
                        depth += 1
                        pos += 1
                    elif b[pos:pos+1] == b"]":
                        depth -= 1
                        pos += 1
                        if depth == 0:
                            break
                    else:
                        pos += 1
                return b[start:pos]
                
            # String
            if char == b"(":
                start = pos
                depth = 0
                while pos < n:
                    if b[pos:pos+1] == b"(" and (pos == 0 or b[pos-1:pos] != b"\\"):
                        depth += 1
                        pos += 1
                    elif b[pos:pos+1] == b")" and (pos == 0 or b[pos-1:pos] != b"\\"):
                        depth -= 1
                        pos += 1
                        if depth == 0:
                            break
                    else:
                        pos += 1
                return b[start:pos]
                
            # Name, Hex, Reference, or Boolean/Numeric
            start = pos
            while pos < n:
                c = b[pos:pos+1]
                if c.isspace() or c in b"/[<>()[]{}":
                    if pos == start: # Delimiter is the token
                        if c in b"/[<>{}]":
                            pos += 1
                        return b[start:pos]
                    break
                pos += 1
            return b[start:pos]

        while pos < n:
            key_tok = next_token()
            if not key_tok:
                break
                
            if not key_tok.startswith(b"/"):
                continue
                
            val_tok = next_token()
            if val_tok is None:
                break
                
            key = key_tok.decode("utf-8", errors="ignore")
            d[key] = self._clean_value(val_tok)
            
        return d

    def _clean_value(self, val: bytes) -> Any:
        """Decode PDF values to Python types."""
        val = val.strip()
        if val.startswith(b"/"):
            return val.decode("utf-8", errors="ignore")
        elif val.startswith(b"("):
            # Text string, remove outer brackets and decode
            s = val[1:-1]
            # Simple escape resolver
            s = s.replace(b"\\(", b"(").replace(b"\\)", b")").replace(b"\\r", b"\r").replace(b"\\n", b"\n")
            # PDF String can be UTF-16 BE with BOM (0xFE 0xFF)
            if s.startswith(b"\xfe\xff"):
                try:
                    return s[2:].decode("utf-16-be", errors="ignore")
                except Exception:
                    pass
            return s.decode("utf-8", errors="ignore")
        elif val.startswith(b"<") and val.endswith(b">"):
            # Hex string
            hex_str = val[1:-1].decode("utf-8", errors="ignore")
            # If length is odd, append 0
            if len(hex_str) % 2 != 0:
                hex_str += "0"
            try:
                b_hex = bytes.fromhex(hex_str)
                if b_hex.startswith(b"\xfe\xff"):
                    return b_hex[2:].decode("utf-16-be", errors="ignore")
                return b_hex.decode("utf-8", errors="ignore")
            except Exception:
                return hex_str
        elif val.startswith(b"[") and val.endswith(b"]"):
            # Parse array elements recursively
            elements = []
            inner = val[1:-1].strip()
            # Split array elements (simple split by spaces/slash)
            # Find elements
            pos = 0
            while pos < len(inner):
                while pos < len(inner) and inner[pos:pos+1].isspace():
                    pos += 1
                if pos >= len(inner):
                    break
                
                # Extract token
                start = pos
                char = inner[pos:pos+1]
                if char == b"(":
                    depth = 0
                    while pos < len(inner):
                        if inner[pos:pos+1] == b"(":
                            depth += 1
                            pos += 1
                        elif inner[pos:pos+1] == b")":
                            depth -= 1
                            pos += 1
                            if depth == 0:
                                break
                        else:
                            pos += 1
                elif char == b"/":
                    pos += 1
                    while pos < len(inner) and not inner[pos:pos+1].isspace() and inner[pos:pos+1] not in b"/[":
                        pos += 1
                else:
                    while pos < len(inner) and not inner[pos:pos+1].isspace() and inner[pos:pos+1] not in b"/[":
                        pos += 1
                
                elements.append(self._clean_value(inner[start:pos]))
            return elements
        
        # Check if reference (e.g. "12 0 R")
        ref_match = re.match(r"^(\d+)\s+(\d+)\s+R$", val.decode("utf-8", errors="ignore"))
        if ref_match:
            return (int(ref_match.group(1)), int(ref_match.group(2)))
            
        # Parse boolean or numeric
        val_str = val.decode("utf-8", errors="ignore")
        if val_str == "true":
            return True
        elif val_str == "false":
            return False
        elif val_str == "null":
            return None
        
        try:
            if "." in val_str:
                return float(val_str)
            return int(val_str)
        except ValueError:
            return val_str

    def resolve_ref(self, val: Any) -> Any:
        """Resolve a PDF reference to its object."""
        if isinstance(val, tuple) and len(val) == 2 and isinstance(val[0], int) and isinstance(val[1], int):
            ref = (val[0], val[1])
            return self.objects.get(ref, None)
        return val


def extract_form_fields(parser: PDFParser) -> List[Dict[str, Any]]:
    """Traverse PDF AcroForm hierarchy and resolve form fields."""
    fields = []
    
    if not parser.catalog_ref:
        return []
        
    catalog = parser.objects.get(parser.catalog_ref)
    if not catalog:
        return []
        
    acroform_ref = catalog.get("/AcroForm")
    if not acroform_ref:
        # Check if AcroForm is directly in catalog
        return []
        
    acroform = parser.resolve_ref(acroform_ref)
    if not isinstance(acroform, dict):
        return []
        
    fields_ref = acroform.get("/Fields")
    if not fields_ref:
        return []
        
    fields_list = parser.resolve_ref(fields_ref)
    if not isinstance(fields_list, list):
        # Could be a single reference
        fields_list = [fields_ref] if fields_ref else []
        
    # Queue for DFS/BFS traversal of the fields tree
    queue = []
    for ref in fields_list:
        queue.append((ref, {})) # (ref/dict, inherited_properties)
        
    while queue:
        item, inherited = queue.pop(0)
        resolved = parser.resolve_ref(item)
        if not isinstance(resolved, dict):
            continue
            
        # Inherit fields
        current_inherited = inherited.copy()
        for key in ["/FT", "/T", "/V", "/DV", "/Opt"]:
            if key in resolved:
                current_inherited[key] = resolved[key]
                
        kids = parser.resolve_ref(resolved.get("/Kids"))
        if isinstance(kids, list):
            # It's a parent node, traverse children
            for kid in kids:
                queue.append((kid, current_inherited))
        else:
            # Leaf node / Form Field
            field_data = {}
            
            # Resolve name
            t_val = resolved.get("/T") or inherited.get("/T")
            field_data["name"] = parser.resolve_ref(t_val) or "(unnamed)"
            
            # Resolve type
            ft_val = resolved.get("/FT") or inherited.get("/FT")
            ft_str = parser.resolve_ref(ft_val)
            
            type_mapping = {
                "/Tx": "Text",
                "/Btn": "Button (Checkbox/Radio)",
                "/Ch": "Choice (Dropdown/List)",
                "/Sig": "Signature"
            }
            field_data["type"] = type_mapping.get(ft_str, ft_str or "Unknown")
            
            # Resolve value
            v_val = resolved.get("/V") or inherited.get("/V")
            field_data["value"] = parser.resolve_ref(v_val) or ""
            
            # Resolve default value
            dv_val = resolved.get("/DV") or inherited.get("/DV")
            field_data["default_value"] = parser.resolve_ref(dv_val) or ""
            
            # Choice options
            opt_val = resolved.get("/Opt") or inherited.get("/Opt")
            options = parser.resolve_ref(opt_val)
            if isinstance(options, list):
                # Clean choices list (can be string or [val, label] pairs)
                cleaned_opts = []
                for opt in options:
                    resolved_opt = parser.resolve_ref(opt)
                    if isinstance(resolved_opt, list) and len(resolved_opt) >= 2:
                        cleaned_opts.append(f"{resolved_opt[0]} ({resolved_opt[1]})")
                    else:
                        cleaned_opts.append(str(resolved_opt))
                field_data["options"] = cleaned_opts
            
            fields.append(field_data)
            
    # Also scan for widgets directly if AcroForm tree traversal yields nothing
    if not fields:
        # Check all widgets
        for (obj_id, obj_gen), obj in parser.objects.items():
            if isinstance(obj, dict) and obj.get("/Subtype") == "/Widget":
                t_val = obj.get("/T")
                if t_val:
                    field_data = {
                        "name": parser.resolve_ref(t_val),
                        "type": type_mapping.get(parser.resolve_ref(obj.get("/FT")), "Widget"),
                        "value": parser.resolve_ref(obj.get("/V")) or "",
                        "default_value": parser.resolve_ref(obj.get("/DV")) or ""
                    }
                    fields.append(field_data)
                    
    return fields


def main():
    parser = argparse.ArgumentParser(
        description="PDF Form Extractor - A zero-dependency PDF parser to extract interactive form fields."
    )
    parser.add_argument(
        "pdf_path",
        help="Path to the PDF file to scan"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output the extracted fields as JSON format"
    )
    args = parser.parse_args()
    
    path = Path(args.pdf_path).resolve()
    if not path.exists():
        print(f"{COLOR_RED}Error: File '{path}' does not exist.{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)
        
    try:
        with open(path, "rb") as f:
            data = f.read()
    except Exception as e:
        print(f"{COLOR_RED}Error reading file: {e}{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)
        
    # Check signature
    if not data.startswith(b"%PDF"):
        print(f"{COLOR_RED}Error: File does not appear to be a valid PDF (missing %PDF header).{COLOR_RESET}", file=sys.stderr)
        sys.exit(1)
        
    print(f"{COLOR_GREY}Parsing PDF structures...{COLOR_RESET}", file=sys.stderr)
    pdf_parser = PDFParser(data)
    
    fields = extract_form_fields(pdf_parser)
    
    if args.json:
        print(json.dumps(fields, indent=4))
        sys.exit(0)
        
    print(f"\n{COLOR_BOLD}{COLOR_CYAN}=== PDF Form Field Report ==={COLOR_RESET}\n")
    print(f"{COLOR_BOLD}File:{COLOR_RESET} {path.name}")
    print(f"{COLOR_BOLD}Total Form Fields Found:{COLOR_RESET} {len(fields)}\n")
    
    if not fields:
        print(f"{COLOR_YELLOW}No interactive form fields or AcroForm definitions found in this PDF.{COLOR_RESET}")
        sys.exit(0)
        
    # Print formatted table
    col_name = "Field Name"
    col_type = "Field Type"
    col_val = "Current Value"
    
    # Calculate widths
    w_name = max(max(len(f["name"]) for f in fields), len(col_name))
    w_type = max(max(len(f["type"]) for f in fields), len(col_type))
    
    # Print header
    header = f"{COLOR_BOLD}{col_name:<{w_name}} | {col_type:<{w_type}} | {col_val}{COLOR_RESET}"
    divider = "-" * (w_name + 1) + "+" + "-" * (w_type + 2) + "+" + "-" * 30
    print(header)
    print(divider)
    
    for f in fields:
        name_str = f"{COLOR_CYAN}{f['name']:<{w_name}}{COLOR_RESET}"
        type_str = f"{COLOR_GREEN}{f['type']:<{w_type}}{COLOR_RESET}"
        val_str = str(f["value"]) if f["value"] != "" else f"{COLOR_GREY}(empty){COLOR_RESET}"
        
        print(f"{name_str} | {type_str} | {val_str}")
        if "options" in f:
            print(f"  {COLOR_GREY}Options: {', '.join(f['options'])}{COLOR_RESET}")
        if f.get("default_value"):
            print(f"  {COLOR_GREY}Default: {f['default_value']}{COLOR_RESET}")
            
    print()


if __name__ == "__main__":
    main()
