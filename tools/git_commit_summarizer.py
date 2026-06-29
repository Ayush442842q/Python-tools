#!/usr/bin/env python3
"""
Git Commit Summarizer - Summarizes git diff changes and generates Conventional Commits messages.
It parses `git diff --cached` (or unstaged changes/branches) to identify modified files, 
added/removed classes, functions, or key configuration parameters, and recommends 
clear, structured commit messages. It can also perform the commit interactively.
"""

import argparse
import re
import subprocess
import sys


def run_git_command(args):
    """Executes a git command and returns its stdout/stderr."""
    try:
        res = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True
        )
        return res.stdout.strip(), None
    except subprocess.CalledProcessError as e:
        return None, e.stderr.strip()
    except FileNotFoundError:
        return None, "git executable not found on system PATH."


def parse_diff(diff_text):
    """Parses the git diff text into a structured dictionary of changes."""
    file_changes = {}
    current_file = None
    hunk_header_re = re.compile(r"^@@ -\d+,\d+ \+(\d+),(\d+) @@")
    
    lines = diff_text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        
        if line.startswith("diff --git"):
            # New file block
            current_file = None
            # Extract filenames
            match = re.match(r"^diff --git a/(.*?) b/(.*?)$", line)
            if match:
                current_file = match.group(2)
                file_changes[current_file] = {
                    "added_lines": 0,
                    "deleted_lines": 0,
                    "added_functions": [],
                    "added_classes": [],
                    "modified_configs": [],
                    "is_new": False,
                    "is_deleted": False,
                }
            i += 1
            continue
            
        if not current_file:
            i += 1
            continue
            
        if line.startswith("new file mode"):
            file_changes[current_file]["is_new"] = True
            i += 1
            continue
            
        if line.startswith("deleted file mode"):
            file_changes[current_file]["is_deleted"] = True
            i += 1
            continue
            
        if line.startswith("+++ b/") or line.startswith("--- a/"):
            i += 1
            continue
            
        if line.startswith("@@"):
            i += 1
            continue
            
        if line.startswith("+") and not line.startswith("+++"):
            file_changes[current_file]["added_lines"] += 1
            added_content = line[1:].strip()
            
            # Python additions (functions/classes)
            if current_file.endswith(".py"):
                func_match = re.match(r"^\s*def\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(", added_content)
                class_match = re.match(r"^\s*class\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*[:\(]", added_content)
                if func_match:
                    file_changes[current_file]["added_functions"].append(func_match.group(1))
                elif class_match:
                    file_changes[current_file]["added_classes"].append(class_match.group(1))
                    
            # Config additions (.env, .ini, etc.)
            elif current_file.endswith((".env", ".ini", ".conf", ".properties")):
                cfg_match = re.match(r"^([A-Z_a-z0-9\-]+)\s*=", added_content)
                if cfg_match:
                    file_changes[current_file]["modified_configs"].append(cfg_match.group(1))
            
            i += 1
            continue
            
        if line.startswith("-") and not line.startswith("---"):
            file_changes[current_file]["deleted_lines"] += 1
            i += 1
            continue
            
        i += 1
        
    return file_changes


def get_scope_from_filename(filename):
    """Derives a commit scope from the modified file path."""
    parts = filename.replace("\\", "/").split("/")
    if len(parts) > 1:
        # e.g., tools/case_converter.py -> 'case_converter'
        base = parts[-1]
        name = base.rsplit(".", 1)[0]
        if name in ("__init__", "main", "run"):
            return parts[-2]
        return name
    return filename.rsplit(".", 1)[0]


