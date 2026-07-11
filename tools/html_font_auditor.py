#!/usr/bin/env python3
"""
HTML & CSS Font Usage Auditor
Recursively scans HTML and CSS files to analyze font-family declarations,
checking for generic fallbacks, unused web font links, and undeclared custom fonts.
"""

import os
import re
import sys
import argparse

# Standard generic CSS font fallbacks
GENERIC_FALLBACKS = {
    'serif', 'sans-serif', 'monospace', 'cursive', 'fantasy', 
    'system-ui', 'ui-serif', 'ui-sans-serif', 'ui-monospace', 'ui-rounded',
    'emoji', 'math', 'fangsong'
}

# Regex definitions
FONT_FAMILY_REGEX = re.compile(r'font-family\s*:\s*([^;!}]+)', re.IGNORECASE)
LINK_FONT_REGEX = re.compile(r'<link[^>]+href=["\']([^"\']*(?:fonts\.googleapis\.com|use\.typekit\.net|api\.fontshare\.com)[^"\']*)["\']', re.IGNORECASE)
IMPORT_FONT_REGEX = re.compile(r'@import\s+(?:url\()?["\']([^"\']*(?:fonts\.googleapis\.com|use\.typekit\.net|api\.fontshare\.com)[^"\']*)["\']\)?', re.IGNORECASE)
FONT_FACE_REGEX = re.compile(r'@font-face\s*\{([^}]+)\}', re.IGNORECASE)

def parse_font_family_value(val):
    """Parse font-family value string into a list of individual font names."""
    # Split by comma but ignore commas inside quotes
    fonts = []
    current = []
    in_quotes = False
    quote_char = None
    
    for char in val:
        if char in ("'", '"'):
            if not in_quotes:
                in_quotes = True
                quote_char = char
            elif char == quote_char:
                in_quotes = False
                quote_char = None
            current.append(char)
        elif char == ',' and not in_quotes:
            fonts.append("".join(current).strip())
            current = []
        else:
            current.append(char)
            
    if current:
        fonts.append("".join(current).strip())
        
    # Clean quotes
    cleaned_fonts = []
    for f in fonts:
        if (f.startswith("'") and f.endswith("'")) or (f.startswith('"') and f.endswith('"')):
            cleaned_fonts.append(f[1:-1].strip())
        else:
            cleaned_fonts.append(f)
    return cleaned_fonts

