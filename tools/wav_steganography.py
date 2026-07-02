#!/usr/bin/env python3
"""
PCM WAV Audio Steganography Tool

Hides and extracts secret text messages or files within standard PCM WAV carrier audio.
Modifies the Least Significant Bit (LSB) of audio samples to insert payload bits, 
ensuring minimal, virtually inaudible audio distortion. 
Supports password-based SHA-256 XOR encryption.
"""

import argparse
import hashlib
import os
import sys
import wave
from typing import Tuple, Optional

# ANSI Colors
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"

MAGIC_SIGNATURE = b"WAV_STEGO_V1"

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

# --- Encryption ---

def xor_crypt(data: bytes, password: str) -> bytes:
    """XOR encryption/decryption using repeated SHA-256 hashing as key stream generator."""
    if not password:
        return data
        
    key = hashlib.sha256(password.encode('utf-8')).digest()
    result = bytearray()
    
    block_index = 0
    current_key = key
    
    for i, byte in enumerate(data):
        key_offset = i % 32
        if key_offset == 0 and i > 0:
            block_index += 1
            current_key = hashlib.sha256(current_key + str(block_index).encode()).digest()
            
        result.append(byte ^ current_key[key_offset])
        
    return bytes(result)

# --- Audio Manipulation Helpers ---

def bytes_to_bits(data: bytes) -> list:
    """Converts a byte array into a list of bits (0s and 1s)."""
    bits = []
    for byte in data:
        for i in range(8):
            bits.append((byte >> (7 - i)) & 1)
    return bits

