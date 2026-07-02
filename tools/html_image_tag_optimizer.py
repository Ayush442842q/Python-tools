#!/usr/bin/env python3
"""
HTML Image Tag Optimizer

Parses HTML documents to find image tags (<img>), audits and optimizes them:
- Warns or auto-adds missing 'alt' attributes.
- Auto-adds 'loading="lazy"' to improve page load performance (above-the-fold images can be skipped).
- Natively reads dimensions of local images (PNG, JPEG, GIF, SVG) to inject missing 'width' and 'height'
  attributes, preventing Cumulative Layout Shift (CLS).

Usage:
    python tools/html_image_tag_optimizer.py [path_to_html_or_dir] [options]
"""

import os
import re
import sys
import struct
import argparse
from pathlib import Path

# ANSI Colors
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"

def print_colored(text: str, color: str, end: str = "\n"):
    if sys.stdout.isatty():
        print(f"{color}{text}{RESET}", end=end)
    else:
        print(text, end=end)

def get_image_size(filepath: Path):
    """
    Zero-dependency extraction of image dimensions (width, height).
    Supports PNG, JPEG, GIF, and SVG.
    """
    if not filepath.is_file():
        return None, None
    try:
        with open(filepath, 'rb') as f:
            head = f.read(24)
            # PNG
            if head.startswith(b'\x89PNG\r\n\x1a\n'):
                f.seek(16)
                width, height = struct.unpack('>ii', f.read(8))
                return width, height
            # GIF
            elif head.startswith(b'GIF87a') or head.startswith(b'GIF89a'):
                width, height = struct.unpack('<HH', head[6:10])
                return width, height
            # JPEG
            elif head.startswith(b'\xff\xd8'):
                f.seek(2)
                while True:
                    marker, size_field = struct.unpack('>HH', f.read(4))
                    if marker == 0xffda or marker == 0xffd9: # Start of scan / End of image
                        break
                    # SOF0 to SOF15 except DHT, JPG, DAC
                    if marker >= 0xffc0 and marker <= 0xffcf and marker not in [0xffc4, 0xffc8, 0xffcc]:
                        f.read(1) # precision
                        height, width = struct.unpack('>HH', f.read(4))
                        return width, height
                    else:
                        # Skip this chunk
                        offset = size_field - 2
                        if offset > 0:
                            f.seek(offset, 1)
            # SVG
            else:
                f.seek(0)
                try:
                    content = f.read(2048).decode('utf-8', errors='ignore')
                    if '<svg' in content:
                        w_match = re.search(r'\bwidth=["\']([\d\.]+)(px|%)?["\']', content)
                        h_match = re.search(r'\bheight=["\']([\d\.]+)(px|%)?["\']', content)
                        if w_match and h_match:
                            return int(float(w_match.group(1))), int(float(h_match.group(1)))
                        vb_match = re.search(r'\bviewBox=["\'][\s\d\.,-]+["\']', content)
                        if vb_match:
                            vb = re.findall(r'[\d\.]+', vb_match.group(0))
                            if len(vb) >= 4:
                                return int(float(vb[2])), int(float(vb[3]))
                except Exception:
                    pass
    except Exception:
        pass
    return None, None

def parse_img_tag(tag_str: str) -> dict:
    """Parses attributes from an <img> tag string using regex."""
    # Find all attribute-value pairs, taking into account single, double, or unquoted values
    pattern = re.compile(r'([a-zA-Z0-9\-]+)\s*=\s*(?:["\']([^"\']*)["\']|([^\s>]+))')
    attrs = {}
    for match in pattern.finditer(tag_str):
        name = match.group(1).lower()
        val = match.group(2) if match.group(2) is not None else match.group(3)
        attrs[name] = val
    return attrs

def build_img_tag(tag_name: str, attrs: dict, self_closing: bool = False) -> str:
    """Constructs an <img> tag string from attributes."""
    parts = [f"<{tag_name}"]
    # Keep original order if possible, or print standard ones first
    ordered_keys = ['src', 'alt', 'width', 'height', 'loading']
    remaining_keys = sorted([k for k in attrs.keys() if k not in ordered_keys])
    
    for k in ordered_keys + remaining_keys:
        if k in attrs and attrs[k] is not None:
            parts.append(f'{k}="{attrs[k]}"')
            
    suffix = " />" if self_closing else ">"
    return " ".join(parts) + suffix

