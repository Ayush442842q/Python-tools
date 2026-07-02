#!/usr/bin/env python3
"""
Python Bytecode Disassembler & Compiler Explorer
A utility to compile Python source code into bytecode and disassemble it,
providing a side-by-side visual mapping of source code to VM instructions.
"""

import sys
import os
import argparse
import dis
import inspect
from typing import List, Dict, Any, Tuple

# Color utilities for terminal formatting
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"
MAGENTA = "\033[35m"

def print_colored(text: str, color: str, end: str = "\n"):
    if sys.stdout.isatty():
        print(f"{color}{text}{RESET}", end=end)
    else:
        print(text, end=end)

def format_instruction(instr: dis.Instruction) -> str:
    """Format a single dis.Instruction object into a detailed string."""
    line_str = f"{instr.starts_line:4d}" if instr.starts_line is not None else "    "
    is_jump = ">>" if instr.is_jump_target else "  "
    oparg_str = f"{instr.oparg:3d}" if instr.oparg is not None else "   "
    argval_str = f"({instr.argrepr})" if instr.argrepr else ""
    
    return f"{line_str} | {is_jump} {instr.offset:5d} {instr.opname:<22} {oparg_str} {argval_str}"

def disassemble_code_object(code_obj: Any, name: str = "root") -> List[Tuple[str, Any]]:
    """Recursively disassemble a code object and return all instructions and nested code objects."""
    results = []
    
    # Header for the current code object
    header = f"{BOLD}{CYAN}Disassembly of '{name}'{RESET} (filename: {code_obj.co_filename}, first line: {code_obj.co_firstlineno})"
    instr_lines = []
    
    try:
        # Use dis.Bytecode to get details
        bc = dis.Bytecode(code_obj)
        for instr in bc:
            # Colorize key VM instructions
            op_color = RESET
            if "LOAD" in instr.opname:
                op_color = GREEN
            elif "STORE" in instr.opname:
                op_color = YELLOW
            elif "JUMP" in instr.opname or "COMPARE" in instr.opname:
                op_color = MAGENTA
            elif "CALL" in instr.opname:
                op_color = CYAN
            
            line_str = f"{instr.starts_line:4d}" if instr.starts_line is not None else "    "
            is_jump = ">>" if instr.is_jump_target else "  "
            oparg_str = f"{instr.oparg:3d}" if instr.oparg is not None else "   "
            argval_str = f"({instr.argrepr})" if instr.argrepr else ""
            
            formatted = f"{line_str} | {is_jump} {instr.offset:5d} {op_color}{instr.opname:<22}{RESET} {oparg_str} {argval_str}"
            instr_lines.append(formatted)
            
            # If the instruction's argument is a code object (e.g. for functions or classes), keep track of it
            if isinstance(instr.argval, type(code_obj)):
                results.append((instr.argval.co_name, instr.argval))
    except Exception as e:
        instr_lines.append(f"{RED}Error disassembling: {e}{RESET}")
        
    final_output = [header, "Line | Jmp Offset Opcode                 Oparg Argrepr", "-" * 60] + instr_lines + [""]
    
    # Run through child items first to output parent then children
    all_disassembled = [(name, "\n".join(final_output))]
    for child_name, child_obj in results:
        all_disassembled.extend(disassemble_code_object(child_obj, child_name))
        
    return all_disassembled

def source_mapped_disassembly(source_code: str) -> None:
    """Disassembles the source code and prints it side-by-side with original source lines."""
    try:
        code_obj = compile(source_code, "<string>", "exec")
    except Exception as e:
        print_colored(f"Compilation Error: {e}", RED)
        return
        
    source_lines = source_code.splitlines()
    instructions = list(dis.get_instructions(code_obj))
    
    # Group instructions by their starting line number
    instr_by_line: Dict[int, List[dis.Instruction]] = {}
    for instr in instructions:
        if instr.starts_line is not None:
            curr_line = instr.starts_line
        if 'curr_line' in locals():
            instr_by_line.setdefault(curr_line, []).append(instr)
            
    print_colored(f"{BOLD}{CYAN}Source Code Mapped to Bytecode:{RESET}", CYAN)
    print("-" * 100)
    
    for idx, line in enumerate(source_lines, 1):
        # Print the source line
        print_colored(f"{idx:3d}: {line:<50}", BOLD)
        
        # Print the corresponding bytecode instructions
        if idx in instr_by_line:
            for instr in instr_by_line[idx]:
                op_color = GREEN if "LOAD" in instr.opname else (YELLOW if "STORE" in instr.opname else RESET)
                is_jump = ">>" if instr.is_jump_target else "  "
                argval_str = f"({instr.argrepr})" if instr.argrepr else ""
                print(f"      {is_jump} {instr.offset:5d} {op_color}{instr.opname:<20}{RESET} {instr.oparg or '':<3} {argval_str}")
        print()

