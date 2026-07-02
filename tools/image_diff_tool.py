#!/usr/bin/env python3
"""
Image Diff Tool
A command-line utility to compare two images pixel-by-pixel.
It calculates similarity statistics (Mean Squared Error, PSNR, percent mismatch)
and generates a visual difference overlay highlighting the differences.

Usage:
    python tools/image_diff_tool.py <image_a> <image_b> [--output OUTPUT_PATH] [options]
"""

import argparse
import math
import os
import sys

# ANSI colors for styling
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
BOLD = "\033[1m"
RESET = "\033[0m"


def check_dependencies():
    """Checks if Pillow is installed. Aborts with helper message if not."""
    try:
        from PIL import Image, ImageChops, ImageColor
        return True
    except ImportError:
        print(f"{RED}Error: Pillow (PIL) library is required to run this tool.{RESET}", file=sys.stderr)
        print(f"Please install it using: {BOLD}pip install Pillow{RESET}", file=sys.stderr)
        sys.exit(1)


def compare_images(path_a, path_b, output_path=None, threshold=0, highlight_color="red", resize_mode="none", binary_mask=False):
    """Compares two images and computes differences."""
    from PIL import Image, ImageChops, ImageColor, ImageDraw

    try:
        img_a = Image.open(path_a).convert("RGB")
    except Exception as e:
        print(f"{RED}Error loading image A '{path_a}': {e}{RESET}", file=sys.stderr)
        return 1

    try:
        img_b = Image.open(path_b).convert("RGB")
    except Exception as e:
        print(f"{RED}Error loading image B '{path_b}': {e}{RESET}", file=sys.stderr)
        return 1

    # Check dimensions
    if img_a.size != img_b.size:
        print(f"{YELLOW}Warning: Image dimensions mismatch!{RESET}")
        print(f"  Image A: {img_a.size[0]}x{img_a.size[1]}")
        print(f"  Image B: {img_b.size[0]}x{img_b.size[1]}")

        if resize_mode == "none":
            print(f"{RED}Error: Cannot compare images of different sizes. Use --resize-mode to force matching.{RESET}", file=sys.stderr)
            return 1
        elif resize_mode == "a-to-b":
            print(f"Resizing Image A to match Image B...")
            img_a = img_a.resize(img_b.size, Image.Resampling.LANCZOS)
        elif resize_mode == "b-to-a":
            print(f"Resizing Image B to match Image A...")
            img_b = img_b.resize(img_a.size, Image.Resampling.LANCZOS)

    width, height = img_a.size
    total_pixels = width * height

    # Parse highlight color
    try:
        hl_rgb = ImageColor.getrgb(highlight_color)
    except ValueError:
        print(f"{YELLOW}Warning: Invalid highlight color '{highlight_color}'. Falling back to red.{RESET}")
        hl_rgb = (255, 0, 0)

    # Compute difference
    pixels_a = img_a.load()
    pixels_b = img_b.load()

    # Create visual diff canvas
    if binary_mask:
        # White background, black differences
        diff_img = Image.new("RGB", (width, height), (255, 255, 255))
    else:
        # Desaturated/darkened version of image A as background for overlay
        diff_img = img_a.copy()
        diff_pixels = diff_img.load()
        for y in range(height):
            for x in range(width):
                r, g, b = diff_pixels[x, y]
                # Desaturate and darken
                gray = int(0.299 * r + 0.587 * g + 0.114 * b)
                diff_pixels[x, y] = (gray // 2, gray // 2, gray // 2)

    diff_pixels = diff_img.load()
    differing_pixels = 0
    squared_error_sum = 0.0

    for y in range(height):
        for x in range(width):
            r_a, g_a, b_a = pixels_a[x, y]
            r_b, g_b, b_b = pixels_b[x, y]

            # Euclidean distance in RGB color space
            dist = math.sqrt((r_a - r_b) ** 2 + (g_a - g_b) ** 2 + (b_a - b_b) ** 2)
            
            # Squared error for MSE
            squared_error_sum += (r_a - r_b) ** 2 + (g_a - g_b) ** 2 + (b_a - b_b) ** 2

            if dist > threshold:
                differing_pixels += 1
                if binary_mask:
                    diff_pixels[x, y] = (0, 0, 0) # Black for difference
                else:
                    diff_pixels[x, y] = hl_rgb # Highlight color overlay
            else:
                if binary_mask:
                    diff_pixels[x, y] = (255, 255, 255) # White for identical

    # Compute stats
    mismatch_percent = (differing_pixels / total_pixels) * 100
    mse = (squared_error_sum / (total_pixels * 3)) # Averaged over RGB channels
    
    if mse == 0:
        psnr = float("inf")
    else:
        psnr = 20 * math.log10(255.0 / math.sqrt(mse))

    # Print results
    print(f"\n{BOLD}--- Image Comparison Report ---{RESET}")
    print(f"Dimensions: {width}x{height} pixels")
    print(f"Total Pixels: {total_pixels}")
    
    if differing_pixels == 0:
        print(f"Similarity: {GREEN}100% Identical{RESET}")
    else:
        similarity = 100.0 - mismatch_percent
        print(f"Similarity: {YELLOW if similarity > 95 else RED}{similarity:.4f}%{RESET}")
        print(f"Differing Pixels: {differing_pixels} ({mismatch_percent:.4f}% mismatch)")
        print(f"Mean Squared Error (MSE): {mse:.2f}")
        print(f"Peak Signal-to-Noise Ratio (PSNR): {f'{psnr:.2f} dB' if psnr != float('inf') else 'Infinity'}")

    # Save output image
    if output_path:
        try:
            diff_img.save(output_path)
            print(f"\n{GREEN}Difference image saved successfully to '{output_path}'{RESET}")
        except Exception as e:
            print(f"{RED}Error saving output image to '{output_path}': {e}{RESET}", file=sys.stderr)
            return 1
    elif differing_pixels > 0:
        print(f"\n{CYAN}Tip: Use the --output parameter to save a visual diff image showing where differences occur.{RESET}")

    return 0 if differing_pixels == 0 else 2


def main():
    check_dependencies()

    parser = argparse.ArgumentParser(
        description="Image Diff Tool - Compare two images and highlight differences.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python image_diff_tool.py original.png edited.png --output diff.png
  python image_diff_tool.py original.jpg edited.jpg --threshold 15 --highlight-color "#FF00FF"
  python image_diff_tool.py a.png b.png --resize-mode a-to-b --output diff.png
"""
    )
    parser.add_argument("image_a", help="Path to the first image")
    parser.add_argument("image_b", help="Path to the second image")
    parser.add_argument("-o", "--output", help="Path to save the visual difference output image")
    parser.add_argument("-t", "--threshold", type=float, default=0.0, help="Distance threshold (0-255) for pixel inequality (default: 0.0)")
    parser.add_argument("-c", "--highlight-color", default="red", help="CSS color name or HEX color (e.g. red, blue, '#FF00FF') to color different pixels")
    parser.add_argument("-r", "--resize-mode", choices=["none", "a-to-b", "b-to-a"], default="none", 
                        help="How to handle differing image dimensions (none: error, a-to-b: resize A to B, b-to-a: resize B to A)")
    parser.add_argument("-m", "--binary-mask", action="store_true", help="Generate a binary black & white diff mask instead of a background overlay")

    args = parser.parse_args()

    return compare_images(
        args.image_a,
        args.image_b,
        output_path=args.output,
        threshold=args.threshold,
        highlight_color=args.highlight_color,
        resize_mode=args.resize_mode,
        binary_mask=args.binary_mask
    )


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Comparison cancelled by user.{RESET}")
        sys.exit(1)
