#!/usr/bin/env python3
"""
Classical Ciphers Toolkit
Encrypt, decrypt, or cryptanalyze classical ciphers including Caesar, Vigenère,
ROT13, Rail Fence, Playfair, and Affine ciphers.
Also includes an automated Caesar cipher cracker using English letter frequency analysis.
"""

import argparse
import sys
import os
import math

# English letter frequencies for cracking Caesar cipher
ENGLISH_FREQ = {
    'A': 0.0817, 'B': 0.0150, 'C': 0.0278, 'D': 0.0425, 'E': 0.1270, 'F': 0.0223,
    'G': 0.0202, 'H': 0.0609, 'I': 0.0697, 'J': 0.0015, 'K': 0.0077, 'L': 0.0403,
    'M': 0.0241, 'N': 0.0675, 'O': 0.0751, 'P': 0.0193, 'Q': 0.0010, 'R': 0.0599,
    'S': 0.0633, 'T': 0.0906, 'U': 0.0276, 'V': 0.0098, 'W': 0.0236, 'X': 0.0015,
    'Y': 0.0197, 'Z': 0.0007
}


class ClassicalCiphers:
    @staticmethod
    def caesar(text, shift, decrypt=False):
        """Encrypts or decrypts Caesar cipher."""
        if decrypt:
            shift = -shift
        result = []
        for char in text:
            if char.isalpha():
                base = ord('A') if char.isupper() else ord('a')
                result.append(chr((ord(char) - base + shift) % 26 + base))
            else:
                result.append(char)
        return "".join(result)

    @staticmethod
    def rot13(text):
        """ROT13 is a special case of Caesar cipher with shift 13."""
        return ClassicalCiphers.caesar(text, 13)

    @staticmethod
    def vigenere(text, key, decrypt=False):
        """Encrypts or decrypts Vigenère cipher."""
        if not key.isalpha():
            raise ValueError("Vigenère key must contain only alphabetic characters.")
        key = key.upper()
        result = []
        key_idx = 0
        for char in text:
            if char.isalpha():
                base = ord('A') if char.isupper() else ord('a')
                shift = ord(key[key_idx % len(key)]) - ord('A')
                if decrypt:
                    shift = -shift
                result.append(chr((ord(char) - base + shift) % 26 + base))
                key_idx += 1
            else:
                result.append(char)
        return "".join(result)

    @staticmethod
    def rail_fence(text, rails, decrypt=False):
        """Encrypts or decrypts Rail Fence (Zigzag) cipher."""
        if rails <= 1:
            return text
            
        if not decrypt:
            # Encryption
            fence = [[] for _ in range(rails)]
            rail = 0
            direction = 1
            for char in text:
                fence[rail].append(char)
                rail += direction
                if rail == rails - 1 or rail == 0:
                    direction = -direction
            return "".join(["".join(r) for r in fence])
        else:
            # Decryption
            # Determine pattern of rails
            pattern = [0] * len(text)
            rail = 0
            direction = 1
            for i in range(len(text)):
                pattern[i] = rail
                rail += direction
                if rail == rails - 1 or rail == 0:
                    direction = -direction
            
            # Count chars per rail
            rail_counts = [pattern.count(r) for r in range(rails)]
            
            # Divide cipher text into rail segments
            segments = []
            idx = 0
            for count in rail_counts:
                segments.append(list(text[idx:idx + count]))
                idx += count
                
            # Reconstruct original text
            result = []
            rail_idx = [0] * rails
            rail = 0
            direction = 1
            for i in range(len(text)):
                target_rail = pattern[i]
                result.append(segments[target_rail][rail_idx[target_rail]])
                rail_idx[target_rail] += 1
            return "".join(result)

    @staticmethod
    def _playfair_matrix(key):
        """Generates 5x5 Playfair key matrix (combining I and J)."""
        key = key.upper().replace('J', 'I')
        seen = set()
        matrix = []
        for char in key:
            if char.isalpha() and char not in seen:
                seen.add(char)
                matrix.append(char)
        for i in range(26):
            char = chr(ord('A') + i)
            if char == 'J':
                continue
            if char not in seen:
                seen.add(char)
                matrix.append(char)
        return [matrix[i:i+5] for i in range(0, 25, 5)]

    @staticmethod
    def playfair(text, key, decrypt=False):
        """Encrypts or decrypts Playfair cipher."""
        matrix = ClassicalCiphers._playfair_matrix(key)
        # Find coordinates
        coords = {}
        for r in range(5):
            for c in range(5):
                coords[matrix[r][c]] = (r, c)
                
        # Clean text
        cleaned_text = []
        for char in text.upper():
            if char.isalpha():
                cleaned_text.append(char.replace('J', 'I'))
                
        # Prepare bigrams
        bigrams = []
        i = 0
        while i < len(cleaned_text):
            char1 = cleaned_text[i]
            char2 = 'X'
            if i + 1 < len(cleaned_text):
                if cleaned_text[i] != cleaned_text[i+1]:
                    char2 = cleaned_text[i+1]
                    i += 2
                else:
                    i += 1
            else:
                i += 1
            bigrams.append((char1, char2))
            
        result = []
        shift = -1 if decrypt else 1
        
        for c1, c2 in bigrams:
            r1, col1 = coords[c1]
            r2, col2 = coords[c2]
            
            if r1 == r2:
                # Same row - shift columns
                result.append(matrix[r1][(col1 + shift) % 5])
                result.append(matrix[r2][(col2 + shift) % 5])
            elif col1 == col2:
                # Same column - shift rows
                result.append(matrix[(r1 + shift) % 5][col1])
                result.append(matrix[(r2 + shift) % 5][col2])
            else:
                # Rectangle - swap columns
                result.append(matrix[r1][col2])
                result.append(matrix[r2][col1])
                
        return "".join(result)

    @staticmethod
    def affine(text, a, b, decrypt=False):
        """Encrypts or decrypts Affine cipher: E(x) = (ax + b) mod 26."""
        if math.gcd(a, 26) != 1:
            raise ValueError(f"Key 'a' ({a}) must be coprime to 26 (gcd(a, 26) == 1).")
            
        # Find modular multiplicative inverse of a mod 26
        a_inv = 1
        for i in range(1, 26):
            if (a * i) % 26 == 1:
                a_inv = i
                break
                
        result = []
        for char in text:
            if char.isalpha():
                is_upper = char.isupper()
                x = ord(char.upper()) - ord('A')
                if not decrypt:
                    y = (a * x + b) % 26
                else:
                    y = (a_inv * (x - b)) % 26
                new_char = chr(y + ord('A'))
                result.append(new_char if is_upper else new_char.lower())
            else:
                result.append(char)
        return "".join(result)

    @staticmethod
    def crack_caesar(ciphertext):
        """Cracks Caesar cipher using English letter frequency analysis."""
        best_shift = 0
        min_chi_squared = float('inf')
        
        # Keep only alphabetic chars for frequency analysis
        alpha_text = [c.upper() for c in ciphertext if c.isalpha()]
        if not alpha_text:
            return 0, ciphertext
            
        total_chars = len(alpha_text)
        
        # Calculate chi-squared statistic for all possible shifts (0-25)
        for shift in range(26):
            shifted_counts = {chr(ord('A') + i): 0 for i in range(26)}
            for char in alpha_text:
                # Apply negative shift to simulate decryption
                decrypted_char = chr((ord(char) - ord('A') - shift) % 26 + ord('A'))
                shifted_counts[decrypted_char] += 1
                
            chi_sq = 0.0
            for char in ENGLISH_FREQ:
                observed = shifted_counts[char]
                expected = ENGLISH_FREQ[char] * total_chars
                if expected > 0:
                    chi_sq += ((observed - expected) ** 2) / expected
                    
            if chi_sq < min_chi_squared:
                min_chi_squared = chi_sq
                best_shift = shift
                
        decrypted_text = ClassicalCiphers.caesar(ciphertext, best_shift, decrypt=True)
        return best_shift, decrypted_text