def bits_to_bytes(bits: list) -> bytes:
    """Converts a list of bits (0s and 1s) into a byte array."""
    data = bytearray()
    # Ensure bits count is multiple of 8
    limit = (len(bits) // 8) * 8
    for i in range(0, limit, 8):
        byte = 0
        for j in range(8):
            byte = (byte << 1) | bits[i + j]
        data.append(byte)
    return bytes(data)

def hide_payload_in_wav(carrier_path: str, output_path: str, payload_bytes: bytes, is_file: bool, filename: str, password: str = ""):
    """Hides payload inside a carrier WAV file using LSB steganography."""
    # 1. Open carrier
    try:
        wav_in = wave.open(carrier_path, 'rb')
    except Exception as e:
        log_error(f"Failed to read WAV carrier: {e}")
        sys.exit(1)
        
    params = wav_in.getparams()
    num_channels = params.nchannels
    sample_width = params.sampwidth  # bytes per sample (e.g. 1 for 8-bit, 2 for 16-bit)
    num_frames = params.nframes
    
    if sample_width not in [1, 2]:
        log_error(f"Unsupported sample width ({sample_width * 8}-bit). Only 8-bit or 16-bit PCM WAV formats are supported.")
        wav_in.close()
        sys.exit(1)
        
    raw_frames = bytearray(wav_in.readframes(num_frames))
    wav_in.close()
    
    total_samples = num_frames * num_channels
    max_payload_bytes = total_samples // 8
    
    # 2. Build and encrypt payload
    filename_bytes = filename.encode('utf-8') if filename else b""
    header = bytearray(MAGIC_SIGNATURE)
    header.extend(len(payload_bytes).to_bytes(4, byteorder='big'))
    header.append(1 if is_file else 0)
    header.append(len(filename_bytes))
    header.extend(filename_bytes)
    
    full_payload = bytes(header) + payload_bytes
    if password:
        # Encrypt everything after the MAGIC_SIGNATURE and header length metadata
        metadata_len = len(MAGIC_SIGNATURE) + 6 + len(filename_bytes)
        encrypted_part = xor_crypt(full_payload[metadata_len:], password)
        full_payload = full_payload[:metadata_len] + encrypted_part
        
    payload_bits = bytes_to_bits(full_payload)
    required_samples = len(payload_bits)
    
    log_info(f"Carrier capacity: {max_payload_bytes} bytes ({total_samples} samples)")
    log_info(f"Required space  : {len(full_payload)} bytes ({required_samples} samples)")
    
    if required_samples > total_samples:
        log_error(f"Carrier WAV is too small to hold the payload. Requires {required_samples} samples, but only has {total_samples}.")
        sys.exit(1)
        
    # 3. Embed bits in LSB of low bytes of samples
    # If 8-bit, each byte is a sample.
    # If 16-bit, samples are 2 bytes (little endian), so low byte is at 2 * idx.
    step = sample_width
    for idx, bit in enumerate(payload_bits):
        byte_offset = idx * step
        raw_frames[byte_offset] = (raw_frames[byte_offset] & ~1) | bit
        
    # 4. Write output file
    try:
        wav_out = wave.open(output_path, 'wb')
        wav_out.setparams(params)
        wav_out.writeframes(raw_frames)
        wav_out.close()
        log_success(f"Successfully hid payload in stego audio file: {output_path}")
    except Exception as e:
        log_error(f"Failed to write stego WAV file: {e}")
        sys.exit(1)

def reveal_payload_from_wav(stego_path: str, password: str = "") -> Tuple[bytes, bool, str]:
    """Extracts steganographic payload from a stego WAV file."""
    try:
        wav = wave.open(stego_path, 'rb')
    except Exception as e:
        log_error(f"Failed to read stego WAV: {e}")
        sys.exit(1)
        
    params = wav.getparams()
    sample_width = params.sampwidth
    num_frames = params.nframes
    num_channels = params.nchannels
    
    if sample_width not in [1, 2]:
        log_error(f"Unsupported sample width ({sample_width * 8}-bit). Only 8-bit or 16-bit PCM WAV formats are supported.")
        wav.close()
        sys.exit(1)
        
    raw_frames = wav.readframes(num_frames)
    wav.close()
    
    total_samples = num_frames * num_channels
    
    # 1. Extract bits from low bytes
    bits = []
    step = sample_width
    for i in range(total_samples):
        byte_offset = i * step
        bits.append(raw_frames[byte_offset] & 1)
        
    # Convert bits back to bytes
    extracted_bytes = bits_to_bytes(bits)
    
    # 2. Parse Header
    if not extracted_bytes.startswith(MAGIC_SIGNATURE):
        raise ValueError("No steganography payload or invalid signature found in this WAV file.")
        
    idx = len(MAGIC_SIGNATURE)
    payload_len = int.from_bytes(extracted_bytes[idx : idx + 4], byteorder='big')
    idx += 4
    
    is_file = extracted_bytes[idx] == 1
    idx += 1
    
    filename_len = extracted_bytes[idx]
    idx += 1
    
    filename = extracted_bytes[idx : idx + filename_len].decode('utf-8', errors='ignore')
    idx += filename_len
    
    # Total header length
    header_len = idx
    total_required = header_len + payload_len
    
    if total_required > len(extracted_bytes):
        raise ValueError("Corrupted steganography metadata or truncated payload.")
        
    payload = extracted_bytes[header_len : total_required]
    
    # 3. Decrypt
    if password:
        payload = xor_crypt(payload, password)
        
    return payload, is_file, filename

# --- CLI Interface ---

def main():
    parser = argparse.ArgumentParser(
        description="PCM WAV Audio Steganography Utility"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Hide parser
    hide_parser = subparsers.add_parser("hide", help="Hide text or file inside WAV carrier")
    hide_parser.add_argument("-c", "--carrier", required=True, help="Input carrier WAV file path")
    hide_parser.add_argument("-o", "--output", required=True, help="Output stego WAV file path")
    hide_parser.add_argument("-s", "--secret", help="Secret text message to hide")
    hide_parser.add_argument("-f", "--file", help="Secret file to hide")
    hide_parser.add_argument("-p", "--password", default="", help="Password for encryption")
    
    # Reveal parser
    reveal_parser = subparsers.add_parser("reveal", help="Reveal hidden payload from stego WAV")
    reveal_parser.add_argument("-s", "--stego", required=True, help="Stego WAV file path")
    reveal_parser.add_argument("-o", "--output", help="Directory or file path to write extracted payload")
    reveal_parser.add_argument("-p", "--password", default="", help="Password for decryption")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
        
    if args.command == "hide":
        payload_bytes = None
        is_file = False
        filename = ""
        
        if args.secret:
            payload_bytes = args.secret.encode('utf-8')
        elif args.file:
            if not os.path.exists(args.file):
                log_error(f"Secret file not found: {args.file}")
                sys.exit(1)
            with open(args.file, 'rb') as f:
                payload_bytes = f.read()
            is_file = True
            filename = os.path.basename(args.file)
        else:
            log_error("Must specify either --secret or --file to hide.")
            sys.exit(1)
            
        log_info(f"Hiding payload in '{args.carrier}'...")
        hide_payload_in_wav(
            carrier_path=args.carrier,
            output_path=args.output,
            payload_bytes=payload_bytes,
            is_file=is_file,
            filename=filename,
            password=args.password
        )
        
    elif args.command == "reveal":
        log_info(f"Extracting payload from '{args.stego}'...")
        try:
            payload, is_file, filename = reveal_payload_from_wav(args.stego, args.password)
            
            if is_file:
                out_path = args.output if args.output else "."
                if os.path.isdir(out_path):
                    out_path = os.path.join(out_path, filename)
                with open(out_path, 'wb') as f:
                    f.write(payload)
                log_success(f"Extracted file saved to: {out_path}")
            else:
                try:
                    text_msg = payload.decode('utf-8')
                    print("\n" + color_text("--- REVEALED SECRET ---", COLOR_BOLD))
                    print(text_msg)
                    print(color_text("-----------------------", COLOR_BOLD))
                except UnicodeDecodeError:
                    log_warning("Payload is not UTF-8 text. Hex representation:")
                    print(payload.hex())
        except Exception as e:
            log_error(f"Failed to extract payload: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
