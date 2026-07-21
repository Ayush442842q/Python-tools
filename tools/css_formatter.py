#!/usr/bin/env python3
"""
css_formatter - CSS stylesheet beautifier and minifier

Parses CSS files, stripping comments, formatting braces, and applying custom
indentation, with optional alphabetical property sorting, or compresses CSS
into an ultra-minified block by removing whitespace, comments, and optimizing
color/numeric values.

Usage:
    python tools/css_formatter.py [FILE] [-o OUTPUT] [--minify] [--sort]

Options:
    FILE                CSS file to process (reads from standard input if omitted)
    -o, --output        Output file path (prints to stdout if omitted)
    -m, --minify        Minify the CSS instead of formatting it
    -i, --indent        Number of spaces for indentation (default: 4)
    -s, --sort          Alphabetize declarations/properties within rule blocks
    --no-comments       Strip comments even when formatting (always stripped in minify)

Example:
    python tools/css_formatter.py styles.css -o styles.min.css --minify
"""

import os
import re
import sys
import argparse

# Terminal colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_BOLD = "\033[1m"
COLOR_END = "\033[0m"

class CSSParser:
    def __init__(self, css_text):
        self.raw_css = css_text
        self.comments = []
        
    def preprocess(self):
        """Remove and store comments if we want to preserve them, or strip them."""
        # Find comments and replace them with placeholder
        # For simplicity, we just strip comments
        css = re.sub(r'/\*.*?\*/', '', self.raw_css, flags=re.DOTALL)
        return css

    def parse(self):
        """Parse CSS into structured rules, supporting one level of nested blocks (like @media)."""
        css = self.preprocess()
        
        # We parse by scanning characters
        nodes = []
        stack = []
        current_selector = ""
        current_decls = ""
        
        i = 0
        length = len(css)
        
        while i < length:
            char = css[i]
            
            if char == '{':
                # Open block
                selector = current_selector.strip()
                stack.append((selector, []))
                current_selector = ""
                current_decls = ""
            elif char == '}':
                # Close block
                if stack:
                    selector, children = stack.pop()
                    
                    # Parse declarations in current block
                    decls = self.parse_declarations(current_decls)
                    current_decls = ""
                    
                    rule_node = {
                        "selector": selector,
                        "declarations": decls,
                        "children": children
                    }
                    
                    if stack:
                        # Nested rule (e.g. inside @media)
                        stack[-1][1].append(rule_node)
                    else:
                        nodes.append(rule_node)
                current_selector = ""
            elif char == ';':
                if stack:
                    current_decls += char
                else:
                    # Semicolons outside blocks (e.g. @import)
                    current_selector += char
            else:
                if stack:
                    current_decls += char
                else:
                    current_selector += char
            i += 1
            
        return nodes

    def parse_declarations(self, decl_text):
        """Split declaration text into list of (property, value) pairs."""
        decls = []
        parts = decl_text.split(';')
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if ':' in part:
                prop, val = part.split(':', 1)
                decls.append((prop.strip(), val.strip()))
            else:
                # e.g., filter/fallback rules without standard colons
                decls.append((part.strip(), ""))
        return decls

def minify_css(css_text):
    """Minify CSS using fast, optimized regex patterns."""
    # 1. Remove comments
    css = re.sub(r'/\*.*?\*/', '', css_text, flags=re.DOTALL)
    
    # 2. Remove extra whitespaces
    css = re.sub(r'\s+', ' ', css) # normalize spaces
    css = re.sub(r'\s*([\{\};:,])\s*', r'\1', css) # remove spaces around characters
    
    # 3. Optimize color values (e.g. #ffffff -> #fff, #aabbcc -> #abc)
    css = re.sub(r'#([0-9a-fA-F])\1([0-9a-fA-F])\2([0-9a-fA-F])\3(?=[^a-fA-F0-9]|$)', r'#\1\2\3', css)
    
    # 4. Remove unnecessary units from zero values (e.g. 0px -> 0, 0em -> 0)
    css = re.sub(r'(?<=[:\s])0(?:px|em|rem|%|in|cm|mm|pc|pt|ex|ch|vh|vw|vmin|vmax)', '0', css)
    
    # 5. Remove trailing semicolons in blocks
    css = css.replace(';}', '}')
    
    # 6. Strip leading/trailing whitespace
    return css.strip()

