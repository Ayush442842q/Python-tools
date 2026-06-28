#!/usr/bin/env python3
"""
Markdown Code Block Runner
Finds, executes, and updates the output of code blocks in Markdown files.
Supports Python, Bash/Shell, and Powershell.
"""

import os
import re
import sys
import argparse
import subprocess
import tempfile
from typing import List, Tuple, Optional

# ANSI Colors
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"

SUPPORTED_LANGUAGES = {
    'python': 'py',
    'py': 'py',
    'bash': 'sh',
    'sh': 'sh',
    'shell': 'sh',
    'powershell': 'ps1',
    'ps1': 'ps1',
}

def run_code(lang: str, code: str, timeout: float = 10.0) -> Tuple[int, str, str]:
    """Execute code in a subprocess based on the language."""
    lang_lower = lang.lower().strip()
    ext = SUPPORTED_LANGUAGES.get(lang_lower)
    if not ext:
        raise ValueError(f"Unsupported language: {lang}")
        
    with tempfile.NamedTemporaryFile(mode='w', suffix=f'.{ext}', delete=False, encoding='utf-8') as temp:
        temp.write(code)
        temp_path = temp.name

    try:
        if ext == 'py':
            cmd = [sys.executable, temp_path]
        elif ext == 'sh':
            # Use bash if available, fallback to sh
            shell_bin = 'bash' if shutil_which('bash') else 'sh'
            cmd = [shell_bin, temp_path]
        elif ext == 'ps1':
            cmd = ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', temp_path]
        else:
            raise ValueError(f"Unmapped extension for: {lang}")

        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Execution timed out after {timeout} seconds."
    except Exception as e:
        return -1, "", f"Execution failed: {e}"
    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass

def shutil_which(cmd: str) -> bool:
    """Helper to check if command exists on system path."""
    import shutil
    return shutil.which(cmd) is not None

def parse_markdown_with_outputs(content: str) -> List[dict]:
    """
    Parse markdown file content into code blocks and text segments,
    tracking existing output markers:
    <!-- block-output: start -->
    ```output
    ...
    ```
    <!-- block-output: end -->
    """
    # Regex to find code blocks
    code_block_re = re.compile(
        r'^(?P<fence>```+)(?P<lang>\w+)?\s*\n(?P<code>.*?)^(?P=fence)\s*$',
        re.MULTILINE | re.DOTALL
    )
    
    output_block_re = re.compile(
        r'^\s*<!-- block-output: start -->\s*\n```output\s*\n(?P<output>.*?)```\s*\n<!-- block-output: end -->\s*$',
        re.MULTILINE | re.DOTALL
    )
    
    parts = []
    last_idx = 0
    
    # We will search sequentially
    for match in code_block_re.finditer(content):
        # Add preceding text
        parts.append({
            'type': 'text',
            'content': content[last_idx:match.start()]
        })
        
        # Check if right after this code block there is an output block
        block_end = match.end()
        next_text = content[block_end:block_end + 1000] # Check first 1000 chars ahead
        output_match = output_block_re.match(next_text)
        
        existing_output = None
        output_len = 0
        if output_match:
            existing_output = output_match.group('output')
            output_len = output_match.end()
            
        parts.append({
            'type': 'code',
            'lang': match.group('lang') or "",
            'code': match.group('code'),
            'fence': match.group('fence'),
            'existing_output': existing_output,
            'output_raw_length': output_len, # length of output block including comments
            'start': match.start(),
            'end': match.end()
        })
        
        last_idx = block_end + output_len
        
    parts.append({
        'type': 'text',
        'content': content[last_idx:]
    })
    
    return parts

