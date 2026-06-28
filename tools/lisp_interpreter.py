#!/usr/bin/env python3
"""
Lisp Interpreter - A minimal Scheme-like Lisp interpreter in Python

This tool provides an interactive Read-Eval-Print Loop (REPL) or evaluates Lisp files.
It implements a token parser, lexical environments (lexical scoping), variable bindings,
user-defined functions (lambda expressions), recursive functions, lists, and basic arithmetic.

Usage:
    python tools/lisp_interpreter.py [file.lisp]
    python tools/lisp_interpreter.py --repl

Example:
    python tools/lisp_interpreter.py -c "(define circle-area (lambda (r) (* 3.14159 (* r r)))) (circle-area 10)"
"""

import argparse
import sys
import math
import traceback
from typing import List, Union, Dict, Any, Optional

# Types
Symbol = str
Number = Union[int, float]
Atom = Union[Symbol, Number]
List_type = list
Exp = Union[Atom, List_type]

class Env(dict):
    """An environment: a dict of {'var': val} pairs, with an outer Env."""
    def __init__(self, parms=(), args=(), outer=None):
        super().__init__()
        self.update(zip(parms, args))
        self.outer = outer

    def find(self, var: str) -> 'Env':
        """Find the innermost Env where var appears."""
        if var in self:
            return self
        elif self.outer is not None:
            return self.outer.find(var)
        else:
            raise NameError(f"Symbol '{var}' is undefined")

def standard_env() -> Env:
    """An environment with standard procedures."""
    env = Env()
    import operator as op
    env.update({
        '+': lambda *args: sum(args),
        '-': lambda x, *args: x - sum(args) if args else -x,
        '*': lambda *args: math.prod(args) if args else 1,
        '/': lambda x, *args: x / math.prod(args) if args else 1/x,
        '>': op.gt,
        '<': op.lt,
        '>=': op.ge,
        '<=': op.le,
        '=': op.eq,
        'equal?': op.eq,
        'abs': abs,
        'append': lambda x, y: x + y,
        'car': lambda x: x[0] if x else [],
        'cdr': lambda x: x[1:] if len(x) > 1 else [],
        'cons': lambda x, y: [x] + y,
        'length': len,
        'list': lambda *x: list(x),
        'list?': lambda x: isinstance(x, list),
        'map': lambda f, x: list(map(f, x)),
        'not': op.not_,
        'null?': lambda x: x == [],
        'number?': lambda x: isinstance(x, (int, float)),
        'print': print,
        'procedure?': callable,
        'symbol?': lambda x: isinstance(x, Symbol),
        'pi': math.pi,
        'e': math.e,
    })
    return env

def tokenize(chars: str) -> List[str]:
    """Convert a string of characters into a list of tokens."""
    # Ensure quotes are separated
    chars = chars.replace('(', ' ( ').replace(')', ' ) ')
    
    # Process string literals in Lisp if any
    tokens = []
    in_string = False
    current_str = []
    
    # Simple lexical scanner
    words = chars.split()
    for word in words:
        tokens.append(word)
    return tokens

def parse(program: str) -> Exp:
    """Read a Lisp expression from a string."""
    tokens = tokenize(program)
    if not tokens:
        raise SyntaxError("Empty program")
    return read_from_tokens(tokens)

def read_from_tokens(tokens: List[str]) -> Exp:
    """Read an expression from a sequence of tokens."""
    if len(tokens) == 0:
        raise SyntaxError('Unexpected EOF')
    token = tokens.pop(0)
    if token == '(':
        L = []
        while tokens and tokens[0] != ')':
            L.append(read_from_tokens(tokens))
        if not tokens:
            raise SyntaxError('Expected closing parenthesis )')
        tokens.pop(0) # pop off ')'
        return L
    elif token == ')':
        raise SyntaxError('Unexpected )')
    else:
        return atom(token)

def atom(token: str) -> Atom:
    """Numbers become numbers; every other token is a symbol."""
    try:
        return int(token)
    except ValueError:
        try:
            return float(token)
        except ValueError:
            return Symbol(token)

