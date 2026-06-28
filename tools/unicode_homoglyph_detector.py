#!/usr/bin/env python3
"""
Unicode Homoglyph Security Detector - Scan text, domain names, or source code files
for homograph attacks, mixed-script token confusion, invisible characters,
and bidirectional overrides.
"""

import os
import sys
import re
import argparse
import unicodedata
from pathlib import Path

def get_color(color_name):
    """Return ANSI escape code for terminal color if supported."""
    colors = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'magenta': '\033[95m',
        'bold': '\033[1m',
        'reset': '\033[0m'
    }
    if sys.platform == 'win32':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            return ''
    return colors.get(color_name, '')

# Common confusable characters map (Unicode -> ASCII representation)
CONFUSABLES_MAP = {
    # Cyrillic small
    '\u0430': 'a', '\u0435': 'e', '\u043e': 'o', '\u0440': 'p', '\u0441': 'c', 
    '\u0443': 'y', '\u0445': 'x', '\u0456': 'i', '\u0455': 's', '\u0458': 'j',
    '\u045e': 'u', '\u04cf': 'l', '\u0501': 'd', '\u051d': 'w',
    # Cyrillic capital
    '\u0410': 'A', '\u0412': 'B', '\u0421': 'C', '\u0415': 'E', '\u041d': 'H',
    '\u0406': 'I', '\u0408': 'J', '\u041a': 'K', '\u041c': 'M', '\u041e': 'O',
    '\u0420': 'P', '\u0422': 'T', '\u0425': 'X', '\u04ae': 'Y', '\u0405': 'S',
    # Greek small
    '\u03bf': 'o', '\u03bd': 'v', '\u03ba': 'k', '\u03c4': 't', '\u03c5': 'u',
    '\u03c7': 'x', '\u03b1': 'a', '\u03b2': 'b', '\u03b5': 'e', '\u03b9': 'i',
    '\u03ba': 'k', '\u03bc': 'u', '\u03c1': 'p',
    # Greek capital
    '\u0391': 'A', '\u0392': 'B', '\u0395': 'E', '\u0396': 'Z', '\u0397': 'H',
    '\u0399': 'I', '\u039a': 'K', '\u039c': 'M', '\u039d': 'N', '\u039f': 'O',
    '\u03a1': 'P', '\u03a4': 'T', '\u03a5': 'Y', '\u03a7': 'X',
    # Other lookalikes
    '\u2010': '-', '\u2013': '-', '\u2212': '-', 
    '\u00a0': ' ', '\u2002': ' ', '\u2003': ' ', '\u2009': ' '
}

# Invisible / Zero-Width characters
INVISIBLE_CHARS = {
    '\u200b': 'Zero-Width Space',
    '\u200c': 'Zero-Width Non-Joiner',
    '\u200d': 'Zero-Width Joiner',
    '\u200e': 'Left-to-Right Mark',
    '\u200f': 'Right-to-Left Mark',
    '\u202a': 'Left-to-Right Embedding',
    '\u202b': 'Right-to-Left Embedding',
    '\u202c': 'Pop Directional Formatting',
    '\u202d': 'Left-to-Right Override (Bidi Risk)',
    '\u202e': 'Right-to-Left Override (Bidi Risk)',
    '\ufeff': 'Byte Order Mark / Zero-Width No-Break Space'
}

def analyze_word(word):
    """Analyze a single word/token for mixed scripts or confusable letters."""
    scripts = set()
    has_lookalikes = False
    lookalike_details = []
    
    for char in word:
        char_ord = ord(char)
        if char_ord <= 127:
            scripts.add("Latin-ASCII")
            continue
            
        # Detect if it's in our lookalike map
        if char in CONFUSABLES_MAP:
            has_lookalikes = True
            try:
                name = unicodedata.name(char)
            except ValueError:
                name = "UNKNOWN CHARACTER"
            lookalike_details.append({
                'char': char,
                'hex': f'U+{char_ord:04X}',
                'name': name,
                'replaces': CONFUSABLES_MAP[char]
            })
            
        # Try to infer script from character name
        try:
            name = unicodedata.name(char).lower()
            if 'cyrillic' in name:
                scripts.add("Cyrillic")
            elif 'greek' in name:
                scripts.add("Greek")
            elif 'latin' in name:
                scripts.add("Latin-Extended")
            elif 'hebrew' in name:
                scripts.add("Hebrew")
            elif 'arabic' in name:
                scripts.add("Arabic")
            else:
                scripts.add("Other-Unicode")
        except ValueError:
            scripts.add("Unknown-Script")

    is_mixed = len(scripts) > 1 and "Latin-ASCII" in scripts
    return is_mixed, has_lookalikes, scripts, lookalike_details

