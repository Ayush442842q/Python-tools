#!/usr/bin/env python3
"""
CSS to Tailwind Utility Class Converter
Parses CSS stylesheets and converts rules into Tailwind utility classes.
"""

import sys
import re
import argparse

# Mapping dictionary for standard static mappings
STATIC_MAPS = {
    # displays
    "display: flex": "flex",
    "display: grid": "grid",
    "display: block": "block",
    "display: inline-block": "inline-block",
    "display: inline": "inline",
    "display: none": "hidden",
    # positions
    "position: absolute": "absolute",
    "position: relative": "relative",
    "position: fixed": "fixed",
    "position: sticky": "sticky",
    # flex settings
    "flex-direction: row": "flex-row",
    "flex-direction: column": "flex-col",
    "flex-wrap: wrap": "flex-wrap",
    "justify-content: center": "justify-center",
    "justify-content: flex-start": "justify-start",
    "justify-content: flex-end": "justify-end",
    "justify-content: space-between": "justify-between",
    "justify-content: space-around": "justify-around",
    "justify-content: space-evenly": "justify-evenly",
    "align-items: center": "items-center",
    "align-items: flex-start": "items-start",
    "align-items: flex-end": "items-end",
    "align-items: stretch": "items-stretch",
    "align-items: baseline": "items-baseline",
    # text align
    "text-align: center": "text-center",
    "text-align: left": "text-left",
    "text-align: right": "text-right",
    "text-align: justify": "text-justify",
    # cursor
    "cursor: pointer": "cursor-pointer",
    "cursor: default": "cursor-default",
    "cursor: not-allowed": "cursor-not-allowed",
    # font weights
    "font-weight: bold": "font-bold",
    "font-weight: 700": "font-bold",
    "font-weight: normal": "font-normal",
    "font-weight: 400": "font-normal",
    "font-weight: 500": "font-medium",
    "font-weight: 600": "font-semibold",
    "font-style: italic": "italic",
    # box sizing
    "box-sizing: border-box": "box-border",
    "box-sizing: content-box": "box-content",
    # float
    "float: left": "float-left",
    "float: right": "float-right",
    # overflow
    "overflow: hidden": "overflow-hidden",
    "overflow: auto": "overflow-auto",
    "overflow: scroll": "overflow-scroll",
    "overflow-x: hidden": "overflow-x-hidden",
    "overflow-y: hidden": "overflow-y-hidden",
    # pointer events
    "pointer-events: none": "pointer-events-none",
    "pointer-events: auto": "pointer-events-auto",
}

# Spacing mapping: px/rem/em to Tailwind spacing steps
SPACING_UNITS = {
    "0": "0",
    "1px": "px",
    "2px": "0.5",
    "4px": "1",
    "6px": "1.5",
    "8px": "2",
    "10px": "2.5",
    "12px": "3",
    "14px": "3.5",
    "16px": "4",
    "20px": "5",
    "24px": "6",
    "28px": "7",
    "32px": "8",
    "36px": "9",
    "40px": "10",
    "44px": "11",
    "48px": "12",
    "56px": "14",
    "64px": "16",
    "80px": "20",
    "96px": "24",
    "112px": "28",
    "128px": "32",
    # Rem approximations
    "0.25rem": "1",
    "0.5rem": "2",
    "0.75rem": "3",
    "1rem": "4",
    "1.25rem": "5",
    "1.5rem": "6",
    "1.75rem": "7",
    "2rem": "8",
    "2.25rem": "9",
    "2.5rem": "10",
    "3rem": "12",
    "4rem": "16",
}

# Border radius map
RADIUS_MAP = {
    "0": "rounded-none",
    "2px": "rounded-sm",
    "4px": "rounded",
    "6px": "rounded-md",
    "8px": "rounded-lg",
    "12px": "rounded-xl",
    "16px": "rounded-2xl",
    "24px": "rounded-3xl",
    "9999px": "rounded-full",
    "50%": "rounded-full",
}

def translate_spacing(prefix, val):
    """Translates spacing (margin, padding, height, width) to Tailwind equivalent."""
    clean_val = val.lower().replace(' ', '')
    if clean_val in SPACING_UNITS:
        return f"{prefix}-{SPACING_UNITS[clean_val]}"
    # Fallback to arbitrary value syntax: e.g. p-[15px]
    return f"{prefix}-[{val}]"

def translate_color(prefix, val):
    """Maps common colors or falls back to arbitrary color config."""
    colors = {
        "white": "white",
        "#ffffff": "white",
        "black": "black",
        "#000000": "black",
        "transparent": "transparent",
        "red": "red-500",
        "blue": "blue-500",
        "green": "green-500",
        "gray": "gray-500",
        "grey": "gray-500",
    }
    clean_val = val.lower()
    if clean_val in colors:
        return f"{prefix}-{colors[clean_val]}"
    # Arbitrary value syntax: text-[#ef4444] or bg-[#333]
    # Remove spaces inside value
    val_no_space = val.replace(' ', '')
    return f"{prefix}-[{val_no_space}]"