def audit_files(directory):
    """Audit font usage in all HTML and CSS files under target directory."""
    html_files = []
    css_files = []
    
    for root, _, files in os.walk(directory):
        for f in files:
            path = os.path.join(root, f)
            if f.endswith(('.html', '.htm')):
                html_files.append(path)
            elif f.endswith('.css'):
                css_files.append(path)

    print(f"Scanning: {os.path.abspath(directory)}")
    print(f"Found {len(html_files)} HTML files and {len(css_files)} CSS files.")
    print("=" * 60)

    used_font_families = {}     # font_name -> list of (file, line_num, full_decl)
    declared_font_faces = {}    # font_name -> list of files
    external_font_links = {}    # url -> list of files
    
    # Process CSS files
    for path in css_files:
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                
            # Find @font-face declarations
            for match in FONT_FACE_REGEX.finditer(content):
                block = match.group(1)
                family_match = re.search(r'font-family\s*:\s*["\']?([^;\'"\s}]+)["\']?', block, re.IGNORECASE)
                if family_match:
                    family_name = family_match.group(1).strip()
                    if family_name not in declared_font_faces:
                        declared_font_faces[family_name] = []
                    declared_font_faces[family_name].append(path)

            # Find imports
            for match in IMPORT_FONT_REGEX.finditer(content):
                url = match.group(1)
                if url not in external_font_links:
                    external_font_links[url] = []
                external_font_links[url].append(path)

            # Process line by line for font-family usage
            lines = content.splitlines()
            for idx, line in enumerate(lines, 1):
                for match in FONT_FAMILY_REGEX.finditer(line):
                    decl = match.group(0).strip()
                    val = match.group(1).strip()
                    fonts = parse_font_family_value(val)
                    if fonts:
                        for font in fonts:
                            # Skip if generic fallback
                            if font.lower() in GENERIC_FALLBACKS:
                                continue
                            if font not in used_font_families:
                                used_font_families[font] = []
                            used_font_families[font].append((path, idx, decl))
        except Exception as e:
            print(f"Error parsing CSS file {path}: {e}")

    # Process HTML files
    for path in html_files:
        try:
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.read().splitlines()
                
            content_full = "\n".join(lines)
            
            # Find external link imports
            for match in LINK_FONT_REGEX.finditer(content_full):
                url = match.group(1)
                if url not in external_font_links:
                    external_font_links[url] = []
                external_font_links[url].append(path)

            # Process line by line for font-family usage in style attributes
            for idx, line in enumerate(lines, 1):
                for match in FONT_FAMILY_REGEX.finditer(line):
                    decl = match.group(0).strip()
                    val = match.group(1).strip()
                    # Clean up if matched inside html attributes (e.g. style="font-family: 'Arial';")
                    val = val.split('"')[0].split("'")[0].strip()
                    fonts = parse_font_family_value(val)
                    if fonts:
                        for font in fonts:
                            if font.lower() in GENERIC_FALLBACKS:
                                continue
                            if font not in used_font_families:
                                used_font_families[font] = []
                            used_font_families[font].append((path, idx, decl))
        except Exception as e:
            print(f"Error parsing HTML file {path}: {e}")

    # Analysis & Reports
    print("\n--- Used Font Families & Fallbacks ---")
    missing_fallbacks = []
    for font, occurrences in used_font_families.items():
        print(f"• '{font}' used {len(occurrences)} time(s)")
        
        # Check occurrences for lack of generic fallbacks
        for file, line, decl in occurrences:
            val = decl.split(':', 1)[1].strip()
            fonts_in_decl = [f.lower() for f in parse_font_family_value(val)]
            has_fallback = any(fb in fonts_in_decl for fb in GENERIC_FALLBACKS)
            if not has_fallback:
                missing_fallbacks.append((file, line, decl))

    if missing_fallbacks:
        print(f"\n✗ Found {len(missing_fallbacks)} font-family declarations missing a generic fallback:")
        for file, line, decl in missing_fallbacks[:15]:
            print(f"  • {os.path.basename(file)}:L{line} -> '{decl}' (Should end with a generic like sans-serif, serif, or monospace)")
        if len(missing_fallbacks) > 15:
            print(f"  ... and {len(missing_fallbacks) - 15} more.")
    else:
        print("✓ All font-family declarations have proper generic fallback fonts.")

    print("\n--- External Fonts & Imports ---")
    if external_font_links:
        print(f"Found {len(external_font_links)} external web font link(s)/import(s):")
        for url, files in external_font_links.items():
            print(f"  • URL: {url}")
            print(f"    Loaded in: {', '.join(os.path.basename(f) for f in files)}")
    else:
        print("No external web font imports/links found.")

    print("\n--- Declared Custom Fonts (@font-face) ---")
    if declared_font_faces:
        for family, files in declared_font_faces.items():
            print(f"  • @font-face '{family}' declared in: {', '.join(os.path.basename(f) for f in files)}")
    else:
        print("No local @font-face declarations found.")

    # Cross-reference used vs declared/imported
    print("\n--- Font Match & Integrity Check ---")
    web_font_families_hinted = set()
    for url in external_font_links:
        # Extract family names from google font urls, e.g., family=Roboto:wght@400;700 or family=Open+Sans
        families = re.findall(r'family=([^&:\s#]+)', url)
        for fam in families:
            names = fam.replace('+', ' ').split('|')
            for name in names:
                web_font_families_hinted.add(name.split(':')[0].strip().lower())

    declared_families_lower = {f.lower() for f in declared_font_faces}
    
    # Common system standard fonts we don't need to import
    common_system_fonts = {
        'arial', 'helvetica', 'times new roman', 'times', 'courier new', 'courier',
        'georgia', 'palatino', 'garamond', 'bookman', 'comic sans ms', 'trebuchet ms',
        'arial black', 'impact', 'verdana', 'tahoma', 'segoe ui', 'system-ui', 'blinkmacsystemfont',
        'pingfang sc', 'hiragino sans gb', 'microsoft yahei', 'consolas', 'menlo', 'monaco'
    }

    undeclared_usages = []
    for font in used_font_families:
        font_l = font.lower()
        if font_l not in common_system_fonts and font_l not in declared_families_lower and font_l not in web_font_families_hinted:
            undeclared_usages.append(font)

    if undeclared_usages:
        print("✗ The following fonts are used but not locally defined or imported from web services:")
        for font in undeclared_usages:
            first_occ = used_font_families[font][0]
            print(f"  • '{font}' (First used in {os.path.basename(first_occ[0])}:L{first_occ[1]})")
        print("  (Make sure you declare them via @font-face or load them via <link>/@import!)")
    else:
        print("✓ All custom/web fonts used are properly imported or declared.")

    print("=" * 60)
    return len(missing_fallbacks) == 0 and len(undeclared_usages) == 0

def main():
    parser = argparse.ArgumentParser(description="HTML & CSS Font Usage Auditor")
    parser.add_argument("dir", nargs="?", default=".", help="Directory to scan (default: current directory)")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.dir):
        print(f"Error: Directory '{args.dir}' does not exist.")
        sys.exit(1)
        
    success = audit_files(args.dir)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
