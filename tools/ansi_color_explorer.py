#!/usr/bin/env python3
"""
ANSI Color Explorer & Terminal Capability Tester
A utility to explore terminal color support (16-color, 256-color, TrueColor/24-bit),
verify contrast compatibility, and generate copy-pasteable ANSI escape sequences.
"""

import os
import sys
import argparse

# Enable ANSI escape sequences on Windows if possible
if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        stdout_handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_ulong()
        if kernel32.GetConsoleMode(stdout_handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(stdout_handle, mode.value | 0x0004)  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
    except Exception:
        pass

# Configure stdout/stderr encoding to UTF-8 to prevent charmap errors on Windows console redirection
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        try:
            stream.reconfigure(encoding='utf-8')
        except Exception:
            pass


# ANSI escape sequence helpers
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
ITALIC = "\033[3m"
UNDERLINE = "\033[4m"
BLINK = "\033[5m"
REVERSE = "\033[7m"
STRIKETHROUGH = "\033[9m"

def is_truecolor_supported():
    """Checks if the terminal supports TrueColor (24-bit)."""
    colorterm = os.environ.get("COLORTERM", "").lower()
    term = os.environ.get("TERM", "").lower()
    return "truecolor" in colorterm or "24bit" in colorterm or "direct" in term

def hex_to_rgb(hex_str):
    """Converts hex color string to RGB tuple."""
    hex_str = hex_str.lstrip("#")
    if len(hex_str) == 3:
        hex_str = "".join(c * 2 for c in hex_str)
    if len(hex_str) != 6:
        raise ValueError("Invalid hex color format. Use #RRGGBB or RRGGBB.")
    return tuple(int(hex_str[i:i+2], 16) for i in (0, 2, 4))

def get_ansi_fg_truecolor(r, g, b):
    return f"\033[38;2;{r};{g};{b}m"

def get_ansi_bg_truecolor(r, g, b):
    return f"\033[48;2;{r};{g};{b}m"

def get_ansi_fg_256(code):
    return f"\033[38;5;{code}m"

def get_ansi_bg_256(code):
    return f"\033[48;5;{code}m"

def print_header(title):
    print(f"\n{BOLD}{UNDERLINE}{title}{RESET}\n")

def show_compatibility():
    """Prints terminal capability summary."""
    print_header("Terminal Capabilities")
    colorterm = os.environ.get("COLORTERM", "Not Set")
    term = os.environ.get("TERM", "Not Set")
    truecolor = is_truecolor_supported()
    
    print(f"  {BOLD}COLORTERM:{RESET} {colorterm}")
    print(f"  {BOLD}TERM:{RESET}      {term}")
    print(f"  {BOLD}Platform:{RESET}  {sys.platform}")
    
    status_str = f"\033[32mSupported (COLORTERM contains 'truecolor')\033[0m" if truecolor else "\033[33mNot officially declared (falling back to standard checking)\033[0m"
    print(f"  {BOLD}TrueColor (24-bit):{RESET} {status_str}")
    
    # Try a quick visual verification
    print(f"  {BOLD}TrueColor Test Pattern:{RESET} ", end="")
    for i in range(20):
        # Gradient from blue to red
        r = int(i * (255 / 19))
        b = 255 - r
        sys.stdout.write(f"{get_ansi_bg_truecolor(r, 0, b)} {RESET}")
    print(" (Should show smooth blue -> red transition if supported)")

def show_16_colors():
    """Displays standard 16 ANSI colors (foreground and background)."""
    print_header("Standard 16-Color Palette")
    
    names = ["Black", "Red", "Green", "Yellow", "Blue", "Magenta", "Cyan", "White"]
    
    print(f"  {BOLD}{'Color':<10} {'Standard FG':<15} {'Bright FG':<15} {'Standard BG':<15} {'Bright BG':<15}{RESET}")
    
    for i in range(8):
        fg_std = f"\033[3{i}m"
        fg_brt = f"\033[9{i}m"
        bg_std = f"\033[4{i}m"
        bg_brt = f"\033[10{i}m"
        
        std_fg_text = f"{fg_std}ColorText{RESET}"
        brt_fg_text = f"{fg_brt}ColorText{RESET}"
        std_bg_text = f"{bg_std}  Text  {RESET}"
        brt_bg_text = f"{bg_brt}  Text  {RESET}"
        
        print(f"  {BOLD}{names[i]:<10}{RESET} {std_fg_text:<15} {brt_fg_text:<15} {std_bg_text:<15} {brt_bg_text:<15}")

def show_256_colors():
    """Displays 256-color palette (color cube and grayscale)."""
    print_header("256-Color Palette")
    
    # System colors 0-15
    print(f"  {BOLD}System Colors (0-15):{RESET}")
    for i in range(16):
        sys.stdout.write(f"{get_ansi_bg_256(i)} {i:02d} {RESET} ")
        if (i + 1) % 8 == 0:
            print()
    print()
    
    # 6x6x6 color cube (16-231)
    print(f"  {BOLD}Color Cube (16-231):{RESET}")
    for r in range(6):
        for g in range(6):
            for b in range(6):
                code = 16 + 36 * r + 6 * g + b
                sys.stdout.write(f"{get_ansi_bg_256(code)}\033[30m{code:03d}{RESET} ")
            sys.stdout.write(" ")
        print()
    print()
    
    # Grayscale ramp (232-255)
    print(f"  {BOLD}Grayscale Ramp (232-255):{RESET}")
    for code in range(232, 256):
        # Use white text for dark backgrounds, black text for light ones
        fg = "\033[30m" if code > 244 else "\033[37m"
        sys.stdout.write(f"{get_ansi_bg_256(code)}{fg}{code:03d}{RESET} ")
    print("\n")

def show_truecolor_gradients():
    """Displays smooth RGB gradients demonstrating TrueColor support."""
    print_header("TrueColor (24-bit) Gradients")
    
    width = 60
    
    # Red-Green-Blue gradient
    print("  RGB Spectrum:")
    sys.stdout.write("  ")
    for i in range(width):
        pos = i / width
        if pos < 0.5:
            r = int((1 - (pos * 2)) * 255)
            g = int((pos * 2) * 255)
            b = 0
        else:
            r = 0
            g = int((1 - ((pos - 0.5) * 2)) * 255)
            b = int(((pos - 0.5) * 2) * 255)
        sys.stdout.write(f"{get_ansi_bg_truecolor(r, g, b)} {RESET}")
    print()
    
    # Grayscale smooth gradient
    print("\n  Grayscale Gradient:")
    sys.stdout.write("  ")
    for i in range(width):
        val = int((i / width) * 255)
        sys.stdout.write(f"{get_ansi_bg_truecolor(val, val, val)} {RESET}")
    print()
    
    # Custom vibrant palettes
    print("\n  Sunset Gradient:")
    sys.stdout.write("  ")
    for i in range(width):
        pos = i / width
        r = 255
        g = int(pos * 128)
        b = int(pos * 255)
        sys.stdout.write(f"{get_ansi_bg_truecolor(r, g, b)} {RESET}")
    print("\n")

def show_styles():
    """Shows text styling formats."""
    print_header("ANSI Formatting Styles")
    styles = [
        ("Normal", RESET),
        ("Bold", BOLD),
        ("Dim/Faint", DIM),
        ("Italic", ITALIC),
        ("Underline", UNDERLINE),
        ("Blink", BLINK),
        ("Reverse Video", REVERSE),
        ("Strikethrough", STRIKETHROUGH),
    ]
    for name, code in styles:
        print(f"  {BOLD}{name:<15}{RESET} -> {code}Sample Text{RESET}")

def generate_snippets(color_val):
    """Generates ANSI escape sequences for a hex or RGB color."""
    print_header(f"Code Generation for: {color_val}")
    
    try:
        if color_val.startswith("#") or len(color_val) == 6 or len(color_val) == 3:
            r, g, b = hex_to_rgb(color_val)
        else:
            parts = [int(p.strip()) for p in color_val.split(",")]
            if len(parts) != 3:
                raise ValueError
            r, g, b = parts
            if not all(0 <= val <= 255 for val in (r, g, b)):
                raise ValueError("RGB components must be between 0 and 255.")
    except Exception:
        print(f"\033[31mError: Could not parse '{color_val}' as HEX (#RRGGBB) or RGB (R,G,B).\033[0m")
        return

    hex_str = f"#{r:02x}{g:02x}{b:02x}"
    print(f"  {BOLD}Color Details:{RESET}")
    print(f"    HEX: {hex_str}")
    print(f"    RGB: ({r}, {g}, {b})")
    print(f"    Preview: {get_ansi_bg_truecolor(r, g, b)}     {RESET} (Foreground: {get_ansi_fg_truecolor(r, g, b)}Sample Text{RESET})\n")

    # Generate Python standard library
    py_fg = f"f'\\033[38;2;{r};{g};{b}m'"
    py_bg = f"f'\\033[48;2;{r};{g};{b}m'"
    py_rst = "'\\033[0m'"
    
    print(f"  {BOLD}Python Snippet:{RESET}")
    print(f"    FG = {py_fg}")
    print(f"    BG = {py_bg}")
    print(f"    RESET = {py_rst}")
    print(f"    print(f\"{{FG}}Hello World{{RESET}}\")")
    print()

    # Generate Bash
    print(f"  {BOLD}Bash Snippet:{RESET}")
    print(f"    FG=\"\\e[38;2;{r};{g};{b}m\"")
    print(f"    BG=\"\\e[48;2;{r};{g};{b}m\"")
    print(f"    RESET=\"\\e[0m\"")
    print(f"    echo -e \"${{FG}}Hello World${{RESET}}\"")
    print()
    
    # Generate HTML/CSS equivalent
    print(f"  {BOLD}CSS Equivalent:{RESET}")
    print(f"    color: rgb({r}, {g}, {b});")
    print(f"    background-color: rgb({r}, {g}, {b});")

def main():
    parser = argparse.ArgumentParser(
        description="ANSI Color Explorer: Test terminal colors, formatting, and generate escapes.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/ansi_color_explorer.py --test
  python tools/ansi_color_explorer.py --palette 256
  python tools/ansi_color_explorer.py --generate #ffaa00
  python tools/ansi_color_explorer.py --generate 128,0,255
"""
    )
    parser.add_argument("--test", "-t", action="store_true", help="Check terminal capabilities and print system info")
    parser.add_argument("--palette", "-p", choices=["16", "256", "truecolor", "all"], default="all",
                        help="Display the specified color palette (default: all)")
    parser.add_argument("--styles", "-s", action="store_true", help="Show text styles (Bold, Underline, etc.)")
    parser.add_argument("--generate", "-g", metavar="COLOR", help="Generate code snippets for HEX (#RRGGBB) or RGB (R,G,B) color")

    args = parser.parse_args()

    # If no flags are passed, default to showing the compatibility summary and styles
    if not any([args.test, args.styles, args.generate]) and len(sys.argv) == 1:
        show_compatibility()
        show_styles()
        print("\nUse --help to see more visual display options.")
        return

    if args.test:
        show_compatibility()

    if args.generate:
        generate_snippets(args.generate)
        return

    if args.styles:
        show_styles()

    if args.palette == "16" or args.palette == "all":
        show_16_colors()
    if args.palette == "256" or args.palette == "all":
        show_256_colors()
    if args.palette == "truecolor" or args.palette == "all":
        show_truecolor_gradients()

if __name__ == "__main__":
    main()