def eval_exp(x: Exp, env: Env) -> Any:
    """Evaluate an expression in an environment."""
    if isinstance(x, Symbol):      # variable reference
        return env.find(x)[x]
    elif not isinstance(x, list):  # constant literal
        return x
    
    if not x:
        return []
        
    op_symbol = x[0]
    
    if op_symbol == 'quote':        # (quote exp)
        if len(x) != 2:
            raise ValueError("quote expects exactly 1 argument")
        return x[1]
    elif op_symbol == 'if':         # (if test conseq alt)
        if len(x) < 3 or len(x) > 4:
            raise ValueError("if expects a test, a consequence, and an optional alternative")
        test = x[1]
        conseq = x[2]
        alt = x[3] if len(x) == 4 else []
        exp = conseq if eval_exp(test, env) else alt
        return eval_exp(exp, env)
    elif op_symbol == 'define':     # (define var exp)
        if len(x) != 3:
            raise ValueError("define expects exactly 2 arguments (variable and expression)")
        var = x[1]
        if not isinstance(var, Symbol):
            raise TypeError("define first argument must be a symbol")
        exp = x[2]
        env[var] = eval_exp(exp, env)
        return env[var]
    elif op_symbol == 'set!':       # (set! var exp)
        if len(x) != 3:
            raise ValueError("set! expects exactly 2 arguments (variable and expression)")
        var = x[1]
        if not isinstance(var, Symbol):
            raise TypeError("set! first argument must be a symbol")
        exp = x[2]
        env.find(var)[var] = eval_exp(exp, env)
        return env[var]
    elif op_symbol == 'lambda':     # (lambda (var...) exp)
        if len(x) < 3:
            raise ValueError("lambda expects parameter list and body expression")
        vars_list = x[1]
        if not isinstance(vars_list, list):
            raise TypeError("lambda parameters must be a list")
        body = x[2]
        return lambda *args: eval_exp(body, Env(vars_list, args, env))
    elif op_symbol == 'begin':      # (begin exp...)
        val = None
        for exp in x[1:]:
            val = eval_exp(exp, env)
        return val
    else:                           # (proc arg...)
        proc = eval_exp(x[0], env)
        args = [eval_exp(arg, env) for arg in x[1:]]
        if not callable(proc):
            raise TypeError(f"Expression {x[0]} evaluates to non-procedure: {proc}")
        return proc(*args)

def to_string(exp: Any) -> str:
    """Convert a Python object back into a Lisp-readable string."""
    if isinstance(exp, list):
        return '(' + ' '.join(map(to_string, exp)) + ')'
    elif exp is True:
        return '#t'
    elif exp is False or exp == []:
        return '#f'
    elif callable(exp):
        return '<procedure>'
    else:
        return str(exp)

def run_code(code: str, env: Env) -> Any:
    """Parse and evaluate multiple expressions in code."""
    # Simple tokenizer logic that handles multiple parenthesized expressions
    # e.g., (define x 10) (define y 20) (+ x y)
    code = code.strip()
    if not code:
        return None
        
    # Standard parsing of multiple S-expressions
    tokens = tokenize(code)
    results = []
    while tokens:
        exp = read_from_tokens(tokens)
        results.append(eval_exp(exp, env))
    return results[-1] if results else None

def repl(env: Env):
    """Start an interactive Read-Eval-Print Loop."""
    print("--------------------------------------------------")
    print(" Lisp Interpreter - Interactive REPL (Scheme-like) ")
    print(" Press Ctrl+C or type (exit) to quit.             ")
    print(" Built-in procedures: +, -, *, /, car, cdr, cons, ")
    print("   define, lambda, if, begin, print, map, list    ")
    print("--------------------------------------------------")
    
    # Add exit to env
    env['exit'] = lambda: sys.exit(0)
    env['quit'] = lambda: sys.exit(0)
    
    bracket_balance = 0
    buffer = []
    
    while True:
        try:
            prompt = "lisp> " if not buffer else "      "
            line = input(prompt)
            buffer.append(line)
            
            # Count parenthesis balance
            full_input = "\n".join(buffer)
            open_brackets = full_input.count('(')
            close_brackets = full_input.count(')')
            
            if open_brackets <= close_brackets and full_input.strip():
                # We have completed a full block (or unbalanced towards closing)
                try:
                    res = run_code(full_input, env)
                    if res is not None:
                        print(f"\033[92m=> {to_string(res)}\033[0m")
                except Exception as e:
                    print(f"\033[91mError: {e}\033[0m")
                buffer = []
            elif not full_input.strip():
                buffer = []
        except KeyboardInterrupt:
            print("\nKeyboardInterrupt")
            buffer = []
        except EOFError:
            print("\nGoodbye!")
            break

def main():
    parser = argparse.ArgumentParser(description="A minimal Scheme-like Lisp interpreter in Python.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument('file', nargs='?', help='Lisp file to evaluate')
    group.add_argument('-c', '--command', help='evaluate Lisp command string')
    group.add_argument('--repl', action='store_true', help='start interactive REPL')
    
    args = parser.parse_args()
    env = standard_env()
    
    if args.command:
        try:
            res = run_code(args.command, env)
            if res is not None:
                print(to_string(res))
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    elif args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                content = f.read()
            res = run_code(content, env)
            if res is not None:
                print(to_string(res))
        except FileNotFoundError:
            print(f"Error: File '{args.file}' not found", file=sys.stderr)
            sys.exit(1)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            traceback.print_exc()
            sys.exit(1)
    else:
        # Default to REPL if no args are specified
        repl(env)

if __name__ == '__main__':
    main()
