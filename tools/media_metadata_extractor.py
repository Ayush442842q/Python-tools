#!/usr/bin/env python3
"""
Media Metadata Extractor
A pure-Python command-line utility that extracts metadata from images (JPEG, PNG, GIF)
and audio files (MP3) without any third-party dependencies.
Supports JPEG EXIF tag parsing, PNG text chunk decoding, and MP3 ID3v1/ID3v2 parsing.
"""

import argparse
import sys
import os
import struct

# Predefined ID3v1 genres
ID3V1_GENRES = [
    "Blues", "Classic Rock", "Country", "Dance", "Disco", "Funk", "Grunge", "Hip-Hop",
    "Jazz", "Metal", "New Age", "Oldies", "Other", "Pop", "R&B", "Rap", "Reggae",
    "Rock", "Techno", "Industrial", "Alternative", "Ska", "Death Metal", "Pranks",
    "Soundtrack", "Euro-Techno", "Ambient", "Trip-Hop", "Vocal", "Jazz+Funk", "Fusion",
    "Trance", "Classical", "Instrumental", "Acid", "House", "Game", "Sound Clip",
    "Gospel", "Noise", "Alternative Rock", "Bass", "Soul", "Punk", "Space", "Meditative",
    "Instrumental Pop", "Instrumental Rock", "Ethnic", "Gothic", "Darkwave",
    "Techno-Industrial", "Electronic", "Pop-Folk", "Eurodance", "Dream", "Southern Rock",
    "Comedy", "Cult", "Gangsta", "Top 40", "Christian Rap", "Pop/Funk", "Jungle",
    "Native American", "Cabaret", "New Wave", "Psychadelic", "Symphonic", "Censored",
    "Acid Jazz", "Club", "Tango", "Samba", "Folklore", "Ballad", "Power Ballad",
    "Rhythmic Soul", "Freestyle", "Duet", "Punk Rock", "Drum Solo", "Acapella",
    "Euro-House", "Dance Hall"
]

# Common EXIF Tag mappings
EXIF_TAGS = {
    0x010f: "Make",
    0x0110: "Model",
    0x0112: "Orientation",
    0x011a: "XResolution",
    0x011b: "YResolution",
    0x0128: "ResolutionUnit",
    0x0131: "Software",
    0x0132: "DateTime",
    0x013b: "Artist",
    0x829a: "ExposureTime",
    0x829d: "FNumber",
    0x8827: "ISOSpeedRatings",
    0x9003: "DateTimeOriginal",
    0x9004: "DateTimeDigitized",
    0x920a: "FocalLength",
    0x9c9b: "UserComment"
}


