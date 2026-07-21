#!/usr/bin/env python3
"""
Developer Code Snippet Manager
A terminal CLI tool to store, categorize, search, copy, and syntax-highlight
frequently used code snippets using a local JSON database and cross-platform clipboard.
"""

import os
import sys
import json
import re
import argparse
import subprocess
from datetime import datetime

# Enable ANSI escape sequences on Windows if possible
if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        stdout_handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        if kernel32.GetConsoleMode(stdout_handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(stdout_handle, mode.value | 0x0004)
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
UNDERLINE = "\033[4m"
RED = "\033[31m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"

# Default database location
DEFAULT_DB = os.path.expanduser("~/.code_snippets.json")

def load_db(db_path):
    """Loads snippet database from JSON file."""
    if not os.path.exists(db_path):
        return {}
    try:
        with open(db_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"{RED}Error loading database: {e}{RESET}", file=sys.stderr)
        return {}

def save_db(db_path, data):
    """Saves snippet database to JSON file."""
    try:
        # Create directory if it doesn't exist
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        with open(db_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"{RED}Error saving database: {e}{RESET}", file=sys.stderr)
        return False

def copy_to_clipboard(text):
    """Copies text to the system clipboard cross-platform using standard commands."""
    try:
        if sys.platform == "win32":
            # Use clip.exe on Windows
            process = subprocess.Popen(['clip'], stdin=subprocess.PIPE, text=True)
            process.communicate(input=text)
            return True
        elif sys.platform == "darwin":
            # Use pbcopy on macOS
            process = subprocess.Popen(['pbcopy'], stdin=subprocess.PIPE, text=True)
            process.communicate(input=text)
            return True
        else:
            # Try xclip or xsel on Linux
            for cmd in [['xclip', '-selection', 'clipboard'], ['xsel', '-b']]:
                try:
                    process = subprocess.Popen(cmd, stdin=subprocess.PIPE, text=True)
                    process.communicate(input=text)
                    return True
                except FileNotFoundError:
                    continue
    except Exception as e:
        print(f"{RED}Clipboard error: {e}{RESET}", file=sys.stderr)
    return False

def highlight_syntax(code, lang):
    """Simple regex-based syntax highlighter for the console."""
    lang = lang.lower()
    if lang not in ['python', 'py', 'javascript', 'js', 'json', 'html', 'xml', 'css', 'bash', 'sh']:
        return code  # Fallback to plain text

    # Standard colors
    CLR_KEYWORD = '\033[94m'  # Light Blue
    CLR_STRING = '\033[92m'   # Green
    CLR_COMMENT = '\033[90m'  # Gray
    CLR_NUMBER = '\033[96m'   # Cyan
    CLR_RESET = '\033[0m'
    
    if lang in ['python', 'py']:
        keywords = r'\b(def|class|return|import|from|as|if|elif|else|for|while|try|except|finally|with|in|is|and|or|not|lambda|pass|break|continue|None|True|False|assert|yield|global|nonlocal)\b'
        rules = [
            ('COMMENT', r'#.*$'),
            ('STRING', r'("""[\s\S]*?"""|\'\'\'[\s\S]*?\'\'\'|"([^"\\]|\\.)*"|\'([^\'\\]|\\.)*\')'),
            ('KEYWORD', keywords),
            ('NUMBER', r'\b\d+(\.\d*)?\b'),
            ('TEXT', r'[\s\S]'),
        ]
    elif lang in ['javascript', 'js']:
        keywords = r'\b(const|let|var|function|return|if|else|for|while|switch|case|default|break|continue|class|import|export|from|true|false|null|undefined|this|new|typeof|instanceof|async|await|try|catch|finally|throw)\b'
        rules = [
            ('COMMENT', r'(//.*$|/\*[\s\S]*?\*/)'),
            ('STRING', r'("([^"\\]|\\.)*"|\'([^\'\\]|\\.)*\'|`([^`\\]|\\.)*`)'),
            ('KEYWORD', keywords),
            ('NUMBER', r'\b\d+(\.\d*)?\b'),
            ('TEXT', r'[\s\S]'),
        ]
    elif lang in ['json']:
        rules = [
            ('STRING', r'"([^"\\]|\\.)*"'),
            ('KEYWORD', r'\b(true|false|null)\b'),
            ('NUMBER', r'\b-?\d+(\.\d*)?\b'),
            ('TEXT', r'[\s\S]'),
        ]
    elif lang in ['html', 'xml']:
        rules = [
            ('COMMENT', r'<!--[\s\S]*?-->'),
            ('KEYWORD', r'</?[a-zA-Z0-9:-]+'),  # Tag names
            ('STRING', r'="[^"]*"|=\'[^\']*\''),  # Attribute values
            ('TEXT', r'[\s\S]'),
        ]
    elif lang == 'css':
        rules = [
            ('COMMENT', r'/\*[\s\S]*?\*/'),
            ('KEYWORD', r'@\w+|[a-zA-Z-]+(?=\s*:)'),  # properties / @rules
            ('STRING', r'"([^"\\]|\\.)*"|\'([^\'\\]|\\.)*\''),
            ('NUMBER', r'\b\d+(px|em|rem|%|s|ms|deg)?\b|#([a-fA-F0-9]{3,8})'),
            ('TEXT', r'[\s\S]'),
        ]
    elif lang in ['bash', 'sh']:
        keywords = r'\b(if|then|elif|else|fi|for|in|do|done|while|case|esac|function|exit|return|local|echo|printf)\b'
        rules = [
            ('COMMENT', r'#.*$'),
            ('STRING', r'("([^"\\]|\\.)*"|\'([^\'\\]|\\.)*\')'),
            ('KEYWORD', keywords),
            ('TEXT', r'[\s\S]'),
        ]
        
    master_regex = '|'.join(f'(?P<{name}>{pattern})' for name, pattern in rules)
    highlighted = []
    
    for match in re.finditer(master_regex, code):
        token_type = match.lastgroup
        token_val = match.group(0)
        
        if token_type == 'COMMENT':
            highlighted.append(f"{CLR_COMMENT}{token_val}{CLR_RESET}")
        elif token_type == 'STRING':
            highlighted.append(f"{CLR_STRING}{token_val}{CLR_RESET}")
        elif token_type == 'KEYWORD':
            highlighted.append(f"{CLR_KEYWORD}{token_val}{CLR_RESET}")
        elif token_type == 'NUMBER':
            highlighted.append(f"{CLR_NUMBER}{token_val}{CLR_RESET}")
        else:
            highlighted.append(token_val)
            
    return "".join(highlighted)

def main():
    parser = argparse.ArgumentParser(
        description="Developer Code Snippet Manager: Store, search, copy and syntax highlight code snippets.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--db", default=DEFAULT_DB, help=f"Path to snippet JSON database (default: {DEFAULT_DB})")
    
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")
    
    # ADD subcommand
    add_parser = subparsers.add_parser("add", help="Add a new code snippet")
    add_parser.add_argument("name", help="Unique identifier or name of the snippet")
    add_parser.add_argument("--lang", "-l", required=True, help="Programming language of the snippet")
    add_parser.add_argument("--desc", "-d", default="", help="Description of what the snippet does")
    add_parser.add_argument("--tags", "-t", default="", help="Comma-separated list of tags")
    add_parser.add_argument("--file", "-f", help="Load code from a file instead of typing interactively")
    
    # LIST subcommand
    list_parser = subparsers.add_parser("list", help="List all stored snippets")
    list_parser.add_argument("--tag", help="Filter listing by tag")
    list_parser.add_argument("--lang", help="Filter listing by programming language")
    
    # VIEW subcommand
    view_parser = subparsers.add_parser("view", help="View snippet code details with syntax highlighting")
    view_parser.add_argument("name", help="Name of the snippet to view")
    view_parser.add_argument("--no-highlight", action="store_true", help="Disable terminal ANSI highlighting")
    
    # SEARCH subcommand
    search_parser = subparsers.add_parser("search", help="Search snippets by keyword in name, tags, or description")
    search_parser.add_argument("query", help="Search string query")
    
    # COPY subcommand
    copy_parser = subparsers.add_parser("copy", help="Copy snippet code directly to the clipboard")
    copy_parser.add_argument("name", help="Name of the snippet to copy")
    
    # DELETE subcommand
    delete_parser = subparsers.add_parser("delete", help="Delete a snippet from the database")
    delete_parser.add_argument("name", help="Name of the snippet to delete")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(0)
        
    db = load_db(args.db)
    
    if args.command == "add":
        name = args.name.strip().replace(" ", "_")
        if name in db:
            confirm = input(f"{YELLOW}Snippet '{name}' already exists. Overwrite? (y/n): {RESET}").strip().lower()
            if confirm not in ['y', 'yes']:
                print("Operation cancelled.")
                sys.exit(0)
                
        # Read snippet code
        if args.file:
            if not os.path.exists(args.file):
                print(f"{RED}Error: Code file '{args.file}' not found.{RESET}", file=sys.stderr)
                sys.exit(1)
            with open(args.file, "r", encoding="utf-8") as f:
                code = f.read()
        else:
            print("Enter/Paste your code snippet below. Press Ctrl-D (Unix) or Ctrl-Z + Enter (Windows) to save:")
            code_lines = sys.stdin.readlines()
            code = "".join(code_lines)
            if not code.strip():
                print(f"{RED}Error: Snippet code cannot be empty.{RESET}", file=sys.stderr)
                sys.exit(1)
                
        # Parse tags
        tags_list = [t.strip().lower() for t in args.tags.split(",") if t.strip()]
        
        db[name] = {
            "name": name,
            "lang": args.lang.strip().lower(),
            "description": args.desc.strip(),
            "tags": tags_list,
            "code": code,
            "updated_at": datetime.now().isoformat()
        }
        
        if save_db(args.db, db):
            print(f"{GREEN}Snippet '{name}' successfully saved to database!{RESET}")
            
    elif args.command == "list":
        if not db:
            print("No snippets stored yet. Use 'add' to save your first snippet!")
            sys.exit(0)
            
        print(f"\n{BOLD}{'Snippet Name':<25} {'Language':<12} {'Tags':<20} {'Description':<30}{RESET}")
        print("-" * 90)
        
        for k, v in sorted(db.items()):
            # Filters
            if args.tag and args.tag.lower() not in v.get("tags", []):
                continue
            if args.lang and args.lang.lower() != v.get("lang", ""):
                continue
                
            tags_str = ", ".join(v.get("tags", []))
            desc_str = v.get("description", "")
            if len(desc_str) > 28:
                desc_str = desc_str[:25] + "..."
                
            print(f"{BLUE}{k:<25}{RESET} {v.get('lang', ''):<12} {tags_str:<20} {desc_str:<30}")
        print()
        
    elif args.command == "view":
        name = args.name.strip()
        if name not in db:
            print(f"{RED}Error: Snippet '{name}' not found.{RESET}", file=sys.stderr)
            sys.exit(1)
            
        snippet = db[name]
        print(f"\n{BOLD}Snippet Name: {RESET}{CYAN}{snippet['name']}{RESET}")
        print(f"{BOLD}Language:     {RESET}{snippet['lang']}")
        if snippet['description']:
            print(f"{BOLD}Description:  {RESET}{snippet['description']}")
        if snippet.get('tags'):
            print(f"{BOLD}Tags:         {RESET}{', '.join(snippet['tags'])}")
        print(f"{BOLD}Updated At:   {RESET}{snippet.get('updated_at', 'N/A')}")
        print("-" * 60)
        
        code = snippet['code']
        if not args.no_highlight:
            code = highlight_syntax(code, snippet['lang'])
            
        print(code)
        print("-" * 60 + "\n")
        
    elif args.command == "search":
        query = args.query.strip().lower()
        if not db:
            print("No snippets stored in the database.")
            sys.exit(0)
            
        results = []
        for k, v in db.items():
            in_name = query in k.lower()
            in_desc = query in v.get("description", "").lower()
            in_tags = any(query in t.lower() for t in v.get("tags", []))
            
            if in_name or in_desc or in_tags:
                results.append(v)
                
        if not results:
            print(f"No snippets matched search query: '{args.query}'")
            sys.exit(0)
            
        print(f"\n{BOLD}Search results for '{args.query}':{RESET}")
        print(f"\n{BOLD}{'Snippet Name':<25} {'Language':<12} {'Tags':<20} {'Description':<30}{RESET}")
        print("-" * 90)
        for v in results:
            tags_str = ", ".join(v.get("tags", []))
            desc_str = v.get("description", "")
            if len(desc_str) > 28:
                desc_str = desc_str[:25] + "..."
            print(f"{BLUE}{v['name']:<25}{RESET} {v.get('lang', ''):<12} {tags_str:<20} {desc_str:<30}")
        print()
        
    elif args.command == "copy":
        name = args.name.strip()
        if name not in db:
            print(f"{RED}Error: Snippet '{name}' not found.{RESET}", file=sys.stderr)
            sys.exit(1)
            
        code = db[name]["code"]
        if copy_to_clipboard(code):
            print(f"{GREEN}Snippet '{name}' code copied to clipboard!{RESET}")
        else:
            print(f"{YELLOW}Warning: Could not copy to clipboard. Snippet code:{RESET}\n")
            print(code)
            
    elif args.command == "delete":
        name = args.name.strip()
        if name not in db:
            print(f"{RED}Error: Snippet '{name}' not found.{RESET}", file=sys.stderr)
            sys.exit(1)
            
        confirm = input(f"{YELLOW}Are you sure you want to delete snippet '{name}'? (y/n): {RESET}").strip().lower()
        if confirm in ['y', 'yes']:
            del db[name]
            if save_db(args.db, db):
                print(f"{GREEN}Snippet '{name}' successfully deleted.{RESET}")
        else:
            print("Operation cancelled.")

if __name__ == "__main__":
    main()
