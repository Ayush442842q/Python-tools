#!/usr/bin/env python3
"""
JSON Patch & Merge Patch Utility
Implement RFC 6902 (JSON Patch) and RFC 7396 (JSON Merge Patch) to apply patches,
compare two JSON documents to generate patches, and validate patch operations.

Usage:
    python tools/json_patch_utility.py target.json patch.json --type patch
    python tools/json_patch_utility.py target.json merge_patch.json --type merge
    python tools/json_patch_utility.py original.json modified.json --diff
"""

import argparse
import copy
import json
import os
import sys
from typing import Any, Dict, List, Tuple, Union

# ANSI Escape Codes for colorized output
COLOR_HEADER = "\033[95m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"
COLOR_GREEN = "\033[92m"
COLOR_WARNING = "\033[93m"
COLOR_FAIL = "\033[91m"
COLOR_END = "\033[0m"
COLOR_BOLD = "\033[1m"


def print_colored(text: str, color: str):
    """Print text with ANSI color codes if output is a TTY."""
    if sys.stdout.isatty():
        print(f"{color}{text}{COLOR_END}")
    else:
        print(text)


def parse_pointer(pointer: str) -> List[str]:
    """Parse a JSON Pointer string (RFC 6901) into tokens."""
    if not pointer:
        return []
    if not pointer.startswith("/"):
        raise ValueError(f"Invalid JSON Pointer (must start with '/'): {pointer}")
    
    parts = pointer.split("/")[1:]
    # Decode '~1' to '/' and '~0' to '~'
    return [p.replace("~1", "/").replace("~0", "~") for p in parts]


def navigate_pointer(doc: Any, tokens: List[str], create_missing: bool = False) -> Tuple[Any, Union[str, int]]:
    """Navigate down to the parent of the pointer destination."""
    curr = doc
    for i, token in enumerate(tokens[:-1]):
        if isinstance(curr, dict):
            if token not in curr:
                if create_missing:
                    curr[token] = {}
                else:
                    raise KeyError(f"Key '{token}' not found")
            curr = curr[token]
        elif isinstance(curr, list):
            try:
                idx = int(token)
                curr = curr[idx]
            except (ValueError, IndexError):
                raise IndexError(f"Invalid list index '{token}'")
        else:
            raise TypeError(f"Cannot navigate path through primitive type at '{token}'")
            
    if not tokens:
        return doc, ""
        
    last_token = tokens[-1]
    if isinstance(curr, list):
        if last_token == "-":
            return curr, "-"
        try:
            return curr, int(last_token)
        except ValueError:
            raise IndexError(f"List index must be integer or '-': {last_token}")
            
    return curr, last_token


