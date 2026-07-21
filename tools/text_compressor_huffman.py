#!/usr/bin/env python3
"""
Huffman Coding Text Compressor & Decompressor

A tool that implements the Huffman Coding algorithm from scratch. It compiles
character frequency trees, encodes input text into a custom binary format (.huff),
and decodes files back to their exact original representation. Shows detailed
statistics, code tables, and compression ratios.

Usage:
    python tools/text_compressor_huffman.py -c -i sample.txt -o compressed.huff
    python tools/text_compressor_huffman.py -d -i compressed.huff -o restored.txt
    python tools/text_compressor_huffman.py -c -i sample.txt --show-codes
"""

import os
import sys
import heapq
import struct
import json
import argparse
from typing import Dict, Any, Tuple, Optional

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
    return bool(supported_platform or is_a_tty)

def color_text(text: str, color_code: str) -> str:
    """Wraps text in color codes if supported."""
    return f"{color_code}{text}{COLOR_RESET}" if supports_color() else text

class HuffmanNode:
    """Node of the Huffman tree."""
    def __init__(self, char: Optional[str], freq: int):
        self.char = char
        self.freq = freq
        self.left: Optional[HuffmanNode] = None
        self.right: Optional[HuffmanNode] = None

    # Implement comparison operators for priority queue (heapq)
    def __lt__(self, other: 'HuffmanNode') -> bool:
        return self.freq < other.freq

    def __eq__(self, other: Any) -> bool:
        if not isinstance(other, HuffmanNode):
            return False
        return self.freq == other.freq

def build_frequency_dict(text: str) -> Dict[str, int]:
    """Calculates character frequencies."""
    freq = {}
    for char in text:
        freq[char] = freq.get(char, 0) + 1
    return freq

def build_huffman_tree(freq_dict: Dict[str, int]) -> Optional[HuffmanNode]:
    """Builds the Huffman tree using a priority queue (min-heap)."""
    heap = []
    for char, freq in freq_dict.items():
        node = HuffmanNode(char, freq)
        heapq.heappush(heap, node)

    if not heap:
        return None

    # Handle single character edge case
    if len(heap) == 1:
        root = HuffmanNode(None, heap[0].freq)
        root.left = heapq.heappop(heap)
        return root

    while len(heap) > 1:
        node1 = heapq.heappop(heap)
        node2 = heapq.heappop(heap)

        merged = HuffmanNode(None, node1.freq + node2.freq)
        merged.left = node1
        merged.right = node2

        heapq.heappush(heap, merged)

    return heap[0]

def build_codes_helper(node: Optional[HuffmanNode], current_code: str, codes: Dict[str, str]):
    """Recursively walks the Huffman tree to build prefix codes."""
    if not node:
        return

    # If leaf node
    if node.char is not None:
        codes[node.char] = current_code
        return

    build_codes_helper(node.left, current_code + "0", codes)
    build_codes_helper(node.right, current_code + "1", codes)

def get_huffman_codes(root: Optional[HuffmanNode]) -> Dict[str, str]:
    """Retrieves huffman codes from the tree."""
    codes = {}
    build_codes_helper(root, "", codes)
    return codes

def pack_bits_to_bytes(bit_string: str) -> Tuple[bytes, int]:
    """Packs a string of '0' and '1' characters into actual bytes, returning (packed_bytes, pad_count)."""
    pad_count = (8 - len(bit_string) % 8) % 8
    bit_string += "0" * pad_count # Pad with zeros at the end to make it multiple of 8
    
    byte_list = []
    for i in range(0, len(bit_string), 8):
        byte_val = int(bit_string[i:i+8], 2)
        byte_list.append(byte_val)
        
    return bytes(byte_list), pad_count

def unpack_bytes_to_bits(packed_bytes: bytes, pad_count: int) -> str:
    """Unpacks bytes back into a bit string of '0' and '1's, removing padding."""
    bit_parts = []
    for b in packed_bytes:
        bit_parts.append(f"{b:08b}")
        
    full_string = "".join(bit_parts)
    if pad_count > 0:
        full_string = full_string[:-pad_count]
    return full_string

def compress_text(input_text: str) -> Tuple[bytes, Dict[str, int]]:
    """Compresses input text and returns the raw packed byte stream and frequency map."""
    if not input_text:
        return b'', {}
        
    freq = build_frequency_dict(input_text)
    root = build_huffman_tree(freq)
    codes = get_huffman_codes(root)
    
    # Generate bitstream
    bit_string = "".join(codes[char] for char in input_text)
    
    packed_bytes, pad_count = pack_bits_to_bytes(bit_string)
    
    # We return packed bytes with pad count prepended as a single byte
    final_payload = bytes([pad_count]) + packed_bytes
    return final_payload, freq

