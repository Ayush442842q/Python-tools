#!/usr/bin/env python3
"""
zip_steganography - Conceal and Extract Hidden Payloads inside ZIP Archives

This tool embeds secret text messages or files inside standard ZIP archives
without corrupting them or affecting standard extraction tools.

Techniques supported:
1. Comment Mode: Stores data inside the ZIP file comment block (Max 65KB).
   Standard extraction tools will run normally but may display the comment.
2. Append Mode: Appends the payload directly after the End of Central Directory
   (EOCD) block (No size limit). Standard utilities ignore anything after EOCD.

Usage:
    python tools/zip_steganography.py embed -z <archive.zip> -m "secret text" [options]
    python tools/zip_steganography.py extract -z <archive.zip> [options]

Example:
    python tools/zip_steganography.py embed -z test.zip -m "Secret Key: 12345" --mode append
    python tools/zip_steganography.py extract -z test.zip --mode append
"""

import argparse
import os
import struct
import sys
import zipfile
from typing import Optional

# Custom signatures to identify hidden payloads
STEG_APPEND_SIG = b"ZIPSTEG\x01\x02"


def embed_comment(zip_path: str, payload: bytes) -> None:
    """Embed payload inside the ZIP archive's comment."""
    if len(payload) > 65535:
        raise ValueError("Payload size exceeds maximum ZIP comment length of 65,535 bytes.")
        
    if not zipfile.is_zipfile(zip_path):
        raise ValueError(f"File '{zip_path}' is not a valid ZIP archive.")

    print(f"[*] Embedding payload of {len(payload)} bytes in Comment Mode...")
    
    # Read zip data
    with open(zip_path, "rb") as f:
        data = f.read()

    # Find the EOCD (End of Central Directory)
    # EOCD signature is PK\x05\x06 (0x06054b50)
    eocd_index = data.rfind(b"\x50\x4b\x05\x06")
    if eocd_index == -1:
        raise ValueError("Could not find End of Central Directory (EOCD) signature.")

    # Write back the zip file with the modified comment in the EOCD
    # The EOCD record is structured as:
    # Offset 0: Signature (4 bytes)
    # Offset 4: Number of this disk (2 bytes)
    # Offset 6: Disk where central directory starts (2 bytes)
    # Offset 8: Number of central directory records on this disk (2 bytes)
    # Offset 10: Total number of central directory records (2 bytes)
    # Offset 12: Size of central directory (4 bytes)
    # Offset 16: Offset of start of central directory, relative to start of archive (4 bytes)
    # Offset 20: Comment length (2 bytes)
    # Offset 22: Comment (variable length)
    
    # We will slice everything up to Offset 20 of the EOCD
    header_part = data[:eocd_index + 20]
    
    # Pack the comment length
    comment_len_bytes = struct.pack("<H", len(payload))
    
    new_data = header_part + comment_len_bytes + payload
    
    with open(zip_path, "wb") as f:
        f.write(new_data)
        
    print("[+] Payload embedded successfully in Comment Mode.")


def extract_comment(zip_path: str) -> bytes:
    """Extract payload from the ZIP archive's comment."""
    if not zipfile.is_zipfile(zip_path):
        raise ValueError(f"File '{zip_path}' is not a valid ZIP archive.")
        
    with zipfile.ZipFile(zip_path, "r") as zf:
        comment = zf.comment
        
    return comment


def embed_append(zip_path: str, payload: bytes) -> None:
    """Embed payload by appending it after the EOCD record."""
    if not zipfile.is_zipfile(zip_path):
        raise ValueError(f"File '{zip_path}' is not a valid ZIP archive.")

    print(f"[*] Embedding payload of {len(payload)} bytes in Append Mode...")
    
    # Read the original zip file
    with open(zip_path, "rb") as f:
        data = f.read()

    # Find and clean any existing append payloads
    eocd_index = data.rfind(b"\x50\x4b\x05\x06")
    if eocd_index == -1:
        raise ValueError("Could not find End of Central Directory (EOCD) signature.")

    # Read comment length at EOCD offset 20
    comment_len = struct.unpack("<H", data[eocd_index + 20 : eocd_index + 22])[0]
    eocd_end = eocd_index + 22 + comment_len

    # Standard ZIP content ends at eocd_end. Slice off any existing append data.
    clean_zip = data[:eocd_end]

    # Package structure: [Clean ZIP] + [STEG_APPEND_SIG] + [Payload Length (4 bytes)] + [Payload]
    payload_len_bytes = struct.pack("<I", len(payload))
    steg_package = clean_zip + STEG_APPEND_SIG + payload_len_bytes + payload

    with open(zip_path, "wb") as f:
        f.write(steg_package)
        
    print("[+] Payload appended successfully after EOCD.")


