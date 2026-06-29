#!/usr/bin/env python3
"""
PDF Page Editor
A command-line utility and interactive wizard to edit PDF files.
Supports merging multiple PDFs, splitting/extracting page ranges,
deleting specific pages, and rotating pages.
"""

import os
import sys
import argparse
from typing import List, Set

# Attempt to load standard PDF library, notify user if missing
try:
    import pypdf
    PDF_LIB = "pypdf"
except ImportError:
    try:
        import PyPDF2 as pypdf
        PDF_LIB = "PyPDF2"
    except ImportError:
        pypdf = None
        PDF_LIB = None

def check_pdf_library():
    """Verify that pypdf is installed, otherwise exit with instructions."""
    if pypdf is None:
        print("[-] Error: A PDF library is required to run this tool.", file=sys.stderr)
        print("[*] Please install the 'pypdf' package by running:", file=sys.stderr)
        print("    pip install pypdf", file=sys.stderr)
        sys.exit(1)

def parse_page_range(range_str: str, max_pages: int) -> List[int]:
    """
    Parse a page range string (e.g. '1-3, 5, 7-9') into a list of 0-based page indices.
    Validates range against max_pages.
    """
    pages = []
    if not range_str.strip():
        return list(range(max_pages))
    
    parts = range_str.split(',')
    for part in parts:
        part = part.strip()
        if '-' in part:
            try:
                start_str, end_str = part.split('-')
                start = int(start_str.strip())
                end = int(end_str.strip())
                
                # Convert 1-indexed to 0-indexed
                start_idx = max(0, start - 1)
                end_idx = min(max_pages, end)
                
                pages.extend(range(start_idx, end_idx))
            except ValueError:
                print(f"[!] Warning: Invalid range format: '{part}'. Skipping.", file=sys.stderr)
        else:
            try:
                val = int(part)
                idx = val - 1
                if 0 <= idx < max_pages:
                    pages.append(idx)
                else:
                    print(f"[!] Warning: Page {val} is out of bounds (max: {max_pages}). Skipping.", file=sys.stderr)
            except ValueError:
                print(f"[!] Warning: Invalid page number: '{part}'. Skipping.", file=sys.stderr)
    
    # Remove duplicates but maintain parsed order
    seen = set()
    unique_pages = []
    for p in pages:
        if p not in seen:
            seen.add(p)
            unique_pages.append(p)
            
    return unique_pages

def pdf_merge(input_files: List[str], output_file: str):
    """Merge multiple PDF files into one output PDF."""
    check_pdf_library()
    merger = pypdf.PdfMerger()
    print(f"[*] Merging {len(input_files)} PDFs into '{output_file}'...")
    
    try:
        for filepath in input_files:
            if not os.path.exists(filepath):
                print(f"[-] Error: File not found: '{filepath}'", file=sys.stderr)
                return False
            merger.append(filepath)
        
        with open(output_file, 'wb') as f:
            merger.write(f)
        
        merger.close()
        print(f"[+] Successfully merged PDFs into '{output_file}'.")
        return True
    except Exception as e:
        print(f"[-] Error during merge: {e}", file=sys.stderr)
        return False

def pdf_split(input_file: str, range_str: str, output_file: str):
    """Extract a range of pages from a PDF and save to a new file."""
    check_pdf_library()
    if not os.path.exists(input_file):
        print(f"[-] Error: File not found: '{input_file}'", file=sys.stderr)
        return False
        
    try:
        reader = pypdf.PdfReader(input_file)
        writer = pypdf.PdfWriter()
        max_pages = len(reader.pages)
        
        target_pages = parse_page_range(range_str, max_pages)
        if not target_pages:
            print("[-] Error: No valid pages selected for extraction.", file=sys.stderr)
            return False

        print(f"[*] Extracting {len(target_pages)} pages from '{input_file}' into '{output_file}'...")
        for page_idx in target_pages:
            writer.add_page(reader.pages[page_idx])

        with open(output_file, 'wb') as f:
            writer.write(f)
            
        print(f"[+] Successfully saved extracted pages to '{output_file}'.")
        return True
    except Exception as e:
        print(f"[-] Error during split/extraction: {e}", file=sys.stderr)
        return False

