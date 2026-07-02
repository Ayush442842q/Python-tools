#!/usr/bin/env python3
"""
EPUB to Markdown Converter

A standalone, zero-dependency utility to convert EPUB (.epub) files into clean,
human-readable Markdown (.md) files. It parses the EPUB archive, extracts chapters
in the correct spine order, converts HTML elements to Markdown, and optionally
extracts embedded images.

Usage:
    python epub_to_markdown.py input.epub -o output.md --extract-images
"""

import os
import sys
import argparse
import zipfile
import re
import html
from urllib.parse import unquote
import xml.etree.ElementTree as ET

# Simple HTML to Markdown translator class
class HTMLToMarkdownParser:
    def __init__(self, extract_images=False, image_dir="images"):
        self.extract_images = extract_images
        self.image_dir = image_dir
        self.list_depth = 0
        self.in_list = False
        self.list_type = [] # Stack of 'ol' or 'ul'
        self.list_index = [] # Stack of current list index for ordered lists

    def clean_text(self, text):
        if not text:
            return ""
        # Replace multiple spaces with a single space
        text = re.sub(r'[ \t\r\n]+', ' ', text)
        return text

    def convert(self, html_content):
        # Extremely lightweight regex-based HTML tag parser
        # It parses common structural tags: h1-h6, p, em, strong, b, i, blockquote, ul, ol, li, a, img, br
        
        # Extract body content if present
        body_match = re.search(r'<body[^>]*>(.*?)</body>', html_content, re.DOTALL | re.IGNORECASE)
        if body_match:
            content = body_match.group(1)
        else:
            content = html_content

        # Remove comments
        content = re.sub(r'<!--.*?-->', '', content, flags=re.DOTALL)
        # Remove head, script, style tags if any leaked in
        content = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
        content = re.sub(r'<style[^>]*>.*?</style>', '', content, flags=re.DOTALL | re.IGNORECASE)
        
        # Tokenize HTML into tags and text
        tokens = re.split(r'(<[^>]+>)', content)
        
        markdown = []
        skip_content = False
        
        for token in tokens:
            if not token:
                continue
            
            if token.startswith('<') and token.endswith('>'):
                tag_content = token[1:-1].strip()
                tag_parts = tag_content.split()
                tag_name = tag_parts[0].lower() if tag_parts else ""
                is_closing = tag_name.startswith('/')
                if is_closing:
                    tag_name = tag_name[1:]
                
                # Parse attributes
                attrs = {}
                for attr_part in tag_parts[1:]:
                    if '=' in attr_part:
                        k, v = attr_part.split('=', 1)
                        attrs[k.lower()] = v.strip('"\'')
                
                if tag_name in ['h1', 'h2', 'h3', 'h4', 'h5', 'h6']:
                    if not is_closing:
                        level = int(tag_name[1])
                        markdown.append('\n\n' + '#' * level + ' ')
                    else:
                        markdown.append('\n')
                elif tag_name == 'p':
                    if not is_closing:
                        markdown.append('\n\n')
                    else:
                        markdown.append('\n')
                elif tag_name in ['strong', 'b']:
                    markdown.append('**')
                elif tag_name in ['em', 'i']:
                    markdown.append('*')
                elif tag_name == 'br':
                    markdown.append('  \n')
                elif tag_name == 'hr':
                    markdown.append('\n\n---\n\n')
                elif tag_name == 'blockquote':
                    if not is_closing:
                        markdown.append('\n\n> ')
                    else:
                        markdown.append('\n\n')
                elif tag_name == 'ul':
                    if not is_closing:
                        self.list_depth += 1
                        self.list_type.append('ul')
                        markdown.append('\n')
                    else:
                        self.list_depth = max(0, self.list_depth - 1)
                        if self.list_type: self.list_type.pop()
                        markdown.append('\n')
                elif tag_name == 'ol':
                    if not is_closing:
                        self.list_depth += 1
                        self.list_type.append('ol')
                        self.list_index.append(1)
                        markdown.append('\n')
                    else:
                        self.list_depth = max(0, self.list_depth - 1)
                        if self.list_type: self.list_type.pop()
                        if self.list_index: self.list_index.pop()
                        markdown.append('\n')
                elif tag_name == 'li':
                    if not is_closing:
                        indent = '  ' * (self.list_depth - 1)
                        if self.list_type and self.list_type[-1] == 'ol':
                            idx = self.list_index[-1]
                            markdown.append(f'\n{indent}{idx}. ')
                            self.list_index[-1] += 1
                        else:
                            markdown.append(f'\n{indent}- ')
                elif tag_name == 'a':
                    if not is_closing:
                        href = attrs.get('href', '#')
                        markdown.append('[')
                        self.current_href = href
                    else:
                        # Append URL
                        href_val = getattr(self, 'current_href', '#')
                        # Keep internal links prefix-free, but strip .html/.xhtml fragments if needed
                        markdown.append(f']({href_val})')
                elif tag_name == 'img':
                    src = attrs.get('src', '')
                    alt = attrs.get('alt', 'Image')
                    if src:
                        if self.extract_images:
                            filename = os.path.basename(unquote(src))
                            markdown.append(f'![{alt}]({self.image_dir}/{filename})')
                        else:
                            markdown.append(f'![{alt}]({src})')
            else:
                # Text token
                text = html.unescape(token)
                # Keep newlines only if they are not surrounded by inline code
                # But generally we format text to be clean
                text = self.clean_text(text)
                if text:
                    markdown.append(text)
                    
        # Reconstruct string and cleanup duplicate newlines
        result = "".join(markdown)
        result = re.sub(r'\n{3,}', '\n\n', result)
        return result.strip()


