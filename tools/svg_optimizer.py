#!/usr/bin/env python3
"""
svg_optimizer - Standalone SVG vector graphic optimizer and minifier

Parses SVG files to strip editor metadata (Inkscape, Illustrator), clean unused groups,
shorten colors, and reduce coordinate precision in paths and points to compress file size.

Usage:
    python tools/svg_optimizer.py [FILE] [-o OUTPUT] [-p PRECISION]

Options:
    FILE                SVG file to optimize (reads from standard input if omitted)
    -o, --output        Output file path (writes to stdout if omitted)
    -p, --precision     Decimal precision for path coordinates (default: 2)
    --strip-metadata    Remove <metadata> and RDF tags (default: True)
    --remove-empty-g    Delete empty group (<g>) tags (default: True)

Example:
    python tools/svg_optimizer.py logo.svg -o logo.min.svg -p 1
"""

import os
import re
import sys
import xml.etree.ElementTree as ET
import argparse

# Console colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_BOLD = "\033[1m"
COLOR_END = "\033[0m"

# Namespace URIs for editor junk
NAMESPACES_TO_REMOVE = {
    'http://www.inkscape.org/namespaces/inkscape',
    'http://sodipodi.sourceforge.net/DTD/sodipodi-0.dtd',
    'http://ns.adobe.com/AdobeSVGViewerExtensions/3.0/',
    'http://ns.adobe.com/SaveForWeb/1.0/',
    'http://ns.adobe.com/AdobeIllustrator/10.0/',
    'http://ns.adobe.com/Variables/1.0/',
    'http://ns.adobe.com/Graphs/1.0/',
    'http://ns.adobe.com/Flows/1.0/',
    'http://ns.adobe.com/ImageReplacement/1.0/',
    'http://ns.adobe.com/Extensibility/1.0/',
    'http://www.w3.org/1999/02/22-rdf-syntax-ns#',
    'http://web.resource.org/cc/',
    'http://purl.org/dc/elements/1.1/'
}

def clean_element(elem, strip_metadata=True, remove_empty_g=True):
    """Recursively clean an XML element and its children."""
    # Remove metadata elements
    if strip_metadata:
        # Check tag name (ignoring namespace prefix in braces)
        tag_local = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
        if tag_local.lower() in ('metadata', 'rdf', 'rdf:rdf', 'work', 'format', 'type', 'title'):
            return None

    # Remove attributes that contain namespaces we want to discard
    attrs_to_del = []
    for attr in elem.attrib:
        if '}' in attr:
            ns = attr.split('}')[0].strip('{')
            if ns in NAMESPACES_TO_REMOVE:
                attrs_to_del.append(attr)
        # Drop inkscape/sodipodi specific raw attributes
        attr_local = attr.split('}')[-1]
        if attr_local.startswith('inkscape:') or attr_local.startswith('sodipodi:'):
            attrs_to_del.append(attr)

    for attr in attrs_to_del:
        del elem.attrib[attr]

    # Recursively clean children
    cleaned_children = []
    for child in list(elem):
        cleaned_child = clean_element(child, strip_metadata, remove_empty_g)
        if cleaned_child is not None:
            # Drop empty group tags if requested
            if remove_empty_g and cleaned_child.tag.endswith('}g') and len(cleaned_child) == 0 and not cleaned_child.attrib:
                continue
            cleaned_children.append(cleaned_child)

    # Replace children list
    elem.clear()
    elem.text = None
    elem.tail = None
    
    # Restore cleaned attributes and children
    for attr, val in elem.attrib.items():
        elem.set(attr, val)
    elem.extend(cleaned_children)

    return elem

def optimize_path_data(path_str, precision):
    """Round numeric coordinates in path data to the specified decimal precision."""
    if not path_str:
        return ""

    def round_match(match):
        val = float(match.group(0))
        # Format float and strip unnecessary trailing zeros/dot
        formatted = f"{val:.{precision}f}"
        if '.' in formatted:
            formatted = formatted.rstrip('0').rstrip('.')
        return formatted

    # Match float numbers (e.g. 12.3456, -0.5, .25)
    # Avoid matching commas or command letters
    path_str = re.sub(r'-?\d*\.\d+|-?\d+\.\d*', round_match, path_str)
    
    # Compress whitespaces around command characters and clean commas
    path_str = re.sub(r'\s*([a-zA-Z])\s*', r'\1', path_str) # Spaces around commands
    path_str = re.sub(r'\s*,\s*', r',', path_str)           # Spaces around commas
    path_str = re.sub(r'\s+', r' ', path_str)               # Multiple spaces to single space
    
    return path_str.strip()

def optimize_points_data(points_str, precision):
    """Round numeric coordinates in polygon/polyline points data."""
    if not points_str:
        return ""
    
    # Split by spaces or commas
    parts = re.split(r'[,\s]+', points_str.strip())
    rounded = []
    for part in parts:
        try:
            val = float(part)
            formatted = f"{val:.{precision}f}"
            if '.' in formatted:
                formatted = formatted.rstrip('0').rstrip('.')
            rounded.append(formatted)
        except ValueError:
            rounded.append(part)
            
    # Reassemble: standard is coordinate pairs separated by spaces, x/y separated by comma
    pairs = []
    for idx in range(0, len(rounded), 2):
        if idx + 1 < len(rounded):
            pairs.append(f"{rounded[idx]},{rounded[idx+1]}")
        else:
            pairs.append(rounded[idx])
            
    return " ".join(pairs)