def run_file(file_path: str, lang_filter: Optional[str], interactive: bool, update: bool, timeout: float):
    """Run code blocks in a markdown file and optionally update them."""
    if not os.path.exists(file_path):
        print(f"{RED}File not found: {file_path}{RESET}", file=sys.stderr)
        return False

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    parts = parse_markdown_with_outputs(content)
    code_blocks = [p for p in parts if p['type'] == 'code']
    
    if not code_blocks:
        print(f"{YELLOW}No code blocks found in {file_path}.{RESET}")
        return True

    print(f"{BOLD}{CYAN}Processing {file_path} ({len(code_blocks)} code blocks found)...{RESET}")
    
    modified = False
    
    for idx, block in enumerate(code_blocks, 1):
        lang = block['lang']
        code = block['code']
        
        # Filter by language
        if not lang or lang.lower().strip() not in SUPPORTED_LANGUAGES:
            continue
        if lang_filter and lang.lower().strip() != lang_filter.lower().strip():
            continue
            
        print(f"\n{BOLD}Block #{idx} [{lang}]:{RESET}")
        print("-" * 40)
        # Show first 5 lines of code
        code_preview = "\n".join(code.splitlines()[:5])
        if len(code.splitlines()) > 5:
            code_preview += "\n..."
        print(code_preview)
        print("-" * 40)
        
        if interactive:
            ans = input(f"Execute block #{idx}? [y/N/q]: ").strip().lower()
            if ans == 'q':
                break
            if ans != 'y':
                print("Skipped.")
                continue

        print(f"{YELLOW}Running...{RESET}")
        code_val, stdout, stderr = run_code(lang, code, timeout)
        
        print(f"Exit code: {code_val}")
        if stdout:
            print(f"{GREEN}Stdout:{RESET}\n{stdout.strip()}")
        if stderr:
            print(f"{RED}Stderr:{RESET}\n{stderr.strip()}")
            
        if update:
            # Prepare new output string
            combined_output = ""
            if stdout:
                combined_output += stdout
            if stderr:
                combined_output += f"--- STDERR ---\n{stderr}"
                
            block['new_output'] = combined_output
            modified = True
            
    if update and modified:
        # Reconstruct markdown
        new_content = ""
        for part in parts:
            if part['type'] == 'text':
                new_content += part['content']
            elif part['type'] == 'code':
                # Write original code block
                new_content += f"{part['fence']}{part['lang']}\n{part['code']}{part['fence']}\n"
                
                # Check if we ran this block and generated new output
                if 'new_output' in part:
                    new_output = part['new_output']
                    if new_output.strip():
                        new_content += "<!-- block-output: start -->\n```output\n"
                        new_content += new_output
                        if not new_output.endswith('\n'):
                            new_content += '\n'
                        new_content += "```\n<!-- block-output: end -->\n"
                elif part['existing_output'] is not None:
                    # Preserve existing output block if we didn't run it
                    new_content += "<!-- block-output: start -->\n```output\n"
                    new_content += part['existing_output']
                    new_content += "```\n<!-- block-output: end -->\n"
                    
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"\n{BOLD}{GREEN}Successfully updated {file_path}!{RESET}")
        
    return True

def main():
    parser = argparse.ArgumentParser(
        description="Extract and run code blocks from Markdown files, inserting execution output.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/markdown_code_runner.py README.md --interactive
  python tools/markdown_code_runner.py doc.md --update --timeout 5.0
        """
    )
    parser.add_argument("file", help="Path to Markdown file to run code from.")
    parser.add_argument("-l", "--lang", help="Filter by code block language (python, bash, sh, powershell)")
    parser.add_argument("-i", "--interactive", action="store_true", help="Ask for confirmation before running each code block")
    parser.add_argument("-u", "--update", action="store_true", help="Insert or update execution output directly in the Markdown file")
    parser.add_argument("-t", "--timeout", type=float, default=10.0, help="Maximum execution time for each code block (seconds)")
    
    args = parser.parse_args()
    run_file(
        file_path=args.file,
        lang_filter=args.lang,
        interactive=args.interactive,
        update=args.update,
        timeout=args.timeout
    )

if __name__ == "__main__":
    main()
