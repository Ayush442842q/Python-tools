#!/usr/bin/env python3
"""
EXIF Metadata Inspector & Cleaner

Inspects EXIF metadata in JPEG images and allows stripping it to preserve privacy.
Works in pure Python (no dependencies) for stripping/cleaning, and uses Pillow
if available to provide detailed EXIF tag inspections.

Usage:
    python exif_cleaner.py image.jpg [options]
"""

import sys
import os
import argparse
from pathlib import Path

# Try to import PIL for enhanced EXIF inspection
HAS_PIL = False
try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
    HAS_PIL = True
except ImportError:
    pass

def inspect_exif_pil(image_path):
    """Inspect and format EXIF using Pillow."""
    try:
        with Image.open(image_path) as img:
            exif = img.getexif()
            if not exif:
                print("No EXIF metadata found using Pillow parser.")
                return False
                
            print("\n--- Image Details ---")
            print(f"Format: {img.format}")
            print(f"Size: {img.width}x{img.height}")
            print(f"Mode: {img.mode}")
            
            print("\n--- EXIF Metadata ---")
            # Print standard tags
            for tag_id, value in exif.items():
                tag_name = TAGS.get(tag_id, f"Unknown (ID: {tag_id})")
                
                # Check for nested GPS details
                if tag_name == "GPSInfo" and isinstance(value, dict):
                    print("GPS Details:")
                    for gps_id in value:
                        gps_tag = GPSTAGS.get(gps_id, f"GPSUnknown (ID: {gps_id})")
                        print(f"  {gps_tag}: {value[gps_id]}")
                else:
                    # Avoid printing giant binary payloads
                    if isinstance(value, bytes) and len(value) > 100:
                        value = f"<Binary Data: {len(value)} bytes>"
                    print(f"{tag_name}: {value}")
            return True
    except Exception as e:
        print(f"Error parsing metadata with Pillow: {e}")
        return False

def inspect_exif_fallback(image_path):
    """Fallback method to scan APP1 binary segment for ASCII strings if Pillow is not available."""
    try:
        with open(image_path, 'rb') as f:
            data = f.read()
            
        if data[:2] != b'\xff\xd8':
            print("Error: Not a valid JPEG file.")
            return False
            
        # Find APP1 (0xFFE1) which usually holds EXIF
        app1_idx = 0
        while True:
            app1_idx = data.find(b'\xff\xe1', app1_idx)
            if app1_idx == -1:
                break
            
            # Check if this is the Exif block
            # Length of APP1 segment is at app1_idx + 2 (2 bytes)
            if app1_idx + 10 < len(data) and data[app1_idx + 4:app1_idx + 8] == b'Exif':
                print("EXIF segment (APP1) detected in binary stream.")
                segment_len = int.from_bytes(data[app1_idx+2:app1_idx+4], byteorder='big')
                exif_block = data[app1_idx+4 : app1_idx+2+segment_len]
                
                # Extract printable ASCII sequences as a fallback
                print("\nRaw readable strings in metadata block:")
                current_str = []
                strings = []
                for b in exif_block:
                    if 32 <= b <= 126:
                        current_str.append(chr(b))
                    else:
                        if len(current_str) >= 4:
                            strings.append("".join(current_str))
                        current_str = []
                if current_str:
                    strings.append("".join(current_str))
                
                # Deduplicate and filter out common noise
                for s in sorted(list(set(strings))):
                    if len(s.strip()) > 3 and not s.startswith(('Exif', 'II*', 'MM*')):
                        print(f"  - {s}")
                return True
                
            app1_idx += 2 # search next
            
        print("No EXIF metadata segment found in image file.")
        return False
    except Exception as e:
        print(f"Error inspecting binary data: {e}")
        return False

