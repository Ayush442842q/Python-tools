#!/usr/bin/env python3
"""
Batch adds text or image watermarks to image files in a directory.
Requires the 'Pillow' library.
"""

import sys
import os
import argparse

try:
    from PIL import Image, ImageDraw, ImageFont, ImageEnhance
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

def install_instructions():
    print("\nError: Pillow library is required to use this tool.", file=sys.stderr)
    print("Please install it using pip:", file=sys.stderr)
    print("    pip install Pillow\n", file=sys.stderr)

def apply_watermark(image_path, output_path, watermark_text=None, watermark_image_path=None, 
                    position="bottom-right", opacity=0.5, font_size=36, margin=20, 
                    watermark_scale=0.2):
    """Applies a text or image watermark to a single image file."""
    if not HAS_PIL:
        install_instructions()
        sys.exit(1)
        
    try:
        base_image = Image.open(image_path).convert("RGBA")
    except Exception as e:
        print(f"Error opening image {image_path}: {e}", file=sys.stderr)
        return False

    # Create transparent overlay layer
    txt_layer = Image.new("RGBA", base_image.size, (255, 255, 255, 0))
    width, height = base_image.size
    
    if watermark_image_path:
        # --- Image Watermark ---
        try:
            watermark = Image.open(watermark_image_path).convert("RGBA")
        except Exception as e:
            print(f"Error opening watermark image {watermark_image_path}: {e}", file=sys.stderr)
            return False
            
        # Scale watermark image relative to base image
        w_width, w_height = watermark.size
        scale_factor = (width * watermark_scale) / w_width
        new_w = int(w_width * scale_factor)
        new_h = int(w_height * scale_factor)
        watermark = watermark.resize((new_w, new_h), Image.Resampling.LANCZOS)
        
        # Apply opacity/alpha transparency to the watermark image
        alpha = watermark.split()[3]
        alpha = ImageEnhance.Brightness(alpha).enhance(opacity)
        watermark.putalpha(alpha)
        
        # Determine position
        if position == "top-left":
            pos = (margin, margin)
        elif position == "top-right":
            pos = (width - new_w - margin, margin)
        elif position == "bottom-left":
            pos = (margin, height - new_h - margin)
        elif position == "center":
            pos = ((width - new_w) // 2, (height - new_h) // 2)
        else: # bottom-right
            pos = (width - new_w - margin, height - new_h - margin)
            
        # Composite layers
        base_image.alpha_composite(watermark, pos)
        
    elif watermark_text:
        # --- Text Watermark ---
        draw = ImageDraw.Draw(txt_layer)
        
        # Load font (try standard system fonts first, otherwise default)
        font = None
        fonts_to_try = [
            "arial.ttf", "LiberationSans-Regular.ttf", "Helvetica.ttf", 
            "DejaVuSans.ttf", "FreeSans.ttf"
        ]
        for f_name in fonts_to_try:
            try:
                font = ImageFont.truetype(f_name, font_size)
                break
            except IOError:
                continue
                
        if not font:
            font = ImageFont.load_default()
            print("Warning: Could not find system TrueType fonts. Using default pixel font.", file=sys.stderr)
            
        # Get text size (compatibility with different Pillow versions)
        try:
            text_w, text_h = draw.textsize(watermark_text, font=font)
        except AttributeError:
            # New Pillow version method
            left, top, right, bottom = draw.textbbox((0, 0), watermark_text, font=font)
            text_w = right - left
            text_h = bottom - top

        # Determine position
        if position == "top-left":
            pos = (margin, margin)
        elif position == "top-right":
            pos = (width - text_w - margin, margin)
        elif position == "bottom-left":
            pos = (margin, height - text_h - margin)
        elif position == "center":
            pos = ((width - text_w) // 2, (height - text_h) // 2)
        else: # bottom-right
            pos = (width - text_w - margin, height - text_h - margin)
            
        # Draw text with specified opacity (RGBA: white with alpha)
        text_color = (255, 255, 255, int(255 * opacity))
        draw.text(pos, watermark_text, font=font, fill=text_color)
        
        # Merge layers
        base_image = Image.alpha_composite(base_image, txt_layer)

    # Save output (convert back to RGB if original format was not transparent)
    try:
        ext = os.path.splitext(output_path)[1].lower()
        if ext in [".jpg", ".jpeg"]:
            final_img = base_image.convert("RGB")
        else:
            final_img = base_image
            
        # Ensure directories exist
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        final_img.save(output_path)
        return True
    except Exception as e:
        print(f"Error saving image to {output_path}: {e}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Batch watermark images with custom text or watermark overlay logo."
    )
    
    # Input/Output
    parser.add_argument("input", help="Path to an image file or directory containing images.")
    parser.add_argument("-o", "--output", required=True, help="Output file path or directory name.")
    
    # Watermark type (Mutually exclusive group)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-t", "--text", help="Watermark text to overlay.")
    group.add_argument("-w", "--watermark-image", help="Watermark image logo path to overlay.")
    
    # Styles and properties
    parser.add_argument(
        "-p", "--position", 
        choices=["top-left", "top-right", "bottom-left", "bottom-right", "center"],
        default="bottom-right", 
        help="Watermark position placement (default: bottom-right)."
    )
    parser.add_argument(
        "--opacity", 
        type=float, 
        default=0.4, 
        help="Opacity value between 0.0 and 1.0 (default: 0.4)."
    )
    parser.add_argument(
        "--font-size", 
        type=int, 
        default=36, 
        help="Font size for text watermarks (default: 36)."
    )
    parser.add_argument(
        "--margin", 
        type=int, 
        default=25, 
        help="Margin spacing from corners in pixels (default: 25)."
    )
    parser.add_argument(
        "--scale", 
        type=float, 
        default=0.2, 
        help="Watermark scale factor relative to base image width (default: 0.2)."
    )
    parser.add_argument(
        "--dry-run", 
        action="store_true", 
        help="Simulate the batch operation without writing files."
    )
    
    args = parser.parse_args()
    
    if not HAS_PIL:
        install_instructions()
        sys.exit(1)
        
    if not os.path.exists(args.input):
        print(f"Error: Input path '{args.input}' does not exist.", file=sys.stderr)
        sys.exit(1)

    # Compile valid extensions
    valid_exts = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff"}
    
    # Find files to process
    files_to_process = []
    if os.path.isdir(args.input):
        for root, _, files in os.walk(args.input):
            for file in files:
                if os.path.splitext(file)[1].lower() in valid_exts:
                    files_to_process.append(os.path.join(root, file))
    else:
        if os.path.splitext(args.input)[1].lower() in valid_exts:
            files_to_process.append(args.input)
            
    if not files_to_process:
        print("No valid images found to process.", file=sys.stderr)
        sys.exit(0)
        
    print(f"Found {len(files_to_process)} image(s) to process.", file=sys.stderr)
    
    success_count = 0
    for idx, filepath in enumerate(files_to_process, 1):
        # Determine output filepath
        if os.path.isdir(args.input):
            rel_path = os.path.relpath(filepath, args.input)
            out_filepath = os.path.join(args.output, rel_path)
        else:
            if os.path.isdir(args.output) or args.output.endswith(("/", "\\")):
                out_filepath = os.path.join(args.output, os.path.basename(filepath))
            else:
                out_filepath = args.output
                
        print(f"[{idx}/{len(files_to_process)}] Processing: {os.path.basename(filepath)} -> {out_filepath}")
        
        if args.dry_run:
            success_count += 1
            continue
            
        success = apply_watermark(
            image_path=filepath,
            output_path=out_filepath,
            watermark_text=args.text,
            watermark_image_path=args.watermark_image,
            position=args.position,
            opacity=args.opacity,
            font_size=args.font_size,
            margin=args.margin,
            watermark_scale=args.scale
        )
        if success:
            success_count += 1
            
    print(f"\nDone! Successfully processed {success_count} of {len(files_to_process)} images.")

if __name__ == "__main__":
    main()
