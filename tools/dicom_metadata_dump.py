#!/usr/bin/env python3
"""
DICOM Metadata Dump & Parser

A standalone, zero-dependency parser for DICOM (.dcm) medical imaging files.
Validates the DICOM preamble, parses Explicit VR elements, and extracts key
metadata elements (patient info, study info, image dimensions, etc.).

Usage:
    python dicom_metadata_dump.py [path_to_dicom_file]
"""

import sys
import os
import argparse
import struct

# Standard DICOM Tag Dictionary (Key Tags)
TAG_DICT = {
    (0x0002, 0x0010): ("TransferSyntaxUID", "Transfer Syntax UID"),
    (0x0008, 0x0020): ("StudyDate", "Study Date"),
    (0x0008, 0x0030): ("StudyTime", "Study Time"),
    (0x0008, 0x0050): ("AccessionNumber", "Accession Number"),
    (0x0008, 0x0060): ("Modality", "Modality"),
    (0x0008, 0x0070): ("Manufacturer", "Manufacturer"),
    (0x0008, 0x0080): ("InstitutionName", "Institution Name"),
    (0x0008, 0x1030): ("StudyDescription", "Study Description"),
    (0x0008, 0x103e): ("SeriesDescription", "Series Description"),
    (0x0010, 0x0010): ("PatientName", "Patient's Name"),
    (0x0010, 0x0020): ("PatientID", "Patient ID"),
    (0x0010, 0x0030): ("PatientBirthDate", "Patient Birth Date"),
    (0x0010, 0x0040): ("PatientSex", "Patient Sex"),
    (0x0018, 0x0015): ("BodyPartExamined", "Body Part Examined"),
    (0x0018, 0x0050): ("SliceThickness", "Slice Thickness (mm)"),
    (0x0018, 0x0060): ("KVP", "kVp"),
    (0x0020, 0x000d): ("StudyInstanceUID", "Study Instance UID"),
    (0x0020, 0x000e): ("SeriesInstanceUID", "Series Instance UID"),
    (0x0020, 0x0010): ("StudyID", "Study ID"),
    (0x0020, 0x0011): ("SeriesNumber", "Series Number"),
    (0x0020, 0x0013): ("InstanceNumber", "Instance Number"),
    (0x0028, 0x0010): ("Rows", "Rows (Height)"),
    (0x0028, 0x0011): ("Columns", "Columns (Width)"),
    (0x0028, 0x0100): ("BitsAllocated", "Bits Allocated"),
    (0x0028, 0x0101): ("BitsStored", "Bits Stored"),
    (0x0028, 0x1050): ("WindowCenter", "Window Center"),
    (0x0028, 0x1051): ("WindowWidth", "Window Width"),
    (0x7fe0, 0x0010): ("PixelData", "Pixel Data (Raw Bytes Count)"),
}

def parse_tag(data, offset, is_little_endian=True):
    """Parses a single 4-byte Tag (Group, Element) from data at offset."""
    fmt = "<HH" if is_little_endian else ">HH"
    return struct.unpack_from(fmt, data, offset)

def clean_value(vr, value_bytes):
    """Converts value bytes into a python representation depending on the VR."""
    # Strip null bytes and trailing spaces
    cleaned = value_bytes.rstrip(b'\x00').rstrip(b' ')
    
    if vr in ('US', 'SS'):  # Unsigned Short, Signed Short
        if len(cleaned) >= 2:
            return struct.unpack("<H", cleaned[:2])[0]
        return ""
    elif vr in ('UL', 'SL'):  # Unsigned Long, Signed Long
        if len(cleaned) >= 4:
            return struct.unpack("<I", cleaned[:4])[0]
        return ""
    elif vr in ('FD', 'FL'):  # Float Double, Float Single
        if vr == 'FD' and len(cleaned) >= 8:
            return struct.unpack("<d", cleaned[:8])[0]
        elif vr == 'FL' and len(cleaned) >= 4:
            return struct.unpack("<f", cleaned[:4])[0]
        return ""
    
    # Textual fields
    try:
        text = cleaned.decode('utf-8', errors='ignore').strip()
        # Decode caret separators standard in DICOM Patient Name (Last^First^Middle)
        if vr == 'PN':
            text = text.replace('^', ', ')
        return text
    except Exception:
        return cleaned