class MediaExtractor:
    @staticmethod
    def parse_png(f):
        """Extract details from PNG files."""
        f.seek(8)  # Skip PNG signature
        info = {"Format": "PNG"}
        
        while True:
            try:
                length_bytes = f.read(4)
                if not length_bytes or len(length_bytes) < 4:
                    break
                length = struct.unpack(">I", length_bytes)[0]
                chunk_type = f.read(4).decode("latin-1", errors="ignore")
                
                if chunk_type == "IHDR":
                    ihdr_data = f.read(length)
                    if len(ihdr_data) >= 13:
                        width, height, bit_depth, color_type = struct.unpack(">IIBB", ihdr_data[:10])
                        info["Width"] = width
                        info["Height"] = height
                        info["Bit Depth"] = bit_depth
                        info["Color Type"] = color_type
                    f.seek(4, 1)  # Skip CRC
                    
                elif chunk_type == "tEXt":
                    text_data = f.read(length)
                    if b"\x00" in text_data:
                        keyword, val = text_data.split(b"\x00", 1)
                        key_str = keyword.decode("latin-1", errors="ignore")
                        val_str = val.decode("utf-8", errors="ignore")
                        if "Metadata" not in info:
                            info["Metadata"] = {}
                        info["Metadata"][key_str] = val_str
                    f.seek(4, 1)  # Skip CRC
                    
                elif chunk_type == "IEND":
                    break
                else:
                    f.seek(length + 4, 1)  # Skip chunk data and CRC
            except Exception:
                break
                
        return info

    @staticmethod
    def parse_gif(f):
        """Extract details from GIF files."""
        f.seek(0)
        sig = f.read(6).decode("latin-1", errors="ignore")
        if sig not in ("GIF89a", "GIF87a"):
            return None
            
        info = {"Format": "GIF", "Version": sig}
        dims = f.read(4)
        if len(dims) == 4:
            width, height = struct.unpack("<HH", dims)
            info["Width"] = width
            info["Height"] = height
        return info

    @staticmethod
    def parse_jpeg(f):
        """Extract details and EXIF from JPEG files."""
        f.seek(0)
        if f.read(2) != b"\xff\xd8":
            return None
            
        info = {"Format": "JPEG", "Metadata": {}}
        
        while True:
            try:
                marker = f.read(2)
                if not marker or len(marker) < 2 or marker[0] != 0xff:
                    break
                
                # Check for start of frame markers containing dimensions
                if marker[1] in (0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf):
                    length = struct.unpack(">H", f.read(2))[0]
                    sof_data = f.read(length - 2)
                    if len(sof_data) >= 5:
                        precision, height, width = struct.unpack(">BHH", sof_data[:5])
                        info["Width"] = width
                        info["Height"] = height
                        info["Precision"] = precision
                        
                elif marker[1] == 0xe1: # APP1 marker - EXIF data resides here
                    length = struct.unpack(">H", f.read(2))[0]
                    app1_data = f.read(length - 2)
                    if app1_data.startswith(b"Exif\x00\x00"):
                        exif_info = MediaExtractor._parse_exif(app1_data[6:])
                        if exif_info:
                            info["Metadata"].update(exif_info)
                else:
                    # Skip chunk
                    if marker[1] not in (0xd8, 0xd9, 0x00):
                        length = struct.unpack(">H", f.read(2))[0]
                        f.seek(length - 2, 1)
            except Exception:
                break
                
        return info

    @staticmethod
    def _parse_exif(tiff_data):
        """Helper to parse TIFF/EXIF blocks."""
        exif = {}
        if len(tiff_data) < 8:
            return exif
            
        # Parse byte alignment
        align = tiff_data[:2]
        if align == b"II":
            endian = "<"  # Little endian
        elif align == b"MM":
            endian = ">"  # Big endian
        else:
            return exif
            
        magic = struct.unpack(f"{endian}H", tiff_data[2:4])[0]
        if magic != 42:
            return exif
            
        ifd_offset = struct.unpack(f"{endian}I", tiff_data[4:8])[0]
        
        # Read first IFD
        idx = ifd_offset
        if idx + 2 > len(tiff_data):
            return exif
            
        num_entries = struct.unpack(f"{endian}H", tiff_data[idx:idx+2])[0]
        idx += 2
        
        for _ in range(num_entries):
            if idx + 12 > len(tiff_data):
                break
            tag_id, tag_type, count, val_offset = struct.unpack(f"{endian}HHI", tiff_data[idx:idx+10])
            idx += 12
            
            # Map known tags
            if tag_id in EXIF_TAGS:
                tag_name = EXIF_TAGS[tag_id]
                
                # Fetch value depending on type
                val = None
                # Type 2: ASCII string
                if tag_type == 2:
                    if count <= 4:
                        # Value resides directly in the offset field
                        val_bytes = struct.pack(f"{endian}I", val_offset)[:count]
                    else:
                        val_bytes = tiff_data[val_offset:val_offset + count]
                    val = val_bytes.decode("latin-1", errors="ignore").strip("\x00 \n\r")
                # Type 3: Short (16-bit unsigned integer)
                elif tag_type == 3:
                    val = val_offset & 0xffff
                # Type 4: Long (32-bit unsigned integer)
                elif tag_type == 4:
                    val = val_offset
                # Type 5: Rational (two 32-bit signed ints)
                elif tag_type == 5:
                    if val_offset + 8 <= len(tiff_data):
                        num, den = struct.unpack(f"{endian}II", tiff_data[val_offset:val_offset+8])
                        val = f"{num}/{den}" if den != 0 else str(num)
                        
                if val is not None:
                    exif[tag_name] = val
                    
        return exif

    @staticmethod
    def parse_mp3(f):
        """Parses MP3 ID3v1 and ID3v2 tags."""
        info = {"Format": "MP3", "Metadata": {}}
        
        # 1. Check ID3v2 at the beginning of the file
        f.seek(0)
        header = f.read(10)
        if len(header) == 10 and header.startswith(b"ID3"):
            version_major = header[3]
            version_minor = header[4]
            info["ID3 Version"] = f"v2.{version_major}.{version_minor}"
            
            # Size is a synchsafe integer (7 bits per byte)
            size = ((header[6] & 0x7f) << 21) | \
                   ((header[7] & 0x7f) << 14) | \
                   ((header[8] & 0x7f) << 7) | \
                   (header[9] & 0x7f)
                   
            # Parse ID3v2 frames
            tag_data = f.read(size)
            idx = 0
            
            # We support standard ID3v2.3 and ID3v2.4 frames
            while idx + 10 < len(tag_data):
                frame_id_bytes = tag_data[idx:idx+4]
                if frame_id_bytes[0] == 0:
                    break # Padding bytes
                    
                frame_id = frame_id_bytes.decode("latin-1", errors="ignore")
                
                # In ID3v2.3 size is normal int, in ID3v2.4 it's synchsafe.
                # We'll treat as normal int for v2.3 and synchsafe for v2.4.
                f_size_bytes = tag_data[idx+4:idx+8]
                if version_major == 4: # v2.4
                    f_size = ((f_size_bytes[0] & 0x7f) << 21) | \
                             ((f_size_bytes[1] & 0x7f) << 14) | \
                             ((f_size_bytes[2] & 0x7f) << 7) | \
                             (f_size_bytes[3] & 0x7f)
                else:
                    f_size = struct.unpack(">I", f_size_bytes)[0]
                    
                idx += 10
                if idx + f_size > len(tag_data):
                    break
                    
                frame_content = tag_data[idx:idx+f_size]
                idx += f_size
                
                # Check for textual frames (start with T, except TXXX)
                if frame_id.startswith("T") and frame_id != "TXXX":
                    if len(frame_content) > 1:
                        encoding = frame_content[0]
                        payload = frame_content[1:]
                        try:
                            if encoding == 0:
                                val = payload.decode("iso-8859-1", errors="ignore")
                            elif encoding == 1:
                                val = payload.decode("utf-16", errors="ignore")
                            elif encoding == 2:
                                val = payload.decode("utf-16-be", errors="ignore")
                            elif encoding == 3:
                                val = payload.decode("utf-8", errors="ignore")
                            else:
                                val = payload.decode("latin-1", errors="ignore")
                            val = val.strip("\x00\ufeff ")
                            
                            # Standard frame mappings
                            tag_name_map = {
                                "TIT2": "Title", "TPE1": "Artist", "TALB": "Album", 
                                "TYER": "Year", "TDRC": "Year", "TRCK": "Track", "TCON": "Genre"
                            }
                            if frame_id in tag_name_map:
                                info["Metadata"][tag_name_map[frame_id]] = val
                            else:
                                info["Metadata"][frame_id] = val
                        except Exception:
                            pass
        
        # 2. Check ID3v1 at the end of the file
        try:
            f.seek(-128, 2)
            id3v1 = f.read(128)
            if len(id3v1) == 128 and id3v1[:3] == b"TAG":
                info["Has ID3v1"] = True
                
                title = id3v1[3:33].decode("latin-1", errors="ignore").strip("\x00 ")
                artist = id3v1[33:63].decode("latin-1", errors="ignore").strip("\x00 ")
                album = id3v1[63:93].decode("latin-1", errors="ignore").strip("\x00 ")
                year = id3v1[93:97].decode("latin-1", errors="ignore").strip("\x00 ")
                
                genre_idx = id3v1[127]
                genre = ID3V1_GENRES[genre_idx] if genre_idx < len(ID3V1_GENRES) else f"Unknown ({genre_idx})"
                
                # Check for ID3v1.1 (track support in comments)
                track = None
                if id3v1[125] == 0 and id3v1[126] != 0:
                    comment = id3v1[97:125].decode("latin-1", errors="ignore").strip("\x00 ")
                    track = id3v1[126]
                else:
                    comment = id3v1[97:127].decode("latin-1", errors="ignore").strip("\x00 ")
                
                # Populate if not already set by ID3v2 (which has higher priority)
                meta = info["Metadata"]
                if "Title" not in meta and title: meta["Title"] = title
                if "Artist" not in meta and artist: meta["Artist"] = artist
                if "Album" not in meta and album: meta["Album"] = album
                if "Year" not in meta and year: meta["Year"] = year
                if "Genre" not in meta and genre: meta["Genre"] = genre
                if "Track" not in meta and track: meta["Track"] = str(track)
                if "Comment" not in meta and comment: meta["Comment"] = comment
        except Exception:
            pass
            
        return info


