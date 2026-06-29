#!/usr/bin/env python3
"""
CLI Matrix Calculator
An interactive terminal-based matrix algebra calculator written in pure Python.
Supports Matrix Addition, Subtraction, Multiplication, Transposition, Determinant,
Inverse, Rank, Trace, and Power calculations with premium Unicode box formatting.
"""

import sys
import os
import math

# ANSI Colors
COLOR_RESET = "\033[0m"
COLOR_GREEN = "\033[32m"
COLOR_CYAN = "\033[36m"
COLOR_YELLOW = "\033[33m"
COLOR_RED = "\033[31m"
COLOR_BOLD = "\033[1m"

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

# Matrix Operations
def matrix_add(A, B):
    if len(A) != len(B) or len(A[0]) != len(B[0]):
        raise ValueError("Matrices must have the same dimensions for addition.")
    return [[A[r][c] + B[r][c] for c in range(len(A[0]))] for r in range(len(A))]

def matrix_subtract(A, B):
    if len(A) != len(B) or len(A[0]) != len(B[0]):
        raise ValueError("Matrices must have the same dimensions for subtraction.")
    return [[A[r][c] - B[r][c] for c in range(len(A[0]))] for r in range(len(A))]

def matrix_multiply(A, B):
    if len(A[0]) != len(B):
        raise ValueError("Columns of A must match rows of B for multiplication.")
    result = [[0.0 for _ in range(len(B[0]))] for _ in range(len(A))]
    for r in range(len(A)):
        for c in range(len(B[0])):
            result[r][c] = sum(A[r][k] * B[k][c] for k in range(len(A[0])))
    return result

def matrix_transpose(A):
    return [[A[r][c] for r in range(len(A))] for c in range(len(A[0]))]

def matrix_trace(A):
    if len(A) != len(A[0]):
        raise ValueError("Matrix must be square to calculate trace.")
    return sum(A[i][i] for i in range(len(A)))

def matrix_determinant(A):
    n = len(A)
    if n != len(A[0]):
        raise ValueError("Matrix must be square to calculate determinant.")
    
    # Base cases for performance/accuracy
    if n == 1:
        return A[0][0]
    if n == 2:
        return A[0][0] * A[1][1] - A[0][1] * A[1][0]
    if n == 3:
        return (A[0][0] * (A[1][1] * A[2][2] - A[1][2] * A[2][1]) -
                A[0][1] * (A[1][0] * A[2][2] - A[1][2] * A[2][0]) +
                A[0][2] * (A[1][0] * A[2][1] - A[1][1] * A[2][0]))
                
    # Gaussian elimination for larger matrices
    M = [[float(val) for val in row] for row in A]
    det = 1.0
    for i in range(n):
        pivot = i
        for r in range(i + 1, n):
            if abs(M[r][i]) > abs(M[pivot][i]):
                pivot = r
        if pivot != i:
            M[i], M[pivot] = M[pivot], M[i]
            det *= -1.0
        if abs(M[i][i]) < 1e-9:
            return 0.0
        det *= M[i][i]
        for r in range(i + 1, n):
            factor = M[r][i] / M[i][i]
            for c in range(i, n):
                M[r][c] -= factor * M[i][c]
    return det

def matrix_inverse(A):
    n = len(A)
    if n != len(A[0]):
        raise ValueError("Matrix must be square to invert.")
    
    # Create augmented matrix [A | I]
    M = [[float(A[r][c]) for c in range(n)] for r in range(n)]
    I = [[1.0 if r == c else 0.0 for c in range(n)] for r in range(n)]
    
    for i in range(n):
        # Search for pivot
        pivot = i
        for r in range(i + 1, n):
            if abs(M[r][i]) > abs(M[pivot][i]):
                pivot = r
        if pivot != i:
            M[i], M[pivot] = M[pivot], M[i]
            I[i], I[pivot] = I[pivot], I[i]
            
        if abs(M[i][i]) < 1e-9:
            raise ValueError("Matrix is singular and cannot be inverted.")
            
        # Normalize pivot row
        divisor = M[i][i]
        for c in range(i, n):
            M[i][c] /= divisor
        for c in range(n):
            I[i][c] /= divisor
            
        # Eliminate other rows
        for r in range(n):
            if r != i:
                factor = M[r][i]
                for c in range(i, n):
                    M[r][c] -= factor * M[i][c]
                for c in range(n):
                    I[r][c] -= factor * I[i][c]
    return I

