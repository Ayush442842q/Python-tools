#!/usr/bin/env python3
"""
Socket Debugger - A cross-platform Python-native TCP/UDP socket test utility (Netcat-like).

Supports:
- TCP/UDP Client and Server modes
- Plain text or formatted Hex Dump visualization
- Multi-threaded interactive connection handling (compatible with Windows console)
- File transfer sending and receiving
"""

import os
import sys
import socket
import threading
import argparse


def hex_dump(data):
    """Generate a formatted hex dump of binary data (similar to hexdump -C)."""
    if not data:
        return ""
    lines = []
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        hex_part = " ".join(f"{b:02x}" for b in chunk)
        hex_pad = hex_part.ljust(47)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"{i:08x}  {hex_pad}  |{ascii_part}|")
    return "\n".join(lines)


def receive_loop(sock, is_udp, display_hex, save_file=None):
    """Continuously receive data from a socket and output/save it."""
    file_handle = None
    if save_file:
        try:
            file_handle = open(save_file, "wb")
            print(f"[*] Saving received data to: {save_file}")
        except Exception as e:
            print(f"[!] Error opening output file: {e}", file=sys.stderr)

    try:
        while True:
            if is_udp:
                data, addr = sock.recvfrom(65535)
                prefix = f"[{addr[0]}:{addr[1]} -> UDP]"
            else:
                data = sock.recv(4096)
                if not data:
                    print("\n[*] Connection closed by remote host.")
                    break
                prefix = ""

            # Save to file or output to screen
            if file_handle:
                file_handle.write(data)
                file_handle.flush()
                
            if display_hex:
                dump_str = hex_dump(data)
                if prefix:
                    print(f"{prefix}\n{dump_str}")
                else:
                    print(dump_str)
            else:
                # Print as text, decoding safely
                text = data.decode('utf-8', errors='replace')
                if prefix:
                    sys.stdout.write(f"{prefix} {text}")
                else:
                    sys.stdout.write(text)
                sys.stdout.flush()

    except ConnectionResetError:
        print("\n[*] Connection reset by remote host.")
    except Exception as e:
        # Ignore socket close errors when thread is shutting down
        pass
    finally:
        if file_handle:
            file_handle.close()
        # Shut down the script cleanly if connection dies
        sys.exit(0)


def send_file(sock, is_udp, filepath, udp_target=None):
    """Send a file over the socket."""
    if not os.path.exists(filepath):
        print(f"[!] File not found: {filepath}", file=sys.stderr)
        return False
    
    print(f"[*] Sending file: {filepath}")
    try:
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(4096)
                if not chunk:
                    break
                if is_udp:
                    sock.sendto(chunk, udp_target)
                else:
                    sock.sendall(chunk)
        print("[*] File transfer completed successfully.")
        return True
    except Exception as e:
        print(f"[!] File send error: {e}", file=sys.stderr)
        return False


def run_server(host, port, is_udp, display_hex, save_file=None):
    """Run socket in server (listening) mode."""
    family = socket.AF_INET
    sock_type = socket.SOCK_DGRAM if is_udp else socket.SOCK_STREAM
    
    server_sock = socket.socket(family, sock_type)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_sock.bind((host, port))
    except Exception as e:
        print(f"[!] Bind failed on {host}:{port} - {e}", file=sys.stderr)
        return

    if is_udp:
        print(f"[*] Listening for UDP packets on {host}:{port}...")
        # UDP does not accept connections, go straight to receive loop
        receive_loop(server_sock, is_udp=True, display_hex=display_hex, save_file=save_file)
    else:
        server_sock.listen(1)
        print(f"[*] Listening for TCP connections on {host}:{port}...")
        try:
            conn, addr = server_sock.accept()
            print(f"[*] Accepted connection from {addr[0]}:{addr[1]}")
            
            # Start listener thread
            recv_thread = threading.Thread(
                target=receive_loop, 
                args=(conn, False, display_hex, save_file),
                daemon=True
            )
            recv_thread.start()

            # Interactive send loop
            while True:
                line = sys.stdin.readline()
                if not line:
                    break
                conn.sendall(line.encode('utf-8'))
        except KeyboardInterrupt:
            print("\n[*] Shutting down server.")
        finally:
            server_sock.close()


