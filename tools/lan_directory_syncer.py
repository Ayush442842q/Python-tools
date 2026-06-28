#!/usr/bin/env python3
"""
LAN Socket-based Directory Syncer

A TCP socket client/server tool to sync directories over a local network.
Compares file MD5 hashes to transfer only new or modified files.

Usage:
    Server (Receiver):
        python tools/lan_directory_syncer.py server --dir <target_directory> [options]
        
    Client (Sender):
        python tools/lan_directory_syncer.py client --host <server_ip> --dir <source_directory> [options]
"""

import sys
import os
import json
import socket
import struct
import hashlib
import argparse
import time

# Terminal colors
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"

def print_banner():
    banner = f"""
{CYAN}{BOLD}=========================================================
      🔄  LAN SOCKET-BASED DIRECTORY SYNCER  🔄
========================================================={RESET}
"""
    print(banner)

def get_file_md5(filepath):
    """Calculates MD5 checksum of a file in chunks."""
    hasher = hashlib.md5()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except Exception:
        return None

def scan_directory(base_dir):
    """Scans directory recursively and lists file metadata."""
    file_list = []
    base_path = os.path.abspath(base_dir)
    
    for root, _, files in os.walk(base_path):
        for f in files:
            full_path = os.path.join(root, f)
            rel_path = os.path.relpath(full_path, base_path).replace("\\", "/")
            try:
                stat = os.stat(full_path)
                md5 = get_file_md5(full_path)
                if md5:
                    file_list.append({
                        "path": rel_path,
                        "size": stat.st_size,
                        "md5": md5
                    })
            except Exception as e:
                print(f"{YELLOW}Warning: Skipping file {rel_path} due to read error: {e}{RESET}")
                
    return file_list

# Network helper functions to send/recv sized payloads
def send_msg(sock, data):
    """Sends arbitrary bytes prefixed with a 4-byte big-endian length."""
    payload = struct.pack(">I", len(data)) + data
    sock.sendall(payload)

def recv_msg(sock):
    """Receives arbitrary bytes prefixed with a 4-byte big-endian length."""
    raw_msglen = recv_all(sock, 4)
    if not raw_msglen:
        return None
    msglen = struct.unpack(">I", raw_msglen)[0]
    return recv_all(sock, msglen)

def recv_all(sock, n):
    """Helper to receive exactly n bytes or return None if EOF."""
    data = bytearray()
    while len(data) < n:
        packet = sock.recv(n - len(data))
        if not packet:
            return None
        data.extend(packet)
    return data


class SyncServer:
    def __init__(self, host, port, target_dir):
        self.host = host
        self.port = port
        self.target_dir = os.path.abspath(target_dir)

    def start(self):
        if not os.path.exists(self.target_dir):
            os.makedirs(self.target_dir)
            
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Allow immediate socket reuse
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((self.host, self.port))
        server_sock.listen(1)
        
        print(f"Server listening on {BOLD}{self.host}:{self.port}{RESET}")
        print(f"Target synchronization directory: {BOLD}{self.target_dir}{RESET}")
        print("Waiting for client connection...\n")

        try:
            conn, addr = server_sock.accept()
            print(f"{GREEN}Connection accepted from: {addr[0]}:{addr[1]}{RESET}")
            self._handle_client(conn)
        except KeyboardInterrupt:
            print("\nServer shutting down.")
        finally:
            server_sock.close()

    def _handle_client(self, conn):
        try:
            # 1. Receive client file list
            raw_metadata = recv_msg(conn)
            if not raw_metadata:
                print(f"{RED}Failed to receive metadata from client.{RESET}")
                return
                
            client_metadata = json.loads(raw_metadata.decode("utf-8"))
            client_files = client_metadata.get("files", [])
            print(f"Client reported {len(client_files)} file(s). Comparing databases...")

            # 2. Compare files and build request list
            requested_files = []
            for cf in client_files:
                local_path = os.path.join(self.target_dir, cf["path"])
                
                # Check if local file exists, size matches, and MD5 matches
                need_transfer = True
                if os.path.exists(local_path):
                    local_size = os.path.getsize(local_path)
                    if local_size == cf["size"]:
                        local_md5 = get_file_md5(local_path)
                        if local_md5 == cf["md5"]:
                            need_transfer = False
                            
                if need_transfer:
                    requested_files.append(cf["path"])

            # 3. Send requested files list to client
            resp = {"requested": requested_files}
            send_msg(conn, json.dumps(resp).encode("utf-8"))
            print(f"Requested {len(requested_files)} missing/modified file(s) from client.")

            # 4. Receive files from client
            transferred_count = 0
            for path in requested_files:
                local_filepath = os.path.join(self.target_dir, path)
                local_dir = os.path.dirname(local_filepath)
                if not os.path.exists(local_dir):
                    os.makedirs(local_dir)

                # Receive file size
                raw_size = recv_all(conn, 8)
                if not raw_size:
                    break
                file_size = struct.unpack(">Q", raw_size)[0]

                # Receive file contents in chunks
                print(f"  Receiving: {path} ({file_size} bytes)...", end="", flush=True)
                bytes_received = 0
                with open(local_filepath, "wb") as f:
                    while bytes_received < file_size:
                        chunk_size = min(4096, file_size - bytes_received)
                        chunk = conn.recv(chunk_size)
                        if not chunk:
                            raise ConnectionError("Connection lost while reading file content.")
                        f.write(chunk)
                        bytes_received += len(chunk)
                print(f" {GREEN}Done{RESET}")
                transferred_count += 1

            print(f"\n{BOLD}{GREEN}Sync completed! Received {transferred_count} file(s).{RESET}")
        except Exception as e:
            print(f"{RED}Error in client handler: {e}{RESET}")
        finally:
            conn.close()


