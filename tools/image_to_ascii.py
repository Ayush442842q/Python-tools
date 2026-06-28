#!/usr/bin/env python3
"""
Image to ASCII Art & ANSI Color Converter - Convert images to terminal ASCII/colored text.

This tool takes an image (BMP natively; PNG, JPEG, WEBP if Pillow is installed)
and converts it into ASCII art. It features customizable scaling, contrast/brightness adjustments,
colorized output using ANSI TrueColor codes, custom character ramps, and HTML export.

Usage:
    python tools/image_to_ascii.py <image_path> [options]

Example:
    python tools/image_to_ascii.py photo.bmp --width 80 --color
    python tools/image_to_ascii.py photo.png -w 100 -o ascii_art.html
"""

import argparse
import os
import struct
import sys
from typing import Tuple, List, Optional

# Try loading Pillow for JPEG/PNG/WEBP support, fallback to native BMP parser
try:
    from PIL import Image as PILImage
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

# Default character ramps from darkest to lightest
RAMP_CHARACTERS = "$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\\|()1{}[]?-_+~<>i!lI;:,\"^`'. "


def adjust_contrast_brightness(r: int, g: int, b: int, contrast: float, brightness: float) -> Tuple[int, int, int]:
    """Adjust contrast and brightness of an RGB pixel."""
    # Scale brightness
    r = int(r * brightness)
    g = int(g * brightness)
    b = int(b * brightness)
    
    # Scale contrast (around middle gray 128)
    r = int(128 + (r - 128) * contrast)
    g = int(128 + (g - 128) * contrast)
    b = int(128 + (b - 128) * contrast)
    
    # Clamp values to [0, 255]
    return (
        max(0, min(255, r)),
        max(0, min(255, g)),
        max(0, min(255, b))
    )


class NativeBMPImage:
    """A minimal, dependency-free BMP file reader parsing 24-bit/32-bit uncompressed BMPs."""
    def __init__(self, filepath: str):
        self.filepath = filepath
        self.width = 0
        self.height = 0
        self.pixels: List[List[Tuple[int, int, int]]] = []  # Grid of (R, G, B)
        self._load()

    def _load(self):
        with open(self.filepath, "rb") as f:
            header = f.read(54)
            if len(header) < 54 or header[:2] != b"BM":
                raise ValueError("Not a valid BMP file.")
                
            # Extract header details
            # Offset to pixel data: bytes 10-13
            pixel_offset = struct.unpack("<I", header[10:14])[0]
            # Width: bytes 18-21
            self.width = struct.unpack("<i", header[18:22])[0]
            # Height: bytes 22-25
            self.height = struct.unpack("<i", header[22:26])[0]
            # Bits per pixel: bytes 28-29
            bpp = struct.unpack("<H", header[28:30])[0]
            # Compression: bytes 30-33 (0 = BI_RGB, uncompressed)
            compression = struct.unpack("<I", header[30:34])[0]

            if bpp not in (24, 32) or compression != 0:
                raise ValueError(f"Unsupported BMP format: {bpp}bpp, compression {compression}. Only 24-bit and 32-bit uncompressed BMPs are supported.")

            f.seek(pixel_offset)
            is_negative_height = self.height < 0
            abs_height = abs(self.height)
            
            # Row padding in BMP: row size must be a multiple of 4 bytes
            bytes_per_pixel = bpp // 8
            row_size = self.width * bytes_per_pixel
            padding = (4 - (row_size % 4)) % 4
            
            rows = []
            for y in range(abs_height):
                row_data = f.read(row_size)
                f.read(padding)  # Skip padding bytes
                
                row_pixels = []
                for x in range(self.width):
                    offset = x * bytes_per_pixel
                    if offset + 3 > len(row_data):
                        break
                    # BMP stores pixels as BGR
                    b, g, r = row_data[offset:offset+3]
                    row_pixels.append((r, g, b))
                rows.append(row_pixels)
                
            # BMP stores bottom rows first, reverse them to get top-down rows
            if not is_negative_height:
                rows.reverse()
                
            self.pixels = rows

    def resize(self, new_width: int, new_height: int) -> 'NativeBMPImage':
        """Resize using basic nearest-neighbor interpolation."""
        resized = NativeBMPImage.__new__(NativeBMPImage)
        resized.filepath = self.filepath
        resized.width = new_width
        resized.height = new_height
        resized.pixels = []
        
        for y in range(new_height):
            orig_y = int(y * len(self.pixels) / new_height)
            orig_y = min(orig_y, len(self.pixels) - 1)
            row = []
            for x in range(new_width):
                orig_x = int(x * self.width / new_width)
                orig_x = min(orig_x, self.width - 1)
                row.append(self.pixels[orig_y][orig_x])
            resized.pixels.append(row)
            
        return resized


