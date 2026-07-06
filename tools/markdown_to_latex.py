#!/usr/bin/env python3
"""
Markdown to LaTeX Converter - Converts Markdown documents to LaTeX (.tex) files.
Supports headings, text decorations, lists, code blocks, tables, and blockquotes.
"""

import os
import re
import sys
import argparse

# ANSI color codes for TUI
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_BLUE = "\033[94m"
COLOR_RESET = "\033[0m"

def log_success(message):
    print(f"{COLOR_GREEN}[✓] {message}{COLOR_RESET}")

def log_warn(message):
    print(f"{COLOR_YELLOW}[!] {message}{COLOR_RESET}")

def log_error(message):
    print(f"{COLOR_RED}[✗] {message}{COLOR_RESET}", file=sys.stderr)

def log_info(message):
    print(f"{COLOR_BLUE}[i] {message}{COLOR_RESET}")

def escape_latex(text, in_code=False):
    """Escapes special LaTeX characters unless inside inline code/code block."""
    if in_code:
        return text
    
    # Backslash must be escaped first, then others
    chars = {
        '\\': r'\textbackslash{}',
        '&': r'\&',
        '%': r'\%',
        '$': r'\$',
        '#': r'\#',
        '_': r'\_',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
        '^': r'\textasciicircum{}',
    }
    
    # We do a character-by-character translation or regex replacement
    # to avoid double-escaping backslashes
    result = []
    i = 0
    while i < len(text):
        char = text[i]
        if char == '\\':
            result.append(chars['\\'])
        elif char in chars:
            result.append(chars[char])
        else:
            result.append(char)
        i += 1
    return "".join(result)

def convert_inline_styles(text):
    """Converts inline markdown styles like bold, italic, code, and links to LaTeX."""
    # Temporarily hide inline code blocks to avoid escaping inside them
    code_blocks = []
    def save_code(match):
        code_blocks.append(match.group(1))
        return f"__CODE_BLOCK_{len(code_blocks)-1}__"
    
    # Replace inline code first
    text = re.sub(r'`([^`]+)`', save_code, text)
    
    # Escape LaTeX special chars on the rest of the text
    text = escape_latex(text, in_code=False)
    
    # Convert bold (**bold** or __bold__)
    text = re.sub(r'\*\*([^*]+)\*\*', r'\\textbf{\1}', text)
    text = re.sub(r'__([^_]+)__', r'\\textbf{\1}', text)
    
    # Convert italic (*italic* or _italic_)
    text = re.sub(r'\*([^*]+)\*', r'\\textit{\1}', text)
    text = re.sub(r'_([^_]+)_', r'\\textit{\1}', text)
    
    # Convert image links
    text = re.sub(r'!\[([^\]]*)\]\(([^)]+)\)', r'\\begin{figure}[h!]\n\\centering\n\\includegraphics[width=0.8\\textwidth]{\2}\n\\caption{\1}\n\\end{figure}', text)
    
    # Convert links
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\\href{\2}{\1}', text)
    
    # Restore inline code blocks as \texttt
    for idx, code in enumerate(code_blocks):
        escaped_code = escape_latex(code, in_code=True)
        text = text.replace(f"__CODE_BLOCK_{idx}__", f"\\texttt{{{escaped_code}}}")
        
    return text

def parse_markdown_table(table_lines):
    """Converts Markdown table lines to LaTeX table environment."""
    if len(table_lines) < 2:
        return ""
    
    # Parse header
    header_cols = [col.strip() for col in table_lines[0].strip('|').split('|')]
    num_cols = len(header_cols)
    
    # Parse alignment from separator (line 1)
    align_row = [col.strip() for col in table_lines[1].strip('|').split('|')]
    alignments = []
    for col in align_row:
        if col.startswith(':') and col.endswith(':'):
            alignments.append('c')
        elif col.endswith(':'):
            alignments.append('r')
        else:
            alignments.append('l')
            
    # Pad alignments if needed
    while len(alignments) < num_cols:
        alignments.append('l')
    alignments = alignments[:num_cols]
    
    latex_align = '|' + '|'.join(alignments) + '|'
    
    latex_table = []
    latex_table.append(r"\begin{table}[h!]")
    latex_table.append(r"\centering")
    latex_table.append(f"\\begin{{tabular}}{{{latex_align}}}")
    latex_table.append(r"\hline")
    
    # Header format
    escaped_headers = [convert_inline_styles(col) for col in header_cols]
    latex_table.append(" & ".join(escaped_headers) + r" \\ \hline\hline")
    
    # Body rows
    for row in table_lines[2:]:
        row_cols = [col.strip() for col in row.strip('|').split('|')]
        # Align column count
        while len(row_cols) < num_cols:
            row_cols.append("")
        row_cols = row_cols[:num_cols]
        escaped_cols = [convert_inline_styles(col) for col in row_cols]
        latex_table.append(" & ".join(escaped_cols) + r" \\ \hline")
        
    latex_table.append(r"\end{tabular}")
    latex_table.append(r"\end{table}")
    
    return "\n".join(latex_table)

