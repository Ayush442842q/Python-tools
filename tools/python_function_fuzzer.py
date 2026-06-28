#!/usr/bin/env python3
"""
Python Function Property-Based Fuzzer
A standalone fuzzer for Python functions. Automatically inspects the signature and type hints
of a target function in a given script, generates random and edge-case inputs, executes the
function repeatedly, and reports inputs that trigger unhandled exceptions (crashes).
"""

import os
import sys
import random
import string
import inspect
import importlib.util
import traceback
import argparse

# Input Generators
def generate_int():
    """Generate random and edge-case integers."""
    edge_cases = [0, 1, -1, 2**31 - 1, -2**31, 2**63 - 1, -2**63, 999999]
    if random.random() < 0.3:
        return random.choice(edge_cases)
    return random.randint(-10000, 10000)

def generate_float():
    """Generate random and edge-case floats."""
    edge_cases = [0.0, -0.0, 1.0, -1.0, float('inf'), float('-inf'), float('nan'), 1e-30, 1e30]
    if random.random() < 0.3:
        return random.choice(edge_cases)
    return random.uniform(-1000.0, 1000.0)

def generate_bool():
    """Generate random boolean."""
    return random.choice([True, False])

def generate_string():
    """Generate random and edge-case strings."""
    edge_cases = [
        "",                 # Empty string
        " ",                # Whitespace
        "A" * 1000,         # Long string
        "\\x00\\n\\r\\t",   # Escape sequences
        "üöäéèà",           # Non-ASCII Unicode
        "💩🔥💻",          # Emoji / high code points
        "'; DROP TABLE users; --",  # SQL injection attempt
        "<script>alert(1)</script>", # XSS attempt
        "12345"             # Digit string
    ]
    if random.random() < 0.3:
        return random.choice(edge_cases)
    
    length = random.randint(1, 50)
    chars = string.ascii_letters + string.digits + string.punctuation + " "
    return "".join(random.choice(chars) for _ in range(length))

def generate_list(item_generator, depth=0):
    """Generate random list containing items from a generator function."""
    if depth > 2:
        return []
    length = random.randint(0, 10)
    return [item_generator() for _ in range(length)]

def generate_dict(key_gen, val_gen, depth=0):
    """Generate random dictionary."""
    if depth > 2:
        return {}
    length = random.randint(0, 5)
    return {key_gen(): val_gen() for _ in range(length)}

def generate_any(depth=0):
    """Fallback generator that yields any random primitive or compound type."""
    choice = random.choice(["int", "float", "bool", "string", "list", "dict", "none"])
    if choice == "int":
        return generate_int()
    elif choice == "float":
        return generate_float()
    elif choice == "bool":
        return generate_bool()
    elif choice == "string":
        return generate_string()
    elif choice == "list":
        # Recursively generate a list of random things
        return generate_list(lambda: generate_any(depth + 1), depth)
    elif choice == "dict":
        return generate_dict(generate_string, lambda: generate_any(depth + 1), depth)
    else:
        return None

def get_generator_for_type(type_annotation):
    """Map python class/type annotation to a random generator."""
    if type_annotation == int:
        return generate_int
    elif type_annotation == float:
        return generate_float
    elif type_annotation == bool:
        return generate_bool
    elif type_annotation == str:
        return generate_string
    elif type_annotation == list or str(type_annotation).startswith("typing.List"):
        # Default list generator using any types
        return lambda: generate_list(generate_any)
    elif type_annotation == dict or str(type_annotation).startswith("typing.Dict"):
        return lambda: generate_dict(generate_string, generate_any)
    else:
        # Fallback to any random generator
        return generate_any

def import_function_from_file(file_path, func_name):
    """Dynamically import a module and extract the target function."""
    module_name = os.path.splitext(os.path.basename(file_path))[0]
    
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load spec for {file_path}")
        
    module = importlib.util.module_from_spec(spec)
    # Add module's parent directory to path so internal relative imports work
    sys.path.insert(0, os.path.dirname(os.path.abspath(file_path)))
    
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
        
    func = getattr(module, func_name, None)
    if func is None:
        raise AttributeError(f"Module '{module_name}' has no attribute '{func_name}'")
    if not callable(func):
        raise TypeError(f"'{func_name}' in '{module_name}' is not callable")
        
    return func

