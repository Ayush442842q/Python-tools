#!/usr/bin/env python3
"""
WebSocket Client & Echo Server (RFC 6455)
A standalone, pure-Python implementation of the WebSocket protocol.
Supports both an interactive CLI client (ws:// and wss://) and a multi-threaded echo server.
"""

import sys
import os
import socket
import ssl
import hashlib
import base64
import struct
import threading
import argparse
import urllib.parse

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"

# Opcodes
OP_CONT = 0x0
OP_TEXT = 0x1
OP_BINARY = 0x2
OP_CLOSE = 0x8
OP_PING = 0x9
OP_PONG = 0xA

class WebSocketFrame:
    def __init__(self, opcode, payload=b"", fin=True, masked=True):
        self.opcode = opcode
        self.payload = payload
        self.fin = fin
        self.masked = masked

    def encode(self):
        header = bytearray()
        first_byte = (0x80 if self.fin else 0x00) | self.opcode
        header.append(first_byte)

        payload_len = len(self.payload)
        mask_bit = 0x80 if self.masked else 0x00

        if payload_len <= 125:
            header.append(mask_bit | payload_len)
        elif payload_len <= 65535:
            header.append(mask_bit | 126)
            header.extend(struct.pack("!H", payload_len))
        else:
            header.append(mask_bit | 127)
            header.extend(struct.pack("!Q", payload_len))

        if self.masked:
            masking_key = os.urandom(4)
            header.extend(masking_key)
            # Mask payload
            masked_payload = bytearray(
                b ^ masking_key[i % 4] for i, b in enumerate(self.payload)
            )
            return bytes(header + masked_payload)
        else:
            return bytes(header + self.payload)

    @classmethod
    def decode_from_socket(cls, sock):
        try:
            # Read first two bytes of header
            data = sock.recv(2)
            if not data or len(data) < 2:
                return None
            
            first_byte, second_byte = data[0], data[1]
            fin = bool(first_byte & 0x80)
            opcode = first_byte & 0x0F
            masked = bool(second_byte & 0x80)
            payload_len = second_byte & 0x7F

            if payload_len == 126:
                len_bytes = sock.recv(2)
                if len(len_bytes) < 2:
                    return None
                payload_len = struct.unpack("!H", len_bytes)[0]
            elif payload_len == 127:
                len_bytes = sock.recv(8)
                if len(len_bytes) < 8:
                    return None
                payload_len = struct.unpack("!Q", len_bytes)[0]

            masking_key = b""
            if masked:
                masking_key = sock.recv(4)
                if len(masking_key) < 4:
                    return None

            # Read payload in chunks
            payload = bytearray()
            remaining = payload_len
            while remaining > 0:
                chunk = sock.recv(min(remaining, 4096))
                if not chunk:
                    break
                payload.extend(chunk)
                remaining -= len(chunk)

            if len(payload) < payload_len:
                return None

            # Unmask payload if masked
            if masked:
                unmasked = bytes(b ^ masking_key[i % 4] for i, b in enumerate(payload))
            else:
                unmasked = bytes(payload)

            return cls(opcode, unmasked, fin, masked)
        except Exception:
            return None


def generate_handshake_key():
    return base64.b64encode(os.urandom(16)).decode('utf-8')


def get_handshake_accept(key):
    sha1 = hashlib.sha1((key + GUID).encode('utf-8')).digest()
    return base64.b64encode(sha1).decode('utf-8')


