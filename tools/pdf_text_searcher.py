#!/usr/bin/env python3
"""
PDF Text Searcher
Recursively searches for text patterns or regular expressions inside all PDF files
in a directory, displaying matching page numbers and line snippets with highlighting.
Uses pypdf if available, otherwise falls back to a custom zero-dependency PDF text stream parser.
"""

import argparse
import os
import re
import sys
import zlib
from typing import Iterator, List, Tuple

# Try importing standard PDF libraries
try:
    import pypdf
    HAS_PYPDF = True
except ImportError:
    try:
        import PyPDF2 as pypdf  # type: ignore
        HAS_PYPDF = True
    except ImportError:
        HAS_PYPDF = False


class FallbackPDFParser:
    """Zero-dependency basic PDF parser for extracting plain text from streams."""

    @staticmethod
    def extract_text(file_path: str) -> List[Tuple[int, str]]:
        """
        Attempts to extract plain text from non-encrypted PDFs by scanning content streams.
        Returns a list of tuples containing (page_number_approx, text_content).
        """
        pages = []
        try:
            with open(file_path, "rb") as f:
                data = f.read()
        except Exception as e:
            print(f"Error reading file {file_path}: {e}", file=sys.stderr)
            return []

        # Locate streams
        start = 0
        streams = []
        while True:
            stream_start = data.find(b"stream", start)
            if stream_start == -1:
                break
            
            content_start = stream_start + 6
            if data[content_start : content_start + 2] == b"\r\n":
                content_start += 2
            elif data[content_start : content_start + 1] == b"\n":
                content_start += 1

            stream_end = data.find(b"endstream", content_start)
            if stream_end == -1:
                break

            content_end = stream_end
            if data[content_end - 2 : content_end] == b"\r\n":
                content_end -= 2
            elif data[content_end - 1 : content_end] == b"\n":
                content_end -= 1

            streams.append(data[content_start:content_end])
            start = stream_end + 9

        # Parse text from streams
        current_page_text = []
        page_counter = 1

        for s in streams:
            try:
                decompressed = zlib.decompress(s)
            except Exception:
                decompressed = s

            # Decode latin1 to preserve byte values but work as text string
            text_str = decompressed.decode("latin1", errors="ignore")
            
            # Simple check to see if we reached a page transition indicator
            if "/Page" in text_str and current_page_text:
                pages.append((page_counter, "\n".join(current_page_text)))
                current_page_text = []
                page_counter += 1

            # Extract Tj/TJ strings within BT...ET blocks
            bt_et_blocks = re.findall(r"BT\s+(.*?)\s+ET", text_str, re.DOTALL)
            for block in bt_et_blocks:
                strings = re.findall(r"\(([^)]*)\)", block)
                cleaned = []
                for s_val in strings:
                    # Clean simple escapes
                    s_val = s_val.replace("\\(", "(").replace("\\)", ")").replace("\\\\", "\\")
                    # Remove octal representation markers if any
                    s_val = re.sub(r"\\\d{3}", "", s_val)
                    cleaned.append(s_val)
                if cleaned:
                    current_page_text.append(" ".join(cleaned))

        if current_page_text:
            pages.append((page_counter, "\n".join(current_page_text)))

        return pages


def extract_pdf_pages(file_path: str) -> List[Tuple[int, str]]:
    """Extracts text from PDF, returning a list of (page_num, text) tuples."""
    if HAS_PYPDF:
        try:
            pages = []
            with open(file_path, "rb") as f:
                reader = pypdf.PdfReader(f)
                for idx, page in enumerate(reader.pages):
                    text = page.extract_text() or ""
                    pages.append((idx + 1, text))
            return pages
        except Exception as e:
            # Fallback to custom parser on failure
            return FallbackPDFParser.extract_text(file_path)
    else:
        return FallbackPDFParser.extract_text(file_path)


