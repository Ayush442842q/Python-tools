#!/usr/bin/env python3
"""
Markdown to Jira Wiki Markup Converter (and vice versa)
Translate document formatting between Markdown and Jira Wiki styles.
Supports headings, text styling, lists, links, code blocks, tables, and blockquotes.
"""

import argparse
import re
import sys

# ANSI Colors for terminal output
COLOR_HEADER = "\033[95m"
COLOR_BLUE = "\033[94m"
COLOR_GREEN = "\033[92m"
COLOR_WARNING = "\033[93m"
COLOR_FAIL = "\033[91m"
COLOR_END = "\033[0m"
COLOR_BOLD = "\033[1m"


def print_banner():
    banner = f"""{COLOR_HEADER}{COLOR_BOLD}
 ███▄ ▄███▓ ▓█████▄    ▄▄▄█████▓ ▒█████       ▄▄▄▄███▄▄▄▄      ▓█████▄ 
 ▓██▒▀█▀ ██▒ ▒██▀ ██▌   ▓  ██▒ ▓▒▒██▒  ██▒    ▓  ██▒ ▓▒ ██▒    ▒██▀ ██▌
 ▓██    ▓██░ ░██   █▌   ▒ ▓██░ ▒░▒██░  ██▒    ▒ ▓██░ ▒░ ██░    ░██   █▌
 ▒██    ▒██  ░▓█▄   ▌   ░ ▓██▓ ░ ▒██   ██░    ░ ▓██▓ ░  ██░    ░▓█▄   ▌
 ▒██▒   ░██▒ ░▒████▓      ▒██▒ ░ ░ ████▓▒░      ▒██▒ ░  ██▒▒██░░▒████▓ 
 ░ ▒░   ░  ░  ▒▒▓  ▒      ▒ ░░   ░ ▒░▒░▒░       ▒ ░░    ░ ▒░ ░ ░▒▒▓  ▒ 
 ░  ░      ░  ░ ▒  ▒        ░      ░ ▒ ▒░         ░     ░ ░  ░  ░ ▒  ▒ 
 ░      ░     ░ ░  ░      ░      ░ ░ ░ ▒        ░       ░      ░ ░  ░ 
        ░       ░                    ░ ░                ░        ░     
              ░                                                ░       
{COLOR_END}{COLOR_BLUE}    Markdown <-> Jira Wiki Markup Converter - Standard Library Edition{COLOR_END}
"""
    print(banner, file=sys.stderr)