def run_client(host, port, is_udp, display_hex, send_str=None, file_to_send=None, timeout=None):
    """Run socket in client mode."""
    family = socket.AF_INET
    sock_type = socket.SOCK_DGRAM if is_udp else socket.SOCK_STREAM
    
    sock = socket.socket(family, sock_type)
    if timeout:
        sock.settimeout(timeout)

    print(f"[*] Connecting to {host}:{port} ({'UDP' if is_udp else 'TCP'})...")
    
    try:
        if not is_udp:
            sock.connect((host, port))
            print("[*] Connected successfully. Press Ctrl+C to disconnect.")
        else:
            # UDP doesn't establish connection, but connect registers default destination
            sock.connect((host, port))
            print("[*] UDP ready. Press Ctrl+C to quit.")
    except Exception as e:
        print(f"[!] Connection failed: {e}", file=sys.stderr)
        return

    # Turn off socket timeout for general interactions after connecting
    sock.settimeout(None)

    # Start receive thread
    recv_thread = threading.Thread(
        target=receive_loop, 
        args=(sock, is_udp, display_hex, None),
        daemon=True
    )
    recv_thread.start()

    # Handle file send
    if file_to_send:
        send_file(sock, is_udp, file_to_send, (host, port) if is_udp else None)
        return

    # Handle raw string send
    if send_str:
        sock.sendall(send_str.encode('utf-8'))
        return

    # Interactive input loop
    try:
        while True:
            line = sys.stdin.readline()
            if not line:
                break
            sock.sendall(line.encode('utf-8'))
    except KeyboardInterrupt:
        print("\n[*] Disconnecting.")
    finally:
        sock.close()


def main():
    parser = argparse.ArgumentParser(
        description="Socket Debugger - A cross-platform TCP/UDP diagnostic and testing tool."
    )
    parser.add_argument(
        "host",
        nargs="?",
        default="0.0.0.0",
        help="Host/IP to connect to (client) or bind to (server, default: 0.0.0.0)"
    )
    parser.add_argument(
        "-p", "--port",
        type=int,
        required=True,
        help="Port number to connect to or listen on"
    )
    parser.add_argument(
        "-l", "--listen",
        action="store_true",
        help="Server mode: listen on the specified port"
    )
    parser.add_argument(
        "-u", "--udp",
        action="store_true",
        help="Use UDP protocol instead of TCP"
    )
    parser.add_argument(
        "--hex",
        action="store_true",
        help="Format incoming payload in a hex dump view"
    )
    parser.add_argument(
        "-s", "--send",
        help="Send a specific string payload and exit"
    )
    parser.add_argument(
        "-f", "--file",
        help="File to send (client mode) or file to write incoming data to (server mode)"
    )
    parser.add_argument(
        "-t", "--timeout",
        type=float,
        help="Connection/read timeout in seconds (client only)"
    )

    args = parser.parse_args()

    if args.listen:
        run_server(
            host=args.host, 
            port=args.port, 
            is_udp=args.udp, 
            display_hex=args.hex, 
            save_file=args.file if not args.udp else None
        )
    else:
        # Client mode requires host to be something other than 0.0.0.0
        host = args.host
        if host == "0.0.0.0":
            print("[!] Host IP '0.0.0.0' is for server bind. Specify a remote IP for client mode.", file=sys.stderr)
            sys.exit(1)
            
        run_client(
            host=host,
            port=args.port,
            is_udp=args.udp,
            display_hex=args.hex,
            send_str=args.send,
            file_to_send=args.file,
            timeout=args.timeout
        )


if __name__ == "__main__":
    main()
