#!/usr/bin/env python3
"""
PWA Web Manifest Generator

A standalone utility to generate a Progressive Web App (PWA) JSON manifest file
(manifest.json) and provide the necessary HTML `<head>` markup. Supports both
command-line arguments and an interactive configuration wizard.

Usage:
    python webmanifest_generator.py --name "My PWA App" --short-name "MyPWA" --theme-color "#2F80ED"
    python webmanifest_generator.py --interactive
"""

import os
import sys
import json
import argparse


def get_default_manifest():
    return {
        "name": "My Progressive Web App",
        "short_name": "MyPWA",
        "description": "An amazing Progressive Web App built with modern standards.",
        "start_url": "/",
        "display": "standalone",
        "background_color": "#ffffff",
        "theme_color": "#000000",
        "orientation": "any",
        "categories": ["utilities"],
        "icons": [
            {
                "src": "icons/icon-192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any"
            },
            {
                "src": "icons/icon-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any"
            },
            {
                "src": "icons/icon-maskable-192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "maskable"
            },
            {
                "src": "icons/icon-maskable-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "maskable"
            }
        ]
    }


def prompt_user(defaults):
    """Interactive CLI prompts to customize the webmanifest fields."""
    print("=" * 60)
    print(" PWA Web Manifest Interactive Wizard ")
    print("=" * 60)
    print("Press Enter to accept the [default value] in brackets.\n")

    manifest = {}

    # App Name
    manifest["name"] = input(f"App Full Name [{defaults['name']}]: ").strip() or defaults["name"]
    
    # Short Name
    default_short = defaults["short_name"]
    manifest["short_name"] = input(f"App Short Name (homescreen) [{default_short}]: ").strip() or default_short

    # Description
    manifest["description"] = input(f"Description [{defaults['description']}]: ").strip() or defaults["description"]

    # Start URL
    manifest["start_url"] = input(f"Start URL [{defaults['start_url']}]: ").strip() or defaults["start_url"]

    # Display Mode
    display_options = ["standalone", "minimal-ui", "fullscreen", "browser"]
    print(f"Display Mode options: {', '.join(display_options)}")
    display = input(f"Display Mode [{defaults['display']}]: ").strip().lower()
    manifest["display"] = display if display in display_options else defaults["display"]

    # Orientation
    orientation_options = ["any", "natural", "landscape", "portrait", "portrait-primary"]
    print(f"Orientation options: {', '.join(orientation_options)}")
    orient = input(f"Orientation [{defaults['orientation']}]: ").strip().lower()
    manifest["orientation"] = orient if orient in orientation_options else defaults["orientation"]

    # Background Color
    bg = input(f"Background Color (hex, e.g., #ffffff) [{defaults['background_color']}]: ").strip()
    manifest["background_color"] = bg if bg.startswith('#') or bg == "" else f"#{bg}"
    if not manifest["background_color"]:
        manifest["background_color"] = defaults["background_color"]

    # Theme Color
    tc = input(f"Theme Color (hex, e.g., #000000) [{defaults['theme_color']}]: ").strip()
    manifest["theme_color"] = tc if tc.startswith('#') or tc == "" else f"#{tc}"
    if not manifest["theme_color"]:
        manifest["theme_color"] = defaults["theme_color"]

    # Categories
    cats = input("Categories (comma separated) [utilities]: ").strip()
    if cats:
        manifest["categories"] = [c.strip().lower() for c in cats.split(",")]
    else:
        manifest["categories"] = defaults["categories"]

    # Icons Prefix Folder
    icons_dir = input("Icons directory path prefix [icons]: ").strip() or "icons"
    manifest["icons"] = [
        {
            "src": f"{icons_dir}/icon-192.png",
            "sizes": "192x192",
            "type": "image/png",
            "purpose": "any"
        },
        {
            "src": f"{icons_dir}/icon-512.png",
            "sizes": "512x512",
            "type": "image/png",
            "purpose": "any"
        },
        {
            "src": f"{icons_dir}/icon-maskable-192.png",
            "sizes": "192x192",
            "type": "image/png",
            "purpose": "maskable"
        },
        {
            "src": f"{icons_dir}/icon-maskable-512.png",
            "sizes": "512x512",
            "type": "image/png",
            "purpose": "maskable"
        }
    ]

    return manifest


