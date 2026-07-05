#!/usr/bin/env python3
"""
SQLite BLOB Extractor & Magic Byte Detector

Scans SQLite databases for binary/BLOB columns, identifies file types using
magic byte signatures (PNG, JPEG, PDF, ZIP, MP3, etc.), extracts files to disk,
and generates a structured manifest log.
"""

import os
import sys
import sqlite3
import json
import argparse
from pathlib import Path

# Terminal Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Magic Byte Definitions for File Signature Detection
MAGIC_SIGNATURES = [
    (b'\x89PNG\r\n\x1a\n', '.png', 'Image (PNG)'),
    (b'\xff\xd8\xff', '.jpg', 'Image (JPEG)'),
    (b'GIF87a', '.gif', 'Image (GIF)'),
    (b'GIF89a', '.gif', 'Image (GIF)'),
    (b'RIFF', '.webp', 'Image (WEBP)'), # Special check for WEBP in RIFF header
    (b'%PDF-', '.pdf', 'Document (PDF)'),
    (b'PK\x03\x04', '.zip', 'Archive (ZIP/DOCX/XLSX)'),
    (b'PK\x05\x06', '.zip', 'Archive (ZIP Empty)'),
    (b'\x1f\x8b\x08', '.tar.gz', 'Archive (GZIP)'),
    (b'ID3', '.mp3', 'Audio (MP3)'),
    (b'\xff\xfb', '.mp3', 'Audio (MP3)'),
    (b'OggS', '.ogg', 'Audio/Video (OGG)'),
    (b'fLaC', '.flac', 'Audio (FLAC)'),
    (b'RIFF', '.wav', 'Audio (WAV)'),
    (b'SQLite format 3\x00', '.sqlite', 'Database (SQLite)'),
    (b'MZ', '.exe', 'Executable (DOS/Windows)'),
    (b'\x7fELF', '.elf', 'Executable (Linux ELF)'),
    (b'BM', '.bmp', 'Image (BMP)'),
    (b'{\\rtf', '.rtf', 'Document (Rich Text)'),
    (b'<\x3fxml', '.xml', 'Document (XML)'),
]


def detect_file_type(blob_data):
    """Detects file extension and human-readable description from blob bytes."""
    if not blob_data or not isinstance(blob_data, (bytes, bytearray)):
        return '.bin', 'Unknown Binary'

    for signature, ext, desc in MAGIC_SIGNATURES:
        if blob_data.startswith(signature):
            if signature == b'RIFF':
                # Check 8-12 bytes for WEBP vs WAV
                if len(blob_data) >= 12:
                    sub_type = blob_data[8:12]
                    if sub_type == b'WEBP':
                        return '.webp', 'Image (WEBP)'
                    elif sub_type == b'WAVE':
                        return '.wav', 'Audio (WAV)'
            return ext, desc

    return '.bin', 'Unknown Binary Data'


def get_tables_with_blobs(conn):
    """Finds tables and blob columns in the SQLite database."""
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    tables = [row[0] for row in cursor.fetchall()]

    table_blob_map = {}

    for table in tables:
        cursor.execute(f"PRAGMA table_info('{table}');")
        columns = cursor.fetchall()
        # columns: (cid, name, type, notnull, dflt_value, pk)
        pk_col = next((c[1] for c in columns if c[5] > 0), columns[0][1] if columns else 'rowid')
        
        blob_cols = []
        for col in columns:
            col_name = col[1]
            col_type = col[2].upper()
            if 'BLOB' in col_type or 'BINARY' in col_type or col_type == '':
                blob_cols.append(col_name)
            else:
                # Sample table rows to detect unregistered BLOBs
                try:
                    cursor.execute(f"SELECT typeof(\"{col_name}\") FROM \"{table}\" WHERE \"{col_name}\" IS NOT NULL LIMIT 5;")
                    types = [r[0] for r in cursor.fetchall()]
                    if 'blob' in types:
                        blob_cols.append(col_name)
                except Exception:
                    pass

        if blob_cols:
            table_blob_map[table] = {'pk': pk_col, 'blob_cols': blob_cols}

    return table_blob_map


def extract_blobs_from_db(db_path, output_dir, target_table=None, limit=None):
    """Extracts BLOB data into files and returns manifest report."""
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database file '{db_path}' not found.")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    tables_map = get_tables_with_blobs(conn)
    manifest = []

    if target_table:
        if target_table not in tables_map:
            print(f"{YELLOW}[WARNING]{RESET} Table '{target_table}' not found or contains no BLOB columns.", file=sys.stderr)
            return manifest
        tables_to_process = {target_table: tables_map[target_table]}
    else:
        tables_to_process = tables_map

    total_extracted = 0

    for table_name, meta in tables_to_process.items():
        pk_col = meta['pk']
        blob_cols = meta['blob_cols']

        cursor = conn.cursor()
        query = f"SELECT \"{pk_col}\", {', '.join(['\"' + c + '\"' for c in blob_cols])} FROM \"{table_name}\""
        if limit:
            query += f" LIMIT {limit}"

        try:
            cursor.execute(query)
            rows = cursor.fetchall()
        except Exception as e:
            print(f"{RED}[ERROR]{RESET} Failed querying table '{table_name}': {e}", file=sys.stderr)
            continue

        for row in rows:
            pk_val = row[pk_col]
            for col_name in blob_cols:
                blob_data = row[col_name]
                if not blob_data or not isinstance(blob_data, (bytes, bytearray)):
                    continue

                ext, desc = detect_file_type(blob_data)
                filename = f"{table_name}_{col_name}_pk{pk_val}{ext}"
                target_folder = os.path.join(output_dir, table_name, col_name)
                os.makedirs(target_folder, exist_ok=True)
                target_path = os.path.join(target_folder, filename)

                with open(target_path, 'wb') as f:
                    f.write(blob_data)

                total_extracted += 1
                manifest.append({
                    'table': table_name,
                    'column': col_name,
                    'pk_value': pk_val,
                    'bytes': len(blob_data),
                    'extension': ext,
                    'type_description': desc,
                    'output_path': target_path
                })

    conn.close()
    return manifest


def main():
    parser = argparse.ArgumentParser(
        description="SQLite BLOB Extractor - Export binary column payloads into files with magic byte detection."
    )
    parser.add_argument("db_file", help="Path to SQLite database file")
    parser.add_argument("-o", "--output-dir", default="extracted_blobs", help="Output directory path (default: ./extracted_blobs)")
    parser.add_argument("-t", "--table", help="Specific table name to extract")
    parser.add_argument("-l", "--limit", type=int, help="Maximum number of rows to extract per table")
    parser.add_argument("-m", "--manifest", help="Save extraction JSON manifest to path")

    args = parser.parse_args()

    try:
        manifest = extract_blobs_from_db(args.db_file, args.output_dir, target_table=args.table, limit=args.limit)
        
        print(f"{GREEN}[SUCCESS]{RESET} Extracted {len(manifest)} BLOB files to '{args.output_dir}'.")
        
        if args.manifest:
            with open(args.manifest, 'w', encoding='utf-8') as f:
                json.dump(manifest, f, indent=2)
            print(f"{GREEN}[SUCCESS]{RESET} Manifest saved to '{args.manifest}'.")

    except Exception as e:
        print(f"{RED}[ERROR]{RESET} {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