def minify_colors(style_str):
    """Minify color codes inside inline style declarations."""
    if not style_str:
        return ""
    
    # Optimize hex values: #ffffff -> #fff, #AABBCC -> #abc
    style_str = re.sub(r'#([0-9a-fA-F])\1([0-9a-fA-F])\2([0-9a-fA-F])\3(?=[^a-fA-F0-9]|$)', r'#\1\2\3', style_str)
    
    # rgb(r,g,b) to hex if possible (only for simple integer rgb values)
    def rgb_repl(match):
        try:
            r = int(match.group(1))
            g = int(match.group(2))
            b = int(match.group(3))
            if 0 <= r <= 255 and 0 <= g <= 255 and 0 <= b <= 255:
                hex_color = f"#{r:02x}{g:02x}{b:02x}"
                # Try to compress hex color
                return re.sub(r'#([0-9a-fA-F])\1([0-9a-fA-F])\2([0-9a-fA-F])\3', r'#\1\2\3', hex_color)
        except Exception:
            pass
        return match.group(0)

    style_str = re.sub(r'rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)', rgb_repl, style_str)
    return style_str

def optimize_element_attributes(elem, precision):
    """Walk element tree and optimize coordinates/styles in specific attributes."""
    tag_local = elem.tag.split('}')[-1] if '}' in elem.tag else elem.tag
    
    # Optimize paths
    if tag_local == 'path' and 'd' in elem.attrib:
        elem.attrib['d'] = optimize_path_data(elem.attrib['d'], precision)
        
    # Optimize polygon/polyline points
    if tag_local in ('polygon', 'polyline') and 'points' in elem.attrib:
        elem.attrib['points'] = optimize_points_data(elem.attrib['points'], precision)
        
    # Optimize numeric fields
    for attr in ('x', 'y', 'x1', 'y1', 'x2', 'y2', 'cx', 'cy', 'r', 'rx', 'ry', 'width', 'height'):
        if attr in elem.attrib:
            try:
                val = float(elem.attrib[attr])
                formatted = f"{val:.{precision}f}"
                if '.' in formatted:
                    formatted = formatted.rstrip('0').rstrip('.')
                elem.attrib[attr] = formatted
            except ValueError:
                pass
                
    # Optimize styles & colors
    if 'style' in elem.attrib:
        elem.attrib['style'] = minify_colors(elem.attrib['style'])
    for attr in ('fill', 'stroke'):
        if attr in elem.attrib:
            elem.attrib[attr] = minify_colors(elem.attrib[attr])

    for child in elem:
        optimize_element_attributes(child, precision)

def main():
    parser = argparse.ArgumentParser(description="Clean editor metadata and reduce coordinate precision of SVG vector graphics.")
    parser.add_argument('file', nargs='?', help='Path to SVG file (reads from stdin if omitted)')
    parser.add_argument('-o', '--output', type=str, help='Output optimized SVG file path')
    parser.add_argument('-p', '--precision', type=int, default=2, help='Decimal precision for coordinates (default: 2)')
    parser.add_argument('--no-metadata', action='store_true', help='Do NOT strip metadata tags')
    parser.add_argument('--no-empty-g', action='store_true', help='Do NOT remove empty group <g> tags')

    args = parser.parse_args()

    # Read SVG content
    if args.file:
        if not os.path.exists(args.file):
            print(f"{COLOR_RED}Error: File '{args.file}' not found.{COLOR_END}", file=sys.stderr)
            return 1
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                svg_data = f.read()
        except Exception as e:
            print(f"{COLOR_RED}Error reading file: {e}{COLOR_END}", file=sys.stderr)
            return 1
    else:
        if sys.stdin.isatty():
            print(f"{COLOR_YELLOW}Reading SVG from standard input (Ctrl+D to process)...{COLOR_END}", file=sys.stderr)
        svg_data = sys.stdin.read()

    if not svg_data.strip():
        print(f"{COLOR_YELLOW}Warning: Input is empty.{COLOR_END}", file=sys.stderr)
        return 0

    try:
        # 1. Parse XML structure
        # Register standard namespaces to avoid custom prefixes (ns0:svg) in output
        ET.register_namespace('', 'http://www.w3.org/2000/svg')
        ET.register_namespace('xlink', 'http://www.w3.org/1999/xlink')
        
        # Parse SVG from string
        root = ET.fromstring(svg_data)

        # 2. Clean namespaces and elements
        root = clean_element(root, strip_metadata=not args.no_metadata, remove_empty_g=not args.no_empty_g)
        
        # 3. Reduce precision and optimize values
        optimize_element_attributes(root, args.precision)

        # 4. Serialize back to string
        # XML declarations and namespaces will be formatted
        out_bytes = ET.tostring(root, encoding='utf-8', method='xml')
        output_svg = out_bytes.decode('utf-8')
        
        # Remove XML declaration if it wasn't in the original to be tidy, or keep standard
        # Standard SVG is fine without <?xml version="1.0" encoding="utf-8"?>
        
        # Minify output spaces between tags
        output_svg = re.sub(r'>\s+<', '><', output_svg)

        # Write output
        if args.output:
            write_mode = 'w'
            with open(args.output, write_mode, encoding='utf-8') as f:
                f.write(output_svg)
            
            orig_size = len(svg_data)
            new_size = len(output_svg)
            diff = orig_size - new_size
            pct = (diff / orig_size) * 100 if orig_size > 0 else 0
            
            print(f"\n{COLOR_GREEN}{COLOR_BOLD}SVG optimization complete!{COLOR_END}")
            print(f"  Optimized Saved to: {COLOR_YELLOW}{args.output}{COLOR_END}")
            print(f"  Original Size:      {orig_size} bytes")
            print(f"  Optimized Size:     {new_size} bytes")
            print(f"  Size Reduction:     {diff} bytes ({pct:.1f}%)")
        else:
            print(output_svg)

    except Exception as e:
        print(f"{COLOR_RED}Error optimizing SVG: {e}{COLOR_END}", file=sys.stderr)
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
