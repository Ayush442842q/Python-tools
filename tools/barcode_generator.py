#!/usr/bin/env python3
"""
Barcode Generator & Scanner Tool
Generate and scan 1D barcodes (EAN, UPC, Code 128, Code 39, etc.)
"""

import argparse
import sys
from pathlib import Path

try:
    import barcode
    from barcode.writer import ImageWriter
    HAS_BARCODE = True
except ImportError:
    HAS_BARCODE = False

try:
    import cv2
    from pyzbar.pyzbar import decode
    HAS_ZBAR = True
except ImportError:
    HAS_ZBAR = False


def generate_barcode(data: str, barcode_type: str, output_path: str, 
                     width: int = 3, height: int = 1, 
                     text: bool = True, padding: int = 10):
    """Generate a barcode image."""
    try:
        import barcode
        from barcode.writer import ImageWriter
    except ImportError:
        print("Error: python-barcode not installed")
        print("Install with: pip install python-barcode")
        sys.exit(1)
    
    barcode_class = barcode.get_barcode_class(barcode_type)
    
    writer = ImageWriter()
    writer_options = {
        'module_width': width,
        'module_height': height,
        'font_size': 10,
        'text': text,
        'margin': padding,
    }
    
    try:
        code = barcode_class(data, writer=writer)
    except barcode.errors.BarcodeError as e:
        print(f"Error: {e}")
        sys.exit(1)
    
    output_file = code.save(output_path, options=writer_options)
    print(f"Barcode generated: {output_file}")
    return output_file


def scan_barcode_from_image(image_path: str) -> list:
    """Scan barcodes from an image file."""
    try:
        import cv2
        from pyzbar.pyzbar import decode
    except ImportError:
        print("Error: Required packages not installed")
        print("Install with: pip install opencv-python pyzbar")
        sys.exit(1)
    
    img = cv2.imread(image_path)
    if img is None:
        print(f"Error: Could not read image '{image_path}'")
        sys.exit(1)
    
    barcodes = decode(img)
    results = []
    
    for bc in barcodes:
        bc_data = bc.data.decode('utf-8')
        bc_type = bc.type
        rect = bc.rect
        results.append({
            'data': bc_data,
            'type': bc_type,
            'position': {
                'left': rect.left,
                'top': rect.top,
                'width': rect.width,
                'height': rect.height
            }
        })
    
    return results


def list_supported_formats():
    """List all supported barcode formats."""
    try:
        import barcode
    except ImportError:
        print("Error: python-barcode not installed")
        sys.exit(1)
    
    formats = barcode.PROVIDED_BARCODES
    print("Supported Barcode Formats:")
    print("-" * 40)
    for fmt in sorted(formats):
        print(f"  - {fmt}")
    print("\nCommon formats:")
    print("  ean13     - European Article Number (13 digits)")
    print("  ean8      - European Article Number (8 digits)")
    print("  upc       - Universal Product Code")
    print("  code128   - Code 128 (alphanumeric)")
    print("  code39    - Code 39 (alphanumeric)")
    print("  i25       - Industrial 2 of 5 (numeric)")
    print("  isbn      - International Standard Book Number")
    print("  isbn13    - ISBN-13")
    print("  codabar   - Codabar (numeric with special chars)")
    print("  gs1       - GS1-128")


def main():
    parser = argparse.ArgumentParser(
        description='Barcode Generator & Scanner - Create and read 1D barcodes'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to execute')
    
    # Generate command
    gen_parser = subparsers.add_parser('generate', help='Generate a barcode')
    gen_parser.add_argument('data', help='Data to encode in barcode')
    gen_parser.add_argument('-t', '--type', default='code128',
                           help='Barcode type (default: code128)')
    gen_parser.add_argument('-o', '--output', default='barcode',
                           help='Output filename without extension')
    gen_parser.add_argument('-w', '--width', type=float, default=3,
                           help='Module width (default: 3)')
    gen_parser.add_argument('-H', '--height', type=float, default=1,
                           help='Module height (default: 1)')
    gen_parser.add_argument('--no-text', action='store_true',
                           help='Do not display text below barcode')
    gen_parser.add_argument('-p', '--padding', type=int, default=10,
                           help='Margin padding (default: 10)')
    
    # Scan command
    scan_parser = subparsers.add_parser('scan', help='Scan barcode from image')
    scan_parser.add_argument('image', help='Path to barcode image')
    scan_parser.add_argument('-o', '--output', choices=['text', 'json'],
                            default='text', help='Output format')
    
    # List command
    subparsers.add_parser('list', help='List supported barcode formats')
    
    args = parser.parse_args()
    
    if args.command == 'list':
        list_supported_formats()
        sys.exit(0)
    
    if args.command == 'generate':
        if not HAS_BARCODE:
            print("Error: python-barcode not installed")
            print("Install with: pip install python-barcode")
            sys.exit(1)
        
        output_path = generate_barcode(
            data=args.data,
            barcode_type=args.type,
            output_path=args.output,
            width=args.width,
            height=args.height,
            text=not args.no_text,
            padding=args.padding
        )
        print(f"Successfully generated {args.type} barcode")
        sys.exit(0)
    
    if args.command == 'scan':
        if not HAS_ZBAR:
            print("Error: pyzbar not installed")
            print("Install with: pip install opencv-python pyzbar")
            sys.exit(1)
        
        image_path = Path(args.image)
        if not image_path.exists():
            print(f"Error: File '{args.image}' not found")
            sys.exit(1)
        
        results = scan_barcode_from_image(str(image_path))
        
        if not results:
            print("No barcodes found in image")
            sys.exit(1)
        
        if args.output == 'json':
            import json
            print(json.dumps(results, indent=2))
        else:
            for i, bc in enumerate(results, 1):
                print(f"\nBarcode #{i}")
                print(f"  Type: {bc['type']}")
                print(f"  Data: {bc['data']}")
                print(f"  Position: ({bc['position']['left']}, {bc['position']['top']})")
        
        sys.exit(0)
    
    parser.print_help()
    sys.exit(1)


if __name__ == '__main__':
    main()