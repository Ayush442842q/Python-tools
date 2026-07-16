#!/usr/bin/env python3
"""
Unicode Braille Art Generator

Converts images into high-resolution terminal Braille art using the Unicode
Braille Patterns block (U+2800 - U+28FF). Each Braille character represents
a 2x4 pixel grid, allowing for 4x the density of standard ASCII character art.

Supports Pillow (PIL) for comprehensive image loading, and falls back to a
native, zero-dependency uncompressed BMP reader if Pillow is not installed.

Usage:
    python braille_art_generator.py image.png --width 80
"""

import sys
import os
import argparse

# Try loading Pillow for JPEG/PNG support.
try:
    from PIL import Image
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

def read_bmp_headers(filepath):
    """Natively decodes basic headers from an uncompressed 24/32-bit BMP file."""
    with open(filepath, 'rb') as f:
        magic = f.read(2)
        if magic != b'BM':
            raise ValueError("Not a valid BMP file.")
            
        f.seek(10)
        pixel_offset = int.from_bytes(f.read(4), byteorder='little')
        
        f.seek(18)
        width = int.from_bytes(f.read(4), byteorder='little', signed=True)
        height = int.from_bytes(f.read(4), byteorder='little', signed=True)
        
        f.seek(28)
        bpp = int.from_bytes(f.read(2), byteorder='little')
        
        if bpp not in (24, 32):
            raise ValueError(f"Only uncompressed 24-bit or 32-bit BMP files supported natively. Got {bpp}bpp.")
            
        # Read pixel array
        f.seek(pixel_offset)
        raw_pixels = f.read()
        
    return width, height, bpp, raw_pixels

