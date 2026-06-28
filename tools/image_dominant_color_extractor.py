#!/usr/bin/env python3
"""
Image Dominant Color Extractor

Extracts the dominant color palette from an image. 
Features:
    - Uses `Pillow` library if installed (supporting JPEG, PNG, WebP, GIF, BMP, etc.).
    - Falls back to a native, zero-dependency BMP parser if Pillow is not available.
    - Quantizes colors to group similar hues together.
    - Displays a beautiful visual palette in the terminal using TrueColor (24-bit) ANSI escape sequences.
    - Exports the palette as CSS custom properties, Tailwind config, or JSON.

Usage:
    python tools/image_dominant_color_extractor.py input.png --colors 5
"""

import os
import sys
import argparse
from collections import Counter

# ANSI escape codes for TrueColor (24-bit background color)
def get_ansi_bg_color(r: int, g: int, b: int) -> str:
    """Returns the ANSI escape sequence for a background TrueColor block."""
    return f"\033[48;2;{r};{g};{b}m      \033[0m"

def print_colored_bullet(r: int, g: int, b: int):
    """Prints a square block with the specified RGB color."""
    sys.stdout.write(get_ansi_bg_color(r, g, b))

def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert RGB values to hexadecimal string."""
    return f"#{r:02x}{g:02x}{b:02x}"

def has_pillow() -> bool:
    """Check if PIL (Pillow) is installed."""
    try:
        from PIL import Image
        return True
    except ImportError:
        return False

def read_pixels_native_bmp(filepath: str) -> list:
    """
    Natively parses a 24-bit or 32-bit uncompressed BMP file to extract pixels
    without using external dependencies.
    """
    pixels = []
    with open(filepath, "rb") as f:
        # BMP Header Validation
        header = f.read(54)
        if len(header) < 54 or header[0:2] != b"BM":
            raise ValueError("Not a valid BMP file.")
            
        # Parse BMP header details
        pixel_offset = int.from_bytes(header[10:14], byteorder="little")
        width = int.from_bytes(header[18:22], byteorder="little")
        height = int.from_bytes(header[22:26], byteorder="little")
        bpp = int.from_bytes(header[28:30], byteorder="little")
        compression = int.from_bytes(header[30:34], byteorder="little")
        
        if compression != 0:
            raise ValueError("Only uncompressed BMP files are supported natively.")
            
        if bpp not in (24, 32):
            raise ValueError(f"Only 24-bit or 32-bit BMP files are supported natively (found {bpp}-bit).")
            
        # Seek to pixel array offset
        f.seek(pixel_offset)
        
        # BMP rows are padded to multiples of 4 bytes
        row_size = ((bpp * width + 31) // 32) * 4
        
        for _ in range(abs(height)):
            row_data = f.read(row_size)
            if not row_data:
                break
                
            idx = 0
            for _ in range(width):
                if bpp == 24:
                    if idx + 3 > len(row_data):
                        break
                    b, g, r = row_data[idx:idx+3]
                    pixels.append((r, g, b))
                    idx += 3
                elif bpp == 32:
                    if idx + 4 > len(row_data):
                        break
                    b, g, r, _ = row_data[idx:idx+4]
                    pixels.append((r, g, b))
                    idx += 4
                    
    return pixels

def extract_dominant_colors(pixels: list, num_colors: int, quantize_bits: int = 4) -> list:
    """
    Group similar colors by quantizing the bits (e.g. keeping top bits)
    and find the most frequent colors in the image.
    """
    if not pixels:
        return []
        
    shift = 8 - quantize_bits
    
    # Quantize pixels to group close colors
    quantized_pixels = []
    pixel_map = {} # quantized -> list of original pixels
    
    for r, g, b in pixels:
        qr = (r >> shift) << shift
        qg = (g >> shift) << shift
        qb = (b >> shift) << shift
        q_color = (qr, qg, qb)
        quantized_pixels.append(q_color)
        
        if q_color not in pixel_map:
            pixel_map[q_color] = []
        pixel_map[q_color].append((r, g, b))
        
    # Count frequency of quantized colors
    counter = Counter(quantized_pixels)
    most_common = counter.most_common(num_colors)
    
    palette = []
    for q_color, count in most_common:
        # Calculate the actual average color of the pixels in this bucket
        bucket_pixels = pixel_map[q_color]
        total_r = sum(p[0] for p in bucket_pixels)
        total_g = sum(p[1] for p in bucket_pixels)
        total_b = sum(p[2] for p in bucket_pixels)
        n = len(bucket_pixels)
        
        avg_color = (total_r // n, total_g // n, total_b // n)
        percentage = (count / len(pixels)) * 100
        palette.append((avg_color, percentage))
        
    return palette

def main():
    parser = argparse.ArgumentParser(
        description="Image Dominant Color Extractor - Find the primary color palette of an image."
    )
    parser.add_argument("image", help="Path to the image file.")
    parser.add_argument("-c", "--colors", type=int, default=5, 
                        help="Number of dominant colors to extract (default: 5).")
    parser.add_argument("-q", "--quantize", type=int, default=4, choices=[3, 4, 5, 6],
                        help="Color quantization bit-depth (default: 4). Lower is broader grouping.")
    parser.add_argument("-f", "--format", choices=["terminal", "css", "tailwind", "json"], default="terminal",
                        help="Format to output results (default: terminal).")
                        
    args = parser.parse_args()
    
    if not os.path.exists(args.image):
        print(f"[-] Error: Image file '{args.image}' not found.", file=sys.stderr)
        sys.exit(1)
        
    pixels = []
    used_pillow = False
    
    if has_pillow():
        from PIL import Image
        try:
            with Image.open(args.image) as img:
                # Convert to RGB if not already
                if img.mode != "RGB":
                    img = img.convert("RGB")
                pixels = list(img.getdata())
                used_pillow = True
        except Exception as e:
            print(f"[-] Error parsing image via Pillow: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # No Pillow installed
        _, ext = os.path.splitext(args.image.lower())
        if ext == ".bmp":
            try:
                pixels = read_pixels_native_bmp(args.image)
            except Exception as e:
                print(f"[-] Native BMP parser failed: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            print("[-] Error: Non-BMP images require the Pillow library.", file=sys.stderr)
            print("    Please install Pillow: `pip install pillow`", file=sys.stderr)
            print("    Or convert the image to uncompressed 24-bit/32-bit BMP to parse natively.", file=sys.stderr)
            sys.exit(1)
            
    palette = extract_dominant_colors(pixels, args.colors, args.quantize)
    
    if not palette:
        print("[-] Error: No colors could be extracted.")
        sys.exit(1)
        
    if args.format == "terminal":
        print(f"\n[*] Extracted {len(palette)} dominant colors (Method: {'Pillow' if used_pillow else 'Native BMP'}):\n")
        for idx, (color, pct) in enumerate(palette):
            r, g, b = color
            hex_val = rgb_to_hex(r, g, b)
            
            # Print visual block
            print_colored_bullet(r, g, b)
            sys.stdout.write(f"  Color {idx+1}: {hex_val.upper()} | RGB: ({r:3}, {g:3}, {b:3}) | Share: {pct:5.2f}%\n")
        print()
        
    elif args.format == "css":
        print("/* Dominant CSS Custom Properties */")
        print(":root {")
        for idx, (color, _) in enumerate(palette):
            r, g, b = color
            print(f"  --color-primary-{idx+1}: {rgb_to_hex(r, g, b)}; /* rgb({r}, {g}, {b}) */")
        print("}")
        
    elif args.format == "tailwind":
        print("// Tailwind CSS Color Palette Extensions")
        print("colors: {")
        for idx, (color, _) in enumerate(palette):
            r, g, b = color
            print(f"  'dominant-{idx+1}': '{rgb_to_hex(r, g, b)}',")
        print("}")
        
    elif args.format == "json":
        output_list = []
        for idx, (color, pct) in enumerate(palette):
            r, g, b = color
            output_list.append({
                "index": idx + 1,
                "hex": rgb_to_hex(r, g, b).upper(),
                "rgb": [r, g, b],
                "percentage": round(pct, 2)
            })
        print(json.dumps(output_list, indent=2))

if __name__ == "__main__":
    main()
