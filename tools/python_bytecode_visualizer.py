#!/usr/bin/env python3
"""
Python Bytecode Visualizer
An interactive developer utility that compiles a Python script or code snippet
and disassembles it using the 'dis' module.
Displays the output in a clean, color-coded terminal table with human-readable explanations of each opcode.
"""

import argparse
import dis
import sys
import types

# A dictionary mapping Python bytecode opcodes to human-friendly explanations
OPCODE_EXPLANATIONS = {
    'LOAD_CONST': "Loads a constant value onto the evaluation stack.",
    'LOAD_FAST': "Loads a local variable value onto the evaluation stack.",
    'STORE_FAST': "Pops the top-of-stack (TOS) and stores it in a local variable.",
    'LOAD_GLOBAL': "Loads a global or built-in name onto the evaluation stack.",
    'STORE_GLOBAL': "Pops the TOS and stores it in a global variable.",
    'LOAD_NAME': "Loads a name (local, global, or built-in) onto the evaluation stack.",
    'STORE_NAME': "Pops the TOS and stores it in a local/global name scope.",
    'LOAD_ATTR': "Replaces TOS with attribute lookup: getattr(TOS, name).",
    'STORE_ATTR': "Implements setattr(TOS1, name, TOS). Pops both.",
    'CALL_FUNCTION': "Calls a function. Pops arguments and the function itself, pushes result.",
    'CALL_METHOD': "Calls a method on an object. Pops arguments, descriptor, object; pushes result.",
    'LOAD_METHOD': "Loads method named co_names[namei] from TOS object.",
    'BINARY_ADD': "Adds the top two stack values: TOS = TOS1 + TOS.",
    'BINARY_SUBTRACT': "Subtracts the top two stack values: TOS = TOS1 - TOS.",
    'BINARY_MULTIPLY': "Multiplies the top two stack values: TOS = TOS1 * TOS.",
    'BINARY_TRUE_DIVIDE': "Divides the top two stack values: TOS = TOS1 / TOS.",
    'BINARY_FLOOR_DIVIDE': "Floor-divides the top two stack values: TOS = TOS1 // TOS.",
    'BINARY_POWER': "Performs exponentiation: TOS = TOS1 ** TOS.",
    'BINARY_MODULO': "Performs modulo arithmetic: TOS = TOS1 % TOS.",
    'COMPARE_OP': "Performs a comparison (e.g., <, >, ==). Pops two, pushes boolean.",
    'IS_OP': "Performs identity comparison (is / is not). Pops two, pushes boolean.",
    'CONTAINS_OP': "Performs membership comparison (in / not in). Pops two, pushes boolean.",
    'POP_JUMP_IF_FALSE': "Jumps to target offset if TOS is false, popping it.",
    'POP_JUMP_IF_TRUE': "Jumps to target offset if TOS is true, popping it.",
    'JUMP_FORWARD': "Increments byte code counter by the instruction argument.",
    'JUMP_ABSOLUTE': "Sets byte code counter to target offset absolute index.",
    'GET_ITER': "Replaces TOS with iter(TOS) to initiate an iterator.",
    'FOR_ITER': "Pops next item from iterator TOS. If done, jumps to target.",
    'RETURN_VALUE': "Pops TOS and returns it as the function's return value.",
    'POP_TOP': "Pops the top-of-stack element and discards it.",
    'DUP_TOP': "Duplicates the reference on top of the stack.",
    'NOP': "Do nothing. Used as a placeholder in optimizations.",
    'BUILD_LIST': "Creates a list from the top N stack elements.",
    'BUILD_TUPLE': "Creates a tuple from the top N stack elements.",
    'BUILD_MAP': "Creates a dictionary from key-value pairs on the stack.",
    'MAKE_FUNCTION': "Creates a function object from code and defaults on the stack.",
    'RESUME': "No-op in 3.11+. Internal command for generators/coroutines.",
    'PUSH_NULL': "Pushes a NULL onto the stack for method resolution (3.11+)."
}

