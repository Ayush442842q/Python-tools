#!/usr/bin/env python3
"""
HTTP Proxy Debugger

A lightweight local HTTP/HTTPS debugging proxy server.
It logs all traffic traversing through it, displaying HTTP request/response details,
HTTP headers, status codes, and HTTPS connection tunnels in colorized terminal output.

Usage:
    python http_proxy_debugger.py --port 8888
    # In another terminal:
    curl -x http://localhost:8888 http://example.com
"""

import sys
import socket
import select
import argparse
import threading
from datetime import datetime

# ANSI Colors for logging
C_BLUE = "\033[94m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_RED = "\033[91m"
C_BOLD = "\033[1m"
C_RESET = "\033[0m"

def log_message(prefix: str, color: str, msg: str):
    """Print time-stamped message with color prefix."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    print(f"[{timestamp}] {color}{prefix:<8}{C_RESET} | {msg}")

def parse_request_line(request_line: str) -> tuple:
    """Parse HTTP request line into (method, url, version)."""
    parts = request_line.split()
    if len(parts) >= 3:
        return parts[0], parts[1], parts[2]
    elif len(parts) == 2:
        return parts[0], parts[1], "HTTP/1.0"
    return "", "", ""

def parse_host_port(url: str, method: str) -> tuple:
    """Extract host and port from URL or method."""
    port = 80
    host = ""
    
    if method == "CONNECT":
        # HTTPS CONNECT request has host:port structure
        parts = url.split(":")
        host = parts[0]
        port = int(parts[1]) if len(parts) > 1 else 443
    else:
        # HTTP request has full URL or host header
        # Check if URL starts with http://
        if url.startswith("http://"):
            url = url[7:]
        elif url.startswith("https://"):
            url = url[8:]
            port = 443
            
        parts = url.split("/")[0].split(":")
        host = parts[0]
        if len(parts) > 1:
            port = int(parts[1])
            
    return host, port

def handle_https_tunnel(client_conn: socket.socket, target_host: str, target_port: int):
    """Establishes a raw TCP tunnel for HTTPS (CONNECT method)."""
    try:
        # Connect to destination server
        target_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        target_conn.settimeout(10.0)
        target_conn.connect((target_host, target_port))
        
        # Send successful CONNECT response to client
        client_conn.sendall(b"HTTP/1.1 200 Connection Established\r\n\r\n")
        
        # Relaying loop
        sockets = [client_conn, target_conn]
        bytes_sent_client = 0
        bytes_sent_target = 0
        
        while True:
            readable, _, writable_err = select.select(sockets, [], sockets, 20.0)
            if writable_err:
                break
            if not readable:
                break  # Timeout
                
            for sock in readable:
                other_sock = target_conn if sock is client_conn else client_conn
                data = sock.recv(8192)
                if not data:
                    return bytes_sent_client, bytes_sent_target
                other_sock.sendall(data)
                
                if sock is client_conn:
                    bytes_sent_target += len(data)
                else:
                    bytes_sent_client += len(data)
                    
    except Exception as e:
        log_message("HTTPS-ERR", C_RED, f"Tunnel error for {target_host}:{target_port}: {e}")
        return 0, 0
    finally:
        try:
            target_conn.close()
        except:
            pass

def handle_client(client_conn: socket.socket, client_addr: tuple):
    """Handle connection from single client."""
    client_ip, client_port = client_addr
    try:
        # Read initial request headers
        data = client_conn.recv(4096)
        if not data:
            return
            
        request_str = data.decode("utf-8", errors="replace")
        lines = request_str.split("\r\n")
        if not lines or not lines[0]:
            return
            
        method, url, version = parse_request_line(lines[0])
        host, port = parse_host_port(url, method)
        
        if not host:
            # Fallback check for Host header
            for line in lines[1:]:
                if line.lower().startswith("host:"):
                    host_val = line.split(":", 1)[1].strip()
                    host, port = parse_host_port(host_val, method)
                    break
                    
        if not host:
            client_conn.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\nNo Host header found.")
            return

        if method == "CONNECT":
            # HTTPS tunnel
            log_message("CONNECT", C_YELLOW, f"{client_ip} -> {host}:{port}")
            tx, rx = handle_https_tunnel(client_conn, host, port)
            log_message("CLOSE", C_RESET, f"Tunnel {host}:{port} closed. Sent: {tx} B, Recv: {rx} B")
        else:
            # Standard HTTP request
            log_message("HTTP-REQ", C_BLUE, f"{client_ip} -> {method} {url}")
            
            # Forward to destination server
            target_conn = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            target_conn.settimeout(10.0)
            target_conn.connect((host, port))
            target_conn.sendall(data)
            
            # Read response and send back to client
            response_data = []
            while True:
                resp = target_conn.recv(4096)
                if not resp:
                    break
                client_conn.sendall(resp)
                response_data.append(resp)
                
            target_conn.close()
            
            # Parse status code from response
            resp_str = b"".join(response_data).decode("utf-8", errors="replace")
            resp_lines = resp_str.split("\r\n")
            status_line = resp_lines[0] if resp_lines else "Unknown"
            
            status_color = C_GREEN if "200" in status_line else C_RED
            log_message("HTTP-RES", status_color, f"{host}:{port} -> {status_line}")
            
    except Exception as e:
        log_message("ERROR", C_RED, f"Client handler error: {e}")
    finally:
        try:
            client_conn.close()
        except:
            pass

def start_server(host: str, port: int):
    """Initialize server socket and listen for clients."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server.bind((host, port))
    except Exception as e:
        log_message("FATAL", C_RED, f"Could not bind to {host}:{port}: {e}")
        sys.exit(1)
        
    server.listen(100)
    log_message("STARTUP", C_GREEN, f"HTTP Proxy Debugger listening on {host}:{port}")
    print(f"[*] To use, set your client proxy to http://{host}:{port}")
    print(f"[*] Press Ctrl+C to stop the server.\n")
    
    try:
        while True:
            conn, addr = server.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        log_message("SHUTDOWN", C_YELLOW, "Stopping proxy debugger...")
    finally:
        server.close()

def main():
    parser = argparse.ArgumentParser(
        description="HTTP Proxy Debugger: Debug API and web traffic locally.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Local address to bind to (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8080,
        help="Local port to bind to (default: 8080)"
    )
    args = parser.parse_args()
    
    start_server(args.host, args.port)

if __name__ == "__main__":
    main()