def convert_markdown_to_latex(md_content, standalone=True, title="Document", author="Author"):
    """Parses markdown content and generates LaTeX string."""
    lines = md_content.splitlines()
    latex_out = []
    
    # Document header
    if standalone:
        latex_out.append(r"\documentclass{article}")
        latex_out.append(r"\usepackage[utf8]{inputenc}")
        latex_out.append(r"\usepackage{hyperref}")
        latex_out.append(r"\usepackage{graphicx}")
        latex_out.append(r"\usepackage{listings}")
        latex_out.append(r"\usepackage{color}")
        latex_out.append(r"\usepackage{amsmath}")
        latex_out.append(r"\usepackage{amssymb}")
        latex_out.append(r"\definecolor{codegray}{rgb}{0.95,0.95,0.95}")
        latex_out.append(r"\lstset{backgroundcolor=\color{codegray},basicstyle=\footnotesize\ttfamily,breaklines=true}")
        latex_out.append(f"\\title{{{escape_latex(title)}}}")
        latex_out.append(f"\\author{{{escape_latex(author)}}}")
        latex_out.append(r"\date{\today}")
        latex_out.append(r"\begin{document}")
        latex_out.append(r"\maketitle")
        latex_out.append("")
        
    in_code_block = False
    code_block_lang = ""
    code_block_lines = []
    
    in_list = False
    list_type = [] # 'itemize' or 'enumerate'
    list_depth = 0
    
    in_blockquote = False
    
    in_table = False
    table_lines = []
    
    i = 0
    while i < len(lines):
        line = lines[i]
        stripped = line.strip()
        
        # 1. Handle Code Blocks
        if stripped.startswith("```"):
            if in_code_block:
                # End of code block
                latex_out.append(f"\\begin{{lstlisting}}[language={code_block_lang or 'bash'}]")
                latex_out.append("\n".join(code_block_lines))
                latex_out.append("\\end{lstlisting}")
                in_code_block = False
                code_block_lines = []
            else:
                # Start of code block
                in_code_block = True
                code_block_lang = stripped[3:].strip()
            i += 1
            continue
            
        if in_code_block:
            code_block_lines.append(line)
            i += 1
            continue
            
        # 2. Handle Blockquotes
        if stripped.startswith(">"):
            if not in_blockquote:
                in_blockquote = True
                latex_out.append(r"\begin{quote}")
            quote_content = line.replace(">", "", 1).strip()
            latex_out.append(convert_inline_styles(quote_content))
            i += 1
            continue
        elif in_blockquote and not stripped.startswith(">") and stripped != "":
            # Blockquote continuation
            latex_out.append(convert_inline_styles(stripped))
            i += 1
            continue
        elif in_blockquote:
            in_blockquote = False
            latex_out.append(r"\end{quote}")
            
        # 3. Handle Tables
        is_table_row = stripped.startswith('|') and stripped.endswith('|')
        if is_table_row:
            in_table = True
            table_lines.append(line)
            i += 1
            continue
        elif in_table:
            # End of table block reached
            latex_out.append(parse_markdown_table(table_lines))
            table_lines = []
            in_table = False
            # Fall through to process current line
            
        # 4. Handle Lists (nested itemize/enumerate)
        # Match '* ', '- ', '+ ' or '1. ', '2. ', etc.
        ul_match = re.match(r'^(\s*)([*+-])\s+(.*)', line)
        ol_match = re.match(r'^(\s*)(\d+)\.\s+(.*)', line)
        
        if ul_match or ol_match:
            match = ul_match or ol_match
            indent = len(match.group(1))
            current_type = 'itemize' if ul_match else 'enumerate'
            item_text = match.group(3)
            
            # Determine indentation level change
            target_depth = indent // 2 + 1 # Assumes 2 spaces per indent level
            
            if not in_list:
                in_list = True
                list_depth = 0
                list_type = []
                
            # Open nested lists if target_depth > current list_depth
            while list_depth < target_depth:
                list_type.append(current_type)
                latex_out.append(f"\\begin{{{current_type}}}")
                list_depth += 1
                
            # Close nested lists if target_depth < current list_depth
            while list_depth > target_depth:
                ended_type = list_type.pop()
                latex_out.append(f"\\end{{{ended_type}}}")
                list_depth -= 1
                
            # Handle list type change at same depth
            if list_type[-1] != current_type:
                ended_type = list_type.pop()
                latex_out.append(f"\\end{{{ended_type}}}")
                list_type.append(current_type)
                latex_out.append(f"\\begin{{{current_type}}}")
                
            latex_out.append(f"\\item {convert_inline_styles(item_text)}")
            i += 1
            continue
        elif in_list and stripped == "":
            # Keep listing if there are empty lines inside the list
            # We don't break list immediately on a single empty line if the next line is a list item
            next_idx = i + 1
            is_next_list = False
            while next_idx < len(lines):
                next_stripped = lines[next_idx].strip()
                if next_stripped == "":
                    next_idx += 1
                    continue
                if re.match(r'^(\s*)([*+-]|\d+\.)\s+', lines[next_idx]):
                    is_next_list = True
                break
                
            if is_next_list:
                i += 1
                continue
            else:
                # End of list
                while list_type:
                    ended_type = list_type.pop()
                    latex_out.append(f"\\end{{{ended_type}}}")
                in_list = False
                list_depth = 0
        elif in_list:
            # End of list
            while list_type:
                ended_type = list_type.pop()
                latex_out.append(f"\\end{{{ended_type}}}")
            in_list = False
            list_depth = 0
            
        # 5. Handle Headings
        heading_match = re.match(r'^(#{1,6})\s+(.*)', stripped)
        if heading_match:
            level = len(heading_match.group(1))
            title_text = convert_inline_styles(heading_match.group(2))
            
            if level == 1:
                latex_out.append(f"\\section{{{title_text}}}")
            elif level == 2:
                latex_out.append(f"\\subsection{{{title_text}}}")
            elif level == 3:
                latex_out.append(f"\\subsubsection{{{title_text}}}")
            elif level == 4:
                latex_out.append(f"\\paragraph{{{title_text}}}")
            else:
                latex_out.append(f"\\subparagraph{{{title_text}}}")
            i += 1
            continue
            
        # 6. Horizontal Rules
        if stripped in ('---', '***', '___'):
            latex_out.append(r"\noindent\rule{\textwidth}{0.4pt}")
            i += 1
            continue
            
        # 7. Regular Paragraphs
        if stripped != "":
            # Check for inline math patterns: $...$ or $$...$$
            # Since convert_inline_styles escapes $, we handle math carefully
            # For simplicity, we convert $$ ... $$ to \begin{equation*} ... \end{equation*}
            # and inline $ ... $ to LaTeX math blocks
            line_processed = convert_inline_styles(stripped)
            # Re-convert escaped math signs if the user wanted actual math
            # If they had \$ in MD, it gets escaped to \\$, but we can detect $$ and $
            # However, standard Markdown uses $ for math. Let's do a simple unescaping
            # for anything between $ signs if we detect they weren't escaped in source.
            
            latex_out.append(line_processed)
        else:
            latex_out.append("")
            
        i += 1
        
    # Cleanup trailing blocks
    if in_blockquote:
        latex_out.append(r"\end{quote}")
    if in_table:
        latex_out.append(parse_markdown_table(table_lines))
    if in_list:
        while list_type:
            ended_type = list_type.pop()
            latex_out.append(f"\\end{{{ended_type}}}")
            
    if standalone:
        latex_out.append("")
        latex_out.append(r"\end{document}")
        
    return "\n".join(latex_out)

