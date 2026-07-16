#!/usr/bin/env python3
"""
Torrent Metadata Explorer
=========================
A zero-dependency command-line utility to parse BitTorrent (.torrent) files,
decode Bencode structures, calculate SHA-1 info hashes, generate magnet links,
and display structured metadata including file trees and size diagnostics.

Author: Antigravity
License: MIT
"""

import os
import sys
import hashlib
import urllib.parse
import json
import datetime
import argparse

# ANSI color codes for rich terminal formatting
BLUE = "\033[94m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BOLD = "\033[1m"
RESET = "\033[0m"

def format_size(size_bytes):
    """Format bytes into a human-readable format."""
    if size_bytes < 0:
        return "0 B"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB', 'PB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} EB"

class BencodeDecodeError(Exception):
    """Custom exception raised during bencode parsing errors."""
    pass

class BencodeDecoder:
    """Recursively decodes a bencoded byte string."""
    def __init__(self, data: bytes):
        self.data = data
        self.index = 0

    def decode(self):
        if not self.data:
            raise BencodeDecodeError("Empty bencoded data.")
        try:
            return self._parse()
        except IndexError:
            raise BencodeDecodeError("Malformed bencoded data: unexpected end of stream.")

    def _parse(self):
        char = self.data[self.index:self.index+1]
        if not char:
            raise BencodeDecodeError("Malformed data: unexpected EOF.")

        if char == b'i':
            self.index += 1
            end_idx = self.data.find(b'e', self.index)
            if end_idx == -1:
                raise BencodeDecodeError("Malformed integer: missing 'e' terminator.")
            val_bytes = self.data[self.index:end_idx]
            self.index = end_idx + 1
            try:
                return int(val_bytes)
            except ValueError:
                raise BencodeDecodeError(f"Invalid integer representation: {val_bytes!r}")

        elif char == b'l':
            self.index += 1
            lst = []
            while self.data[self.index:self.index+1] != b'e':
                lst.append(self._parse())
            self.index += 1 # skip 'e'
            return lst

        elif char == b'd':
            self.index += 1
            dct = {}
            while self.data[self.index:self.index+1] != b'e':
                # Keys must be strings (bencoded byte strings)
                key_start = self.index
                key = self._parse()
                if not isinstance(key, bytes):
                    raise BencodeDecodeError(f"Dictionary key must be bytes, got {type(key).__name__} at index {key_start}")
                
                # Check for duplicate keys
                # (BitTorrent spec requires keys to be sorted, but we just check presence)
                val = self._parse()
                dct[key] = val
            self.index += 1 # skip 'e'
            return dct

        elif char.isdigit():
            colon_idx = self.data.find(b':', self.index)
            if colon_idx == -1:
                raise BencodeDecodeError("Malformed byte string: missing colon separator.")
            try:
                length = int(self.data[self.index:colon_idx])
            except ValueError:
                raise BencodeDecodeError("Invalid byte string length prefix.")
            
            self.index = colon_idx + 1
            start = self.index
            self.index += length
            if self.index > len(self.data):
                raise BencodeDecodeError(f"Byte string length mismatch: expected {length} bytes, got less.")
            return self.data[start:self.index]
        
        else:
            raise BencodeDecodeError(f"Invalid bencode token start prefix: {char!r} at index {self.index}")

def bencode_encode(obj) -> bytes:
    """Helper encoder to reconstruct parts (specifically for hashing the info dict)."""
    if isinstance(obj, bytes):
        return str(len(obj)).encode('ascii') + b':' + obj
    elif isinstance(obj, str):
        encoded = obj.encode('utf-8')
        return str(len(encoded)).encode('ascii') + b':' + encoded
    elif isinstance(obj, int):
        return f"i{obj}e".encode('ascii')
    elif isinstance(obj, list):
        return b'l' + b''.join(bencode_encode(item) for item in obj) + b'e'
    elif isinstance(obj, dict):
        # Dictionary keys must be sorted alphabetically by raw byte value
        sorted_keys = sorted(obj.keys())
        encoded_pairs = []
        for k in sorted_keys:
            key_bytes = k if isinstance(k, bytes) else k.encode('utf-8')
            encoded_pairs.append(bencode_encode(key_bytes) + bencode_encode(obj[k]))
        return b'd' + b''.join(encoded_pairs) + b'e'
    else:
        raise TypeError(f"Cannot bencode object of type {type(obj).__name__}")

