#!/usr/bin/env python3
"""
Converts standard Markdown into Confluence Storage Format (XHTML) for easy copy-pasting
or publishing to Confluence via its REST API.
"""

import sys
import os
import re
import argparse

def escape_html(text):
    """Escapes special HTML characters."""
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&#x27;')

class MarkdownToConfluence:
    def __init__(self):
        self.in_list = False
        self.list_type = None  # 'ul' or 'ol'
        self.in_blockquote = False
        self.in_code_block = False
        self.code_block_lang = ""
        self.code_block_lines = []
        self.in_table = False
        self.table_headers = []
        self.table_alignments = []
        self.table_rows = []

    def convert(self, md_text):
        """Converts Markdown text into Confluence Storage Format (XHTML)."""
        lines = md_text.splitlines()
        xhtml_output = []
        
        i = 0
        while i < len(lines):
            line = lines[i]
            
            # --- Code Blocks ---
            if line.strip().startswith("```"):
                if self.in_code_block:
                    # End of code block
                    code_content = "\n".join(self.code_block_lines)
                    lang_param = ""
                    if self.code_block_lang:
                        lang_param = f'<ac:parameter ac:name="language">{escape_html(self.code_block_lang)}</ac:parameter>'
                    
                    xhtml_output.append(
                        f'<ac:structured-macro ac:name="code" ac:schema-version="1">\n'
                        f'  {lang_param}\n'
                        f'  <ac:plain-text-body><![CDATA[{code_content}]]></ac:plain-text-body>\n'
                        f'</ac:structured-macro>'
                    )
                    self.in_code_block = False
                    self.code_block_lines = []
                else:
                    # Start of code block
                    self.in_code_block = True
                    self.code_block_lang = line.strip()[3:].strip()
                i += 1
                continue
                
            if self.in_code_block:
                self.code_block_lines.append(line)
                i += 1
                continue

            # Close list if line is not a list item
            is_list_item = re.match(r'^(\s*)[\*\-\+]\s+(.*)', line) or re.match(r'^(\s*)\d+\.\s+(.*)', line)
            if self.in_list and not is_list_item and line.strip() != "":
                xhtml_output.append(f"</{self.list_type}>")
                self.in_list = False
                self.list_type = None

            # Close blockquote if line is not a blockquote
            is_blockquote = line.strip().startswith(">")
            if self.in_blockquote and not is_blockquote and line.strip() != "":
                xhtml_output.append("</ac:rich-text-body>\n</ac:structured-macro>")
                self.in_blockquote = False

            # Close table if line is not a table row
            is_table_row = line.strip().startswith("|")
            if self.in_table and not is_table_row and line.strip() != "":
                xhtml_output.append(self.render_table())
                self.in_table = False
                self.table_headers = []
                self.table_alignments = []
                self.table_rows = []

            # Skip empty lines, but close structures
            if line.strip() == "":
                i += 1
                continue

            # --- Headers ---
            header_match = re.match(r'^(#{1,6})\s+(.*)', line)
            if header_match:
                level = len(header_match.group(1))
                content = self.parse_inline(header_match.group(2))
                xhtml_output.append(f"<h{level}>{content}</h{level}>")
                i += 1
                continue

            # --- Blockquotes (Rendered as Confluence Info/Panel macros) ---
            if line.strip().startswith(">"):
                content = line.strip()[1:].strip()
                if not self.in_blockquote:
                    self.in_blockquote = True
                    xhtml_output.append(
                        '<ac:structured-macro ac:name="info" ac:schema-version="1">\n'
                        '<ac:rich-text-body>'
                    )
                xhtml_output.append(f"<p>{self.parse_inline(content)}</p>")
                i += 1
                continue

            # --- Lists ---
            # Unordered lists
            ul_match = re.match(r'^(\s*)[\*\-\+]\s+(.*)', line)
            if ul_match:
                content = self.parse_inline(ul_match.group(2))
                if not self.in_list or self.list_type != 'ul':
                    if self.in_list:
                        xhtml_output.append(f"</{self.list_type}>")
                    self.in_list = True
                    self.list_type = 'ul'
                    xhtml_output.append("<ul>")
                xhtml_output.append(f"  <li>{content}</li>")
                i += 1
                continue

            # Ordered lists
            ol_match = re.match(r'^(\s*)\d+\.\s+(.*)', line)
            if ol_match:
                content = self.parse_inline(ol_match.group(2))
                if not self.in_list or self.list_type != 'ol':
                    if self.in_list:
                        xhtml_output.append(f"</{self.list_type}>")
                    self.in_list = True
                    self.list_type = 'ol'
                    xhtml_output.append("<ol>")
                xhtml_output.append(f"  <li>{content}</li>")
                i += 1
                continue

            # --- Tables ---
            if line.strip().startswith("|"):
                row_cells = [cell.strip() for cell in line.strip().split("|")[1:-1]]
                
                # Check if the next line is a separator line (e.g. |---|---|)
                if i + 1 < len(lines) and re.match(r'^\s*\|(\s*:?-+:?\s*\|)+\s*$', lines[i+1]):
                    self.in_table = True
                    self.table_headers = row_cells
                    # Determine alignments
                    separator_cells = [cell.strip() for cell in lines[i+1].strip().split("|")[1:-1]]
                    for cell in separator_cells:
                        if cell.startswith(":") and cell.endswith(":"):
                            self.table_alignments.append("center")
                        elif cell.endswith(":"):
                            self.table_alignments.append("right")
                        else:
                            self.table_alignments.append("left")
                    i += 2  # Skip header and separator
                    continue
                elif self.in_table:
                    self.table_rows.append(row_cells)
                    i += 1
                    continue
                else:
                    # Regular text starting with pipe or malformed table
                    pass

            # --- Paragraphs ---
            content = self.parse_inline(line.strip())
            xhtml_output.append(f"<p>{content}</p>")
            i += 1

        # Clean up remaining open blocks
        if self.in_list:
            xhtml_output.append(f"</{self.list_type}>")
        if self.in_blockquote:
            xhtml_output.append("</ac:rich-text-body>\n</ac:structured-macro>")
        if self.in_table:
            xhtml_output.append(self.render_table())
        if self.in_code_block:
            # Unclosed code block
            code_content = "\n".join(self.code_block_lines)
            xhtml_output.append(
                f'<ac:structured-macro ac:name="code" ac:schema-version="1">\n'
                f'  <ac:plain-text-body><![CDATA[{code_content}]]></ac:plain-text-body>\n'
                f'</ac:structured-macro>'
            )

        return "\n".join(xhtml_output)

    def render_table(self):
        """Renders the parsed table structure into Confluence HTML format."""
        html = ["<table>", "  <tbody>"]
        
        # Render Headers
        if self.table_headers:
            html.append("    <tr>")
            for idx, header in enumerate(self.table_headers):
                align = self.table_alignments[idx] if idx < len(self.table_alignments) else "left"
                align_style = f' style="text-align: {align};"' if align != "left" else ""
                html.append(f"      <th{align_style}>{self.parse_inline(header)}</th>")
            html.append("    </tr>")
            
        # Render Rows
        for row in self.table_rows:
            html.append("    <tr>")
            for idx, cell in enumerate(row):
                align = self.table_alignments[idx] if idx < len(self.table_alignments) else "left"
                align_style = f' style="text-align: {align};"' if align != "left" else ""
                html.append(f"      <td{align_style}>{self.parse_inline(cell)}</td>")
            html.append("    </tr>")
            
        html.extend(["  </tbody>", "</table>"])
        return "\n".join(html)

    def parse_inline(self, text):
        """Parses inline markdown formatting (bold, italic, code, links, images)."""
        # Escape raw HTML first
        text = escape_html(text)
        
        # Bold: **text** or __text__
        text = re.sub(r'\*\*(.*?)\*\*', r'<strong>\1</strong>', text)
        text = re.sub(r'__(.*?)__', r'<strong>\1</strong>', text)
        
        # Italic: *text* or _text_
        text = re.sub(r'\*(.*?)\*', r'<em>\1</em>', text)
        text = re.sub(r'_(.*?)_', r'<em>\1</em>', text)
        
        # Strikethrough: ~~text~~
        text = re.sub(r'~~(.*?)~~', r'<del>\1</del>', text)
        
        # Inline Code: `code`
        text = re.sub(r'`(.*?)`', r'<code>\1</code>', text)
        
        # Images: ![alt](url) -> Confluence Image macro
        # Format: <ac:image><ri:url ri:value="url"/></ac:image>
        text = re.sub(
            r'!\[(.*?)\]\((.*?)\)',
            r'<ac:image ac:alt="\1"><ri:url ri:value="\2"/></ac:image>',
            text
        )
        
        # Links: [text](url) -> Confluence format: <a href="url">text</a>
        text = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2">\1</a>', text)
        
        # Confluence status badge: {status:colour=Green|title=DONE} -> Confluence macro
        status_match = re.finditer(r'\{status:colour=([^|]+)\|title=([^}]+)\}', text)
        for m in status_match:
            color = m.group(1)
            title = m.group(2)
            macro = (
                f'<ac:structured-macro ac:name="status" ac:schema-version="1">\n'
                f'  <ac:parameter ac:name="title">{title}</ac:parameter>\n'
                f'  <ac:parameter ac:name="colour">{color}</ac:parameter>\n'
                f'</ac:structured-macro>'
            )
            text = text.replace(m.group(0), macro)

        return text