def convert_image_to_ascii(
    image_path: str,
    target_width: int,
    contrast: float,
    brightness: float,
    invert: bool,
    ramp: str
) -> Tuple[List[List[Tuple[int, int, int]]], List[List[str]]]:
    """Read and scale image, return pixel colors and corresponding ASCII chars."""
    pixels: List[List[Tuple[int, int, int]]] = []
    
    if HAS_PIL:
        # Load and resize using Pillow
        img = PILImage.open(image_path).convert("RGB")
        # Aspect ratio adjustment: terminal characters are taller than they are wide.
        # We compensate by squeezing the image height by a factor of ~0.55.
        aspect_ratio = img.height / img.width
        target_height = int(target_width * aspect_ratio * 0.55)
        
        # Prevent 0 height
        target_height = max(1, target_height)
        img = img.resize((target_width, target_height), PILImage.Resampling.BILINEAR)
        
        for y in range(img.height):
            row = []
            for x in range(img.width):
                row.append(img.getpixel((x, y)))
            pixels.append(row)
    else:
        # Fallback to native BMP loader
        if not image_path.lower().endswith(".bmp"):
            print("Error: Pillow is not installed. Native mode only supports .bmp files.", file=sys.stderr)
            print("Please convert your image to BMP format or install Pillow: pip install Pillow", file=sys.stderr)
            sys.exit(1)
            
        bmp = NativeBMPImage(image_path)
        aspect_ratio = bmp.height / bmp.width
        target_height = int(target_width * aspect_ratio * 0.55)
        target_height = max(1, target_height)
        
        scaled_bmp = bmp.resize(target_width, target_height)
        pixels = scaled_bmp.pixels

    # Convert pixels to ASCII chars
    ascii_rows = []
    adjusted_pixels = []
    
    ramp_len = len(ramp)
    
    for row in pixels:
        ascii_row = []
        adjusted_row = []
        for r, g, b in row:
            # Contrast/brightness adjustments
            r, g, b = adjust_contrast_brightness(r, g, b, contrast, brightness)
            adjusted_row.append((r, g, b))
            
            # Map luminance to character index
            # Standard relative luminance formula
            luminance = 0.299 * r + 0.587 * g + 0.114 * b
            
            char_idx = int((luminance / 255) * (ramp_len - 1))
            if invert:
                char_idx = (ramp_len - 1) - char_idx
                
            ascii_row.append(ramp[char_idx])
        ascii_rows.append(ascii_row)
        adjusted_pixels.append(adjusted_row)
        
    return adjusted_pixels, ascii_rows


def generate_ansi_colored_output(pixels: List[List[Tuple[int, int, int]]], chars: List[List[str]]) -> str:
    """Generate ANSI color-coded text for terminal output."""
    output = []
    for y in range(len(pixels)):
        line = []
        for x in range(len(pixels[y])):
            r, g, b = pixels[y][x]
            char = chars[y][x]
            # TrueColor ANSI code \033[38;2;R;G;Bm
            line.append(f"\033[38;2;{r};{g};{b}m{char}")
        # Add reset code at end of each line
        output.append("".join(line) + "\033[0m")
    return "\n".join(output)


def generate_html_output(pixels: List[List[Tuple[int, int, int]]], chars: List[List[str]]) -> str:
    """Generate HTML document with colored spans."""
    html_lines = []
    for y in range(len(pixels)):
        line_spans = []
        for x in range(len(pixels[y])):
            r, g, b = pixels[y][x]
            char = chars[y][x]
            # Escape HTML characters
            escaped_char = char.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace(" ", "&nbsp;")
            line_spans.append(f'<span style="color:rgb({r},{g},{b})">{escaped_char}</span>')
        html_lines.append("".join(line_spans))
        
    html_content = "<br>\n".join(html_lines)
    
    return f"""<!DOCTYPE html>
<html>
<head>
    <title>ASCII Art</title>
    <style>
        body {{
            background-color: #0c0c0c;
            color: #ffffff;
            font-family: "Courier New", Courier, monospace;
            font-size: 8px;
            line-height: 1.0;
            letter-spacing: 0px;
            white-space: nowrap;
            margin: 20px;
        }}
        .art-container {{
            display: inline-block;
            background-color: #0c0c0c;
            padding: 10px;
            border-radius: 5px;
        }}
    </style>
</head>
<body>
    <div class="art-container">
        {html_content}
    </div>
</body>
</html>
"""


def main():
    parser = argparse.ArgumentParser(description="Convert images to ASCII art and ANSI-colored text.")
    parser.add_argument("image", help="Path to the source image file")
    parser.add_argument("-w", "--width", type=int, help="Target width in characters (default: 80)")
    parser.add_argument("-c", "--color", action="store_true", help="Output ANSI-colored text to terminal")
    parser.add_argument("-i", "--invert", action="store_true", help="Invert character ramp (darker/lighter swaps)")
    parser.add_argument("--brightness", type=float, default=1.0, help="Brightness modifier factor (default: 1.0)")
    parser.add_argument("--contrast", type=float, default=1.0, help="Contrast modifier factor (default: 1.0)")
    parser.add_argument("-r", "--ramp", default=RAMP_CHARACTERS, help="Custom character ramp from dark to light")
    parser.add_argument("-o", "--output", help="Save output to a text file (or HTML file if ends in .html)")
    
    args = parser.parse_args()

    if not os.path.exists(args.image):
        print(f"Error: Image path '{args.image}' does not exist.", file=sys.stderr)
        sys.exit(1)

    # Determine default terminal width if width is not specified
    width = args.width
    if not width:
        try:
            width = os.get_terminal_size().columns - 2
        except Exception:
            width = 80
            
    # Cap width to prevent massive calculations
    width = max(10, min(500, width))

    try:
        if not HAS_PIL:
            print("Note: Pillow package is not installed. Running in Native BMP mode.")
            
        pixels, chars = convert_image_to_ascii(
            args.image,
            target_width=width,
            contrast=args.contrast,
            brightness=args.brightness,
            invert=args.invert,
            ramp=args.ramp
        )
        
        # Save output to file if specified
        if args.output:
            if args.output.lower().endswith(".html"):
                html_data = generate_html_output(pixels, chars)
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(html_data)
                print(f"ASCII Art HTML generated and saved to: {args.output}")
            else:
                text_data = "\n".join(["".join(row) for row in chars])
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(text_data)
                print(f"ASCII Art text saved to: {args.output}")
        else:
            # Print to terminal
            if args.color:
                colored_text = generate_ansi_colored_output(pixels, chars)
                print(colored_text)
            else:
                text_data = "\n".join(["".join(row) for row in chars])
                print(text_data)
                
    except Exception as e:
        print(f"Error converting image: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