def safe_decode_string(byte_str: bytes, encoding='utf-8') -> str:
    """Attempt decoding a string with fallback to latin-1 to avoid crashes."""
    try:
        return byte_str.decode(encoding)
    except UnicodeDecodeError:
        return byte_str.decode('latin-1', errors='replace')

def parse_torrent(filepath):
    """Parse a torrent file and return structured metadata dictionary."""
    with open(filepath, 'rb') as f:
        content = f.read()

    decoder = BencodeDecoder(content)
    torrent_dict = decoder.decode()

    if not isinstance(torrent_dict, dict):
        raise ValueError("Invalid torrent format: Root element is not a bencoded dictionary.")

    info = torrent_dict.get(b'info')
    if not info or not isinstance(info, dict):
        raise ValueError("Invalid torrent format: Missing or invalid 'info' dictionary.")

    # Calculate Info Hash (SHA-1 over raw bencoded info dictionary)
    raw_info = bencode_encode(info)
    info_hash = hashlib.sha1(raw_info).hexdigest()

    # Reconstruct standard details
    metadata = {}
    
    # Announce
    metadata['announce'] = safe_decode_string(torrent_dict.get(b'announce', b''))
    
    # Announce-list (optional multi-tracker list)
    announce_list = []
    if b'announce-list' in torrent_dict:
        for tier in torrent_dict[b'announce-list']:
            tier_urls = [safe_decode_string(url) for url in tier if isinstance(url, bytes)]
            if tier_urls:
                announce_list.append(tier_urls)
    metadata['announce_list'] = announce_list

    # Creation details
    metadata['created_by'] = safe_decode_string(torrent_dict.get(b'created by', b'Unknown'))
    
    creation_date_raw = torrent_dict.get(b'creation date')
    if creation_date_raw is not None:
        try:
            dt = datetime.datetime.fromtimestamp(int(creation_date_raw), tz=datetime.timezone.utc)
            metadata['creation_date'] = dt.strftime('%Y-%m-%d %H:%M:%S UTC')
        except (ValueError, TypeError):
            metadata['creation_date'] = "Unknown (Invalid timestamp)"
    else:
        metadata['creation_date'] = "Unknown"

    metadata['comment'] = safe_decode_string(torrent_dict.get(b'comment', b''))

    # Name of the torrent (file or folder name)
    name = safe_decode_string(info.get(b'name', b'Unnamed_Torrent'))
    metadata['name'] = name

    # Pieces configuration
    piece_length = info.get(b'piece length', 0)
    metadata['piece_length'] = piece_length
    pieces_bytes = info.get(b'pieces', b'')
    metadata['piece_count'] = len(pieces_bytes) // 20

    # Files Extraction
    files = []
    total_size = 0

    if b'files' in info:
        # Multi-file torrent
        for f_info in info[b'files']:
            length = f_info.get(b'length', 0)
            total_size += length
            
            # Paths are list of bytes
            path_parts = [safe_decode_string(part) for part in f_info.get(b'path', [])]
            path_str = os.path.join(*path_parts)
            files.append({
                'path': path_str,
                'size': length
            })
    else:
        # Single-file torrent
        length = info.get(b'length', 0)
        total_size = length
        files.append({
            'path': name,
            'size': length
        })

    metadata['files'] = files
    metadata['total_size'] = total_size
    metadata['info_hash'] = info_hash
    metadata['is_multi_file'] = b'files' in info

    # Generate Magnet Link
    # magnet:?xt=urn:btih:<info_hash>&dn=<name>&tr=<announce>
    magnet_params = {
        'dn': name,
    }
    magnet_url = f"magnet:?xt=urn:btih:{info_hash}"
    for k, v in magnet_params.items():
        magnet_url += f"&{k}={urllib.parse.quote(v)}"
    
    # Add main announce
    if metadata['announce']:
        magnet_url += f"&tr={urllib.parse.quote(metadata['announce'])}"
    
    # Add other trackers from announce-list
    for tier in announce_list:
        for url in tier:
            if url != metadata['announce']:
                magnet_url += f"&tr={urllib.parse.quote(url)}"

    metadata['magnet_link'] = magnet_url

    return metadata