def print_html_tags(manifest, manifest_path):
    """Outputs the recommended HTML header elements for PWA capability."""
    manifest_filename = os.path.basename(manifest_path)
    theme_color = manifest.get("theme_color", "#000000")
    short_name = manifest.get("short_name", "PWA")
    
    # Try to find a 180x180 or 192x192 icon for Apple Touch Icon
    apple_icon_href = "icons/icon-192.png"
    for icon in manifest.get("icons", []):
        if "192" in icon.get("sizes", ""):
            apple_icon_href = icon.get("src")
            break

    html_markup = f"""
<!-- Add this code to the <head> section of your index.html -->
<link rel="manifest" href="/{manifest_filename}">

<!-- Mobile & Theme Options -->
<meta name="theme-color" content="{theme_color}">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-title" content="{short_name}">

<!-- Apple Touch Icon (iOS Homescreen) -->
<link rel="apple-touch-icon" href="{apple_icon_href}">
"""
    print("\n" + "=" * 60)
    print(" RECOMMENDED HTML HEADER TAGS ")
    print("=" * 60)
    print(html_markup.strip())
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Generate standard-compliant PWA Web Manifest (manifest.json) files."
    )
    
    parser.add_argument(
        "-i", "--interactive", 
        action="store_true", 
        help="Run interactive config wizard prompts"
    )
    parser.add_argument("-o", "--output", default="manifest.json", help="Path to save the manifest.json file")
    
    parser.add_argument("--name", help="Full name of the web application")
    parser.add_argument("--short-name", help="Short name of the web application")
    parser.add_argument("--description", help="Description of the application")
    parser.add_argument("--start-url", help="Start URL for the PWA (defaults to '/')")
    parser.add_argument("--display", choices=["standalone", "minimal-ui", "fullscreen", "browser"], help="PWA display mode")
    parser.add_argument("--theme-color", help="Theme color (hex format, e.g., #0088cc)")
    parser.add_argument("--background-color", help="Background color (hex format, e.g., #ffffff)")
    parser.add_argument("--icons-dir", default="icons", help="Icon folder directory prefix")

    args = parser.parse_args()

    defaults = get_default_manifest()

    if args.interactive or (len(sys.argv) == 1):
        manifest = prompt_user(defaults)
    else:
        # Use arguments, fallback to defaults
        manifest = defaults.copy()
        if args.name:
            manifest["name"] = args.name
        if args.short_name:
            manifest["short_name"] = args.short_name
        if args.description:
            manifest["description"] = args.description
        if args.start_url:
            manifest["start_url"] = args.start_url
        if args.display:
            manifest["display"] = args.display
        
        # Color normalization
        if args.theme_color:
            tc = args.theme_color
            manifest["theme_color"] = tc if tc.startswith('#') else f"#{tc}"
        if args.background_color:
            bg = args.background_color
            manifest["background_color"] = bg if bg.startswith('#') else f"#{bg}"
            
        if args.icons_dir != "icons":
            manifest["icons"] = [
                {
                    "src": f"{args.icons_dir}/icon-192.png",
                    "sizes": "192x192",
                    "type": "image/png",
                    "purpose": "any"
                },
                {
                    "src": f"{args.icons_dir}/icon-512.png",
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "any"
                },
                {
                    "src": f"{args.icons_dir}/icon-maskable-192.png",
                    "sizes": "192x192",
                    "type": "image/png",
                    "purpose": "maskable"
                },
                {
                    "src": f"{args.icons_dir}/icon-maskable-512.png",
                    "sizes": "512x512",
                    "type": "image/png",
                    "purpose": "maskable"
                }
            ]

    # Write manifest file
    try:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
        print(f"\nManifest successfully created and written to '{args.output}'")
        
        # Output recommended header tags
        print_html_tags(manifest, args.output)
        return 0
    except Exception as e:
        print(f"Error writing manifest file: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    main()
