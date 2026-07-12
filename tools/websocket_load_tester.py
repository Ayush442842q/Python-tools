#!/usr/bin/env python3
"""
WebSocket Load Tester
Performs concurrent stress testing and throughput benchmarking on WebSocket servers.
Natively implements the WebSocket protocol (RFC 6455) handshake and frame encoding
using only standard libraries to measure connection limits, messages/sec, and latencies.
"""

import os
import sys
import time
import socket
import ssl
import base64
import argparse
import urllib.parse
import threading
import json
from typing import Dict, List, Tuple, Optional


def parse_ws_url(url: str) -> Tuple[bool, str, int, str]:
    """Parse a ws:// or wss:// URL into components."""
    parsed = urllib.parse.urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in ('ws', 'wss'):
        raise ValueError("URL scheme must be 'ws' or 'wss'")
    
    host = parsed.hostname
    if not host:
        raise ValueError("URL must contain a host")
    port = parsed.port
    if not port:
        port = 443 if scheme == 'wss' else 80
        
    path = parsed.path if parsed.path else '/'
    if parsed.query:
        path += '?' + parsed.query
        
    return scheme == 'wss', host, port, path


def connect_ws(secure: bool, host: str, port: int, path: str, timeout: float = 5.0) -> socket.socket:
    """Perform WebSocket handshake and return connected socket."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    
    if secure:
        context = ssl.create_default_context()
        sock = context.wrap_socket(sock, server_hostname=host)
        
    sock.connect((host, port))
    
    rand_bytes = os.urandom(16)
    key = base64.b64encode(rand_bytes).decode('utf-8')
    
    handshake_headers = [
        f"GET {path} HTTP/1.1",
        f"Host: {host}:{port}",
        "Upgrade: websocket",
        "Connection: Upgrade",
        f"Sec-WebSocket-Key: {key}",
        "Sec-WebSocket-Version: 13",
        "\r\n"
    ]
    
    sock.sendall(("\r\n".join(handshake_headers)).encode('utf-8'))
    
    # Read HTTP response headers
    response = b""
    while b"\r\n\r\n" not in response:
        chunk = sock.recv(1024)
        if not chunk:
            break
        response += chunk
        
    headers_part = response.split(b"\r\n\r\n")[0].decode('utf-8', errors='ignore')
    lines = headers_part.splitlines()
    
    if not lines or not lines[0].startswith("HTTP/1.1 101"):
        raise ConnectionError(f"Handshake failed: {lines[0] if lines else 'No response'}")
        
    return sock


def make_ws_frame(data: str, opcode: int = 1) -> bytes:
    """Create a masked WebSocket frame (client-to-server frames must be masked)."""
    payload = data.encode('utf-8') if isinstance(data, str) else data
    payload_len = len(payload)
    
    frame = bytearray()
    # FIN = 1, RSV = 0, Opcode
    frame.append(0x80 | (opcode & 0x0F))
    
    # Mask bit = 1
    if payload_len <= 125:
        frame.append(0x80 | payload_len)
    elif payload_len <= 65535:
        frame.append(0x80 | 126)
        frame.extend(payload_len.to_bytes(2, byteorder='big'))
    else:
        frame.append(0x80 | 127)
        frame.extend(payload_len.to_bytes(8, byteorder='big'))
        
    mask_key = os.urandom(4)
    frame.extend(mask_key)
    
    masked_payload = bytearray(payload_len)
    for i in range(payload_len):
        masked_payload[i] = payload[i] ^ mask_key[i % 4]
        
    frame.extend(masked_payload)
    return bytes(frame)


def recv_ws_frame(sock: socket.socket) -> Tuple[Optional[int], Optional[bytes]]:
    """Receive and parse a WebSocket frame."""
    try:
        header = sock.recv(2)
        if len(header) < 2:
            return None, None
            
        opcode = header[0] & 0x0F
        masked = bool(header[1] & 0x80)
        payload_len = header[1] & 0x7F
        
        if payload_len == 126:
            len_bytes = sock.recv(2)
            payload_len = int.from_bytes(len_bytes, byteorder='big')
        elif payload_len == 127:
            len_bytes = sock.recv(8)
            payload_len = int.from_bytes(len_bytes, byteorder='big')
            
        if masked:
            mask_key = sock.recv(4)
            
        payload = bytearray()
        while len(payload) < payload_len:
            chunk = sock.recv(payload_len - len(payload))
            if not chunk:
                break
            payload.extend(chunk)
            
        if masked:
            for i in range(len(payload)):
                payload[i] ^= mask_key[i % 4]
                
        return opcode, bytes(payload)
    except Exception:
        return None, None


class LoadTesterClient:
    def __init__(self, client_id: int, secure: bool, host: str, port: int, path: str,
                 duration: float, rate: float, payload: str):
        self.client_id = client_id
        self.secure = secure
        self.host = host
        self.port = port
        self.path = path
        self.duration = duration
        self.rate = rate  # Msg per second
        self.payload = payload
        
        self.sent_count = 0
        self.recv_count = 0
        self.latencies: List[float] = []
        self.errors = 0
        self.connected = False
        self.bytes_sent = 0
        self.bytes_recv = 0
        
    def run(self):
        try:
            sock = connect_ws(self.secure, self.host, self.port, self.path)
            self.connected = True
        except Exception:
            self.errors += 1
            return
            
        sock.setblocking(False)
        start_time = time.perf_counter()
        next_send_time = start_time
        
        frame_to_send = make_ws_frame(self.payload)
        frame_len = len(frame_to_send)
        
        # Track pending responses
        # key: send_time_stamp
        pending_sends = []
        
        while time.perf_counter() - start_time < self.duration:
            now = time.perf_counter()
            
            # Send phase (pacing message sending)
            if now >= next_send_time:
                try:
                    sock.sendall(frame_to_send)
                    self.sent_count += 1
                    self.bytes_sent += frame_len
                    pending_sends.append(now)
                    next_send_time = now + (1.0 / self.rate)
                except (socket.error, ConnectionError):
                    self.errors += 1
                    break
                    
            # Read phase (non-blocking read)
            try:
                op, resp = recv_ws_frame(sock)
                if op is not None:
                    self.recv_count += 1
                    self.bytes_recv += len(resp) if resp else 0
                    if pending_sends:
                        send_t = pending_sends.pop(0)
                        rtt = (time.perf_counter() - send_t) * 1000  # ms
                        self.latencies.append(rtt)
            except BlockingIOError:
                # No data to read yet
                pass
            except Exception:
                self.errors += 1
                break
                
            # Short sleep to prevent 100% CPU utilization
            time.sleep(0.001)
            
        try:
            sock.sendall(make_ws_frame("", opcode=0x08))  # Close frame
            sock.close()
        except Exception:
            pass


def main():
    parser = argparse.ArgumentParser(description="WebSocket Concurrency Stress & Load Tester")
    parser.add_argument("url", help="WebSocket endpoint to test (ws:// or wss://)")
    parser.add_argument("-c", "--concurrency", type=int, default=10, help="Number of concurrent clients (default: 10)")
    parser.add_argument("-d", "--duration", type=int, default=10, help="Test duration in seconds (default: 10)")
    parser.add_argument("-r", "--rate", type=float, default=5.0, help="Message send rate per client per second (default: 5.0)")
    parser.add_argument("-s", "--size", type=int, default=128, help="Message payload size in bytes (default: 128)")
    parser.add_argument("--ramp-up", type=float, default=1.0, help="Ramp up duration for connecting clients in seconds (default: 1.0)")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    
    args = parser.parse_args()
    
    try:
        secure, host, port, path = parse_ws_url(args.url)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
        
    payload = "x" * args.size
    clients: List[LoadTesterClient] = []
    threads: List[threading.Thread] = []
    
    if not args.json:
        print("====================================================")
        print("           WEBSOCKET STRESS LOAD TESTER             ")
        print("====================================================")
        print(f"Target URL:    {args.url}")
        print(f"Concurrency:   {args.concurrency} concurrent client(s)")
        print(f"Ramp Up Time:  {args.ramp_up}s")
        print(f"Duration:      {args.duration}s")
        print(f"Rate/Client:   {args.rate} msg/s (Total Target: {args.concurrency * args.rate:.1f} msg/s)")
        print(f"Payload Size:  {args.size} bytes")
        print("----------------------------------------------------")
        print("Spawning clients...")

    # Spawn clients with ramp up pacing
    start_spawn = time.perf_counter()
    ramp_interval = args.ramp_up / args.concurrency if args.concurrency > 1 else 0
    
    for i in range(args.concurrency):
        client = LoadTesterClient(i, secure, host, port, path, args.duration, args.rate, payload)
        clients.append(client)
        
        t = threading.Thread(target=client.run)
        threads.append(t)
        t.start()
        
        if ramp_interval > 0:
            time.sleep(ramp_interval)
            
    # Wait for all clients to finish
    for t in threads:
        t.join()
        
    # Analyze stats
    total_sent = 0
    total_recv = 0
    total_bytes_sent = 0
    total_bytes_recv = 0
    total_errors = 0
    successful_conns = 0
    all_latencies = []
    
    for client in clients:
        total_sent += client.sent_count
        total_recv += client.recv_count
        total_bytes_sent += client.bytes_sent
        total_bytes_recv += client.bytes_recv
        total_errors += client.errors
        if client.connected:
            successful_conns += 1
        all_latencies.extend(client.latencies)
        
    duration_actual = time.perf_counter() - start_spawn
    
    avg_latency = sum(all_latencies) / len(all_latencies) if all_latencies else 0
    min_latency = min(all_latencies) if all_latencies else 0
    max_latency = max(all_latencies) if all_latencies else 0
    
    throughput_sent = total_sent / args.duration
    throughput_recv = total_recv / args.duration
    bandwidth_sent_kb = (total_bytes_sent / 1024) / args.duration
    bandwidth_recv_kb = (total_bytes_recv / 1024) / args.duration
    
    # Calculate simple percentile distributions
    all_latencies.sort()
    p50 = all_latencies[int(len(all_latencies) * 0.50)] if all_latencies else 0
    p90 = all_latencies[int(len(all_latencies) * 0.90)] if all_latencies else 0
    p99 = all_latencies[int(len(all_latencies) * 0.99)] if all_latencies else 0
    
    report = {
        "concurrency_target": args.concurrency,
        "concurrency_connected": successful_conns,
        "total_sent": total_sent,
        "total_recv": total_recv,
        "throughput_sent_msg_per_sec": round(throughput_sent, 2),
        "throughput_recv_msg_per_sec": round(throughput_recv, 2),
        "bandwidth_sent_kb_per_sec": round(bandwidth_sent_kb, 2),
        "bandwidth_recv_kb_per_sec": round(bandwidth_recv_kb, 2),
        "errors": total_errors,
        "latency_min_ms": round(min_latency, 2),
        "latency_max_ms": round(max_latency, 2),
        "latency_avg_ms": round(avg_latency, 2),
        "latency_p50_ms": round(p50, 2),
        "latency_p90_ms": round(p90, 2),
        "latency_p99_ms": round(p99, 2),
    }
    
    if args.json:
        print(json.dumps(report, indent=2))
        return
        
    print("\n================== BENCHMARK RESULTS ==================")
    print(f"Connections Opened:  {successful_conns} / {args.concurrency} ({successful_conns/args.concurrency*100:.1f}%)")
    print(f"Total Messages:      Sent: {total_sent} | Received: {total_recv}")
    print(f"Msg Throughput:      Sent: {throughput_sent:.1f} msg/s | Received: {throughput_recv:.1f} msg/s")
    print(f"Data Bandwidth:      Sent: {bandwidth_sent_kb:.1f} KB/s | Received: {bandwidth_recv_kb:.1f} KB/s")
    print(f"Protocol Errors:     {total_errors}")
    print("-------------------------------------------------------")
    print(f"RTT Latency (ms):")
    print(f"  Min:  {min_latency:.2f} ms")
    print(f"  Avg:  {avg_latency:.2f} ms")
    print(f"  Max:  {max_latency:.2f} ms")
    print(f"  P50:  {p50:.2f} ms")
    print(f"  P90:  {p90:.2f} ms")
    print(f"  P99:  {p99:.2f} ms")
    
    # ASCII Histogram if there are latencies
    if all_latencies:
        print("-------------------------------------------------------")
        print("RTT Latency Distribution Histogram (ms):")
        # Divide into 5 buckets
        num_buckets = 5
        min_l, max_l = all_latencies[0], all_latencies[-1]
        bucket_size = (max_l - min_l) / num_buckets if max_l > min_l else 1
        buckets = [0] * num_buckets
        
        for l in all_latencies:
            b_idx = int((l - min_l) / bucket_size)
            if b_idx >= num_buckets:
                b_idx = num_buckets - 1
            buckets[b_idx] += 1
            
        max_bucket_val = max(buckets) if max(buckets) > 0 else 1
        for i in range(num_buckets):
            b_min = min_l + (i * bucket_size)
            b_max = b_min + bucket_size
            bar_len = int((buckets[i] / max_bucket_val) * 20)
            bar = "█" * bar_len
            print(f"  [{b_min:6.1f} - {b_max:6.1f} ms] : {buckets[i]:4d} | {bar}")
    print("=======================================================")


if __name__ == "__main__":
    main()
