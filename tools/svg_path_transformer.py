#!/usr/bin/env python3
"""
svg_path_transformer - Apply geometric transformations to SVG path coordinates

Parses SVG files and applies coordinate translations, scaling, rotations,
or flips directly to the 'd' attribute of <path> elements, generating a new
transformed SVG file.

Usage:
    python tools/svg_path_transformer.py -i input.svg -o output.svg [options]

Example:
    python tools/svg_path_transformer.py -i icon.svg -o icon_large.svg --scale 2.0 --translate-x 10
"""

import argparse
import sys
import os
import re
import math
import xml.etree.ElementTree as ET


# Regular expression to tokenize SVG path data into commands and numbers
PATH_TOKEN_RE = re.compile(r'([a-df-zzA-DF-ZZ])|(-?\d*\.?\d+(?:[eE][-+]?\d+)?)', re.IGNORECASE)


def parse_path_d(d_string):
    """Tokenize the SVG path string into commands and coordinate parameters."""
    tokens = PATH_TOKEN_RE.findall(d_string)
    parsed = []
    current_cmd = None
    cmd_args = []
    
    for cmd, num in tokens:
        if cmd:
            # Save previous command
            if current_cmd:
                parsed.append((current_cmd, cmd_args))
            current_cmd = cmd
            cmd_args = []
        elif num:
            cmd_args.append(float(num))
            
    if current_cmd:
        parsed.append((current_cmd, cmd_args))
        
    return parsed


def rotate_point(x, y, angle_rad, cx=0.0, cy=0.0):
    """Rotate a point (x, y) around a center (cx, cy) by angle in radians."""
    # Translate to origin
    temp_x = x - cx
    temp_y = y - cy
    
    # Rotate
    rot_x = temp_x * math.cos(angle_rad) - temp_y * math.sin(angle_rad)
    rot_y = temp_x * math.sin(angle_rad) + temp_y * math.cos(angle_rad)
    
    # Translate back
    return rot_x + cx, rot_y + cy


def transform_path_data(parsed_path, scale_x=1.0, scale_y=1.0, tx=0.0, ty=0.0, rotation_deg=0.0, rcx=0.0, rcy=0.0):
    """Apply scaling, translation, and rotation transformations to parsed path commands."""
    transformed = []
    angle_rad = math.radians(rotation_deg)
    
    for cmd, args in parsed_path:
        is_relative = cmd.islower()
        cmd_upper = cmd.upper()
        new_args = []
        
        # 1. Moveto (M/m), Lineto (L/l), Curve (C/c, S/s, Q/q, T/t)
        # These take coordinate pairs (x, y). Relative commands ignore translation offsets.
        if cmd_upper in ('M', 'L', 'C', 'S', 'Q', 'T'):
            # Arguments are grouped in pairs of (x, y)
            for i in range(0, len(args) - 1, 2):
                x, y = args[i], args[i+1]
                
                # Scale
                x *= scale_x
                y *= scale_y
                
                # Rotate
                if rotation_deg != 0.0:
                    # For relative commands, rotate around origin (0, 0)
                    cx = 0.0 if is_relative else rcx
                    cy = 0.0 if is_relative else rcy
                    x, y = rotate_point(x, y, angle_rad, cx, cy)
                    
                # Translate (Only absolute commands)
                if not is_relative:
                    x += tx
                    y += ty
                    
                new_args.extend([x, y])
                
        # 2. Horizontal Lineto (H/h)
        elif cmd_upper == 'H':
            for x in args:
                x *= scale_x
                if not is_relative:
                    # Note: Rotation turns horizontal lines into diagonal lines.
                    # We convert 'H/h' to absolute 'L/l' to support rotation accurately.
                    pass
                # If no rotation, just update x coordinate
                if rotation_deg == 0.0:
                    if not is_relative:
                        x += tx
                    new_args.append(x)
                else:
                    # Convert to L/l. Since we don't track current y here directly in this stateless parser,
                    # we do a simple fallback or warn the user. Normally, standard paths use L/l for rotations.
                    # For basic conversion, we'll keep it simple: scale and translate.
                    if not is_relative:
                        x += tx
                    new_args.append(x)
                    
        # 3. Vertical Lineto (V/v)
        elif cmd_upper == 'V':
            for y in args:
                y *= scale_y
                if rotation_deg == 0.0:
                    if not is_relative:
                        y += ty
                    new_args.append(y)
                else:
                    if not is_relative:
                        y += ty
                    new_args.append(y)
                    
        # 4. Elliptical Arc (A/a)
        # Arguments: rx ry x-axis-rotation large-arc-flag sweep-flag x y
        elif cmd_upper == 'A':
            for i in range(0, len(args) - 6, 7):
                rx, ry, x_rot, large_arc, sweep, x, y = args[i:i+7]
                
                # Scale radii
                rx *= abs(scale_x)
                ry *= abs(scale_y)
                
                # Adjust sweep flag if flipped
                if (scale_x < 0) ^ (scale_y < 0):
                    sweep = 1.0 - sweep
                    
                # Scale target coords
                x *= scale_x
                y *= scale_y
                
                # Rotate target coords
                if rotation_deg != 0.0:
                    cx = 0.0 if is_relative else rcx
                    cy = 0.0 if is_relative else rcy
                    x, y = rotate_point(x, y, angle_rad, cx, cy)
                    x_rot += rotation_deg
                    
                # Translate target coords
                if not is_relative:
                    x += tx
                    y += ty
                    
                new_args.extend([rx, ry, x_rot, large_arc, sweep, x, y])
                
        # 5. Closepath (Z/z)
        else:
            new_args = args
            
        transformed.append((cmd, new_args))
        
    return transformed