def matrix_rank(A):
    rows = len(A)
    cols = len(A[0])
    M = [[float(val) for val in row] for row in A]
    
    rank = 0
    c = 0
    for r in range(rows):
        while c < cols:
            # Find non-zero element in column c from row r downwards
            pivot = r
            while pivot < rows and abs(M[pivot][c]) < 1e-9:
                pivot += 1
            if pivot < rows:
                # Swap rows
                M[r], M[pivot] = M[pivot], M[r]
                # Eliminate elements below pivot
                for i in range(r + 1, rows):
                    factor = M[i][c] / M[r][c]
                    for j in range(c, cols):
                        M[i][j] -= factor * M[r][j]
                rank += 1
                c += 1
                break
            else:
                c += 1
    return rank

def matrix_power(A, power):
    if len(A) != len(A[0]):
        raise ValueError("Matrix must be square to calculate power.")
    if power < 0:
        raise ValueError("Matrix power must be a non-negative integer.")
    n = len(A)
    if power == 0:
        return [[1.0 if r == c else 0.0 for c in range(n)] for r in range(n)]
    
    # Binary exponentiation
    result = [[1.0 if r == c else 0.0 for c in range(n)] for r in range(n)]
    base = [[val for val in row] for row in A]
    while power > 0:
        if power % 2 == 1:
            result = matrix_multiply(result, base)
        base = matrix_multiply(base, base)
        power //= 2
    return result

# Presentation
def format_matrix(matrix):
    """Formats matrix nicely with Unicode brackets."""
    if not matrix or not matrix[0]:
        return "[]"
        
    rows = len(matrix)
    cols = len(matrix[0])
    
    # Convert elements to neat strings
    str_matrix = []
    max_len = 0
    for row in matrix:
        str_row = []
        for val in row:
            # Format nicely: strip trailing zeros from floats if they are integers
            if abs(val - round(val)) < 1e-9:
                s = str(int(round(val)))
            else:
                s = f"{val:.4f}".rstrip('0').rstrip('.')
            str_row.append(s)
            max_len = max(max_len, len(s))
        str_matrix.append(str_row)
        
    output = []
    for r in range(rows):
        # Choose bracket character based on position
        if rows == 1:
            left, right = "[", "]"
        elif r == 0:
            left, right = "┌", "┐"
        elif r == rows - 1:
            left, right = "└", "┘"
        else:
            left, right = "│", "│"
            
        row_str = "  ".join(s.rjust(max_len) for s in str_matrix[r])
        output.append(f"{left}  {row_str}  {right}")
        
    return "\n".join(output)

def input_matrix(name="Matrix"):
    print(f"\n{COLOR_CYAN}Entering {name}:{COLOR_RESET}")
    while True:
        try:
            dims = input("Enter dimensions (rows cols, e.g. '3 3'): ").strip().split()
            if len(dims) != 2:
                print(f"{COLOR_RED}Please enter exactly two integers.{COLOR_RESET}")
                continue
            rows, cols = int(dims[0]), int(dims[1])
            if rows <= 0 or cols <= 0:
                print(f"{COLOR_RED}Dimensions must be positive integers.{COLOR_RESET}")
                continue
            break
        except ValueError:
            print(f"{COLOR_RED}Invalid dimensions. Use integers.{COLOR_RESET}")
            
    matrix = []
    print(f"Enter matrix values row by row (space-separated, e.g. '1 2 3'):")
    for r in range(rows):
        while True:
            try:
                row_input = input(f"Row {r+1}: ").strip().split()
                if len(row_input) != cols:
                    print(f"{COLOR_RED}Expected {cols} values, got {len(row_input)}.{COLOR_RESET}")
                    continue
                row_vals = [float(x) for x in row_input]
                matrix.append(row_vals)
                break
            except ValueError:
                print(f"{COLOR_RED}Invalid numeric value in row.{COLOR_RESET}")
    return matrix

