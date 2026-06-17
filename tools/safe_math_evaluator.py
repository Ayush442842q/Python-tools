#!/usr/bin/env python3
"""
safe_math_evaluator - Safely evaluate mathematical expressions

An AST-based mathematical expression evaluator. Unlike standard evaluation, this script
exclusively permits safe mathematical tokens, protecting against code execution.
It supports variables, basic operators, and a variety of standard math functions.

Usage:
    python tools/safe_math_evaluator.py [expression] [options]

Options:
    -h, --help            Show this help message and exit
    -e EXPR, --expr EXPR  Expression to evaluate
    -v VARS, --vars VARS  Define variables as key-value pairs (e.g. x=5,y=10)
    -i, --interactive     Launch an interactive math shell/REPL

Supported Operators:
    +, -, *, /, //, %, ** (power)

Supported Math Constants/Functions:
    pi, e, sin, cos, tan, asin, acos, atan, sinh, cosh, tanh,
    sqrt, log, log10, exp, pow, abs, ceil, floor, radians, degrees

Examples:
    python tools/safe_math_evaluator.py "2 * (3 + 4) ** 2"
    python tools/safe_math_evaluator.py "sin(pi / 2) + sqrt(x)" --vars "x=16"
    python tools/safe_math_evaluator.py --interactive
"""

import argparse
import ast
import math
import operator
import sys

# Whitelist of safe binary operations
SAFE_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}

# Whitelist of safe unary operations
SAFE_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}

# Whitelist of math functions and constants
SAFE_FUNCTIONS = {
    # Functions
    'sin': math.sin,
    'cos': math.cos,
    'tan': math.tan,
    'asin': math.asin,
    'acos': math.acos,
    'atan': math.atan,
    'sinh': math.sinh,
    'cosh': math.cosh,
    'tanh': math.tanh,
    'sqrt': math.sqrt,
    'log': math.log,
    'log10': math.log10,
    'exp': math.exp,
    'pow': pow,
    'abs': abs,
    'ceil': math.ceil,
    'floor': math.floor,
    'radians': math.radians,
    'degrees': math.degrees,
}

SAFE_CONSTANTS = {
    'pi': math.pi,
    'e': math.e,
}

class SafeEvalVisitor(ast.NodeVisitor):
    """AST Node Visitor that safely evaluates math expressions."""
    
    def __init__(self, variables=None):
        self.variables = variables or {}

    def visit(self, node):
        """Override to return evaluation rather than just traverse."""
        if isinstance(node, ast.Expression):
            return self.visit(node.body)
        
        # Numbers/Constants (Python 3.8+)
        elif isinstance(node, ast.Constant):
            if isinstance(node.value, (int, float, complex)):
                return node.value
            raise TypeError(f"Unsupported constant type: {type(node.value).__name__}")
        
        # Numbers (Python < 3.8)
        elif type(node).__name__ == 'Num':
            return node.n
        
        # Binary Operations (+, -, *, /, etc.)
        elif isinstance(node, ast.BinOp):
            left = self.visit(node.left)
            right = self.visit(node.right)
            op_type = type(node.op)
            if op_type in SAFE_BIN_OPS:
                # Prevent overflow / DivisionByZero / negative exponents check
                if op_type == ast.Pow and left > 10000 and right > 1000:
                    raise ValueError("Overflow: Exponentiation parameters too large")
                try:
                    return SAFE_BIN_OPS[op_type](left, right)
                except ZeroDivisionError:
                    raise ZeroDivisionError("Math Error: Division by zero")
            raise TypeError(f"Unsupported binary operator: {op_type.__name__}")
            
        # Unary Operations (-x, +x)
        elif isinstance(node, ast.UnaryOp):
            operand = self.visit(node.operand)
            op_type = type(node.op)
            if op_type in SAFE_UNARY_OPS:
                return SAFE_UNARY_OPS[op_type](operand)
            raise TypeError(f"Unsupported unary operator: {op_type.__name__}")
            
        # Variables or Constants
        elif isinstance(node, ast.Name):
            name = node.id
            if name in self.variables:
                return self.variables[name]
            if name in SAFE_CONSTANTS:
                return SAFE_CONSTANTS[name]
            raise NameError(f"Undefined variable or constant: '{name}'")
            
        # Math Function Calls (e.g. sin(x))
        elif isinstance(node, ast.Call):
            if not isinstance(node.func, ast.Name):
                raise TypeError("Function calls must be direct named calls")
            func_name = node.func.id
            if func_name in SAFE_FUNCTIONS:
                args = [self.visit(arg) for arg in node.args]
                try:
                    return SAFE_FUNCTIONS[func_name](*args)
                except ValueError as e:
                    raise ValueError(f"Math Error in {func_name}(): {e}")
            raise NameError(f"Unsupported function call: '{func_name}'")
            
        # Any other AST type is strictly rejected
        raise TypeError(f"Security Alert: Unpermitted expression element: {type(node).__name__}")

