#!/usr/bin/env python3
"""
DOCX to Markdown Converter

A standalone, zero-dependency utility to convert Microsoft Word (.docx) files
into clean Markdown (.md) documents. Extracts paragraphs, headings, bold/italic,
hyperlinks, tables, lists, and embedded images.

Usage:
    python docx_to_markdown.py input.docx -o output.md
"""

import sys
import os
import argparse
import zipfile
import xml.etree.ElementTree as ET
import re

# XML Namespaces used in docx format
NAMESPACES = {
    'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'rel': 'http://schemas.openxmlformats.org/package/2006/relationships',
}

def parse_relationships(docx_zip):
    """Parses relationship file to map relationship IDs to target URLs and media paths."""
    rels = {}
    try:
        rels_xml = docx_zip.read('word/_rels/document.xml.rels')
        root = ET.fromstring(rels_xml)
        for child in root:
            r_id = child.attrib.get('Id')
            r_target = child.attrib.get('Target')
            r_type = child.attrib.get('Type', '')
            rels[r_id] = {
                'target': r_target,
                'type': r_type
            }
    except KeyError:
        # Relationship file might not exist or be named differently
        pass
    return rels

def extract_media(docx_zip, rels, output_dir):
    """Extracts embedded images from the zip and maps their relationship IDs."""
    media_map = {}
    media_dir = os.path.join(output_dir, 'media')
    
    for r_id, rel_info in rels.items():
        target = rel_info['target']
        # Check if the relationship is an image
        if 'image' in rel_info['type'].lower() or target.startswith('media/'):
            zip_path = f"word/{target}" if not target.startswith('word/') else target
            try:
                # Read image data
                img_data = docx_zip.read(zip_path)
                
                # Ensure output media directory exists
                os.makedirs(media_dir, exist_ok=True)
                
                # File name on disk
                img_name = os.path.basename(target)
                dest_path = os.path.join(media_dir, img_name)
                
                with open(dest_path, 'wb') as img_file:
                    img_file.write(img_data)
                    
                # Store relative path for Markdown embedding
                media_map[r_id] = os.path.join('media', img_name).replace('\\', '/')
            except Exception as e:
                print(f"Warning: Failed to extract media '{target}': {e}", file=sys.stderr)
                
    return media_map

def get_text_formatting(r_elem):
    """Extracts formatting properties of a run (bold, italic)."""
    rPr = r_elem.find('w:rPr', NAMESPACES)
    bold = False
    italic = False
    if rPr is not None:
        if rPr.find('w:b', NAMESPACES) is not None:
            bold = True
        if rPr.find('w:i', NAMESPACES) is not None:
            italic = True
    return bold, italic

def parse_run(r_elem):
    """Parses a text run, returns the text contents and formatting flags."""
    text = ""
    t_elems = r_elem.findall('w:t', NAMESPACES)
    for t in t_elems:
        if t.text:
            text += t.text
            
    # Handle tab elements
    if r_elem.find('w:tab', NAMESPACES) is not None:
        text += '\t'
        
    bold, italic = get_text_formatting(r_elem)
    return text, bold, italic

def get_paragraph_style(p_elem):
    """Detects heading levels or list styles of a paragraph."""
    pPr = p_elem.find('w:pPr', NAMESPACES)
    if pPr is not None:
        pStyle = pPr.find('w:pStyle', NAMESPACES)
        if pStyle is not None:
            style_val = pStyle.attrib.get(f"{{{NAMESPACES['w']}}}val", "")
            # Look for Headings
            heading_match = re.search(r'Heading(\d)', style_val, re.IGNORECASE)
            if heading_match:
                return 'heading', int(heading_match.group(1))
                
        # Check if list item
        numPr = pPr.find('w:numPr', NAMESPACES)
        if numPr is not None:
            # It's a list item
            return 'list_item', numPr
            
    return 'paragraph', 0

