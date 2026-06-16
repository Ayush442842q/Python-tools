#!/usr/bin/env python3
"""
Steganography Tool

Hide and extract secret text messages or files within carrier files (images or text).
Supports:
1. Image EOF Steganography (JPEG, PNG, GIF) - Appends payload securely after the file's natural EOF marker.
2. Text Zero-Width Character Steganography (ZWC) - Hides invisible text inside ordinary text documents.
3. Password encryption - Uses a SHA-256 key-based XOR stream cipher to encrypt hidden data.

Usage:
    python tools/steganography_tool.py hide -c input.jpg -s "My secret message" -o output.jpg -p mypassword
    python tools/steganography_tool.py reveal -c output.jpg -p mypassword
"""

import argparse
import hashlib
import os
import sys
from typing import Tuple, Optional

# ANSI Colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"

# Magic signatures
MAGIC_SIG_IMAGE = b"STEGO_IMG_V1"
MAGIC_SIG_TEXT_START = "\u200d\u200e\u200d"  # ZWJ + LTR + ZWJ as start marker
MAGIC_SIG_TEXT_END = "\u200d\u200f\u200d"    # ZWJ + RTL + ZWJ as end marker

# Zero-width mappings
ZWC_0 = "\u200b"  # Zero-width space
ZWC_1 = "\u200c"  # Zero-width non-joiner

# Image EOF Markers
EOF_MARKERS = {
    b".jpg": b"\xff\xd9",
    b".jpeg": b"\xff\xd9",
    b".png": b"\x49\x45\x4e\x44\xae\x42\x60\x82",
    b".gif": b"\x00\x3b"
}

def supports_color() -> bool:
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform or is_a_tty

def color_text(text: str, color_code: str) -> str:
    return f"{color_code}{text}{COLOR_RESET}" if supports_color() else text

def log_success(msg: str):
    print(color_text("[+] " + msg, COLOR_GREEN))

def log_info(msg: str):
    print(color_text("[*] " + msg, COLOR_CYAN))

def log_warning(msg: str):
    print(color_text("[!] " + msg, COLOR_YELLOW))

def log_error(msg: str):
    print(color_text("[-] ERROR: " + msg, COLOR_RED), file=sys.stderr)

def xor_crypt(data: bytes, password: str) -> bytes:
    """XOR encryption/decryption using repeated SHA-256 hashing as key stream generator."""
    if not password:
        return data
        
    key = hashlib.sha256(password.encode('utf-8')).digest()
    result = bytearray()
    
    # Simple keystream generator based on key hashing chain
    block_index = 0
    current_key = key
    
    for i, byte in enumerate(data):
        key_offset = i % 32
        if key_offset == 0 and i > 0:
            block_index += 1
            # Chain the hash for next 32 bytes
            current_key = hashlib.sha256(current_key + str(block_index).encode()).digest()
            
        result.append(byte ^ current_key[key_offset])
        
    return bytes(result)

# --- Text ZWC Steganography ---

def text_to_zwc(text_data: str) -> str:
    """Converts a string of text into a sequence of zero-width unicode characters."""
    binary_str = ''.join(format(b, '08b') for b in text_data.encode('utf-8'))
    zwc_list = []
    for char in binary_str:
        if char == '0':
            zwc_list.append(ZWC_0)
        else:
            zwc_list.append(ZWC_1)
    return MAGIC_SIG_TEXT_START + "".join(zwc_list) + MAGIC_SIG_TEXT_END