def decompress_text(payload: bytes, freq_dict: Dict[str, int]) -> str:
    """Decompresses binary payload back into text using the frequency map."""
    if not payload or not freq_dict:
        return ""
        
    pad_count = payload[0]
    packed_bytes = payload[1:]
    
    bit_string = unpack_bytes_to_bits(packed_bytes, pad_count)
    
    # Rebuild Huffman tree
    root = build_huffman_tree(freq_dict)
    
    # Decode bits using the tree
    decoded_chars = []
    current_node = root
    
    for bit in bit_string:
        if bit == '0':
            current_node = current_node.left if current_node else None
        else:
            current_node = current_node.right if current_node else None
            
        if current_node and current_node.char is not None:
            decoded_chars.append(current_node.char)
            current_node = root
            
    return "".join(decoded_chars)

# Custom Huffman File Structure (.huff):
# 4 bytes: Magic string (b'HUFF')
# 4 bytes: Frequency JSON length (uint32)
# N bytes: Frequency JSON string (UTF-8 encoded)
# M bytes: Compressed payload (pad count byte + packed bits)

def save_compressed_file(filepath: str, payload: bytes, freq: Dict[str, int]):
    """Saves compressed data and frequency dictionary into a .huff file."""
    # Convert frequency keys to JSON. Huffman trees might contain special control characters
    freq_json = json.dumps(freq).encode('utf-8')
    json_len = len(freq_json)
    
    with open(filepath, 'wb') as f:
        # Write magic signature
        f.write(b'HUFF')
        # Write json length
        f.write(struct.pack('>I', json_len))
        # Write json data
        f.write(freq_json)
        # Write compressed payload
        f.write(payload)

def read_compressed_file(filepath: str) -> Tuple[bytes, Dict[str, int]]:
    """Reads and parses a .huff file."""
    with open(filepath, 'rb') as f:
        magic = f.read(4)
        if magic != b'HUFF':
            raise ValueError("Invalid file format. Magic signature 'HUFF' missing.")
            
        json_len_bytes = f.read(4)
        json_len = struct.unpack('>I', json_len_bytes)[0]
        
        freq_json = f.read(json_len).decode('utf-8')
        freq = json.loads(freq_json)
        
        payload = f.read()
        
    return payload, freq

def main():
    parser = argparse.ArgumentParser(
        description="Huffman Coding Text Compression & Decompression Utility.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-c", "--compress", action="store_true", help="Compress a text file.")
    group.add_argument("-d", "--decompress", action="store_true", help="Decompress a .huff file.")
    
    parser.add_argument("-i", "--input", required=True, help="Path to the input file.")
    parser.add_argument("-o", "--output", required=True, help="Path to the output file.")
    parser.add_argument("--show-codes", action="store_true", help="Display Huffman codes dictionary.")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.input):
        print(color_text(f"Error: Input file '{args.input}' not found.", COLOR_RED), file=sys.stderr)
        return 1
        
    if args.compress:
        try:
            with open(args.input, 'r', encoding='utf-8', errors='replace') as f:
                input_text = f.read()
                
            orig_size = len(input_text.encode('utf-8'))
            if orig_size == 0:
                print(color_text("Error: Input file is empty. Nothing to compress.", COLOR_RED), file=sys.stderr)
                return 1
                
            payload, freq = compress_text(input_text)
            save_compressed_file(args.output, payload, freq)
            
            comp_size = os.path.getsize(args.output)
            saving = (1 - (comp_size / orig_size)) * 100.0 if orig_size > 0 else 0
            
            print(color_text("✓ Compression completed successfully.", COLOR_GREEN))
            print(f"  Original size:   {orig_size} bytes")
            print(f"  Compressed size: {comp_size} bytes")
            print(f"  Space savings:   {saving:.2f}%")
            
            if args.show_codes:
                root = build_huffman_tree(freq)
                codes = get_huffman_codes(root)
                print("-" * 50)
                print(color_text("Huffman Codes Map (Sorted by frequency):", COLOR_BOLD))
                sorted_freq = sorted(freq.items(), key=lambda x: x[1], reverse=True)
                for char, count in sorted_freq:
                    # Clean visualization of control chars
                    vis_char = char
                    if char == '\n':
                        vis_char = '\\n'
                    elif char == '\t':
                        vis_char = '\\t'
                    elif char == ' ':
                        vis_char = '[Space]'
                        
                    print(f"  {vis_char!r:10} | Freq: {count:5d} | Code: {codes[char]}")
                print("-" * 50)
                
        except Exception as e:
            print(color_text(f"Compression Failed: {str(e)}", COLOR_RED), file=sys.stderr)
            return 2
            
    elif args.decompress:
        try:
            payload, freq = read_compressed_file(args.input)
            restored_text = decompress_text(payload, freq)
            
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(restored_text)
                
            orig_size = os.path.getsize(args.input)
            rest_size = len(restored_text.encode('utf-8'))
            
            print(color_text("✓ Decompression completed successfully.", COLOR_GREEN))
            print(f"  Huffman archive size: {orig_size} bytes")
            print(f"  Restored file size:   {rest_size} bytes")
            print(f"  Output saved to:      {args.output}")
            
        except Exception as e:
            print(color_text(f"Decompression Failed: {str(e)}", COLOR_RED), file=sys.stderr)
            return 2
            
    return 0

if __name__ == "__main__":
    sys.exit(main())
