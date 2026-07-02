#!/usr/bin/env python3
"""
Web App Manifest Validator

Validates web application manifest files (usually manifest.json or site.webmanifest)
for syntax, PWA installability requirements, recommended practices, and type correctness.

Usage:
    python tools/webmanifest_validator.py path/to/manifest.json

Requirements:
    - Python 3.6+
"""

import os
import sys
import json
import re
import argparse

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Valid values for display mode
VALID_DISPLAY_MODES = {"fullscreen", "standalone", "minimal-ui", "browser"}

# Valid values for orientation
VALID_ORIENTATIONS = {
    "any", "natural", "landscape", "landscape-primary", "landscape-secondary",
    "portrait", "portrait-primary", "portrait-secondary"
}

# Hex color regex
HEX_COLOR_pattern = re.compile(r"^#([A-Fa-f0-9]{3,4}|[A-Fa-f0-9]{6}|[A-Fa-f0-9]{8})$")
# Named/RGB/RGBA/HSL/HSLA color basic validation
OTHER_COLOR_pattern = re.compile(r"^(rgb|rgba|hsl|hsla)\(.*?\)$|^[a-zA-Z]+$")

def is_valid_color(color_str):
    if not isinstance(color_str, str):
        return False
    color_str = color_str.strip()
    return bool(HEX_COLOR_pattern.match(color_str) or OTHER_COLOR_pattern.match(color_str))

