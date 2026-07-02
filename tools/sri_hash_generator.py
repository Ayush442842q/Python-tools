#!/usr/bin/env python3
"""
Subresource Integrity (SRI) Hash Generator & Auditor

Scans HTML files, extracts stylesheet and script resources (local and remote),
calculates their Subresource Integrity (SRI) hashes (SHA-256, SHA-384, SHA-512),
and checks or updates the HTML files with the correct 'integrity' and 'crossorigin' attributes.

Usage:
    python tools/sri_hash_generator.py path/to/index.html [options]
    python tools/sri_hash_generator.py -d ./templates --write
"""

import argparse
import base64
import hashlib
import os
import re
import sys
import urllib.request
import urllib.error
from html.parser import HTMLParser
from typing import Dict, List, Optional, Tuple

class AssetParser(HTMLParser):
    """HTML Parser to extract script and stylesheet tag positions and attributes."""
    def __init__(self) -> None:
        super().__init__()
        # List of tags: (tag_name, attrs_dict, start_pos, end_pos)
        self.tags: List[Tuple[str, Dict[str, str], int, int]] = []
        self._raw_html: str = ""

    def feed_html(self, html: str) -> None:
        self._raw_html = html
        self.tags.clear()
        self.feed(html)

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        attrs_dict = {k: v for k, v in attrs if v is not None}
        
        # We only care about script tags with 'src' and link tags with 'rel="stylesheet"' and 'href'
        if tag == "script" and "src" in attrs_dict:
            pos = self.getpos()  # (line, offset)
            self._record_tag(tag, attrs_dict, pos)
        elif tag == "link" and attrs_dict.get("rel") == "stylesheet" and "href" in attrs_dict:
            pos = self.getpos()
            self._record_tag(tag, attrs_dict, pos)

    def _record_tag(self, tag: str, attrs_dict: Dict[str, str], pos: Tuple[int, int]) -> None:
        # Calculate character index from line and offset
        line_num, offset = pos
        lines = self._raw_html.splitlines(keepends=True)
        char_idx = sum(len(lines[i]) for i in range(line_num - 1)) + offset
        
        # Find the end of this start tag
        tag_str = self._raw_html[char_idx:]
        match = re.match(r"^<[^>]+>", tag_str)
        if match:
            end_idx = char_idx + len(match.group(0))
            self.tags.append((tag, attrs_dict, char_idx, end_idx))

def calculate_sri_hash(content: bytes, algorithm: str) -> str:
    """Calculate the SRI hash value for the given content."""
    if algorithm == "sha256":
        hasher = hashlib.sha256()
    elif algorithm == "sha384":
        hasher = hashlib.sha384()
    elif algorithm == "sha512":
        hasher = hashlib.sha512()
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")
    
    hasher.update(content)
    digest = hasher.digest()
    encoded = base64.b64encode(digest).decode("utf-8")
    return f"{algorithm}-{encoded}"

def fetch_asset(path: str, html_dir: str, verbose: bool = False) -> Tuple[Optional[bytes], str]:
    """Fetch/read the asset content. Returns (content_bytes, source_description)."""
    # Remote URL
    if path.startswith(("http://", "https://", "//")):
        url = "https:" + path if path.startswith("//") else path
        if verbose:
            print(f"  Fetching remote asset: {url}")
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SRI-Generator/1.0"}
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.read(), f"Remote: {url}"
        except urllib.error.URLError as e:
            return None, f"Remote Fail: {url} ({str(e)})"
        except Exception as e:
            return None, f"Remote Fail: {url} ({str(e)})"
    
    # Local file
    else:
        # Resolve path relative to HTML file directory
        clean_path = path.split("?")[0].split("#")[0]  # Remove query/anchor params
        local_path = os.path.normpath(os.path.join(html_dir, clean_path))
        if verbose:
            print(f"  Reading local asset: {local_path}")
        
        if not os.path.exists(local_path):
            return None, f"Local Missing: {local_path}"
        
        try:
            with open(local_path, "rb") as f:
                return f.read(), f"Local: {local_path}"
        except Exception as e:
            return None, f"Local Fail: {local_path} ({str(e)})"

