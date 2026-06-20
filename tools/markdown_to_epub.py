#!/usr/bin/env python3
"""
Markdown to EPUB E-book Compiler
Converts a directory of Markdown files or a single Markdown document (split by headings) 
into a standard, fully-validated EPUB e-book using only Python standard libraries.
"""

import argparse
import html
import os
import re
import sys
import uuid
import zipfile
from typing import List, Tuple

# Basic Markdown-to-HTML converter using regexes (since we want pure stdlib)
def simple_markdown_to_html(md_text: str) -> str:
    """Converts a subset of Markdown (headings, paragraphs, lists, emphasis, code) to XHTML."""
    lines = md_text.splitlines()
    html_lines = []
    in_list = False
    in_code_block = False
    list_type = None  # 'ul' or 'ol'
    
    for line in lines:
        stripped = line.strip()
        
        # Code block handling
        if stripped.startswith("```"):
            if in_code_block:
                html_lines.append("</code></pre>")
                in_code_block = False
            else:
                html_lines.append("<pre><code>")
                in_code_block = True
            continue
            
        if in_code_block:
            html_lines.append(html.escape(line))
            continue
            
        # List handling
        is_unordered = stripped.startswith("* ") or stripped.startswith("- ")
        is_ordered = bool(re.match(r"^\d+\.\s+", stripped))
        
        if is_unordered or is_ordered:
            if not in_list:
                in_list = True
                list_type = "ul" if is_unordered else "ol"
                html_lines.append(f"<{list_type}>")
            
            # Extract content
            if is_unordered:
                item_content = stripped[2:]
            else:
                item_content = re.sub(r"^\d+\.\s+", "", stripped)
                
            # Apply inline styles
            item_content = parse_inline_markdown(item_content)
            html_lines.append(f"<li>{item_content}</li>")
            continue
        elif in_list:
            html_lines.append(f"</{list_type}>")
            in_list = False
            list_type = None
            
        # Empty line -> Paragraph separator
        if not stripped:
            continue
            
        # Headings
        if stripped.startswith("#"):
            h_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
            if h_match:
                level = len(h_match.group(1))
                content = parse_inline_markdown(h_match.group(2))
                html_lines.append(f"<h{level}>{content}</h{level}>")
                continue
                
        # Blockquote
        if stripped.startswith(">"):
            content = parse_inline_markdown(stripped[1:].strip())
            html_lines.append(f"<blockquote>{content}</blockquote>")
            continue
            
        # Horizontal Rule
        if stripped in ("---", "***", "___"):
            html_lines.append("<hr />")
            continue
            
        # Normal Paragraph
        content = parse_inline_markdown(stripped)
        html_lines.append(f"<p>{content}</p>")
        
    if in_list:
        html_lines.append(f"</{list_type}>")
        
    return "\n".join(html_lines)

def parse_inline_markdown(text: str) -> str:
    """Parses bold, italic, inline code, and links in Markdown line."""
    # Escape HTML characters first
    text = html.escape(text)
    
    # Inline code: `code`
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    
    # Bold: **bold** or __bold__
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"__([^_]+)__", r"<strong>\1</strong>", text)
    
    # Italic: *italic* or _italic_
    text = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", text)
    text = re.sub(r"_([^_]+)_", r"<em>\1</em>", text)
    
    # Links: [text](url)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    
    return text