def pdf_delete(input_file: str, range_str: str, output_file: str):
    """Delete a range of pages from a PDF and save the rest to a new file."""
    check_pdf_library()
    if not os.path.exists(input_file):
        print(f"[-] Error: File not found: '{input_file}'", file=sys.stderr)
        return False
        
    try:
        reader = pypdf.PdfReader(input_file)
        writer = pypdf.PdfWriter()
        max_pages = len(reader.pages)
        
        pages_to_delete = set(parse_page_range(range_str, max_pages))
        if not pages_to_delete:
            print("[*] No valid pages specified for deletion. Copying original file.")
            pages_to_keep = list(range(max_pages))
        else:
            pages_to_keep = [i for i in range(max_pages) if i not in pages_to_delete]
            
        if not pages_to_keep:
            print("[-] Error: Cannot delete all pages. At least one page must remain.", file=sys.stderr)
            return False

        print(f"[*] Deleting {len(pages_to_delete)} pages; keeping {len(pages_to_keep)} pages.")
        for page_idx in pages_to_keep:
            writer.add_page(reader.pages[page_idx])

        with open(output_file, 'wb') as f:
            writer.write(f)
            
        print(f"[+] Successfully wrote modified PDF to '{output_file}'.")
        return True
    except Exception as e:
        print(f"[-] Error during deletion: {e}", file=sys.stderr)
        return False

def pdf_rotate(input_file: str, range_str: str, angle: int, output_file: str):
    """Rotate a range of pages in a PDF by a specified angle."""
    check_pdf_library()
    if angle not in (90, 180, 270):
        print(f"[-] Error: Invalid rotation angle {angle}. Must be 90, 180, or 270.", file=sys.stderr)
        return False
        
    if not os.path.exists(input_file):
        print(f"[-] Error: File not found: '{input_file}'", file=sys.stderr)
        return False
        
    try:
        reader = pypdf.PdfReader(input_file)
        writer = pypdf.PdfWriter()
        max_pages = len(reader.pages)
        
        pages_to_rotate = set(parse_page_range(range_str, max_pages))
        
        print(f"[*] Rotating specified pages in '{input_file}' by {angle} degrees...")
        for idx in range(max_pages):
            page = reader.pages[idx]
            if idx in pages_to_rotate:
                page.rotate(angle)
            writer.add_page(page)

        with open(output_file, 'wb') as f:
            writer.write(f)
            
        print(f"[+] Successfully saved rotated PDF to '{output_file}'.")
        return True
    except Exception as e:
        print(f"[-] Error during page rotation: {e}", file=sys.stderr)
        return False

