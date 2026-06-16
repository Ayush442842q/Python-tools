#!/usr/bin/env python3
"""
SVG Optimizer & Minifier

Optimizes SVG vector graphics files by removing editor metadata, namespaces,
comments, and empty elements, and optionally rounding coordinates to a custom 
decimal precision.

Usage:
    python tools/svg_optimizer.py -i input.svg -o output.svg -p 2
    python tools/svg_optimizer.py -i input.svg --dry-run
"""

import argparse
import os
import re
import sys

def optimize_svg(svg_content, precision=2, strip_metadata=True):
    """
    Optimizes the SVG content.
    """
    # 1. Remove XML/HTML comments
    svg_content = re.sub(r'<!--.*?-->', '', svg_content, flags=re.DOTALL)

    # 2. Strip editor namespaces and metadata blocks if requested
    if strip_metadata:
        # Remove metadata tags and their contents
        svg_content = re.sub(r'<metadata>.*?</metadata>', '', svg_content, flags=re.DOTALL)
        svg_content = re.sub(r'<desc>.*?</desc>', '', svg_content, flags=re.DOTALL)
        svg_content = re.sub(r'<title>.*?</title>', '', svg_content, flags=re.DOTALL)
        # Remove sodipodi:namedview blocks
        svg_content = re.sub(r'<sodipodi:namedview.*?>.*?</sodipodi:namedview>', '', svg_content, flags=re.DOTALL)
        svg_content = re.sub(r'<sodipodi:namedview.*?/>', '', svg_content, flags=re.DOTALL)

    # 3. Strip editor-specific attributes (inkscape:*, sodipodi:*, etc.)
    editor_attrs = [
        r'\s*inkscape:[a-z0-9-]+="[^"]*"',
        r'\s*sodipodi:[a-z0-9-]+="[^"]*"',
        r'\s*xmlns:inkscape="[^"]*"',
        r'\s*xmlns:sodipodi="[^"]*"',
        r'\s*xmlns:rdf="[^"]*"',
        r'\s*xmlns:cc="[^"]*"',
        r'\s*xmlns:dc="[^"]*"',
        r'\s*rdf:[a-z0-9-]+="[^"]*"',
    ]
    for pattern in editor_attrs:
        svg_content = re.sub(pattern, '', svg_content, flags=re.IGNORECASE)

    # 4. Round decimal coordinates/numbers to specified precision
    if precision >= 0:
        # Match floating point numbers in attributes, especially path data (d="...")
        # A float can look like: 12.3456, -0.456, .456, -.456
        float_pattern = re.compile(r'([-+]?\d*\.\d+([eE][-+]?\d+)?)')
        
        def round_match(match):
            val_str = match.group(1)
            try:
                val = float(val_str)
                # Formats float to remove trailing zeros and format correctly
                rounded = f"{val:.{precision}f}".rstrip('0').rstrip('.')
                # If rounded is empty (e.g. for .000), make it 0
                return rounded if rounded and rounded != '-' else '0'
            except ValueError:
                return val_str

        # Find all attributes containing path coordinates, points, or numeric dimensions
        # Matches content inside double quotes: name="value"
        attr_pattern = re.compile(r'([a-zA-Z0-9:-]+)="([^"]*)"')

        def opt_attributes(match):
            attr_name = match.group(1)
            attr_val = match.group(2)
            # Apply coordinate rounding only to specific numeric attributes
            # e.g., d, points, x, y, cx, cy, r, rx, ry, width, height, x1, y1, x2, y2, transform
            numeric_attrs = {
                'd', 'points', 'x', 'y', 'cx', 'cy', 'r', 'rx', 'ry', 
                'width', 'height', 'x1', 'y1', 'x2', 'y2', 'transform', 
                'viewBox', 'stroke-width', 'dx', 'dy'
            }
            if attr_name.lower() in numeric_attrs or ':' in attr_name: # round values in attributes
                new_val = float_pattern.sub(round_match, attr_val)
                # Clean up spaces around signs and separators in path/coordinates
                # "M 10, 20" -> "M10,20"
                new_val = re.sub(r'\s*([,+-])\s*', r'\1', new_val)
                # Compress double spaces
                new_val = re.sub(r'\s+', ' ', new_val).strip()
                return f'{attr_name}="{new_val}"'
            return match.group(0)

        svg_content = attr_pattern.sub(opt_attributes, svg_content)

    # 5. Minify: strip unnecessary spaces and empty lines
    # Remove leading/trailing spaces on each line
    lines = [line.strip() for line in svg_content.split('\n')]
    # Remove empty lines
    lines = [line for line in lines if line]
    # Reassemble as minified string (single line or space-separated tags)
    minified = "".join(lines)
    # Put spaces between tags if they are adjacent, but only when safe
    minified = re.sub(r'>\s+<', '><', minified)
    
    return minified