def parse_single_file(filepath: str) -> List[Tuple[str, str]]:
    """Parses a single Markdown file, splitting it into chapters based on H1 headings."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Split content by H1 heading
    parts = re.split(r"^(#\s+.*)$", content, flags=re.MULTILINE)
    
    chapters = []
    current_title = "Introduction"
    current_body = []
    
    # If the file doesn't start with H1, collect prefix content
    first_part = parts[0].strip()
    if first_part:
        current_body.append(first_part)
        
    for i in range(1, len(parts), 2):
        title = parts[i].replace("#", "").strip()
        body = parts[i+1]
        
        # If we have previous chapter data, save it
        if current_body:
            chapters.append((current_title, "\n".join(current_body)))
            current_body = []
            
        current_title = title
        current_body.append(body.strip())
        
    if current_body:
        chapters.append((current_title, "\n".join(current_body)))
        
    return chapters

def parse_directory(dirpath: str) -> List[Tuple[str, str]]:
    """Parses a directory of Markdown files sorted alphabetically/numerically."""
    chapters = []
    files = sorted([f for f in os.listdir(dirpath) if f.endswith(".md")])
    
    for filename in files:
        filepath = os.path.join(dirpath, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            
        # Use filename as title fallback, or first line H1
        title = filename.rstrip(".md").replace("_", " ").title()
        first_line = content.strip().splitlines()
        if first_line and first_line[0].startswith("# "):
            title = first_line[0].replace("#", "").strip()
            # Strip the title heading line from content to avoid double headers
            content = "\n".join(content.strip().splitlines()[1:])
            
        chapters.append((title, content))
        
    return chapters

def build_epub(chapters: List[Tuple[str, str]], output_path: str, title: str, author: str, cover_path: str = None):
    """Compiles the list of chapters (title, md_content) into a valid EPUB zip container."""
    book_id = str(uuid.uuid4())
    
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as epub:
        # 1. mimetype (Must be first, and uncompressed!)
        epub.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
        
        # 2. META-INF/container.xml
        container_xml = """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
    <rootfiles>
        <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
    </rootfiles>
</container>"""
        epub.writestr("META-INF/container.xml", container_xml)
        
        # 3. OEBPS/stylesheet.css
        stylesheet_css = """body {
    font-family: "Georgia", "DejaVu Serif", serif;
    margin: 10%;
    line-height: 1.6;
    color: #111111;
}
h1, h2, h3, h4 {
    font-family: sans-serif;
    color: #333333;
    margin-top: 1.5em;
    margin-bottom: 0.5em;
}
h1 {
    text-align: center;
    border-bottom: 1px solid #cccccc;
    padding-bottom: 0.3em;
}
p {
    margin-bottom: 1.2em;
    text-indent: 1em;
}
p:first-of-type {
    text-indent: 0;
}
pre {
    background-color: #f5f5f5;
    border: 1px solid #dddddd;
    padding: 10px;
    overflow: auto;
    font-family: monospace;
    font-size: 0.9em;
}
code {
    font-family: monospace;
    background-color: #f5f5f5;
    padding: 0 4px;
}
blockquote {
    border-left: 4px solid #cccccc;
    margin-left: 0;
    padding-left: 20px;
    font-style: italic;
    color: #555555;
}
li {
    margin-bottom: 0.5em;
}"""
        epub.writestr("OEBPS/stylesheet.css", stylesheet_css)
        
        # Include cover image if available
        cover_filename = None
        if cover_path and os.path.exists(cover_path):
            cover_ext = os.path.splitext(cover_path)[1].lower()
            cover_filename = f"cover{cover_ext}"
            mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
            cover_mime = mime_map.get(cover_ext, "image/jpeg")
            epub.write(cover_path, f"OEBPS/{cover_filename}")
            
        # Write individual XHTML chapters
        manifest_items = []
        spine_items = []
        toc_entries = []
        
        # Include stylesheet in manifest
        manifest_items.append('<item id="css" href="stylesheet.css" media-type="text/css"/>')
        
        # Cover image items in manifest
        if cover_filename:
            manifest_items.append(f'<item id="cover-image" href="{cover_filename}" media-type="{cover_mime}"/>')
            # Generate cover.xhtml
            cover_html = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>Cover</title>
    <style type="text/css">
        body {{ text-align: center; padding: 0; margin: 0; }}
        img {{ max-width: 100%; height: auto; }}
    </style>
</head>
<body>
    <img src="{cover_filename}" alt="Cover Image" />
</body>
</html>"""
            epub.writestr("OEBPS/cover.xhtml", cover_html)
            manifest_items.append('<item id="cover" href="cover.xhtml" media-type="application/xhtml+xml"/>')
            spine_items.append('<itemref idref="cover" linear="no"/>')
            
        for idx, (ch_title, ch_content) in enumerate(chapters, 1):
            ch_id = f"chap_{idx}"
            ch_filename = f"chapter_{idx}.xhtml"
            
            # Build XHTML page
            html_body = simple_markdown_to_html(ch_content)
            xhtml_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.1//EN" "http://www.w3.org/TR/xhtml11/DTD/xhtml11.dtd">