def extract_append(zip_path: str) -> Optional[bytes]:
    """Scan and extract payload appended after the EOCD record."""
    with open(zip_path, "rb") as f:
        data = f.read()

    # Find EOCD
    eocd_index = data.rfind(b"\x50\x4b\x05\x06")
    if eocd_index == -1:
        raise ValueError("Could not find End of Central Directory (EOCD) signature.")

    # Locate our steg signature
    sig_index = data.rfind(STEG_APPEND_SIG)
    if sig_index == -1 or sig_index < eocd_index:
        return None

    # Read length from the 4 bytes following the signature
    len_offset = sig_index + len(STEG_APPEND_SIG)
    if len_offset + 4 > len(data):
        return None
        
    payload_len = struct.unpack("<I", data[len_offset : len_offset + 4])[0]
    payload_offset = len_offset + 4
    
    if payload_offset + payload_len > len(data):
        return None
        
    return data[payload_offset : payload_offset + payload_len]


def main() -> int:
    parser = argparse.ArgumentParser(
        description="ZIP Archive Steganography Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Embed subparser
    embed_parser = subparsers.add_parser("embed", help="Embed secret payload in ZIP archive")
    embed_parser.add_argument("-z", "--zip", required=True, help="Path to target ZIP file")
    embed_parser.add_argument("-m", "--message", help="Secret text message to hide")
    embed_parser.add_argument("-f", "--file", help="Path to secret file to hide")
    embed_parser.add_argument("--mode", default="comment", choices=["comment", "append"], help="Steganography mode")
    
    # Extract subparser
    extract_parser = subparsers.add_parser("extract", help="Extract secret payload from ZIP archive")
    extract_parser.add_argument("-z", "--zip", required=True, help="Path to target ZIP file")
    extract_parser.add_argument("-o", "--output", help="Path to write the extracted payload (if it was a file)")
    extract_parser.add_argument("--mode", default="comment", choices=["comment", "append"], help="Steganography mode")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "embed":
        # Resolve payload bytes
        if args.message:
            payload = args.message.encode("utf-8")
        elif args.file:
            if not os.path.exists(args.file):
                print(f"[!] Error: Secret file '{args.file}' not found.", file=sys.stderr)
                return 1
            with open(args.file, "rb") as sf:
                payload = sf.read()
        else:
            print("[!] Error: Either --message or --file must be specified to embed data.", file=sys.stderr)
            return 1

        try:
            if args.mode == "comment":
                embed_comment(args.zip, payload)
            else:
                embed_append(args.zip, payload)
            return 0
        except Exception as e:
            print(f"[!] Embedding failed: {e}", file=sys.stderr)
            return 1

    elif args.command == "extract":
        try:
            payload = None
            if args.mode == "comment":
                payload = extract_comment(args.zip)
            else:
                payload = extract_append(args.zip)

            if not payload:
                print("[-] No hidden payload found matching specified mode.")
                return 0

            # Output results
            if args.output:
                with open(args.output, "wb") as of:
                    of.write(payload)
                print(f"[+] Extracted payload saved to: {args.output}")
            else:
                try:
                    text = payload.decode("utf-8")
                    print("[+] Extracted Message:")
                    print(text)
                except UnicodeDecodeError:
                    print(f"[+] Extracted binary payload ({len(payload)} bytes). Use -o/--output option to save it to a file.")
            return 0
        except Exception as e:
            print(f"[!] Extraction failed: {e}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
