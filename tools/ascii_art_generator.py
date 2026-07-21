#!/usr/bin/env python3
"""
ASCII Art Generator - A utility to generate text banners in various ASCII styles.
Comes with built-in fonts (Block, Slant, Thin) and options for border styling.
"""

import argparse
import sys

# Built-in font definitions (5 lines tall)
FONTS = {
    'block': {
        'A': ["  ███  ", " ██ ██ ", "██   ██", "███████", "██   ██"],
        'B': ["██████ ", "██   ██", "██████ ", "██   ██", "██████ "],
        'C': [" █████ ", "██    ", "██    ", "██    ", " █████ "],
        'D': ["██████ ", "██   ██", "██   ██", "██   ██", "██████ "],
        'E': ["███████", "██     ", "█████  ", "██     ", "███████"],
        'F': ["███████", "██     ", "█████  ", "██     ", "██     "],
        'G': [" █████ ", "██     ", "██  ███", "██   ██", " █████ "],
        'H': ["██   ██", "██   ██", "███████", "██   ██", "██   ██"],
        'I': ["█████", "  ██ ", "  ██ ", "  ██ ", "█████"],
        'J': ["  ████", "    ██", "    ██", "██  ██", " ████ "],
        'K': ["██  ██ ", "██ ██  ", "████   ", "██ ██  ", "██  ██ "],
        'L': ["██     ", "██     ", "██     ", "██     ", "███████"],
        'M': ["██   ██", "███ ███", "██ █ ██", "██   ██", "██   ██"],
        'N': ["██   ██", "████  ██", "██ ██ ██", "██  ████", "██   ██"],
        'O': [" █████ ", "██   ██", "██   ██", "██   ██", " █████ "],
        'P': ["██████ ", "██   ██", "██████ ", "██     ", "██     "],
        'Q': [" █████ ", "██   ██", "██   ██", "██  ███", " ██████"],
        'R': ["██████ ", "██   ██", "██████ ", "██   ██", "██   ██"],
        'S': [" █████ ", "██     ", " █████ ", "    ██ ", "█████  "],
        'T': ["███████", "  ██   ", "  ██   ", "  ██   ", "  ██   "],
        'U': ["██   ██", "██   ██", "██   ██", "██   ██", " █████ "],
        'V': ["██   ██", "██   ██", " ██ ██ ", " ██ ██ ", "  ███  "],
        'W': ["██   ██", "██   ██", "██ █ ██", "███████", "██   ██"],
        'X': ["██   ██", " ██ ██ ", "  ███  ", " ██ ██ ", "██   ██"],
        'Y': ["██   ██", " ██ ██ ", "  ███  ", "  ██   ", "  ██   "],
        'Z': ["███████", "   ██  ", "  ██   ", " ██    ", "███████"],
        ' ': ["   ", "   ", "   ", "   ", "   "],
        '?': [" ████  ", "    ██ ", "  ███  ", "       ", "  ██   "],
        '!': [" ██ ", " ██ ", " ██ ", "    ", " ██ "],
        '-': ["      ", "      ", "██████", "      ", "      "],
        '+': ["      ", "  ██  ", "██████", "  ██  ", "      "],
        '.': ["  ", "  ", "  ", "  ", "██"]
    },
    'slant': {
        'A': ["   /|   ", "  / |   ", " /__|   ", "/   |   ", "        "],
        'B': [" ___    ", "|   )   ", "|==<    ", "|___)   ", "        "],
        'C': ["  ___   ", " /      ", "|       ", " \\___   ", "        "],
        'D': [" ___    ", "|   \\   ", "|    |  ", "|___/   ", "        "],
        'E': [" ___   ", "|__    ", "|      ", "|___   ", "       "],
        'F': [" ___   ", "|__    ", "|      ", "|      ", "       "],
        'G': ["  ___   ", " /  _   ", "|  |_|  ", " \\___|  ", "        "],
        'H': [" _   _  ", "| | | | ", "|==| |  ", "| | |_| ", "        "],
        'I': [" ___ ", "  |  ", "  |  ", " _|_ ", "     "],
        'J': ["   _ ", "  | |", "  | |", "\\_| |", "     "],
        'K': [" _  _  ", "| |/ / ", "|  <   ", "| |\\ \\ ", "       "],
        'L': [" _     ", "| |    ", "| |    ", "|____  ", "       "],
        'M': [" _   _ ", "| \\_/ |", "| | | |", "|_| |_|", "       "],
        'N': [" _   _ ", "| \\ | |", "|  \\| |", "|_| \\_|", "       "],
        'O': ["  ___   ", " /   \\  ", "|     | ", " \\___/  ", "        "],
        'P': [" ___   ", "|   )  ", "|__/   ", "|      ", "       "],
        'Q': ["  ___   ", " /   \\  ", "|   \\|  ", " \\___\\\\ ", "        "],
        'R': [" ___   ", "|   )  ", "|__/   ", "|  \\   ", "       "],
        'S': ["  ___  ", " /___  ", "  ___| ", " \\___| ", "       "],
        'T': [" ___ ", "  |  ", "  |  ", "  |  ", "     "],
        'U': [" _   _  ", "| | | | ", "| | | | ", " \\___/  ", "        "],
        'V': [" _   _ ", "| | | |", " | | | ", "  \\_/  ", "       "],
        'W': [" _ _ _ ", "| | | |", "| | | |", " \\_^_/ ", "       "],
        'X': [" _   _ ", " \\_/ / ", " / \\_  ", "/_/ \\_\\", "       "],
        'Y': [" _   _ ", " \\_/ / ", "  | |  ", "  |_|  ", "       "],
        'Z': [" ___  ", "   /  ", "  /   ", " /___ ", "      "],
        ' ': ["   ", "   ", "   ", "   ", "   "],
        '?': [" ___  ", "    ) ", "   /  ", "  o   ", "      "],
        '!': [" _ ", "| |", "| |", " o ", "   "],
        '-': ["    ", "    ", "____", "    ", "    "],
        '+': ["    ", " _  ", "|+| ", "    ", "    "],
        '.': ["  ", "  ", "  ", "  ", " o"]
    },
    'thin': {
        'A': [" /\\ ", "/--\\", "/  \\", "    ", "    "],
        'B': ["|-) ", "|-) ", "|-  ", "    ", "    "],
        'C': ["(-- ", "(   ", "(-- ", "    ", "    "],
        'D': ["|-) ", "|  )", "|-/ ", "    ", "    "],
        'E': ["|-- ", "|-  ", "|-- ", "    ", "    "],
        'F': ["|-- ", "|-  ", "|   ", "    ", "    "],
        'G': ["(-- ", "| - ", "(--|", "    ", "    "],
        'H': ["|  |", "|--|", "|  |", "    ", "    "],
        'I': [" | ", " | ", " | ", "   ", "   "],
        'J': ["  |", "  |", "\\-|", "   ", "   "],
        'K': ["| /", "|< ", "| \\", "   ", "   "],
        'L': ["|  ", "|  ", "|__", "   ", "   "],
        'M': ["|\\/|", "|  |", "|  |", "   ", "   "],
        'N': ["|\\ |", "| \\|", "|  |", "   ", "   "],
        'O': ["(--)", "(  )", "(--)", "    ", "    "],
        'P': ["|-) ", "|`  ", "|   ", "    ", "    "],
        'Q': ["(--)", "(  )", "(--\\", "    ", "    "],
        'R': ["|-) ", "| \\ ", "|  \\", "    ", "    "],
        'S': ["(-- ", " -) ", "(-- ", "    ", "    "],
        'T': ["---", " | ", " | ", "   ", "   "],
        'U': ["|  |", "|  |", "\\--/", "    ", "    "],
        'V': ["\\  /", " \\/ ", "    ", "    ", "    "],
        'W': ["|  |", "|/\\|", "|  |", "    ", "    "],
        'X': ["\\ /", " X ", "/ \\", "   ", "   "],
        'Y': ["\\ /", " | ", " | ", "   ", "   "],
        'Z': ["--/", " / ", "/__", "   ", "   "],
        ' ': ["  ", "  ", "  ", "  ", "  "],
        '?': [" - ", "  ?", "  .", "   ", "   "],
        '!': [" | ", " | ", " . ", "   ", "   "],
        '-': ["   ", "---", "   ", "   ", "   "],
        '+': [" | ", "-+-", " | ", "   ", "   "],
        '.': [" ", " ", ".", " ", " "]
    }
}