def main():
    parser = argparse.ArgumentParser(
        description="Classical Ciphers Toolkit - Encrypt, decrypt, or crack classical ciphers."
    )
    parser.add_argument(
        '--cipher', '-c', 
        choices=['caesar', 'vigenere', 'rot13', 'railfence', 'playfair', 'affine'], 
        required=True,
        help="Cipher algorithm to use"
    )
    parser.add_argument(
        '--mode', '-m', 
        choices=['encrypt', 'decrypt', 'crack'], 
        default='encrypt',
        help="Operation mode (default: encrypt). Note: 'crack' only supports Caesar cipher."
    )
    parser.add_argument(
        '--key', '-k', 
        help="Key for the cipher. Caesar/Railfence: int, Vigenere/Playfair: string, Affine: 'a,b' (e.g., '5,8')"
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--text', '-t', help="Text to process")
    group.add_argument('--file', '-f', help="Path to file containing text to process")
    
    parser.add_argument('--output', '-o', help="Output file path (prints to terminal if omitted)")
    
    args = parser.parse_args()
    
    # Get input text
    if args.file:
        if not os.path.exists(args.file):
            print(f"Error: File '{args.file}' not found.", file=sys.stderr)
            return 1
        with open(args.file, 'r', encoding='utf-8') as f:
            text = f.read()
    else:
        text = args.text

    # Basic validations
    if args.mode == 'crack':
        if args.cipher != 'caesar':
            print("Error: The 'crack' mode is only supported with the 'caesar' cipher.", file=sys.stderr)
            return 1
    elif args.cipher != 'rot13' and not args.key:
        print(f"Error: Cipher '{args.cipher}' requires a --key.", file=sys.stderr)
        return 1

    try:
        if args.cipher == 'caesar':
            if args.mode == 'crack':
                shift, decrypted = ClassicalCiphers.crack_caesar(text)
                result = f"--- Cracked Caesar Cipher ---\nEstimated Shift Key: {shift}\nDecrypted Text:\n{decrypted}"
            else:
                try:
                    shift = int(args.key)
                except ValueError:
                    print("Error: Caesar cipher key must be an integer.", file=sys.stderr)
                    return 1
                decrypt = (args.mode == 'decrypt')
                result = ClassicalCiphers.caesar(text, shift, decrypt)
                
        elif args.cipher == 'rot13':
            result = ClassicalCiphers.rot13(text)
            
        elif args.cipher == 'vigenere':
            decrypt = (args.mode == 'decrypt')
            result = ClassicalCiphers.vigenere(text, args.key, decrypt)
            
        elif args.cipher == 'railfence':
            try:
                rails = int(args.key)
            except ValueError:
                print("Error: Rail Fence cipher key (rails) must be an integer.", file=sys.stderr)
                return 1
            decrypt = (args.mode == 'decrypt')
            result = ClassicalCiphers.rail_fence(text, rails, decrypt)
            
        elif args.cipher == 'playfair':
            decrypt = (args.mode == 'decrypt')
            result = ClassicalCiphers.playfair(text, args.key, decrypt)
            
        elif args.cipher == 'affine':
            try:
                a_str, b_str = args.key.split(',')
                a, b = int(a_str), int(b_str)
            except ValueError:
                print("Error: Affine key must be in the format 'a,b' where a and b are integers (e.g. '5,8').", file=sys.stderr)
                return 1
            decrypt = (args.mode == 'decrypt')
            result = ClassicalCiphers.affine(text, a, b, decrypt)
            
    except Exception as e:
        print(f"Execution Error: {e}", file=sys.stderr)
        return 1

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(result)
        print(f"Successfully wrote output to '{args.output}'.")
    else:
        print(result)
        
    return 0


if __name__ == "__main__":
    sys.exit(main())
