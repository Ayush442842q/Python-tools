#!/usr/bin/env python3
"""
mock_ftp_server - Mock FTP Server for Testing

Implements a basic, multi-threaded RFC 959 FTP server over TCP using Python's
standard socket and threading libraries. Useful for local script integration
and automated testing.

Usage:
    # Start on default port 2121 using current directory as home
    python tools/mock_ftp_server.py

    # Start with custom port and custom home directory
    python tools/mock_ftp_server.py --port 2121 --dir ./ftp_root --anonymous
"""

import argparse
import os
import socket
import sys
import threading
import time


class FTPControlConnection(threading.Thread):
    def __init__(self, conn, addr, server):
        super().__init__()
        self.conn = conn
        self.addr = addr
        self.server = server
        self.cwd = "/"
        self.user = None
        self.authenticated = False
        self.mode = "I"  # default Image/Binary mode
        self.data_ip = None
        self.data_port = None
        self.pasv_server = None
        self.active_conn = None

    def send_resp(self, code, message):
        """Send a standard FTP response."""
        try:
            self.conn.sendall(f"{code} {message}\r\n".encode("utf-8"))
        except OSError:
            pass

    def get_absolute_path(self, path):
        """Map virtual FTP paths to the real filesystem path."""
        # Sanitize path
        if path.startswith("/"):
            target_virtual = os.path.normpath(path)
        else:
            target_virtual = os.path.normpath(os.path.join(self.cwd, path))
        
        # Prevent path traversal
        if not target_virtual.startswith("/"):
            target_virtual = "/"
            
        real_root = os.path.abspath(self.server.root_dir)
        real_path = os.path.abspath(os.path.join(real_root, target_virtual.lstrip("/")))
        
        # Verify it stays within the real root
        if not real_path.startswith(real_root):
            return real_root, "/"
            
        return real_path, target_virtual

    def establish_data_connection(self):
        """Establish the data connection using active (PORT) or passive (PASV) mode."""
        if self.pasv_server:
            # Passive mode
            try:
                self.pasv_server.settimeout(10.0)
                data_conn, addr = self.pasv_server.accept()
                self.pasv_server.close()
                self.pasv_server = None
                return data_conn
            except socket.timeout:
                self.send_resp(425, "Timeout waiting for passive connection.")
                return None
            except OSError as e:
                self.send_resp(425, f"Can't open data connection: {e}")
                return None
        elif self.data_ip and self.data_port:
            # Active mode
            try:
                data_conn = socket.create_connection((self.data_ip, self.data_port), timeout=10)
                return data_conn
            except OSError as e:
                self.send_resp(425, f"Can't open active data connection to {self.data_ip}:{self.data_port}: {e}")
                return None
        else:
            self.send_resp(425, "Use PORT or PASV first.")
            return None

    def run(self):
        self.send_resp(220, "Mock FTP Server Ready.")
        try:
            buffer = ""
            while True:
                data = self.conn.recv(4096)
                if not data:
                    break
                buffer += data.decode("utf-8", errors="ignore")
                while "\r\n" in buffer:
                    line, buffer = buffer.split("\r\n", 1)
                    if self.server.verbose:
                        print(f"[{self.addr[0]}:{self.addr[1]}] -> {line}")
                    self.handle_command(line)
        except OSError:
            pass
        finally:
            self.cleanup()

    def cleanup(self):
        try:
            self.conn.close()
        except OSError:
            pass
        if self.pasv_server:
            try:
                self.pasv_server.close()
            except OSError:
                pass
        if self.server.verbose:
            print(f"[{self.addr[0]}:{self.addr[1]}] Connection closed.")

    def handle_command(self, line):
        if not line.strip():
            return
            
        parts = line.split(" ", 1)
        cmd = parts[0].upper()
        args = parts[1] if len(parts) > 1 else ""

        # Non-authenticated commands allowed
        if cmd == "QUIT":
            self.send_resp(221, "Goodbye.")
            self.conn.close()
            return
        elif cmd == "USER":
            self.user = args
            self.send_resp(331, f"Password required for {args}.")
            return
        elif cmd == "PASS":
            if self.user:
                # Basic check
                if self.server.anonymous and self.user.lower() == "anonymous":
                    self.authenticated = True
                    self.send_resp(230, "User logged in, proceed.")
                elif not self.server.anonymous and self.user == self.server.username and args == self.server.password:
                    self.authenticated = True
                    self.send_resp(230, "User logged in, proceed.")
                else:
                    self.send_resp(530, "Login incorrect.")
            else:
                self.send_resp(503, "Bad sequence of commands (send USER first).")
            return

        if not self.authenticated:
            self.send_resp(530, "Please login with USER and PASS.")
            return

        # Authenticated commands
        if cmd == "SYST":
            self.send_resp(215, "UNIX Type: L8")
        elif cmd == "PWD":
            self.send_resp(257, f'"{self.cwd}" is current directory.')
        elif cmd == "TYPE":
            if args.upper() in ("A", "I"):
                self.mode = args.upper()
                self.send_resp(200, f"Type set to {self.mode}.")
            else:
                self.send_resp(504, "Unsupported type.")
        elif cmd == "PORT":
            # e.g., PORT 127,0,0,1,19,137 (IP = 127.0.0.1, Port = 19 * 256 + 137 = 5001)
            parts = args.split(",")
            if len(parts) == 6:
                try:
                    self.data_ip = ".".join(parts[:4])
                    self.data_port = int(parts[4]) * 256 + int(parts[5])
                    self.pasv_server = None  # Clear PASV
                    self.send_resp(200, "PORT command successful.")
                except ValueError:
                    self.send_resp(501, "Syntax error in IP/Port.")
            else:
                self.send_resp(501, "Syntax error in parameters.")
        elif cmd == "PASV":
            try:
                # Open ephemeral port for passive data transfer
                self.pasv_server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.pasv_server.bind((self.server.host, 0))
                self.pasv_server.listen(1)
                port = self.pasv_server.getsockname()[1]
                
                # Get server IP representation
                ip_parts = self.server.host.split(".")
                if len(ip_parts) != 4:
                    # Fallback to local loopback if not IPv4
                    ip_parts = ["127", "0", "0", "1"]
                p1 = port // 256
                p2 = port % 256
                ip_str = ",".join(ip_parts)
                self.send_resp(227, f"Entering Passive Mode ({ip_str},{p1},{p2}).")
            except OSError as e:
                self.send_resp(425, f"Cannot open passive port: {e}")
        elif cmd in ("LIST", "NLST"):
            real_path, _ = self.get_absolute_path(args)
            if not os.path.exists(real_path):
                self.send_resp(550, "File or directory not found.")
                return

            data_conn = self.establish_data_connection()
            if not data_conn:
                return

            self.send_resp(150, "Here comes the directory listing.")
            try:
                listing = ""
                if os.path.isdir(real_path):
                    for entry in os.listdir(real_path):
                        full_entry = os.path.join(real_path, entry)
                        if cmd == "LIST":
                            # Mock long listing: -rw-r--r-- 1 owner group size date name
                            stat = os.stat(full_entry)
                            sz = stat.st_size
                            mtime = time.strftime("%b %d %H:%M", time.localtime(stat.st_mtime))
                            is_dir = "d" if os.path.isdir(full_entry) else "-"
                            listing += f"{is_dir}rwxr-xr-x 1 ftp ftp {sz} {mtime} {entry}\r\n"
                        else:
                            listing += f"{entry}\r\n"
                else:
                    entry = os.path.basename(real_path)
                    stat = os.stat(real_path)
                    sz = stat.st_size
                    mtime = time.strftime("%b %d %H:%M", time.localtime(stat.st_mtime))
                    listing += f"-rwxr-xr-x 1 ftp ftp {sz} {mtime} {entry}\r\n"

                data_conn.sendall(listing.encode("utf-8"))
                data_conn.close()
                self.send_resp(226, "Directory send OK.")
            except OSError as e:
                self.send_resp(426, f"Connection closed; transfer aborted: {e}")
            finally:
                data_conn.close()
        elif cmd == "CWD":
            real_path, virt_path = self.get_absolute_path(args)
            if os.path.isdir(real_path):
                self.cwd = virt_path
                self.send_resp(250, f"Directory successfully changed to {self.cwd}")
            else:
                self.send_resp(550, "Failed to change directory.")
        elif cmd == "MKD":
            real_path, _ = self.get_absolute_path(args)
            try:
                os.makedirs(real_path, exist_ok=True)
                self.send_resp(257, f'"{args}" directory created.')
            except OSError as e:
                self.send_resp(550, f"Create directory failed: {e}")
        elif cmd == "RMD":
            real_path, _ = self.get_absolute_path(args)
            try:
                os.rmdir(real_path)
                self.send_resp(250, "Directory removed successfully.")
            except OSError as e:
                self.send_resp(550, f"Remove directory failed: {e}")
        elif cmd == "DELE":
            real_path, _ = self.get_absolute_path(args)
            try:
                os.remove(real_path)
                self.send_resp(250, "File deleted successfully.")
            except OSError as e:
                self.send_resp(550, f"Delete file failed: {e}")
        elif cmd == "SIZE":
            real_path, _ = self.get_absolute_path(args)
            if os.path.isfile(real_path):
                self.send_resp(213, str(os.path.getsize(real_path)))
            else:
                self.send_resp(550, "Could not get file size.")
        elif cmd == "RETR":
            real_path, _ = self.get_absolute_path(args)
            if not os.path.isfile(real_path):
                self.send_resp(550, "File not found.")
                return

            data_conn = self.establish_data_connection()
            if not data_conn:
                return

            self.send_resp(150, f"Opening data connection for {args}.")
            try:
                mode = "rb" if self.mode == "I" else "r"
                enc = None if self.mode == "I" else "utf-8"
                with open(real_path, mode, encoding=enc) as f:
                    while True:
                        chunk = f.read(8192)
                        if not chunk:
                            break
                        if self.mode == "I":
                            data_conn.sendall(chunk)
                        else:
                            data_conn.sendall(chunk.encode("utf-8"))
                data_conn.close()
                self.send_resp(226, "Transfer complete.")
            except OSError as e:
                self.send_resp(426, f"Connection closed; transfer aborted: {e}")
            finally:
                data_conn.close()
        elif cmd == "STOR":
            real_path, _ = self.get_absolute_path(args)
            data_conn = self.establish_data_connection()
            if not data_conn:
                return

            self.send_resp(150, f"Ok to send data for {args}.")
            try:
                # Ensure directory exists
                os.makedirs(os.path.dirname(real_path), exist_ok=True)
                
                mode = "wb" if self.mode == "I" else "w"
                enc = None if self.mode == "I" else "utf-8"
                with open(real_path, mode, encoding=enc) as f:
                    while True:
                        chunk = data_conn.recv(8192)
                        if not chunk:
                            break
                        if self.mode == "I":
                            f.write(chunk)
                        else:
                            f.write(chunk.decode("utf-8", errors="ignore"))
                data_conn.close()
                self.send_resp(226, "Transfer complete.")
            except OSError as e:
                self.send_resp(426, f"Connection closed; transfer aborted: {e}")
            finally:
                data_conn.close()
        else:
            self.send_resp(502, f"Command '{cmd}' not implemented on this mock server.")


