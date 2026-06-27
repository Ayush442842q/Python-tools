#!/usr/bin/env python3
"""
Mock Redis Server - A lightweight, in-memory, TCP-based Redis mock server.
Implements the Redis Serialization Protocol (RESP) and supports basic commands.

Usage:
    python tools/mock_redis_server.py [--host HOST] [--port PORT]

Example:
    python tools/mock_redis_server.py --port 6379
"""

import argparse
import socket
import sys
import threading
import time
import fnmatch

class RedisDb:
    def __init__(self):
        self.data = {}      # key -> value (string)
        self.expires = {}   # key -> timestamp (float)
        self.lock = threading.Lock()

    def _is_expired(self, key):
        if key in self.expires:
            if time.time() > self.expires[key]:
                self.data.pop(key, None)
                self.expires.pop(key, None)
                return True
        return False

    def get(self, key):
        with self.lock:
            if self._is_expired(key):
                return None
            return self.data.get(key)

    def set(self, key, value, expire_at=None):
        with self.lock:
            self.data[key] = value
            if expire_at:
                self.expires[key] = expire_at
            else:
                self.expires.pop(key, None)
            return True

    def delete(self, keys):
        count = 0
        with self.lock:
            for key in keys:
                self._is_expired(key)
                if key in self.data:
                    self.data.pop(key)
                    self.expires.pop(key, None)
                    count += 1
            return count

    def exists(self, keys):
        count = 0
        with self.lock:
            for key in keys:
                if not self._is_expired(key) and key in self.data:
                    count += 1
            return count

    def incr(self, key, amount=1):
        with self.lock:
            if self._is_expired(key):
                val = "0"
            else:
                val = self.data.get(key, "0")
            try:
                int_val = int(val) + amount
                self.data[key] = str(int_val)
                return int_val
            except ValueError:
                raise ValueError("ERR value is not an integer or out of range")

    def expire(self, key, seconds):
        with self.lock:
            if self._is_expired(key) or key not in self.data:
                return 0
            self.expires[key] = time.time() + seconds
            return 1

    def ttl(self, key):
        with self.lock:
            if self._is_expired(key) or key not in self.data:
                return -2
            if key not in self.expires:
                return -1
            return int(self.expires[key] - time.time())

    def keys(self, pattern):
        with self.lock:
            # Clean up expired keys first
            expired_keys = [k for k in self.expires if time.time() > self.expires[k]]
            for k in expired_keys:
                self.data.pop(k, None)
                self.expires.pop(k, None)
            
            all_keys = list(self.data.keys())
            return fnmatch.filter(all_keys, pattern)

    def flushdb(self):
        with self.lock:
            self.data.clear()
            self.expires.clear()
            return True

    def dbsize(self):
        with self.lock:
            expired_keys = [k for k in self.expires if time.time() > self.expires[k]]
            for k in expired_keys:
                self.data.pop(k, None)
                self.expires.pop(k, None)
            return len(self.data)


# RESP Serialization functions
def serialize_simple_string(s):
    return f"+{s}\r\n".encode('utf-8')

def serialize_error(err):
    return f"-{err}\r\n".encode('utf-8')

def serialize_integer(i):
    return f":{i}\r\n".encode('utf-8')

def serialize_bulk_string(s):
    if s is None:
        return b"$-1\r\n"
    s_bytes = s.encode('utf-8')
    return f"${len(s_bytes)}\r\n".encode('utf-8') + s_bytes + b"\r\n"

def serialize_array(arr):
    if arr is None:
        return b"*-1\r\n"
    res = f"*{len(arr)}\r\n".encode('utf-8')
    for item in arr:
        if isinstance(item, str):
            res += serialize_bulk_string(item)
        elif isinstance(item, int):
            res += serialize_integer(item)
        elif isinstance(item, list):
            res += serialize_array(item)
        elif item is None:
            res += b"$-1\r\n"
        else:
            res += serialize_bulk_string(str(item))
    return res


# RESP Parsing function
def read_resp(rfile):
    line = rfile.readline()
    if not line:
        return None
    prefix = line[0:1]
    payload = line[1:-2]  # strip prefix and \r\n
    
    if prefix == b'+':
        return payload.decode('utf-8')
    elif prefix == b'-':
        return Exception(payload.decode('utf-8'))
    elif prefix == b':':
        return int(payload)
    elif prefix == b'$':
        length = int(payload)
        if length == -1:
            return None
        data = rfile.read(length)
        rfile.read(2)  # consume \r\n
        return data.decode('utf-8')
    elif prefix == b'*':
        count = int(payload)
        if count == -1:
            return None
        items = []
        for _ in range(count):
            items.append(read_resp(rfile))
        return items
    raise ValueError(f"Unknown RESP type prefix: {prefix}")


