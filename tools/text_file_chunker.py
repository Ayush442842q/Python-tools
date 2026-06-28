#!/usr/bin/env python3
"""
Text File Chunker
Splits large text files (documents, code, logs) into smaller overlapping chunks,
ideal for preparing inputs for Large Language Models (LLMs) or retrieval systems (RAG).
Supports simple, paragraph, Markdown header-aware, and code block-aware splitting strategies.
"""

import argparse
import os
import re
import sys
from typing import List, Dict

# Reconfigure stdout to UTF-8 on Windows to support outputting Unicode content
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass


def safe_print(text: str, end: str = "\n"):
    """Prints text using the configured encoding, replacing unencodable characters."""
    try:
        sys.stdout.write(text + end)
    except UnicodeEncodeError:
        # Fallback by encoding to stdout's encoding with backslashreplace or replace
        encoding = sys.stdout.encoding or "utf-8"
        encoded = text.encode(encoding, errors="replace")
        sys.stdout.buffer.write(encoded + end.encode(encoding))


def chunk_by_characters(text: str, chunk_size: int, overlap: int) -> List[str]:
    """Splits text by character count with a sliding window overlap."""
    if chunk_size <= 0:
        return [text]
    
    chunks = []
    start = 0
    text_len = len(text)
    
    while start < text_len:
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        # Advance by size minus overlap
        start += chunk_size - overlap
        if chunk_size <= overlap:
            break
            
    return chunks


def chunk_by_lines(text: str, chunk_size: int, overlap: int) -> List[str]:
    """Splits text by line count with line overlap."""
    lines = text.splitlines(keepends=True)
    if chunk_size <= 0:
        return [text]
        
    chunks = []
    start = 0
    total_lines = len(lines)
    
    while start < total_lines:
        end = start + chunk_size
        chunk = "".join(lines[start:end])
        chunks.append(chunk)
        start += chunk_size - overlap
        if chunk_size <= overlap:
            break
            
    return chunks


def chunk_by_words(text: str, chunk_size: int, overlap: int) -> List[str]:
    """Splits text by word count with word overlap."""
    words = text.split()
    if chunk_size <= 0:
        return [text]
        
    chunks = []
    start = 0
    total_words = len(words)
    
    while start < total_words:
        end = start + chunk_size
        chunk = " ".join(words[start:end])
        chunks.append(chunk)
        start += chunk_size - overlap
        if chunk_size <= overlap:
            break
            
    return chunks


def chunk_by_paragraphs(text: str, max_chars: int) -> List[str]:
    """Splits text by double newlines, keeping paragraphs intact up to max_chars."""
    paragraphs = text.split("\n\n")
    chunks = []
    current_chunk = []
    current_length = 0
    
    for p in paragraphs:
        p = p.strip()
        if not p:
            continue
        p_len = len(p) + 2  # account for double newline separator
        
        # If paragraph itself is larger than max_chars, split it by characters
        if p_len > max_chars:
            if current_chunk:
                chunks.append("\n\n".join(current_chunk))
                current_chunk = []
                current_length = 0
            sub_chunks = chunk_by_characters(p, max_chars, 0)
            chunks.extend(sub_chunks)
        elif current_length + p_len > max_chars:
            chunks.append("\n\n".join(current_chunk))
            current_chunk = [p]
            current_length = p_len
        else:
            current_chunk.append(p)
            current_length += p_len
            
    if current_chunk:
        chunks.append("\n\n".join(current_chunk))
        
    return chunks


def chunk_by_markdown(text: str, max_chars: int) -> List[str]:
    """
    Splits text by Markdown headers (# , ## , etc.) and attempts to prefix
    subsequent chunks with the header context (e.g. 'Context: # Header > ## Subheader').
    """
    lines = text.splitlines(keepends=True)
    chunks = []
    
    current_chunk = []
    current_length = 0
    
    # Active headers stack (level, title)
    header_stack: List[tuple] = []
    
    for line in lines:
        match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if match:
            # We hit a header
            level = len(match.group(1))
            title = match.group(2).strip()
            
            # Pop headers of same or deeper levels
            while header_stack and header_stack[-1][0] >= level:
                header_stack.pop()
            header_stack.append((level, title))
            
            # Flush current chunk if any
            if current_chunk:
                chunks.append("".join(current_chunk))
                current_chunk = []
                current_length = 0
                
        line_len = len(line)
        if current_length + line_len > max_chars:
            # Flush
            if current_chunk:
                chunks.append("".join(current_chunk))
            
            # Start next chunk with header context if stack exists
            context_prefix = ""
            if header_stack:
                trail = " > ".join([h[1] for h in header_stack])
                context_prefix = f"/* Context: {trail} */\n"
                
            current_chunk = [context_prefix, line]
            current_length = len(context_prefix) + line_len
        else:
            current_chunk.append(line)
            current_length += line_len
            
    if current_chunk:
        chunks.append("".join(current_chunk))
        
    return chunks


def chunk_by_code(text: str, max_lines: int) -> List[str]:
    """
    Code-aware line-based chunker that tries to split on class/function boundaries
    (indentation level 0 def/class keywords or equivalent).
    """
    lines = text.splitlines(keepends=True)
    chunks = []
    current_chunk = []
    
    for line in lines:
        # Check if line is a function or class definition at base level
        is_boundary = re.match(r"^(def\s+|class\s+|function\s+|export\s+default\s+|export\s+class\s+)", line)
        
        if is_boundary and len(current_chunk) >= max_lines // 2:
            # Flush since we are at a clean code boundary and have enough lines
            chunks.append("".join(current_chunk))
            current_chunk = [line]
        elif len(current_chunk) >= max_lines:
            # Hard limit split
            chunks.append("".join(current_chunk))
            current_chunk = [line]
        else:
            current_chunk.append(line)
            
    if current_chunk:
        chunks.append("".join(current_chunk))
        
    return chunks


