#!/usr/bin/env python3
"""
banner - Print an ASCII banner with optional color

Usage:
    python tools/banner.py  [--color COLOR] [MESSAGE]

Colors: red, green, yellow, blue, magenta, cyan, white

Example:
    python tools/banner.py --color cyan "Hello World"
"""

import argparse, sys

COLORS = {
    'black': '\033[30m',
    'red': '\033[31m',
    'green': '\033[32m',
    'yellow': '\033[33m',
    'blue': '\033[34m',
    'magenta': '\033[35m',
    'cyan': '\033[36m',
    'white': '\033[37m',
}

RESET = '\033[0m'

def main():
    parser = argparse.ArgumentParser(description='Print ascii banner with optional color')
    parser.add_argument('--color', choices=COLORS.keys(), help='ANSI color')
    parser.add_argument('message', nargs='*', default=['Hello'], help='Text to display')
    args = parser.parse_args()
    text = ' '.join(args.message)
    color = COLORS.get(args.color, '')
    banner = (color + text + RESET) if color else text
    print(banner)
    return 0

if __name__ == '__main__':
    sys.exit(main())