class MockFTPServer:
    def __init__(self, host, port, root_dir, username, password, anonymous, verbose):
        self.host = host
        self.port = port
        self.root_dir = root_dir
        self.username = username
        self.password = password
        self.anonymous = anonymous
        self.verbose = verbose
        self.server_socket = None
        self.running = False

        os.makedirs(self.root_dir, exist_ok=True)

    def start(self):
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            self.server_socket.bind((self.host, self.port))
            self.server_socket.listen(5)
            self.running = True
            print(f"Mock FTP Server running on {self.host}:{self.port}")
            print(f"Root Directory: {os.path.abspath(self.root_dir)}")
            if self.anonymous:
                print("Authentication: ANONYMOUS allowed")
            else:
                print(f"Authentication: Username='{self.username}', Password='{self.password}'")
        except OSError as e:
            print(f"Failed to bind to {self.host}:{self.port} - {e}", file=sys.stderr)
            sys.exit(1)

        try:
            while self.running:
                self.server_socket.settimeout(1.0)
                try:
                    conn, addr = self.server_socket.accept()
                    if self.verbose:
                        print(f"[{addr[0]}:{addr[1]}] Control connection established.")
                    client_thread = FTPControlConnection(conn, addr, self)
                    client_thread.daemon = True
                    client_thread.start()
                except socket.timeout:
                    continue
        except KeyboardInterrupt:
            print("\nShutting down Mock FTP Server...")
        finally:
            self.stop()

    def stop(self):
        self.running = False
        if self.server_socket:
            self.server_socket.close()


def main():
    parser = argparse.ArgumentParser(description="Start a lightweight mock FTP server for testing.")
    parser.add_argument("--host", default="127.0.0.1", help="Host address to bind to.")
    parser.add_argument("--port", type=int, default=2121, help="Port to bind to (default: 2121).")
    parser.add_argument("--dir", default="./ftp_root", help="Root directory for FTP files (default: ./ftp_root).")
    parser.add_argument("--username", default="user", help="FTP username (default: user).")
    parser.add_argument("--password", default="pass", help="FTP password (default: pass).")
    parser.add_argument("--anonymous", action="store_true", help="Allow anonymous logins.")
    parser.add_argument("--verbose", action="store_true", help="Log control commands to stdout.")

    args = parser.parse_args()

    server = MockFTPServer(
        host=args.host,
        port=args.port,
        root_dir=args.dir,
        username=args.username,
        password=args.password,
        anonymous=args.anonymous,
        verbose=args.verbose
    )
    server.start()


if __name__ == "__main__":
    main()
