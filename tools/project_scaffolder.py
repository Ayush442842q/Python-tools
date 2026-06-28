#!/usr/bin/env python3
"""
Project Scaffolder & Code Generator
Recursively processes a template directory containing placeholders like {{PROJECT_NAME}}
in folder names, file names, and file contents, and instantiates it into a target directory.
"""

import os
import sys
import re
import argparse
import shutil

# Regex to find placeholders like {{VARIABLE_NAME}}
PLACEHOLDER_RE = re.compile(r'\{\{([A-Za-z0-9_]+)\}\}')

# Common binary file extensions to skip text replacement
BINARY_EXTENSIONS = {
    # Images
    '.png', '.jpg', '.jpeg', '.gif', '.ico', '.pdf', '.webp', '.bmp',
    # Archives
    '.zip', '.tar', '.gz', '.bz2', '.7z', '.rar', '.iso',
    # Audio/Video
    '.mp3', '.mp4', '.wav', '.avi', '.mkv', '.mov', '.flac',
    # Compiled/Executables
    '.pyc', '.exe', '.dll', '.so', '.dylib', '.bin', '.class', '.o',
    # Fonts
    '.ttf', '.otf', '.woff', '.woff2', '.eot'
}

def is_binary_file(filepath):
    _, ext = os.path.splitext(filepath.lower())
    if ext in BINARY_EXTENSIONS:
        return True
    
    # Heuristic check: read first 1024 bytes and search for null byte
    try:
        with open(filepath, 'rb') as f:
            chunk = f.read(1024)
            return b'\x00' in chunk
    except Exception:
        # If we can't read it, treat as binary
        return True


def find_placeholders_in_string(s):
    return set(PLACEHOLDER_RE.findall(s))


def scan_placeholders(template_dir):
    placeholders = set()
    for root, dirs, files in os.walk(template_dir):
        # Scan folder names
        for d in dirs:
            placeholders.update(find_placeholders_in_string(d))
        
        # Scan file names and contents
        for f in files:
            placeholders.update(find_placeholders_in_string(f))
            
            filepath = os.path.join(root, f)
            if not is_binary_file(filepath):
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as file_obj:
                        content = file_obj.read()
                        placeholders.update(find_placeholders_in_string(content))
                except Exception:
                    pass
    return placeholders


def replace_placeholders(text, variables):
    def replace_match(match):
        var_name = match.group(1)
        return str(variables.get(var_name, match.group(0)))
    return PLACEHOLDER_RE.sub(replace_match, text)


def scaffold_project(template_dir, target_dir, variables, dry_run=False):
    print(f"[*] Scaffolding project from '{template_dir}' to '{target_dir}'...")
    
    if not os.path.exists(target_dir) and not dry_run:
        os.makedirs(target_dir)

    for root, dirs, files in os.walk(template_dir):
        # Determine relative path from template root
        rel_path = os.path.relpath(root, template_dir)
        if rel_path == '.':
            target_root = target_dir
        else:
            # Replace placeholders in path
            replaced_rel_path = replace_placeholders(rel_path, variables)
            target_root = os.path.join(target_dir, replaced_rel_path)
            if not os.path.exists(target_root) and not dry_run:
                os.makedirs(target_root)

        for f in files:
            # Replace placeholders in filename
            replaced_filename = replace_placeholders(f, variables)
            src_file = os.path.join(root, f)
            dest_file = os.path.join(target_root, replaced_filename)
            
            if dry_run:
                print(f"[Dry-Run] Would create file: {dest_file}")
                continue

            if is_binary_file(src_file):
                print(f"[Copy Binary] {src_file} -> {dest_file}")
                shutil.copy2(src_file, dest_file)
            else:
                print(f"[Generate File] {src_file} -> {dest_file}")
                try:
                    with open(src_file, 'r', encoding='utf-8', errors='ignore') as sf:
                        content = sf.read()
                    
                    replaced_content = replace_placeholders(content, variables)
                    
                    with open(dest_file, 'w', encoding='utf-8') as df:
                        df.write(replaced_content)
                except Exception as e:
                    print(f"[-] Error generating file {dest_file}: {e}", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description="Template-based Project Scaffolder & Code Generator")
    parser.add_argument("template", help="Path to the template directory")
    parser.add_argument("target", help="Path to target directory where project will be generated")
    parser.add_argument("--dry-run", action="store_true", help="Dry run mode (shows planned modifications without writing)")
    parser.add_argument("-v", "--var", action="append", help="Define variables directly via CLI in name=value format")

    args = parser.parse_args()

    template_dir = os.path.abspath(args.template)
    target_dir = os.path.abspath(args.target)

    if not os.path.exists(template_dir) or not os.path.isdir(template_dir):
        print(f"[-] Error: Template directory '{template_dir}' does not exist or is not a folder.", file=sys.stderr)
        sys.exit(1)

    print(f"[*] Scanning template folder '{template_dir}' for placeholders...")
    placeholders = scan_placeholders(template_dir)
    
    if not placeholders:
        print("[*] No placeholders found. Proceeding with regular directory copying.")
    else:
        print(f"[+] Found {len(placeholders)} unique placeholders: {', '.join(sorted(placeholders))}")

    # Parse CLI variables
    variables = {}
    if args.var:
        for var_expr in args.var:
            if '=' in var_expr:
                name, val = var_expr.split('=', 1)
                variables[name.strip()] = val.strip()

    # Interactively prompt for missing variables
    if placeholders:
        print("\n[*] Please provide values for the following template variables:")
        for ph in sorted(placeholders):
            if ph in variables:
                # Value provided in CLI arguments
                print(f"  {ph}: {variables[ph]} (provided via CLI)")
                continue
            
            # Suggest a default guess from environment or defaults
            default_val = ""
            if ph.upper() == "YEAR":
                import datetime
                default_val = str(datetime.datetime.now().year)
            elif ph.upper() == "USER" or ph.upper() == "AUTHOR":
                default_val = os.getlogin() or os.environ.get("USER") or os.environ.get("USERNAME") or ""

            prompt_str = f"  {ph}"
            if default_val:
                prompt_str += f" [{default_val}]"
            prompt_str += ": "
            
            user_val = input(prompt_str).strip()
            if not user_val and default_val:
                user_val = default_val
            
            variables[ph] = user_val

    # Run the scaffold
    print("")
    scaffold_project(template_dir, target_dir, variables, dry_run=args.dry_run)
    print("\n[+] Done!")


if __name__ == "__main__":
    main()