def main():
    parser = argparse.ArgumentParser(
        description="Media Metadata Extractor - Extract dimensions & metadata from JPEG, PNG, GIF, and MP3 files."
    )
    parser.add_argument(
        'file_path',
        help="Path to the media file"
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.file_path):
        print(f"Error: File '{args.file_path}' not found.", file=sys.stderr)
        return 1
        
    try:
        with open(args.file_path, 'rb') as f:
            header = f.read(10)
            f.seek(0)
            
            info = None
            if header.startswith(b"\x89PNG\r\n\x1a\n"):
                info = MediaExtractor.parse_png(f)
            elif header.startswith(b"GIF89a") or header.startswith(b"GIF87a"):
                info = MediaExtractor.parse_gif(f)
            elif header.startswith(b"\xff\xd8"):
                info = MediaExtractor.parse_jpeg(f)
            elif header.startswith(b"ID3") or header.startswith(b"\xff\xfb") or header.startswith(b"\xff\xf3"):
                info = MediaExtractor.parse_mp3(f)
            else:
                # Fallback check for MP3 with no ID3v2 header but might contain ID3v1 at the end
                ext = os.path.splitext(args.file_path)[1].lower()
                if ext == '.mp3':
                    info = MediaExtractor.parse_mp3(f)
                    
            if info is None:
                print("Error: Unsupported file format or unparseable metadata signature.", file=sys.stderr)
                return 1
                
            # Print results beautifully
            print(f"=== Metadata for file: {os.path.basename(args.file_path)} ===")
            print(f"Format: {info.get('Format', 'Unknown')}")
            
            if "Width" in info and "Height" in info:
                print(f"Dimensions: {info['Width']} x {info['Height']} pixels")
                
            for k in ["Version", "Bit Depth", "Color Type", "ID3 Version"]:
                if k in info:
                    print(f"{k}: {info[k]}")
                    
            meta = info.get("Metadata", {})
            if meta:
                print("\nMetadata / Tags:")
                for tag, val in sorted(meta.items()):
                    print(f"  {tag}: {val}")
            else:
                print("\nNo metadata tags found.")
                
    except Exception as e:
        print(f"Execution Error: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
