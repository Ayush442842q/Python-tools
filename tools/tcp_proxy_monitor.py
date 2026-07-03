#!/usr/bin/env python3
"""
TCP Socket Proxy & Traffic Monitor - Intercept raw TCP traffic, print hex dumps, and inject latency/drops.
"""

import sys
import socket
import argparse
import threading
import time
import random

# ANSI colors
def get_color(color_name):
    colors = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'bold': '\033[1m',
        'cyan': '\033[96m',
        'magenta': '\033[95m',
        'reset': '\033[0m'
    }
    if sys.platform == 'win32':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            return ''
    return colors.get(color_name, '')

def hex_dump(data: bytes, width=16) -> str:
    """Generate a classic hex dump format string for bytes."""
    lines = []
    for i in range(0, len(data), width):
        chunk = data[i:i+width]
        hex_parts = [f"{b:02x}" for b in chunk]
        # Pad hex representation
        hex_str = " ".join(hex_parts)
        if len(chunk) < width:
            hex_str += " " * (width - len(chunk)) * 3
            
        # ASCII representation
        ascii_str = "".join(chr(b) if 32 <= b <= 126 else "." for b in chunk)
        lines.append(f"{i:04x}  {hex_str}  |{ascii_str}|")
    return "\n".join(lines)

def handle_traffic(source_sock: socket.socket, dest_sock: socket.socket, direction: str, 
                   color: str, reset_color: str, delay: float, drop_rate: float, lock: threading.Lock):
    """Forward data from source_sock to dest_sock, printing logs with optional delay/drops."""
    try:
        while True:
            data = source_sock.recv(4096)
            if not data:
                break
                
            # Simulate Packet Drop
            if drop_rate > 0 and random.random() < drop_rate:
                with lock:
                    print(f"\n{get_color('red')}[DROP] Discarded {len(data)} bytes ({direction}){reset_color}")
                continue
                
            # Simulate Network Latency
            if delay > 0:
                time.sleep(delay)
                
            # Send data to destination
            dest_sock.sendall(data)
            
            # Print hex dump
            with lock:
                print(f"\n{color}[{direction}] Transmitted {len(data)} bytes:{reset_color}")
                print(f"{color}{hex_dump(data)}{reset_color}")
                sys.stdout.flush()
                
    except Exception as e:
        # Silently exit or print error depending on connection status
        pass
    finally:
        try:
            source_sock.close()
        except:
            pass
        try:
            dest_sock.close()
        except:
            pass

def proxy_connection(client_sock: socket.socket, target_host: str, target_port: int, 
                     delay: float, drop_rate: float, colors: dict, print_lock: threading.Lock):
    """Establish connection to remote target and spin up two threads to bridge traffic bidirectional."""
    try:
        # Connect to remote target
        target_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        target_sock.connect((target_host, target_port))
    except Exception as e:
        print(f"{colors['red']}[ERROR] Failed connecting to remote target {target_host}:{target_port} - {e}{colors['reset']}")
        client_sock.close()
        return

    # Thread 1: Client -> Target
    t_client_to_target = threading.Thread(
        target=handle_traffic,
        args=(client_sock, target_sock, "CLIENT -> TARGET", colors['cyan'], colors['reset'], delay, drop_rate, print_lock),
        daemon=True
    )
    # Thread 2: Target -> Client
    t_target_to_client = threading.Thread(
        target=handle_traffic,
        args=(target_sock, client_sock, "TARGET -> CLIENT", colors['magenta'], colors['reset'], delay, drop_rate, print_lock),
        daemon=True
    )

    t_client_to_target.start()
    t_target_to_client.start()

def main():
    parser = argparse.ArgumentParser(
        description="TCP Socket Proxy & Traffic Monitor - Monitor raw traffic, inject latency/packet loss."
    )
    parser.add_argument("--listen-ip", default="127.0.0.1", help="IP address to listen on (default: 127.0.0.1)")
    parser.add_argument("--listen-port", type=int, required=True, help="Local port to bind the proxy to")
    parser.add_argument("--target-host", required=True, help="Target server host IP or domain")
    parser.add_argument("--target-port", type=int, required=True, help="Target server port")
    parser.add_argument("--delay", type=float, default=0.0, help="Simulated latency in seconds to apply to packets (default: 0.0)")
    parser.add_argument("--drop-rate", type=float, default=0.0, help="Packet drop rate as fraction (0.0 to 1.0; default: 0.0)")

    args = parser.parse_args()

    colors = {
        'red': get_color('red'),
        'green': get_color('green'),
        'yellow': get_color('yellow'),
        'blue': get_color('blue'),
        'cyan': get_color('cyan'),
        'magenta': get_color('magenta'),
        'bold': get_color('bold'),
        'reset': get_color('reset')
    }

    if not (0.0 <= args.drop_rate <= 1.0):
        print(f"{colors['red']}[ERROR] Drop rate must be between 0.0 and 1.0{colors['reset']}", file=sys.stderr)
        sys.exit(1)

    print_lock = threading.Lock()

    # Create server socket
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server.bind((args.listen_ip, args.listen_port))
        server.listen(100)
    except Exception as e:
        print(f"{colors['red']}[ERROR] Failed binding to {args.listen_ip}:{args.listen_port} - {e}{colors['reset']}", file=sys.stderr)
        sys.exit(1)

    print("=" * 65)
    print(f"{colors['bold']}{colors['green']}TCP Proxy Listening on:{colors['reset']} {args.listen_ip}:{args.listen_port}")
    print(f"{colors['bold']}{colors['green']}Forwarding to:{colors['reset']}          {args.target_host}:{args.target_port}")
    if args.delay > 0:
        print(f"{colors['yellow']}Simulated Latency:     {args.delay} seconds{colors['reset']}")
    if args.drop_rate > 0:
        print(f"{colors['red']}Packet Drop Rate:      {args.drop_rate * 100}%{colors['reset']}")
    print("=" * 65)
    print("Press Ctrl+C to stop the proxy.\n")

    try:
        while True:
            client_sock, addr = server.accept()
            with print_lock:
                print(f"{colors['green']}[+] Incoming connection from {addr[0]}:{addr[1]}{colors['reset']}")
            
            # Start forwarding proxy thread
            t = threading.Thread(
                target=proxy_connection,
                args=(client_sock, args.target_host, args.target_port, args.delay, args.drop_rate, colors, print_lock),
                daemon=True
            )
            t.start()
    except KeyboardInterrupt:
        print(f"\n{colors['yellow']}[*] Stopping TCP Proxy Server...{colors['reset']}")
    finally:
        server.close()

if __name__ == '__main__':
    main()