def parse_dicom(filepath):
    """Parses a DICOM file and returns extracted metadata elements."""
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' does not exist.", file=sys.stderr)
        return None
        
    try:
        with open(filepath, 'rb') as f:
            data = f.read()
    except Exception as e:
        print(f"Error reading file '{filepath}': {e}", file=sys.stderr)
        return None

    # DICOM files have a 128-byte preamble, followed by 'DICM'
    if len(data) < 132:
        print("Error: File is too small to be a DICOM file.", file=sys.stderr)
        return None

    preamble = data[:128]
    magic = data[128:132]
    if magic != b'DICM':
        print("Error: Invalid DICOM file. 'DICM' prefix not found at byte 128.", file=sys.stderr)
        return None

    offset = 132
    metadata = {}
    is_little_endian = True
    is_explicit_vr = True

    # Parse dataset elements
    while offset < len(data) - 8:
        try:
            # 1. Parse Tag
            group, element = parse_tag(data, offset, is_little_endian)
            tag = (group, element)
            offset += 4

            # Group 0002 is always Explicit VR Little Endian.
            # If we are parsing other groups, we respect the Transfer Syntax.
            # Handle Item / Sequence delimitation tags which don't have VR
            if group in (0xFFFE, 0x7FE0) and element in (0xE00D, 0xE0DD, 0xE000):
                # Length is always 4 bytes
                length = struct.unpack_from("<I", data, offset)[0]
                offset += 4
                # Skip sequence item payloads
                if length != 0xFFFFFFFF and length > 0:
                    offset += length
                continue

            # 2. Parse VR (Value Representation)
            vr = data[offset:offset+2].decode('ascii', errors='ignore')
            
            # Explicit VR vs Implicit VR
            # If VR is indeed a valid uppercase 2-letter ASCII code:
            if vr.isupper() and vr.isalpha():
                offset += 2
                # In Explicit VR: depending on VR, length is 2 bytes or (reserved 2 bytes + 4 bytes)
                if vr in ('OB', 'OW', 'OF', 'SQ', 'UT', 'UN'):
                    # Skip 2 reserved bytes
                    offset += 2
                    length = struct.unpack_from("<I", data, offset)[0]
                    offset += 4
                else:
                    length = struct.unpack_from("<H", data, offset)[0]
                    offset += 2
            else:
                # Implicit VR: VR is not in the stream. Length is 4 bytes.
                # Look up VR from Tag if possible, otherwise treat as UN (Unknown)
                vr = "UN"
                length = struct.unpack_from("<I", data, offset)[0]
                offset += 4

            # 3. Read Value Bytes
            if length == 0xFFFFFFFF:
                # Undefined length (typically for sequences or compressed pixel data)
                # We skip to avoid parsing complex nested sequences
                # In basic metadata parser, we just break or search for Sequence Delimitation Item
                break
                
            value_bytes = data[offset:offset+length]
            offset += length

            # If tag is in our key dictionary, store it
            if tag in TAG_DICT:
                val = clean_value(vr, value_bytes)
                metadata[tag] = {
                    'name': TAG_DICT[tag][0],
                    'label': TAG_DICT[tag][1],
                    'vr': vr,
                    'value': val
                }

            # Check if this is the Transfer Syntax UID to adjust parsing (if we were to support Implicit)
            if tag == (0x0002, 0x0010):
                syntax_uid = clean_value(vr, value_bytes)
                # '1.2.840.10008.1.2' is Implicit VR Little Endian
                if syntax_uid == '1.2.840.10008.1.2':
                    # Future elements will be Implicit VR
                    is_explicit_vr = False

        except Exception as e:
            # Parse error or EOF
            break

    return metadata

def main():
    parser = argparse.ArgumentParser(
        description="Natively inspects and extracts metadata from medical DICOM (.dcm) images.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "dicom_file",
        help="Path to the DICOM (.dcm) image file."
    )
    
    args = parser.parse_args()
    
    print("DICOM Metadata Parser")
    print("=" * 60)
    
    metadata = parse_dicom(args.dicom_file)
    if metadata is None:
        return 1
        
    if not metadata:
        print("No metadata elements found or failed to parse.")
        return 0

    # Print out results by Category
    patient_tags = [(0x0010, 0x0010), (0x0010, 0x0020), (0x0010, 0x0030), (0x0010, 0x0040)]
    study_tags = [(0x0008, 0x0020), (0x0008, 0x0030), (0x0008, 0x0050), (0x0008, 0x0060), (0x0008, 0x1030)]
    image_tags = [(0x0028, 0x0010), (0x0028, 0x0011), (0x0028, 0x0100), (0x0028, 0x0101), (0x0028, 0x1050), (0x0028, 0x1051), (0x7fe0, 0x0010)]

    print("\n[Patient Information]")
    print("-" * 60)
    for tag in patient_tags:
        if tag in metadata:
            print(f"  {metadata[tag]['label']:<25} : {metadata[tag]['value']}")
            
    print("\n[Study & Equipment Information]")
    print("-" * 60)
    for tag in study_tags:
        if tag in metadata:
            print(f"  {metadata[tag]['label']:<25} : {metadata[tag]['value']}")
            
    print("\n[Image & Pixel Information]")
    print("-" * 60)
    for tag in image_tags:
        if tag in metadata:
            val = metadata[tag]['value']
            # Special formatting for Pixel Data size
            if tag == (0x7fe0, 0x0010):
                val = f"{len(val) if isinstance(val, bytes) else val} bytes"
            print(f"  {metadata[tag]['label']:<25} : {val}")

    print("\n[All Parsed Tags]")
    print("-" * 60)
    row_format = "  ({:04X},{:04X}) {:<25} | {:<4} | {}"
    print(row_format.format("Grp", "Elem", "Name", "VR", "Value"))
    print("  " + "-" * 58)
    for tag, info in sorted(metadata.items()):
        val = info['value']
        if isinstance(val, bytes):
            val = f"<Binary Data: {len(val)} bytes>"
        print(row_format.format(tag[0], tag[1], info['label'][:25], info['vr'], val))
        
    print("=" * 60)
    return 0

if __name__ == "__main__":
    sys.exit(main())
