#!/usr/bin/env python3
"""
Mock Memcached Server

A pure Python, zero-dependency mock implementation of the Memcached ASCII protocol.
Runs a local TCP socket server (default port 11211) and supports standard operations:
set, add, replace, append, prepend, get, gets, delete, incr, decr, stats, flush_all, version, and quit.
Includes automatic key expiration (TTL) handling and live operation logging.

Usage:
    python tools/mock_memcached_server.py [options]
"""

import argparse
import socket
import sys
import threading
import time
from typing import Dict, List, Optional, Tuple

class MemcachedItem:
    """Represents a value stored in the mock Memcached server."""
    def __init__(self, value: bytes, flags: int, exptime: int) -> None:
        self.value = value
        self.flags = flags
        self.created_at = time.time()
        self.cas_unique = int(self.created_at * 1000) & 0xffffffff
        
        # exptime logic:
        # If exptime is 0, the item never expires.
        # If exptime is greater than 30 days (2592000 seconds), it's treated as a Unix timestamp.
        # Otherwise, it's treated as a relative offset in seconds from now.
        if exptime == 0:
            self.expires_at: Optional[float] = None
        elif exptime > 2592000:
            self.expires_at = float(exptime)
        else:
            self.expires_at = self.created_at + float(exptime)

    def is_expired(self) -> bool:
        """Check if the item has expired based on its TTL."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

class MockMemcachedServer:
    """Mock Memcached TCP Server implementing the ASCII protocol."""
    def __init__(self, host: str = "127.0.0.1", port: int = 11211, verbose: bool = False) -> None:
        self.host = host
        self.port = port
        self.verbose = verbose
        self.store: Dict[str, MemcachedItem] = {}
        self.lock = threading.Lock()
        
        # Statistics
        self.stats = {
            "pid": os.getpid() if hasattr(os, "getpid") else 0,
            "uptime": time.time(),
            "curr_connections": 0,
            "total_connections": 0,
            "cmd_get": 0,
            "cmd_set": 0,
            "get_hits": 0,
            "get_misses": 0,
            "bytes_read": 0,
            "bytes_written": 0,
        }

    def start(self) -> None:
        """Starts the TCP socket listener."""
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            server.bind((self.host, self.port))
            server.listen(5)
        except Exception as e:
            print(f"Error binding to {self.host}:{self.port} - {e}", file=sys.stderr)
            sys.exit(1)

        print("=" * 60)
        print(f" MOCK MEMCACHED SERVER STARTED")
        print(f" Listening on: tcp://{self.host}:{self.port}")
        print(f" Logs will display below in real-time...")
        print("=" * 60)

        # Start a thread to clean expired keys periodically
        cleaner = threading.Thread(target=self._expiration_loop, daemon=True)
        cleaner.start()

        try:
            while True:
                client_sock, client_addr = server.accept()
                with self.lock:
                    self.stats["curr_connections"] += 1
                    self.stats["total_connections"] += 1
                
                if self.verbose:
                    print(f"[+] Client connected: {client_addr[0]}:{client_addr[1]}")
                
                t = threading.Thread(target=self._handle_client, args=(client_sock, client_addr), daemon=True)
                t.start()
        except KeyboardInterrupt:
            print("\nShutting down server...")
        finally:
            server.close()

    def _expiration_loop(self) -> None:
        """Periodically cleans up expired keys from the store."""
        while True:
            time.sleep(5)
            with self.lock:
                expired_keys = [k for k, item in self.store.items() if item.is_expired()]
                for k in expired_keys:
                    del self.store[k]
                    if self.verbose:
                        print(f"[-] Key expired and purged: {k}")

    def _handle_client(self, sock: socket.socket, addr: Tuple[str, int]) -> None:
        """Handles commands sent by a single connected client."""
        # Socket buffer wrapper
        conn_file = sock.makefile('rwb')
        try:
            while True:
                line = conn_file.readline()
                if not line:
                    break
                
                with self.lock:
                    self.stats["bytes_read"] += len(line)

                # Parse Memcached command line
                cmd_line = line.strip().decode('utf-8', errors='ignore')
                if not cmd_line:
                    continue

                parts = cmd_line.split()
                cmd = parts[0].lower()
                
                # Close connection if requested
                if cmd == 'quit':
                    break
                    
                response = self._process_command(cmd, parts, conn_file)
                if response:
                    conn_file.write(response)
                    conn_file.flush()
                    with self.lock:
                        self.stats["bytes_written"] += len(response)
                        
        except Exception as e:
            if self.verbose:
                print(f"[!] Error handling client {addr}: {e}")
        finally:
            try:
                sock.close()
            except Exception:
                pass
            with self.lock:
                self.stats["curr_connections"] -= 1
            if self.verbose:
                print(f"[-] Client disconnected: {addr[0]}:{addr[1]}")

    def _process_command(self, cmd: str, parts: List[str], conn_file) -> bytes:
        """Processes standard Memcached commands and formats response payloads."""
        # --- STORAGE COMMANDS (set, add, replace, append, prepend, cas) ---
        if cmd in ('set', 'add', 'replace', 'append', 'prepend', 'cas'):
            if len(parts) < 5:
                return b"CLIENT_ERROR bad command line format\r\n"
            
            key = parts[1]
            try:
                flags = int(parts[2])
                exptime = int(parts[3])
                bytes_len = int(parts[4])
            except ValueError:
                return b"CLIENT_ERROR bad command line format\r\n"

            cas_unique = None
            if cmd == 'cas':
                if len(parts) < 6:
                    return b"CLIENT_ERROR bad command line format\r\n"
                try:
                    cas_unique = int(parts[5])
                except ValueError:
                    return b"CLIENT_ERROR bad command line format\r\n"

            # Read raw data payload (bytes_len + 2 bytes for trailing \r\n)
            data_with_crlf = conn_file.read(bytes_len + 2)
            with self.lock:
                self.stats["bytes_read"] += len(data_with_crlf)
            
            data = data_with_crlf[:-2]  # strip trailing \r\n
            
            with self.lock:
                self.stats["cmd_set"] += 1
                
                # Check current item state
                item_exists = key in self.store and not self.store[key].is_expired()
                
                if cmd == 'add' and item_exists:
                    print(f"  [ADD] Key exists: '{key}'")
                    return b"NOT_STORED\r\n"
                
                if cmd == 'replace' and not item_exists:
                    print(f"  [REPLACE] Key missing: '{key}'")
                    return b"NOT_STORED\r\n"
                
                if cmd == 'cas':
                    if not item_exists:
                        return b"NOT_FOUND\r\n"
                    if self.store[key].cas_unique != cas_unique:
                        return b"EXISTS\r\n"

                if cmd == 'append':
                    if not item_exists:
                        return b"NOT_STORED\r\n"
                    data = self.store[key].value + data
                elif cmd == 'prepend':
                    if not item_exists:
                        return b"NOT_STORED\r\n"
                    data = data + self.store[key].value
                
                # Save item in store
                self.store[key] = MemcachedItem(data, flags, exptime)
                print(f"  [{cmd.upper()}] Stored key '{key}' ({bytes_len} bytes)")
                return b"STORED\r\n"

        # --- RETRIEVAL COMMANDS (get, gets) ---
        elif cmd in ('get', 'gets'):
            if len(parts) < 2:
                return b"CLIENT_ERROR bad command line format\r\n"
            
            keys = parts[1:]
            response_chunks = []
            
            with self.lock:
                self.stats["cmd_get"] += 1
                for key in keys:
                    if key in self.store:
                        item = self.store[key]
                        if item.is_expired():
                            del self.store[key]
                            self.stats["get_misses"] += 1
                            print(f"  [GET] Expired key: '{key}'")
                            continue
                        
                        self.stats["get_hits"] += 1
                        val_len = len(item.value)
                        
                        if cmd == 'gets':
                            header = f"VALUE {key} {item.flags} {val_len} {item.cas_unique}\r\n".encode()
                        else:
                            header = f"VALUE {key} {item.flags} {val_len}\r\n".encode()
                        
                        response_chunks.append(header)
                        response_chunks.append(item.value + b"\r\n")
                        print(f"  [GET] Hit key: '{key}' ({val_len} bytes)")
                    else:
                        self.stats["get_misses"] += 1
                        print(f"  [GET] Miss key: '{key}'")

            response_chunks.append(b"END\r\n")
            return b"".join(response_chunks)

        # --- DELETION ---
        elif cmd == 'delete':
            if len(parts) < 2:
                return b"CLIENT_ERROR bad command line format\r\n"
            
            key = parts[1]
            with self.lock:
                if key in self.store and not self.store[key].is_expired():
                    del self.store[key]
                    print(f"  [DELETE] Removed key: '{key}'")
                    return b"DELETED\r\n"
                else:
                    print(f"  [DELETE] Key missing: '{key}'")
                    return b"NOT_FOUND\r\n"

        # --- ARITHMETIC (incr, decr) ---
        elif cmd in ('incr', 'decr'):
            if len(parts) < 3:
                return b"CLIENT_ERROR bad command line format\r\n"
            
            key = parts[1]
            try:
                val_diff = int(parts[2])
            except ValueError:
                return b"CLIENT_ERROR value is not a valid integer\r\n"

            with self.lock:
                if key not in self.store or self.store[key].is_expired():
                    return b"NOT_FOUND\r\n"
                
                item = self.store[key]
                try:
                    current_int = int(item.value.decode('utf-8').strip())
                except ValueError:
                    return b"CLIENT_ERROR cannot increment or decrement non-numeric value\r\n"

                if cmd == 'incr':
                    new_val = current_int + val_diff
                else:
                    new_val = max(0, current_int - val_diff)  # Memcached decr doesn't wrap under 0

                new_bytes = str(new_val).encode()
                # Update item retaining flags/TTL
                item.value = new_bytes
                item.cas_unique = int(time.time() * 1000) & 0xffffffff
                
                print(f"  [{cmd.upper()}] Key '{key}' new value: {new_val}")
                return f"{new_val}\r\n".encode()

        # --- UTILITIES ---
        elif cmd == 'stats':
            uptime = int(time.time() - self.stats["uptime"])
            res = [
                f"STAT pid {self.stats['pid']}",
                f"STAT uptime {uptime}",
                f"STAT curr_connections {self.stats['curr_connections']}",
                f"STAT total_connections {self.stats['total_connections']}",
                f"STAT cmd_get {self.stats['cmd_get']}",
                f"STAT cmd_set {self.stats['cmd_set']}",
                f"STAT get_hits {self.stats['get_hits']}",
                f"STAT get_misses {self.stats['get_misses']}",
                f"STAT bytes_read {self.stats['bytes_read']}",
                f"STAT bytes_written {self.stats['bytes_written']}",
                "END"
            ]
            return ("\r\n".join(res) + "\r\n").encode()

        elif cmd == 'flush_all':
            with self.lock:
                self.store.clear()
            print("  [FLUSH_ALL] Cleared all store entries.")
            return b"OK\r\n"

        elif cmd == 'version':
            return b"VERSION MockMemcached/1.0.0\r\n"

        return b"ERROR\r\n"

import os

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Mock Memcached Server (ASCII Protocol)"
    )
    parser.add_argument(
        "-b", "--bind", default="127.0.0.1", help="Interface bind address (default: 127.0.0.1)"
    )
    parser.add_argument(
        "-p", "--port", type=int, default=11211, help="TCP port identifier (default: 11211)"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Print debug connection lifecycle updates"
    )

    args = parser.parse_args()

    server = MockMemcachedServer(host=args.bind, port=args.port, verbose=args.verbose)
    server.start()

if __name__ == "__main__":
    main()