def parse_epub(epub_path, output_md_path, extract_images=False):
    if not zipfile.is_zipfile(epub_path):
        print(f"Error: {epub_path} is not a valid zip archive (EPUB).", file=sys.stderr)
        return 1

    output_dir = os.path.dirname(output_md_path) if os.path.dirname(output_md_path) else "."
    image_subdir = "images"
    image_dir_full = os.path.join(output_dir, image_subdir)

    with zipfile.ZipFile(epub_path, 'r') as epub:
        # 1. Read container.xml to locate OPF file
        try:
            container_xml = epub.read('META-INF/container.xml')
            container_root = ET.fromstring(container_xml)
            # Find rootfile element
            rootfile_elem = container_root.find('.//{urn:oasis:names:tc:opendocument:xmlns:container}rootfile')
            if rootfile_elem is None:
                # Try generic matching without namespace just in case
                rootfile_elem = container_root.find('.//*[local-name()="rootfile"]')
            
            if rootfile_elem is None:
                print("Error: Could not parse rootfile from container.xml", file=sys.stderr)
                return 1
                
            opf_path = rootfile_elem.attrib['full-path']
        except Exception as e:
            print(f"Error reading container.xml: {e}", file=sys.stderr)
            return 1

        opf_dir = os.path.dirname(opf_path)
        
        # 2. Read OPF file content
        try:
            opf_xml = epub.read(opf_path)
            opf_root = ET.fromstring(opf_xml)
        except Exception as e:
            print(f"Error reading OPF file {opf_path}: {e}", file=sys.stderr)
            return 1

        # XML namespace maps
        ns = {
            'opf': 'http://www.idpf.org/2007/opf',
            'dc': 'http://purl.org/dc/elements/1.1/'
        }

        # 3. Extract Metadata
        title = "EPUB Book"
        author = "Unknown Author"
        
        metadata_elem = opf_root.find('.//opf:metadata', ns)
        if metadata_elem is None:
            metadata_elem = opf_root.find('.//*[local-name()="metadata"]')
            
        if metadata_elem is not None:
            title_elem = metadata_elem.find('.//dc:title', ns) or metadata_elem.find('.//*[local-name()="title"]')
            creator_elem = metadata_elem.find('.//dc:creator', ns) or metadata_elem.find('.//*[local-name()="creator"]')
            if title_elem is not None and title_elem.text:
                title = title_elem.text.strip()
            if creator_elem is not None and creator_elem.text:
                author = creator_elem.text.strip()

        # 4. Extract Manifest (item ID -> href)
        manifest_elem = opf_root.find('.//opf:manifest', ns) or opf_root.find('.//*[local-name()="manifest"]')
        if manifest_elem is None:
            print("Error: OPF manifest section not found.", file=sys.stderr)
            return 1

        manifest = {}
        for item in manifest_elem:
            item_id = item.attrib.get('id')
            item_href = item.attrib.get('href')
            item_media = item.attrib.get('media-type', '')
            if item_id and item_href:
                manifest[item_id] = {
                    'href': item_href,
                    'media': item_media
                }

        # 5. Extract Spine (linear reading order)
        spine_elem = opf_root.find('.//opf:spine', ns) or opf_root.find('.//*[local-name()="spine"]')
        if spine_elem is None:
            print("Error: OPF spine section not found.", file=sys.stderr)
            return 1

        spine = []
        for itemref in spine_elem:
            idref = itemref.attrib.get('idref')
            if idref in manifest:
                spine.append(idref)

        # 6. Optionally extract images
        if extract_images:
            os.makedirs(image_dir_full, exist_ok=True)
            for item_id, item_info in manifest.items():
                if 'image' in item_info['media']:
                    img_href = item_info['href']
                    # Build full zip path for image
                    # Hrefs in OPF are relative to OPF file
                    img_zip_path = os.path.normpath(os.path.join(opf_dir, unquote(img_href))).replace('\\', '/')
                    try:
                        img_data = epub.read(img_zip_path)
                        dest_img_path = os.path.join(image_dir_full, os.path.basename(unquote(img_href)))
                        with open(dest_img_path, 'wb') as img_out:
                            img_out.write(img_data)
                    except KeyError:
                        # Zip path might not have relative directory, try direct
                        try:
                            img_data = epub.read(unquote(img_href))
                            dest_img_path = os.path.join(image_dir_full, os.path.basename(unquote(img_href)))
                            with open(dest_img_path, 'wb') as img_out:
                                img_out.write(img_data)
                        except Exception as ex:
                            print(f"Warning: Could not extract image {img_href}: {ex}", file=sys.stderr)

        # 7. Convert HTML Chapters to Markdown
        md_parser = HTMLToMarkdownParser(extract_images=extract_images, image_dir=image_subdir)
        full_markdown = []
        
        # Add book title/author header
        full_markdown.append(f"# {title}")
        full_markdown.append(f"**Author:** {author}\n\n---\n")

        print(f"Processing '{title}' with {len(spine)} chapters...")
        
        for i, idref in enumerate(spine, 1):
            item_info = manifest[idref]
            html_href = item_info['href']
            # Hrefs are relative to OPF file path
            html_zip_path = os.path.normpath(os.path.join(opf_dir, unquote(html_href))).replace('\\', '/')
            
            try:
                html_bytes = epub.read(html_zip_path)
            except KeyError:
                # Try direct path
                try:
                    html_bytes = epub.read(unquote(html_href))
                except Exception as ex:
                    print(f"Warning: Spine item {idref} ({html_href}) not found in archive. Skipping.", file=sys.stderr)
                    continue

            # Decode text
            try:
                html_content = html_bytes.decode('utf-8')
            except UnicodeDecodeError:
                html_content = html_bytes.decode('latin-1')

            print(f"  [{i}/{len(spine)}] Converting chapter: {os.path.basename(html_href)}")
            chapter_md = md_parser.convert(html_content)
            if chapter_md:
                full_markdown.append(chapter_md)
                full_markdown.append("\n\n---\n") # Section separator

        # Remove the final section separator
        if full_markdown and full_markdown[-1] == "\n\n---\n":
            full_markdown.pop()

        # Write out Markdown file
        try:
            with open(output_md_path, 'w', encoding='utf-8') as md_file:
                md_file.write("\n".join(full_markdown))
            print(f"Conversion complete! Markdown saved to '{output_md_path}'")
            return 0
        except Exception as e:
            print(f"Error saving markdown output: {e}", file=sys.stderr)
            return 1


def main():
    parser = argparse.ArgumentParser(
        description="Convert EPUB e-books to clean, standalone Markdown documents."
    )
    parser.add_argument("epub_file", help="Path to the input .epub file")
    parser.add_argument(
        "-o", "--output", 
        help="Path to the output Markdown (.md) file. Defaults to same directory/base name."
    )
    parser.add_argument(
        "-i", "--extract-images", 
        action="store_true", 
        help="Extract embedded images to an 'images/' folder relative to the output file"
    )

    args = parser.parse_args()

    # Determine default output file path
    if not args.output:
        base, _ = os.path.splitext(args.epub_file)
        args.output = base + ".md"

    sys.exit(parse_epub(args.epub_file, args.output, args.extract_images))


if __name__ == "__main__":
    main()