class WebSocketClient:
    def __init__(self, url):
        self.url = url
        self.parsed_url = urllib.parse.urlparse(url)
        if self.parsed_url.scheme not in ('ws', 'wss'):
            raise ValueError("URL scheme must be ws or wss")
        
        self.host = self.parsed_url.hostname
        self.port = self.parsed_url.port or (443 if self.parsed_url.scheme == 'wss' else 80)
        self.path = self.parsed_url.path or '/'
        if self.parsed_url.query:
            self.path += '?' + self.parsed_url.query

        self.sock = None
        self.connected = False

    def connect(self):
        print(f"[*] Connecting to {self.host}:{self.port}...", flush=True)
        raw_sock = socket.create_connection((self.host, self.port), timeout=10)

        if self.parsed_url.scheme == 'wss':
            context = ssl.create_default_context()
            self.sock = context.wrap_socket(raw_sock, server_hostname=self.host)
        else:
            self.sock = raw_sock

        key = generate_handshake_key()
        handshake_req = (
            f"GET {self.path} HTTP/1.1\r\n"
            f"Host: {self.host}:{self.port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n\r\n"
        )
        self.sock.sendall(handshake_req.encode('utf-8'))

        # Read handshake response
        response = b""
        while b"\r\n\r\n" not in response:
            chunk = self.sock.recv(1024)
            if not chunk:
                break
            response += chunk

        header_part = response.split(b"\r\n\r\n")[0].decode('utf-8')
        lines = header_part.split("\r\n")
        status_line = lines[0]

        if "101" not in status_line:
            raise RuntimeError(f"Handshake failed: {status_line}")

        headers = {}
        for line in lines[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()

        expected_accept = get_handshake_accept(key)
        actual_accept = headers.get('sec-websocket-accept')

        if actual_accept != expected_accept:
            raise RuntimeError("Handshake failed: invalid Sec-WebSocket-Accept key")

        self.connected = True
        print("[+] Connection established!", flush=True)

    def send(self, message, is_binary=False):
        if not self.connected:
            raise RuntimeError("Not connected")
        opcode = OP_BINARY if is_binary else OP_TEXT
        payload = message if isinstance(message, bytes) else message.encode('utf-8')
        frame = WebSocketFrame(opcode, payload, fin=True, masked=True)
        self.sock.sendall(frame.encode())

    def receive(self):
        if not self.connected:
            raise RuntimeError("Not connected")
        frame = WebSocketFrame.decode_from_socket(self.sock)
        if frame is None:
            self.connected = False
            return None
        return frame

    def close(self):
        if self.connected:
            try:
                frame = WebSocketFrame(OP_CLOSE, b"", fin=True, masked=True)
                self.sock.sendall(frame.encode())
            except Exception:
                pass
        if self.sock:
            self.sock.close()
        self.connected = False
        print("[*] Connection closed.", flush=True)


def handle_server_client(client_sock, client_addr):
    print(f"[+] Client connected from {client_addr[0]}:{client_addr[1]}")
    try:
        # Handshake
        request = b""
        while b"\r\n\r\n" not in request:
            chunk = client_sock.recv(1024)
            if not chunk:
                break
            request += chunk
        
        if not request:
            return

        header_part = request.split(b"\r\n\r\n")[0].decode('utf-8', errors='ignore')
        lines = header_part.split("\r\n")
        
        headers = {}
        for line in lines[1:]:
            if ":" in line:
                k, v = line.split(":", 1)
                headers[k.strip().lower()] = v.strip()

        ws_key = headers.get("sec-websocket-key")
        if not ws_key:
            client_sock.sendall(b"HTTP/1.1 400 Bad Request\r\n\r\n")
            return

        accept_key = get_handshake_accept(ws_key)
        response = (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            f"Sec-WebSocket-Accept: {accept_key}\r\n\r\n"
        )
        client_sock.sendall(response.encode('utf-8'))

        # Echo loop
        while True:
            frame = WebSocketFrame.decode_from_socket(client_sock)
            if frame is None or frame.opcode == OP_CLOSE:
                break
            
            if frame.opcode == OP_PING:
                pong = WebSocketFrame(OP_PONG, frame.payload, fin=True, masked=False)
                client_sock.sendall(pong.encode())
            elif frame.opcode in (OP_TEXT, OP_BINARY):
                # Echo the exact payload back
                if frame.opcode == OP_TEXT:
                    msg = frame.payload.decode('utf-8', errors='ignore')
                    print(f"[{client_addr[0]}:{client_addr[1]}] Text received: {msg}")
                else:
                    print(f"[{client_addr[0]}:{client_addr[1]}] Binary received: {len(frame.payload)} bytes")
                
                echo_frame = WebSocketFrame(frame.opcode, frame.payload, fin=True, masked=False)
                client_sock.sendall(echo_frame.encode())

    except Exception as e:
        print(f"[-] Error handling client {client_addr}: {e}")
    finally:
        client_sock.close()
        print(f"[-] Client disconnected: {client_addr[0]}:{client_addr[1]}")


def run_server(host, port):
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        server.bind((host, port))
        server.listen(5)
        print(f"[*] WebSocket Echo Server listening on ws://{host}:{port}")
        while True:
            client_sock, client_addr = server.accept()
            t = threading.Thread(target=handle_server_client, args=(client_sock, client_addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("\n[*] Stopping server.")
    finally:
        server.close()


def run_client(url):
    client = WebSocketClient(url)
    try:
        client.connect()
    except Exception as e:
        print(f"[-] Connection failed: {e}")
        return

    # Receiver thread
    def receive_loop():
        while client.connected:
            frame = client.receive()
            if frame is None:
                print("\n[-] Connection closed by remote server.")
                break
            if frame.opcode == OP_TEXT:
                print(f"\n<- {frame.payload.decode('utf-8', errors='ignore')}\nws> ", end="", flush=True)
            elif frame.opcode == OP_BINARY:
                print(f"\n<- [Binary payload: {len(frame.payload)} bytes]\nws> ", end="", flush=True)
            elif frame.opcode == OP_PONG:
                print("\n<- Pong frame received\nws> ", end="", flush=True)

    t = threading.Thread(target=receive_loop, daemon=True)
    t.start()

    print("[*] Type messages and press Enter. Type '/exit' or '/quit' to exit.")
    try:
        while client.connected:
            msg = input("ws> ")
            if msg.strip() in ('/exit', '/quit'):
                break
            if not client.connected:
                break
            client.send(msg)
    except KeyboardInterrupt:
        pass
    finally:
        client.close()


def main():
    parser = argparse.ArgumentParser(description="Standalone Pure-Python WebSocket Tool (RFC 6455)")
    subparsers = parser.add_subparsers(dest="mode", required=True, help="Mode to run in (client or server)")

    client_parser = subparsers.add_parser("client", help="Run as an interactive WebSocket client")
    client_parser.add_argument("url", help="WebSocket URL to connect to (ws://... or wss://...)")

    server_parser = subparsers.add_parser("server", help="Run as a WebSocket echo server")
    server_parser.add_argument("--host", default="localhost", help="Host to bind server to")
    server_parser.add_argument("--port", type=int, default=8765, help="Port to bind server to")

    args = parser.parse_args()

    if args.mode == "client":
        run_client(args.url)
    elif args.mode == "server":
        run_server(args.host, args.port)


if __name__ == "__main__":
    main()
