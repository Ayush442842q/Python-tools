#!/usr/bin/env python3
"""
Python Function Call Tracer

A tool to run a target Python script and trace the execution flow of functions 
and methods at runtime. It displays a hierarchical, tree-structured log of 
function entries, arguments, return values, exceptions, and durations (in milliseconds).

Usage:
    python tools/python_function_call_tracer.py target_script.py [args...]
    python tools/python_function_call_tracer.py -d 3 target_script.py (limit depth)
"""

import argparse
import os
import sys
import runpy
import time
from typing import List, Dict, Tuple, Any

# ANSI Colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_GRAY = "\033[90m"

def supports_color() -> bool:
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform or is_a_tty

def color_text(text: str, color_code: str) -> str:
    return f"{color_code}{text}{COLOR_RESET}" if supports_color() else text

class CallTracker:
    def __init__(self, target_dir: str, max_depth: int = None, show_args: bool = True, show_return: bool = True):
        self.target_dir = os.path.abspath(target_dir)
        self.max_depth = max_depth
        self.show_args = show_args
        self.show_return = show_return
        
        # State tracking
        self.stack: List[Tuple[str, float]] = []  # Elements: (func_key, start_time)
        self.depth = 0
        self.last_was_call = False

    def get_indent(self, is_last: bool = False) -> str:
        """Returns the tree branch box drawing indentation."""
        if self.depth <= 0:
            return ""
        
        # We build indentation using tree guides
        parts = []
        for i in range(self.depth - 1):
            parts.append("│  ")
        if is_last:
            parts.append("└─ ")
        else:
            parts.append("├─ ")
        return "".join(parts)

    def format_args(self, f_locals: dict, co_varnames: tuple, co_argcount: int) -> str:
        """Formats the argument names and values beautifully."""
        if not self.show_args:
            return ""
        arg_names = co_varnames[:co_argcount]
        parts = []
        for name in arg_names:
            if name in f_locals:
                val = f_locals[name]
                # Truncate representation if too long
                val_repr = repr(val)
                if len(val_repr) > 40:
                    val_repr = val_repr[:37] + "..."
                parts.append(f"{name}={val_repr}")
        return f"({', '.join(parts)})"

    def format_return_val(self, val: Any) -> str:
        """Formats return value."""
        val_repr = repr(val)
        if len(val_repr) > 60:
            val_repr = val_repr[:57] + "..."
        return val_repr

    def trace_calls(self, frame, event, arg):
        co = frame.f_code
        filename = os.path.abspath(co.co_filename)
        
        # Only trace files in target directory and ignore our own script
        if not filename.startswith(self.target_dir) or "python_function_call_tracer.py" in filename:
            return None
            
        # Ignore stdlib or virtual environments
        if "lib/python" in filename or "site-packages" in filename or ".venv" in filename:
            return None

        func_name = co.co_name
        class_name = None
        
        # Try to resolve class name if method
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

        func_display = f"{class_name + '.' if class_name else ''}{func_name}"

        if event == 'call':
            if self.max_depth is not None and self.depth >= self.max_depth:
                return None
                
            indent = self.get_indent(is_last=False)
            arg_str = self.format_args(frame.f_locals, co.co_varnames, co.co_argcount)
            
            # Print the call entry
            print(f"{color_text(indent, COLOR_GRAY)}{color_text(func_display, COLOR_CYAN)}{arg_str}")
            
            self.depth += 1
            self.stack.append((func_display, time.perf_counter()))
            self.last_was_call = True
            
            return self.trace_returns

        return None

    def trace_returns(self, frame, event, arg):
        if event == 'return':
            self.depth = max(0, self.depth - 1)
            start_time = time.perf_counter()
            func_display = "unknown"
            
            if self.stack:
                func_display, start_time = self.stack.pop()
                
            duration = (time.perf_counter() - start_time) * 1000.0  # in ms
            
            if self.show_return:
                indent = self.get_indent(is_last=True)
                ret_val = self.format_return_val(arg)
                duration_str = f"{duration:.2f}ms"
                
                print(f"{color_text(indent, COLOR_GRAY)}← {color_text(func_display, COLOR_GREEN)} returned {color_text(ret_val, COLOR_YELLOW)} {color_text('[' + duration_str + ']', COLOR_GRAY)}")
            
            self.last_was_call = False
        elif event == 'exception':
            self.depth = max(0, self.depth - 1)
            func_display = "unknown"
            if self.stack:
                func_display, _ = self.stack.pop()
            exc_type, exc_value, _ = arg
            indent = self.get_indent(is_last=True)
            print(f"{color_text(indent, COLOR_GRAY)}💥 {color_text(func_display, COLOR_RED)} raised {exc_type.__name__}: {exc_value}")
            self.last_was_call = False

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Trace a Python script's execution to print an interactive function call flow chart."
    )
    parser.add_argument("script", help="Target Python script to trace")
    parser.add_argument("args", nargs=argparse.REMAINDER, help="Arguments to pass to the target script")
    parser.add_argument("-d", "--depth", type=int, help="Maximum stack depth to print")
    parser.add_argument("--no-args", action="store_true", help="Do not show function arguments")
    parser.add_argument("--no-returns", action="store_true", help="Do not show return events and values")
    
    args, target_args = parser.parse_known_args()
    
    if not args.script:
        parser.print_help()
        return 1
        
    script_path = os.path.abspath(args.script)
    if not os.path.exists(script_path):
        print(color_text(f"Error: Script file '{args.script}' not found.", COLOR_RED), file=sys.stderr)
        return 1

    sys.argv = [script_path] + target_args
    sys.path.insert(0, os.path.dirname(script_path))

    print(color_text(f"[*] Tracing execution of {os.path.basename(script_path)}", COLOR_BOLD))
    print(color_text("[*] Target folder: " + os.path.dirname(script_path), COLOR_GRAY))
    print(color_text("--------------------------------------------------\n", COLOR_GRAY))
    
    tracker = CallTracker(
        target_dir=os.path.dirname(script_path),
        max_depth=args.depth,
        show_args=not args.no_args,
        show_return=not args.no_returns
    )
    
    # Run target script with trace function
    sys.settrace(tracker.trace_calls)
    
    try:
        runpy.run_path(script_path, run_name="__main__")
    except SystemExit as e:
        exit_code = e.code if isinstance(e.code, int) else 0
        print(color_text(f"\n[*] Target script exited with code {exit_code}.", COLOR_YELLOW))
    except Exception as e:
        print(color_text(f"\n[!] Target script crashed with exception: {e}", COLOR_RED), file=sys.stderr)
        import traceback
        traceback.print_exc()
    finally:
        sys.settrace(None)
        
    print(color_text("\n--------------------------------------------------", COLOR_GRAY))
    print(color_text("[*] Tracing complete.", COLOR_BOLD))
    return 0

if __name__ == "__main__":
    sys.exit(main())
