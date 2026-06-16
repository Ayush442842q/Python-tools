#!/usr/bin/env python3
"""
Base Converter & Bitwise Calculator

A CLI utility to convert numbers between binary, octal, decimal, hexadecimal, 
and custom bases (2 to 36), and to visualize bitwise operations (AND, OR, XOR, 
NOT, shifts) step-by-step.

Usage:
    python tools/base_converter.py -n 42 --to-base all
    python tools/base_converter.py -n 0xff -t 2 -b 16
    python tools/base_converter.py -n 12 --op AND --val 5
    python tools/base_converter.py -n 0b1010 --op LSHIFT --shift 2
"""

import argparse
import os
import sys
from typing import List, Dict, Any, Tuple

# ANSI Colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"

def supports_color() -> bool:
    """Checks if terminal supports colors."""
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform or is_a_tty

def color_text(text: str, color_code: str) -> str:
    """Wraps text in color codes if supported."""
    return f"{color_code}{text}{COLOR_RESET}" if supports_color() else text

def int_to_base(n: int, base: int) -> str:
    """Converts an integer to a string in the specified base (2-36)."""
    if n == 0:
        return "0"
    
    is_negative = n < 0
    n = abs(n)
    
    digits = "0123456789abcdefghijklmnopqrstuvwxyz"
    result = []
    
    while n:
        result.append(digits[n % base])
        n //= base
        
    if is_negative:
        result.append("-")
        
    return "".join(reversed(result))

def parse_number(num_str: str, from_base: int = None) -> int:
    """Parses a number string into an integer, auto-detecting base if not specified."""
    num_str = num_str.strip().lower()
    
    if from_base:
        return int(num_str, from_base)
        
    # Auto-detect base
    if num_str.startswith('0x'):
        return int(num_str, 16)
    elif num_str.startswith('0b'):
        return int(num_str, 2)
    elif num_str.startswith('0o'):
        return int(num_str, 8)
    else:
        # Try base 10, then 16 (in case prefix is missing but contains hex chars), then fail
        try:
            return int(num_str, 10)
        except ValueError:
            try:
                return int(num_str, 16)
            except ValueError:
                raise ValueError(f"Could not auto-detect base of '{num_str}'. Please specify base explicitly.")