def search_pdf(file_path: str, query: str, is_regex: bool, case_insensitive: bool) -> List[Tuple[int, int, str]]:
    """
    Searches a PDF file for matches.
    Returns list of tuples: (page_num, line_num, line_content)
    """
    matches = []
    pages = extract_pdf_pages(file_path)
    
    flags = re.IGNORECASE if case_insensitive else 0
    if is_regex:
        try:
            pattern = re.compile(query, flags)
        except re.error as e:
            print(f"Invalid regex pattern '{query}': {e}", file=sys.stderr)
            sys.exit(1)
    else:
        pattern = re.compile(re.escape(query), flags)

    for page_num, text in pages:
        lines = text.splitlines()
        for line_num, line in enumerate(lines, 1):
            if pattern.search(line):
                matches.append((page_num, line_num, line.strip()))
                
    return matches


def highlight_match(text: str, query: str, is_regex: bool, case_insensitive: bool) -> str:
    """Applies ANSI terminal escape codes to highlight matches."""
    if not sys.stdout.isatty():
        return text

    flags = re.IGNORECASE if case_insensitive else 0
    if is_regex:
        pattern = re.compile(f"({query})", flags)
    else:
        pattern = re.compile(f"({re.escape(query)})", flags)

    # Highlight color: Light Red background or Yellow text
    return pattern.sub(r"\033[93m\033[1m\1\033[0m", text)


def find_pdf_files(directory: str) -> Iterator[str]:
    """Finds all PDF files recursively in directory."""
    for root, _, files in os.walk(directory):
        for file in files:
            if file.lower().endswith(".pdf"):
                yield os.path.join(root, file)


def main():
    parser = argparse.ArgumentParser(
        description="Search for text patterns recursively inside PDF files."
    )
    parser.add_argument("query", help="Text or regex pattern to search for")
    parser.add_argument("path", nargs="?", default=".", help="Directory or file path to search (default: current directory)")
    parser.add_argument("-r", "--regex", action="store_true", help="Treat query as a regular expression")
    parser.add_argument("-i", "--ignore-case", action="store_true", help="Perform case-insensitive search")
    parser.add_argument("-s", "--silent", action="store_true", help="Suppress status and header messages, only output matches")

    args = parser.parse_args()

    if not os.path.exists(args.path):
        print(f"Path not found: {args.path}", file=sys.stderr)
        sys.exit(1)

    pdf_files = []
    if os.path.isdir(args.path):
        pdf_files = list(find_pdf_files(args.path))
    elif args.path.lower().endswith(".pdf"):
        pdf_files = [args.path]

    if not pdf_files:
        if not args.silent:
            print("No PDF files found to search.")
        sys.exit(0)

    if not args.silent:
        if HAS_PYPDF:
            print(f"Search engine: pypdf library")
        else:
            print(f"Search engine: Built-in raw stream parser (Fallback mode; run 'pip install pypdf' for full Unicode support)")
        print(f"Searching for '{args.query}' in {len(pdf_files)} PDF file(s)...")
        print("=" * 80)

    total_matches = 0
    total_files_with_matches = 0

    for pdf_file in pdf_files:
        try:
            matches = search_pdf(pdf_file, args.query, args.regex, args.ignore_case)
            if matches:
                total_files_with_matches += 1
                total_matches += len(matches)
                relative_path = os.path.relpath(pdf_file)
                print(f"\nFile: {relative_path}")
                print("-" * len(f"File: {relative_path}"))
                for page, line, text in matches:
                    highlighted_text = highlight_match(text, args.query, args.regex, args.ignore_case)
                    print(f"  Page {page:3d} (Line {line:3d}): {highlighted_text}")
        except Exception as e:
            print(f"Error processing {pdf_file}: {e}", file=sys.stderr)

    if not args.silent:
        print("\n" + "=" * 80)
        print(f"Search complete. Found {total_matches} match(es) across {total_files_with_matches} file(s).")


if __name__ == "__main__":
    main()