def safe_evaluate(expr_str, variables=None):
    """Parse and evaluate the math expression string safely."""
    try:
        # ast.parse with mode='eval' parses a single expression
        tree = ast.parse(expr_str.strip(), mode='eval')
        visitor = SafeEvalVisitor(variables)
        return visitor.visit(tree), None
    except SyntaxError as se:
        return None, f"Syntax Error: {se.msg} (at char {se.offset})"
    except Exception as e:
        return None, f"Error: {e}"

def parse_vars(vars_str):
    """Parse variables string (e.g. x=5,y=10) into a dictionary of floats."""
    if not vars_str:
        return {}
    variables = {}
    for item in vars_str.split(','):
        if '=' not in item:
            raise ValueError(f"Invalid variable format '{item}'. Must be key=value.")
        key, value = item.split('=', 1)
        key = key.strip()
        if not key.isidentifier():
            raise ValueError(f"Invalid variable name '{key}'")
        try:
            variables[key] = float(value.strip())
        except ValueError:
            raise ValueError(f"Variable '{key}' must have a numeric value (got '{value}')")
    return variables

def interactive_shell():
    """Run interactive REPL shell."""
    print("=========================================================")
    print(" Safe Math Evaluator Shell")
    print(" Type your expressions below. Type 'exit' or 'quit' to end.")
    print(" Constants available: pi, e. Functions: sin, cos, sqrt, log...")
    print(" Define variables: x = 42, then use them.")
    print("=========================================================")
    
    variables = {}
    while True:
        try:
            line = input("math > ").strip()
            if not line:
                continue
            if line.lower() in ('exit', 'quit'):
                break
                
            # Allow interactive variable assignments like "x = 5 + 4"
            if '=' in line and not any(op in line.split('=')[0] for op in ['>', '<', '!', '=']):
                parts = line.split('=', 1)
                var_name = parts[0].strip()
                expr = parts[1].strip()
                if var_name.isidentifier():
                    result, err = safe_evaluate(expr, variables)
                    if err:
                        print(err)
                    else:
                        variables[var_name] = result
                        print(f"{var_name} = {result}")
                    continue
                
            # Standard expression evaluation
            result, err = safe_evaluate(line, variables)
            if err:
                print(err)
            else:
                print(result)
        except (KeyboardInterrupt, EOFError):
            print("\nGoodbye!")
            break
        except Exception as e:
            print(f"Error: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="Safely evaluate mathematical expressions using AST analysis without using built-in evaluation."
    )
    parser.add_argument('expression', nargs='?', help='Mathematical expression to evaluate')
    parser.add_argument('-e', '--expr', help='Mathematical expression to evaluate (alternative to positional argument)')
    parser.add_argument('-v', '--vars', help='Variables defined as key-value pairs, comma-separated (e.g. x=5,y=10)')
    parser.add_argument('-i', '--interactive', action='store_true', help='Start interactive math REPL session')
    
    args = parser.parse_args()
    
    # Check for variables
    variables = {}
    if args.vars:
        try:
            variables = parse_vars(args.vars)
        except ValueError as ve:
            print(ve, file=sys.stderr)
            return 1
            
    if args.interactive:
        interactive_shell()
        return 0
        
    expr = args.expression or args.expr
    if not expr:
        parser.print_help()
        return 1
        
    result, err = safe_evaluate(expr, variables)
    if err:
        print(err, file=sys.stderr)
        return 1
    else:
        # Print representation: integer if it ends in .0, otherwise float
        if isinstance(result, float) and result.is_integer():
            print(int(result))
        else:
            print(result)
        return 0

if __name__ == "__main__":
    sys.exit(main())
