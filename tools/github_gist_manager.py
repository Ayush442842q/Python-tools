#!/usr/bin/env python3
"""
GitHub Gist Manager

A CLI tool to list, view, create, update, and delete GitHub Gists using the GitHub API.
Requires a GitHub Personal Access Token (PAT) with the 'gist' scope.

Usage:
    # Set the token environment variable
    export GITHUB_TOKEN="your_personal_access_token"

    # List gists
    python tools/github_gist_manager.py list

    # View a gist
    python tools/github_gist_manager.py view <gist_id>

    # Create a gist
    python tools/github_gist_manager.py create -d "My gist description" file1.txt file2.py

    # Update a gist
    python tools/github_gist_manager.py update <gist_id> -d "Updated description" --file file1.txt

    # Delete a gist
    python tools/github_gist_manager.py delete <gist_id>
"""

import os
import sys
import json
import urllib.request
import urllib.parse
import argparse
from typing import Dict, Any, List, Optional

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

def print_colored(text: str, color: str, file=sys.stdout):
    """Print colored text to the specified stream."""
    if file.isatty():
        file.write(f"{color}{text}{RESET}\n")
    else:
        file.write(f"{text}\n")

def get_token() -> str:
    """Retrieves the GitHub token from the environment."""
    token = os.getenv("GITHUB_TOKEN")
    if not token:
        print_colored("[-] Error: GITHUB_TOKEN environment variable not set.", RED, sys.stderr)
        print_colored("[*] Set it using: export GITHUB_TOKEN=\"your_token\" (Linux/macOS) or set GITHUB_TOKEN=\"your_token\" (Windows)", YELLOW, sys.stderr)
        sys.exit(1)
    return token

def make_request(url: str, method: str = "GET", data: Optional[Dict[str, Any]] = None, token: str = "") -> tuple:
    """Performs an authenticated API request to GitHub."""
    req = urllib.request.Request(url, method=method)
    req.add_header("User-Agent", "Python-Gist-Manager")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("X-GitHub-Api-Version", "2022-11-28")

    if data is not None:
        req.add_header("Content-Type", "application/json")
        json_data = json.dumps(data).encode("utf-8")
        req.data = json_data

    try:
        with urllib.request.urlopen(req) as response:
            res_data = response.read().decode("utf-8")
            status = response.status
            return status, json.loads(res_data) if res_data else {}
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")
        try:
            err_json = json.loads(err_msg)
            message = err_json.get("message", e.reason)
        except Exception:
            message = err_msg if err_msg else e.reason
        print_colored(f"[-] GitHub API Error ({e.code}): {message}", RED, sys.stderr)
        sys.exit(1)
    except Exception as e:
        print_colored(f"[-] Connection Error: {e}", RED, sys.stderr)
        sys.exit(1)

def list_gists(token: str):
    """Lists the user's gists."""
    print_colored("[*] Fetching gists...", BLUE)
    status, gists = make_request("https://api.github.com/gists", token=token)
    
    if not gists:
        print_colored("[*] No gists found.", YELLOW)
        return

    print_colored(f"{'Gist ID':<36} | {'Public':<6} | {'Files':<5} | {'Description'}", BOLD + CYAN)
    print_colored("-" * 80, BLUE)
    for g in gists:
        gist_id = g.get("id", "")
        public = "Yes" if g.get("public") else "No"
        files_count = len(g.get("files", {}))
        desc = g.get("description") or "(No description)"
        if len(desc) > 30:
            desc = desc[:27] + "..."
        print(f"{gist_id:<36} | {public:<6} | {files_count:<5} | {desc}")

def view_gist(gist_id: str, token: str):
    """Displays the details and contents of a specific gist."""
    print_colored(f"[*] Fetching gist {gist_id}...", BLUE)
    status, gist = make_request(f"https://api.github.com/gists/{gist_id}", token=token)

    print_colored(f"\n{BOLD}Gist ID:{RESET} {gist.get('id')}")
    print_colored(f"{BOLD}Description:{RESET} {gist.get('description') or '(No description)'}")
    print_colored(f"{BOLD}Created At:{RESET} {gist.get('created_at')}")
    print_colored(f"{BOLD}Public:{RESET} {'Yes' if gist.get('public') else 'No'}")
    print_colored(f"{BOLD}URL:{RESET} {gist.get('html_url')}")
    print_colored(f"\n{BOLD}Files ({len(gist.get('files', {}))}):{RESET}", CYAN)
    print_colored("=" * 40, BLUE)

    for filename, file_info in gist.get("files", {}).items():
        print_colored(f"\n--- File: {filename} ({file_info.get('language') or 'Text'}, {file_info.get('size')} bytes) ---", GREEN + BOLD)
        content = file_info.get("content")
        if content:
            print(content)
        else:
            raw_url = file_info.get("raw_url")
            print_colored(f"[Truncated/External] Raw URL: {raw_url}", YELLOW)

