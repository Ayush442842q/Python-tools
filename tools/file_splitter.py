#!/usr/bin/env python3
"""
File Splitter/Joiner - Split large files into parts and rejoin them.

This utility splits large files into smaller chunks for easier transfer
and can rejoin them back into the original file.
"""

import os
import sys
import argparse
from pathlib import Path
import math


def split_file(
    input_path: Path,
    output_dir: Path,
    part_size: int,
    prefix: str = None,
) -> List[Path]:
    """
    Split a file into parts.
    
    Args:
        input_path: Path to file to split
        output_dir: Directory to put parts in
        part_size: Size of each part in bytes
        prefix: Prefix for part files (defaults to input filename)
        
    Returns:
        List of part file paths
    """
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    
    if prefix is None:
        prefix = input_path.name
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    part_files = []
    part_num = 1
    
    with open(input_path, 'rb') as infile:
        while True:
            chunk = infile.read(part_size)
            if not chunk:
                break
            
            part_filename = f"{prefix}.part{part_num:03d}"
            part_path = output_dir / part_filename
            
            with open(part_path, 'wb') as outfile:
                outfile.write(chunk)
            
            part_files.append(part_path)
            part_num += 1
    
    return part_files


def join_files(
    input_dir: Path,
    output_path: Path,
    prefix: str,
    cleanup: bool = False,
) -> Path:
    """
    Join split files back together.
    
    Args:
        input_dir: Directory containing part files
        output_path: Path for the joined output file
        prefix: Prefix of the part files
        cleanup: Whether to delete part files after joining
        
    Returns:
        Path to the joined file
    """
    # Find all part files
    pattern = f"{prefix}.part*"
    part_files = sorted(input_dir.glob(pattern))
    
    if not part_files:
        raise FileNotFoundError(f"No part files found matching {pattern} in {input_dir}")
    
    # Verify we have sequential parts
    expected_num = 1
    for part_file in part_files:
        # Extract number from filename like "file.part001"
        try:
            num_str = part_file.name.split('.part')[-1]
            num = int(num_str)
            if num != expected_num:
                raise ValueError(f"Missing part {expected_num}, found {num}")
            expected_num += 1
        except (ValueError, IndexError):
            raise ValueError(f"Invalid part filename: {part_file.name}")
    
    # Join the files
    with open(output_path, 'wb') as outfile:
        for part_file in part_files:
            with open(part_file, 'rb') as infile:
                outfile.write(infile.read())
    
    # Cleanup if requested
    if cleanup:
        for part_file in part_files:
            part_file.unlink()
    
    return output_path


def parse_size(size_str: str) -> int:
    """Parse size string like '10M', '1G', etc. into bytes."""
    size_str = size_str.upper().strip()
    units = {
        'B': 1,
        'K': 1024,
        'M': 1024**2,
        'G': 1024**3,
        'T': 1024**4
    }
    
    if size_str[-1] in units:
        try:
            number = float(size_str[:-1])
            return int(number * units[size_str[-1]])
        except ValueError:
            pass
    
    # Try as plain bytes
    try:
        return int(size_str)
    except ValueError:
        raise ValueError(f"Invalid size format: {size_str}")


def main():
    """Main entry point for the file splitter/joiner."""
    parser = argparse.ArgumentParser(
        description="Split large files into parts and rejoin them",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Split examples:
  %(prog)s split large_file.iso --size 100M --output parts/
  %(prog)s split movie.mkv -s 500M -o chunks/

Join examples:
  %(prog)s join parts/ --output large_file.iso --prefix large_file.iso
  %(prog)s join chunks/ -o movie.mkv --prefix movie.mkv --cleanup
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Split command
    split_parser = subparsers.add_parser('split', help='Split a file into parts')
    split_parser.add_argument('input_file', type=str, help='File to split')
    split_parser.add_argument('-s', '--size', type=str, required=True,
                            help='Size of each part (e.g., 10M, 1G)')
    split_parser.add_argument('-o', '--output', type=str, required=True,
                            help='Output directory for parts')
    split_parser.add_argument('-p', '--prefix', type=str,
                            help='Prefix for part files (defaults to input filename)')
    
    # Join command
    join_parser = subparsers.add_parser('join', help='Join split files')
    join_parser.add_argument('input_dir', type=str, help='Directory containing part files')
    join_parser.add_argument('-o', '--output', type=str, required=True,
                            help='Output file path')
    join_parser.add_argument('-p', '--prefix', type=str, required=True,
                            help='Prefix of the part files')
    join_parser.add_argument('-c', '--cleanup', action='store_true',
                            help='Delete part files after joining')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    try:
        if args.command == 'split':
            input_path = Path(args.input_file).expanduser().resolve()
            output_dir = Path(args.output).expanduser().resolve()
            part_size = parse_size(args.size)
            
            print(f"Splitting: {input_path}")
            print(f"Part size: {part_size:,} bytes")
            print(f"Output directory: {output_dir}")
            
            part_files = split_file(input_path, output_dir, part_size, args.prefix)
            
            print(f"\nSplit complete! Created {len(part_files)} parts:")
            for i, part_file in enumerate(part_files, 1):
                size = part_file.stat().st_size
                print(f"  {i:3d}. {part_file.name} ({size:,} bytes)")
            
        elif args.command == 'join':
            input_dir = Path(args.input_dir).expanduser().resolve()
            output_path = Path(args.output).expanduser().resolve()
            
            print(f"Joining parts from: {input_dir}")
            print(f"Prefix: {args.prefix}")
            print(f"Output file: {output_path}")
            
            joined_file = join_files(input_dir, output_path, args.prefix, args.cleanup)
            
            size = joined_file.stat().st_size
            print(f"\nJoin complete! Created: {joined_file}")
            print(f"Size: {size:,} bytes")
            
            if args.cleanup:
                print("Part files have been deleted.")
    
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()