# ANSI Colors
COLOR_CYAN = "\033[96m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_MAGENTA = "\033[95m"
COLOR_RED = "\033[91m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"


def print_title(title):
    print(f"\n{COLOR_BOLD}{COLOR_CYAN}=== {title} ==={COLOR_RESET}")


def get_opcode_explanation(opname):
    """Returns a short description of what the opcode does."""
    # Handle minor Python version differences by cleaning suffix or checking start
    clean_opname = opname.split('+')[0]
    if clean_opname in OPCODE_EXPLANATIONS:
        return OPCODE_EXPLANATIONS[clean_opname]
    
    # Generic prefix matching
    for key, desc in OPCODE_EXPLANATIONS.items():
        if clean_opname.startswith(key):
            return desc
            
    return "Instruction details vary or are python version-specific."


def visualize_code_object(code_obj, name="<module>"):
    """Recursively visualizes a code object and any nested function/class code objects."""
    print_title(f"Disassembly of: {name}")
    
    # Define table format
    header_fmt = "  {:<6} | {:<8} | {:<22} | {:<12} | {:<22} | {}"
    row_fmt = "  {:<6} | {:<8} | {:<22} | {:<12} | {:<22} | {}"
    
    separator = "  " + "-" * 6 + "-+-" + "-" * 8 + "-+-" + "-" * 22 + "-+-" + "-" * 12 + "-+-" + "-" * 22 + "-+-" + "-" * 35
    
    print(separator)
    print(COLOR_BOLD + header_fmt.format("Line", "Offset", "Opcode", "Arg (Raw)", "Arg Value (Resolved)", "Description") + COLOR_RESET)
    print(separator)
    
    # Track nested code objects to disassemble afterwards
    nested_code_objects = []
    
    # Iterate instructions
    for instr in dis.get_instructions(code_obj):
        line = str(instr.starts_line) if instr.starts_line is not None else ""
        offset = str(instr.offset)
        opname = instr.opname
        arg = str(instr.arg) if instr.arg is not None else ""
        argval = str(instr.argval) if instr.argval is not None else ""
        
        # Colorize important opcodes
        colored_opname = opname
        if "JUMP" in opname:
            colored_opname = COLOR_YELLOW + opname + COLOR_RESET
        elif "LOAD" in opname:
            colored_opname = COLOR_GREEN + opname + COLOR_RESET
        elif "STORE" in opname:
            colored_opname = COLOR_MAGENTA + opname + COLOR_RESET
        elif "RETURN" in opname:
            colored_opname = COLOR_RED + opname + COLOR_RESET
            
        desc = get_opcode_explanation(opname)
        
        print(row_fmt.format(line, offset, colored_opname, arg, argval, desc))
        
        # If the argument is a code object (nested function/generator/lambda), track it
        if isinstance(instr.argval, types.CodeType):
            nested_code_objects.append((instr.argval, instr.argval.co_name))
            
    print(separator + "\n")
    
    # Recurse into nested functions/classes
    for nested_obj, nested_name in nested_code_objects:
        visualize_code_object(nested_obj, nested_name)


def main():
    parser = argparse.ArgumentParser(description="Python Bytecode Visualizer")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-f", "--file", type=str, help="Python source file to disassemble")
    group.add_argument("-c", "--code", type=str, help="Inline Python code string to disassemble")
    
    args = parser.parse_args()
    
    source_code = ""
    source_name = ""
    
    if args.file:
        try:
            with open(args.file, "r", encoding="utf-8") as f:
                source_code = f.read()
            source_name = args.file
        except Exception as e:
            print(f"Error reading file '{args.file}': {e}", file=sys.stderr)
            sys.exit(1)
    else:
        source_code = args.code
        source_name = "<inline_string>"
        
    try:
        # Compile source to a code object
        code_obj = compile(source_code, source_name, "exec")
    except SyntaxError as e:
        print(f"Syntax Error in source code:\n{e.text}\n{' ' * (e.offset or 0)}^", file=sys.stderr)
        print(f"Error: {e.msg}", file=sys.stderr)
        sys.exit(1)
        
    visualize_code_object(code_obj, source_name)


if __name__ == "__main__":
    main()
