#!/usr/bin/env python3
"""
CLI Cheat Sheet - A search utility for popular command-line syntax (Git, Docker, Bash, PowerShell, Pip).
Supports keyword searches, parameter explanations, and direct clipboard copying.
"""

import argparse
import subprocess
import sys

# Built-in cheat sheet database
CHEAT_SHEETS = {
    'git': [
        {
            'cmd': 'git commit -am "Commit message"',
            'desc': 'Stage all modified files and create a commit in one step.',
            'details': '-a: stage all modified/deleted files automatically\n-m: specify the commit message inline'
        },
        {
            'cmd': 'git checkout -b <branch-name>',
            'desc': 'Create a new local branch and switch to it immediately.',
            'details': '-b: create branch\n<branch-name>: name of the new branch'
        },
        {
            'cmd': 'git log --oneline --graph --all',
            'desc': 'Display history as a compact text-based graphical tree.',
            'details': '--oneline: show each commit on one line\n--graph: draw branch structure\n--all: show all branches'
        },
        {
            'cmd': 'git stash push -m "work description"',
            'desc': 'Temporarily save modifications and reset working directory.',
            'details': 'push: save changes to stash\n-m: associate a custom comment/message with the stash'
        },
        {
            'cmd': 'git reset --hard HEAD~1',
            'desc': 'Undo the last commit, discarding all uncommitted changes.',
            'details': '--hard: reset the index and working tree (all changes lost!)\nHEAD~1: reference to the parent commit'
        }
    ],
    'docker': [
        {
            'cmd': 'docker run -d -p <host-port>:<container-port> --name <name> <image>',
            'desc': 'Run a container in detached background mode with port forwarding.',
            'details': '-d: run container in background (detached)\n-p: publish port mapping\n--name: assign custom container name'
        },
        {
            'cmd': 'docker exec -it <container-id> /bin/bash',
            'desc': 'Open an interactive bash terminal inside a running container.',
            'details': '-i: keep STDIN open\n-t: allocate a pseudo-TTY terminal\n/bin/bash: shell program to run'
        },
        {
            'cmd': 'docker build -t <tag-name> .',
            'desc': 'Build a Docker image from a Dockerfile in the current directory.',
            'details': '-t: tag/name the image\n.: path to build context (current folder)'
        },
        {
            'cmd': 'docker system prune -a --volumes',
            'desc': 'Clean up all unused container, image, network, and volume data.',
            'details': '-a: remove all unused images (not just dangling ones)\n--volumes: prune volume storage as well'
        }
    ],
    'bash': [
        {
            'cmd': 'find . -type f -name "*.txt" -exec grep -l "search_text" {} +',
            'desc': 'Find all text files under current directory containing a specific word.',
            'details': '-type f: search for files only\n-name: glob matching file extension\n-exec: execute grep on the results\n-l: only output matching filenames'
        },
        {
            'cmd': 'tar -czvf archive.tar.gz /path/to/folder',
            'desc': 'Create a compressed tarball archive of a folder.',
            'details': '-c: create new archive\n-z: compress via gzip\n-v: verbose listing of processed files\n-f: specify the archive filename'
        },
        {
            'cmd': 'lsof -i :<port-number>',
            'desc': 'List process IDs running on a specific network port.',
            'details': '-i: select internet socket files\n:<port-number>: target port'
        },
        {
            'cmd': 'rsync -avz --progress /source/ /destination/',
            'desc': 'Fast, incremental file transfer/sync with bandwidth compression.',
            'details': '-a: archive mode (preserves permissions, times, symlinks)\n-v: verbose output\n-z: compress file data during transfer\n--progress: show file transfer indicators'
        }
    ],
    'powershell': [
        {
            'cmd': 'Get-Process | Sort-Object CPU -Descending | Select-Object -First 10',
            'desc': 'Find the top 10 processes consuming the most CPU.',
            'details': 'Get-Process: retrieves system processes\nSort-Object: sorts results by property\nSelect-Object -First: grabs slice of output'
        },
        {
            'cmd': 'Get-ChildItem -Path . -Recurse -Filter "web.config"',
            'desc': 'Search recursively for files named "web.config" starting from current folder.',
            'details': '-Path: start directory\n-Recurse: search nested directories\n-Filter: match files with specific names'
        },
        {
            'cmd': 'Test-NetConnection -ComputerName <ip> -Port <port>',
            'desc': 'Check TCP socket connectivity to a host/port with diagnostic trace.',
            'details': '-ComputerName: hostname or IP address\n-Port: TCP target port to check'
        }
    ],
    'pip': [
        {
            'cmd': 'pip install -r requirements.txt --upgrade',
            'desc': 'Install or upgrade all packages listed in requirements.txt.',
            'details': '-r: read packages from requirements file\n--upgrade: update all specified packages'
        },
        {
            'cmd': 'pip freeze > requirements.txt',
            'desc': 'Export names and versions of all installed packages in pip format.',
            'details': 'freeze: prints packages in pip requirements syntax\n>: writes output to file'
        },
        {
            'cmd': 'python -m venv venv',
            'desc': 'Create a new local Python virtual environment.',
            'details': '-m venv: run the standard library venv module\nvenv: destination directory name'
        }
    ]
}