def compare_snippets(code1: str, code2: str) -> None:
    """Compare the bytecode instructions of two snippets side-by-side."""
    try:
        co1 = compile(code1, "<snippet 1>", "exec")
        co2 = compile(code2, "<snippet 2>", "exec")
    except Exception as e:
        print_colored(f"Error compiling code snippet: {e}", RED)
        return
        
    insts1 = [f"{i.opname} ({i.argrepr})" if i.argrepr else i.opname for i in dis.get_instructions(co1)]
    insts2 = [f"{i.opname} ({i.argrepr})" if i.argrepr else i.opname for i in dis.get_instructions(co2)]
    
    print_colored(f"{BOLD}{CYAN}Bytecode Comparison:{RESET}", CYAN)
    print(f"{'Snippet 1 (Size: ' + str(len(insts1)) + ' instr)':<48} | {'Snippet 2 (Size: ' + str(len(insts2)) + ' instr)':<48}")
    print("-" * 100)
    
    max_len = max(len(insts1), len(insts2))
    for i in range(max_len):
        part1 = insts1[i] if i < len(insts1) else ""
        part2 = insts2[i] if i < len(insts2) else ""
        
        # Highlight differences
        if part1 == part2:
            print(f"{part1:<48} | {part2:<48}")
        else:
            print_colored(f"{part1:<48} | {part2:<48}", YELLOW)

def main():
    parser = argparse.ArgumentParser(
        description="Python Bytecode Disassembler & Compiler Explorer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python python_bytecode_disassembler.py -c "x = [i*2 for i in range(10)]"
  python python_bytecode_disassembler.py -f my_script.py
  python python_bytecode_disassembler.py --map -c "def add(a, b): return a + b"
  python python_bytecode_disassembler.py --compare -c1 "a + b" -c2 "a.__add__(b)"
        """
    )
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-c", "--code", type=str, help="Inline Python code string to disassemble")
    group.add_argument("-f", "--file", type=str, help="Python source file path to disassemble")
    
    parser.add_argument("-m", "--map", action="store_true", help="Show source code lines mapped directly to their bytecode instructions")
    parser.add_argument("--compare", action="store_true", help="Compare two snippets side-by-side (requires -c1 and -c2)")
    parser.add_argument("-c1", type=str, help="First code snippet for comparison")
    parser.add_argument("-c2", type=str, help="Second code snippet for comparison")
    
    args = parser.parse_args()
    
    if args.compare:
        if not args.c1 or not args.c2:
            parser.error("--compare requires both -c1 and -c2 code snippets")
        compare_snippets(args.c1, args.c2)
        return
        
    source_code = ""
    if args.code:
        source_code = args.code
    elif args.file:
        if not os.path.exists(args.file):
            print_colored(f"Error: File '{args.file}' not found.", RED)
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8") as f:
            source_code = f.read()
    else:
        # Interactive mode or read from stdin
        if not sys.stdin.isatty():
            source_code = sys.stdin.read()
        else:
            print_colored("Python Bytecode Disassembler REPL (type 'exit' or Ctrl-D to compile & run):", BOLD)
            lines = []
            while True:
                try:
                    line = input(">>> ")
                    if line.strip() == "exit":
                        break
                    lines.append(line)
                except (EOFError, KeyboardInterrupt):
                    break
            source_code = "\n".join(lines)
            
    if not source_code.strip():
        print_colored("No source code provided.", YELLOW)
        return
        
    if args.map:
        source_mapped_disassembly(source_code)
    else:
        try:
            code_obj = compile(source_code, "<string>", "exec")
            all_dis = disassemble_code_object(code_obj)
            for name, out in all_dis:
                print(out)
        except Exception as e:
            print_colored(f"Compilation Error: {e}", RED)
            sys.exit(1)

if __name__ == "__main__":
    main()