def validate_manifest(file_path, check_local_assets=False):
    errors = []
    warnings = []
    info = []

    if not os.path.exists(file_path):
        return None, [f"File not found: {file_path}"], [], []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as jde:
        return None, [f"Invalid JSON format: {jde}"], [], []
    except Exception as e:
        return None, [f"Error reading file: {e}"], [], []

    if not isinstance(data, dict):
        return None, ["Manifest root must be a JSON object."], [], []

    # 1. Check Identity fields
    if "name" not in data and "short_name" not in data:
        errors.append("PWA Installability: Either 'name' or 'short_name' must be specified.")
    else:
        if "name" in data and not isinstance(data["name"], str):
            errors.append("'name' must be a string.")
        if "short_name" in data:
            if not isinstance(data["short_name"], str):
                errors.append("'short_name' must be a string.")
            elif len(data["short_name"]) > 12:
                warnings.append("'short_name' should ideally be 12 characters or less to avoid truncation on home screens.")

    # 2. Check Description & Categories
    if "description" in data:
        if not isinstance(data["description"], str):
            errors.append("'description' must be a string.")
    else:
        warnings.append("Recommended: Add a 'description' to explain the purpose of your app.")

    if "categories" in data:
        if not isinstance(data["categories"], list):
            errors.append("'categories' must be a list of strings.")
        else:
            for cat in data["categories"]:
                if not isinstance(cat, str):
                    errors.append(f"Category '{cat}' in 'categories' list must be a string.")

    # 3. Check Start URL & Scope
    if "start_url" not in data:
        errors.append("PWA Installability: 'start_url' is required.")
    elif not isinstance(data["start_url"], str):
        errors.append("'start_url' must be a string.")
        
    if "scope" in data:
        if not isinstance(data["scope"], str):
            errors.append("'scope' must be a string.")
    else:
        info.append("Info: 'scope' is not defined. Defaults to the directory containing the manifest.")

    # 4. Check Display & Orientation
    if "display" not in data:
        errors.append("PWA Installability: 'display' is required.")
    elif not isinstance(data["display"], str):
        errors.append("'display' must be a string.")
    elif data["display"] not in VALID_DISPLAY_MODES:
        errors.append(f"'display' must be one of: {', '.join(VALID_DISPLAY_MODES)} (found: '{data['display']}')")
    elif data["display"] not in {"standalone", "minimal-ui", "fullscreen"}:
        warnings.append(f"PWA Installability: 'display' should be 'standalone', 'minimal-ui', or 'fullscreen' to be installable on mobile browsers (found: '{data['display']}').")

    if "orientation" in data:
        if not isinstance(data["orientation"], str):
            errors.append("'orientation' must be a string.")
        elif data["orientation"] not in VALID_ORIENTATIONS:
            errors.append(f"'orientation' must be one of: {', '.join(VALID_ORIENTATIONS)} (found: '{data['orientation']}')")

    # 5. Check Colors
    for color_field in ("theme_color", "background_color"):
        if color_field in data:
            val = data[color_field]
            if not isinstance(val, str):
                errors.append(f"'{color_field}' must be a string.")
            elif not is_valid_color(val):
                errors.append(f"'{color_field}' is not a valid CSS color format: '{val}'. Use hex codes (#FFF or #FFFFFF) or standard CSS color values.")
        elif color_field == "theme_color":
            warnings.append("Recommended: Define a 'theme_color' to customize the browser address bar/UI toolbar color.")
        elif color_field == "background_color":
            warnings.append("Recommended: Define a 'background_color' for a smooth splash screen transition.")

    # 6. Check Icons
    has_large_icon = False
    has_maskable_icon = False
    
    if "icons" not in data:
        errors.append("PWA Installability: 'icons' array is required.")
    elif not isinstance(data["icons"], list):
        errors.append("'icons' must be a list of icon objects.")
    else:
        if len(data["icons"]) == 0:
            errors.append("PWA Installability: 'icons' array must not be empty.")
        for idx, icon in enumerate(data["icons"]):
            if not isinstance(icon, dict):
                errors.append(f"Icon at index {idx} must be a JSON object.")
                continue

            # Icon src
            if "src" not in icon:
                errors.append(f"Icon at index {idx} is missing 'src' attribute.")
            elif not isinstance(icon["src"], str):
                errors.append(f"Icon at index {idx} 'src' must be a string.")
            elif check_local_assets:
                # Check if asset exists locally relative to manifest
                manifest_dir = os.path.dirname(file_path)
                asset_path = os.path.join(manifest_dir, icon["src"].lstrip("/"))
                if not os.path.exists(asset_path):
                    warnings.append(f"Local asset check: Icon file '{icon['src']}' not found at '{asset_path}'.")

            # Icon sizes
            if "sizes" not in icon:
                errors.append(f"Icon at index {idx} is missing 'sizes' attribute (e.g., '192x192').")
            elif not isinstance(icon["sizes"], str):
                errors.append(f"Icon at index {idx} 'sizes' must be a string (e.g. '192x192' or space-separated list of sizes).")
            else:
                sizes_list = icon["sizes"].split()
                for size in sizes_list:
                    if size.lower() == "any":
                        continue
                    match = re.match(r"^(\d+)x(\d+)$", size.lower())
                    if not match:
                        errors.append(f"Icon at index {idx} size '{size}' is invalid. Must be in format <width>x<height> or 'any'.")
                    else:
                        w, h = int(match.group(1)), int(match.group(2))
                        if w >= 192 and h >= 192:
                            has_large_icon = True
                        if w != h:
                            warnings.append(f"Icon at index {idx} size '{size}' is non-square ({w}x{h}). App icons should be square.")

            # Icon type
            if "type" in icon:
                if not isinstance(icon["type"], str):
                    errors.append(f"Icon at index {idx} 'type' must be a string (e.g., 'image/png').")
                elif not icon["type"].startswith("image/"):
                    errors.append(f"Icon at index {idx} 'type' must be a valid image mime type (e.g. 'image/png', 'image/webp'). Found: '{icon['type']}'.")
            
            # Icon purpose
            if "purpose" in icon:
                if not isinstance(icon["purpose"], str):
                    errors.append(f"Icon at index {idx} 'purpose' must be a string.")
                else:
                    purposes = icon["purpose"].split()
                    for p in purposes:
                        if p not in {"any", "maskable", "monochrome"}:
                            errors.append(f"Icon at index {idx} purpose '{p}' is invalid. Allowed purposes: 'any', 'maskable', 'monochrome'.")
                        if p == "maskable":
                            has_maskable_icon = True

    if not has_large_icon:
        errors.append("PWA Installability: Must supply at least one icon of size 192x192 or larger (typically 192x192 and 512x512 PNGs are recommended).")
    if not has_maskable_icon:
        warnings.append("Recommended: Add a maskable icon ('purpose': 'maskable') so it looks good on devices that crop icons (like Android).")

    # 7. Check shortcuts
    if "shortcuts" in data:
        if not isinstance(data["shortcuts"], list):
            errors.append("'shortcuts' must be an array/list of shortcut objects.")
        else:
            for s_idx, shortcut in enumerate(data["shortcuts"]):
                if not isinstance(shortcut, dict):
                    errors.append(f"Shortcut at index {s_idx} must be a JSON object.")
                    continue
                if "name" not in shortcut or not isinstance(shortcut["name"], str):
                    errors.append(f"Shortcut at index {s_idx} requires a 'name' string.")
                if "url" not in shortcut or not isinstance(shortcut["url"], str):
                    errors.append(f"Shortcut at index {s_idx} requires a 'url' string.")

    # 8. Check screenshots
    if "screenshots" in data:
        if not isinstance(data["screenshots"], list):
            errors.append("'screenshots' must be a list of screenshot objects.")
        else:
            for s_idx, ss in enumerate(data["screenshots"]):
                if not isinstance(ss, dict):
                    errors.append(f"Screenshot at index {s_idx} must be a JSON object.")
                    continue
                if "src" not in ss or not isinstance(ss["src"], str):
                    errors.append(f"Screenshot at index {s_idx} requires a 'src' string.")
                if "sizes" in ss and not isinstance(ss["sizes"], str):
                    errors.append(f"Screenshot at index {s_idx} 'sizes' must be a string.")
                if "form_factor" in ss:
                    if not isinstance(ss["form_factor"], str):
                        errors.append(f"Screenshot at index {s_idx} 'form_factor' must be a string.")
                    elif ss["form_factor"] not in {"narrow", "wide"}:
                        errors.append(f"Screenshot at index {s_idx} 'form_factor' must be 'narrow' or 'wide'.")

    return data, errors, warnings, info