def apply_json_patch(doc: Any, patch: List[Dict[str, Any]]) -> Any:
    """Applies a JSON Patch (RFC 6902) to the document in-place (or returning copy)."""
    work_doc = copy.deepcopy(doc)
    
    for op_idx, operation in enumerate(patch):
        if not isinstance(operation, dict) or "op" not in operation:
            raise ValueError(f"Operation #{op_idx} is not a valid JSON object with 'op'")
            
        op = operation["op"]
        path = operation.get("path")
        if path is None:
            raise ValueError(f"Operation #{op_idx} is missing 'path'")
            
        tokens = parse_pointer(path)
        
        if op == "add":
            if "value" not in operation:
                raise ValueError(f"Operation #{op_idx} (add) is missing 'value'")
            val = operation["value"]
            
            if not tokens: # Replace root document
                work_doc = val
                continue
                
            parent, key = navigate_pointer(work_doc, tokens, create_missing=True)
            if isinstance(parent, dict):
                parent[key] = val
            elif isinstance(parent, list):
                if key == "-":
                    parent.append(val)
                else:
                    assert isinstance(key, int)
                    if key < 0 or key > len(parent):
                        raise IndexError(f"Index {key} out of bounds for list size {len(parent)}")
                    parent.insert(key, val)
                    
        elif op == "remove":
            if not tokens:
                raise ValueError("Cannot remove root document via patch")
            parent, key = navigate_pointer(work_doc, tokens)
            if isinstance(parent, dict):
                if key not in parent:
                    raise KeyError(f"Key '{key}' not found at path '{path}'")
                del parent[key]
            elif isinstance(parent, list):
                assert isinstance(key, int)
                if key < 0 or key >= len(parent):
                    raise IndexError(f"Index {key} out of bounds")
                parent.pop(key)
                
        elif op == "replace":
            if "value" not in operation:
                raise ValueError(f"Operation #{op_idx} (replace) is missing 'value'")
            val = operation["value"]
            if not tokens:
                work_doc = val
                continue
            parent, key = navigate_pointer(work_doc, tokens)
            if isinstance(parent, dict):
                if key not in parent:
                    raise KeyError(f"Key '{key}' not found at path '{path}'")
                parent[key] = val
            elif isinstance(parent, list):
                assert isinstance(key, int)
                if key < 0 or key >= len(parent):
                    raise IndexError(f"Index {key} out of bounds")
                parent[key] = val
                
        elif op == "move":
            from_path = operation.get("from")
            if from_path is None:
                raise ValueError(f"Operation #{op_idx} (move) is missing 'from'")
                
            if from_path == path:
                continue # No-op
                
            from_tokens = parse_pointer(from_path)
            from_parent, from_key = navigate_pointer(work_doc, from_tokens)
            
            # Fetch and remove item
            if isinstance(from_parent, dict):
                if from_key not in from_parent:
                    raise KeyError(f"Key '{from_key}' not found at '{from_path}'")
                val = from_parent.pop(from_key)
            elif isinstance(from_parent, list):
                assert isinstance(from_key, int)
                val = from_parent.pop(from_key)
            else:
                raise TypeError(f"Invalid 'from' parent element at '{from_path}'")
                
            # Insert item
            if not tokens:
                work_doc = val
                continue
            parent, key = navigate_pointer(work_doc, tokens, create_missing=True)
            if isinstance(parent, dict):
                parent[key] = val
            elif isinstance(parent, list):
                if key == "-":
                    parent.append(val)
                else:
                    assert isinstance(key, int)
                    parent.insert(key, val)
                    
        elif op == "copy":
            from_path = operation.get("from")
            if from_path is None:
                raise ValueError(f"Operation #{op_idx} (copy) is missing 'from'")
            from_tokens = parse_pointer(from_path)
            from_parent, from_key = navigate_pointer(work_doc, from_tokens)
            
            # Fetch item
            if isinstance(from_parent, dict):
                if from_key not in from_parent:
                    raise KeyError(f"Key '{from_key}' not found at '{from_path}'")
                val = copy.deepcopy(from_parent[from_key])
            elif isinstance(from_parent, list):
                assert isinstance(from_key, int)
                val = copy.deepcopy(from_parent[from_key])
            else:
                raise TypeError(f"Invalid 'from' parent element at '{from_path}'")
                
            # Insert item
            if not tokens:
                work_doc = val
                continue
            parent, key = navigate_pointer(work_doc, tokens, create_missing=True)
            if isinstance(parent, dict):
                parent[key] = val
            elif isinstance(parent, list):
                if key == "-":
                    parent.append(val)
                else:
                    assert isinstance(key, int)
                    parent.insert(key, val)
                    
        elif op == "test":
            if "value" not in operation:
                raise ValueError(f"Operation #{op_idx} (test) is missing 'value'")
            expected = operation["value"]
            if not tokens:
                if work_doc != expected:
                    raise ValueError(f"Test failed at root. Expected {expected}, got {work_doc}")
                continue
            parent, key = navigate_pointer(work_doc, tokens)
            if isinstance(parent, dict):
                val = parent.get(key)
            elif isinstance(parent, list):
                assert isinstance(key, int)
                val = parent[key]
            else:
                val = None
                
            if val != expected:
                raise ValueError(f"Test failed at '{path}'. Expected {expected}, got {val}")
        else:
            raise ValueError(f"Unknown operation type '{op}' at index {op_idx}")
            
    return work_doc


def apply_json_merge_patch(doc: Any, patch: Any) -> Any:
    """Applies a JSON Merge Patch (RFC 7396) recursively."""
    if isinstance(patch, dict):
        if not isinstance(doc, dict):
            doc = {}
        for key, val in patch.items():
            if val is None:
                if key in doc:
                    del doc[key]
            else:
                doc[key] = apply_json_merge_patch(doc.get(key), val)
        return doc
    return copy.deepcopy(patch)


def generate_diff(orig: Any, mod: Any, path: str = "") -> List[Dict[str, Any]]:
    """Generates a list of JSON Patch operations to transform orig into mod."""
    patch = []
    
    if type(orig) != type(mod):
        patch.append({"op": "replace", "path": path or "/", "value": mod})
        return patch
        
    if isinstance(orig, dict):
        # Check removed keys
        for key in list(orig.keys()):
            if key not in mod:
                patch.append({"op": "remove", "path": f"{path}/{key.replace('~', '~0').replace('/', '~1')}"})
                
        # Check added or changed keys
        for key, val in mod.items():
            escaped_key = key.replace("~", "~0").replace("/", "~1")
            sub_path = f"{path}/{escaped_key}"
            if key not in orig:
                patch.append({"op": "add", "path": sub_path, "value": val})
            else:
                patch.extend(generate_diff(orig[key], val, sub_path))
                
    elif isinstance(orig, list):
        # Simplistic index-based list diffing. If size or items differ, replace.
        if orig != mod:
            patch.append({"op": "replace", "path": path or "/", "value": mod})
    else:
        if orig != mod:
            patch.append({"op": "replace", "path": path or "/", "value": mod})
            
    return patch