def create_gist(description: str, public: bool, files: List[str], token: str):
    """Creates a new gist with the specified files."""
    gist_files = {}
    for filepath in files:
        if not os.path.exists(filepath):
            print_colored(f"[-] Error: File not found: {filepath}", RED, sys.stderr)
            sys.exit(1)
        filename = os.path.basename(filepath)
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
            if not content.strip():
                print_colored(f"[-] Error: File '{filepath}' is empty. Gists require non-empty files.", RED, sys.stderr)
                sys.exit(1)
            gist_files[filename] = {"content": content}
        except Exception as e:
            print_colored(f"[-] Error reading file '{filepath}': {e}", RED, sys.stderr)
            sys.exit(1)

    if not gist_files:
        print_colored("[-] Error: No files specified or read.", RED, sys.stderr)
        sys.exit(1)

    data = {
        "description": description,
        "public": public,
        "files": gist_files
    }

    print_colored("[*] Creating gist on GitHub...", BLUE)
    status, res = make_request("https://api.github.com/gists", method="POST", data=data, token=token)
    print_colored(f"[+] Gist created successfully!", GREEN)
    print_colored(f"ID: {res.get('id')}", GREEN)
    print_colored(f"URL: {res.get('html_url')}", GREEN)

def update_gist(gist_id: str, description: Optional[str], file_updates: List[str], token: str):
    """Updates an existing gist's description and/or files."""
    data: Dict[str, Any] = {}
    if description is not None:
        data["description"] = description

    if file_updates:
        gist_files = {}
        for filepath in file_updates:
            # Format: filename:local_path or just local_path
            if ":" in filepath and not os.path.exists(filepath):
                # might be target_name:source_path
                parts = filepath.split(":", 1)
                gist_name = parts[0]
                local_path = parts[1]
            else:
                gist_name = os.path.basename(filepath)
                local_path = filepath

            if not os.path.exists(local_path):
                print_colored(f"[-] Error: Local file not found: {local_path}", RED, sys.stderr)
                sys.exit(1)

            try:
                with open(local_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                gist_files[gist_name] = {"content": content}
            except Exception as e:
                print_colored(f"[-] Error reading file '{local_path}': {e}", RED, sys.stderr)
                sys.exit(1)
        data["files"] = gist_files

    if not data:
        print_colored("[-] Error: Nothing specified to update. Use -d or --file.", RED, sys.stderr)
        sys.exit(1)

    print_colored(f"[*] Updating gist {gist_id}...", BLUE)
    status, res = make_request(f"https://api.github.com/gists/{gist_id}", method="PATCH", data=data, token=token)
    print_colored(f"[+] Gist updated successfully!", GREEN)
    print_colored(f"URL: {res.get('html_url')}", GREEN)

def delete_gist(gist_id: str, token: str):
    """Deletes a gist."""
    print_colored(f"[*] Deleting gist {gist_id}...", BLUE)
    status, res = make_request(f"https://api.github.com/gists/{gist_id}", method="DELETE", token=token)
    if status == 204:
        print_colored(f"[+] Gist {gist_id} deleted successfully.", GREEN)
    else:
        print_colored(f"[-] Unexpected response status: {status}", YELLOW)

def main():
    parser = argparse.ArgumentParser(description="Manage GitHub Gists from the command line.")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # List
    subparsers.add_parser("list", help="List your gists")

    # View
    view_parser = subparsers.add_parser("view", help="View a specific gist")
    view_parser.add_argument("gist_id", help="The unique ID of the gist")

    # Create
    create_parser = subparsers.add_parser("create", help="Create a new gist")
    create_parser.add_argument("-d", "--description", default="", help="Gist description")
    create_parser.add_argument("--public", action="store_true", help="Make gist public (default is secret)")
    create_parser.add_argument("files", nargs="+", help="Files to add to the gist")

    # Update
    update_parser = subparsers.add_parser("update", help="Update an existing gist")
    update_parser.add_argument("gist_id", help="The unique ID of the gist")
    update_parser.add_argument("-d", "--description", default=None, help="Update description")
    update_parser.add_argument("--file", action="append", dest="files", default=[],
                               help="File to add or update. Format: 'filename:local_path' or just 'local_path'")

    # Delete
    delete_parser = subparsers.add_parser("delete", help="Delete a specific gist")
    delete_parser.add_argument("gist_id", help="The unique ID of the gist")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    token = get_token()

    if args.command == "list":
        list_gists(token)
    elif args.command == "view":
        view_gist(args.gist_id, token)
    elif args.command == "create":
        create_gist(args.description, args.public, args.files, token)
    elif args.command == "update":
        update_gist(args.gist_id, args.description, args.files, token)
    elif args.command == "delete":
        confirm = input(f"Are you sure you want to delete gist {args.gist_id}? (y/N): ").strip().lower()
        if confirm == 'y':
            delete_gist(args.gist_id, token)
        else:
            print_colored("Aborted.", YELLOW)

if __name__ == "__main__":
    main()
