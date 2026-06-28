#!/usr/bin/env python3
"""
Directory Merkle Tree Generator & Comparer - Verify directory structures cryptographically.

This tool recursively generates a Merkle Tree (Hash Tree) of a directory structure.
Each file's hash is computed, and each directory's hash is computed by hashing the
sorted combination of its children's names and hashes.

It supports:
  1. Generating and saving a Merkle Tree to a JSON file.
  2. Comparing a directory against a saved JSON Merkle tree.
  3. Comparing two directories directly to locate added/modified/deleted files.

Usage:
    python tools/directory_merkle_tree.py generate DIRNAME [--output FILE.json]
    python tools/directory_merkle_tree.py compare PATH1 PATH2
"""

import argparse
import hashlib
import json
import os
import sys


def init_colors():
    if sys.stdout.isatty() and os.name == 'nt':
        os.system('')
    use_color = sys.stdout.isatty()
    return {
        "green": "\033[92m" if use_color else "",
        "red": "\033[91m" if use_color else "",
        "yellow": "\033[93m" if use_color else "",
        "blue": "\033[94m" if use_color else "",
        "cyan": "\033[96m" if use_color else "",
        "bold": "\033[1m" if use_color else "",
        "reset": "\033[0m" if use_color else ""
    }


COLORS = init_colors()


