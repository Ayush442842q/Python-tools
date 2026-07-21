#!/usr/bin/env python3
"""
HTML Formatter & Minifier - Format, beautify, or minify HTML documents.

This tool parses HTML files using the standard library html.parser, builds a
DOM-like tree, and outputs either a clean, human-readable indented format or
a fully minified, single-line format.
"""

import os
import sys
import argparse
from html.parser import HTMLParser


class Node:
    """A simple DOM-like node structure for formatting."""
    def __init__(self, node_type, tag=None, attrs=None, text=None):
        self.node_type = node_type  # 'element', 'text', 'comment', 'decl', 'root'
        self.tag = tag.lower() if tag else None
        self.attrs = attrs or []
        self.text = text
        self.children = []


class HTMLTreeBuilder(HTMLParser):
    """Parses HTML into a Node tree."""
    def __init__(self):
        super().__init__()
        self.root = Node('root')
        self.stack = [self.root]
        self.void_tags = {
            'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 
            'link', 'meta', 'param', 'source', 'track', 'wbr'
        }
        self.literal_tags = {'pre', 'code', 'script', 'style'}

    @property
    def current(self):
        return self.stack[-1]

    def handle_decl(self, decl):
        node = Node('decl', text=decl)
        self.current.children.append(node)

    def handle_comment(self, data):
        node = Node('comment', text=data)
        self.current.children.append(node)

    def handle_starttag(self, tag, attrs):
        node = Node('element', tag=tag, attrs=attrs)
        self.current.children.append(node)
        if tag.lower() not in self.void_tags:
            self.stack.append(node)

    def handle_endtag(self, tag):
        tag_lower = tag.lower()
        # Find the matching tag in the stack
        for i in range(len(self.stack) - 1, 0, -1):
            if self.stack[i].tag == tag_lower:
                # Close all intermediate unclosed tags (lenient parsing)
                while len(self.stack) > i:
                    self.stack.pop()
                break

    def handle_data(self, data):
        # Determine if we are inside a tag that preserves exact whitespaces
        in_literal = False
        for node in self.stack:
            if node.tag in self.literal_tags:
                in_literal = True
                break

        if in_literal:
            node = Node('text', text=data)
            self.current.children.append(node)
        else:
            # Strip outer spaces but keep single spaces between words
            cleaned = " ".join(data.split())
            if cleaned:
                node = Node('text', text=cleaned)
                self.current.children.append(node)


