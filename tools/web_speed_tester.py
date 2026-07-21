#!/usr/bin/env python3
"""
Web Speed Tester & HTTP Waterfall Analyzer

Measures the exact latency of different phases of an HTTP/HTTPS request:
1. DNS Resolution
2. TCP Connection Handshake
3. SSL/TLS Handshake
4. Time to First Byte (TTFB)
5. Content Download Speed
Generates a visual waterfall timeline chart directly in the terminal.
"""

import argparse
import os
import socket
import ssl
import sys
import time
from urllib.parse import urlparse

# Configure stdout/stderr encoding to UTF-8 to prevent charmap errors on Windows console redirection
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        try:
            stream.reconfigure(encoding='utf-8')
        except Exception:
            pass

# ANSI Styling
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"

def supports_color() -> bool:
    plat = sys.platform
    supported_platform = plat != 'Pocket PC' and (plat != 'win32' or 'ANSICON' in os.environ)
    is_a_tty = hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()
    return supported_platform or is_a_tty

def color_text(text: str, color_code: str) -> str:
    return f"{color_code}{text}{COLOR_RESET}" if supports_color() else text

def format_duration(seconds: float) -> str:
    if seconds < 0.001:
        return f"{seconds * 1000000:.1f} μs"
    elif seconds < 1.0:
        return f"{seconds * 1000:.1f} ms"
    else:
        return f"{seconds:.2f} s"