class HomoglyphDetector:
    def __init__(self, verbose=False):
        self.verbose = verbose
        self.total_scanned_files = 0
        self.total_issues_found = 0

    def scan_string(self, text, source_label="Input String"):
        """Scan a raw string for homoglyphs, invisibles, and bidi overrides."""
        issues = []
        
        # 1. Look for invisible / zero-width characters
        for char, desc in INVISIBLE_CHARS.items():
            matches = [m.start() for m in re.finditer(char, text)]
            for pos in matches:
                issues.append({
                    'type': 'Invisible Character',
                    'detail': f"Found {desc} (U+{ord(char):04X}) at index {pos}",
                    'raw_char': char,
                    'position': pos,
                    'line_num': None
                })

        # 2. Tokenize and check for mixed-script confusables
        # Find contiguous sequences of letters/numbers
        words = re.findall(r'\b\w+\b', text)
        for word in set(words):
            is_mixed, has_lookalike, scripts, lookalikes = analyze_word(word)
            
            if is_mixed or (has_lookalike and any(s != "Latin-ASCII" for s in scripts)):
                # This token is suspicious
                scripts_str = " + ".join(scripts)
                details_str = ", ".join(f"'{l['char']}' ({l['hex']} {l['name']}) looks like '{l['replaces']}'" for l in lookalikes)
                
                issues.append({
                    'type': 'Mixed-Script Homoglyph Token',
                    'detail': f"Suspicious word '{word}' contains scripts: [{scripts_str}]. Lookalikes: {details_str}",
                    'raw_char': word,
                    'position': None,
                    'line_num': None
                })
                
        return issues

    def scan_file(self, filepath):
        """Scan a file line by line for issues."""
        self.total_scanned_files += 1
        issues = []
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                for line_idx, line in enumerate(f, 1):
                    # Check for Bidi control overrides specifically
                    for char, desc in INVISIBLE_CHARS.items():
                        if char in line:
                            pos = line.find(char)
                            issues.append({
                                'type': 'Bidi / Zero-Width Control',
                                'detail': f"Line {line_idx}: {desc} (U+{ord(char):04X}) detected in code",
                                'raw_char': char,
                                'position': pos,
                                'line_num': line_idx,
                                'snippet': line.strip()
                            })
                            
                    # Tokenize line
                    words = re.findall(r'[a-zA-Z0-9\u0080-\uFFFF]+', line)
                    for word in words:
                        is_mixed, has_lookalike, scripts, lookalikes = analyze_word(word)
                        if is_mixed or (has_lookalike and any(s != "Latin-ASCII" for s in scripts)):
                            scripts_str = " + ".join(scripts)
                            details_str = ", ".join(f"'{l['char']}' ({l['hex']}) -> '{l['replaces']}'" for l in lookalikes)
                            
                            issues.append({
                                'type': 'Mixed-Script Homoglyph',
                                'detail': f"Line {line_idx}: Token '{word}' has scripts [{scripts_str}]. Confusables: {details_str}",
                                'raw_char': word,
                                'position': line.find(word),
                                'line_num': line_idx,
                                'snippet': line.strip()
                            })
        except Exception as e:
            if self.verbose:
                print(f"Skipping file '{filepath}' due to read error: {e}")
                
        self.total_issues_found += len(issues)
        return issues

    def scan_directory(self, dirpath, extensions=None):
        """Recursively scan a directory for code/text files containing homoglyphs."""
        root = Path(dirpath)
        if not root.exists():
            print(f"Error: Directory '{dirpath}' does not exist.")
            return {}

        results = {}
        for file_path in root.rglob('*'):
            if file_path.is_file():
                # Skip version control and binary files by extension
                if any(part.startswith('.') for part in file_path.parts):
                    continue
                if extensions and file_path.suffix not in extensions:
                    continue
                if file_path.suffix in ['.png', '.jpg', '.gif', '.zip', '.tar', '.gz', '.pdf', '.exe', '.dll', '.so']:
                    continue
                
                file_issues = self.scan_file(str(file_path))
                if file_issues:
                    results[str(file_path.relative_to(root))] = file_issues
                    
        return results