def main():
    parser = argparse.ArgumentParser(
        description="Convert Standard Markdown to Confluence Storage Format (XHTML)."
    )
    parser.add_argument(
        "input", 
        nargs="?", 
        help="Input Markdown file path. If omitted, reads from standard input."
    )
    parser.add_argument(
        "-o", "--output", 
        help="Output file path. If omitted, writes to standard output."
    )
    parser.add_argument(
        "--api-payload", 
        action="store_true", 
        help="Wrap the output in a Confluence REST API JSON page payload."
    )
    parser.add_argument(
        "--title", 
        default="Converted Page", 
        help="Page title to use when --api-payload is enabled."
    )
    parser.add_argument(
        "--space-key", 
        default="DS", 
        help="Confluence space key to use when --api-payload is enabled."
    )
    
    args = parser.parse_args()
    
    if args.input:
        try:
            with open(args.input, "r", encoding="utf-8") as f:
                md_content = f.read()
        except Exception as e:
            print(f"Error reading input file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Check if stdin is a TTY
        if sys.stdin.isatty():
            print("Reading from standard input... (Press Ctrl+D/Ctrl+Z to complete)", file=sys.stderr)
        md_content = sys.stdin.read()

    converter = MarkdownToConfluence()
    xhtml = converter.convert(md_content)

    if args.api_payload:
        import json
        payload = {
            "title": args.title,
            "type": "page",
            "space": {"key": args.space_key},
            "body": {
                "storage": {
                    "value": xhtml,
                    "representation": "storage"
                }
            }
        }
        output_data = json.dumps(payload, indent=2)
    else:
        output_data = xhtml

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output_data)
            print(f"Successfully converted and saved to {args.output}", file=sys.stderr)
        except Exception as e:
            print(f"Error writing output file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(output_data)

if __name__ == "__main__":
    main()
