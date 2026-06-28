#!/usr/bin/env python3
"""
Markdown Document Compiler - Compile multiple markdown files into a single master document.

Features:
  - Consolidates multiple markdown files in an ordered directory structure.
  - Resolves local cross-document links into internal page anchors.
  - Shifts heading levels (# -> ##) dynamically based on document nesting depth.
  - Auto-generates a global Table of Contents (TOC) with correct anchor links.
  - Option to strip YAML frontmatter blocks from individual files during compilation.
"""

import os
import re
import sys
import argparse

# ANSI color codes
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"
COLOR_RESET = "\033[0m"

class MarkdownCompiler:
    def __init__(self, input_dir, output_file, manifest_path=None, shift_headers=True, add_toc=True, strip_frontmatter=True):
        self.input_dir = input_dir
        self.output_file = output_file
        self.manifest_path = manifest_path
        self.shift_headers = shift_headers
        self.add_toc = add_toc
        self.strip_frontmatter = strip_frontmatter
        self.files_to_process = []
        self.anchor_mappings = {}  # maps original filename -> anchor slug of its first heading or slugified name

    def get_slug(self, text):
        """Convert a heading text into a markdown anchor-friendly slug."""
        text = text.lower().strip()
        text = re.sub(r'[^\w\s-]', '', text)  # remove non-alphanumeric/non-space/non-dash
        text = re.sub(r'[-\s]+', '-', text)  # replace spaces and dashes with a single dash
        return text

    def discover_files(self):
        """Determine the list of markdown files and their compilation order."""
        if self.manifest_path and os.path.exists(self.manifest_path):
            print(f"Reading compilation order from manifest: {COLOR_CYAN}{self.manifest_path}{COLOR_RESET}")
            try:
                with open(self.manifest_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#'):
                            full_path = os.path.join(self.input_dir, line)
                            if os.path.exists(full_path):
                                self.files_to_process.append(full_path)
                            else:
                                print(f"{COLOR_YELLOW}Warning: File from manifest not found: {line}{COLOR_RESET}", file=sys.stderr)
                return True
            except Exception as e:
                print(f"Error reading manifest: {e}", file=sys.stderr)
                return False

        # Auto-discovery
        print(f"Auto-discovering markdown files in: {COLOR_CYAN}{self.input_dir}{COLOR_RESET}")
        md_files = []
        for root, _, files in os.walk(self.input_dir):
            for file in files:
                if file.lower().endswith(('.md', '.markdown')):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, self.input_dir)
                    md_files.append((rel_path, full_path))

        if not md_files:
            print(f"{COLOR_RED}Error: No markdown files found in '{self.input_dir}'.{COLOR_RESET}", file=sys.stderr)
            return False

        # Sort files: first by numeric prefixes (01_, 02_ etc.) then alphabetically
        def sort_key(item):
            rel_path = item[0]
            parts = rel_path.split(os.sep)
            key_parts = []
            for part in parts:
                match = re.match(r'^(\d+)', part)
                if match:
                    key_parts.append((0, int(match.group(1)), part))
                else:
                    key_parts.append((1, 0, part))
            return key_parts

        md_files.sort(key=sort_key)
        self.files_to_process = [item[1] for item in md_files]
        print(f"Discovered {len(self.files_to_process)} markdown files.")
        return True

    def scan_anchors(self):
        """First pass: build mappings from filenames to their primary header anchor slugs."""
        for file in self.files_to_process:
            rel_path = os.path.relpath(file, self.input_dir)
            base_name = os.path.basename(file)
            
            # Default slug is based on filename
            primary_slug = self.get_slug(os.path.splitext(base_name)[0])
            
            # Try to find first header
            try:
                with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                    in_frontmatter = False
                    for line in f:
                        if self.strip_frontmatter:
                            if line.strip() == "---":
                                in_frontmatter = not in_frontmatter
                                continue
                            if in_frontmatter:
                                continue
                        
                        match = re.match(r'^(#+)\s+(.+)$', line)
                        if match:
                            header_text = match.group(2).strip()
                            primary_slug = self.get_slug(header_text)
                            break
            except Exception:
                pass
            
            self.anchor_mappings[rel_path.replace('\\', '/')] = primary_slug
            self.anchor_mappings[base_name] = primary_slug

    def compile(self):
        if not self.files_to_process:
            return False

        self.scan_anchors()
        compiled_sections = []
        
        # Track headers for Table of Contents
        headers_toc = []

        print("Compiling files...")
        for idx, file in enumerate(self.files_to_process):
            rel_path = os.path.relpath(file, self.input_dir)
            rel_path_unix = rel_path.replace('\\', '/')
            print(f"  [{idx+1}/{len(self.files_to_process)}] Processing: {COLOR_CYAN}{rel_path}{COLOR_RESET}")

            # Calculate heading offset based on subdirectory depth
            depth = len(rel_path.split(os.sep)) - 1
            header_offset = depth if self.shift_headers else 0

            section_lines = []
            try:
                with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception as e:
                print(f"{COLOR_RED}Error reading {file}: {e}{COLOR_RESET}", file=sys.stderr)
                continue

            # Strip frontmatter
            if self.strip_frontmatter and content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    content = parts[2]

            # Process line by line
            lines = content.splitlines()
            for line in lines:
                # 1. Shift headers
                header_match = re.match(r'^(#+)\s+(.+)$', line)
                if header_match:
                    hashes = header_match.group(1)
                    title = header_match.group(2).strip()
                    new_hashes = hashes + ('#' * header_offset)
                    # Limit to max 6 markdown hashes
                    if len(new_hashes) > 6:
                        new_hashes = '#' * 6
                    
                    line = f"{new_hashes} {title}"
                    headers_toc.append((len(new_hashes), title, self.get_slug(title)))

                # 2. Rewrite cross-document markdown links
                # Matches links like [Label](path/to/file.md#anchor) or [Label](file.md)
                link_matches = re.finditer(r'\[([^\]]+)\]\(([^)]+)\)', line)
                for match in link_matches:
                    label = match.group(1)
                    href = match.group(2)
                    
                    # Check if link points to local markdown file
                    # Matches local md files, possibly with relative pathing and internal anchors
                    parsed_href = urlparse(href)
                    if not parsed_href.scheme and parsed_href.path.lower().endswith(('.md', '.markdown')):
                        path_part = parsed_href.path
                        anchor_part = parsed_href.fragment
                        
                        # Resolve path relative to current file's directory
                        curr_dir = os.path.dirname(rel_path_unix)
                        resolved_path = urljoin(curr_dir + "/", path_part)
                        resolved_path = os.path.normpath(resolved_path).replace('\\', '/')
                        
                        # Clean leading dots
                        resolved_path = resolved_path.lstrip('./')
                        
                        # Find mapping slug
                        new_anchor = anchor_part
                        if not new_anchor:
                            # Map to the file's primary heading
                            new_anchor = self.anchor_mappings.get(resolved_path, self.anchor_mappings.get(os.path.basename(resolved_path), ""))
                        
                        if new_anchor:
                            new_href = f"#{new_anchor}"
                            line = line.replace(f"({href})", f"({new_href})")
                            
                section_lines.append(line)

            compiled_sections.append("\n".join(section_lines))

        # Combine
        full_document = "\n\n".join(compiled_sections)

        # Build TOC
        if self.add_toc and headers_toc:
            print("Generating Table of Contents...")
            toc_lines = ["# Table of Contents\n"]
            for level, title, slug in headers_toc:
                # Indent based on heading level
                indent = "  " * (level - 1)
                toc_lines.append(f"{indent}- [{title}](#{slug})")
            
            toc_string = "\n".join(toc_lines)
            full_document = toc_string + "\n\n---\n\n" + full_document

        # Write output
        try:
            # Ensure output directory exists
            out_dir = os.path.dirname(self.output_file)
            if out_dir and not os.path.exists(out_dir):
                os.makedirs(out_dir, exist_ok=True)
                
            with open(self.output_file, 'w', encoding='utf-8') as f:
                f.write(full_document)
            print(f"\n{COLOR_GREEN}✓ Compilation completed successfully!{COLOR_RESET}")
            print(f"Master file: {COLOR_CYAN}{self.output_file}{COLOR_RESET}")
            return True
        except Exception as e:
            print(f"{COLOR_RED}Error writing output file: {e}{COLOR_RESET}", file=sys.stderr)
            return False

def main():
    parser = argparse.ArgumentParser(description="Compile multiple markdown files into a single master document.")
    parser.add_argument("-i", "--input", required=True, help="Directory containing markdown files to compile")
    parser.add_argument("-o", "--output", required=True, help="Output filename for the compiled markdown document")
    parser.add_argument("-m", "--manifest", help="Optional text file listing the ordered files to compile (one relative path per line)")
    parser.add_argument("--no-shift", action="store_true", help="Do not shift heading levels based on directory nesting depth")
    parser.add_argument("--no-toc", action="store_true", help="Do not generate a global Table of Contents")
    parser.add_argument("--keep-frontmatter", action="store_true", help="Do not strip YAML frontmatter blocks from individual files")

    args = parser.parse_args()

    compiler = MarkdownCompiler(
        input_dir=args.input,
        output_file=args.output,
        manifest_path=args.manifest,
        shift_headers=not args.no_shift,
        add_toc=not args.no_toc,
        strip_frontmatter=not args.keep_frontmatter
    )

    if not compiler.discover_files():
        sys.exit(1)

    if not compiler.compile():
        sys.exit(1)

if __name__ == "__main__":
    main()
