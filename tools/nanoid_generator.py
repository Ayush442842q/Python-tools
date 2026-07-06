#!/usr/bin/env python3
"""
NanoID Generator & Collision Estimator
Generates secure, URL-friendly unique IDs with customizable size and alphabets.
Includes a collision probability estimator based on birthday problem math.
"""

import argparse
import math
import secrets
import sys

# Standard URL-friendly NanoID alphabet (64 characters)
DEFAULT_ALPHABET = "_-0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

def generate_nanoid(alphabet=DEFAULT_ALPHABET, size=21):
    """
    Generate a secure NanoID using standard masking logic to avoid modulo bias.
    """
    if not alphabet:
        raise ValueError("Alphabet cannot be empty.")
    if size <= 0:
        raise ValueError("Size must be greater than zero.")
        
    alphabet_len = len(alphabet)
    
    # Calculate mask
    # Find the nearest power of 2 that is greater than or equal to alphabet_len
    # mask = (2 ^ x) - 1 where 2 ^ x >= alphabet_len
    mask = (2 << int(math.log(alphabet_len - 1) / math.log(2))) - 1
    
    # Estimate the buffer size needed to generate enough characters in a single batch
    step = int(math.ceil(1.6 * mask * size / alphabet_len))
    
    id_chars = []
    while True:
        random_bytes = secrets.token_bytes(step)
        for byte in random_bytes:
            byte_masked = byte & mask
            if byte_masked < alphabet_len:
                id_chars.append(alphabet[byte_masked])
                if len(id_chars) == size:
                    return "".join(id_chars)

def calculate_collision_info(alphabet_len, size, target_prob=0.01):
    """
    Calculate the number of IDs needed to reach a target collision probability.
    Using approximation of Birthday Problem:
    p = 1 - exp(-n^2 / (2 * N)) where N = alphabet_len ^ size
    Solving for n:
    n = sqrt(-2 * N * ln(1 - p))
    """
    N = alphabet_len ** size
    try:
        n = math.sqrt(-2 * N * math.log(1 - target_prob))
        return n
    except OverflowError:
        # If N is too large, return infinity or float('inf')
        return float('inf')

def format_large_number(num):
    """Format large numbers in a human-readable format (thousands, millions, billions, etc.)"""
    if num == float('inf'):
        return "Virtually Infinite (beyond standard limits)"
    
    if num < 1000:
        return f"{num:.0f}"
    
    units = ["", "Thousand", "Million", "Billion", "Trillion", "Quadrillion", "Quintillion", "Sextillion", "Septillion"]
    power = 0
    while num >= 1000 and power < len(units) - 1:
        num /= 1000.0
        power += 1
        
    return f"{num:.2f} {units[power]}"

def main():
    parser = argparse.ArgumentParser(description="NanoID Generator - Generate secure, URL-friendly unique IDs")
    
    parser.add_argument("-n", "--count", type=int, default=1, help="Number of IDs to generate")
    parser.add_argument("-s", "--size", type=int, default=21, help="Length of the generated IDs (default: 21)")
    parser.add_argument("-a", "--alphabet", type=str, default=DEFAULT_ALPHABET, 
                        help="Custom alphabet to use (default: standard url-friendly A-Za-z0-9_-)")
    parser.add_argument("-e", "--estimate", action="store_true", 
                        help="Show safety and collision statistics for the given alphabet and size instead of generating IDs")
    parser.add_argument("-p", "--probability", type=float, default=0.01,
                        help="Target collision probability for estimation (default: 0.01 / 1%%)")

    args = parser.parse_args()

    # Check alphabet duplicates
    unique_alphabet = "".join(sorted(list(set(args.alphabet))))
    if len(unique_alphabet) != len(args.alphabet):
        # Clean duplicates but preserve order if possible, or warn user
        cleaned = []
        for char in args.alphabet:
            if char not in cleaned:
                cleaned.append(char)
        args.alphabet = "".join(cleaned)

    if args.estimate:
        alphabet_len = len(args.alphabet)
        size = args.size
        prob = args.probability
        
        if prob <= 0 or prob >= 1:
            print("Error: Probability must be between 0 and 1 (exclusive).", file=sys.stderr)
            sys.exit(1)

        print("====================================================")
        print("                 NANOID SAFETY REPORT               ")
        print("====================================================")
        print(f"Alphabet Size: {alphabet_len} characters")
        print(f"ID Length:     {size} characters")
        print(f"Total Space:   {alphabet_len}^{size} ({format_large_number(alphabet_len ** size)} combinations)")
        print(f"Target Risk:   {prob * 100:.2f}% chance of at least one collision")
        
        n = calculate_collision_info(alphabet_len, size, prob)
        print(f"Required IDs:  {format_large_number(n)}")
        print("----------------------------------------------------")
        
        # Calculate time estimations at different generation rates
        if n != float('inf'):
            rates = [
                ("1,000 / sec", n / 1000),
                ("10,000 / sec", n / 10000),
                ("100,000 / sec", n / 100000),
                ("1,000,000 / sec", n / 1000000)
            ]
            print("Time to reach risk threshold:")
            for rate_name, secs in rates:
                # Convert seconds to days/years
                if secs < 60:
                    time_str = f"{secs:.2f} seconds"
                elif secs < 3600:
                    time_str = f"{secs / 60.0:.2f} minutes"
                elif secs < 86400:
                    time_str = f"{secs / 3600.0:.2f} hours"
                elif secs < 31536000:
                    time_str = f"{secs / 86400.0:.2f} days"
                else:
                    time_str = f"{secs / 31536000.0:.2f} years"
                print(f"  At {rate_name:15}: {time_str}")
        else:
            print("Time to reach risk threshold: Virtually infinite (billions of years at 1M/sec)")
        print("====================================================")
        return

    # Generate IDs
    try:
        for _ in range(args.count):
            print(generate_nanoid(args.alphabet, args.size))
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