def main():
    parser = argparse.ArgumentParser(description="Unicode Homoglyph & Phishing Lookalike Security Scanner")
    parser.add_argument("target", nargs="?", default=".", help="File, Directory, or raw string/domain to scan")
    parser.add_argument("-s", "--string", action="store_true", help="Treat target parameter as a raw string/domain rather than a file path")
    parser.add_argument("-e", "--extensions", help="Comma-separated list of file extensions to scan (e.g. .py,.js,.txt)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Output diagnostic information")
    args = parser.parse_args()

    c_red = get_color('red')
    c_green = get_color('green')
    c_yellow = get_color('yellow')
    c_magenta = get_color('magenta')
    c_bold = get_color('bold')
    c_reset = get_color('reset')

    detector = HomoglyphDetector(verbose=args.verbose)

    print(f"{c_bold}{c_magenta}======================================================================{c_reset}")
    print(f"{c_bold}{c_red}              Unicode Homoglyph & Confusable Detector                 {c_reset}")
    print(f"{c_bold}{c_magenta}======================================================================{c_reset}")

    # Case 1: Scanning a raw input string or domain
    if args.string or (args.target and not os.path.exists(args.target)):
        # If it looks like a domain, check if it's punycode or has homoglyphs
        text_to_scan = args.target
        print(f"Target String: '{text_to_scan}'")
        print("-" * 70)
        
        # Check if punycode representation differs
        try:
            punycode = text_to_scan.encode('idna').decode('ascii')
            if punycode != text_to_scan.lower() and punycode.startswith('xn--'):
                print(f"{c_yellow}[!] Domain IDN Detected!{c_reset}")
                print(f"    Punycode: {c_bold}{punycode}{c_reset}")
        except Exception:
            pass

        issues = detector.scan_string(text_to_scan)
        if issues:
            print(f"\n{c_red}Security Issues Detected ({len(issues)}):{c_reset}")
            for iss in issues:
                print(f"  {c_red}✗{c_reset} [{iss['type']}] {iss['detail']}")
        else:
            print(f"\n{c_green}✓ No suspicious homoglyphs or zero-width overrides detected in string.{c_reset}")
        print(f"{c_bold}{c_magenta}======================================================================{c_reset}")
        sys.exit(1 if issues else 0)

    # Case 2: Scanning a file or directory
    target_path = Path(args.target).resolve()
    ext_list = None
    if args.extensions:
        ext_list = [ext.strip() if ext.startswith('.') else f'.{ext.strip()}' for ext in args.extensions.split(',')]

    if target_path.is_file():
        print(f"Scanning File: '{target_path}'")
        print("-" * 70)
        issues = detector.scan_file(str(target_path))
        if issues:
            print(f"\n{c_red}Found {len(issues)} security issues in file:{c_reset}")
            for iss in issues:
                print(f"  {c_red}✗{c_reset} [{iss['type']}] {iss['detail']}")
                if 'snippet' in iss:
                    print(f"    Snippet: {iss['snippet']}")
        else:
            print(f"\n{c_green}✓ File is clean. No homoglyphs or hidden characters found.{c_reset}")
        print(f"{c_bold}{c_magenta}======================================================================{c_reset}")
        sys.exit(1 if issues else 0)

    elif target_path.is_dir():
        print(f"Scanning Directory: '{target_path}'")
        if ext_list:
            print(f"Filtering extensions: {ext_list}")
        print("-" * 70)
        
        results = detector.scan_directory(str(target_path), extensions=ext_list)
        
        if results:
            print(f"\n{c_red}Homoglyph/Security Issues found in {len(results)} files:{c_reset}")
            for rel_path, issues in results.items():
                print(f"\n{c_bold}{rel_path}{c_reset} ({len(issues)} issues):")
                for iss in issues:
                    print(f"  {c_red}✗{c_reset} [{iss['type']}] {iss['detail']}")
                    if 'snippet' in iss:
                        print(f"    Snippet: {c_yellow}{iss['snippet']}{c_reset}")
            print(f"\n{c_bold}{c_magenta}======================================================================{c_reset}")
            print(f"{c_red}STATUS: FAILED ({detector.total_issues_found} total issues across {detector.total_scanned_files} files){c_reset}")
            sys.exit(1)
        else:
            print(f"\n{c_green}✓ Directory clean. Scanned {detector.total_scanned_files} files, 0 issues found.{c_reset}")
            print(f"{c_bold}{c_magenta}======================================================================{c_reset}")
            sys.exit(0)

if __name__ == "__main__":
    main()