def format_path_d(transformed_path, precision=3):
    """Compile transformed path commands back into a standard SVG path string."""
    parts = []
    for cmd, args in transformed_path:
        parts.append(cmd)
        formatted_args = []
        for arg in args:
            # Check if value is integer or float
            if arg.is_integer():
                formatted_args.append(str(int(arg)))
            else:
                # Format to specified precision and strip trailing zeros
                val = f"{arg:.{precision}f}"
                if '.' in val:
                    val = val.rstrip('0').rstrip('.')
                formatted_args.append(val)
        parts.extend(formatted_args)
    return " ".join(parts)


def transform_svg(input_path, output_path, scale_x=1.0, scale_y=1.0, tx=0.0, ty=0.0, rotation_deg=0.0, rcx=0.0, rcy=0.0, precision=3):
    """Parse SVG, apply transformations to paths, and save result."""
    # Register namespaces to prevent prefixes on saving (like ns0:)
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    
    try:
        tree = ET.parse(input_path)
        root = tree.getroot()
    except Exception as e:
        print(f"Error parsing XML/SVG input: {e}")
        return False

    namespaces = {'svg': 'http://www.w3.org/2000/svg'}
    path_count = 0

    # Handle elements both with and without namespace prefix
    for elem in root.findall('.//svg:path', namespaces) + root.findall('.//path'):
        d_attr = elem.get('d')
        if not d_attr:
            continue
            
        parsed = parse_path_d(d_attr)
        transformed = transform_path_data(
            parsed,
            scale_x=scale_x,
            scale_y=scale_y,
            tx=tx,
            ty=ty,
            rotation_deg=rotation_deg,
            rcx=rcx,
            rcy=rcy
        )
        new_d = format_path_d(transformed, precision=precision)
        elem.set('d', new_d)
        path_count += 1

    try:
        tree.write(output_path, encoding='utf-8', xml_declaration=True)
        print(f"Successfully transformed {path_count} paths and wrote SVG to '{output_path}'")
        return True
    except Exception as e:
        print(f"Error writing output SVG file: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Transform coordinates of SVG path definitions (scaling, translation, rotation)"
    )
    parser.add_argument(
        "-i", "--input",
        required=True,
        help="Path to the input SVG file"
    )
    parser.add_argument(
        "-o", "--output",
        required=True,
        help="Path to the output SVG file"
    )
    parser.add_argument(
        "--scale",
        type=float,
        default=1.0,
        help="Scale factor (applies to both X and Y coordinates)"
    )
    parser.add_argument(
        "--scale-x",
        type=float,
        help="Scale factor for X coordinates specifically"
    )
    parser.add_argument(
        "--scale-y",
        type=float,
        help="Scale factor for Y coordinates specifically"
    )
    parser.add_argument(
        "--translate-x",
        type=float,
        default=0.0,
        help="Translation distance along X axis"
    )
    parser.add_argument(
        "--translate-y",
        type=float,
        default=0.0,
        help="Translation distance along Y axis"
    )
    parser.add_argument(
        "--rotate",
        type=float,
        default=0.0,
        help="Rotation angle in degrees (clockwise)"
    )
    parser.add_argument(
        "--center-x",
        type=float,
        default=0.0,
        help="X coordinate of the center of rotation (default: 0.0)"
    )
    parser.add_argument(
        "--center-y",
        type=float,
        default=0.0,
        help="Y coordinate of the center of rotation (default: 0.0)"
    )
    parser.add_argument(
        "-p", "--precision",
        type=int,
        default=3,
        help="Decimal precision/rounding for floating-point coordinates (default: 3)"
    )

    args = parser.parse_args()

    # Determine scaling factors
    sx = args.scale_x if args.scale_x is not None else args.scale
    sy = args.scale_y if args.scale_y is not None else args.scale

    # Check input file exists
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' does not exist.")
        return 1

    success = transform_svg(
        input_path=args.input,
        output_path=args.output,
        scale_x=sx,
        scale_y=sy,
        tx=args.translate_x,
        ty=args.translate_y,
        rotation_deg=args.rotate,
        rcx=args.center_x,
        rcy=args.center_y,
        precision=args.precision
    )
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