def zwc_to_text(zwc_str: str) -> Optional[str]:
    """Converts a sequence of zero-width unicode characters back into readable text."""
    if MAGIC_SIG_TEXT_START not in zwc_str or MAGIC_SIG_TEXT_END not in zwc_str:
        return None
        
    # Extract only the payload between signatures
    start_idx = zwc_str.find(MAGIC_SIG_TEXT_START) + len(MAGIC_SIG_TEXT_START)
    end_idx = zwc_str.find(MAGIC_SIG_TEXT_END, start_idx)
    payload_zwc = zwc_str[start_idx:end_idx]
    
    binary_chars = []
    for char in payload_zwc:
        if char == ZWC_0:
            binary_chars.append('0')
        elif char == ZWC_1:
            binary_chars.append('1')
            
    binary_str = "".join(binary_chars)
    if len(binary_str) % 8 != 0:
        log_warning("Extracted binary length is not a multiple of 8. The message might be corrupted.")
        # Truncate to multiple of 8
        binary_str = binary_str[:(len(binary_str) // 8) * 8]
        
    if not binary_str:
        return ""
        
    byte_list = []
    for i in range(0, len(binary_str), 8):
        byte_list.append(int(binary_str[i:i+8], 2))
        
    try:
        return bytes(byte_list).decode('utf-8')
    except UnicodeDecodeError:
        log_error("Failed to decode extracted bytes to UTF-8. Wrong password or corrupted file?")
        return None

def hide_in_text(carrier_path: str, secret_bytes: bytes, output_path: str) -> bool:
    """Hides the secret payload in a text file using Zero-Width characters."""
    try:
        with open(carrier_path, 'r', encoding='utf-8') as f:
            carrier_text = f.read()
            
        # Convert secret bytes to hexadecimal string to avoid byte boundary issues in string decoding
        secret_hex = secret_bytes.hex()
        zwc_hidden = text_to_zwc(secret_hex)
        
        # Insert ZWC payload after the first line (or at the end if single line)
        lines = carrier_text.splitlines(keepends=True)
        if lines:
            lines[0] = lines[0].rstrip('\r\n') + zwc_hidden + ('\n' if lines[0].endswith('\n') else '')
            output_text = "".join(lines)
        else:
            output_text = zwc_hidden
            
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(output_text)
            
        return True
    except Exception as e:
        log_error(f"Text hiding failed: {e}")
        return False

def reveal_from_text(carrier_path: str) -> Optional[bytes]:
    """Reveals the secret payload hidden in a text file using Zero-Width characters."""
    try:
        with open(carrier_path, 'r', encoding='utf-8') as f:
            stego_text = f.read()
            
        secret_hex = zwc_to_text(stego_text)
        if secret_hex is None:
            return None
            
        return bytes.fromhex(secret_hex)
    except Exception as e:
        log_error(f"Text extraction failed: {e}")
        return None

# --- Image EOF Steganography ---

def get_eof_marker(file_path: str) -> Optional[bytes]:
    """Gets the standard EOF marker based on file extension."""
    ext = os.path.splitext(file_path.lower())[1].encode('utf-8')
    return EOF_MARKERS.get(ext)

def hide_in_image(carrier_path: str, secret_bytes: bytes, output_path: str) -> bool:
    """Hides the secret bytes in an image by appending them after the EOF marker."""
    try:
        with open(carrier_path, 'rb') as f:
            image_data = f.read()
            
        eof_marker = get_eof_marker(carrier_path)
        
        if eof_marker is None:
            log_warning("Unknown file extension. Appending payload to the absolute end of the file.")
            split_index = len(image_data)
        else:
            # Find the last occurrence of the EOF marker
            split_index = image_data.rfind(eof_marker)
            if split_index == -1:
                log_warning("EOF marker not found in image. Appending to the absolute end.")
                split_index = len(image_data)
            else:
                split_index += len(eof_marker)
                
        # Construct the payload structure:
        # Carrier header + EOF marker + [MAGIC_SIG] + [PAYLOAD_LENGTH (4 bytes)] + [PAYLOAD]
        payload_len = len(secret_bytes).to_bytes(4, byteorder='big')
        stego_payload = MAGIC_SIG_IMAGE + payload_len + secret_bytes
        
        output_data = image_data[:split_index] + stego_payload + image_data[split_index:]
        
        with open(output_path, 'wb') as f:
            f.write(output_data)
            
        return True
    except Exception as e:
        log_error(f"Image hiding failed: {e}")
        return False

def reveal_from_image(stego_path: str) -> Optional[bytes]:
    """Extracts the secret bytes appended after the image EOF marker."""
    try:
        with open(stego_path, 'rb') as f:
            stego_data = f.read()
            
        # Scan for magic signature
        sig_index = stego_data.rfind(MAGIC_SIG_IMAGE)
        if sig_index == -1:
            log_error("No steganographic signature found in this image.")
            return None
            
        len_start = sig_index + len(MAGIC_SIG_IMAGE)
        if len_start + 4 > len(stego_data):
            log_error("Corrupted stego data: length header missing.")
            return None
            
        payload_len = int.from_bytes(stego_data[len_start:len_start+4], byteorder='big')
        payload_start = len_start + 4
        payload_end = payload_start + payload_len
        
        if payload_end > len(stego_data):
            log_error(f"Corrupted stego data: declared payload length ({payload_len} bytes) exceeds file size.")
            return None
            
        return stego_data[payload_start:payload_end]
    except Exception as e:
        log_error(f"Image extraction failed: {e}")
        return None

# --- Main CLI ---

def main():
    parser = argparse.ArgumentParser(
        description="Steganography Tool: Hide & extract secrets inside images or text files.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", required=True, help="Command to run")
    
    # Hide Subparser
    hide_parser = subparsers.add_parser("hide", help="Hide a secret inside a carrier file")
    hide_parser.add_argument("-c", "--carrier", required=True, help="Path to the carrier file (image or text)")
    hide_parser.add_argument("-o", "--output", required=True, help="Path for the output stego file")
    
    secret_group = hide_parser.add_mutually_exclusive_group(required=True)
    secret_group.add_argument("-s", "--secret", help="Secret message string to hide")
    secret_group.add_argument("-f", "--secret-file", help="Path to a file containing secret data to hide")
    
    hide_parser.add_argument("-p", "--password", help="Optional password to encrypt the secret payload")
    hide_parser.add_argument("-m", "--mode", choices=["auto", "image-eof", "text-zwc"], default="auto",
                             help="Steganography mode (default: auto-detect by file extension)")
    
    # Reveal Subparser
    reveal_parser = subparsers.add_parser("reveal", help="Reveal a secret from a stego file")
    reveal_parser.add_argument("-c", "--carrier", required=True, help="Path to the stego file")
    reveal_parser.add_argument("-p", "--password", help="Optional password to decrypt the payload")
    reveal_parser.add_argument("-o", "--output-file", help="Save extracted secret as a file instead of displaying it")
    reveal_parser.add_argument("-m", "--mode", choices=["auto", "image-eof", "text-zwc"], default="auto",
                               help="Steganography mode (default: auto-detect)")

    args = parser.parse_args()
    
    if args.command == "hide":
        # Prepare secret bytes
        if args.secret:
            secret_bytes = args.secret.encode('utf-8')
            is_file_payload = False
        else:
            try:
                with open(args.secret_file, 'rb') as sf:
                    secret_bytes = sf.read()
                is_file_payload = True
            except Exception as e:
                log_error(f"Could not read secret file: {e}")
                sys.exit(1)
                
        # Auto-detect mode
        mode = args.mode
        if mode == "auto":
            ext = os.path.splitext(args.carrier.lower())[1]
            if ext in ['.txt', '.py', '.md', '.html', '.css', '.json', '.xml', '.ini', '.yaml']:
                mode = "text-zwc"
            elif ext in ['.jpg', '.jpeg', '.png', '.gif']:
                mode = "image-eof"
            else:
                log_warning("Unable to auto-detect mode from extension. Defaulting to 'image-eof'.")
                mode = "image-eof"
                
        # Optional encryption
        if args.password:
            log_info("Encrypting secret payload...")
            secret_bytes = xor_crypt(secret_bytes, args.password)
            
        # Hide based on mode
        success = False
        if mode == "text-zwc":
            log_info(f"Hiding secret using zero-width unicode characters in text...")
            success = hide_in_text(args.carrier, secret_bytes, args.output)
        elif mode == "image-eof":
            log_info(f"Hiding secret using EOF signature injection in image...")
            success = hide_in_image(args.carrier, secret_bytes, args.output)
            
        if success:
            log_success(f"Secret successfully hidden inside: {args.output}")
        else:
            log_error("Steganography hide operation failed.")
            sys.exit(1)
            
    elif args.command == "reveal":
        # Auto-detect mode
        mode = args.mode
        if mode == "auto":
            ext = os.path.splitext(args.carrier.lower())[1]
            if ext in ['.txt', '.py', '.md', '.html', '.css', '.json', '.xml', '.ini', '.yaml']:
                mode = "text-zwc"
            else:
                mode = "image-eof"
                
        # Reveal based on mode
        raw_payload = None
        if mode == "text-zwc":
            log_info("Extracting zero-width character payload from text...")
            raw_payload = reveal_from_text(args.carrier)
        elif mode == "image-eof":
            log_info("Extracting EOF signature payload from image...")
            raw_payload = reveal_from_image(args.carrier)
            
        if raw_payload is None:
            log_error("Could not find or extract any secret payload.")
            sys.exit(1)
            
        # Decrypt if password provided
        if args.password:
            log_info("Decrypting secret payload...")
            raw_payload = xor_crypt(raw_payload, args.password)
            
        # Output
        if args.output_file:
            try:
                with open(args.output_file, 'wb') as out_f:
                    out_f.write(raw_payload)
                log_success(f"Extracted payload saved to: {args.output_file}")
            except Exception as e:
                log_error(f"Failed to write extracted payload to file: {e}")
                sys.exit(1)
        else:
            # Try decoding as text, print as string. Fallback to hex if decoding fails
            try:
                decoded_str = raw_payload.decode('utf-8')
                log_success("Extracted Message:")
                print(color_text(decoded_str, COLOR_BOLD))
            except UnicodeDecodeError:
                log_warning("Payload is binary or could not be decoded as UTF-8 text.")
                log_success("Extracted Hex Representation:")
                print(raw_payload.hex())

if __name__ == "__main__":
    main()
