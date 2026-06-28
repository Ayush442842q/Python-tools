#!/usr/bin/env python3
"""
QR Code Reader & Scanner Tool
Reads and decodes QR codes from image files or webcam.
"""

import argparse
import sys
from pathlib import Path

try:
    import cv2
    from pyzbar.pyzbar import decode
    HAS_ZBAR = True
except ImportError:
    HAS_ZBAR = False


def decode_qr_from_image(image_path: str) -> list:
    """Decode QR codes from an image file."""
    try:
        import cv2
        from pyzbar.pyzbar import decode
    except ImportError:
        print("Error: Required packages not installed.")
        print("Install with: pip install opencv-python pyzbar")
        sys.exit(1)
    
    img = cv2.imread(image_path)
    if img is None:
        print(f"Error: Could not read image '{image_path}'")
        sys.exit(1)
    
    qr_codes = decode(img)
    results = []
    
    for qr in qr_codes:
        qr_data = qr.data.decode('utf-8')
        qr_type = qr.type
        rect = qr.rect
        results.append({
            'data': qr_data,
            'type': qr_type,
            'position': {
                'left': rect.left,
                'top': rect.top,
                'width': rect.width,
                'height': rect.height
            }
        })
    
    return results


def decode_qr_from_webcam(timeout: int = 30):
    """Capture and decode QR codes from webcam."""
    try:
        import cv2
        from pyzbar.pyzbar import decode
    except ImportError:
        print("Error: Required packages not installed.")
        print("Install with: pip install opencv-python pyzbar")
        sys.exit(1)
    
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Error: Could not access webcam")
        sys.exit(1)
    
    print("QR Code Scanner - Point camera at QR code (Press 'q' to quit)")
    print("-" * 50)
    
    frame_count = 0
    max_frames = timeout * 30  # Approx 30 FPS
    
    while frame_count < max_frames:
        ret, frame = cap.read()
        if not ret:
            break
        
        qr_codes = decode(frame)
        
        for qr in qr_codes:
            qr_data = qr.data.decode('utf-8')
            print(f"\n✓ QR Code Detected!")
            print(f"  Type: {qr.type}")
            print(f"  Data: {qr_data}")
            print(f"  Position: ({qr.rect.left}, {qr.rect.top})")
            print(f"  Size: {qr.rect.width}x{qr.rect.height}")
            print("-" * 50)
            
            cap.release()
            return qr_data
        
        frame_count += 1
    
    cap.release()
    print("No QR code detected within timeout period")
    return None


def main():
    parser = argparse.ArgumentParser(
        description='QR Code Reader & Scanner - Decode QR codes from images or webcam'
    )
    parser.add_argument(
        'image',
        nargs='?',
        help='Path to image file containing QR code'
    )
    parser.add_argument(
        '-w', '--webcam',
        action='store_true',
        help='Use webcam to scan QR codes'
    )
    parser.add_argument(
        '-t', '--timeout',
        type=int,
        default=30,
        help='Webcam timeout in seconds (default: 30)'
    )
    parser.add_argument(
        '-o', '--output',
        choices=['text', 'json'],
        default='text',
        help='Output format (default: text)'
    )
    
    args = parser.parse_args()
    
    if not HAS_ZBAR:
        print("Error: pyzbar not installed")
        print("Install with: pip install opencv-python pyzbar")
        print("\nAlternatively, install system package:")
        print("  Windows: Download zbar DLLs from https://github.com/letmaik/pyzbar")
        print("  Ubuntu/Debian: sudo apt-get install libzbar0")
        print("  macOS: brew install zbar")
        sys.exit(1)
    
    if args.webcam:
        result = decode_qr_from_webcam(args.timeout)
        if result:
            sys.exit(0)
        sys.exit(1)
    
    if args.image:
        image_path = Path(args.image)
        if not image_path.exists():
            print(f"Error: File '{args.image}' not found")
            sys.exit(1)
        
        results = decode_qr_from_image(str(image_path))
        
        if not results:
            print("No QR codes found in image")
            sys.exit(1)
        
        if args.output == 'json':
            import json
            print(json.dumps(results, indent=2))
        else:
            for i, qr in enumerate(results, 1):
                print(f"\nQR Code #{i}")
                print(f"  Type: {qr['type']}")
                print(f"  Data: {qr['data']}")
                print(f"  Position: ({qr['position']['left']}, {qr['position']['top']})")
                print(f"  Size: {qr['position']['width']}x{qr['position']['height']}")
        
        sys.exit(0)
    
    parser.print_help()
    sys.exit(1)


if __name__ == '__main__':
    main()