def print_text_report(metadata):
    """Print a clean, visually appealing terminal text report."""
    print(f"\n{BOLD}{BLUE}======================================================================{RESET}")
    print(f"{BOLD}{GREEN}                   TORRENT METADATA EXPLORER                          {RESET}")
    print(f"{BOLD}{BLUE}======================================================================{RESET}\n")

    print(f"{BOLD}Torrent Name:{RESET}   {metadata['name']}")
    print(f"{BOLD}Info Hash:{RESET}      {YELLOW}{metadata['info_hash']}{RESET}")
    print(f"{BOLD}Created By:{RESET}     {metadata['created_by']}")
    print(f"{BOLD}Creation Date:{RESET}  {metadata['creation_date']}")
    if metadata['comment']:
        print(f"{BOLD}Comment:{RESET}        {metadata['comment']}")
    
    print(f"\n{BOLD}{BLUE}--- Tracker Information ---{RESET}")
    print(f"{BOLD}Primary Tracker:{RESET} {metadata['announce']}")
    if metadata['announce_list']:
        print(f"{BOLD}Tier Trackers:{RESET}")
        for idx, tier in enumerate(metadata['announce_list']):
            for url in tier:
                print(f"  [{idx+1}] {url}")

    print(f"\n{BOLD}{BLUE}--- Structure & Size Diagnostics ---{RESET}")
    print(f"{BOLD}Mode:{RESET}           {'Multi-file' if metadata['is_multi_file'] else 'Single-file'}")
    print(f"{BOLD}Total Size:{RESET}     {GREEN}{format_size(metadata['total_size'])}{RESET} ({metadata['total_size']} bytes)")
    print(f"{BOLD}Piece Size:{RESET}     {format_size(metadata['piece_length'])}")
    print(f"{BOLD}Piece Count:{RESET}    {metadata['piece_count']}")
    print(f"{BOLD}Total Files:{RESET}    {len(metadata['files'])}")

    print(f"\n{BOLD}{BLUE}--- File Tree List ---{RESET}")
    if len(metadata['files']) > 20:
        for f in metadata['files'][:15]:
            print(f"  {f['path']} ({format_size(f['size'])})")
        print(f"  ... and {len(metadata['files']) - 15} more files (use --files-only to view all).")
    else:
        for f in metadata['files']:
            print(f"  {f['path']} ({format_size(f['size'])})")

    print(f"\n{BOLD}{BLUE}--- Magnet Link ---{RESET}")
    print(f"{GREEN}{metadata['magnet_link']}{RESET}")
    print(f"\n{BOLD}{BLUE}======================================================================{RESET}\n")

def main():
    parser = argparse.ArgumentParser(
        description="Torrent Metadata Explorer - Parse, diagnose, and generate magnet links for .torrent files natively."
    )
    parser.add_argument("-i", "--input", required=True, help="Path to the target .torrent file.")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-m", "--magnet-only", action="store_true", help="Print only the magnet link (raw text).")
    group.add_argument("-j", "--json", action="store_true", help="Print the metadata in JSON format.")
    group.add_argument("-f", "--files-only", action="store_true", help="Print only the list of files in the torrent.")

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"{RED}Error: File '{args.input}' not found.{RESET}", file=sys.stderr)
        sys.exit(1)

    try:
        metadata = parse_torrent(args.input)
    except BencodeDecodeError as e:
        print(f"{RED}Bencode Decoding Error: {e}{RESET}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"{RED}Parsing Error: {e}{RESET}", file=sys.stderr)
        sys.exit(1)

    if args.magnet_only:
        print(metadata['magnet_link'])
    elif args.json:
        # We need to construct a JSON-serializable dictionary
        json_meta = {
            'name': metadata['name'],
            'info_hash': metadata['info_hash'],
            'created_by': metadata['created_by'],
            'creation_date': metadata['creation_date'],
            'comment': metadata['comment'],
            'announce': metadata['announce'],
            'announce_list': metadata['announce_list'],
            'is_multi_file': metadata['is_multi_file'],
            'total_size': metadata['total_size'],
            'piece_length': metadata['piece_length'],
            'piece_count': metadata['piece_count'],
            'magnet_link': metadata['magnet_link'],
            'files': metadata['files']
        }
        print(json.dumps(json_meta, indent=4))
    elif args.files_only:
        for f in metadata['files']:
            print(f"{f['path']}\t{f['size']}")
    else:
        print_text_report(metadata)

if __name__ == "__main__":
    main()