class ClientHandler(threading.Thread):
    def __init__(self, conn, addr, db):
        super().__init__()
        self.conn = conn
        self.addr = addr
        self.db = db
        self.running = True

    def run(self):
        print(f"[*] Client connected from {self.addr[0]}:{self.addr[1]}")
        rfile = self.conn.makefile('rb')
        try:
            while self.running:
                req = read_resp(rfile)
                if req is None:
                    break
                
                if not isinstance(req, list) or len(req) == 0:
                    self.conn.sendall(serialize_error("ERR Protocol error: expected array"))
                    continue
                
                cmd = req[0].upper()
                args = req[1:]
                
                print(f"[Command] {self.addr[0]}:{self.addr[1]} -> {cmd} {args}")
                
                try:
                    response = self.handle_command(cmd, args)
                    self.conn.sendall(response)
                except Exception as e:
                    self.conn.sendall(serialize_error(str(e)))
        except ConnectionResetError:
            pass
        except Exception as e:
            print(f"[!] Error handling client {self.addr}: {e}")
        finally:
            rfile.close()
            self.conn.close()
            print(f"[*] Client disconnected: {self.addr[0]}:{self.addr[1]}")

    def handle_command(self, cmd, args):
        if cmd == "PING":
            msg = args[0] if len(args) > 0 else "PONG"
            return serialize_simple_string(msg)
            
        elif cmd == "SET":
            if len(args) < 2:
                return serialize_error("ERR wrong number of arguments for 'set' command")
            key, val = args[0], args[1]
            expire_at = None
            
            # Parse SET extra options (EX, PX)
            i = 2
            while i < len(args):
                opt = args[i].upper()
                if opt == "EX" and i + 1 < len(args):
                    expire_at = time.time() + int(args[i+1])
                    i += 2
                elif opt == "PX" and i + 1 < len(args):
                    expire_at = time.time() + (int(args[i+1]) / 1000.0)
                    i += 2
                else:
                    return serialize_error(f"ERR syntax error at option {args[i]}")
            
            self.db.set(key, val, expire_at)
            return serialize_simple_string("OK")
            
        elif cmd == "GET":
            if len(args) != 1:
                return serialize_error("ERR wrong number of arguments for 'get' command")
            val = self.db.get(args[0])
            return serialize_bulk_string(val)
            
        elif cmd == "DEL":
            if len(args) < 1:
                return serialize_error("ERR wrong number of arguments for 'del' command")
            count = self.db.delete(args)
            return serialize_integer(count)
            
        elif cmd == "EXISTS":
            if len(args) < 1:
                return serialize_error("ERR wrong number of arguments for 'exists' command")
            count = self.db.exists(args)
            return serialize_integer(count)
            
        elif cmd == "INCR":
            if len(args) != 1:
                return serialize_error("ERR wrong number of arguments for 'incr' command")
            try:
                new_val = self.db.incr(args[0], 1)
                return serialize_integer(new_val)
            except ValueError as e:
                return serialize_error(str(e))
                
        elif cmd == "DECR":
            if len(args) != 1:
                return serialize_error("ERR wrong number of arguments for 'decr' command")
            try:
                new_val = self.db.incr(args[0], -1)
                return serialize_integer(new_val)
            except ValueError as e:
                return serialize_error(str(e))
                
        elif cmd == "EXPIRE":
            if len(args) != 2:
                return serialize_error("ERR wrong number of arguments for 'expire' command")
            try:
                seconds = int(args[1])
                res = self.db.expire(args[0], seconds)
                return serialize_integer(res)
            except ValueError:
                return serialize_error("ERR value is not an integer or out of range")
                
        elif cmd == "TTL":
            if len(args) != 1:
                return serialize_error("ERR wrong number of arguments for 'ttl' command")
            res = self.db.ttl(args[0])
            return serialize_integer(res)
            
        elif cmd == "KEYS":
            if len(args) != 1:
                return serialize_error("ERR wrong number of arguments for 'keys' command")
            matched = self.db.keys(args[0])
            return serialize_array(matched)
            
        elif cmd == "FLUSHDB":
            self.db.flushdb()
            return serialize_simple_string("OK")
            
        elif cmd == "DBSIZE":
            size = self.db.dbsize()
            return serialize_integer(size)
            
        elif cmd == "COMMAND":
            # Command returns command descriptions (standard behavior for clients like redis-cli)
            # We return empty array to keep it simple and compatible
            return serialize_array([])
            
        elif cmd == "QUIT":
            self.running = False
            return serialize_simple_string("OK")
            
        else:
            return serialize_error(f"ERR unknown command '{cmd}'")


def main():
    parser = argparse.ArgumentParser(description="Mock Redis Server in pure Python")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind to")
    parser.add_argument("--port", type=int, default=6379, help="Port to listen on")
    args = parser.parse_args()

    db = RedisDb()
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_socket.bind((args.host, args.port))
        server_socket.listen(10)
        print(f"[*] Mock Redis Server running on {args.host}:{args.port}")
        print("[*] Press Ctrl+C to stop.")
    except Exception as e:
        print(f"[!] Failed to bind to {args.host}:{args.port} - {e}")
        return 1

    try:
        while True:
            conn, addr = server_socket.accept()
            handler = ClientHandler(conn, addr, db)
            handler.daemon = True
            handler.start()
    except KeyboardInterrupt:
        print("\n[*] Stopping Mock Redis Server...")
    finally:
        server_socket.close()
    return 0

if __name__ == "__main__":
    sys.exit(main())