def optimize_html_file(file_path: Path, args) -> bool:
    """Analyzes and modifies an HTML file to optimize <img> tags."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            html_content = f.read()
    except Exception as e:
        print_colored(f"Error reading {file_path}: {e}", RED)
        return False

    # Find <img> tags
    # Handles multiline and self-closing tags
    img_pattern = re.compile(r'(<img\b[^>]*>)', re.IGNORECASE | re.DOTALL)
    
    changes = []
    warnings = []
    
    def replace_img(match):
        img_tag = match.group(1)
        # Check if it is self-closing
        self_closing = img_tag.rstrip().endswith("/>")
        attrs = parse_img_tag(img_tag)
        
        src = attrs.get('src', '')
        if not src:
            warnings.append(f"Image tag without 'src' attribute found: {img_tag.strip()}")
            return img_tag
            
        modified = False
        tag_desc = f"<img> src='{src}'"
        
        # 1. Alt tag check
        if 'alt' not in attrs:
            warnings.append(f"Missing 'alt' attribute: {tag_desc}")
            if args.fix_alt:
                attrs['alt'] = ""
                modified = True
                
        # 2. Loading lazy check
        if 'loading' not in attrs:
            # Check if we should skip above-the-fold images if they have certain classes
            # (simple heuristic: classes containing 'hero', 'banner', 'nav', 'header')
            classes = attrs.get('class', '').lower()
            above_fold_keywords = ['hero', 'banner', 'nav', 'header', 'above-fold']
            is_above_fold = any(kw in classes for kw in above_fold_keywords)
            
            if is_above_fold and not args.force_lazy:
                warnings.append(f"Skipping loading='lazy' for likely above-the-fold image: {tag_desc}")
            else:
                attrs['loading'] = 'lazy'
                modified = True
                changes.append(f"Added loading='lazy' to {tag_desc}")

        # 3. Dimension check (width/height)
        if 'width' not in attrs or 'height' not in attrs:
            # Try resolving local path relative to HTML file or relative to webroot
            img_path = None
            if not src.startswith(('http://', 'https://', 'data:', '//')):
                # Relative path
                img_path = file_path.parent / src
                if not img_path.exists() and args.webroot:
                    img_path = Path(args.webroot) / src.lstrip('/')
                
                if img_path and img_path.is_file():
                    w, h = get_image_size(img_path)
                    if w and h:
                        if 'width' not in attrs:
                            attrs['width'] = str(w)
                            modified = True
                            changes.append(f"Injected width='{w}' to {tag_desc}")
                        if 'height' not in attrs:
                            attrs['height'] = str(h)
                            modified = True
                            changes.append(f"Injected height='{h}' to {tag_desc}")
                    else:
                        warnings.append(f"Could not read local image dimensions: {src}")
                else:
                    warnings.append(f"Local image file not found: {src} (resolved as: {img_path})")
            else:
                # External images warning
                warnings.append(f"Skipped dimension injection for remote image: {src}")
                
        if modified:
            return build_img_tag("img", attrs, self_closing)
        return img_tag

    new_html_content = img_pattern.sub(replace_img, html_content)
    
    # Report findings
    if changes or warnings:
        print_colored(f"\nFile: {file_path}", BOLD)
        for w in warnings:
            print_colored(f"  [WARNING] {w}", YELLOW)
        for c in changes:
            print_colored(f"  [FIXED] {c}", GREEN)
            
        if not args.dry_run and new_html_content != html_content:
            try:
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(new_html_content)
                print_colored("  Saved changes.", GREEN)
            except Exception as e:
                print_colored(f"  Error writing file: {e}", RED)
        elif args.dry_run and new_html_content != html_content:
            print_colored("  Dry run: changes not written to disk.", CYAN)
            
    return True

def main():
    parser = argparse.ArgumentParser(
        description="Optimize HTML img tags for performance and prevention of layout shifts."
    )
    parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to an HTML file or a directory containing HTML files (default: current directory)"
    )
    parser.add_argument(
        "--dry-run", "-d",
        action="store_true",
        help="Print issues and proposed fixes without writing changes back to files"
    )
    parser.add_argument(
        "--fix-alt",
        action="store_true",
        default=True,
        help="Automatically inject missing alt=\"\" tags (default: True)"
    )
    parser.add_argument(
        "--force-lazy",
        action="store_true",
        help="Force loading='lazy' even for hero, header, or banner images"
    )
    parser.add_argument(
        "--webroot", "-r",
        help="Virtual webroot folder to resolve absolute image paths (e.g. src='/images/logo.png')"
    )
    
    args = parser.parse_args()
    
    target_path = Path(args.path)
    if not target_path.exists():
        print_colored(f"Error: path '{target_path}' does not exist.", RED)
        return 1
        
    html_files = []
    if target_path.is_file():
        if target_path.suffix.lower() in ['.html', '.htm']:
            html_files.append(target_path)
    else:
        for root, _, files in os.walk(target_path):
            for file in files:
                if file.lower().endswith(('.html', '.htm')):
                    html_files.append(Path(root) / file)
                    
    if not html_files:
        print_colored("No HTML files found to optimize.", YELLOW)
        return 0
        
    print_colored(f"Scanning {len(html_files)} HTML file(s) for <img> optimizations...", BOLD)
    success_count = 0
    for file in html_files:
        if optimize_html_file(file, args):
            success_count += 1
            
    print_colored(f"\nOptimization complete! Successfully processed {success_count}/{len(html_files)} files.", BOLD)
    return 0

if __name__ == "__main__":
    sys.exit(main())