<html xmlns="http://www.w3.org/1999/xhtml">
<head>
    <title>{html.escape(ch_title)}</title>
    <link rel="stylesheet" href="stylesheet.css" type="text/css" />
</head>
<body>
    <h1>{html.escape(ch_title)}</h1>
    {html_body}
</body>
</html>"""
            epub.writestr(f"OEBPS/{ch_filename}", xhtml_content)
            
            # Register in OPF lists
            manifest_items.append(f'<item id="{ch_id}" href="{ch_filename}" media-type="application/xhtml+xml"/>')
            spine_items.append(f'<itemref idref="{ch_id}"/>')
            toc_entries.append((ch_id, ch_filename, ch_title))
            
        # Register Table of Contents (toc.ncx)
        manifest_items.append('<item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>')
        
        # 4. Generate OEBPS/toc.ncx
        toc_navpoints = []
        for i, (ch_id, ch_filename, ch_title) in enumerate(toc_entries, 1):
            nav = f"""    <navPoint id="navpoint-{i}" playOrder="{i}">
        <navLabel><text>{html.escape(ch_title)}</text></navLabel>
        <content src="{ch_filename}"/>
    </navPoint>"""
            toc_navpoints.append(nav)
            
        toc_ncx = f"""<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
    <head>
        <meta name="dtb:uid" content="{book_id}"/>
        <meta name="dtb:depth" content="1"/>
        <meta name="dtb:totalPageCount" content="0"/>
        <meta name="dtb:maxPageNumber" content="0"/>
    </head>
    <docTitle><text>{html.escape(title)}</text></docTitle>
    <docAuthor><text>{html.escape(author)}</text></docAuthor>
    <navMap>
    {"\n".join(toc_navpoints)}
    </navMap>
</ncx>"""
        epub.writestr("OEBPS/toc.ncx", toc_ncx)
        
        # 5. Generate OEBPS/content.opf
        content_opf = f"""<?xml version="1.0" encoding="UTF-8"?>
<package xmlns="http://www.idpf.org/2007/opf" unique-identifier="bookid" version="2.0">
    <metadata xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:opf="http://www.idpf.org/2007/opf">
        <dc:title>{html.escape(title)}</dc:title>
        <dc:creator opf:role="aut">{html.escape(author)}</dc:creator>
        <dc:language>en</dc:language>
        <dc:identifier id="bookid">urn:uuid:{book_id}</dc:identifier>
        {f'<meta name="cover" content="cover-image"/>' if cover_filename else ''}
    </metadata>
    <manifest>
        {"\n        ".join(manifest_items)}
    </manifest>
    <spine toc="ncx">
        {"\n        ".join(spine_items)}
    </spine>
</package>"""
        epub.writestr("OEBPS/content.opf", content_opf)

def main():
    parser = argparse.ArgumentParser(
        description="Markdown to EPUB E-book Compiler"
    )
    parser.add_argument(
        "--input", required=True,
        help="Path to input Markdown file (splits by H1 headers) or directory containing sorted Markdown files."
    )
    parser.add_argument(
        "--output", required=True,
        help="Path where the compiled EPUB file will be saved."
    )
    parser.add_argument(
        "--title", default="Untitled E-book",
        help="E-book Title metadata (default: 'Untitled E-book')"
    )
    parser.add_argument(
        "--author", default="Unknown Author",
        help="E-book Author metadata (default: 'Unknown Author')"
    )
    parser.add_argument(
        "--cover", help="Path to optional cover image (JPG/PNG)."
    )
    args = parser.parse_args()

    input_path = os.path.abspath(args.input)
    output_path = os.path.abspath(args.output)

    if not os.path.exists(input_path):
        print(f"Error: Input path '{input_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    print(f"Reading Markdown input from: {input_path}")
    
    if os.path.isdir(input_path):
        chapters = parse_directory(input_path)
    else:
        chapters = parse_single_file(input_path)

    if not chapters:
        print("Error: No chapter content found. Ensure your Markdown files have headers or content.", file=sys.stderr)
        sys.exit(1)

    print(f"Found {len(chapters)} chapter(s). Compiling EPUB...")
    
    try:
        build_epub(chapters, output_path, args.title, args.author, args.cover)
        print(f"Success! EPUB compiled successfully: {output_path}")
    except Exception as e:
        print(f"Error compiling EPUB: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
