#!/usr/bin/env python3
"""
Web Bundle Size Auditor
-----------------------
Scans web build output directories (like dist/ or build/) to analyze bundle files.
Features:
1. Calculates raw and Gzipped sizes of JS, CSS, HTML, and image files.
2. Checks files against customizable size budgets.
3. Audits files for minification status (heuristics based on whitespace/newlines).
4. Detects missing or exposed source maps (.map files).
5. Outputs a beautiful terminal report or JSON summary.

Author: Antigravity
License: MIT
"""

import os
import sys
import json
import gzip
import argparse
from typing import Dict, List, Any, Tuple

# Default budgets in bytes
DEFAULT_BUDGETS = {
    ".js": 250 * 1024,      # 250 KB
    ".css": 100 * 1024,     # 100 KB
    ".html": 50 * 1024,     # 50 KB
    "image": 500 * 1024,    # 500 KB (jpg, png, gif, svg, webp)
    "other": 1024 * 1024,   # 1 MB
}

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico"}

def get_gzip_size(filepath: str) -> int:
    """Calculate the size of the file when gzipped."""
    try:
        with open(filepath, "rb") as f_in:
            data = f_in.read()
        return len(gzip.compress(data))
    except Exception:
        return 0

def format_size(size_bytes: int) -> str:
    """Format bytes into a human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.2f} MB"

def check_minified(filepath: str) -> bool:
    """
    Check if a JS or CSS file is likely minified.
    Heuristic: Checks if the average line length is very high,
    or if the file is extremely large but has very few lines.
    """
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            sample = f.read(10000)  # Read first 10KB
            if not sample:
                return True
            lines = sample.splitlines()
            if not lines:
                return True
            # If the average line length is > 200 characters, it's likely minified
            avg_line_len = len(sample) / len(lines)
            return avg_line_len > 200
    except Exception:
        return False

def analyze_build_dir(dir_path: str, budgets: Dict[str, int]) -> Dict[str, Any]:
    """Scan and audit files in the build directory."""
    results = []
    category_sizes = {"JS": 0, "CSS": 0, "HTML": 0, "Images": 0, "SourceMaps": 0, "Other": 0}
    category_counts = {"JS": 0, "CSS": 0, "HTML": 0, "Images": 0, "SourceMaps": 0, "Other": 0}

    for root, _, files in os.walk(dir_path):
        for file in files:
            filepath = os.path.join(root, file)
            rel_path = os.path.relpath(filepath, dir_path)
            
            # Skip directories or zero-byte files
            if not os.path.isfile(filepath):
                continue
                
            raw_size = os.path.getsize(filepath)
            gz_size = get_gzip_size(filepath) if raw_size > 0 else 0
            
            _, ext = os.path.splitext(file.lower())
            
            # Determine category & budget key
            category = "Other"
            budget_key = "other"
            
            if ext == ".js":
                category = "JS"
                budget_key = ".js"
            elif ext == ".css":
                category = "CSS"
                budget_key = ".css"
            elif ext in (".html", ".htm"):
                category = "HTML"
                budget_key = ".html"
            elif ext in IMAGE_EXTENSIONS:
                category = "Images"
                budget_key = "image"
            elif ext == ".map":
                category = "SourceMaps"
                budget_key = "other"

            category_sizes[category] += raw_size
            category_counts[category] += 1
            
            # Get budget
            budget = budgets.get(budget_key, DEFAULT_BUDGETS["other"])
            exceeds_budget = raw_size > budget
            
            # Minification check for JS/CSS
            is_minified = None
            if category in ("JS", "CSS"):
                is_minified = check_minified(filepath)
                
            # Source map check
            has_sourcemap = False
            if category in ("JS", "CSS"):
                map_file = filepath + ".map"
                if os.path.exists(map_file):
                    has_sourcemap = True

            results.append({
                "path": rel_path,
                "category": category,
                "raw_size": raw_size,
                "gzip_size": gz_size,
                "budget": budget,
                "exceeds_budget": exceeds_budget,
                "is_minified": is_minified,
                "has_sourcemap": has_sourcemap
            })

    total_size = sum(category_sizes.values())
    
    return {
        "files": results,
        "summary": {
            "total_size": total_size,
            "category_sizes": category_sizes,
            "category_counts": category_counts
        }
    }

def main():
    parser = argparse.ArgumentParser(description="Web Bundle Size Auditor - Audit front-end builds for size budgets and optimization issues.")
    parser.add_argument("dir", nargs="?", default=".", help="Build output directory to scan (e.g. dist/ or build/)")
    parser.add_argument("--js-budget", type=int, help="Override budget for JavaScript files in KB")
    parser.add_argument("--css-budget", type=int, help="Override budget for CSS files in KB")
    parser.add_argument("--img-budget", type=int, help="Override budget for Image files in KB")
    parser.add_argument("--json", action="store_true", help="Output audit report as JSON")
    args = parser.parse_args()

    build_dir = os.path.abspath(args.dir)
    if not os.path.exists(build_dir) or not os.path.isdir(build_dir):
        print(f"Error: Directory '{build_dir}' does not exist or is not a directory.", file=sys.stderr)
        sys.exit(1)

    # Configure budgets
    budgets = DEFAULT_BUDGETS.copy()
    if args.js_budget:
        budgets[".js"] = args.js_budget * 1024
    if args.css_budget:
        budgets[".css"] = args.css_budget * 1024
    if args.img_budget:
        budgets["image"] = args.img_budget * 1024

    analysis = analyze_build_dir(build_dir, budgets)

    if args.json:
        print(json.dumps(analysis, indent=2))
        return

    # Visual terminal report
    print("=" * 95)
    print(f"WEB BUNDLE SIZE AUDIT: {build_dir}")
    print("=" * 95)
    
    summary = analysis["summary"]
    print(f"{'Category':<15} | {'Count':<8} | {'Total Size':<15} | {'Percentage':<10}")
    print("-" * 55)
    
    for cat, size in summary["category_sizes"].items():
        count = summary["category_counts"][cat]
        pct = (size / summary["total_size"] * 100) if summary["total_size"] > 0 else 0
        print(f"{cat:<15} | {count:<8} | {format_size(size):<15} | {pct:.1f}%")
        
    print("-" * 55)
    print(f"{'TOTAL':<15} | {sum(summary['category_counts'].values()):<8} | {format_size(summary['total_size']):<15} | 100.0%")
    print("=" * 95)
    
    # Audit Warnings
    warnings = []
    unminified_files = []
    oversized_files = []
    exposed_sourcemaps = []
    
    for file_info in analysis["files"]:
        # Budget warning
        if file_info["exceeds_budget"]:
            oversized_files.append(file_info)
        
        # Minification check
        if file_info["category"] in ("JS", "CSS") and file_info["is_minified"] is False:
            unminified_files.append(file_info)
            
        # Exposed map warnings
        if file_info["category"] == "SourceMaps":
            exposed_sourcemaps.append(file_info)

    if oversized_files:
        print(f"\n\033[91m[WARNING] {len(oversized_files)} file(s) exceed their size budget:\033[0m")
        for f in oversized_files:
            print(f"  - {f['path']} ({format_size(f['raw_size'])}) > Budget: {format_size(f['budget'])}")

    if unminified_files:
        print(f"\n\033[93m[WARNING] {len(unminified_files)} JavaScript/CSS file(s) appear to be unminified:\033[0m")
        for f in unminified_files:
            print(f"  - {f['path']} ({format_size(f['raw_size'])})")

    if exposed_sourcemaps:
        print(f"\n\033[93m[INFO] {len(exposed_sourcemaps)} Source Map (.map) file(s) detected in build:\033[0m")
        for f in exposed_sourcemaps:
            print(f"  - {f['path']} - ensure maps are not deployed to production unless desired for public debugging.")

    if not oversized_files and not unminified_files:
        print("\n\033[92m[SUCCESS] All files conform to size budgets and are properly minified!\033[0m")

if __name__ == "__main__":
    main()