def main():
    parser = argparse.ArgumentParser(
        description="Validate Web App Manifest file for PWA requirements and recommendations.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("file", help="Path to manifest JSON file")
    parser.add_argument("-c", "--check-assets", action="store_true", help="Check if local icon files listed exist relative to manifest directory")
    parser.add_argument("--no-color", action="store_true", help="Disable colored output")

    args = parser.parse_args()
    use_color = not args.no_color and sys.stdout.isatty() and os.name != 'nt' or (os.name == 'nt' and 'COLORTERM' in os.environ)

    data, errors, warnings, infos = validate_manifest(args.file, args.check_assets)

    print()
    print_colored(f"{BOLD}Web App Manifest Audit: {args.file}{RESET}", BOLD if use_color else "", use_color)
    print("=" * (24 + len(args.file)))

    if data is None:
        for err in errors:
            print_colored(f"[-] FATAL: {err}", RED, use_color)
        return 1

    # Print results
    has_issues = False
    
    if errors:
        has_issues = True
        print_colored(f"\n{BOLD}[x] Errors ({len(errors)}) - MUST fix for PWA compatibility:{RESET}", RED, use_color)
        for err in errors:
            print_colored(f"  * {err}", RED, use_color)

    if warnings:
        print_colored(f"\n{BOLD}[!] Warnings ({len(warnings)}) - Recommended improvements:{RESET}", YELLOW, use_color)
        for warn in warnings:
            print_colored(f"  * {warn}", YELLOW, use_color)

    if infos:
        print_colored(f"\n{BOLD}[i] Details & Info:{RESET}", BLUE, use_color)
        for info in infos:
            print_colored(f"  * {info}", BLUE, use_color)

    print("\n-------------------------------------------------")
    if errors:
        print_colored(f"{BOLD}Result: FAILED{RESET} ({len(errors)} error(s), {len(warnings)} warning(s))", RED, use_color)
        return 1
    else:
        if warnings:
            print_colored(f"{BOLD}Result: PASSED WITH WARNINGS{RESET} (0 errors, {len(warnings)} warning(s))", YELLOW, use_color)
        else:
            print_colored(f"{BOLD}Result: PASSED{RESET} (All checks passed!)", GREEN, use_color)
        return 0

if __name__ == "__main__":
    sys.exit(main())