def process_html_file(filepath: str, algo: str, write: bool, crossorigin: str, remote_only: bool, local_only: bool, verbose: bool) -> bool:
    """Process a single HTML file to audit or inject SRI hashes."""
    print(f"\nScanning: {filepath}")
    
    try:
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            html_content = f.read()
    except Exception as e:
        print(f"Error reading file '{filepath}': {e}", file=sys.stderr)
        return False

    html_dir = os.path.dirname(os.path.abspath(filepath))
    parser = AssetParser()
    parser.feed_html(html_content)

    if not parser.tags:
        print("  No script or stylesheet tags found.")
        return True

    # Process tags in reverse order to preserve char offsets during replacement
    modified_content = html_content
    any_changes = False
    
    ok_count = 0
    mismatch_count = 0
    added_count = 0
    failed_count = 0

    for tag, attrs, start, end in reversed(parser.tags):
        src_attr = "src" if tag == "script" else "href"
        asset_path = attrs[src_attr]
        
        is_remote = asset_path.startswith(("http://", "https://", "//"))
        if remote_only and not is_remote:
            continue
        if local_only and is_remote:
            continue

        content, src_desc = fetch_asset(asset_path, html_dir, verbose)
        if content is None:
            print(f"  [FAIL] Could not retrieve: {asset_path} ({src_desc})")
            failed_count += 1
            continue

        actual_hash = calculate_sri_hash(content, algo)
        current_integrity = attrs.get("integrity", "")
        
        # Check integrity
        needs_update = False
        status_msg = ""
        
        if not current_integrity:
            status_msg = f"Missing integrity. Calculated: {actual_hash}"
            needs_update = True
            added_count += 1
        else:
            # Check if actual hash is in the integrity attribute (it can contain multiple hashes separated by spaces)
            hashes_present = current_integrity.split()
            if actual_hash in hashes_present:
                status_msg = "Integrity match [OK]"
                ok_count += 1
            else:
                status_msg = f"Mismatch! Current: '{current_integrity}' | Expected: '{actual_hash}'"
                needs_update = True
                mismatch_count += 1

        print(f"  <{tag} {src_attr}=\"{asset_path}\">: {status_msg}")

        if needs_update and (write or not write):
            # Check crossorigin attribute
            current_crossorigin = attrs.get("crossorigin")
            
            # Construct updated tag
            raw_tag = html_content[start:end]
            
            # Build attributes string
            new_attrs = []
            for k, v in attrs.items():
                if k in ("integrity", "crossorigin"):
                    continue
                new_attrs.append(f'{k}="{v}"')
            
            new_attrs.append(f'integrity="{actual_hash}"')
            if crossorigin:
                new_attrs.append(f'crossorigin="{crossorigin}"')
            
            # Form final tag
            if raw_tag.endswith("/>"):
                updated_tag = f"<{tag} {' '.join(new_attrs)} />"
            else:
                updated_tag = f"<{tag} {' '.join(new_attrs)}>"

            modified_content = modified_content[:start] + updated_tag + modified_content[end:]
            any_changes = True

    # Save changes if requested
    if any_changes and write:
        try:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(modified_content)
            print(f"  [SAVED] File updated successfully.")
        except Exception as e:
            print(f"  [ERROR] Failed to save changes: {e}", file=sys.stderr)
    elif any_changes:
        print(f"  [DRY-RUN] Changes detected. Run with --write to apply.")
    else:
        print(f"  [NO CHANGES] All checked resources are compliant.")

    print(f"  Summary: OK: {ok_count} | Added: {added_count} | Mismatch: {mismatch_count} | Failed: {failed_count}")
    return True

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Subresource Integrity (SRI) Hash Generator & Auditor"
    )
    parser.add_argument(
        "files", nargs="*", help="HTML files to audit/update"
    )
    parser.add_argument(
        "-d", "--directory", help="Search directory recursively for HTML files"
    )
    parser.add_argument(
        "-a", "--algorithm", choices=["sha256", "sha384", "sha512"], default="sha384",
        help="SRI hash algorithm (default: sha384)"
    )
    parser.add_argument(
        "-w", "--write", action="store_true",
        help="Write/overwrite integrity attributes directly to the HTML files"
    )
    parser.add_argument(
        "--crossorigin", choices=["anonymous", "use-credentials", ""], default="anonymous",
        help="Value for crossorigin attribute (default: anonymous)"
    )
    parser.add_argument(
        "--remote-only", action="store_true", help="Only check remote scripts/stylesheets"
    )
    parser.add_argument(
        "--local-only", action="store_true", help="Only check local scripts/stylesheets"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Output detailed network/disk operations"
    )

    args = parser.parse_args()

    # Collect HTML files
    html_files = []
    if args.directory:
        if not os.path.isdir(args.directory):
            print(f"Error: Directory '{args.directory}' does not exist.", file=sys.stderr)
            sys.exit(1)
        for root, _, files in os.walk(args.directory):
            for file in files:
                if file.lower().endswith((".html", ".htm")):
                    html_files.append(os.path.join(root, file))
    
    for f in args.files:
        if os.path.isfile(f):
            html_files.append(f)
        else:
            print(f"Warning: File '{f}' not found, skipping.", file=sys.stderr)

    if not html_files:
        print("Error: No HTML files specified or found in directory.", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    print("=" * 60)
    print(" SUBRESOURCE INTEGRITY (SRI) AUDITOR & GENERATOR")
    print(f" Mode: {'WRITE (Modifying HTML files)' if args.write else 'AUDIT ONLY (Dry Run)'}")
    print(f" Target Hash Algorithm: {args.algorithm}")
    print("=" * 60)

    success = True
    for file in html_files:
        if not process_html_file(file, args.algorithm, args.write, args.crossorigin, args.remote_only, args.local_only, args.verbose):
            success = False

    print("\nProcessing complete.")
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