def run_wizard():
    """Run an interactive console menu wizard."""
    print("=========================================")
    print("          PDF Page Editor Wizard         ")
    print("=========================================")
    if pypdf is None:
        print("[-] Error: 'pypdf' library is missing.")
        print("Please install it to run the wizard: pip install pypdf")
        sys.exit(1)

    print(f"[i] Using {PDF_LIB} library.")
    print("Select an action:")
    print(" 1) Merge multiple PDFs")
    print(" 2) Extract/Split pages from a PDF")
    print(" 3) Delete pages from a PDF")
    print(" 4) Rotate pages in a PDF")
    print(" 5) Exit")
    
    choice = input("\nEnter choice (1-5): ").strip()
    
    if choice == '1':
        files_str = input("Enter PDF file paths to merge (comma separated): ").strip()
        files = [f.strip() for f in files_str.split(',') if f.strip()]
        if not files:
            print("[-] No files specified.")
            return
        output = input("Enter output PDF file path: ").strip()
        if not output:
            output = "merged_output.pdf"
        pdf_merge(files, output)
        
    elif choice == '2':
        infile = input("Enter input PDF file path: ").strip()
        if not os.path.exists(infile):
            print("[-] File not found.")
            return
        reader = pypdf.PdfReader(infile)
        print(f"[i] PDF has {len(reader.pages)} pages.")
        
        range_str = input("Enter page range to extract (e.g. 1-3, 5, 7-10): ").strip()
        output = input("Enter output PDF file path: ").strip()
        if not output:
            output = "extracted_output.pdf"
        pdf_split(infile, range_str, output)
        
    elif choice == '3':
        infile = input("Enter input PDF file path: ").strip()
        if not os.path.exists(infile):
            print("[-] File not found.")
            return
        reader = pypdf.PdfReader(infile)
        print(f"[i] PDF has {len(reader.pages)} pages.")
        
        range_str = input("Enter page range to delete (e.g. 2, 4-6): ").strip()
        output = input("Enter output PDF file path: ").strip()
        if not output:
            output = "deleted_output.pdf"
        pdf_delete(infile, range_str, output)
        
    elif choice == '4':
        infile = input("Enter input PDF file path: ").strip()
        if not os.path.exists(infile):
            print("[-] File not found.")
            return
        reader = pypdf.PdfReader(infile)
        print(f"[i] PDF has {len(reader.pages)} pages.")
        
        range_str = input("Enter page range to rotate (e.g. 1-2, 5): ").strip()
        try:
            angle = int(input("Enter rotation angle (90, 180, 270): ").strip())
        except ValueError:
            print("[-] Invalid angle.")
            return
        output = input("Enter output PDF file path: ").strip()
        if not output:
            output = "rotated_output.pdf"
        pdf_rotate(infile, range_str, angle, output)
        
    elif choice == '5':
        print("[*] Exiting wizard.")
        sys.exit(0)
    else:
        print("[-] Invalid selection.")

def main():
    parser = argparse.ArgumentParser(description="PDF Page Editor Utility")
    
    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Editing command to run")
    
    # Merge subparser
    merge_p = subparsers.add_parser("merge", help="Merge multiple PDFs into one")
    merge_p.add_argument("inputs", nargs="+", help="Input PDF files")
    merge_p.add_argument("-o", "--output", required=True, help="Output PDF file")
    
    # Split subparser
    split_p = subparsers.add_parser("extract", help="Extract/Split page ranges from PDF")
    split_p.add_argument("input", help="Input PDF file")
    split_p.add_argument("-r", "--range", required=True, help="Page range to extract (e.g. 1-3, 5, 7-10)")
    split_p.add_argument("-o", "--output", required=True, help="Output PDF file")
    
    # Delete subparser
    delete_p = subparsers.add_parser("delete", help="Delete page ranges from PDF")
    delete_p.add_argument("input", help="Input PDF file")
    delete_p.add_argument("-r", "--range", required=True, help="Page range to delete (e.g. 2, 4-6)")
    delete_p.add_argument("-o", "--output", required=True, help="Output PDF file")
    
    # Rotate subparser
    rotate_p = subparsers.add_parser("rotate", help="Rotate pages in PDF")
    rotate_p.add_argument("input", help="Input PDF file")
    rotate_p.add_argument("-r", "--range", required=True, help="Page range to rotate (e.g. 1-5)")
    rotate_p.add_argument("-a", "--angle", type=int, choices=[90, 180, 270], required=True, help="Angle in degrees (90, 180, 270)")
    rotate_p.add_argument("-o", "--output", required=True, help="Output PDF file")
    
    args = parser.parse_args()
    
    if args.command is None:
        # Run interactive wizard if no subcommand was supplied
        try:
            run_wizard()
        except KeyboardInterrupt:
            print("\n[!] Exited by user.")
        return
        
    if args.command == "merge":
        pdf_merge(args.inputs, args.output)
    elif args.command == "extract":
        pdf_split(args.input, args.range, args.output)
    elif args.command == "delete":
        pdf_delete(args.input, args.range, args.output)
    elif args.command == "rotate":
        pdf_rotate(args.input, args.range, args.angle, args.output)

if __name__ == "__main__":
    main()