def md_to_jira(md_text):
    """Convert Markdown text to Jira Wiki Markup."""
    lines = md_text.splitlines()
    jira_lines = []
    
    in_code_block = False
    code_lang = ""
    code_block_lines = []
    
    in_table = False
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # 1. Code Block Handling
        if line.strip().startswith("```"):
            if not in_code_block:
                in_code_block = True
                match = re.match(r"^```(\w*)", line.strip())
                code_lang = match.group(1) if match else ""
                code_block_lines = []
            else:
                in_code_block = False
                lang_param = f":language={code_lang}" if code_lang else ""
                jira_lines.append(f"{{code{lang_param}}}")
                jira_lines.extend(code_block_lines)
                jira_lines.append("{code}")
            i += 1
            continue
            
        if in_code_block:
            code_block_lines.append(line)
            i += 1
            continue

        # 2. Blockquote Handling
        if line.strip().startswith(">"):
            # Accumulate blockquote lines
            bq_lines = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                bq_lines.append(re.sub(r"^>\s?", "", lines[i]))
                i += 1
            jira_lines.append("{quote}")
            jira_lines.append("\n".join(bq_lines))
            jira_lines.append("{quote}")
            continue

        # 3. Headings
        heading_match = re.match(r"^(#{1,6})\s+(.*)$", line)
        if heading_match:
            level = len(heading_match.group(1))
            title = heading_match.group(2)
            jira_lines.append(f"h{level}. {title}")
            i += 1
            continue

        # 4. Tables
        # Check if line looks like a table row
        if re.match(r"^\s*\|.*\|\s*$", line):
            # Check if next line is a separator line (e.g. |---|---|)
            is_separator = False
            if i + 1 < len(lines) and re.match(r"^\s*\|[\s\-\|:]*\|\s*$", lines[i + 1]):
                is_separator = True
            
            if is_separator:
                # This line is the header line
                headers = [h.strip() for h in line.strip().split("|")[1:-1]]
                jira_lines.append("||" + "||".join(headers) + "||")
                i += 2  # Skip separator line
                in_table = True
                continue
            else:
                # Ordinary table row
                cells = [c.strip() for c in line.strip().split("|")[1:-1]]
                # Inline style conversion for cells
                converted_cells = [convert_inline_md_to_jira(c) for c in cells]
                jira_lines.append("|" + "|".join(converted_cells) + "|")
                i += 1
                in_table = True
                continue
        else:
            if in_table:
                in_table = False

        # 5. Lists (Unordered & Ordered)
        # Match unordered lists: *, -, +
        ul_match = re.match(r"^(\s*)([\*\-\+])\s+(.*)$", line)
        if ul_match:
            indent = len(ul_match.group(1))
            depth = (indent // 2) + 1  # Assume 2 spaces per indent level
            content = convert_inline_md_to_jira(ul_match.group(3))
            jira_lines.append("*" * depth + " " + content)
            i += 1
            continue

        # Match ordered lists: 1. or 1)
        ol_match = re.match(r"^(\s*)(\d+[\.\)])\s+(.*)$", line)
        if ol_match:
            indent = len(ol_match.group(1))
            depth = (indent // 2) + 1
            content = convert_inline_md_to_jira(ol_match.group(3))
            jira_lines.append("#" * depth + " " + content)
            i += 1
            continue

        # 6. Normal Line with Inline Conversions
        jira_lines.append(convert_inline_md_to_jira(line))
        i += 1

    return "\n".join(jira_lines)


def convert_inline_md_to_jira(text):
    """Convert inline Markdown styling (bold, italic, links, code, strikethrough) to Jira."""
    # Bold: **text** or __text__ -> *text*
    text = re.sub(r"\*\*(.*?)\*\*", r"*\1*", text)
    text = re.sub(r"__(.*?)__", r"*\1*", text)

    # Italic: *text* or _text_ -> _text_
    # Make sure we don't match the asterisks we just processed for bold or lists
    text = re.sub(r"\*(.*?)\*", r"_\1_", text)
    text = re.sub(r"_(.*?)_", r"_\1_", text)

    # Strikethrough: ~~text~~ -> -text-
    text = re.sub(r"~~(.*?)~~", r"-\1-", text)

    # Inline code: `text` -> {{text}}
    text = re.sub(r"`([^`]+)`", r"{{\1}}", text)

    # Links: [Text](URL) -> [Text|URL]
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"[\1|\2]", text)
    
    # Auto-links: <URL> -> [URL]
    text = re.sub(r"<((https?|ftp|file)://[^>]+)>", r"[\1]", text)

    # Image links: ![AltText](URL) -> !URL!
    text = re.sub(r"!\[.*?\]\((.*?)\)", r"!\1!", text)

    return text


def jira_to_md(jira_text):
    """Convert Jira Wiki Markup to Markdown."""
    lines = jira_text.splitlines()
    md_lines = []
    
    in_code_block = False
    in_quote = False
    quote_lines = []
    in_table = False
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # 1. Code Block Handling
        if re.match(r"^\{code(:language=(\w+))?\}", line.strip()):
            if not in_code_block:
                in_code_block = True
                match = re.match(r"^\{code:language=(\w+)\}", line.strip())
                lang = match.group(1) if match else ""
                md_lines.append(f"```{lang}")
            else:
                in_code_block = False
                md_lines.append("```")
            i += 1
            continue
            
        if in_code_block:
            md_lines.append(line)
            i += 1
            continue

        # 2. Quote Block Handling
        if line.strip() == "{quote}":
            if not in_quote:
                in_quote = True
                quote_lines = []
            else:
                in_quote = False
                for ql in quote_lines:
                    md_lines.append(f"> {ql}")
            i += 1
            continue
            
        if in_quote:
            quote_lines.append(line)
            i += 1
            continue

        # 3. Headings
        heading_match = re.match(r"^h([1-6])\.\s+(.*)$", line)
        if heading_match:
            level = int(heading_match.group(1))
            title = heading_match.group(2)
            md_lines.append("#" * level + " " + title)
            i += 1
            continue

        # 4. Tables
        # Jira table headers: ||Header 1||Header 2||
        if line.startswith("||"):
            headers = [h.strip() for h in line.split("||")[1:-1]]
            md_lines.append("| " + " | ".join(headers) + " |")
            # Generate separator line
            md_lines.append("|" + "|".join(["---" for _ in headers]) + "|")
            in_table = True
            i += 1
            continue
        # Jira table row: |cell 1|cell 2|
        elif line.startswith("|") and not line.startswith("||"):
            cells = [c.strip() for c in line.split("|")[1:-1]]
            converted_cells = [convert_inline_jira_to_md(c) for c in cells]
            md_lines.append("| " + " | ".join(converted_cells) + " |")
            in_table = True
            i += 1
            continue
        else:
            if in_table:
                in_table = False

        # 5. Lists (Unordered & Ordered)
        # Jira Bullet list: * item, ** item
        ul_match = re.match(r"^(\*+)\s+(.*)$", line)
        if ul_match:
            depth = len(ul_match.group(1))
            indent = "  " * (depth - 1)
            content = convert_inline_jira_to_md(ul_match.group(2))
            md_lines.append(f"{indent}- {content}")
            i += 1
            continue

        # Jira Numbered list: # item, ## item
        ol_match = re.match(r"^(#+)\s+(.*)$", line)
        if ol_match:
            depth = len(ol_match.group(1))
            indent = "  " * (depth - 1)
            content = convert_inline_jira_to_md(ol_match.group(2))
            md_lines.append(f"{indent}1. {content}")
            i += 1
            continue

        # 6. Normal Line with Inline Conversions
        md_lines.append(convert_inline_jira_to_md(line))
        i += 1

    return "\n".join(md_lines)


def convert_inline_jira_to_md(text):
    """Convert inline Jira Wiki styling to Markdown."""
    # Bold: *text* -> **text**
    text = re.sub(r"\*(.*?)\*", r"**\1**", text)

    # Italic: _text_ -> *text*
    text = re.sub(r"_(.*?)_", r"*\1*", text)

    # Strikethrough: -text- -> ~~text~~
    # Be careful not to replace dashes inside links or lists
    text = re.sub(r"\b-(.*?)-\b", r"~~\1~~", text)

    # Inline code: {{text}} -> `text`
    text = re.sub(r"\{\{([^\}]+)\}\}", r"`\1`", text)

    # Links: [Text|URL] -> [Text](URL)
    text = re.sub(r"\[([^\|\]]+)\|([^\]]+)\]", r"[\1](\2)", text)
    
    # Auto-links: [URL] -> <URL>
    text = re.sub(r"\[((https?|ftp|file)://[^\]]+)\]", r"<\1>", text)

    # Image links: !URL! -> ![](URL)
    text = re.sub(r"!(https?://[^\s!]+)!", r"![](\1)", text)

    return text


def main():
    parser = argparse.ArgumentParser(
        description="Convert files or text between Markdown and Jira Wiki Markup bidirectional formatting."
    )
    parser.add_argument(
        "file",
        nargs="?",
        help="Path to the input file. If omitted, reads from standard input."
    )
    parser.add_argument(
        "-o", "--output",
        help="Path to write the converted output. If omitted, prints to stdout."
    )
    parser.add_argument(
        "-m", "--mode",
        choices=["md2jira", "jira2md", "auto"],
        default="auto",
        help="Conversion mode. 'auto' (default) infers mode from file extension or contents."
    )
    parser.add_argument(
        "--no-banner",
        action="store_true",
        help="Suppress the CLI graphical banner."
    )

    args = parser.parse_args()

    if not args.no_banner and not args.output:
        print_banner()

    # Read input text
    input_text = ""
    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                input_text = f.read()
        except Exception as e:
            print(f"{COLOR_FAIL}Error reading file '{args.file}': {e}{COLOR_END}", file=sys.stderr)
            sys.exit(1)
    else:
        # Check if stdin has content
        if not sys.stdin.isatty():
            input_text = sys.stdin.read()
        else:
            parser.print_help()
            sys.exit(0)

    # Determine mode
    mode = args.mode
    if mode == "auto":
        if args.file:
            if args.file.lower().endswith((".md", ".markdown")):
                mode = "md2jira"
            elif args.file.lower().endswith((".jira", ".txt")):
                # Check contents for common Jira patterns
                if "{code" in input_text or "h1." in input_text or "||" in input_text:
                    mode = "jira2md"
                else:
                    mode = "md2jira"
            else:
                mode = "md2jira"
        else:
            # Analyze stdin content
            if "h1." in input_text or "{code" in input_text or "||" in input_text:
                mode = "jira2md"
            else:
                mode = "md2jira"

    # Run Conversion
    if mode == "md2jira":
        if not args.output:
            print(f"{COLOR_GREEN}Translating Markdown to Jira Wiki Markup...{COLOR_END}\n", file=sys.stderr)
        output_text = md_to_jira(input_text)
    else:
        if not args.output:
            print(f"{COLOR_GREEN}Translating Jira Wiki Markup to Markdown...{COLOR_END}\n", file=sys.stderr)
        output_text = jira_to_md(input_text)

    # Write output
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output_text)
            print(f"{COLOR_GREEN}Success! Output written to '{args.output}'{COLOR_END}", file=sys.stderr)
        except Exception as e:
            print(f"{COLOR_FAIL}Error writing file '{args.output}': {e}{COLOR_END}", file=sys.stderr)
            sys.exit(1)
    else:
        print(output_text)


if __name__ == "__main__":
    main()