def get_file_hash(filepath):
    """Calculates the SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    try:
        with open(filepath, 'rb') as f:
            while chunk := f.read(8192):
                sha256.update(chunk)
        return sha256.hexdigest()
    except (IOError, OSError) as e:
        return f"error:{type(e).__name__}"


def build_merkle_tree(path, root_path=None):
    """Recursively builds a Merkle tree dictionary for a directory path."""
    if root_path is None:
        root_path = path
        
    name = os.path.basename(path)
    rel_path = os.path.relpath(path, root_path)
    if rel_path == '.':
        rel_path = ''
        
    if os.path.isfile(path):
        f_hash = get_file_hash(path)
        size = os.path.getsize(path)
        return {
            "name": name,
            "path": rel_path,
            "type": "file",
            "hash": f_hash,
            "size": size
        }
        
    # Directory
    children = []
    try:
        entries = os.listdir(path)
    except OSError:
        entries = []
        
    for entry in entries:
        child_path = os.path.join(path, entry)
        # Skip git directory
        if entry in ('.git', '__pycache__'):
            continue
        child_node = build_merkle_tree(child_path, root_path)
        children.append(child_node)
        
    # Sort children by name to guarantee deterministic hashing
    children.sort(key=lambda x: x["name"])
    
    # Hash the children's contents and names
    hasher = hashlib.sha256()
    for child in children:
        # Include name, type, and hash in parent's hash calculation
        hasher.update(f"{child['name']}:{child['type']}:{child['hash']}".encode('utf-8'))
        
    dir_hash = hasher.hexdigest()
    
    return {
        "name": name,
        "path": rel_path,
        "type": "directory",
        "hash": dir_hash,
        "children": children
    }


def print_tree(node, indent="", is_last=True):
    """Prints a beautiful visual tree of the Merkle nodes."""
    marker = "└── " if is_last else "├── "
    color = COLORS['blue'] if node['type'] == 'directory' else COLORS['green']
    
    short_hash = node['hash'][:8]
    if node['hash'].startswith('error:'):
        short_hash = f"{COLORS['red']}{node['hash']}{COLORS['reset']}"
        
    print(f"{indent}{marker}{color}{node['name']}{COLORS['reset']} ({COLORS['cyan']}{short_hash}{COLORS['reset']})")
    
    if node['type'] == 'directory':
        indent += "    " if is_last else "│   "
        child_count = len(node['children'])
        for idx, child in enumerate(node['children']):
            print_tree(child, indent, idx == child_count - 1)


def compare_trees(tree_a, tree_b, rel_path=""):
    """Compares two Merkle trees and returns differences."""
    diffs = {
        "added": [],
        "deleted": [],
        "modified": []
    }
    
    if tree_a['hash'] == tree_b['hash']:
        return diffs  # Completely identical
        
    if tree_a['type'] != tree_b['type']:
        diffs['modified'].append({
            "path": rel_path or tree_a['name'],
            "reason": f"Type mismatch: {tree_a['type']} vs {tree_b['type']}"
        })
        return diffs
        
    if tree_a['type'] == 'file':
        diffs['modified'].append({
            "path": rel_path or tree_a['name'],
            "reason": f"File content modified (hash change)"
        })
        return diffs
        
    # Directories with differing hashes
    a_children = {c['name']: c for c in tree_a['children']}
    b_children = {c['name']: c for c in tree_b['children']}
    
    all_names = set(a_children.keys()).union(b_children.keys())
    
    for name in all_names:
        child_path = os.path.join(rel_path, name) if rel_path else name
        
        if name in a_children and name not in b_children:
            diffs['deleted'].append({
                "path": child_path,
                "type": a_children[name]['type']
            })
        elif name not in a_children and name in b_children:
            diffs['added'].append({
                "path": child_path,
                "type": b_children[name]['type']
            })
        else:
            # Present in both, but hash differed
            sub_diffs = compare_trees(a_children[name], b_children[name], child_path)
            diffs['added'].extend(sub_diffs['added'])
            diffs['deleted'].extend(sub_diffs['deleted'])
            diffs['modified'].extend(sub_diffs['modified'])
            
    return diffs


def load_tree_json(filepath):
    """Loads a saved Merkle tree from a JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(description="Directory Merkle Tree Integrity Checker")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # Generate Subcommand
    gen_parser = subparsers.add_parser("generate", help="Generate Merkle tree for a directory")
    gen_parser.add_argument("dir", help="Directory path to scan")
    gen_parser.add_argument("-o", "--output", help="Save tree to JSON file")
    gen_parser.add_argument("-v", "--visual", action="store_true", help="Print visual tree structure")
    
    # Compare Subcommand
    comp_parser = subparsers.add_parser("compare", help="Compare two directories or saved trees")
    comp_parser.add_argument("path1", help="First directory or Merkle JSON file")
    comp_parser.add_argument("path2", help="Second directory or Merkle JSON file")
    
    args = parser.parse_args()
    
    if args.command == "generate":
        target_dir = os.path.abspath(args.dir)
        if not os.path.isdir(target_dir):
            print(f"{COLORS['red']}[!] Path is not a directory: {target_dir}{COLORS['reset']}")
            sys.exit(1)
            
        print(f"Building Merkle Tree for: {COLORS['cyan']}{target_dir}{COLORS['reset']}...")
        tree = build_merkle_tree(target_dir)
        print(f"Root Hash (SHA-256): {COLORS['bold']}{COLORS['green']}{tree['hash']}{COLORS['reset']}")
        
        if args.visual:
            print(f"\n{COLORS['bold']}Merkle Tree Visualization:{COLORS['reset']}")
            print_tree(tree)
            
        if args.output:
            out_file = os.path.abspath(args.output)
            with open(out_file, 'w', encoding='utf-8') as f:
                json.dump(tree, f, indent=2)
            print(f"\n{COLORS['green']}Saved Merkle JSON to: {out_file}{COLORS['reset']}")
            
    elif args.command == "compare":
        # Load or generate tree 1
        path1 = os.path.abspath(args.path1)
        if os.path.isdir(path1):
            print(f"Building Merkle Tree for local directory: {COLORS['cyan']}{path1}{COLORS['reset']}...")
            tree1 = build_merkle_tree(path1)
        elif os.path.isfile(path1) and path1.endswith('.json'):
            print(f"Loading Merkle Tree file: {COLORS['cyan']}{path1}{COLORS['reset']}...")
            tree1 = load_tree_json(path1)
        else:
            print(f"{COLORS['red']}[!] Path 1 is neither a directory nor a JSON file: {path1}{COLORS['reset']}")
            sys.exit(1)
            
        # Load or generate tree 2
        path2 = os.path.abspath(args.path2)
        if os.path.isdir(path2):
            print(f"Building Merkle Tree for local directory: {COLORS['cyan']}{path2}{COLORS['reset']}...")
            tree2 = build_merkle_tree(path2)
        elif os.path.isfile(path2) and path2.endswith('.json'):
            print(f"Loading Merkle Tree file: {COLORS['cyan']}{path2}{COLORS['reset']}...")
            tree2 = load_tree_json(path2)
        else:
            print(f"{COLORS['red']}[!] Path 2 is neither a directory nor a JSON file: {path2}{COLORS['reset']}")
            sys.exit(1)
            
        print("\nComparing Merkle Trees...")
        print(f"  Tree 1 Root Hash: {COLORS['bold']}{tree1['hash'][:16]}...{COLORS['reset']}")
        print(f"  Tree 2 Root Hash: {COLORS['bold']}{tree2['hash'][:16]}...{COLORS['reset']}")
        
        if tree1['hash'] == tree2['hash']:
            print(f"\n{COLORS['bold']}{COLORS['green']}✓ Directories are completely identical! (Hashes match){COLORS['reset']}")
            return
            
        diffs = compare_trees(tree1, tree2)
        
        print(f"\n{COLORS['bold']}{COLORS['yellow']}[!] Differences found between sources:{COLORS['reset']}")
        
        if diffs['added']:
            print(f"\n{COLORS['green']}Added elements in Tree 2:{COLORS['reset']}")
            for item in diffs['added']:
                typ_indicator = "[D]" if item['type'] == 'directory' else "[F]"
                print(f"  {typ_indicator} {item['path']}")
                
        if diffs['deleted']:
            print(f"\n{COLORS['red']}Deleted elements in Tree 2:{COLORS['reset']}")
            for item in diffs['deleted']:
                typ_indicator = "[D]" if item['type'] == 'directory' else "[F]"
                print(f"  {typ_indicator} {item['path']}")
                
        if diffs['modified']:
            print(f"\n{COLORS['yellow']}Modified elements in Tree 2:{COLORS['reset']}")
            for item in diffs['modified']:
                print(f"  [M] {item['path']} ({item['reason']})")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print(f"\n{COLORS['yellow']}Operation canceled.{COLORS['reset']}")
        sys.exit(1)
    except Exception as e:
        print(f"{COLORS['red']}Error: {e}{COLORS['reset']}")
        sys.exit(1)