def translate_declaration(prop, val):
    """Maps an individual CSS declaration to its Tailwind utility equivalent."""
    combined = f"{prop}: {val}"
    
    # Check static mappings
    if combined in STATIC_MAPS:
        return STATIC_MAPS[combined]
        
    # Spacing properties
    if prop == "padding":
        # Check if shorthand (e.g., 10px 20px)
        parts = val.split()
        if len(parts) == 1:
            return translate_spacing("p", val)
        elif len(parts) == 2:
            return f'{translate_spacing("py", parts[0])} {translate_spacing("px", parts[1])}'
        elif len(parts) == 4:
            return f'{translate_spacing("pt", parts[0])} {translate_spacing("pr", parts[1])} {translate_spacing("pb", parts[2])} {translate_spacing("pl", parts[3])}'
            
    if prop == "padding-top": return translate_spacing("pt", val)
    if prop == "padding-bottom": return translate_spacing("pb", val)
    if prop == "padding-left": return translate_spacing("pl", val)
    if prop == "padding-right": return translate_spacing("pr", val)
    
    if prop == "margin":
        parts = val.split()
        if len(parts) == 1:
            return translate_spacing("m", val)
        elif len(parts) == 2:
            return f'{translate_spacing("my", parts[0])} {translate_spacing("mx", parts[1])}'
        elif len(parts) == 4:
            return f'{translate_spacing("mt", parts[0])} {translate_spacing("mr", parts[1])} {translate_spacing("mb", parts[2])} {translate_spacing("ml", parts[3])}'
            
    if prop == "margin-top": return translate_spacing("mt", val)
    if prop == "margin-bottom": return translate_spacing("mb", val)
    if prop == "margin-left": return translate_spacing("ml", val)
    if prop == "margin-right": return translate_spacing("mr", val)
    
    # Dimensions
    if prop == "width":
        if val == "100%": return "w-full"
        if val == "100vw": return "w-screen"
        return translate_spacing("w", val)
    if prop == "height":
        if val == "100%": return "h-full"
        if val == "100vh": return "h-screen"
        return translate_spacing("h", val)
        
    # Colors & Backgrounds
    if prop == "color": return translate_color("text", val)
    if prop == "background-color": return translate_color("bg", val)
    
    # Border radius
    if prop == "border-radius":
        clean_val = val.lower().replace(' ', '')
        if clean_val in RADIUS_MAP:
            return RADIUS_MAP[clean_val]
        return f"rounded-[{clean_val}]"
        
    # Font Sizes
    if prop == "font-size":
        sizes = {
            "12px": "text-xs",
            "14px": "text-sm",
            "16px": "text-base",
            "18px": "text-lg",
            "20px": "text-xl",
            "24px": "text-2xl",
            "30px": "text-3xl",
            "36px": "text-4xl",
            "0.75rem": "text-xs",
            "0.875rem": "text-sm",
            "1rem": "text-base",
            "1.125rem": "text-lg",
            "1.25rem": "text-xl",
            "1.5rem": "text-2xl",
        }
        clean_val = val.lower().replace(' ', '')
        if clean_val in sizes:
            return sizes[clean_val]
        return f"text-[{clean_val}]"

    # Default fallback: Arbitrary Tailwind v3 syntax
    val_no_space = val.replace(' ', '')
    return f"[{prop}:{val_no_space}]"

def parse_css_rules(css_text):
    """Extracts selectors and their property/value pairs from CSS content."""
    # Remove comments
    css_clean = re.sub(r"/\*.*?\*/", "", css_text, flags=re.DOTALL)
    
    # Match blocks: selector { declarations }
    pattern = re.compile(r"([^{]+)\s*\{\s*([^}]+)\s*\}")
    rules = []
    
    for m in pattern.finditer(css_clean):
        selector = m.group(1).strip()
        body = m.group(2).strip()
        
        declarations = []
        # Split declarations by semicolon
        for item in body.split(';'):
            item = item.strip()
            if not item:
                continue
            if ':' in item:
                prop, val = item.split(':', 1)
                declarations.append((prop.strip(), val.strip()))
                
        rules.append((selector, declarations))
        
    return rules

def convert_css_to_tailwind(css_text):
    """Translates CSS rules into Tailwind utility classes."""
    parsed_rules = parse_css_rules(css_text)
    output = []
    
    for selector, decs in parsed_rules:
        classes = []
        for prop, val in decs:
            tw_class = translate_declaration(prop, val)
            # Sourced classes could contain spaces (e.g. from shorthands)
            classes.extend(tw_class.split())
            
        # Deduplicate and sort
        unique_classes = sorted(list(set(classes)))
        output.append((selector, unique_classes))
        
    return output

def main():
    parser = argparse.ArgumentParser(description="CSS to Tailwind Utility Class Converter")
    parser.add_argument("css_file", nargs="?", help="Path to CSS file (if omitted, reads from stdin)")
    parser.add_argument("-o", "--output", help="Save translated utilities report to a text file")
    args = parser.parse_args()

    # Load CSS content
    if args.css_file:
        try:
            with open(args.css_file, 'r', encoding='utf-8') as f:
                css_text = f.read()
        except FileNotFoundError:
            print(f"❌ Error: File not found - {args.css_file}", file=sys.stderr)
            sys.exit(1)
    else:
        # Check if stdin has data
        if not sys.stdin.isatty():
            css_text = sys.stdin.read()
        else:
            print("==============================================")
            print("  CSS to Tailwind Utility Class Converter")
            print("==============================================")
            print("Enter your CSS block below (Press Ctrl+D on empty line to convert):")
            css_text = sys.stdin.read()

    if not css_text.strip():
        print("❌ Error: No CSS content provided.")
        sys.exit(1)

    translated = convert_css_to_tailwind(css_text)
    
    # Build report
    report_lines = []
    report_lines.append("==============================================")
    report_lines.append("  CSS to Tailwind Translation Report")
    report_lines.append("==============================================")
    
    for selector, classes in translated:
        tw_string = " ".join(classes)
        report_lines.append(f"\nCSS Selector: {selector}")
        report_lines.append(f"Tailwind Utility Class List:")
        report_lines.append(f"  class=\"{tw_string}\"")
        
    report = "\n".join(report_lines)
    print(report)

    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"\n💾 Saved translation report to: {args.output}")
        except Exception as e:
            print(f"Error saving to file: {e}", file=sys.stderr)

if __name__ == "__main__":
    main()