def copy_to_clipboard(text):
    """Copies text to the system clipboard based on the host OS."""
    try:
        if sys.platform.startswith('win'):
            # Windows
            process = subprocess.Popen('clip', stdin=subprocess.PIPE, shell=True)
            process.communicate(input=text.encode('utf-8'))
            return True
        elif sys.platform.startswith('darwin'):
            # macOS
            process = subprocess.Popen('pbcopy', stdin=subprocess.PIPE)
            process.communicate(input=text.encode('utf-8'))
            return True
        else:
            # Linux
            process = subprocess.Popen(['xclip', '-selection', 'clipboard'], stdin=subprocess.PIPE)
            process.communicate(input=text.encode('utf-8'))
            return True
    except Exception:
        return False

def print_command_card(entry):
    """Prints a styled card representing a command cheat sheet."""
    print("=" * 60)
    print(f"COMMAND: {entry['cmd']}")
    print(f"DESC   : {entry['desc']}")
    if entry.get('details'):
        print("-" * 60)
        print("PARAMETERS:")
        for line in entry['details'].split('\n'):
            print(f"  {line}")
    print("=" * 60)

def search_commands(query, category=None):
    """Searches commands by keyword in cmd or description."""
    results = []
    cats = [category] if category else list(CHEAT_SHEETS.keys())
    
    query = query.lower()
    for cat in cats:
        if cat in CHEAT_SHEETS:
            for entry in CHEAT_SHEETS[cat]:
                if query in entry['cmd'].lower() or query in entry['desc'].lower() or query in entry['details'].lower():
                    results.append((cat, entry))
                    
    return results

def interactive_mode():
    """Drops into an interactive terminal menu when no CLI arguments are supplied."""
    print("*" * 60)
    print("           CLI CHEAT SHEET - INTERACTIVE MENU")
    print("*" * 60)
    
    categories = list(CHEAT_SHEETS.keys())
    while True:
        print("\nCategories:")
        for idx, cat in enumerate(categories, 1):
            print(f"  [{idx}] {cat.capitalize()}")
        print("  [S] Search all commands")
        print("  [Q] Exit")
        
        choice = input("\nSelect an option (1-5, S, Q): ").strip().lower()
        
        if choice == 'q':
            print("Goodbye!")
            break
        elif choice == 's':
            query = input("Enter search keyword: ").strip()
            results = search_commands(query)
            if not results:
                print("[-] No matching commands found.")
            else:
                print(f"\nFound {len(results)} matches:")
                for idx, (cat, entry) in enumerate(results, 1):
                    print(f"\n[{idx}] Category: {cat.capitalize()}")
                    print_command_card(entry)
                handle_copy_choice(results)
        elif choice.isdigit() and 1 <= int(choice) <= len(categories):
            cat = categories[int(choice) - 1]
            print(f"\n--- {cat.upper()} CHEAT SHEET ---")
            entries = CHEAT_SHEETS[cat]
            for idx, entry in enumerate(entries, 1):
                print(f"\n[{idx}] {entry['desc']}")
                print(f"    Code: {entry['cmd']}")
            
            sub_choice = input(f"\nSelect a command index (1-{len(entries)}) or press Enter to return: ").strip()
            if sub_choice.isdigit() and 1 <= int(sub_choice) <= len(entries):
                entry = entries[int(sub_choice) - 1]
                print()
                print_command_card(entry)
                
                copy_input = input("\nCopy this command to clipboard? (y/n): ").strip().lower()
                if copy_input == 'y':
                    if copy_to_clipboard(entry['cmd']):
                        print("[+] Copied command to clipboard.")
                    else:
                        print("[!] Failed to copy (clipboard utility not found).")
        else:
            print("[!] Invalid option. Try again.")

def handle_copy_choice(results):
    """Asks user which command they want to copy from a search list."""
    copy_idx = input("\nEnter a command index to view details and copy (or press Enter to return): ").strip()
    if copy_idx.isdigit() and 1 <= int(copy_idx) <= len(results):
        _, entry = results[int(copy_idx) - 1]
        print()
        print_command_card(entry)
        copy_input = input("\nCopy this command to clipboard? (y/n): ").strip().lower()
        if copy_input == 'y':
            if copy_to_clipboard(entry['cmd']):
                print("[+] Copied command to clipboard.")
            else:
                print("[!] Failed to copy (clipboard utility not found).")

def main():
    parser = argparse.ArgumentParser(
        description="CLI Cheat Sheet: Look up popular shell, Git, Docker, and pip command templates offline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
If no arguments are provided, the tool starts in interactive menu mode.
"""
    )
    
    parser.add_argument("-s", "--search", help="Search cheat sheets for matching keyword")
    parser.add_argument("-c", "--category", choices=list(CHEAT_SHEETS.keys()), help="Filter commands by category")
    parser.add_argument("-y", "--copy", action="store_true", help="Automatically copy the first matching command to clipboard")
    
    args = parser.parse_args()
    
    # If no arguments, drop into interactive terminal
    if len(sys.argv) == 1:
        interactive_mode()
        return

    # Handle query
    if args.search:
        results = search_commands(args.search, args.category)
        if not results:
            print(f"[-] No commands found matching '{args.search}' under category '{args.category or 'all'}'.")
            sys.exit(0)
            
        print(f"[+] Found {len(results)} matches:")
        for cat, entry in results:
            print(f"\n[Category: {cat.capitalize()}]")
            print_command_card(entry)
            
        if args.copy:
            first_cmd = results[0][1]['cmd']
            if copy_to_clipboard(first_cmd):
                print(f"\n[+] Copied first match to clipboard: '{first_cmd}'")
            else:
                print("\n[!] Failed to copy to clipboard.")
    
    elif args.category:
        print(f"=== {args.category.upper()} COMMANDS ===")
        for entry in CHEAT_SHEETS[args.category]:
            print_command_card(entry)
            print()

if __name__ == "__main__":
    main()
