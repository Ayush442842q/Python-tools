#!/usr/bin/env python3
"""
File Signature Detector

Detects the actual type of a file by reading its magic bytes (file signature)
and compares it with its file extension to identify potential mismatches or
renamed malicious/hidden files.

Usage:
    python tools/file_signature_detector.py <file_or_directory_path>
    python tools/file_signature_detector.py file.png -v
    python tools/file_signature_detector.py . --recursive
    python tools/file_signature_detector.py document.pdf --json
"""

import os
import sys
import argparse
import json
from typing import Dict, List, Any, Optional, Tuple

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

# Database of File Signatures
# Tuple format: (offset, magic_bytes, mime_type, description, extensions)
# magic_bytes can be:
#   - bytes object for direct exact matching at offset
#   - a function that takes the file header (bytes) and returns True/False
SIGNATURES: List[Tuple[int, bytes, str, str, List[str]]] = [
    # Image Formats
    (0, b'\xFF\xD8\xFF', "image/jpeg", "JPEG Image File", ["jpg", "jpeg", "jpe"]),
    (0, b'\x89PNG\r\n\x1a\n', "image/png", "PNG Image File", ["png"]),
    (0, b'GIF87a', "image/gif", "GIF87a Graphics Interchange Format", ["gif"]),
    (0, b'GIF89a', "image/gif", "GIF89a Graphics Interchange Format", ["gif"]),
    (0, b'BM', "image/bmp", "Windows Bitmap Image File", ["bmp"]),
    (0, b'II*\x00', "image/tiff", "TIFF Image File (Little Endian)", ["tiff", "tif"]),
    (0, b'MM\x00*', "image/tiff", "TIFF Image File (Big Endian)", ["tiff", "tif"]),
    (0, b'RIFF', "image/webp", "WebP Image File", ["webp"]), # RIFF container (WebP checks offset 8)
    (0, b'8BPS', "image/vnd.adobe.photoshop", "Photoshop Document (PSD)", ["psd"]),
    
    # Audio/Video Formats
    (0, b'ID3', "audio/mpeg", "MP3 Audio File with ID3 Metadata", ["mp3"]),
    (0, b'\xFF\xFB', "audio/mpeg", "MP3 Audio File (MPEG-1 Layer 3)", ["mp3"]),
    (0, b'\xFF\xF3', "audio/mpeg", "MP3 Audio File (MPEG-1 Layer 3, No ID3)", ["mp3"]),
    (0, b'\xFF\xF2', "audio/mpeg", "MP3 Audio File (MPEG-1 Layer 3, No ID3)", ["mp3"]),
    (0, b'OggS', "audio/ogg", "Ogg Vorbis/Theora Audio/Video Container", ["ogg", "oga", "ogv", "ogx"]),
    (0, b'fLaC', "audio/flac", "Free Lossless Audio Codec", ["flac"]),
    (0, b'RIFF', "audio/wav", "Waveform Audio File (WAV)", ["wav"]), # Checked along with WAVE below
    
    # Document/Archive Formats
    (0, b'%PDF', "application/pdf", "Portable Document Format (PDF)", ["pdf"]),
    (0, b'PK\x03\x04', "application/zip", "ZIP Archive File", ["zip", "jar", "xlsx", "docx", "pptx", "epub"]),
    (0, b'PK\x05\x06', "application/zip", "ZIP Archive (Empty)", ["zip"]),
    (0, b'PK\x07\x08', "application/zip", "ZIP Archive (Spanned)", ["zip"]),
    (0, b'Rar!\x1A\x07\x00', "application/vnd.rar", "RAR Archive File (v4)", ["rar"]),
    (0, b'Rar!\x1A\x07\x01\x00', "application/vnd.rar", "RAR Archive File (v5)", ["rar"]),
    (0, b'37\x7a\xbc\xaf\x27\x1c', "application/x-7z-compressed", "7-Zip Archive File", ["7z"]),
    (0, b'\x1F\x8B', "application/gzip", "GZIP Compressed File", ["gz", "tar.gz"]),
    (0, b'BZh', "application/x-bzip2", "BZIP2 Compressed File", ["bz2", "tar.bz2"]),
    (0, b'{\\rtf', "application/rtf", "Rich Text Format", ["rtf"]),
    (0, b'SQLite format 3\x00', "application/vnd.sqlite3", "SQLite 3 Database File", ["sqlite", "sqlite3", "db"]),
    
    # Executable Formats
    (0, b'MZ', "application/x-msdownload", "Windows Executable/DLL File", ["exe", "dll", "sys", "scr"]),
    (0, b'\x7fELF', "application/x-elf", "Linux Executable and Linkable Format", ["elf", "bin", "so", "out"]),
    (0, b'\xCA\xFE\xBA\xBE', "application/java-vm", "Java Class File (Compiled)", ["class"]),
    (0, b'dex\n', "application/vnd.android.dex", "Dalvik Executable (Android)", ["dex"]),
    (0, b'Cr24', "application/x-chrome-extension", "Google Chrome Extension", ["crx"]),
    (0, b'!<arch>\n', "application/x-debian-package", "Debian Package / Static Library", ["deb", "a"]),
    
    # Markup and Code Formats
    (0, b'<?xml', "application/xml", "XML Document File", ["xml"]),
    (0, b'<!DOCTYPE html', "text/html", "HTML Document File", ["html", "htm"]),
    (0, b'<html', "text/html", "HTML Document File", ["html", "htm"]),
    (0, b'# !/usr/bin/env', "text/x-script", "Script File (Interpreter directive)", ["py", "sh", "bash", "pl", "rb"]),
    (0, b'#!/usr/bin/env', "text/x-script", "Script File (Interpreter directive)", ["py", "sh", "bash", "pl", "rb"]),
    (0, b'# !/bin/', "text/x-script", "Script File (Interpreter directive)", ["sh", "bash"]),
    (0, b'#!/bin/', "text/x-script", "Script File (Interpreter directive)", ["sh", "bash"]),
]