def main():
    parser = argparse.ArgumentParser(
        description="Python Function Fuzzer - Run property-based testing on a Python function to find crashes",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("file", help="Path to the Python file containing the target function")
    parser.add_argument("function", help="Name of the function to fuzz")
    parser.add_argument("-n", "--iterations", type=int, default=100,
                        help="Number of fuzzing test runs (default: 100)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Show every function invocation details")

    args = parser.parse_args()

    if not os.path.exists(args.file):
        print(f"Error: File '{args.file}' does not exist.", file=sys.stderr)
        sys.exit(1)

    # 1. Load function
    try:
        func = import_function_from_file(args.file, args.function)
    except Exception as e:
        print(f"Error importing function: {e}", file=sys.stderr)
        sys.exit(1)

    # 2. Inspect signature
    sig = inspect.signature(func)
    print(f"[*] Function loaded: {args.function}{sig}")
    print(f"[*] Starting fuzzing with {args.iterations} iterations...")
    print("-" * 60)

    # Setup generators for parameters
    params = sig.parameters
    param_generators = {}
    
    for name, param in params.items():
        # Handle *args or **kwargs parameter scopes
        if param.kind in (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD):
            continue
            
        annotation = param.annotation
        # If no type hint, print a warning and fallback to Any
        if annotation == inspect.Parameter.empty:
            print(f"[*] Warning: Parameter '{name}' is missing type hints. Using random fallback generator.", file=sys.stderr)
            param_generators[name] = generate_any
        else:
            param_generators[name] = get_generator_for_type(annotation)

    crashes = []
    runs = 0
    
    for i in range(args.iterations):
        # Generate inputs
        inputs = {}
        for name, gen in param_generators.items():
            inputs[name] = gen()
            
        # Log invocation if verbose
        if args.verbose:
            inputs_str = ", ".join(f"{k}={repr(v)}" for k, v in inputs.items())
            print(f"Run #{i+1:3d}: calling {args.function}({inputs_str})")
            
        runs += 1
        
        # Execute function
        try:
            func(**inputs)
        except Exception as e:
            # Caught a crash!
            tb = traceback.format_exc()
            crashes.append({
                "run": i + 1,
                "inputs": inputs,
                "exception": e,
                "traceback": tb
            })
            
            # Print a quick crash indicator in non-verbose mode
            if not args.verbose:
                sys.stdout.write("F")
                sys.stdout.flush()
        else:
            if not args.verbose:
                sys.stdout.write(".")
                sys.stdout.flush()

    if not args.verbose:
        print() # Newline after progress dots

    print("-" * 60)
    print(f"Fuzzing complete: {runs} runs executed.")
    print(f"Detected Crashes: {len(crashes)}")
    print("=" * 60)

    if crashes:
        print("CRASH LOGS SUMMARY:")
        print("-" * 60)
        # Group identical crashes by exception type + last line of traceback
        unique_crashes = {}
        for crash in crashes:
            ex_type = type(crash["exception"]).__name__
            tb_lines = crash["traceback"].strip().splitlines()
            last_tb_line = tb_lines[-1] if tb_lines else ""
            key = (ex_type, last_tb_line)
            
            if key not in unique_crashes:
                unique_crashes[key] = []
            unique_crashes[key].append(crash)

        for (ex_type, last_tb_line), items in unique_crashes.items():
            first_item = items[0]
            print(f"Exception Type: {ex_type}")
            print(f"Crash Message:  {first_item['exception']}")
            print(f"Failed Inputs:  {first_item['inputs']}")
            print(f"Occurrences:    {len(items)} times")
            print("Traceback:")
            # Indent traceback
            for line in first_item["traceback"].splitlines():
                print(f"  {line}")
            print("-" * 60)
        sys.exit(1)
    else:
        print("Success: No crashes detected. The function proved robust to all fuzzed inputs!")
        sys.exit(0)

if __name__ == "__main__":
    main()