class HTMLFormatter:
    """Formats or minifies a Node tree."""
    def __init__(self, indent_size=2, minify=False, wrap_limit=80):
        self.indent_size = indent_size
        self.minify_mode = minify
        self.wrap_limit = wrap_limit
        self.inline_tags = {
            'a', 'abbr', 'span', 'strong', 'em', 'b', 'i', 'u', 'code', 
            'kbd', 'samp', 'var', 'cite', 'dfn', 'sub', 'sup', 'small', 
            'mark', 'time', 'q', 'button', 'input', 'label', 'select', 'textarea'
        }

    def _format_attrs(self, attrs):
        if not attrs:
            return ""
        result = []
        for name, val in attrs:
            if val is None:
                result.append(name)
            else:
                result.append(f'{name}="{val}"')
        return " " + " ".join(result)

    def _is_all_inline_children(self, node):
        """Check if all children of a node can be printed inline."""
        if not node.children:
            return True
        for child in node.children:
            if child.node_type == 'element' and child.tag not in self.inline_tags:
                return False
        return True

    def minify(self, node):
        """Convert tree to a single line with minimal whitespace."""
        if node.node_type == 'root':
            return "".join(self.minify(c) for c in node.children)
        elif node.node_type == 'text':
            return node.text
        elif node.node_type == 'comment':
            return f"<!--{node.text.strip()}-->"
        elif node.node_type == 'decl':
            return f"<!{node.text.strip()}>"
        elif node.node_type == 'element':
            attrs_str = self._format_attrs(node.attrs)
            if not node.children:
                if node.tag in {'meta', 'link', 'img', 'br', 'hr', 'input'}:
                    return f"<{node.tag}{attrs_str}>"
                return f"<{node.tag}{attrs_str}></{node.tag}>"
            
            inner = "".join(self.minify(c) for c in node.children)
            # Avoid wrapping spaces for scripts/styles
            if node.tag in {'script', 'style', 'pre'}:
                # Keep spacing inside intact
                inner = "".join(c.text if c.node_type == 'text' else self.minify(c) for c in node.children)
                
            return f"<{node.tag}{attrs_str}>{inner}</{node.tag}>"
        return ""

    def beautify(self, node, level=0):
        """Beautify HTML with consistent indentation."""
        indent = " " * (level * self.indent_size)
        
        if node.node_type == 'root':
            return "\n".join(self.beautify(c, level) for c in node.children).strip() + "\n"
            
        elif node.node_type == 'text':
            return indent + node.text
            
        elif node.node_type == 'comment':
            return f"{indent}<!-- {node.text.strip()} -->"
            
        elif node.node_type == 'decl':
            return f"{indent}<!{node.text.strip()}>"
            
        elif node.node_type == 'element':
            attrs_str = self._format_attrs(node.attrs)
            
            # Self-closing tags
            if not node.children:
                if node.tag in {'meta', 'link', 'img', 'br', 'hr', 'input'}:
                    return f"{indent}<{node.tag}{attrs_str}>"
                return f"{indent}<{node.tag}{attrs_str}></{node.tag}>"
            
            # Literal block tags (script, style, pre)
            if node.tag in {'pre', 'code', 'script', 'style'}:
                content = []
                for child in node.children:
                    if child.node_type == 'text':
                        content.append(child.text)
                    else:
                        content.append(self.beautify(child, level + 1))
                inner = "".join(content)
                # Format opening and closing tags nicely, but keep inner intact
                return f"{indent}<{node.tag}{attrs_str}>\n{inner.rstrip()}\n{indent}</{node.tag}>"

            # Check if we can inline all children (e.g. <p>Hello <b>World</b></p>)
            if self._is_all_inline_children(node):
                # Render children inline
                inline_content = []
                for child in node.children:
                    if child.node_type == 'text':
                        inline_content.append(child.text)
                    elif child.node_type == 'element':
                        attrs_sub = self._format_attrs(child.attrs)
                        sub_inner = "".join(c.text for c in child.children if c.node_type == 'text')
                        if child.children:
                            inline_content.append(f"<{child.tag}{attrs_sub}>{sub_inner}</{child.tag}>")
                        else:
                            inline_content.append(f"<{child.tag}{attrs_sub}>")
                
                joined_inner = "".join(inline_content)
                full_tag = f"<{node.tag}{attrs_str}>{joined_inner}</{node.tag}>"
                
                # Check line limit wrapping
                if len(indent) + len(full_tag) <= self.wrap_limit:
                    return f"{indent}{full_tag}"

            # General block tag layout
            open_tag = f"{indent}<{node.tag}{attrs_str}>"
            close_tag = f"{indent}</{node.tag}>"
            
            formatted_children = []
            for child in node.children:
                formatted_child = self.beautify(child, level + 1)
                if formatted_child.strip():
                    formatted_children.append(formatted_child)
            
            joined_children = "\n".join(formatted_children)
            return f"{open_tag}\n{joined_children}\n{close_tag}"

        return ""


def main():
    parser = argparse.ArgumentParser(
        description="HTML Formatter & Minifier - Clean, beautify or compress HTML code."
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="HTML file to format (if omitted, reads from standard input)"
    )
    parser.add_argument(
        "-i", "--indent",
        type=int,
        default=2,
        help="Indentation size in spaces (default: 2)"
    )
    parser.add_argument(
        "-m", "--minify",
        action="store_true",
        help="Minify HTML output into a compact single-line form"
    )
    parser.add_argument(
        "-w", "--wrap",
        type=int,
        default=80,
        help="Line length limit for inlining tags (default: 80)"
    )
    parser.add_argument(
        "-o", "--output",
        help="Output file path (default: prints to stdout)"
    )

    args = parser.parse_args()

    # Read input
    if args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                html_content = f.read()
        except FileNotFoundError:
            print(f"Error: File '{args.file}' not found.", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error reading file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        # Read from stdin
        if sys.stdin.isatty():
            print("Enter/Paste HTML content (Press Ctrl+D/Ctrl+Z to end):")
        html_content = sys.stdin.read()

    if not html_content.strip():
        print("Error: Empty HTML content provided.", file=sys.stderr)
        sys.exit(1)

    # Parse HTML
    builder = HTMLTreeBuilder()
    try:
        builder.feed(html_content)
        builder.close()
    except Exception as e:
        print(f"Error parsing HTML: {e}", file=sys.stderr)
        sys.exit(1)

    # Format Tree
    formatter = HTMLFormatter(indent_size=args.indent, minify=args.minify, wrap_limit=args.wrap)
    if args.minify:
        output_content = formatter.minify(builder.root)
    else:
        output_content = formatter.beautify(builder.root)

    # Write Output
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(output_content)
            print(f"Success: Output written to '{args.output}'")
        except Exception as e:
            print(f"Error writing output file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        sys.stdout.write(output_content)


if __name__ == "__main__":
    main()
