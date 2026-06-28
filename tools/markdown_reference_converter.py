#!/usr/bin/env python3
"""
Markdown Link Reference Converter
Converts inline Markdown links `[text](url)` to reference-style links `[text][ref]`
and places reference definitions at the end of the document, or vice-versa.
Includes options to clean up unused references, sort definitions, and format output.
Uses standard libraries only.
"""

import argparse
import re
import sys
import urllib.parse
from typing import Dict, List, Set, Tuple, Optional

# Match inline links: [text](url) or ![alt](url) (ignoring escaped brackets)
# Avoid matching inline links inside code blocks (we'll do a simple code block skipper)
INLINE_LINK_RE = re.compile(r'(!?)\[([^\]]+)\]\(([^)]+)\)')

# Match reference links: [text][ref] or [text][]
REF_LINK_RE = re.compile(r'(!?)\[([^\]]+)\]\[([^\]]*)\]')

# Match reference definition lines: [ref]: url "title"
REF_DEF_RE = re.compile(r'^\[([^\]]+)\]:\s*(\S+)(?:\s+[\'"]([^\'"]+)[\'"])?\s*$', re.MULTILINE)

def slugify(text: str) -> str:
    """Creates a clean identifier from link text or URL domain."""
    # Try to extract domain name if it looks like a URL
    if text.startswith(('http://', 'https://')):
        try:
            parsed = urllib.parse.urlparse(text)
            text = parsed.netloc.replace('www.', '')
        except Exception:
            pass
            
    # Clean non-alphanumeric chars
    slug = re.sub(r'[^a-zA-Z0-9\-]', '', text.replace(' ', '-').lower())
    slug = re.sub(r'-+', '-', slug).strip('-')
    return slug or "link"


class MarkdownReferenceConverter:
    """Converts Markdown documents between inline and reference link formats."""
    def __init__(self, use_numbers: bool = False, prefix: str = "ref-"):
        self.use_numbers = use_numbers
        self.prefix = prefix
        self.ref_counter = 1
        
    def _strip_code_blocks(self, text: str) -> Tuple[str, List[str]]:
        """Temporarily replaces code blocks with placeholders to avoid modifying links inside code."""
        placeholders = []
        
        # Helper to store block and return placeholder
        def repl(match):
            placeholder = f"<!--CODE_BLOCK_PLACEHOLDER_{len(placeholders)}-->"
            placeholders.append(match.group(0))
            return placeholder

        # Match multiline code blocks ```...```
        text_no_blocks = re.sub(r'(```[a-zA-Z]*\n[\s\S]*?\n```)', repl, text)
        # Match inline code `...`
        text_no_blocks = re.sub(r'(`[^`\n]+`)', repl, text_no_blocks)
        
        return text_no_blocks, placeholders

    def _restore_code_blocks(self, text: str, placeholders: List[str]) -> str:
        """Restores code blocks back from placeholders."""
        for i, block in enumerate(placeholders):
            placeholder = f"<!--CODE_BLOCK_PLACEHOLDER_{i}-->"
            text = text.replace(placeholder, block)
        return text

    def convert_to_reference(self, text: str) -> str:
        """Converts all inline links to reference-style links."""
        # 1. Strip code blocks
        working_text, code_blocks = self._strip_code_blocks(text)
        
        # 2. Extract existing reference definitions
        existing_refs = {}
        for match in REF_DEF_RE.finditer(working_text):
            ref_id = match.group(1).strip().lower()
            url = match.group(2).strip()
            title = match.group(3) or ""
            existing_refs[ref_id] = (url, title)
            
        # Remove existing reference lines from working text
        working_text = REF_DEF_RE.sub('', working_text)
        
        # Map URL -> Reference ID
        url_to_id = {}
        # Prepopulate with existing references
        for ref_id, (url, title) in existing_refs.items():
            url_to_id[(url, title)] = ref_id
            
        new_refs = existing_refs.copy()
        
        def replace_inline(match):
            is_image = match.group(1)  # '!' or ''
            link_text = match.group(2)
            url_part = match.group(3).strip()
            
            # Separate URL and optional title, e.g. "https://google.com 'Google Search'"
            url = url_part
            title = ""
            title_match = re.search(r'\s+[\'"]([^\'"]+)[\'"]$', url_part)
            if title_match:
                title = title_match.group(1)
                url = url_part[:title_match.start()].strip()
                
            key = (url, title)
            
            if key not in url_to_id:
                # Generate unique ID
                if self.use_numbers:
                    ref_id = str(self.ref_counter)
                    self.ref_counter += 1
                    # Ensure no collision with pre-existing refs
                    while ref_id.lower() in new_refs:
                        ref_id = str(self.ref_counter)
                        self.ref_counter += 1
                else:
                    base_id = self.prefix + slugify(link_text or url)
                    ref_id = base_id
                    counter = 1
                    while ref_id.lower() in new_refs:
                        ref_id = f"{base_id}-{counter}"
                        counter += 1
                        
                url_to_id[key] = ref_id
                new_refs[ref_id.lower()] = (url, title)
            else:
                ref_id = url_to_id[key]
                
            # Replace inline link with reference link
            return f"{is_image}[{link_text}][{ref_id}]"

        # Replace all inline links
        converted_text = INLINE_LINK_RE.sub(replace_inline, working_text)
        
        # Clean trailing empty lines
        converted_text = converted_text.rstrip()
        
        # Append reference list at the bottom
        if new_refs:
            converted_text += "\n\n"
            # Sort references based on key
            for ref_id in sorted(new_refs.keys()):
                url, title = new_refs[ref_id]
                title_str = f' "{title}"' if title else ""
                converted_text += f"[{ref_id}]: {url}{title_str}\n"
                
        # Restore code blocks
        final_text = self._restore_code_blocks(converted_text, code_blocks)
        return final_text

    def convert_to_inline(self, text: str) -> str:
        """Converts all reference-style links back to inline links."""
        # 1. Strip code blocks
        working_text, code_blocks = self._strip_code_blocks(text)
        
        # 2. Extract reference definitions
        refs = {}
        for match in REF_DEF_RE.finditer(working_text):
            ref_id = match.group(1).strip().lower()
            url = match.group(2).strip()
            title = match.group(3) or ""
            refs[ref_id] = (url, title)
            
        # Remove reference lines
        working_text = REF_DEF_RE.sub('', working_text)
        
        def replace_ref(match):
            is_image = match.group(1)
            link_text = match.group(2)
            ref_id = match.group(3).strip().lower()
            
            # If [text][] is used, the reference ID is the link text itself
            if not ref_id:
                ref_id = link_text.strip().lower()
                
            if ref_id in refs:
                url, title = refs[ref_id]
                title_str = f' "{title}"' if title else ""
                return f"{is_image}[{link_text}]({url}{title_str})"
            else:
                # Keep unchanged if definition not found
                return match.group(0)

        # Replace reference links with inline links
        converted_text = REF_LINK_RE.sub(replace_ref, working_text)
        
        # Restore code blocks
        final_text = self._restore_code_blocks(converted_text, code_blocks)
        return final_text

    def clean_and_sort_references(self, text: str, sort_by_appearance: bool = False) -> str:
        """Removes unused references and sorts the reference list."""
        working_text, code_blocks = self._strip_code_blocks(text)
        
        # Extract references
        refs = {}
        for match in REF_DEF_RE.finditer(working_text):
            ref_id = match.group(1).strip().lower()
            url = match.group(2).strip()
            title = match.group(3) or ""
            refs[ref_id] = (url, title)
            
        # Strip references lines
        working_text = REF_DEF_RE.sub('', working_text)
        
        # Find all used reference IDs in document body
        used_ids = []
        used_ids_set = set()
        
        for match in REF_LINK_RE.finditer(working_text):
            ref_id = match.group(3).strip().lower()
            if not ref_id:
                ref_id = match.group(2).strip().lower()
            if ref_id in refs and ref_id not in used_ids_set:
                used_ids.append(ref_id)
                used_ids_set.add(ref_id)
                
        # Remove reference lines
        working_text = working_text.rstrip()
        
        if used_ids:
            working_text += "\n\n"
            # Choose sorting method
            sorted_ids = used_ids if sort_by_appearance else sorted(list(used_ids))
            
            for ref_id in sorted_ids:
                url, title = refs[ref_id]
                title_str = f' "{title}"' if title else ""
                working_text += f"[{ref_id}]: {url}{title_str}\n"
                
        final_text = self._restore_code_blocks(working_text, code_blocks)
        return final_text