def main():
    parser = argparse.ArgumentParser(
        description="Split a text file or stream into overlapping semantic chunks for LLM ingestion."
    )
    parser.add_argument("file", nargs="?", default="-", help="Input file path (default: stdin)")
    parser.add_argument("-s", "--size", type=int, default=1000, help="Target size of each chunk (characters, lines, or words)")
    parser.add_argument("-o", "--overlap", type=int, default=100, help="Overlap size between chunks")
    parser.add_argument("-u", "--unit", choices=["char", "word", "line"], default="char",
                        help="Unit for size and overlap parameters (default: char)")
    parser.add_argument("-t", "--strategy", choices=["simple", "paragraph", "markdown", "code"], default="simple",
                        help="Chunking strategy logic to apply (default: simple)")
    parser.add_argument("-d", "--output-dir", help="Directory to save the chunks as separate files")
    parser.add_argument("-m", "--metadata", action="store_true", help="Inject metadata headers into each chunk")
    parser.add_argument("-p", "--preview", action="store_true", help="Print a summary and preview of first few chunks, don't write files")

    args = parser.parse_args()

    # 1. Read input
    text = ""
    if args.file == "-":
        text = sys.stdin.read()
        filename = "stdin"
    else:
        if not os.path.exists(args.file):
            safe_print(f"File not found: {args.file}", end="\n")
            sys.exit(1)
        try:
            with open(args.file, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
            filename = os.path.basename(args.file)
        except Exception as e:
            safe_print(f"Error reading file: {e}", end="\n")
            sys.exit(1)

    if not text:
        safe_print("Empty input. No text to chunk.", end="\n")
        sys.exit(1)

    # Validate overlap
    if args.overlap >= args.size and args.strategy == "simple":
        safe_print("Error: Overlap must be smaller than size.", end="\n")
        sys.exit(1)

    # 2. Perform chunking based on strategy
    chunks: List[str] = []
    
    if args.strategy == "simple":
        if args.unit == "char":
            chunks = chunk_by_characters(text, args.size, args.overlap)
        elif args.unit == "line":
            chunks = chunk_by_lines(text, args.size, args.overlap)
        elif args.unit == "word":
            chunks = chunk_by_words(text, args.size, args.overlap)
    elif args.strategy == "paragraph":
        chunks = chunk_by_paragraphs(text, args.size)
    elif args.strategy == "markdown":
        chunks = chunk_by_markdown(text, args.size)
    elif args.strategy == "code":
        max_lines = args.size if args.unit == "line" else (args.size // 40 or 25)
        chunks = chunk_by_code(text, max_lines)

    # 3. Add metadata headers if requested
    if args.metadata:
        processed_chunks = []
        for i, chunk in enumerate(chunks, 1):
            char_count = len(chunk)
            word_count = len(chunk.split())
            line_count = len(chunk.splitlines())
            
            header = (
                f"--- CHUNK START (File: {filename} | Index: {i}/{len(chunks)} | "
                f"Chars: {char_count} | Words: {word_count} | Lines: {line_count}) ---\n"
            )
            processed_chunks.append(header + chunk + "\n--- CHUNK END ---\n")
        chunks = processed_chunks

    # 4. Handle output
    if args.preview:
        safe_print(f"\n{'-'*30} CHUNKER PREVIEW {'-'*30}")
        safe_print(f"File: {filename}")
        safe_print(f"Strategy: {args.strategy} | Unit: {args.unit}")
        safe_print(f"Total Content Length: {len(text)} characters")
        safe_print(f"Generated Chunks: {len(chunks)}")
        safe_print(f"{'-'*77}\n")
        
        preview_count = min(3, len(chunks))
        for idx in range(preview_count):
            safe_print(f"--- Chunk {idx + 1} Preview ---")
            safe_print(chunks[idx][:300] + ("..." if len(chunks[idx]) > 300 else ""))
            safe_print("-" * 50)
            
        if len(chunks) > preview_count:
            safe_print(f"... and {len(chunks) - preview_count} more chunks.")
    elif args.output_dir:
        os.makedirs(args.output_dir, exist_ok=True)
        pad_width = len(str(len(chunks)))
        
        base_name, ext = os.path.splitext(filename)
        if not ext:
            ext = ".txt"
            
        safe_print(f"Writing {len(chunks)} chunks to directory: {args.output_dir}...")
        for idx, chunk in enumerate(chunks, 1):
            out_file = os.path.join(args.output_dir, f"{base_name}_chunk_{idx:0{pad_width}d}{ext}")
            try:
                with open(out_file, "w", encoding="utf-8") as f:
                    f.write(chunk)
            except Exception as e:
                safe_print(f"Failed to write chunk {idx}: {e}", end="\n")
                sys.exit(1)
        safe_print("Success.")
    else:
        for idx, chunk in enumerate(chunks, 1):
            if not args.metadata:
                safe_print(f"=== CHUNK {idx} ===")
            safe_print(chunk)


if __name__ == "__main__":
    main()
