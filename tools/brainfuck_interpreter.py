#!/usr/bin/env python3
"""
Brainfuck Interpreter & Debugger - An interpreter and visual debugger for Brainfuck programs.
"""

import sys
import argparse
import time

def precompute_brackets(code):
    """Precompute matching brackets to allow fast jumps."""
    stack = []
    brackets = {}
    for pos, char in enumerate(code):
        if char == '[':
            stack.append(pos)
        elif char == ']':
            if not stack:
                raise SyntaxError(f"Mismatched bracket ']' at position {pos}")
            start = stack.pop()
            brackets[start] = pos
            brackets[pos] = start
    if stack:
        raise SyntaxError(f"Mismatched bracket '[' at position {stack[-1]}")
    return brackets

def render_tape(tape, ptr, view_range=10):
    """Generates an ASCII representation of the memory tape centered around the pointer."""
    start = max(0, ptr - view_range)
    end = min(len(tape), ptr + view_range + 1)
    
    indices = []
    values = []
    markers = []
    
    for i in range(start, end):
        indices.append(f"{i:^5}")
        values.append(f"{tape[i]:^5}")
        markers.append(f"{'^' if i == ptr else ' ':^5}")
        
    res = []
    res.append(" Tape:  " + " | ".join(indices))
    res.append(" Value: " + " | ".join(values))
    res.append("        " + "   ".join(markers))
    return "\n".join(res)

def run_brainfuck(code, tape_size=30000, debug=False, input_string="", cell_bits=8):
    # Filter code to include only valid Brainfuck instructions
    valid_chars = set('><+-.,[]')
    clean_code = [char for char in code if char in valid_chars]
    
    try:
        brackets = precompute_brackets(clean_code)
    except SyntaxError as e:
        print(f"\033[91mSyntax Error: {e}\033[0m")
        return False
        
    tape = [0] * tape_size
    ptr = 0
    code_ptr = 0
    input_ptr = 0
    cycles = 0
    max_val = (2 ** cell_bits) - 1
    
    output = []
    
    start_time = time.perf_counter()
    
    while code_ptr < len(clean_code):
        char = clean_code[code_ptr]
        cycles += 1
        
        if debug:
            print("\033[H\033[J") # Clear screen
            print(f"Step: {cycles} | Inst: '{char}' | IP: {code_ptr}/{len(clean_code)}")
            print(render_tape(tape, ptr))
            print(f"Output so far: {''.join(output)}")
            print("-" * 50)
            time.sleep(0.1)
            # Optional: Wait for user input to step
            # input("Press Enter to step...")
            
        if char == '>':
            ptr += 1
            if ptr >= tape_size:
                ptr = 0  # Wrap around memory tape
        elif char == '<':
            ptr -= 1
            if ptr < 0:
                ptr = tape_size - 1
        elif char == '+':
            tape[ptr] = (tape[ptr] + 1) & max_val
        elif char == '-':
            tape[ptr] = (tape[ptr] - 1) & max_val
        elif char == '.':
            output.append(chr(tape[ptr]))
        elif char == ',':
            if input_ptr < len(input_string):
                tape[ptr] = ord(input_string[input_ptr]) & max_val
                input_ptr += 1
            else:
                # Read from stdin if no custom inputs left
                try:
                    char_in = sys.stdin.read(1)
                    tape[ptr] = ord(char_in) & max_val if char_in else 0
                except KeyboardInterrupt:
                    print("\nAborted.")
                    return False
        elif char == '[':
            if tape[ptr] == 0:
                code_ptr = brackets[code_ptr]
        elif char == ']':
            if tape[ptr] != 0:
                code_ptr = brackets[code_ptr]
                
        code_ptr += 1
        
    duration = time.perf_counter() - start_time
    
    if not debug:
        print("".join(output))
        
    print("\n" + "=" * 40)
    print(f"Cycles Executed: {cycles}")
    print(f"Execution Time : {duration:.4f} seconds")
    print(f"End Pointer Pos: {ptr}")
    print(f"End Value at Ptr: {tape[ptr]}")
    print("=" * 40)
    return True

def main():
    parser = argparse.ArgumentParser(
        description="Brainfuck Interpreter & Debugger - Run and trace esoteric Brainfuck code."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("file", nargs="?", help="Path to Brainfuck source file")
    group.add_argument("-c", "--code", help="Raw Brainfuck code to execute")
    
    parser.add_argument("-d", "--debug", action="store_true", help="Run in step-by-step visual debug mode")
    parser.add_argument("-i", "--input", default="", help="String input buffer to feed to ',' operations")
    parser.add_argument("--tape-size", type=int, default=30000, help="Memory tape size (default: 30000)")
    parser.add_argument("--bits", type=int, default=8, choices=[8, 16, 32], help="Bits per memory cell (default: 8)")
    
    args = parser.parse_args()
    
    code = ""
    if args.code:
        code = args.code
    elif args.file:
        try:
            with open(args.file, 'r') as f:
                code = f.read()
        except FileNotFoundError:
            print(f"Error: File '{args.file}' not found.")
            sys.exit(1)
            
    run_brainfuck(code, tape_size=args.tape_size, debug=args.debug, input_string=args.input, cell_bits=args.bits)

if __name__ == "__main__":
    main()
