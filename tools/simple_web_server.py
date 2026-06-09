#!/usr/bin/env python3
"""
Simple Web Server - A standalone HTTP server utility.
Serves a directory over HTTP, providing basic access logs, directory listing,
and customizable address and port settings.
"""

import argparse
import os
import sys
from http.server import SimpleHTTPRequestHandler, HTTPServer

def create_handler(directory, log_file=None, quiet=False):
    """Factory to create a Custom HTTP Request Handler serving a specific directory."""
    # Resolve directory path to absolute
    normalized_dir = os.path.abspath(directory)
    
    class CustomHTTPRequestHandler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            # In Python 3.7+, SimpleHTTPRequestHandler accepts a directory argument
            super().__init__(*args, directory=normalized_dir, **kwargs)
            
        def log_message(self, format_str, *args):
            # Format custom log message
            message = "%s - - [%s] %s\n" % (
                self.client_address[0],
                self.log_date_time_string(),
                format_str % args
            )
            
            if not quiet:
                # Write to stdout with a [LOG] prefix
                sys.stdout.write(f"[LOG] {message}")
                sys.stdout.flush()
                
            if log_file:
                try:
                    with open(log_file, "a", encoding="utf-8") as f:
                        f.write(message)
                except Exception as e:
                    sys.stderr.write(f"[ERROR] Could not write to log file: {e}\n")
                    
    return CustomHTTPRequestHandler

def main():
    parser = argparse.ArgumentParser(
        description="Simple Web Server - Start a lightweight HTTP server to serve local files."
    )
    parser.add_argument(
        "-p", "--port", 
        type=int, 
        default=8000, 
        help="Port number to listen on (default: 8000)"
    )
    parser.add_argument(
        "-b", "--bind", 
        default="127.0.0.1", 
        help="IP address to bind the server to (default: 127.0.0.1). Use 0.0.0.0 to listen on all interfaces."
    )
    parser.add_argument(
        "-d", "--directory", 
        default=".", 
        help="Directory to serve (default: current working directory)"
    )
    parser.add_argument(
        "-l", "--log", 
        help="Path to an optional file where access logs should be saved"
    )
    parser.add_argument(
        "-q", "--quiet", 
        action="store_true", 
        help="Quiet mode: suppress console log output"
    )

    args = parser.parse_args()

    # Validate target directory
    if not os.path.isdir(args.directory):
        print(f"[ERROR] Specified directory does not exist or is not a directory: {args.directory}", file=sys.stderr)
        sys.exit(1)

    # Resolve log file if path provided
    log_filepath = None
    if args.log:
        try:
            # Check write accessibility to log file path
            log_filepath = os.path.abspath(args.log)
            with open(log_filepath, "a", encoding="utf-8") as f:
                pass
        except Exception as e:
            print(f"[ERROR] Log file is not writable: {e}", file=sys.stderr)
            sys.exit(1)

    # Create HTTP handler with directory and logging configuration
    handler_class = create_handler(args.directory, log_file=log_filepath, quiet=args.quiet)

    # Start the server
    try:
        server = HTTPServer((args.bind, args.port), handler_class)
    except Exception as e:
        print(f"[ERROR] Could not start server on {args.bind}:{args.port} - {e}", file=sys.stderr)
        sys.exit(1)

    # Print startup info
    print(f"[OK] Simple HTTP Server started!")
    print(f"     Serving directory:  {os.path.abspath(args.directory)}")
    print(f"     URL:                http://{args.bind}:{args.port}/")
    print(f"     Press Ctrl+C to stop.")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[INFO] Keyboard interrupt received. Shutting down server...")
    finally:
        server.server_close()
        print("[OK] Server stopped.")

if __name__ == "__main__":
    main()