def convert_to_markdown(docx_path, output_dir=""):
    """Main converter logic."""
    if not zipfile.is_zipfile(docx_path):
        raise ValueError(f"File '{docx_path}' is not a valid docx (ZIP archive) file.")
        
    md_content = []
    
    with zipfile.ZipFile(docx_path, 'r') as docx_zip:
        # Load relationships
        rels = parse_relationships(docx_zip)
        
        # Extract media files if output directory is defined
        media_map = {}
        if output_dir:
            media_map = extract_media(docx_zip, rels, output_dir)
            
        # Parse document.xml
        doc_xml = docx_zip.read('word/document.xml')
        root = ET.fromstring(doc_xml)
        body = root.find('w:body', NAMESPACES)
        
        if body is None:
            raise ValueError("Document XML body structure not found.")
            
        # Traverse elements in body
        for elem in body:
            tag = elem.tag.split('}')[-1]
            
            # 1. PARAGRAPH
            if tag == 'p':
                p_type, p_detail = get_paragraph_style(elem)
                
                # Gather all text runs inside the paragraph
                p_runs = []
                for child in elem:
                    c_tag = child.tag.split('}')[-1]
                    
                    if c_tag == 'r':
                        run_text, b, it = parse_run(child)
                        # Check if it has drawing (image) inside
                        drawing = child.find('.//w:drawing', NAMESPACES)
                        if drawing is not None:
                            # Try to find embed relation ID
                            blip = drawing.find('.//a:blip', {'a': 'http://schemas.openxmlformats.org/drawingml/2006/main'})
                            if blip is not None:
                                embed_id = blip.attrib.get(f"{{{NAMESPACES['r']}}}embed")
                                if embed_id in media_map:
                                    img_rel_path = media_map[embed_id]
                                    run_text += f"\n\n![Embedded Image]({img_rel_path})\n\n"
                        p_runs.append((run_text, b, it))
                        
                    elif c_tag == 'hyperlink':
                        r_id = child.attrib.get(f"{{{NAMESPACES['r']}}}id")
                        link_url = ""
                        if r_id in rels:
                            link_url = rels[r_id]['target']
                        
                        # Process children runs in hyperlink
                        link_text = ""
                        for r in child.findall('w:r', NAMESPACES):
                            txt, _, _ = parse_run(r)
                            link_text += txt
                            
                        p_runs.append((f"[{link_text}]({link_url})" if link_url else link_text, False, False))
                
                # Construct markdown representation
                raw_text = ""
                for txt, b, it in p_runs:
                    if not txt.strip():
                        raw_text += txt
                        continue
                    
                    lead_space = re.match(r'^(\s*)', txt).group(1)
                    trail_space = re.search(r'(\s*)$', txt).group(1)
                    clean_txt = txt.strip()
                    
                    # Bold & Italic wrapping
                    if b and it:
                        clean_txt = f"***{clean_txt}***"
                    elif b:
                        clean_txt = f"**{clean_txt}**"
                    elif it:
                        clean_txt = f"*{clean_txt}*"
                        
                    raw_text += lead_space + clean_txt + trail_space
                
                if not raw_text.strip():
                    continue
                    
                if p_type == 'heading':
                    h_level = p_detail
                    md_content.append(f"{'#' * h_level} {raw_text.strip()}")
                elif p_type == 'list_item':
                    # Determine indent or list type if possible
                    # Basic markdown list fallback
                    md_content.append(f"- {raw_text.strip()}")
                else:
                    md_content.append(raw_text.strip())
                    
            # 2. TABLE
            elif tag == 'tbl':
                table_md = []
                rows = elem.findall('w:tr', NAMESPACES)
                
                max_cols = 0
                parsed_rows = []
                
                for r in rows:
                    cells = r.findall('w:tc', NAMESPACES)
                    max_cols = max(max_cols, len(cells))
                    
                    row_cells = []
                    for c in cells:
                        # Extract text from cell paragraphs
                        cell_text = []
                        for p in c.findall('w:p', NAMESPACES):
                            p_text = ""
                            for r_node in p.findall('w:r', NAMESPACES):
                                txt, _, _ = parse_run(r_node)
                                p_text += txt
                            if p_text.strip():
                                cell_text.append(p_text.strip())
                        row_cells.append(" ".join(cell_text).replace('|', '\\|'))
                    parsed_rows.append(row_cells)
                
                if max_cols > 0:
                    for idx, row in enumerate(parsed_rows):
                        # Pad rows that are shorter
                        row += [""] * (max_cols - len(row))
                        table_md.append("| " + " | ".join(row) + " |")
                        
                        # Output separator after the first header row
                        if idx == 0:
                            table_md.append("| " + " | ".join(["---"] * max_cols) + " |")
                            
                    md_content.append("\n".join(table_md))
                    
    # Join items with double newline
    return "\n\n".join(md_content)

def main():
    parser = argparse.ArgumentParser(
        description="Convert Microsoft Word (.docx) documents to Markdown.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "docx_file",
        help="Path to the input Word (.docx) file."
    )
    
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Path to save the output Markdown (.md) file. (If omitted, prints to stdout)"
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.docx_file):
        print(f"Error: Input file '{args.docx_file}' not found.", file=sys.stderr)
        return 1
        
    output_dir = ""
    if args.output:
        # Use target folder to extract media images
        output_dir = os.path.dirname(os.path.abspath(args.output))
        
    try:
        markdown_text = convert_to_markdown(args.docx_file, output_dir)
    except Exception as e:
        print(f"Error converting document: {e}", file=sys.stderr)
        return 1
        
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(markdown_text)
            print(f"Successfully converted '{args.docx_file}' to '{args.output}'")
        except Exception as e:
            print(f"Error writing output file: {e}", file=sys.stderr)
            return 1
    else:
        # Print to stdout
        print(markdown_text)
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
