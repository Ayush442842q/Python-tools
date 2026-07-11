#!/usr/bin/env python3
"""
WebSocket Ping Tester & Load Benchmarker
Natively implements the WebSocket protocol (RFC 6455) handshake and frame encoding
using only Python standard library to test latency and perform concurrency benchmarking.
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

def parse_ws_url(url):
    """Parse a ws:// or wss:// URL into components."""
    parsed = urllib.parse.urlparse(url)
    scheme = parsed.scheme.lower()
    if scheme not in ('ws', 'wss'):
        raise ValueError("URL scheme must be 'ws' or 'wss'")
    
    host = parsed.hostname
    port = parsed.port
    if not port:
        port = 443 if scheme == 'wss' else 80
        
    path = parsed.path if parsed.path else '/'
    if parsed.query:
        path += '?' + parsed.query
        
    return scheme == 'wss', host, port, path

def connect_ws(secure, host, port, path, timeout=10):
    """Perform WebSocket handshake and return connected socket."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    
    if secure:
        context = ssl.create_default_context()
        sock = context.wrap_socket(sock, server_hostname=host)
        
    sock.connect((host, port))
    
    # Generate client handshake key
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
        raise ConnectionError(f"WebSocket handshake failed: {lines[0] if lines else 'No response'}")
        
    return sock

def make_ws_frame(data, opcode=1):
    """Create a masked WebSocket frame (client frames must be masked)."""
    payload = data.encode('utf-8') if isinstance(data, str) else data
    payload_len = len(payload)
    
    frame = bytearray()
    # FIN bit = 1, RSV = 0, opcode
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
        
    # Masking key
    mask_key = os.urandom(4)
    frame.extend(mask_key)
    
    # Mask payload
    masked_payload = bytearray(payload_len)
    for i in range(payload_len):
        masked_payload[i] = payload[i] ^ mask_key[i % 4]
        
    frame.extend(masked_payload)
    return bytes(frame)

def recv_ws_frame(sock):
    """Receive and parse a WebSocket frame."""
    header = sock.recv(2)
    if len(header) < 2:
        return None, None
        
    fin = bool(header[0] & 0x80)
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

def ping_worker(thread_id, secure, host, port, path, count, interval, payload_size, results):
    """Thread worker to run ping tests on a single socket."""
    latencies = []
    lost = 0
    
    try:
        sock = connect_ws(secure, host, port, path)
    except Exception as e:
        results[thread_id] = {"error": str(e)}
        return

    # Payload to send
    ping_data = "x" * payload_size
    
    for i in range(count):
        try:
            start_time = time.perf_counter()
            # Send custom Ping frame (opcode 0x09)
            sock.sendall(make_ws_frame(ping_data, opcode=0x09))
            
            # Wait for Pong frame (opcode 0x0A) or text frame responding
            sock.settimeout(3.0)  # 3 second timeout for response
            while True:
                op, resp = recv_ws_frame(sock)
                if op is None:
                    # Connection closed
                    lost += (count - i)
                    break
                # 0x0A is Pong, 0x01 is Text echo
                if op in (0x0A, 0x01, 0x09): 
                    end_time = time.perf_counter()
                    rtt = (end_time - start_time) * 1000  # in ms
                    latencies.append(rtt)
                    break
            
            if i < count - 1:
                time.sleep(interval)
        except (socket.timeout, ConnectionError):
            lost += 1
            
    try:
        # Send close frame
        sock.sendall(make_ws_frame(b"", opcode=0x08))
        sock.close()
    except Exception:
        pass
        
    results[thread_id] = {
        "latencies": latencies,
        "lost": lost,
        "total": count
    }

def main():
    parser = argparse.ArgumentParser(description="WebSocket Ping Tester & Concurrency Benchmarker")
    parser.add_argument("url", help="WebSocket URL to test (ws:// or wss://)")
    parser.add_argument("-c", "--count", type=int, default=5, help="Number of pings to send per connection (default: 5)")
    parser.add_argument("-i", "--interval", type=float, default=1.0, help="Interval in seconds between pings (default: 1.0)")
    parser.add_argument("-s", "--size", type=int, default=32, help="Payload size in bytes (default: 32)")
    parser.add_argument("-n", "--connections", type=int, default=1, help="Number of concurrent connections/threads (default: 1)")
    parser.add_argument("-o", "--output", help="Save performance logs to CSV file")
    
    args = parser.parse_args()
    
    try:
        secure, host, port, path = parse_ws_url(args.url)
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
        
    print(f"WebSocket Ping Test Parameters:")
    print(f"  Target URL:   {args.url}")
    print(f"  Secure (SSL): {secure}")
    print(f"  Host:         {host}:{port}")
    print(f"  Path:         {path}")
    print(f"  Connections:  {args.connections} concurrent client(s)")
    print(f"  Pings/Client: {args.count}")
    print(f"  Ping Interval:{args.interval}s")
    print(f"  Payload Size: {args.size} bytes")
    print("=" * 60)
    print("Connecting and starting benchmark...")

    results = {}
    threads = []
    
    start_bench = time.perf_counter()
    for t_id in range(args.connections):
        t = threading.Thread(
            target=ping_worker,
            args=(t_id, secure, host, port, path, args.count, args.interval, args.size, results)
        )
        threads.append(t)
        t.start()
        
    for t in threads:
        t.join()
    end_bench = time.perf_counter()
    
    # Process results
    total_latency_list = []
    total_pings_sent = 0
    total_pings_lost = 0
    failed_connections = 0
    
    for t_id, res in results.items():
        if "error" in res:
            failed_connections += 1
            total_pings_lost += args.count
            print(f"  [Client {t_id}] Connection error: {res['error']}")
        else:
            total_latency_list.extend(res["latencies"])
            total_pings_lost += res["lost"]
            total_pings_sent += res["total"]

    print("=" * 60)
    print(f"Benchmark finished in {end_bench - start_bench:.2f} seconds.")
    print(f"Connections Status: {args.connections - failed_connections}/{args.connections} Successful")
    
    if total_pings_sent == 0:
        print("Error: All connections failed. Could not measure latency.")
        sys.exit(1)
        
    loss_pct = (total_pings_lost / (args.connections * args.count)) * 100
    
    # Stats calculations
    total_latency_list.sort()
    min_lat = total_latency_list[0]
    max_lat = total_latency_list[-1]
    avg_lat = sum(total_latency_list) / len(total_latency_list)
    mid = len(total_latency_list) // 2
    med_lat = total_latency_list[mid] if len(total_latency_list) % 2 != 0 else (total_latency_list[mid-1] + total_latency_list[mid]) / 2

    print("\n--- Latency & Loss Statistics ---")
    print(f"  Pings Transmitted: {args.connections * args.count}")
    print(f"  Pings Received:    {len(total_latency_list)}")
    print(f"  Pings Lost:        {total_pings_lost} ({loss_pct:.1f}% loss)")
    print(f"  Min RTT Latency:   {min_lat:.2f} ms")
    print(f"  Max RTT Latency:   {max_lat:.2f} ms")
    print(f"  Avg RTT Latency:   {avg_lat:.2f} ms")
    print(f"  Median RTT Latency:{med_lat:.2f} ms")
    
    # Write to CSV
    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as csv_file:
                csv_file.write("client_id,rtt_ms\n")
                for t_id, res in results.items():
                    if "latencies" in res:
                        for lat in res["latencies"]:
                            csv_file.write(f"{t_id},{lat:.4f}\n")
            print(f"\n✓ Saved latency logs to: {args.output}")
        except Exception as e:
            print(f"Error saving logs: {e}")

if __name__ == "__main__":
    main()
