#!/usr/bin/env python3
"""
Network Throughput Tester - Benchmark network bandwidth and packet loss between client and server

A pure Python command-line tool similar to iperf. It measures TCP throughput
(bandwidth) or UDP packet loss and jitter between a server and a client.

Usage:
    Server: python tools/network_throughput_tester.py --server [--port PORT] [--udp]
    Client: python tools/network_throughput_tester.py --client SERVER_IP [--port PORT] [--udp] [--time SECONDS]

Example:
    python tools/network_throughput_tester.py --server
    python tools/network_throughput_tester.py --client 192.168.1.50 --time 10
"""

import argparse
import socket
import sys
import time
import struct
from typing import Tuple

DEFAULT_PORT = 5001
TCP_BUFFER_SIZE = 65536
UDP_BUFFER_SIZE = 1400  # Avoid IP fragmentation on standard 1500 MTU networks

def format_speed(bytes_per_sec: float) -> str:
    """Formats bytes per second into human-readable speed units (bps, Kbps, Mbps, Gbps)."""
    bits_per_sec = bytes_per_sec * 8
    if bits_per_sec >= 1e9:
        return f"{bits_per_sec / 1e9:.2f} Gbits/sec"
    elif bits_per_sec >= 1e6:
        return f"{bits_per_sec / 1e6:.2f} Mbits/sec"
    elif bits_per_sec >= 1e3:
        return f"{bits_per_sec / 1e3:.2f} Kbits/sec"
    return f"{bits_per_sec:.2f} bits/sec"

def run_tcp_server(port: int):
    """Listens for TCP connections and measures incoming data throughput."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(('', port))
        s.listen(1)
        print(f"TCP server listening on port {port}...")
        
        while True:
            conn, addr = s.accept()
            print(f"Accepted connection from {addr[0]}:{addr[1]}")
            
            total_bytes = 0
            start_time = time.time()
            last_report_time = start_time
            last_report_bytes = 0
            
            try:
                while True:
                    data = conn.recv(TCP_BUFFER_SIZE)
                    if not data:
                        break
                    total_bytes += len(data)
                    
                    now = time.time()
                    elapsed = now - last_report_time
                    if elapsed >= 1.0:
                        interval_bytes = total_bytes - last_report_bytes
                        speed = interval_bytes / elapsed
                        print(f"Interval: {now - start_time - elapsed:.1f}-{now - start_time:.1f} sec | Speed: {format_speed(speed)}")
                        last_report_time = now
                        last_report_bytes = total_bytes
            except socket.error as e:
                print(f"Socket error: {e}")
            finally:
                conn.close()
                end_time = time.time()
                duration = end_time - start_time
                if duration > 0:
                    avg_speed = total_bytes / duration
                    print(f"Connection closed. Received {total_bytes / (1024*1024):.2f} MBytes.")
                    print(f"Average Speed: {format_speed(avg_speed)} over {duration:.2f} seconds.")
                    print("-" * 50)
    except KeyboardInterrupt:
        print("\nStopping TCP server.")
    finally:
        s.close()

def run_tcp_client(host: str, port: int, duration: int):
    """Connects to a TCP server and sends continuous dummy data to measure throughput."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        print(f"Connecting to TCP server {host}:{port}...")
        s.connect((host, port))
        print("Connected. Starting benchmark...")
        
        dummy_data = b'x' * TCP_BUFFER_SIZE
        total_bytes = 0
        start_time = time.time()
        last_report_time = start_time
        last_report_bytes = 0
        
        while time.time() - start_time < duration:
            sent = s.send(dummy_data)
            total_bytes += sent
            
            now = time.time()
            elapsed = now - last_report_time
            if elapsed >= 1.0:
                interval_bytes = total_bytes - last_report_bytes
                speed = interval_bytes / elapsed
                print(f"Interval: {now - start_time - elapsed:.1f}-{now - start_time:.1f} sec | Speed: {format_speed(speed)}")
                last_report_time = now
                last_report_bytes = total_bytes
                
        end_time = time.time()
        final_duration = end_time - start_time
        avg_speed = total_bytes / final_duration
        print(f"Benchmark finished. Sent {total_bytes / (1024*1024):.2f} MBytes.")
        print(f"Average Transmit Speed: {format_speed(avg_speed)} over {final_duration:.2f} seconds.")
        
    except socket.error as e:
        print(f"Socket error: {e}")
    finally:
        s.close()

