#!/usr/bin/env python3
"""
Port Forwarder

A mock tool demonstrating a simple port forwarder structure.

Usage:
    python tools/port_forwarder.py --local 8080 --remote 80
"""

import argparse
import sys

def main():
    parser = argparse.ArgumentParser(description="Simple TCP Port Forwarder (Mock)")
    parser.add_argument('--local', type=int, required=True, help='Local port to listen on')
    parser.add_argument('--remote', type=int, required=True, help='Remote port to forward to')
    parser.add_argument('--host', default='127.0.0.1', help='Remote host to forward to')
    args = parser.parse_args()

    print(f"Starting port forwarding from local port {args.local} to {args.host}:{args.remote}...")
    print("(This is a mock implementation. Press Ctrl+C to exit.)")
    
    try:
        # Mock wait
        while True:
            pass
    except KeyboardInterrupt:
        print("\nPort forwarding stopped.")
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
