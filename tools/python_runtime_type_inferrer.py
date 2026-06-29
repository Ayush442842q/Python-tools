#!/usr/bin/env python3
"""
Python Runtime Type Inferrer

A utility to run a target Python script and trace function and method calls 
at runtime using sys.settrace. It inspects argument types and return types 
to construct PEP 484 type annotations and outputs them as a .pyi stub file 
or direct console printout.

Usage:
    python tools/python_runtime_type_inferrer.py target_script.py [args...]
    python tools/python_runtime_type_inferrer.py -o stubs.pyi target_script.py
"""

import argparse
import os
import sys
import runpy
from typing import Dict, Set, Tuple, Any, List

# ANSI Colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"

def supports_color() -> bool:
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform or is_a_tty

def color_text(text: str, color_code: str) -> str:
    return f"{color_code}{text}{COLOR_RESET}" if supports_color() else text

# Database to store inferred types
# Structure: { (filename, class_name, func_name): { "args": {arg_name: set(types)}, "return": set(types) } }
type_database = {}

def get_type_name(val: Any) -> str:
    """Returns a clean string representation of a type."""
    if val is None:
        return "None"
    t = type(val)
    if t.__module__ == 'builtins':
        return t.__name__
    return f"{t.__module__}.{t.__name__}"

def format_type_set(type_set: Set[str]) -> str:
    """Formats a set of type names into a Union string if multiple exist."""
    if not type_set:
        return "Any"
    types = sorted(list(type_set))
    if len(types) == 1:
        return types[0]
    if "None" in types:
        non_none = [t for t in types if t != "None"]
        if len(non_none) == 1:
            return f"Optional[{non_none[0]}]"
    return f"Union[{', '.join(types)}]"

def make_trace_func(target_dir: str, verbose: bool):
    """Creates a trace function that intercepts calls and returns."""
    target_dir = os.path.abspath(target_dir)

    def trace_calls(frame, event, arg):
        co = frame.f_code
        filename = os.path.abspath(co.co_filename)
        
        # Only trace files in target directory and ignore our own script
        if not filename.startswith(target_dir) or "python_runtime_type_inferrer.py" in filename:
            return None
            
        # Ignore stdlib or virtual environments
        if "lib/python" in filename or "site-packages" in filename or ".venv" in filename:
            return None

        func_name = co.co_name
        
        # Try to resolve class name if method
        class_name = None
        if frame.f_code.co_argcount > 0:
            first_arg_name = frame.f_code.co_varnames[0]
            if first_arg_name == 'self':
                # Attempt to get the class of self
                self_obj = frame.f_locals.get('self')
                if self_obj is not None:
                    class_name = self_obj.__class__.__name__
            elif first_arg_name == 'cls':
                cls_obj = frame.f_locals.get('cls')
                if cls_obj is not None and isinstance(cls_obj, type):
                    class_name = cls_obj.__name__

        key = (filename, class_name, func_name)

        if event == 'call':
            if key not in type_database:
                # Capture argument names
                arg_count = co.co_argcount
                arg_names = co.co_varnames[:arg_count]
                type_database[key] = {
                    "args": {name: set() for name in arg_names},
                    "return": set()
                }
            
            # Record parameter types
            db_entry = type_database[key]
            for arg_name in db_entry["args"]:
                if arg_name in frame.f_locals:
                    val = frame.f_locals[arg_name]
                    db_entry["args"][arg_name].add(get_type_name(val))
                    
            if verbose:
                arg_str = ", ".join(f"{k}: {get_type_name(v)}" for k, v in frame.f_locals.items() if k in db_entry["args"])
                print(color_text(f"[CALL] {class_name + '.' if class_name else ''}{func_name}({arg_str}) in {os.path.basename(filename)}", COLOR_CYAN))

            # Return trace_returns for return events in this frame
            return trace_returns

        return None

    def trace_returns(frame, event, arg):
        if event == 'return':
            co = frame.f_code
            filename = os.path.abspath(co.co_filename)
            func_name = co.co_name
            
            class_name = None
            if frame.f_code.co_argcount > 0:
                first_arg_name = frame.f_code.co_varnames[0]
                if first_arg_name == 'self':
                    self_obj = frame.f_locals.get('self')
                    if self_obj is not None:
                        class_name = self_obj.__class__.__name__
                elif first_arg_name == 'cls':
                    cls_obj = frame.f_locals.get('cls')
                    if cls_obj is not None and isinstance(cls_obj, type):
                        class_name = cls_obj.__name__
                        
            key = (filename, class_name, func_name)
            if key in type_database:
                ret_type = get_type_name(arg)
                type_database[key]["return"].add(ret_type)
                if verbose:
                    print(color_text(f"[RETURN] {class_name + '.' if class_name else ''}{func_name} -> {ret_type}", COLOR_GREEN))
                    
    return trace_calls