def generate_merge_patch(orig: Any, mod: Any) -> Any:
    """Generates a JSON Merge Patch (RFC 7396) object to transform orig into mod."""
    if not isinstance(orig, dict) or not isinstance(mod, dict):
        return copy.deepcopy(mod)
        
    patch = {}
    # Key removals
    for key in orig:
        if key not in mod:
            patch[key] = None
            
    # Key changes and additions
    for key, val in mod.items():
        if key not in orig:
            patch[key] = copy.deepcopy(val)
        else:
            diff = generate_merge_patch(orig[key], val)
            if orig[key] != val:
                patch[key] = diff
                
    return patch


def main():
    parser = argparse.ArgumentParser(
        description="JSON Patch (RFC 6902) & Merge Patch (RFC 7396) Utility CLI.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("target", help="Path to the target/original JSON file")
    parser.add_argument("patch_or_mod", help="Path to the patch file OR modified JSON file (if using --diff)")
    
    parser.add_argument("--type", "-t", choices=["patch", "merge"], default="patch",
                        help="Type of patch to apply: RFC 6902 JSON Patch ('patch') or RFC 7396 ('merge') (default: patch)")
    parser.add_argument("--diff", "-d", action="store_true", help="Generate a patch/diff between target and modified JSON files")
    parser.add_argument("--output", "-o", help="Save the patched JSON or generated patch to this file path")
    
    args = parser.parse_args()
    
    # Load original/target file
    try:
        with open(args.target, "r", encoding="utf-8") as f:
            target_data = json.load(f)
    except Exception as e:
        print_colored(f"[!] Error loading target JSON file '{args.target}': {e}", COLOR_FAIL)
        sys.exit(1)
        
    # Load patch or modified file
    try:
        with open(args.patch_or_mod, "r", encoding="utf-8") as f:
            patch_or_mod_data = json.load(f)
    except Exception as e:
        print_colored(f"[!] Error loading file '{args.patch_or_mod}': {e}", COLOR_FAIL)
        sys.exit(1)
        
    if args.diff:
        # Generate diff/patch
        print_colored(f"[*] Comparing target and modified JSON documents...", COLOR_CYAN)
        if args.type == "patch":
            result = generate_diff(target_data, patch_or_mod_data)
            patch_desc = "RFC 6902 JSON Patch"
        else:
            result = generate_merge_patch(target_data, patch_or_mod_data)
            patch_desc = "RFC 7396 JSON Merge Patch"
            
        formatted_json = json.dumps(result, indent=2)
        print_colored(f"\n[+] Generated {patch_desc}:", COLOR_GREEN)
        print(formatted_json)
        
        if args.output:
            try:
                with open(args.output, "w", encoding="utf-8") as f:
                    f.write(formatted_json)
                print_colored(f"\n[*] Patch saved to '{args.output}'", COLOR_BLUE)
            except Exception as e:
                print_colored(f"[!] Failed to save output: {e}", COLOR_FAIL)
    else:
        # Apply patch
        print_colored(f"[*] Applying patch of type '{args.type}'...", COLOR_CYAN)
        try:
            if args.type == "patch":
                if not isinstance(patch_or_mod_data, list):
                    raise TypeError("JSON Patch (RFC 6902) must be a JSON Array of patch operations.")
                result_data = apply_json_patch(target_data, patch_or_mod_data)
            else:
                result_data = apply_json_merge_patch(target_data, patch_or_mod_data)
                
            formatted_json = json.dumps(result_data, indent=2)
            print_colored("\n[+] Patch Applied Successfully. Result:", COLOR_GREEN)
            print(formatted_json)
            
            if args.output:
                try:
                    with open(args.output, "w", encoding="utf-8") as f:
                        f.write(formatted_json)
                    print_colored(f"\n[*] Output saved to '{args.output}'", COLOR_BLUE)
                except Exception as e:
                    print_colored(f"[!] Failed to save output: {e}", COLOR_FAIL)
        except Exception as e:
            print_colored(f"\n[!] Patch application failed: {e}", COLOR_FAIL)
            sys.exit(1)


if __name__ == "__main__":
    main()