def strip_metadata(input_path, output_path):
    """Strips APP1 (EXIF), APP2 (ICC Profile), APP13 (IPTC), COM (Comments) from JPEG."""
    try:
        with open(input_path, 'rb') as f:
            data = f.read()
            
        if data[:2] != b'\xff\xd8':
            print("Error: Input is not a valid JPEG file.", file=sys.stderr)
            return False
            
        out_bytes = bytearray()
        out_bytes.extend(data[:2]) # Write SOI
        
        pos = 2
        stripped_count = 0
        stripped_bytes = 0
        
        while pos < len(data):
            # Find next marker
            if data[pos:pos+1] != b'\xff':
                # Stream out of sync or hit entropy-coded scan data
                out_bytes.extend(data[pos:])
                break
                
            marker = data[pos+1:pos+2]
            
            if marker == b'\xd9': # EOI
                out_bytes.extend(data[pos:pos+2])
                break
            elif marker == b'\xd8': # SOI
                out_bytes.extend(data[pos:pos+2])
                pos += 2
                continue
                
            # Read length of segment
            if pos + 4 > len(data):
                out_bytes.extend(data[pos:])
                break
                
            segment_len = int.from_bytes(data[pos+2:pos+4], byteorder='big')
            
            # Identify segments to strip:
            # - APP1 (0xE1): EXIF, XMP
            # - APP2 (0xE2): ICC Profile (sometimes kept, but strip for complete privacy)
            # - APP13 (0xED): IPTC metadata
            # - COM (0xFE): Comments
            is_metadata = marker in (b'\xe1', b'\xe2', b'\xed', b'\xfe')
            
            if is_metadata:
                stripped_count += 1
                stripped_bytes += segment_len + 2
                pos += segment_len + 2 # Skip this segment
            elif marker == b'\xda': # SOS (Start of Scan) - contains entropy data
                # SOS runs to the end of the file or next marker, write it and the rest
                out_bytes.extend(data[pos:])
                break
            else:
                # Keep other segments (APP0 JFIF, DQT, DHT, SOF0, etc.)
                out_bytes.extend(data[pos : pos + 2 + segment_len])
                pos += segment_len + 2
                
        # Write clean data
        with open(output_path, 'wb') as f:
            f.write(out_bytes)
            
        print(f"Metadata stripping complete.")
        print(f"Removed {stripped_count} segment(s) total.")
        print(f"Saved {stripped_bytes} bytes of privacy-sensitive metadata.")
        return True
    except Exception as e:
        print(f"Error stripping metadata: {e}", file=sys.stderr)
        return False

def main():
    parser = argparse.ArgumentParser(
        description="Inspect and strip EXIF/metadata from JPEG images to preserve privacy.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "image",
        help="Path to the JPEG image file."
    )
    parser.add_argument(
        "--strip", "-s",
        action="store_true",
        help="Strip EXIF metadata from the image."
    )
    parser.add_argument(
        "--output", "-o",
        help="Path to save the stripped image. If not specified, overrides the input image (creates backup)."
    )
    
    args = parser.parse_args()
    
    image_path = Path(args.image).resolve()
    if not image_path.exists():
        print(f"Error: File '{args.image}' does not exist.", file=sys.stderr)
        return 1
        
    if not image_path.suffix.lower() in ('.jpg', '.jpeg'):
        print("Warning: This tool is optimized for JPEG/JPG format.", file=sys.stderr)
        
    # 1. Inspection mode
    if not args.strip:
        print(f"Inspecting '{image_path.name}'...")
        success = False
        if HAS_PIL:
            success = inspect_exif_pil(image_path)
            if not success:
                print("Falling back to raw binary search...")
                success = inspect_exif_fallback(image_path)
        else:
            print("Pillow library not installed. Using raw binary search.")
            print("Note: Install Pillow ('pip install Pillow') for rich, structured EXIF tag details.")
            success = inspect_exif_fallback(image_path)
            
        if success:
            print("\nUse the --strip option to remove this metadata.")
        return 0
        
    # 2. Strip mode
    output_path = args.output
    if not output_path:
        # Override original, but make a backup first
        output_path = str(image_path)
        backup_path = image_path.with_name(image_path.stem + "_backup" + image_path.suffix)
        print(f"Overwriting original. Creating backup at '{backup_path.name}'...")
        try:
            import shutil
            shutil.copy2(image_path, backup_path)
        except Exception as e:
            print(f"Error creating backup file: {e}", file=sys.stderr)
            return 1
            
    print(f"Stripping metadata from '{image_path.name}'...")
    if strip_metadata(image_path, output_path):
        print(f"Saved cleaned image to '{Path(output_path).name}'.")
        return 0
    return 1

if __name__ == "__main__":
    sys.exit(main())
