#!/usr/bin/env python3
"""
Image Optimizer
Optimize images by compressing, resizing, and converting formats.

Usage:
    python image_optimizer.py <image1.jpg image2.png ...> [options]
    python image_optimizer.py --dir ./images --recursive
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Tuple

try:
    from PIL import Image
except ImportError:
    print("Installing Pillow...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "Pillow", "-q"])
    from PIL import Image


def get_image_info(path: str) -> dict:
    """Get detailed information about an image."""
    try:
        with Image.open(path) as img:
            return {
                "format": img.format,
                "mode": img.mode,
                "size": img.size,
                "width": img.width,
                "height": img.height,
                "file_size": os.path.getsize(path)
            }
    except Exception as e:
        return {"error": str(e)}


def optimize_image(
    input_path: str,
    output_path: str = None,
    quality: int = 85,
    max_width: int = None,
    max_height: int = None,
    output_format: str = None,
    progressive: bool = True,
    optimize: bool = True
) -> dict:
    """
    Optimize an image with various settings.
    
    Args:
        input_path: Path to input image
        output_path: Path for output image (default: overwrite input)
        quality: JPEG quality (1-100, default: 85)
        max_width: Maximum width (resize if exceeded)
        max_height: Maximum height (resize if exceeded)
        output_format: Output format (default: same as input)
        progressive: Use progressive JPEG
        optimize: Enable PIL optimizations
    
    Returns:
        dict with optimization results
    """
    input_path = Path(input_path)
    
    if not output_path:
        # Create output path with _opt suffix
        output_path = input_path.parent / f"{input_path.stem}_opt{input_path.suffix}"
    else:
        output_path = Path(output_path)
    
    try:
        with Image.open(input_path) as img:
            original_info = get_image_info(str(input_path))
            
            # Convert to RGB if necessary (for JPEG output)
            if output_format and output_format.upper() == 'JPEG':
                if img.mode in ('RGBA', 'P'):
                    # Create white background for transparency
                    background = Image.new('RGB', img.size, (255, 255, 255))
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    background.paste(img, mask=img.split()[3] if img.mode == 'RGBA' else None)
                    img = background
                elif img.mode != 'RGB':
                    img = img.convert('RGB')
            
            # Resize if dimensions exceed max
            if max_width or max_height:
                orig_width, orig_height = img.size
                
                if max_width and orig_width > max_width:
                    ratio = max_width / orig_width
                    new_width = max_width
                    new_height = int(orig_height * ratio)
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                
                if max_height and img.size[1] > max_height:
                    ratio = max_height / img.size[1]
                    new_height = max_height
                    new_width = int(img.size[0] * ratio)
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            
            # Determine output format
            if output_format:
                save_format = output_format.upper()
            else:
                save_format = img.format or 'PNG'
            
            # Save options
            save_kwargs = {
                "optimize": optimize,
            }
            
            if save_format == 'JPEG':
                save_kwargs["quality"] = quality
                save_kwargs["progressive"] = progressive
            elif save_format == 'PNG':
                save_kwargs["optimize"] = True
            elif save_format in ('WEBP',):
                save_kwargs["quality"] = quality
                save_kwargs["method"] = 6  # Best compression
            
            # Save the optimized image
            img.save(str(output_path), format=save_format, **save_kwargs)
            
            # Get optimized info
            optimized_info = get_image_info(str(output_path))
            
            if "error" in optimized_info:
                return {
                    "success": False,
                    "error": optimized_info["error"],
                    "input_path": str(input_path),
                    "output_path": str(output_path)
                }
            
            original_size = original_info["file_size"]
            optimized_size = optimized_info["file_size"]
            savings = original_size - optimized_size
            savings_percent = (savings / original_size * 100) if original_size > 0 else 0
            
            return {
                "success": True,
                "input_path": str(input_path),
                "output_path": str(output_path),
                "original": {
                    "format": original_info["format"],
                    "size": original_info["size"],
                    "file_size": original_size,
                    "file_size_mb": round(original_size / (1024 * 1024), 2)
                },
                "optimized": {
                    "format": optimized_info["format"],
                    "size": optimized_info["size"],
                    "file_size": optimized_size,
                    "file_size_mb": round(optimized_size / (1024 * 1024), 2)
                },
                "savings": {
                    "bytes": savings,
                    "mb": round(savings / (1024 * 1024), 2),
                    "percent": round(savings_percent, 2)
                },
                "settings": {
                    "quality": quality,
                    "max_width": max_width,
                    "max_height": max_height,
                    "format": save_format,
                    "progressive": progressive,
                    "optimize": optimize
                }
            }
            
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "input_path": str(input_path),
            "output_path": str(output_path) if 'output_path' in locals() else None
        }


def format_output(results: list, json_format: bool = False) -> str:
    """Format optimization results for output."""
    if json_format:
        return json.dumps(results, indent=2)
    
    output_lines = []
    output_lines.append("=" * 80)
    output_lines.append("IMAGE OPTIMIZER")
    output_lines.append("=" * 80)
    
    total_original = 0
    total_optimized = 0
    success_count = 0
    
    for result in results:
        if result.get("success"):
            success_count += 1
            total_original += result["original"]["file_size"]
            total_optimized += result["optimized"]["file_size"]
            
            output_lines.append(f"\n✅ {result['input_path']}")
            output_lines.append(f"  Original:  {result['original']['file_size']:,} bytes ({result['original']['size'][0]}x{result['original']['size'][1]})")
            output_lines.append(f"  Optimized: {result['optimized']['file_size']:,} bytes ({result['optimized']['size'][0]}x{result['optimized']['size'][1]})")
            output_lines.append(f"  Saved:     {result['savings']['bytes']:,} bytes ({result['savings']['percent']:.1f}%)")
            
            if result["output_path"] != result["input_path"]:
                output_lines.append(f"  Output:    {result['output_path']}")
        else:
            output_lines.append(f"\n❌ {result.get('input_path', 'Unknown')}")
            output_lines.append(f"  Error: {result.get('error', 'Unknown error')}")
    
    if success_count > 0:
        total_savings = total_original - total_optimized
        total_savings_percent = (total_savings / total_original * 100) if total_original > 0 else 0
        
        output_lines.append("\n" + "=" * 80)
        output_lines.append("SUMMARY")
        output_lines.append(f"  Processed: {success_count} images")
        output_lines.append(f"  Original size:  {total_original:,} bytes ({total_original/(1024*1024):.2f} MB)")
        output_lines.append(f"  Optimized size: {total_optimized:,} bytes ({total_optimized/(1024*1024):.2f} MB)")
        output_lines.append(f"  Total savings:  {total_savings:,} bytes ({total_savings/(1024*1024):.2f} MB, {total_savings_percent:.1f}%)")
        output_lines.append("=" * 80)
    else:
        output_lines.append("\n" + "=" * 80)
        output_lines.append("No images were successfully optimized.")
        output_lines.append("=" * 80)
    
    return "\n".join(output_lines)


def main():
    parser = argparse.ArgumentParser(
        description="Optimize images by compressing, resizing, and converting formats."
    )
    parser.add_argument(
        "images",
        nargs="*",
        help="Image files to optimize"
    )
    parser.add_argument(
        "--dir", "-d",
        type=str,
        help="Directory containing images to optimize"
    )
    parser.add_argument(
        "--recursive", "-r",
        action="store_true",
        help="Recursively search directory for images"
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        help="Output directory (default: optimize in-place with _opt suffix)"
    )
    parser.add_argument(
        "--quality", "-q",
        type=int,
        default=85,
        help="JPEG/WebP quality (1-100, default: 85)"
    )
    parser.add_argument(
        "--max-width",
        type=int,
        help="Maximum width in pixels"
    )
    parser.add_argument(
        "--max-height",
        type=int,
        help="Maximum height in pixels"
    )
    parser.add_argument(
        "--format", "-f",
        type=str,
        choices=["JPEG", "PNG", "WEBP"],
        help="Output format (default: same as input)"
    )
    parser.add_argument(
        "--no-progressive",
        action="store_true",
        help="Disable progressive JPEG encoding"
    )
    parser.add_argument(
        "--no-optimize",
        action="store_true",
        help="Disable PIL optimization"
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output results in JSON format"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be optimized without actually processing"
    )
    
    args = parser.parse_args()
    
    # Collect image files
    image_files = list(args.images) if args.images else []
    
    if args.dir:
        dir_path = Path(args.dir)
        if not dir_path.exists():
            print(f"Error: Directory '{args.dir}' not found.")
            sys.exit(1)
        
        if args.recursive:
            patterns = ["**/*.jpg", "**/*.jpeg", "**/*.png", "**/*.gif", "**/*.webp", "**/*.bmp"]
        else:
            patterns = ["*.jpg", "*.jpeg", "*.png", "*.gif", "*.webp", "*.bmp"]
        
        for pattern in patterns:
            image_files.extend([str(p) for p in dir_path.glob(pattern)])
    
    if not image_files:
        parser.print_help()
        print("\nError: No image files provided.")
        sys.exit(1)
    
    # Remove duplicates
    image_files = list(set(image_files))
    
    print(f"Found {len(image_files)} image(s) to process...")
    
    if args.dry_run:
        print("\nDry run - would optimize the following images:")
        for img in image_files:
            info = get_image_info(img)
            if "error" not in info:
                print(f"  {img} ({info['size'][0]}x{info['size'][1]}, {info['file_size']:,} bytes)")
            else:
                print(f"  {img} (ERROR: {info['error']})")
        sys.exit(0)
    
    # Optimize images
    results = []
    for img_path in image_files:
        # Determine output path
        output_path = None
        if args.output:
            output_dir = Path(args.output)
            output_dir.mkdir(parents=True, exist_ok=True)
            output_path = output_dir / Path(img_path).name
        
        result = optimize_image(
            img_path,
            output_path=output_path,
            quality=args.quality,
            max_width=args.max_width,
            max_height=args.max_height,
            output_format=args.format,
            progressive=not args.no_progressive,
            optimize=not args.no_optimize
        )
        results.append(result)
    
    output = format_output(results, json_format=args.json)
    print(output)
    
    # Exit with error if any failures
    failures = sum(1 for r in results if not r.get("success"))
    if failures > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()