def main():
    parser = argparse.ArgumentParser(
        description="Markdown Link Reference Converter - Restructures links in Markdown documents."
    )
    parser.add_argument("file", help="Input Markdown file path")
    parser.add_argument(
        "-m", "--mode",
        choices=["reference", "inline", "clean"],
        default="reference",
        help="Reformatting mode (default: reference)"
    )
    parser.add_argument(
        "-n", "--numbers",
        action="store_true",
        help="Use sequential numbers [1], [2]... for reference IDs instead of slugs (reference mode)"
    )
    parser.add_argument(
        "-p", "--prefix",
        default="ref-",
        help="Prefix to prepend to reference IDs (default: ref-)"
    )
    parser.add_argument(
        "-s", "--sort-by-appearance",
        action="store_true",
        help="Sort trailing reference list by order of appearance in text instead of alphabetically (reference/clean mode)"
    )
    parser.add_argument(
        "-i", "--in-place",
        dest="in_place",
        action="store_true",
        help="Overwrite input file directly"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file path (prints to stdout if omitted and not in-place)"
    )

    args = parser.parse_args()

    # Read input file
    try:
        with open(args.file, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception as e:
        print(f"[-] Error reading file {args.file}: {e}", file=sys.stderr)
        return 1

    converter = MarkdownReferenceConverter(use_numbers=args.numbers, prefix=args.prefix)
    
    # Process
    if args.mode == "reference":
        result = converter.convert_to_reference(content)
    elif args.mode == "inline":
        result = converter.convert_to_inline(content)
    elif args.mode == "clean":
        result = converter.clean_and_sort_references(content, sort_by_appearance=args.sort_by_appearance)
    else:
        result = content

    # Write output
    if args.in_place:
        try:
            with open(args.file, 'w', encoding='utf-8') as f:
                f.write(result)
            print(f"[+] Successfully updated {args.file} in-place.")
        except Exception as e:
            print(f"[-] Error writing file {args.file}: {e}", file=sys.stderr)
            return 1
    elif args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(result)
            print(f"[+] Output written to {args.output}")
        except Exception as e:
            print(f"[-] Error writing file {args.output}: {e}", file=sys.stderr)
            return 1
    else:
        # Print to stdout
        sys.stdout.write(result)

    return 0

if __name__ == "__main__":
    sys.exit(main())
