#!/usr/bin/env python3
"""
TCP Port Forwarder & Tunneling Utility
A standalone local port redirector that forwards incoming TCP traffic from a local port
to a remote host and port, displaying transfer rates and logs.
"""

import argparse
import socket
import sys
import threading
import time

# Keep track of statistics
STATS = {
    'connections_active': 0,
    'connections_total': 0,
    'bytes_sent': 0,
    'bytes_received': 0
}
stats_lock = threading.Lock()


def format_bytes(n):
    """Format bytes to a human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if n < 1024.0:
            return f"{n:.2f} {unit}"
        n /= 1024.0
    return f"{n:.2f} PB"


def pipe_data(src_sock, dst_sock, direction, buffer_size=4096):
    """Pipe data from src_sock to dst_sock and update statistics."""
    global STATS
    try:
        while True:
            data = src_sock.recv(buffer_size)
            if not data:
                break
            dst_sock.sendall(data)
            
            # Update stats
            with stats_lock:
                if direction == 'incoming':
                    STATS['bytes_received'] += len(data)
                else:
                    STATS['bytes_sent'] += len(data)
    except Exception:
        pass
    finally:
        try:
            src_sock.close()
        except Exception:
            pass
        try:
            dst_sock.close()
        except Exception:
            pass


def handle_client(client_sock, target_host, target_port, buffer_size):
    """Handle a single client connection by establishing a connection to target."""
    global STATS
    with stats_lock:
        STATS['connections_active'] += 1
        STATS['connections_total'] += 1
    
    print(f"[*] Connection received from {client_sock.getpeername()[0]}:{client_sock.getpeername()[1]}")
    
    # Connect to target server
    try:
        target_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        target_sock.connect((target_host, target_port))
    except Exception as e:
        print(f"[!] Failed to connect to target {target_host}:{target_port} - {e}")
        client_sock.close()
        with stats_lock:
            STATS['connections_active'] -= 1
        return

    # Start bi-directional piping threads
    t_incoming = threading.Thread(target=pipe_data, args=(client_sock, target_sock, 'outgoing', buffer_size))
    t_outgoing = threading.Thread(target=pipe_data, args=(target_sock, client_sock, 'incoming', buffer_size))
    
    t_incoming.start()
    t_outgoing.start()
    
    # Wait for both threads to finish
    t_incoming.join()
    t_outgoing.join()
    
    with stats_lock:
        STATS['connections_active'] -= 1
    print(f"[*] Connection closed for {client_sock.getpeername()[0] if client_sock else 'Client'}")


def stats_reporter():
    """Periodically reports traffic statistics to console."""
    while True:
        time.sleep(5)
        with stats_lock:
            active = STATS['connections_active']
            total = STATS['connections_total']
            sent = format_bytes(STATS['bytes_sent'])
            received = format_bytes(STATS['bytes_received'])
        print(f"[STATS] Active: {active} | Total: {total} | Sent: {sent} | Received: {received}")


def main():
    parser = argparse.ArgumentParser(
        description="Forward TCP traffic from a local port to a target host/port."
    )
    parser.add_argument("-l", "--local-port", type=int, required=True, help="Local port to bind to")
    parser.add_argument("-t", "--target-host", required=True, help="Remote target host address")
    parser.add_argument("-p", "--target-port", type=int, required=True, help="Remote target port")
    parser.add_argument("-b", "--bind-ip", default="127.0.0.1", help="Local IP to bind listener (default: 127.0.0.1)")
    parser.add_argument("--buffer-size", type=int, default=4096, help="Receive buffer size in bytes (default: 4096)")
    parser.add_argument("--no-stats", action="store_true", help="Disable periodic status reports")

    args = parser.parse_args()

    # Bind local listener socket
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Allow socket address reuse immediately
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server.bind((args.bind_ip, args.local_port))
    except Exception as e:
        print(f"[!] Error binding to local port {args.local_port}: {e}", file=sys.stderr)
        return 1

    server.listen(10)
    print(f"[*] Port Forwarder active: Listening on {args.bind_ip}:{args.local_port}")
    print(f"[*] Forwarding to target: {args.target_host}:{args.target_port}")
    print("[*] Press Ctrl+C to terminate.")

    # Start stats reporting thread if not disabled
    if not args.no_stats:
        t_stats = threading.Thread(target=stats_reporter, daemon=True)
        t_stats.start()

    try:
        while True:
            client_sock, addr = server.accept()
            # Start client handler thread
            t = threading.Thread(
                target=handle_client,
                args=(client_sock, args.target_host, args.target_port, args.buffer_size),
                daemon=True
            )
            t.start()
    except KeyboardInterrupt:
        print("\n[*] Shutting down port forwarder.")
    finally:
        server.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