def generate_commit_suggestions(file_changes):
    """Suggests conventional commit messages based on the analyzed file changes."""
    if not file_changes:
        return ["chore: update files"]
        
    suggestions = []
    
    # Analyze global changes to choose the most likely type (feat, fix, refactor, chore)
    all_files = list(file_changes.keys())
    total_added = sum(f["added_lines"] for f in file_changes.values())
    total_deleted = sum(f["deleted_lines"] for f in file_changes.values())
    
    is_docs = all(f.endswith((".md", ".txt", ".rst")) for f in all_files)
    is_test = all("test" in f.lower() for f in all_files)
    is_ci = all("github/workflows" in f or f == ".gitignore" or f.endswith((".yml", ".yaml")) for f in all_files)
    
    # 1. Scope recommendation
    scopes = [get_scope_from_filename(f) for f in all_files]
    scope = scopes[0] if len(set(scopes)) == 1 else ""
    scope_str = f"({scope})" if scope else ""
    
    # Helper to clean/shorten
    def plural(count, noun):
        return f"{count} {noun}{'s' if count != 1 else ''}"

    if is_docs:
        suggestions.append(f"docs{scope_str}: update documentation and references")
        if len(all_files) == 1:
            suggestions.append(f"docs({scope}): edit {all_files[0].split('/')[-1]}")
    elif is_test:
        suggestions.append(f"test{scope_str}: add tests for {scope or 'application functionality'}")
    elif is_ci:
        suggestions.append(f"ci{scope_str}: configure workflows or pipeline files")
    else:
        # Code changes
        # Look for specific features (e.g., new file or many new functions)
        new_files = [f for f, data in file_changes.items() if data["is_new"]]
        
        if new_files:
            for nf in new_files:
                name = get_scope_from_filename(nf)
                suggestions.append(f"feat({name}): introduce new {name} module/tool")
        
        # Check added classes and functions
        added_funcs = []
        added_classes = []
        for f, data in file_changes.items():
            added_funcs.extend(data["added_functions"])
            added_classes.extend(data["added_classes"])
            
        if added_classes:
            suggestions.append(f"feat{scope_str}: implement {', '.join(added_classes)} class{'es' if len(added_classes)>1 else ''}")
        if added_funcs:
            suggestions.append(f"feat{scope_str}: add {', '.join(added_funcs)} function{'s' if len(added_funcs)>1 else ''}")
            
        # General changes
        suggestions.append(f"refactor{scope_str}: optimize structure and clean up code in {plural(len(all_files), 'file')}")
        suggestions.append(f"feat{scope_str}: add enhancements and modifications to {scope or 'codebase'}")
        suggestions.append(f"fix{scope_str}: resolve issues and correct behavior in {scope or 'codebase'}")
        
    return suggestions


def print_summary(file_changes):
    """Displays a formatted summary of the changes in the diff."""
    print("=" * 60)
    print("                 GIT CHANGES SUMMARY")
    print("=" * 60)
    
    if not file_changes:
        print("No changes detected.")
        return
        
    for filename, stats in file_changes.items():
        status = " [NEW]" if stats["is_new"] else (" [DELETED]" if stats["is_deleted"] else "")
        print(f"\n* {filename}{status}")
        print(f"  Lines: +{stats['added_lines']} / -{stats['deleted_lines']}")
        
        if stats["added_classes"]:
            print(f"  Added Classes: {', '.join(stats['added_classes'])}")
        if stats["added_functions"]:
            print(f"  Added Functions: {', '.join(stats['added_functions'])}")
        if stats["modified_configs"]:
            print(f"  Added Config Variables: {', '.join(stats['modified_configs'])}")
            
    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description="Git Commit Summarizer - Analyze diffs and write Conventional Commits."
    )
    parser.add_argument(
        "-u", "--unstaged",
        action="store_true",
        help="Analyze unstaged changes instead of staged (cached) changes"
    )
    parser.add_argument(
        "-c", "--commit",
        action="store_true",
        help="Interactively select a message and commit the changes"
    )
    parser.add_argument(
        "-d", "--diff",
        help="Provide raw diff text directly via file or string"
    )
    
    args = parser.parse_args()
    
    # Fetch diff text
    diff_text = ""
    if args.diff:
        try:
            with open(args.diff, "r", encoding="utf-8") as f:
                diff_text = f.read()
        except FileNotFoundError:
            diff_text = args.diff
    else:
        # Run git command
        git_args = ["diff", "--cached"] if not args.unstaged else ["diff"]
        stdout, err = run_git_command(git_args)
        if err:
            print(f"Error running git command: {err}", file=sys.stderr)
            return 1
        diff_text = stdout
        
    if not diff_text.strip():
        print("No differences found. Make sure files are staged/tracked or use -u.")
        return 0
        
    file_changes = parse_diff(diff_text)
    print_summary(file_changes)
    
    suggestions = generate_commit_suggestions(file_changes)
    
    print("\nSuggested Commit Messages:")
    for idx, msg in enumerate(suggestions, 1):
        print(f"[{idx}] {msg}")
        
    if args.commit:
        print("\nSelect a number to commit, or press Enter to cancel:")
        try:
            choice = input("> ").strip()
            if not choice:
                print("Commit cancelled.")
                return 0
            
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(suggestions):
                selected_msg = suggestions[choice_idx]
                
                # Perform git commit
                print(f"Committing with message: '{selected_msg}'...")
                stdout, err = run_git_command(["commit", "-m", selected_msg])
                if err:
                    print(f"Error during commit: {err}", file=sys.stderr)
                    return 1
                print(stdout)
                print("[+] Changes committed successfully!")
            else:
                print("Invalid selection. Commit cancelled.")
        except ValueError:
            print("Invalid input. Commit cancelled.")
        except KeyboardInterrupt:
            print("\nCommit cancelled.")
            
    return 0


if __name__ == "__main__":
    sys.exit(main())
