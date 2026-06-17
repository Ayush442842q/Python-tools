#!/usr/bin/env python3
"""
HTTP Downloader with Resuming & Checksum Verification

A pure standard library file downloader that displays a detailed terminal
progress bar, download speed, and ETA. Supports resuming interrupted downloads
using HTTP Range headers and verifying file integrity with MD5 or SHA-256 hashes.

Usage:
    python tools/http_downloader.py https://example.com/largefile.zip
    python tools/http_downloader.py https://example.com/largefile.zip -o my_file.zip
    python tools/http_downloader.py URL --sha256 <hash_string>
    python tools/http_downloader.py URL --resume
"""

import os
import sys
import time
import urllib.request
import urllib.error
import hashlib
import argparse
from typing import Optional, Tuple, Dict, Any

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

def format_size(bytes_size: float) -> str:
    """Formats bytes into human readable sizes (KB, MB, GB)."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.2f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.2f} PB"

def format_time(seconds: float) -> str:
    """Formats time duration in seconds to MM:SS or HH:MM:SS."""
    if seconds == float('inf') or seconds < 0:
        return "--:--"
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"

def calculate_checksum(filepath: str, algo: str) -> str:
    """Calculates the hash of a file using MD5 or SHA-256."""
    hash_func = hashlib.md5() if algo.lower() == 'md5' else hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(65536), b''):
            hash_func.update(chunk)
    return hash_func.hexdigest()

def draw_progress_bar(downloaded: int, total: int, start_time: float, prefix: str = ""):
    """Draws a custom visual progress bar in the terminal."""
    # Terminal width detection
    try:
        columns = os.get_terminal_size().columns
    except OSError:
        columns = 80
        
    bar_width = max(10, columns - len(prefix) - 45)
    
    elapsed = time.time() - start_time
    speed = downloaded / elapsed if elapsed > 0 else 0
    
    if total > 0:
        percent = min(100.0, (downloaded / total) * 100.0)
        filled_length = int(bar_width * downloaded // total)
        bar = '█' * filled_length + '░' * (bar_width - filled_length)
        
        eta_seconds = (total - downloaded) / speed if speed > 0 else float('inf')
        eta_str = format_time(eta_seconds)
        
        status = f" {percent:5.1f}% | [{bar}] | {format_size(downloaded)}/{format_size(total)} | {format_size(speed)}/s | ETA: {eta_str}"
    else:
        # Unknown total size (streaming content)
        status = f" | {format_size(downloaded)} downloaded | {format_size(speed)}/s | Elapsed: {format_time(elapsed)}"
        
    sys.stdout.write(f"\r{prefix}{status}")
    sys.stdout.flush()

def download_file(url: str, output_path: str, resume: bool = False) -> bool:
    """Downloads a file with optional resuming, showing progress bar."""
    # Build request
    req = urllib.request.Request(url)
    req.add_header('User-Agent', 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Python-urllib')
    
    existing_bytes = 0
    mode = 'wb'
    
    # Handle resuming
    if resume and os.path.exists(output_path):
        existing_bytes = os.path.getsize(output_path)
        if existing_bytes > 0:
            req.add_header('Range', f'bytes={existing_bytes}-')
            mode = 'ab'
            print(f"Attempting to resume download from byte {existing_bytes}...")
            
    try:
        response = urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        if resume and e.code == 416: # Range Not Satisfiable (file might already be fully downloaded)
            print(color_text("Error: Range not satisfiable. The local file might already be complete.", COLOR_YELLOW))
            return True
        print(color_text(f"HTTP Error: {e.code} - {e.reason}", COLOR_RED), file=sys.stderr)
        return False
    except Exception as e:
        print(color_text(f"Connection Error: {str(e)}", COLOR_RED), file=sys.stderr)
        return False
        
    # Check if server accepted range request
    is_partial = response.getcode() == 206
    content_length = response.getheader('Content-Length')
    
    total_bytes = 0
    if content_length:
        total_bytes = int(content_length)
        
    if is_partial:
        total_bytes += existing_bytes
        print(color_text("✓ Server supported partial download resume.", COLOR_GREEN))
    elif resume and existing_bytes > 0:
        # Server did not support range, so restart
        print(color_text("! Server does not support resume. Restarting download from scratch...", COLOR_YELLOW))
        existing_bytes = 0
        mode = 'wb'
        
    # Start download loop
    chunk_size = 1024 * 16 # 16KB blocks
    downloaded_bytes = existing_bytes
    start_time = time.time()
    # Adjust start time to simulate progress speed for resume
    if downloaded_bytes > 0:
        start_time -= 1.0 # arbitrary offset to avoid division by zero
        
    print(f"Saving to: {output_path}")
    prefix = "Downloading:"
    
    try:
        with open(output_path, mode) as f:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded_bytes += len(chunk)
                draw_progress_bar(downloaded_bytes, total_bytes, start_time, prefix)
        print("\n" + color_text("✓ Download completed successfully.", COLOR_GREEN))
        return True
    except KeyboardInterrupt:
        print("\n" + color_text("! Download interrupted by user.", COLOR_YELLOW))
        return False
    except Exception as e:
        print(f"\n{color_text('Error writing file:', COLOR_RED)} {str(e)}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Download files over HTTP/HTTPS with progress bar, download resuming, and checksum checking.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("url", help="Target URL to download.")
    parser.add_argument("-o", "--output", help="Output file path (inferred from URL if omitted).")
    parser.add_argument("-r", "--resume", action="store_true", help="Try to resume an interrupted download if file exists.")
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--sha256", help="Validate downloaded file integrity using SHA-256 hash.")
    group.add_argument("--md5", help="Validate downloaded file integrity using MD5 hash.")
    
    args = parser.parse_args()
    
    # Infer output name if not provided
    output_path = args.output
    if not output_path:
        # Strip query parameters and fragment
        clean_url = args.url.split('?')[0].split('#')[0]
        output_path = os.path.basename(clean_url)
        if not output_path:
            output_path = "downloaded_file.bin"
            
    output_path = os.path.abspath(output_path)
    
    success = download_file(args.url, output_path, args.resume)
    
    if not success:
        return 1
        
    # Checksum validation
    if args.sha256 or args.md5:
        algo = 'sha256' if args.sha256 else 'md5'
        expected = args.sha256 if args.sha256 else args.md5
        expected = expected.lower().strip()
        
        print("Calculating file checksum...")
        actual = calculate_checksum(output_path, algo)
        
        print(f"Expected: {expected}")
        print(f"Actual:   {actual}")
        
        if actual == expected:
            print(color_text("✓ Checksum MATCHES! File integrity verified.", COLOR_GREEN))
        else:
            print(color_text("✗ Checksum MISMATCH! File may be corrupted or modified.", COLOR_RED), file=sys.stderr)
            return 2
            
    return 0

if __name__ == "__main__":
    sys.exit(main())