def pretty_print_xml(xml_str):
    """
    Formats XML string with indentation for better readability.
    """
    # Simple formatting: split by tag transitions and add indentation
    xml_str = re.sub(r'><', '>\n<', xml_str)
    lines = xml_str.split('\n')
    
    indent = 0
    formatted = []
    for line in lines:
        if not line:
            continue
        # If it's a closing tag
        if line.startswith('</'):
            indent = max(0, indent - 1)
            formatted.append('  ' * indent + line)
        # If it's self-closing or a declaration/doctype
        elif line.endswith('/>') or line.startswith('<?') or line.startswith('<!'):
            formatted.append('  ' * indent + line)
        # If it's an opening tag
        elif line.startswith('<') and not line.startswith('</'):
            formatted.append('  ' * indent + line)
            # Check if there's no closing tag on the same line
            tag_name = re.match(r'<([a-zA-Z0-9:-]+)', line)
            if tag_name:
                close_tag = f'</{tag_name.group(1)}>'
                if close_tag not in line and not line.endswith('/>'):
                    indent += 1
        else:
            formatted.append('  ' * indent + line)
            
    return '\n'.join(formatted)

def main():
    parser = argparse.ArgumentParser(description="SVG Optimizer & Minifier - Shrink SVG files by cleaning editor tags and rounding coordinates.")
    parser.add_argument('-i', '--input', required=True, help='Path to the input SVG file')
    parser.add_argument('-o', '--output', help='Path to the output SVG file (prints to stdout if omitted)')
    parser.add_argument('-p', '--precision', type=int, default=2, help='Decimal precision for rounding coordinates (default: 2, set -1 to disable)')
    parser.add_argument('--pretty', action='store_true', help='Format and indent output instead of minifying to a single line')
    parser.add_argument('--no-strip-metadata', action='store_true', help='Do not strip metadata, desc, and title elements')
    parser.add_argument('--dry-run', action='store_true', help='Simulate optimization and report file size reduction without writing')

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"❌ Error: Input file '{args.input}' does not exist.", file=sys.stderr)
        return 1

    try:
        with open(args.input, 'r', encoding='utf-8', errors='ignore') as f:
            original_content = f.read()
    except Exception as e:
        print(f"❌ Error reading input file: {e}", file=sys.stderr)
        return 1

    original_size = len(original_content.encode('utf-8'))

    # Run optimizer
    optimized = optimize_svg(
        original_content, 
        precision=args.precision, 
        strip_metadata=not args.no_strip-metadata if hasattr(args, 'no_strip_metadata') else not args.no_strip_metadata
    )

    if args.pretty:
        optimized = pretty_print_xml(optimized)

    optimized_size = len(optimized.encode('utf-8'))
    reduction = original_size - optimized_size
    percent = (reduction / original_size) * 100 if original_size > 0 else 0

    if args.dry_run:
        print(f"📊 DRY RUN RESULTS for '{args.input}':")
        print(f"  Original Size  : {original_size:,} bytes")
        print(f"  Optimized Size : {optimized_size:,} bytes")
        print(f"  Reduction      : {reduction:,} bytes ({percent:.2f}%)")
        return 0

    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(optimized)
            print(f"⚡ Optimized SVG saved to: {args.output}")
            print(f"  Size reduced from {original_size:,} to {optimized_size:,} bytes (-{percent:.1f}%)")
        except Exception as e:
            print(f"❌ Error writing output file: {e}", file=sys.stderr)
            return 1
    else:
        sys.stdout.write(optimized)
        if not optimized.endswith('\n'):
            sys.stdout.write('\n')

    return 0

if __name__ == "__main__":
    sys.exit(main())
 Maroon