def analyze_file(filepath: str) -> Dict[str, Any]:
    """Analyzes a file, reading its header to determine its signature and format."""
    result = {
        "filepath": filepath,
        "filename": os.path.basename(filepath),
        "extension": os.path.splitext(filepath)[1].lower().lstrip('.'),
        "size_bytes": 0,
        "status": "unknown", # match, mismatch, unknown, error
        "detected_mime": "application/octet-stream",
        "detected_desc": "Unknown binary data or plain text",
        "matched_extensions": [],
        "hex_header": "",
        "message": ""
    }

    try:
        if not os.path.exists(filepath):
            result["status"] = "error"
            result["message"] = "File not found"
            return result
        
        if os.path.isdir(filepath):
            result["status"] = "error"
            result["message"] = "Path is a directory, not a file"
            return result

        result["size_bytes"] = os.path.getsize(filepath)
        
        # Read the first 256 bytes for analysis
        with open(filepath, 'rb') as f:
            header = f.read(256)
            
        result["hex_header"] = " ".join(f"{b:02X}" for b in header[:16])

        # Try to find a matching signature
        matched_sig = None
        for offset, magic, mime, desc, extensions in SIGNATURES:
            # Check boundary
            if len(header) >= offset + len(magic):
                file_chunk = header[offset:offset+len(magic)]
                if file_chunk == magic:
                    # Additional checks for container formats
                    # WAV check
                    if magic == b'RIFF':
                        if len(header) >= 12:
                            type_chunk = header[8:12]
                            if type_chunk == b'WAVE':
                                if mime == "audio/wav":
                                    matched_sig = (mime, desc, extensions)
                                    break
                            elif type_chunk == b'WEBP':
                                if mime == "image/webp":
                                    matched_sig = (mime, desc, extensions)
                                    break
                            elif type_chunk == b'AVI ':
                                matched_sig = ("video/x-msvideo", "AVI Video File", ["avi"])
                                break
                        continue # Skip standard RIFF if not sub-matched yet
                    
                    # EPUB check
                    if magic == b'PK\x03\x04' and len(header) >= 58:
                        if b'mimetypeapplication/epub+zip' in header:
                            matched_sig = ("application/epub+zip", "EPUB E-Book File", ["epub"])
                            break
                    
                    # Direct match
                    matched_sig = (mime, desc, extensions)
                    break

        if matched_sig:
            mime, desc, extensions = matched_sig
            result["detected_mime"] = mime
            result["detected_desc"] = desc
            result["matched_extensions"] = extensions
            
            # Check mismatch
            if not result["extension"]:
                result["status"] = "mismatch"
                result["message"] = f"No file extension. Detected as: {desc} ({mime})"
            elif result["extension"] in extensions:
                result["status"] = "match"
                result["message"] = f"File extension matches signature: {desc}"
            else:
                # Special cases where ZIP-based formats are mapped
                zip_extensions = ["docx", "xlsx", "pptx", "jar", "epub", "apk"]
                if mime == "application/zip" and result["extension"] in zip_extensions:
                    result["status"] = "match"
                    result["message"] = f"ZIP container used by standard extension: {result['extension'].upper()} format"
                else:
                    result["status"] = "mismatch"
                    result["message"] = f"Extension Mismatch! Extension is '.{result['extension']}' but signature indicates: {desc} ({', '.join(f'.{ext}' for ext in extensions)})"
        else:
            # Check if it looks like plain text
            try:
                # Try decoding as UTF-8
                text_preview = header.decode('utf-8')
                # If it decodes, check if it contains too many control chars
                control_chars = sum(1 for c in text_preview if ord(c) < 32 and c not in '\n\r\t')
                if len(text_preview) > 0 and (control_chars / len(text_preview)) < 0.05:
                    result["detected_mime"] = "text/plain"
                    result["detected_desc"] = "Plain Text File"
                    result["matched_extensions"] = ["txt", "ini", "log", "conf", "cfg", "csv", "json", "md", "py", "js", "html", "css", "sh"]
                    
                    if result["extension"] in result["matched_extensions"] or not result["extension"]:
                        result["status"] = "match"
                        result["message"] = "Plain Text File"
                    else:
                        result["status"] = "match" # Text extensions are very broad
                        result["message"] = "Text-like document structure"
                else:
                    result["status"] = "unknown"
                    result["message"] = "Unknown binary file signature"
            except UnicodeDecodeError:
                result["status"] = "unknown"
                result["message"] = "Unknown binary file signature"

    except Exception as e:
        result["status"] = "error"
        result["message"] = f"Error during analysis: {str(e)}"
        
    return result