class NativeImage:
    """A minimal, zero-dependency Image class that mirrors Pillow for uncompressed BMPs."""
    def __init__(self, width, height, bpp, raw_pixels):
        self.width = width
        self.height = abs(height)
        self.bpp = bpp
        self.raw_pixels = raw_pixels
        self.is_bottom_up = (height > 0)
        
    def resize(self, new_size):
        """Simplistic nearest-neighbor image resizer."""
        new_w, new_h = new_size
        resized_pixels = bytearray(new_w * new_h * (self.bpp // 8))
        
        scale_x = self.width / new_w
        scale_y = self.height / new_h
        bytes_per_pixel = self.bpp // 8
        row_size = ((self.width * self.bpp + 31) // 32) * 4 # padding to 4 bytes boundary
        
        for y in range(new_h):
            orig_y = int(y * scale_y)
            # Handle bottom-up BMP ordering
            actual_y = (self.height - 1 - orig_y) if self.is_bottom_up else orig_y
            
            for x in range(new_w):
                orig_x = int(x * scale_x)
                
                orig_idx = actual_y * row_size + orig_x * bytes_per_pixel
                new_idx = (y * new_w + x) * bytes_per_pixel
                
                if orig_idx + bytes_per_pixel <= len(self.raw_pixels):
                    resized_pixels[new_idx : new_idx + bytes_per_pixel] = \
                        self.raw_pixels[orig_idx : orig_idx + bytes_per_pixel]
                        
        return NativeImage(new_w, new_h, self.bpp, bytes(resized_pixels))

    def convert_to_grayscale(self):
        """Converts pixels to 8-bit grayscale intensity values."""
        bytes_per_pixel = self.bpp // 8
        grayscale = []
        for i in range(0, len(self.raw_pixels), bytes_per_pixel):
            if i + 3 <= len(self.raw_pixels):
                b, g, r = self.raw_pixels[i : i+3]
                # Luminosity formula for grayscale conversion
                gray = int(0.299 * r + 0.587 * g + 0.114 * b)
                grayscale.append(gray)
        return grayscale

def generate_braille_char(grid, threshold=128, invert=False):
    """
    Translates a 2x4 binary matrix (grid) into a single Unicode Braille character.
    grid is a list of lists: [[c0_r0, c1_r0], ..., [c0_r3, c1_r3]]
    """
    # Unicode Braille dot mapping (relative binary flags)
    # Dot 1: (0,0) = 0x01
    # Dot 2: (0,1) = 0x02
    # Dot 3: (0,2) = 0x04
    # Dot 4: (1,0) = 0x08
    # Dot 5: (1,1) = 0x10
    # Dot 6: (1,2) = 0x20
    # Dot 7: (0,3) = 0x40
    # Dot 8: (1,3) = 0x80
    dot_mask = [
        [0x01, 0x08],
        [0x02, 0x10],
        [0x04, 0x20],
        [0x40, 0x80]
    ]
    
    code = 0
    for r in range(4):
        for c in range(2):
            val = grid[r][c]
            # Active pixel is below threshold (dark pixel on white background)
            # or above threshold (if inverted)
            is_active = (val < threshold) if not invert else (val >= threshold)
            if is_active:
                code |= dot_mask[r][c]
                
    return chr(0x2800 + code)

def main():
    parser = argparse.ArgumentParser(
        description="Convert images to high-density Unicode Braille Art.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "image_path",
        help="Path to the image file. Note: If Pillow is not installed, only uncompressed .bmp is supported."
    )
    
    parser.add_argument(
        "-w", "--width",
        type=int,
        default=80,
        help="Target art width in characters (default: 80)"
    )
    
    parser.add_argument(
        "-t", "--threshold",
        type=int,
        default=127,
        help="Grayscale threshold value (0-255) for active dots (default: 127)"
    )
    
    parser.add_argument(
        "-i", "--invert",
        action="store_true",
        help="Invert active pixels (useful for dark terminal themes)"
    )
    
    args = parser.parse_args()

    # 1. Load Image
    if HAS_PILLOW:
        try:
            img = Image.open(args.image_path)
            # Resize image to match character aspect ratio (each char is 2x4 grid, so width ratio is 2, height is 4)
            # Adjust height because terminal fonts are taller than they are wide (approx aspect ratio 2:1)
            char_width = args.width
            pixel_width = char_width * 2
            
            aspect = img.height / img.width
            # Height in characters (accounting for 2:1 character aspect ratio in terminals)
            char_height = int(char_width * aspect * 0.5)
            pixel_height = char_height * 4
            
            # Prevent zero sizes
            pixel_width = max(2, pixel_width - (pixel_width % 2))
            pixel_height = max(4, pixel_height - (pixel_height % 4))
            
            img_resized = img.resize((pixel_width, pixel_height)).convert("L")
            grayscale_data = list(img_resized.getdata())
            width, height = pixel_width, pixel_height
        except Exception as e:
            print(f"Error loading image via Pillow: {e}", file=sys.stderr)
            return 1
    else:
        # Check if file is BMP
        if not args.image_path.lower().endswith('.bmp'):
            print("Pillow is not installed. Native fallback only supports uncompressed .bmp files.", file=sys.stderr)
            print("Please install pillow via: pip install pillow", file=sys.stderr)
            return 1
            
        try:
            w, h, bpp, raw = read_bmp_headers(args.image_path)
            native_img = NativeImage(w, h, bpp, raw)
            
            char_width = args.width
            pixel_width = char_width * 2
            aspect = native_img.height / native_img.width
            char_height = int(char_width * aspect * 0.5)
            pixel_height = char_height * 4
            
            pixel_width = max(2, pixel_width - (pixel_width % 2))
            pixel_height = max(4, pixel_height - (pixel_height % 4))
            
            resized = native_img.resize((pixel_width, pixel_height))
            grayscale_data = resized.convert_to_grayscale()
            width, height = pixel_width, pixel_height
        except Exception as e:
            print(f"Error parsing BMP natively: {e}", file=sys.stderr)
            return 1

    # 2. Render to Braille Grid
    output_lines = []
    
    # Each character is 2 pixels wide and 4 pixels high
    for y in range(0, height, 4):
        line_chars = []
        for x in range(0, width, 2):
            # Extract 2x4 pixel block
            block = []
            for dy in range(4):
                row = []
                for dx in range(2):
                    pixel_idx = (y + dy) * width + (x + dx)
                    if pixel_idx < len(grayscale_data):
                        row.append(grayscale_data[pixel_idx])
                    else:
                        row.append(255) # Out of bounds falls back to white (inactive)
                block.append(row)
                
            braille_char = generate_braille_char(block, args.threshold, args.invert)
            line_chars.append(braille_char)
            
        output_lines.append("".join(line_chars))

    # 3. Print Braille Art
    for line in output_lines:
        print(line)
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