def generate_stub_content() -> str:
    """Generates the content for a .pyi stub file from the database."""
    lines = []
    lines.append("# Generated by Python Runtime Type Inferrer")
    lines.append("from typing import Any, Union, Optional, List, Dict, Tuple, Set\n")
    
    # Group by filename
    by_file = {}
    for (filename, class_name, func_name), data in type_database.items():
        by_file.setdefault(filename, []).append((class_name, func_name, data))
        
    for filename, entries in sorted(by_file.items()):
        rel_path = os.path.relpath(filename)
        lines.append(f"# File: {rel_path}")
        
        # Group by class
        classes = {}
        globals_funcs = []
        for class_name, func_name, data in entries:
            if class_name:
                classes.setdefault(class_name, []).append((func_name, data))
            else:
                globals_funcs.append((func_name, data))
                
        # Write classes
        for class_name, methods in sorted(classes.items()):
            lines.append(f"class {class_name}:")
            for func_name, data in sorted(methods):
                args_formatted = []
                for name, types in data["args"].items():
                    type_str = format_type_set(types)
                    args_formatted.append(f"{name}: {type_str}")
                ret_str = format_type_set(data["return"])
                lines.append(f"    def {func_name}({', '.join(args_formatted)}) -> {ret_str}: ...")
            lines.append("")
            
        # Write module level functions
        for func_name, data in sorted(globals_funcs):
            args_formatted = []
            for name, types in data["args"].items():
                type_str = format_type_set(types)
                args_formatted.append(f"{name}: {type_str}")
            ret_str = format_type_set(data["return"])
            lines.append(f"def {func_name}({', '.join(args_formatted)}) -> {ret_str}: ...")
        lines.append("")
        
    return "\n".join(lines)

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Trace a Python script's execution to infer function/method parameter and return types."
    )
    parser.add_argument("script", help="Target Python script to trace")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="Arguments to pass to the target script")
    parser.add_argument("-o", "--output", help="Save the generated .pyi stub output to this file")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print call and return traces in real-time")
    
    # Parse only our options, leave rest for target script
    # We do this by custom splitting or standard parse_known_args
    args, target_args = parser.parse_known_args()
    
    if not args.script:
        parser.print_help()
        return 1
        
    script_path = os.path.abspath(args.script)
    if not os.path.exists(script_path):
        print(color_text(f"Error: Script file '{args.script}' not found.", COLOR_RED), file=sys.stderr)
        return 1

    # Prep sys.argv for the target script
    sys.argv = [script_path] + target_args
    sys.path.insert(0, os.path.dirname(script_path))

    print(color_text(f"[*] Starting execution tracer on {os.path.basename(script_path)}...", COLOR_BOLD))
    print(color_text("[*] Tracing modules in the script directory. Please wait...", COLOR_YELLOW))
    
    # Establish trace function
    target_dir = os.path.dirname(script_path)
    trace_func = make_trace_func(target_dir, args.verbose)
    
    sys.settrace(trace_func)
    
    try:
        # Run target script
        runpy.run_path(script_path, run_name="__main__")
    except SystemExit as e:
        # Handle sys.exit calls gracefully
        exit_code = e.code if isinstance(e.code, int) else 0
        print(color_text(f"\n[*] Target script exited with code {exit_code}.", COLOR_YELLOW))
    except Exception as e:
        print(color_text(f"\n[!] Target script crashed with exception: {e}", COLOR_RED), file=sys.stderr)
        import traceback
        traceback.print_exc()
    finally:
        # Ensure trace is cleared
        sys.settrace(None)
        
    # Generate stubs
    if not type_database:
        print(color_text("\n[!] No user function executions were traced. Check target directory or imports.", COLOR_RED))
        return 1
        
    stub_content = generate_stub_content()
    
    print("\n" + color_text("=== Inferred Type Signatures ===", COLOR_BOLD))
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(stub_content)
            print(color_text(f"[+] Successfully wrote stubs to {args.output}", COLOR_GREEN))
        except Exception as e:
            print(color_text(f"[-] Error writing stub file: {e}", COLOR_RED), file=sys.stderr)
    else:
        print(stub_content)
        print(color_text("[*] Tip: Use '-o <filename>.pyi' to save these signatures to a stub file.", COLOR_CYAN))
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