def scan_directory(dir_path: str, recursive: bool = False, verbose: bool = False) -> List[Dict[str, Any]]:
    """Scans a directory analyzing all files inside."""
    results = []
    for root, dirs, files in os.walk(dir_path):
        for file in files:
            filepath = os.path.join(root, file)
            # Skip symlinks and special files
            if not os.path.islink(filepath):
                res = analyze_file(filepath)
                results.append(res)
        if not recursive:
            break
    return results

def main():
    parser = argparse.ArgumentParser(
        description="Analyze file magic headers to determine true file type and check for extension mismatches.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("path", help="Path to the file or directory to analyze.")
    parser.add_argument("--recursive", "-r", action="store_true", help="Recursively scan if path is a directory.")
    parser.add_argument("--mismatch-only", "-m", action="store_true", help="Only output files that have extension mismatches.")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format.")
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose headers printing.")
    
    args = parser.parse_args()
    
    target_path = os.path.abspath(args.path)
    
    if not os.path.exists(target_path):
        print(color_text(f"Error: Path '{args.path}' does not exist.", COLOR_RED), file=sys.stderr)
        return 1
        
    results = []
    if os.path.isdir(target_path):
        if not args.json:
            print(f"Scanning directory: {target_path} " + ("(recursively)" if args.recursive else ""))
        results = scan_directory(target_path, recursive=args.recursive, verbose=args.verbose)
    else:
        results = [analyze_file(target_path)]

    # Filter mismatch only
    if args.mismatch_only:
        results = [r for r in results if r["status"] == "mismatch"]

    if args.json:
        print(json.dumps(results, indent=2))
        return 0

    # Print user-facing report
    mismatches = 0
    errors = 0
    matches = 0
    unknowns = 0
    
    print("-" * 80)
    print(f"{color_text('FILE SIGNATURE DETECTOR REPORT', COLOR_BOLD)}")
    print("-" * 80)
    
    for r in results:
        status_str = ""
        if r["status"] == "match":
            status_str = color_text("[ MATCH ]", COLOR_GREEN)
            matches += 1
        elif r["status"] == "mismatch":
            status_str = color_text("[MISMATCH]", COLOR_RED)
            mismatches += 1
        elif r["status"] == "error":
            status_str = color_text("[ ERROR ]", COLOR_RED)
            errors += 1
        else:
            status_str = color_text("[UNKNOWN]", COLOR_YELLOW)
            unknowns += 1
            
        print(f"{status_str} {r['filename']} ({r['size_bytes']} bytes)")
        print(f"  Path:       {r['filepath']}")
        print(f"  Type:       {r['detected_desc']} ({r['detected_mime']})")
        print(f"  Result:     {r['message']}")
        
        if args.verbose and r["hex_header"]:
            print(f"  Hex Header: {r['hex_header']}...")
        print()
        
    print("-" * 80)
    summary_text = f"Total Scanned: {len(results)} | "
    summary_text += color_text(f"Matches: {matches}", COLOR_GREEN) + " | "
    summary_text += color_text(f"Mismatches: {mismatches}", COLOR_RED) + " | "
    summary_text += color_text(f"Unknowns: {unknowns}", COLOR_YELLOW) + " | "
    summary_text += color_text(f"Errors: {errors}", COLOR_RED)
    print(summary_text)
    print("-" * 80)
    
    if mismatches > 0:
        print(color_text("Warning: Found files with mismatched extensions/headers! This could indicate renamed files.", COLOR_YELLOW))
        return 2
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
