#!/usr/bin/env python3
"""
Port Listener & HTTP/TCP/UDP Request Dumper
Starts a server on a specified port and dumps all incoming request details (including headers, bodies, and hex representation) to console and/or a log file.
Uses only standard Python libraries.
"""
import argparse
from datetime import datetime
import socket
import sys

def make_hex_dump(data):
    """Generate a clean, classic hex dump of bytes (16 bytes per line)."""
    lines = []
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        hex_part = " ".join(f"{b:02X}" for b in chunk)
        # Pad hex part to align ascii part
        hex_part = hex_part.ljust(47)
        # Printable ascii characters (replace non-printables with dot)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{i:08X}  {hex_part}  |{ascii_part}|")
    return "\n".join(lines)

def parse_http_request(raw_data):
    """
    Attempt to parse raw data as an HTTP request.
    Returns (request_line, headers_dict, body_bytes) if successful, otherwise None.
    """
    try:
        # HTTP headers usually end with double CRLF or double LF
        parts = raw_data.split(b'\r\n\r\n', 1)
        if len(parts) < 2:
            parts = raw_data.split(b'\n\n', 1)
            if len(parts) < 2:
                return None
                
        header_section, body = parts
        header_lines = header_section.decode('utf-8', errors='ignore').splitlines()
        
        if not header_lines:
            return None
            
        request_line = header_lines[0]
        # Verify request line resembles HTTP (e.g. "GET / HTTP/1.1")
        if not any(request_line.startswith(method) for method in ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS", "CONNECT", "TRACE"]):
            if "HTTP/" not in request_line:
                return None
                
        headers = {}
        for line in header_lines[1:]:
            if ":" in line:
                key, val = line.split(":", 1)
                headers[key.strip()] = val.strip()
                
        return request_line, headers, body
    except Exception:
        return None

def log_message(msg, log_file=None):
    """Print message and optionally write to log file."""
    print(msg)
    if log_file:
        try:
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(msg + '\n')
        except Exception as e:
            print(f"Error writing to log file: {e}", file=sys.stderr)

def start_tcp_server(host, port, response_data, log_file=None):
    """Run TCP Listener and HTTP/Raw parser."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Allow port reuse immediately
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server_socket.bind((host, port))
        server_socket.listen(5)
    except Exception as e:
        print(f"Error binding to {host}:{port} - {e}", file=sys.stderr)
        sys.exit(1)
        
    start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_message(f"[*] TCP Request Dumper listening on {host}:{port} (Started: {start_time})", log_file)
    log_message("[*] Press Ctrl+C to stop.\n", log_file)
    
    try:
        while True:
            client_socket, client_address = server_socket.accept()
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            log_message(f"[{timestamp}] New connection from {client_address[0]}:{client_address[1]}", log_file)
            
            # Read data (up to 64KB)
            try:
                raw_data = client_socket.recv(65536)
                if not raw_data:
                    log_message(f"[{timestamp}] Connection closed with no data.", log_file)
                    client_socket.close()
                    continue
                    
                log_message("-" * 60, log_file)
                log_message(f"Received {len(raw_data)} bytes:", log_file)
                
                # Check if it looks like HTTP
                http_parse = parse_http_request(raw_data)
                if http_parse:
                    req_line, headers, body = http_parse
                    log_message(f"  [HTTP Protocol Detected]", log_file)
                    log_message(f"  Request: {req_line}", log_file)
                    log_message("  Headers:", log_file)
                    for k, v in headers.items():
                        log_message(f"    {k}: {v}", log_file)
                    
                    if body:
                        log_message("  Body:", log_file)
                        try:
                            # Try printing body as text
                            body_text = body.decode('utf-8')
                            log_message(f"    {body_text}", log_file)
                        except UnicodeDecodeError:
                            log_message("    [Binary body payload]", log_file)
                            log_message(make_hex_dump(body), log_file)
                else:
                    log_message("  [Raw TCP Data]", log_file)
                    try:
                        # Try decoding raw data as text
                        text_data = raw_data.decode('utf-8')
                        log_message(text_data, log_file)
                    except UnicodeDecodeError:
                        # Fallback to hex dump if binary
                        log_message(make_hex_dump(raw_data), log_file)
                
                log_message("-" * 60 + "\n", log_file)
                
                # Send response
                if response_data:
                    client_socket.sendall(response_data)
                else:
                    # Default HTTP response if request looks like HTTP
                    if http_parse:
                        http_response = (
                            b"HTTP/1.1 200 OK\r\n"
                            b"Content-Type: text/plain\r\n"
                            b"Connection: close\r\n\r\n"
                            b"Request received successfully by Request Dumper."
                        )
                        client_socket.sendall(http_response)
                    else:
                        client_socket.sendall(b"OK\n")
                        
            except Exception as e:
                log_message(f"Error handling connection: {e}", log_file)
            finally:
                client_socket.close()
                
    except KeyboardInterrupt:
        log_message("\n[*] Stopping TCP Server...", log_file)
    finally:
        server_socket.close()

def start_udp_server(host, port, response_data, log_file=None):
    """Run UDP Listener."""
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    
    try:
        server_socket.bind((host, port))
    except Exception as e:
        print(f"Error binding to UDP {host}:{port} - {e}", file=sys.stderr)
        sys.exit(1)
        
    start_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    log_message(f"[*] UDP Request Dumper listening on {host}:{port} (Started: {start_time})", log_file)
    log_message("[*] Press Ctrl+C to stop.\n", log_file)
    
    try:
        while True:
            raw_data, client_address = server_socket.recvfrom(65536)
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            log_message(f"[{timestamp}] Packet received from {client_address[0]}:{client_address[1]}", log_file)
            log_message("-" * 60, log_file)
            log_message(f"Received {len(raw_data)} bytes:", log_file)
            
            try:
                text_data = raw_data.decode('utf-8')
                log_message(text_data, log_file)
            except UnicodeDecodeError:
                log_message(make_hex_dump(raw_data), log_file)
                
            log_message("-" * 60 + "\n", log_file)
            
            # Send optional response
            if response_data:
                try:
                    server_socket.sendto(response_data, client_address)
                except Exception as e:
                    log_message(f"Error sending UDP response: {e}", log_file)
                    
    except KeyboardInterrupt:
        log_message("\n[*] Stopping UDP Server...", log_file)
    finally:
        server_socket.close()

def main():
    parser = argparse.ArgumentParser(description="Start a port listener to log and dump incoming connection details and data.")
    parser.add_argument("-p", "--port", type=int, default=8080, help="Port to listen on (default: 8080)")
    parser.add_argument("-i", "--interface", default="0.0.0.0", help="Network interface to bind to (default: 0.0.0.0)")
    parser.add_argument("-u", "--udp", action="store_true", help="Use UDP protocol instead of TCP")
    parser.add_argument("-l", "--log-file", help="Path to file where request dumps will be saved")
    parser.add_argument("-r", "--response", help="Custom text response to send back to client")
    parser.add_argument("--raw-response", help="Custom raw response (supports escape sequences like \\r\\n)")
    
    args = parser.parse_args()
    
    # Configure response bytes
    response_bytes = None
    if args.raw_response:
        response_bytes = args.raw_response.encode('utf-8').decode('unicode_escape').encode('utf-8')
    elif args.response:
        response_bytes = args.response.encode('utf-8')
        
    if args.udp:
        start_udp_server(args.interface, args.port, response_bytes, args.log_file)
    else:
        start_tcp_server(args.interface, args.port, response_bytes, args.log_file)

if __name__ == "__main__":
    main()
