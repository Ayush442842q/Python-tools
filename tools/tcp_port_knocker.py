#!/usr/bin/env python3
"""
TCP/UDP Port Knocker & Daemon Simulator

A standalone utility to demonstrate and perform port knocking. It operates in 
two modes:
1. Client Mode: Knocks on a specified sequence of ports to signal the server.
2. Daemon Simulator Mode: Listens on multiple ports, tracks incoming knock 
   sequences from remote IPs, and simulates triggering a firewall rule (e.g., 
   opening SSH port 22) when the correct sequence is completed.

Usage:
    # Run the server simulator listening on 7000, 8000, 9000 (sequence to unlock 22)
    python tools/tcp_port_knocker.py server --sequence 7000,8000,9000 --unlock-port 22

    # Run the client to knock on localhost ports 7000, 8000, 9000
    python tools/tcp_port_knocker.py client localhost --sequence 7000,8000,9000
"""

import sys
import os
import time
import socket
import argparse
import threading
from collections import defaultdict

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"

# Global state for daemon
knocks_history = defaultdict(list)  # IP -> list of (port, timestamp)
history_lock = threading.Lock()

def print_colored(text, color):
    """Print text with ANSI color."""
    print(f"{color}{text}{RESET}")

def run_client(host: str, sequence: list, delay_ms: int, use_udp: bool):
    """Client mode: Knocks on target ports in sequence."""
    proto = "UDP" if use_udp else "TCP"
    print_colored(f"[*] Starting client knock sequence to {host} via {proto}...", BLUE)
    print_colored(f"[*] Target sequence: {sequence}", BLUE)
    
    sock_type = socket.SOCK_DGRAM if use_udp else socket.SOCK_STREAM
    
    for idx, port in enumerate(sequence):
        print(f"[{idx+1}/{len(sequence)}] Knocking on port {port}...")
        try:
            # We use a short timeout for knocks
            s = socket.socket(socket.AF_INET, sock_type)
            s.settimeout(0.5)
            if use_udp:
                s.sendto(b"\x00", (host, port))
            else:
                # For TCP, just attempt connection
                s.connect((host, port))
        except (socket.timeout, ConnectionRefusedError, socket.error):
            # Port knocking usually expects connection timeouts or refusals!
            # The server registers the attempt even if it rejects the handshake.
            pass
        finally:
            s.close()
            
        if idx < len(sequence) - 1:
            time.sleep(delay_ms / 1000.0)
            
    print_colored("[+] Knock sequence complete!", GREEN)

def start_server_listener(port: int, use_udp: bool, unlock_port: int, sequence: list, timeout_sec: int):
    """Starts a socket listener on a specific port to record knocks."""
    sock_type = socket.SOCK_DGRAM if use_udp else socket.SOCK_STREAM
    proto = "UDP" if use_udp else "TCP"
    
    s = socket.socket(socket.AF_INET, sock_type)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        s.bind(("0.0.0.0", port))
    except Exception as e:
        print_colored(f"[-] Failed to bind port {port}: {e}", RED)
        return
        
    if not use_udp:
        s.listen(5)
        
    while True:
        try:
            if use_udp:
                _, addr = s.recvfrom(1024)
                client_ip = addr[0]
            else:
                conn, addr = s.accept()
                client_ip = addr[0]
                conn.close()
                
            handle_knock(client_ip, port, sequence, unlock_port, timeout_sec)
        except Exception:
            break

def handle_knock(client_ip: str, port: int, sequence: list, unlock_port: int, timeout_sec: int):
    """Process a registered knock from a client IP."""
    now = time.time()
    with history_lock:
        # Prune old knocks first
        knocks_history[client_ip] = [
            (p, ts) for p, ts in knocks_history[client_ip]
            if now - ts <= timeout_sec
        ]
        
        # Log the current knock
        print_colored(f"[Knock] IP {client_ip} hit port {port}", YELLOW)
        knocks_history[client_ip].append((port, now))
        
        # Check if sequence matches
        recent_ports = [p for p, ts in knocks_history[client_ip]]
        
        # Check if the sequence is a subsegment of client's knock history ending at current time
        if len(recent_ports) >= len(sequence):
            # Check last N elements
            last_n_knocks = recent_ports[-len(sequence):]
            if last_n_knocks == sequence:
                print_colored(f"\n{BOLD}{GREEN}[★] SUCCESS: Correct sequence completed by {client_ip}!{RESET}", GREEN)
                print_colored(f"[★] SIMULATED ACTION: Firewall rule added! Opened port {unlock_port} for {client_ip}", GREEN)
                print()
                # Clear history for this IP to prevent immediate re-triggering
                knocks_history[client_ip] = []

def run_server(sequence: list, unlock_port: int, use_udp: bool, timeout_sec: int):
    """Server mode: Runs listeners on all sequence ports."""
    proto = "UDP" if use_udp else "TCP"
    print_colored(f"[*] Starting Port Knocker Daemon Simulator via {proto}...", BLUE)
    print_colored(f"[*] Awaiting sequence: {sequence} (timeout: {timeout_sec}s)", BLUE)
    print_colored(f"[*] Target action: Simulated unlock of port {unlock_port}", BLUE)
    print_colored("[*] Press Ctrl+C to terminate.", BLUE)
    print()

    threads = []
    for port in sequence:
        t = threading.Thread(
            target=start_server_listener,
            args=(port, use_udp, unlock_port, sequence, timeout_sec),
            daemon=True
        )
        t.start()
        threads.append(t)
        
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print_colored("\n[-] Server shutting down.", RED)

def parse_sequence(seq_str: str) -> list:
    """Helper to convert '7000,8000,9000' to [7000, 8000, 9000]."""
    try:
        return [int(p.strip()) for p in seq_str.split(",")]
    except ValueError:
        raise argparse.ArgumentTypeError("Sequence must be a comma-separated list of integers.")

def main():
    parser = argparse.ArgumentParser(description="TCP/UDP Port Knocker & Daemon Simulator")
    subparsers = parser.add_subparsers(dest="mode", required=True, help="Modes: client or server")
    
    # Client parser
    client_parser = subparsers.add_parser("client", help="Knock on a sequence of ports.")
    client_parser.add_argument("host", help="Target hostname or IP address.")
    client_parser.add_argument("-s", "--sequence", type=parse_sequence, required=True,
                               help="Comma-separated list of ports to knock (e.g. 7000,8000,9000).")
    client_parser.add_argument("-d", "--delay", type=int, default=200,
                               help="Delay between knocks in milliseconds (default: 200).")
    client_parser.add_argument("-u", "--udp", action="store_true", help="Use UDP packets instead of TCP.")
    
    # Server parser
    server_parser = subparsers.add_parser("server", help="Listen for knock sequences and trigger actions.")
    server_parser.add_argument("-s", "--sequence", type=parse_sequence, required=True,
                               help="Comma-separated list of ports to listen on.")
    server_parser.add_argument("-u", "--unlock-port", type=int, default=22,
                               help="Port to unlock on success (default: 22).")
    server_parser.add_argument("-w", "--window", type=int, default=10,
                               help="Time window in seconds to complete sequence (default: 10).")
    server_parser.add_argument("-udp", "--udp-ports", action="store_true", help="Listen for UDP knocks instead of TCP.")
    
    args = parser.parse_args()
    
    if args.mode == "client":
        run_client(args.host, args.sequence, args.delay, args.udp)
    elif args.mode == "server":
        run_server(args.sequence, args.unlock_port, args.udp_ports, args.window)

if __name__ == "__main__":
    main()