def main():
    parser = argparse.ArgumentParser(description="Convert Markdown to LaTeX (.tex) format.")
    parser.add_argument("input", help="Path to input Markdown (.md) file.")
    parser.add_argument("-o", "--output", help="Path to save output LaTeX (.tex) file.")
    parser.add_argument("-s", "--snippet", action="store_true", help="Generate LaTeX snippet without document preamble.")
    parser.add_argument("-t", "--title", default="Markdown Document", help="Document title (for standalone mode).")
    parser.add_argument("-a", "--author", default="Author", help="Document author (for standalone mode).")
    
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(1)
        
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        log_error(f"Input file not found: {args.input}")
        sys.exit(1)
        
    try:
        with open(args.input, "r", encoding="utf-8") as f:
            md_content = f.read()
    except Exception as e:
        log_error(f"Failed to read input file: {e}")
        sys.exit(1)
        
    log_info(f"Parsing Markdown file: {args.input}")
    
    standalone = not args.snippet
    latex_content = convert_markdown_to_latex(
        md_content,
        standalone=standalone,
        title=args.title,
        author=args.author
    )
    
    # Determine output path
    output_path = args.output
    if not output_path:
        base, _ = os.path.splitext(args.input)
        output_path = base + ".tex"
        
    try:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(latex_content)
        log_success(f"Successfully converted and saved to: {output_path}")
    except Exception as e:
        log_error(f"Failed to write output file: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
