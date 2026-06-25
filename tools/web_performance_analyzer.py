#!/usr/bin/env python3
"""
Web Performance Analyzer - Measure connection timing details and audit HTML assets.
"""

import os
import sys
import time
import socket
import ssl
import argparse
from urllib.parse import urlparse
from html.parser import HTMLParser

class AssetParser(HTMLParser):
    """HTML Parser to extract external assets from page HTML."""
    def __init__(self):
        super().__init__()
        self.scripts = []
        self.stylesheets = []
        self.images = []
        self.links = []

    def handle_starttag(self, tag, attrs):
        attr_dict = dict(attrs)
        if tag == 'script' and 'src' in attr_dict:
            self.scripts.append(attr_dict['src'])
        elif tag == 'link':
            rel = attr_dict.get('rel', '').lower()
            href = attr_dict.get('href', '')
            if 'stylesheet' in rel and href:
                self.stylesheets.append(href)
            elif href:
                self.links.append(href)
        elif tag == 'img' and 'src' in attr_dict:
            self.images.append(attr_dict['src'])
        elif tag == 'a' and 'href' in attr_dict:
            self.links.append(attr_dict['href'])

def get_color(color_name):
    """Return ANSI escape code for terminal color if supported."""
    colors = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'magenta': '\033[95m',
        'bold': '\033[1m',
        'reset': '\033[0m'
    }
    if sys.platform == 'win32':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            return ''
    return colors.get(color_name, '')

