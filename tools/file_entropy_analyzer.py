#!/usr/bin/env python3
"""
File Entropy Analyzer

Calculates the Shannon entropy of a file or its chunks to detect encryption,
compression, or hidden payloads (steganography, packing).

Shannon entropy ranges from 0.0 (fully structured/uniform data) to 8.0
(fully random/uniformly distributed bytes, typical of encryption/compression).

Usage:
    python tools/file_entropy_analyzer.py path/to/file [options]
"""

import argparse
import math
import os
import sys

def calculate_entropy(data):
    """Calculate Shannon entropy of a byte string."""
    if not data:
        return 0.0
    
    # Count frequency of each byte value (0-255)
    frequencies = [0] * 256
    for byte in data:
        frequencies[byte] += 1
        
    # Calculate Shannon entropy
    entropy = 0.0
    total_len = len(data)
    for count in frequencies:
        if count > 0:
            p = count / total_len
            entropy -= p * math.log2(p)
            
    return entropy

def get_entropy_color_bar(val):
    """Return visual block character based on entropy range."""
    # Scale:
    # 0-4: Low, 4-6: Mid, 6-7.5: High, 7.5+: Extremely High (likely encrypted/compressed)
    if val < 4.0:
        return "░"
    elif val < 6.0:
        return "▒"
    elif val < 7.5:
        return "▓"
    else:
        return "█"

def analyze_file(filepath, chunk_size=None, num_blocks=40):
    """Analyze file entropy globally and block-by-block."""
    if not os.path.isfile(filepath):
        print(f"Error: File '{filepath}' does not exist.", file=sys.stderr)
        return None

    file_size = os.path.getsize(filepath)
    if file_size == 0:
        print("Error: File is empty.", file=sys.stderr)
        return {
            "global_entropy": 0.0,
            "file_size": 0,
            "blocks": []
        }

    # Determine chunk size if not specified
    if chunk_size is None:
        chunk_size = max(1024, file_size // num_blocks)

    global_data = bytearray()
    blocks = []
    
    with open(filepath, "rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            global_data.extend(chunk)
            block_entropy = calculate_entropy(chunk)
            blocks.append({
                "offset": f.tell() - len(chunk),
                "size": len(chunk),
                "entropy": block_entropy
            })

    global_entropy = calculate_entropy(global_data)
    
    return {
        "global_entropy": global_entropy,
        "file_size": file_size,
        "blocks": blocks,
        "chunk_size": chunk_size
    }

def print_report(filepath, result, show_blocks=False):
    """Print a clean visual report of the file entropy analysis."""
    print("=" * 60)
    print(f" FILE ENTROPY REPORT: {os.path.basename(filepath)}")
    print("=" * 60)
    print(f"File Path:    {filepath}")
    print(f"File Size:    {result['file_size']} bytes")
    print(f"Global Entropy: {result['global_entropy']:.4f} / 8.0000")
    
    # Determine likely state of the data
    entropy = result['global_entropy']
    if entropy > 7.9:
        status = "Highly Random / Fully Encrypted / Compressed"
    elif entropy > 7.5:
        status = "Likely Encrypted, Compressed, or Packed Binary"
    elif entropy > 6.0:
        status = "Medium-High Randomness (compiled executable / dense data)"
    elif entropy > 4.0:
        status = "Medium Randomness (structured text, source code, sparse markup)"
    else:
        status = "Low Randomness (highly repetitive, empty space, basic text)"
        
    print(f"Interpretation: {status}")
    print("-" * 60)
    
    blocks = result['blocks']
    if not blocks:
        return
        
    # Render visual map
    print("Entropy Distribution Map:")
    map_str = ""
    for block in blocks:
        map_str += get_entropy_color_bar(block['entropy'])
    print(f"[{map_str}]")
    print("Legend: [░] Low (0-4)  [▒] Structured (4-6)  [▓] Dense (6-7.5)  [█] Encrypted/Compressed (7.5+)")
    print("-" * 60)

    # Print summary statistics
    entropies = [b['entropy'] for b in blocks]
    max_e = max(entropies)
    min_e = min(entropies)
    avg_e = sum(entropies) / len(entropies)
    
    print(f"Block Count:  {len(blocks)} (Size: {result['chunk_size']} bytes per block)")
    print(f"Min Block Entropy:  {min_e:.4f}")
    print(f"Max Block Entropy:  {max_e:.4f}")
    print(f"Average Block Entropy: {avg_e:.4f}")
    
    if show_blocks:
        print("-" * 60)
        print(f"{'Block Offset':<14} | {'Size (Bytes)':<12} | {'Entropy':<8} | {'Intensity'}")
        print("-" * 60)
        for i, block in enumerate(blocks):
            bar = "█" * int(block['entropy'] * 2)
            print(f"0x{block['offset']:08X}     | {block['size']:<12} | {block['entropy']:<8.4f} | {bar}")

def main():
    parser = argparse.ArgumentParser(description="Shannon Entropy File Analyzer")
    parser.add_argument("file", help="Path to the file to analyze")
    parser.add_argument("-c", "--chunk-size", type=int, default=None,
                        help="Size of blocks/chunks in bytes (default: autoscale based on file size)")
    parser.add_argument("-b", "--blocks", type=int, default=40,
                        help="Number of blocks to split the file into for visualization (default: 40)")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="Print detailed block table with offset and entropy details")
                        
    args = parser.parse_args()
    
    try:
        res = analyze_file(args.file, chunk_size=args.chunk_size, num_blocks=args.blocks)
        if res:
            print_report(args.file, res, show_blocks=args.verbose)
            return 0
    except Exception as e:
        print(f"Error during analysis: {e}", file=sys.stderr)
        
    return 1

if __name__ == "__main__":
    sys.exit(main())