def build_bar(start_pct: float, end_pct: float, total_width: int = 40, color: str = COLOR_GREEN) -> str:
    start_idx = int(round(start_pct * total_width))
    end_idx = int(round(end_pct * total_width))
    
    # Bound-check
    start_idx = max(0, min(total_width, start_idx))
    end_idx = max(start_idx, min(total_width, end_idx))
    
    duration_width = end_idx - start_idx
    if duration_width == 0 and end_pct > start_pct:
        duration_width = 1  # ensure at least one mark if there's duration
        
    bar_str = " " * start_idx + "█" * duration_width + " " * (total_width - start_idx - duration_width)
    return color_text(f"[{bar_str[:total_width]}]", color)

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Web Speed Tester - Analyze HTTP/HTTPS phase-by-phase connection timings.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("url", help="Target URL to test (e.g. https://www.google.com/)")
    parser.add_argument("-t", "--timeout", type=float, default=10.0, help="Connection timeout in seconds")
    parser.add_argument("-u", "--user-agent", default="WebSpeedTester/1.0", help="Custom User-Agent header")
    
    args = parser.parse_args()
    
    url = args.url
    if not url.startswith(("http://", "https://")):
        url = "https://" + url  # Default to HTTPS
        
    parsed = urlparse(url)
    host = parsed.hostname
    port = parsed.port
    scheme = parsed.scheme
    path = parsed.path if parsed.path else "/"
    if parsed.query:
        path += "?" + parsed.query
        
    if not host:
        print(color_text("[-] Error: Invalid URL structure. Could not find hostname.", COLOR_RED), file=sys.stderr)
        return 1
        
    if not port:
        port = 443 if scheme == "https" else 80
        
    print(color_text(f"\n[*] Starting speed test for: {url}", COLOR_CYAN))
    print(f"[*] Target IP Host: {host}:{port} ({scheme.upper()})\n")
    
    # Time milestones
    t_start = time.perf_counter()
    
    try:
        # 1. DNS Resolution
        t0 = time.perf_counter()
        addr_info = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
        t_dns_end = time.perf_counter()
        dns_time = t_dns_end - t0
        
        # Extract connection parameters dynamically to support IPv4 & IPv6
        family, socktype, proto, _, sockaddr = addr_info[0]
        target_ip = sockaddr[0]
        print(f"  [+] Resolved {host} to {target_ip} in {format_duration(dns_time)}")
        
        # 2. TCP Handshake
        t1 = time.perf_counter()
        sock = socket.socket(family, socktype, proto)
        sock.settimeout(args.timeout)
        sock.connect(sockaddr)
        t_tcp_end = time.perf_counter()
        tcp_time = t_tcp_end - t1
        print(f"  [+] TCP Connection established in {format_duration(tcp_time)}")
        
        # 3. SSL/TLS Handshake
        ssl_time = 0.0
        active_sock = sock
        if scheme == "https":
            t2 = time.perf_counter()
            ssl_context = ssl.create_default_context()
            active_sock = ssl_context.wrap_socket(sock, server_hostname=host)
            t_ssl_end = time.perf_counter()
            ssl_time = t_ssl_end - t2
            print(f"  [+] SSL/TLS Handshake completed in {format_duration(ssl_time)}")
            
        # 4. Request send & TTFB
        t3 = time.perf_counter()
        request_headers = (
            f"GET {path} HTTP/1.1\r\n"
            f"Host: {host}\r\n"
            f"User-Agent: {args.user_agent}\r\n"
            f"Accept: */*\r\n"
            f"Connection: close\r\n\r\n"
        )
        active_sock.sendall(request_headers.encode("utf-8"))
        
        # Wait for the first byte of response
        first_byte = active_sock.recv(1)
        t_ttfb_end = time.perf_counter()
        ttfb_time = t_ttfb_end - t3
        print(f"  [+] Time to First Byte (TTFB): {format_duration(ttfb_time)}")
        
        # 5. Content download
        t4 = time.perf_counter()
        response_data = first_byte
        while True:
            chunk = active_sock.recv(8192)
            if not chunk:
                break
            response_data += chunk
        t_download_end = time.perf_counter()
        download_time = t_download_end - t4
        total_time = t_download_end - t_start
        
        active_sock.close()
        
        download_size = len(response_data)
        print(f"  [+] Downloaded {download_size} bytes in {format_duration(download_time)}")
        print(color_text(f"  [+] Total request cycle finished in {format_duration(total_time)}", COLOR_GREEN + COLOR_BOLD))
        
        # Timeline offsets (relative to start)
        dns_start_pct = 0.0
        dns_end_pct = dns_time / total_time
        
        tcp_start_pct = dns_end_pct
        tcp_end_pct = (dns_time + tcp_time) / total_time
        
        ssl_start_pct = tcp_end_pct
        ssl_end_pct = (dns_time + tcp_time + ssl_time) / total_time
        
        ttfb_start_pct = ssl_end_pct
        ttfb_end_pct = (dns_time + tcp_time + ssl_time + ttfb_time) / total_time
        
        download_start_pct = ttfb_end_pct
        download_end_pct = 1.0
        
        # Render visual waterfall chart
        print(color_text("\n--- Request Waterfall Chart ---", COLOR_CYAN + COLOR_BOLD))
        
        bar_width = 40
        print(f"  DNS Lookup  : {build_bar(dns_start_pct, dns_end_pct, bar_width, COLOR_YELLOW)} {format_duration(dns_time):>10}")
        print(f"  TCP Connect : {build_bar(tcp_start_pct, tcp_end_pct, bar_width, COLOR_CYAN)} {format_duration(tcp_time):>10}")
        if scheme == "https":
            print(f"  TLS Handopt : {build_bar(ssl_start_pct, ssl_end_pct, bar_width, COLOR_RED)} {format_duration(ssl_time):>10}")
        print(f"  TTFB        : {build_bar(ttfb_start_pct, ttfb_end_pct, bar_width, COLOR_GREEN)} {format_duration(ttfb_time):>10}")
        print(f"  Download    : {build_bar(download_start_pct, download_end_pct, bar_width, COLOR_BOLD)} {format_duration(download_time):>10}")
        print(color_text("  " + "-" * 57, COLOR_CYAN))
        print(f"  Total Time  : {' ' * bar_width} {format_duration(total_time):>10}")
        
        # Speed calc
        if download_time > 0:
            speed_kb = (download_size / 1024) / download_time
            print(f"  Avg Speed   : {speed_kb:.2f} KB/s")
            
    except socket.gaierror:
        print(color_text(f"[-] DNS Error: Could not resolve hostname '{host}'. Please verify the URL.", COLOR_RED), file=sys.stderr)
        return 2
    except socket.timeout:
        print(color_text(f"[-] Connection Error: Request timed out after {args.timeout} seconds.", COLOR_RED), file=sys.stderr)
        return 3
    except Exception as e:
        print(color_text(f"[-] Error: {e}", COLOR_RED), file=sys.stderr)
        return 4
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