def generate_ascii(text, font_style='block', border=False):
    """Generate ASCII art list of lines from text."""
    font = FONTS.get(font_style, FONTS['block'])
    text = text.upper()
    
    # Initialize empty canvas of 5 lines
    canvas = [""] * 5
    
    for char in text:
        if char in font:
            char_lines = font[char]
        else:
            # Fallback for unknown characters (just space/box)
            char_lines = [" █ ", " █ ", " █ ", "   ", " █ "] if font_style == 'block' else [" | ", " | ", " | ", "   ", " | "]
            
        for i in range(5):
            canvas[i] += char_lines[i] + (" " if font_style != 'thin' else "")

    if border:
        width = len(canvas[0])
        border_char = "*" if font_style != 'block' else "█"
        top_bottom = border_char * (width + 4)
        bordered_canvas = [top_bottom]
        bordered_canvas.append(f"{border_char} {' ' * width} {border_char}")
        for line in canvas:
            bordered_canvas.append(f"{border_char} {line} {border_char}")
        bordered_canvas.append(f"{border_char} {' ' * width} {border_char}")
        bordered_canvas.append(top_bottom)
        return "\n".join(bordered_canvas)
        
    return "\n".join(canvas)

def main():
    parser = argparse.ArgumentParser(
        description="ASCII Art Generator - Create terminal text banners in various font styles."
    )
    parser.add_argument("text", nargs="?", help="Text string to convert into ASCII banner")
    parser.add_argument("-t", "--text-arg", dest="text_arg", help="The text string to convert")
    parser.add_argument("-f", "--font", choices=['block', 'slant', 'thin'], default='block', help="Font style (default: block)")
    parser.add_argument("-b", "--border", action="store_true", help="Add a border around the generated banner")
    parser.add_argument("-o", "--output", help="Output file path to save the banner")

    args = parser.parse_args()

    text = args.text_arg or args.text
    if not text:
        print("ASCII Art Generator")
        print("Usage: python ascii_art_generator.py <TEXT> [-f FONT] [-b]")
        print("Fonts: block, slant, thin")
        return 1

    banner = generate_ascii(text, font_style=args.font, border=args.border)
    print(banner)

    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(banner + '\n')
            print(f"\n[+] ASCII Art saved to: {args.output}")
        except Exception as e:
            print(f"Error saving file: {e}", file=sys.stderr)
            return 1
            
    return 0

if __name__ == "__main__":
    sys.exit(main())