def to_binary_str(val: int, bits: int = None) -> str:
    """Formats an integer into a binary string of specific bit width (two's complement if negative)."""
    if bits is None:
        # Auto bits (multiple of 8)
        bit_len = val.bit_length()
        bits = max(8, ((bit_len + 7) // 8) * 8)
        
    if val < 0:
        # Two's complement for negative numbers
        val = (1 << bits) + val
        if val < 0:
            raise ValueError(f"Value too negative to fit in {bits} bits")
            
    # Mask to specified bit width
    mask = (1 << bits) - 1
    val = val & mask
    
    binary_str = f"{val:0{bits}b}"
    
    # Format with spaces every 4 bits for readability
    parts = [binary_str[i:i+4] for i in range(0, len(binary_str), 4)]
    return " ".join(parts)

def show_conversions(val: int, bits: int = None) -> None:
    """Prints number represented in all common bases."""
    print(color_text(f"=== Representations for Decimal: {val} ===", COLOR_BOLD))
    print(f"  {color_text('Decimal:', COLOR_CYAN):<15} {val}")
    print(f"  {color_text('Hexadecimal:', COLOR_CYAN):<15} 0x{int_to_base(val, 16)}")
    print(f"  {color_text('Octal:', COLOR_CYAN):<15} 0o{int_to_base(val, 8)}")
    
    try:
        binary_formatted = to_binary_str(val, bits)
        print(f"  {color_text('Binary:', COLOR_CYAN):<15} 0b{binary_formatted}")
    except ValueError as e:
        print(f"  {color_text('Binary:', COLOR_CYAN):<15} 0b{int_to_base(val, 2)} (cannot fit in two's complement: {e})")
        
    # Additional bases
    print(f"  {color_text('Base 3 (Ternary):', COLOR_CYAN):<15} {int_to_base(val, 3)}")
    print(f"  {color_text('Base 12 (Duodecimal):', COLOR_CYAN):<15} {int_to_base(val, 12)}")
    print(f"  {color_text('Base 36:', COLOR_CYAN):<15} {int_to_base(val, 36)}")

def visualize_bitwise(val1: int, val2: int, op: str, bits: int = None) -> None:
    """Displays a step-by-step bitwise operation visualization."""
    if bits is None:
        max_val = max(abs(val1), abs(val2))
        bit_len = max_val.bit_length()
        bits = max(8, ((bit_len + 7) // 8) * 8)
        
    bin1 = to_binary_str(val1, bits)
    bin2 = to_binary_str(val2, bits) if val2 is not None else ""
    
    print(color_text(f"=== Bitwise Operation Visualization ({bits}-bit) ===", COLOR_BOLD))
    
    # Setup strings
    label1 = f"Val 1 ({val1})"
    label2 = f"Val 2 ({val2})"
    
    max_label_len = max(len(label1), len(label2)) + 2
    
    print(f"{label1:<{max_label_len}}: {bin1}")
    
    result = 0
    op_symbol = ""
    
    if op == 'AND':
        result = val1 & val2
        op_symbol = "&"
        print(f"{op_symbol} {label2:<{max_label_len-2}}: {bin2}")
    elif op == 'OR':
        result = val1 | val2
        op_symbol = "|"
        print(f"{op_symbol} {label2:<{max_label_len-2}}: {bin2}")
    elif op == 'XOR':
        result = val1 ^ val2
        op_symbol = "^"
        print(f"{op_symbol} {label2:<{max_label_len-2}}: {bin2}")
    elif op == 'NOT':
        result = ~val1
        op_symbol = "~"
        # NOT is unary
        print(f"{op_symbol} {'(Unary NOT)':<{max_label_len-2}}")
    elif op == 'LSHIFT':
        # val2 is the shift amount
        result = val1 << val2
        op_symbol = "<<"
        print(f"{op_symbol} {f'Shift by {val2}':<{max_label_len-2}}")
    elif op == 'RSHIFT':
        result = val1 >> val2
        op_symbol = ">>"
        print(f"{op_symbol} {f'Shift by {val2}':<{max_label_len-2}}")
        
    bin_res = to_binary_str(result, bits)
    
    # Print separator
    sep_len = max_label_len + len(bin1) + 2
    print("-" * sep_len)
    
    res_label = f"Result ({result})"
    print(f"{res_label:<{max_label_len}}: {color_text(bin_res, COLOR_GREEN)}")
    
    # Extra output breakdown
    print(f"\nResult representations:")
    print(f"  Decimal: {result}")
    print(f"  Hex:     0x{int_to_base(result, 16)}")

def main() -> int:
    parser = argparse.ArgumentParser(description="Base Converter & Bitwise Calculator")
    parser.add_argument('-n', '--number', required=True, help="Number to convert/operate on (e.g. 42, 0b1010, 0x2a)")
    parser.add_argument('-f', '--from-base', type=int, choices=range(2, 37), help="Base of the input number (2-36, auto-detected if omitted)")
    parser.add_argument('-t', '--to-base', help="Base to convert to (2-36 or 'all', default: 10)")
    parser.add_argument('-b', '--bits', type=int, choices=[8, 16, 32, 64], help="Bit width for binary display (8, 16, 32, or 64)")
    
    # Bitwise arguments
    parser.add_argument('--op', choices=['AND', 'OR', 'XOR', 'NOT', 'LSHIFT', 'RSHIFT'], help="Bitwise operation to perform")
    parser.add_argument('--val', help="Second operand value (for AND, OR, XOR)")
    parser.add_argument('--shift', type=int, help="Shift amount (for LSHIFT, RSHIFT)")
    
    args = parser.parse_args()
    
    try:
        val1 = parse_number(args.number, args.from_base)
    except ValueError as e:
        print(f"Error parsing input number: {e}", file=sys.stderr)
        return 1
        
    # Bitwise operation execution path
    if args.op:
        val2 = None
        if args.op in ['AND', 'OR', 'XOR']:
            if args.val is None:
                print(f"Error: Operation {args.op} requires a second operand (--val).", file=sys.stderr)
                return 1
            try:
                val2 = parse_number(args.val)
            except ValueError as e:
                print(f"Error parsing second operand (--val): {e}", file=sys.stderr)
                return 1
        elif args.op in ['LSHIFT', 'RSHIFT']:
            if args.shift is None:
                print(f"Error: Operation {args.op} requires shift amount (--shift).", file=sys.stderr)
                return 1
            val2 = args.shift
            
        try:
            visualize_bitwise(val1, val2, args.op, args.bits)
        except ValueError as e:
            print(f"Error executing bitwise operation: {e}", file=sys.stderr)
            return 1
            
    # Simple conversion path
    else:
        to_base = args.to_base or "10"
        
        if to_base.lower() == 'all':
            show_conversions(val1, args.bits)
        else:
            try:
                base_num = int(to_base)
                if base_num < 2 or base_num > 36:
                    raise ValueError("Base must be between 2 and 36")
            except ValueError:
                print(f"Error: Target base must be an integer between 2 and 36, or 'all'. Received '{to_base}'", file=sys.stderr)
                return 1
                
            converted = int_to_base(val1, base_num)
            
            # Special formatting for binary/hex/octal prefixes
            prefix = ""
            if base_num == 2:
                prefix = "0b"
                try:
                    converted = to_binary_str(val1, args.bits)
                except ValueError:
                    pass
            elif base_num == 8:
                prefix = "0o"
            elif base_num == 16:
                prefix = "0x"
                
            print(f"{prefix}{converted}")
            
    return 0

if __name__ == "__main__":
    sys.exit(main())
