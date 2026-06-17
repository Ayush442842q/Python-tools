#!/usr/bin/env python3
"""
DNS Benchmarker
Benchmarks response times of multiple DNS resolvers for a set of test domains.
Uses raw UDP DNS queries implemented with Python standard libraries (no external dependencies).
"""

import argparse
import random
import socket
import struct
import sys
import time

# Default public DNS resolvers to benchmark
DEFAULT_RESOLVERS = {
    "Cloudflare (1.1.1.1)": "1.1.1.1",
    "Google (8.8.8.8)": "8.8.8.8",
    "Quad9 (9.9.9.9)": "9.9.9.9",
    "OpenDNS (208.67.222.222)": "208.67.222.222",
    "AdGuard (94.140.14.14)": "94.140.14.14",
    "Control D (76.76.2.0)": "76.76.2.0",
}

# Default domains to query
DEFAULT_DOMAINS = [
    "google.com",
    "github.com",
    "wikipedia.org",
    "amazon.com",
    "microsoft.com",
    "apple.com"
]

def query_dns_server(server_ip, domain, timeout=2.0):
    """
    Performs a raw DNS query for an A record of the domain to the specified server_ip.
    Returns (latency_ms, status_message) or (None, error_message).
    """
    transaction_id = random.randint(0, 65535)
    # Header: ID, Flags (0x0100 Standard Query), QDCOUNT=1, ANCOUNT=0, NSCOUNT=0, ARCOUNT=0
    header = struct.pack('!HHHHHH', transaction_id, 0x0100, 1, 0, 0, 0)
    
    # QNAME encoding (e.g. www.google.com -> 3www6google3com0)
    parts = domain.split('.')
    qname = b''
    for part in parts:
        if part:
            encoded_part = part.encode('utf-8')
            qname += bytes([len(encoded_part)]) + encoded_part
    qname += b'\x00'
    
    # QTYPE=1 (A record), QCLASS=1 (IN class)
    question = qname + struct.pack('!HH', 1, 1)
    packet = header + question
    
    start_time = time.perf_counter()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(timeout)
        sock.sendto(packet, (server_ip, 53))
        data, addr = sock.recvfrom(512)
        latency = (time.perf_counter() - start_time) * 1000 # convert to ms
        
        # Parse basic response headers to verify transaction ID and RCODE
        if len(data) >= 12:
            resp_id = struct.unpack('!H', data[:2])[0]
            if resp_id == transaction_id:
                flags = struct.unpack('!H', data[2:4])[0]
                rcode = flags & 0x000F
                if rcode == 0:
                    return latency, "OK"
                elif rcode == 3:
                    return latency, "NXDOMAIN"
                else:
                    return latency, f"RCODE_{rcode}"
            else:
                return None, "Mismatch ID"
        return None, "Truncated"
    except socket.timeout:
        return None, "Timeout"
    except Exception as e:
        return None, f"Error: {e}"
    finally:
        sock.close()

def main():
    parser = argparse.ArgumentParser(
        description="Benchmark DNS query speeds of public DNS resolvers using raw UDP queries."
    )
    parser.add_argument('-d', '--domains', nargs='+', default=DEFAULT_DOMAINS,
                        help='Domains to query for testing (default: standard set of 6 popular sites)')
    parser.add_argument('-r', '--resolvers', nargs='+',
                        help='Specific DNS resolver IPs to test (format: IP or Name=IP). Example: 1.1.1.1 8.8.8.8')
    parser.add_argument('-c', '--count', type=int, default=3,
                        help='Number of queries to perform per domain per resolver (default: 3)')
    parser.add_argument('-t', '--timeout', type=float, default=2.0,
                        help='Timeout in seconds for each query (default: 2.0)')
    
    args = parser.parse_args()

    # Parse resolvers
    resolvers_to_test = {}
    if args.resolvers:
        for res in args.resolvers:
            if '=' in res:
                name, ip = res.split('=', 1)
                resolvers_to_test[name.strip()] = ip.strip()
            else:
                resolvers_to_test[res] = res
    else:
        resolvers_to_test = DEFAULT_RESOLVERS

    print(f"Starting DNS Benchmark with {len(resolvers_to_test)} resolvers...")
    print(f"Testing against {len(args.domains)} domains ({args.count} queries per domain, timeout {args.timeout}s).")
    print("-" * 85)

    results = {}
    for name, ip in resolvers_to_test.items():
        print(f"Benchmarking {name} ({ip})... ", end='', flush=True)
        latencies = []
        successes = 0
        total_queries = 0

        for domain in args.domains:
            for _ in range(args.count):
                total_queries += 1
                lat, status = query_dns_server(ip, domain, args.timeout)
                if lat is not None:
                    latencies.append(lat)
                    successes += 1
                # Small pause to avoid flooding resolvers
                time.sleep(0.02)
        
        if latencies:
            avg_lat = sum(latencies) / len(latencies)
            min_lat = min(latencies)
            max_lat = max(latencies)
            success_rate = (successes / total_queries) * 100
        else:
            avg_lat = float('inf')
            min_lat = float('inf')
            max_lat = float('inf')
            success_rate = 0.0

        results[name] = {
            "ip": ip,
            "avg": avg_lat,
            "min": min_lat,
            "max": max_lat,
            "success_rate": success_rate,
            "total": total_queries,
            "successes": successes
        }
        print("Done")

    # Sort results by average latency
    sorted_results = sorted(results.items(), key=lambda x: x[1]['avg'])

    # Print results table
    print("\nBenchmark Results (sorted by average speed):")
    print("=" * 85)
    print(f"{'Resolver Name':<28} | {'IP Address':<15} | {'Avg (ms)':<9} | {'Min (ms)':<9} | {'Max (ms)':<9} | {'Success':<8}")
    print("-" * 85)

    for idx, (name, metrics) in enumerate(sorted_results):
        avg_str = f"{metrics['avg']:.2f}" if metrics['avg'] != float('inf') else "N/A"
        min_str = f"{metrics['min']:.2f}" if metrics['min'] != float('inf') else "N/A"
        max_str = f"{metrics['max']:.2f}" if metrics['max'] != float('inf') else "N/A"
        success_str = f"{metrics['success_rate']:.1f}%"
        
        # Highlight the fastest resolver
        prefix = "-> " if idx == 0 and metrics['avg'] != float('inf') else "   "
        
        print(f"{prefix}{name:<25} | {metrics['ip']:<15} | {avg_str:>9} | {min_str:>9} | {max_str:>9} | {success_str:>8}")
    print("=" * 85)

    if sorted_results and sorted_results[0][1]['avg'] != float('inf'):
        print(f"Fastest DNS Resolver: {sorted_results[0][0]} ({sorted_results[0][1]['ip']}) with average latency of {sorted_results[0][1]['avg']:.2f} ms.")
    else:
        print("All queries failed.")

    return 0

if __name__ == '__main__':
    sys.exit(main())