class SyncClient:
    def __init__(self, host, port, source_dir, dry_run=False):
        self.host = host
        self.port = port
        self.source_dir = os.path.abspath(source_dir)
        self.dry_run = dry_run

    def start(self):
        if not os.path.exists(self.source_dir):
            print(f"{RED}Error: Source directory '{self.source_dir}' does not exist.{RESET}")
            return

        print(f"Scanning source directory: {BOLD}{self.source_dir}{RESET}...")
        client_files = scan_directory(self.source_dir)
        print(f"Scanned {len(client_files)} files. Connecting to server {self.host}:{self.port}...")

        client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            client_sock.connect((self.host, self.port))
            print(f"{GREEN}Connected to server!{RESET}")

            # 1. Send file metadata list
            metadata = {"files": client_files}
            send_msg(client_sock, json.dumps(metadata).encode("utf-8"))

            # 2. Receive server request list
            raw_response = recv_msg(client_sock)
            if not raw_response:
                print(f"{RED}Server closed connection.{RESET}")
                return
                
            response = json.loads(raw_response.decode("utf-8"))
            requested = response.get("requested", [])

            print(f"Server requested {len(requested)} file(s).")
            if self.dry_run:
                print(f"{YELLOW}[Dry-run] Files that would be synced:{RESET}")
                for r in requested:
                    print(f"  - {r}")
                client_sock.close()
                return

            # 3. Transmit requested files
            start_time = time.time()
            total_bytes_sent = 0
            for path in requested:
                filepath = os.path.join(self.source_dir, path)
                file_size = os.path.getsize(filepath)

                # Send 8-byte big-endian file size
                client_sock.sendall(struct.pack(">Q", file_size))

                # Send file content in chunks
                print(f"  Sending: {path} ({file_size} bytes)...", end="", flush=True)
                bytes_sent = 0
                with open(filepath, "rb") as f:
                    while bytes_sent < file_size:
                        chunk = f.read(4096)
                        if not chunk:
                            break
                        client_sock.sendall(chunk)
                        bytes_sent += len(chunk)
                total_bytes_sent += file_size
                print(f" {GREEN}Sent{RESET}")

            elapsed = time.time() - start_time
            speed_kb = (total_bytes_sent / 1024) / elapsed if elapsed > 0 else 0
            print(f"\n{BOLD}{GREEN}Sync finished!{RESET}")
            print(f"Transferred: {len(requested)} files ({total_bytes_sent} bytes) in {elapsed:.2f} seconds ({speed_kb:.2f} KB/s).")

        except ConnectionRefusedError:
            print(f"{RED}Error: Connection refused. Is the server running on {self.host}:{self.port}?{RESET}")
        except Exception as e:
            print(f"{RED}Error during synchronization: {e}{RESET}")
        finally:
            client_sock.close()


def main():
    print_banner()
    parser = argparse.ArgumentParser(
        description="Synchronize folders over local network using sockets",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("mode", choices=["client", "server"], help="Run as client (sender) or server (receiver)")
    parser.add_argument("--host", default="127.0.0.1", help="Server IP address (client mode only) or interface bind (server mode)")
    parser.add_argument("--port", type=int, default=9999, help="TCP port (default: 9999)")
    parser.add_argument("--dir", required=True, help="Directory to sync (source for client, destination for server)")
    parser.add_argument("--dry-run", action="store_true", help="Print what files would be synced without sending them (client mode only)")

    args = parser.parse_args()

    if args.mode == "server":
        # Server can bind to 0.0.0.0 to listen on all interfaces
        bind_host = "0.0.0.0" if args.host == "127.0.0.1" else args.host
        server = SyncServer(bind_host, args.port, args.dir)
        server.start()
    elif args.mode == "client":
        client = SyncClient(args.host, args.port, args.dir, args.dry_run)
        client.start()

    return 0

if __name__ == "__main__":
    sys.exit(main())