def analyze_web_performance(url, timeout=10, show_assets=False):
    c_red = get_color('red')
    c_green = get_color('green')
    c_yellow = get_color('yellow')
    c_blue = get_color('blue')
    c_magenta = get_color('magenta')
    c_bold = get_color('bold')
    c_reset = get_color('reset')

    parsed_url = urlparse(url)
    if not parsed_url.scheme or not parsed_url.netloc:
        print(f"{c_red}Error: Invalid URL format. Must include scheme (http or https) and host.{c_reset}")
        return False

    scheme = parsed_url.scheme.lower()
    host = parsed_url.netloc
    path = parsed_url.path if parsed_url.path else '/'
    if parsed_url.query:
        path += '?' + parsed_url.query

    # Separate host and port
    if ':' in host:
        host, port_str = host.split(':', 1)
        port = int(port_str)
    else:
        port = 443 if scheme == 'https' else 80

    print(f"{c_bold}Web Performance Analyzer for:{c_reset} {url}")
    print("=" * 60)

    # 1. DNS Resolution
    print("Performing DNS resolution...", end="", flush=True)
    t_dns_start = time.perf_counter()
    try:
        ip_addresses = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
        ip = ip_addresses[0][4][0]
        t_dns_end = time.perf_counter()
        dns_time = (t_dns_end - t_dns_start) * 1000
        print(f"\rDNS Resolution: {c_green}{dns_time:.2f} ms{c_reset} ({ip})")
    except Exception as e:
        print(f"\r{c_red}DNS Resolution Failed: {str(e)}{c_reset}")
        return False

    # 2. TCP Handshake
    print("Connecting via TCP...", end="", flush=True)
    t_tcp_start = time.perf_counter()
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((ip, port))
        t_tcp_end = time.perf_counter()
        tcp_time = (t_tcp_end - t_tcp_start) * 1000
        print(f"\rTCP Connection: {c_green}{tcp_time:.2f} ms{c_reset}")
    except Exception as e:
        print(f"\r{c_red}TCP Connection Failed: {str(e)}{c_reset}")
        return False

    # 3. SSL/TLS Handshake
    ssl_time = 0.0
    connected_sock = sock
    if scheme == 'https':
        print("Performing SSL/TLS Handshake...", end="", flush=True)
        t_ssl_start = time.perf_counter()
        try:
            context = ssl.create_default_context()
            connected_sock = context.wrap_socket(sock, server_hostname=host)
            t_ssl_end = time.perf_counter()
            ssl_time = (t_ssl_end - t_ssl_start) * 1000
            print(f"\rSSL/TLS Handshake: {c_green}{ssl_time:.2f} ms{c_reset} ({connected_sock.version()})")
        except Exception as e:
            print(f"\r{c_red}SSL/TLS Handshake Failed: {str(e)}{c_reset}")
            sock.close()
            return False

    # 4. HTTP Request sending and TTFB (Time to First Byte)
    print("Sending HTTP GET request...", end="", flush=True)
    request_str = f"GET {path} HTTP/1.1\r\nHost: {host}\r\nUser-Agent: WebPerformanceAnalyzer/1.0\r\nAccept: text/html\r\nConnection: close\r\n\r\n"
    
    t_send_start = time.perf_counter()
    try:
        connected_sock.sendall(request_str.encode('utf-8'))
        t_sent = time.perf_counter()
        
        # Read the first byte
        first_byte = connected_sock.recv(1)
        t_first_byte = time.perf_counter()
        ttfb = (t_first_byte - t_send_start) * 1000
        print(f"\rTime to First Byte (TTFB): {c_green}{ttfb:.2f} ms{c_reset}")
    except Exception as e:
        print(f"\r{c_red}HTTP Transfer Failed: {str(e)}{c_reset}")
        connected_sock.close()
        return False

    # 5. Content Download
    print("Downloading response payload...", end="", flush=True)
    t_download_start = time.perf_counter()
    response_data = first_byte
    try:
        while True:
            chunk = connected_sock.recv(4096)
            if not chunk:
                break
            response_data += chunk
        t_download_end = time.perf_counter()
        download_time = (t_download_end - t_download_start) * 1000
        total_time = (t_download_end - t_dns_start) * 1000
        print(f"\rContent Download: {c_green}{download_time:.2f} ms{c_reset}")
    except Exception as e:
        print(f"\r{c_red}Content Download Failed: {str(e)}{c_reset}")
        connected_sock.close()
        return False
    finally:
        connected_sock.close()

    print("-" * 60)
    print(f"{c_bold}Overall Connection Performance Summary:{c_reset}")
    print(f"  • DNS Lookup Time:    {dns_time:8.2f} ms")
    print(f"  • TCP Connection Time:{tcp_time:8.2f} ms")
    if scheme == 'https':
        print(f"  • SSL Handshake Time: {ssl_time:8.2f} ms")
    print(f"  • Time to First Byte: {ttfb:8.2f} ms")
    print(f"  • Content Download:   {download_time:8.2f} ms")
    print(f"  • {c_bold}Total Response Time: {total_time:8.2f} ms{c_reset}")
    print("-" * 60)

    # 6. Parse response headers and body
    try:
        header_part, body_part = response_data.split(b'\r\n\r\n', 1)
    except ValueError:
        header_part = response_data
        body_part = b''

    headers = header_part.decode('utf-8', errors='ignore').split('\r\n')
    status_line = headers[0]
    print(f"HTTP Status: {c_magenta}{status_line}{c_reset}")

    header_dict = {}
    for line in headers[1:]:
        if ':' in line:
            k, v = line.split(':', 1)
            header_dict[k.strip().lower()] = v.strip()

    content_type = header_dict.get('content-type', '')
    content_len = len(body_part)
    server_info = header_dict.get('server', 'Unknown')
    
    print(f"Server Software: {c_blue}{server_info}{c_reset}")
    print(f"Page Size:       {c_blue}{content_len / 1024:.2f} KB{c_reset}")
    print(f"Content Type:    {c_blue}{content_type}{c_reset}")
    print("-" * 60)

    # 7. HTML Asset Diagnostics
    if 'text/html' in content_type:
        print(f"{c_bold}Page Asset Audit:{c_reset}")
        html_content = body_part.decode('utf-8', errors='ignore')
        
        parser = AssetParser()
        try:
            parser.feed(html_content)
            
            print(f"  • External Scripts (<script src>):  {len(parser.scripts)}")
            print(f"  • Stylesheets (<link href CSS>):   {len(parser.stylesheets)}")
            print(f"  • Images (<img src>):              {len(parser.images)}")
            print(f"  • Hyperlinks (<a href>):            {len(parser.links)}")
            
            # Asset detail reporting
            if show_assets:
                if parser.scripts:
                    print(f"\n{c_yellow}Scripts ({len(parser.scripts)}):{c_reset}")
                    for s in parser.scripts[:15]:
                        print(f"  - {s}")
                    if len(parser.scripts) > 15:
                        print("  ... and more")
                if parser.stylesheets:
                    print(f"\n{c_yellow}Stylesheets ({len(parser.stylesheets)}):{c_reset}")
                    for s in parser.stylesheets[:15]:
                        print(f"  - {s}")
                    if len(parser.stylesheets) > 15:
                        print("  ... and more")
                if parser.images:
                    print(f"\n{c_yellow}Images ({len(parser.images)}):{c_reset}")
                    for img in parser.images[:15]:
                        print(f"  - {img}")
                    if len(parser.images) > 15:
                        print("  ... and more")
        except Exception as e:
            print(f"{c_yellow}Warning: Failed to parse HTML contents: {str(e)}{c_reset}")
    else:
        print("Page does not appear to be HTML, skipping asset parse.")

    return True

def main():
    parser = argparse.ArgumentParser(description="Web Performance Analyzer - Audits HTTP connection latency and parses HTML assets.")
    parser.add_argument("url", nargs="?", help="The HTTP/HTTPS URL to analyze")
    parser.add_argument("-u", "--url-check", help="URL to analyze (alternative syntax)")
    parser.add_argument("-t", "--timeout", type=float, default=10.0, help="Connection timeout in seconds (default: 10.0)")
    parser.add_argument("-a", "--assets", action="store_true", help="Print lists of discovered HTML assets (CSS, JS, images)")

    args = parser.parse_args()
    url = args.url_check or args.url

    if not url:
        print("Web Performance Analyzer")
        print("Usage: python web_performance_analyzer.py <URL> [options]")
        print("\nOptions:")
        print("  -a, --assets    Show the paths of scripts, CSS, and images found on the page")
        print("  -t, --timeout   Specify socket timeout in seconds")
        print("\nExample:")
        print("  python web_performance_analyzer.py https://example.com -a")
        return

    # Add default scheme if missing
    if not url.startswith('http://') and not url.startswith('https://'):
        url = 'https://' + url

    analyze_web_performance(url, timeout=args.timeout, show_assets=args.assets)

if __name__ == '__main__':
    main()