def format_rules(nodes, indent_size=4, sort_properties=False, level=0):
    """Recursively format parsed CSS nodes back to a beautiful string."""
    indent = " " * (indent_size * level)
    child_indent = " " * (indent_size * (level + 1))
    lines = []
    
    for node in nodes:
        selector = node["selector"]
        decls = node["declarations"]
        children = node["children"]
        
        # Sort declarations if requested
        if sort_properties:
            decls = sorted(decls, key=lambda x: x[0].lower())
            
        if children:
            # Group rules like @media
            lines.append(f"\n{indent}{selector} {{")
            child_str = format_rules(children, indent_size, sort_properties, level + 1)
            lines.append(child_str)
            lines.append(f"{indent}}}")
        else:
            # Standard leaf rule
            if not decls:
                lines.append(f"\n{indent}{selector} {{}}")
                continue
                
            lines.append(f"\n{indent}{selector} {{")
            for prop, val in decls:
                if val:
                    lines.append(f"{child_indent}{prop}: {val};")
                else:
                    lines.append(f"{child_indent}{prop};")
            lines.append(f"{indent}}}")
            
    # Combine and trim leading/trailing newlines
    result = "\n".join(lines).strip()
    return result

def main():
    parser = argparse.ArgumentParser(description="Beautify or minify CSS stylesheets with custom indentation and optional sorting.")
    parser.add_argument('file', nargs='?', help='Path to the CSS file (reads from stdin if omitted)')
    parser.add_argument('-o', '--output', type=str, help='Output file path (writes to stdout if omitted)')
    parser.add_argument('-m', '--minify', action='store_true', help='Minify CSS output')
    parser.add_argument('-i', '--indent', type=int, default=4, help='Number of spaces for formatting indent (default: 4)')
    parser.add_argument('-s', '--sort', action='store_true', help='Sort declarations alphabetically by property name')
    
    args = parser.parse_args()

    # Read input CSS
    if args.file:
        if not os.path.exists(args.file):
            print(f"{COLOR_RED}Error: File '{args.file}' not found.{COLOR_END}", file=sys.stderr)
            return 1
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                css_content = f.read()
        except Exception as e:
            print(f"{COLOR_RED}Error reading file: {e}{COLOR_END}", file=sys.stderr)
            return 1
    else:
        if sys.stdin.isatty():
            print(f"{COLOR_YELLOW}Reading CSS from standard input (Ctrl+D to process)...{COLOR_END}", file=sys.stderr)
        css_content = sys.stdin.read()

    if not css_content.strip():
        print(f"{COLOR_YELLOW}Warning: Empty CSS content.{COLOR_END}", file=sys.stderr)
        return 0

    try:
        # Perform action
        if args.minify:
            output_css = minify_css(css_content)
        else:
            parser = CSSParser(css_content)
            nodes = parser.parse()
            output_css = format_rules(nodes, indent_size=args.indent, sort_properties=args.sort)

        # Write output
        if args.output:
            write_mode = 'w'
            with open(args.output, write_mode, encoding='utf-8') as f:
                f.write(output_css)
                # Ensure a trailing newline for non-minified files
                if not args.minify:
                    f.write('\n')
            
            # Print stats
            orig_size = len(css_content)
            new_size = len(output_css)
            diff = orig_size - new_size
            pct = (diff / orig_size) * 100 if orig_size > 0 else 0
            
            print(f"\n{COLOR_GREEN}{COLOR_BOLD}CSS processing complete!{COLOR_END}")
            print(f"  Output saved to: {COLOR_YELLOW}{args.output}{COLOR_END}")
            print(f"  Original Size:   {orig_size} bytes")
            print(f"  Processed Size:  {new_size} bytes")
            if args.minify:
                print(f"  Size Reduction:  {diff} bytes ({pct:.1f}%)")
        else:
            # Print to stdout
            print(output_css)

    except Exception as e:
        print(f"{COLOR_RED}Error processing CSS: {e}{COLOR_END}", file=sys.stderr)
        import traceback
        traceback.print_exc(file=sys.stderr)
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