def run_udp_server(port: int):
    """Listens for UDP packets and measures bandwidth, packet loss, and jitter."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.bind(('', port))
        print(f"UDP server listening on port {port}...")
        
        # We listen for a starting packet that tells us a client is benchmarking
        while True:
            print("Waiting for sender...")
            data, addr = s.recvfrom(UDP_BUFFER_SIZE)
            
            total_bytes = len(data)
            start_time = time.time()
            last_report_time = start_time
            last_report_bytes = total_bytes
            
            expected_seq = 0
            lost_packets = 0
            received_packets = 1
            jitter_sum = 0.0
            last_transit_time = None
            
            s.settimeout(2.0)  # Stop benchmark if no packet received for 2 seconds
            
            try:
                # Unpack header: sequence number (4 bytes), timestamp (8 bytes double)
                if len(data) >= 12:
                    seq, ts = struct.unpack("!Id", data[:12])
                    expected_seq = seq + 1
                    transit = start_time - ts
                    last_transit_time = transit

                while True:
                    try:
                        data, _ = s.recvfrom(UDP_BUFFER_SIZE)
                        received_time = time.time()
                        total_bytes += len(data)
                        received_packets += 1
                        
                        # Parse header
                        if len(data) >= 12:
                            seq, ts = struct.unpack("!Id", data[:12])
                            
                            # Jitter computation (RFC 1889 / RFC 3550 style)
                            transit = received_time - ts
                            if last_transit_time is not None:
                                d = abs(transit - last_transit_time)
                                jitter_sum += d
                            last_transit_time = transit
                            
                            # Packet loss tracking
                            if seq > expected_seq:
                                lost_packets += (seq - expected_seq)
                                expected_seq = seq + 1
                            elif seq < expected_seq:
                                # Out of order packets
                                pass
                            else:
                                expected_seq += 1
                                
                        now = time.time()
                        elapsed = now - last_report_time
                        if elapsed >= 1.0:
                            interval_bytes = total_bytes - last_report_bytes
                            speed = interval_bytes / elapsed
                            print(f"Interval: {now - start_time - elapsed:.1f}-{now - start_time:.1f} sec | Speed: {format_speed(speed)}")
                            last_report_time = now
                            last_report_bytes = total_bytes
                            
                    except socket.timeout:
                        print("Benchmark idle timeout (no packets received).")
                        break
            except Exception as e:
                print(f"Error during run: {e}")
            finally:
                s.settimeout(None)
                end_time = time.time() - 2.0  # Subtract the timeout delay
                duration = end_time - start_time
                if duration <= 0:
                    duration = 0.01
                avg_speed = (total_bytes - last_report_bytes) / duration if duration > 0 else 0
                
                total_expected = received_packets + lost_packets
                loss_pct = (lost_packets / total_expected * 100) if total_expected > 0 else 0
                avg_jitter = (jitter_sum / received_packets * 1000) if received_packets > 1 else 0
                
                print(f"Benchmark from {addr[0]}:{addr[1]} finished.")
                print(f"Received {total_bytes / (1024*1024):.2f} MBytes | {received_packets} packets.")
                print(f"Packet Loss: {lost_packets}/{total_expected} ({loss_pct:.2f}%)")
                print(f"Average Jitter: {avg_jitter:.3f} ms")
                print(f"Average Speed: {format_speed(avg_speed)}")
                print("-" * 50)
    except KeyboardInterrupt:
        print("\nStopping UDP server.")
    finally:
        s.close()

def run_udp_client(host: str, port: int, duration: int):
    """Sends UDP packets with sequence numbers and timestamps to a server to measure bandwidth and loss."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_addr = (host, port)
    
    print(f"Sending UDP stream to {host}:{port}...")
    start_time = time.time()
    last_report_time = start_time
    total_bytes = 0
    last_report_bytes = 0
    seq = 0
    
    # We send packet at a throttled rate to avoid immediate buffer overflows locally
    # If the user wants max throughput, we sleep minimally, but standard UDP sends need pacing.
    target_pps = 5000  # Packets per second limit to prevent overwhelming local buffer
    packet_interval = 1.0 / target_pps
    
    try:
        while time.time() - start_time < duration:
            send_time = time.time()
            # Struct format: sequence number (uint32), timestamp (double), rest is padding
            header = struct.pack("!Id", seq, send_time)
            padding = b'y' * (UDP_BUFFER_SIZE - len(header))
            packet = header + padding
            
            s.sendto(packet, server_addr)
            total_bytes += len(packet)
            seq += 1
            
            # Pacing
            time_spent = time.time() - send_time
            if time_spent < packet_interval:
                time.sleep(packet_interval - time_spent)
                
            now = time.time()
            elapsed = now - last_report_time
            if elapsed >= 1.0:
                interval_bytes = total_bytes - last_report_bytes
                speed = interval_bytes / elapsed
                print(f"Interval: {now - start_time - elapsed:.1f}-{now - start_time:.1f} sec | Speed: {format_speed(speed)}")
                last_report_time = now
                last_report_bytes = total_bytes
                
        end_time = time.time()
        final_duration = end_time - start_time
        avg_speed = total_bytes / final_duration
        print(f"Benchmark finished. Sent {seq} packets ({total_bytes / (1024*1024):.2f} MBytes).")
        print(f"Average Transmit Speed: {format_speed(avg_speed)}")
        print("Check server console for detailed packet loss and jitter statistics.")
        
    except socket.error as e:
        print(f"Socket error: {e}")
    finally:
        s.close()

def main():
    parser = argparse.ArgumentParser(
        description="Benchmark network bandwidth, packet loss, and jitter using TCP or UDP sockets."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--server', '-s', action='store_true', help='Run in server mode')
    group.add_argument('--client', '-c', metavar='HOST', help='Run in client mode, connecting to HOST')
    
    parser.add_argument('--port', '-p', type=int, default=DEFAULT_PORT, help=f'Port to listen/connect on (default: {DEFAULT_PORT})')
    parser.add_argument('--udp', '-u', action='store_true', help='Use UDP instead of TCP')
    parser.add_argument('--time', '-t', type=int, default=10, help='Client transmit duration in seconds (default: 10)')
    
    args = parser.parse_args()
    
    if args.server:
        if args.udp:
            run_udp_server(args.port)
        else:
            run_tcp_server(args.port)
    else:
        if args.time <= 0:
            print("Error: Benchmarking time must be a positive integer.", file=sys.stderr)
            return 1
            
        if args.udp:
            run_udp_client(args.client, args.port, args.time)
        else:
            run_tcp_client(args.client, args.port, args.time)
            
    return 0

if __name__ == "__main__":
    sys.exit(main())