def interactive_menu():
    history = {}
    
    while True:
        clear_screen()
        print(f"{COLOR_BOLD}{COLOR_CYAN}=== CLI MATRIX CALCULATOR ==={COLOR_RESET}")
        print("1. Matrix Addition (A + B)")
        print("2. Matrix Subtraction (A - B)")
        print("3. Matrix Multiplication (A * B)")
        print("4. Matrix Transposition (A^T)")
        print("5. Matrix Determinant (det(A))")
        print("6. Matrix Inverse (A^-1)")
        print("7. Matrix Rank (rank(A))")
        print("8. Matrix Trace (tr(A))")
        print("9. Matrix Power (A^k)")
        print("0. Exit")
        
        choice = input("\nSelect operation (0-9): ").strip()
        if choice == '0':
            print(f"\n{COLOR_GREEN}Goodbye!{COLOR_RESET}")
            break
            
        if choice not in ['1', '2', '3', '4', '5', '6', '7', '8', '9']:
            input(f"\n{COLOR_RED}Invalid option. Press Enter to try again.{COLOR_RESET}")
            continue
            
        try:
            if choice in ['1', '2', '3']:
                A = input_matrix("Matrix A")
                B = input_matrix("Matrix B")
                
                print(f"\n{COLOR_BOLD}A:{COLOR_RESET}")
                print(format_matrix(A))
                print(f"\n{COLOR_BOLD}B:{COLOR_RESET}")
                print(format_matrix(B))
                
                if choice == '1':
                    result = matrix_add(A, B)
                    print(f"\n{COLOR_BOLD}{COLOR_GREEN}Result (A + B):{COLOR_RESET}")
                elif choice == '2':
                    result = matrix_subtract(A, B)
                    print(f"\n{COLOR_BOLD}{COLOR_GREEN}Result (A - B):{COLOR_RESET}")
                else:
                    result = matrix_multiply(A, B)
                    print(f"\n{COLOR_BOLD}{COLOR_GREEN}Result (A * B):{COLOR_RESET}")
                    
                print(format_matrix(result))
                
            elif choice in ['4', '5', '6', '7', '8', '9']:
                A = input_matrix("Matrix A")
                print(f"\n{COLOR_BOLD}Matrix A:{COLOR_RESET}")
                print(format_matrix(A))
                
                if choice == '4':
                    result = matrix_transpose(A)
                    print(f"\n{COLOR_BOLD}{COLOR_GREEN}Result (A^T):{COLOR_RESET}")
                    print(format_matrix(result))
                elif choice == '5':
                    det = matrix_determinant(A)
                    print(f"\n{COLOR_BOLD}{COLOR_GREEN}Determinant (det(A)):{COLOR_RESET} {det:.6f}".rstrip('0').rstrip('.'))
                elif choice == '6':
                    result = matrix_inverse(A)
                    print(f"\n{COLOR_BOLD}{COLOR_GREEN}Inverse (A^-1):{COLOR_RESET}")
                    print(format_matrix(result))
                elif choice == '7':
                    rank = matrix_rank(A)
                    print(f"\n{COLOR_BOLD}{COLOR_GREEN}Rank (rank(A)):{COLOR_RESET} {rank}")
                elif choice == '8':
                    trace = matrix_trace(A)
                    print(f"\n{COLOR_BOLD}{COLOR_GREEN}Trace (tr(A)):{COLOR_RESET} {trace:.6f}".rstrip('0').rstrip('.'))
                elif choice == '9':
                    while True:
                        try:
                            k = int(input("Enter power (integer >= 0): ").strip())
                            if k < 0:
                                print(f"{COLOR_RED}Power must be non-negative.{COLOR_RESET}")
                                continue
                            break
                        except ValueError:
                            print(f"{COLOR_RED}Please enter an integer.{COLOR_RESET}")
                    result = matrix_power(A, k)
                    print(f"\n{COLOR_BOLD}{COLOR_GREEN}Result (A^{k}):{COLOR_RESET}")
                    print(format_matrix(result))
                    
        except ValueError as e:
            print(f"\n{COLOR_RED}Math Error: {e}{COLOR_RESET}")
        except Exception as e:
            print(f"\n{COLOR_RED}Error: {e}{COLOR_RESET}")
            
        input("\nPress Enter to continue...")

def main():
    try:
        interactive_menu()
    except KeyboardInterrupt:
        print(f"\n\n{COLOR_YELLOW}Operation cancelled by user. Goodbye!{COLOR_RESET}")

if __name__ == "__main__":
    main()
