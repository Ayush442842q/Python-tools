#!/usr/bin/env python3
"""
Port Scanner & Service Detector
A zero-dependency, multi-threaded TCP port scanner that identifies open ports and
attempts protocol-specific banner grabbing and service detection (HTTP, SSH, FTP, SMTP, Redis).
"""

import argparse
import queue
import socket
import sys
import threading

# ANSI color codes
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
BOLD = "\033[1m"
RESET = "\033[0m"


class PortScanner:
    # Common ports and their default service names
    COMMON_PORTS = {
        21: "FTP", 22: "SSH", 23: "Telnet", 25: "SMTP", 53: "DNS",
        80: "HTTP", 110: "POP3", 115: "SFTP", 135: "RPC", 139: "NetBIOS",
        143: "IMAP", 443: "HTTPS", 445: "SMB", 993: "IMAPS", 995: "POP3S",
        1433: "MSSQL", 3306: "MySQL", 3389: "RDP", 5432: "PostgreSQL",
        5900: "VNC", 6379: "Redis", 8000: "HTTP-Alt", 8080: "HTTP-Proxy",
        8443: "HTTPS-Alt"
    }

    def __init__(self, host, ports, threads=50, timeout=1.0):
        self.host = host
        self.ports = ports
        self.threads = threads
        self.timeout = timeout
        self.results = []
        self.lock = threading.Lock()
        self.queue = queue.Queue()

    def resolve_host(self):
        """Resolves target hostname to IP address."""
        try:
            ip = socket.gethostbyname(self.host)
            return ip
        except socket.gaierror:
            return None

    def grab_banner(self, sock, port):
        """Attempts to grab banners and detect services running on open ports."""
        sock.settimeout(self.timeout * 2)  # Give banner grabbing slightly more time
        try:
            # 1. SSH / FTP / SMTP often send banners immediately upon connection
            if port in [21, 22, 23, 25, 110, 143]:
                banner = sock.recv(1024).decode("utf-8", errors="ignore").strip()
                if banner:
                    return banner
            
            # 2. HTTP Probes
            if port in [80, 443, 8000, 8080, 8443]:
                req = "GET / HTTP/1.0\r\n\r\n"
                if port == 443 or port == 8443:
                    # In a real environment, we'd need SSL wrapping.
                    # As a zero-dependency script, we send a basic HTTP request or wrap standard socket.
                    # We try to send raw HTTP first.
                    pass
                sock.sendall(req.encode())
                response = sock.recv(1024).decode("utf-8", errors="ignore")
                for line in response.split("\n"):
                    if line.lower().startswith("server:"):
                        return f"HTTP Web Server: {line.split(':', 1)[1].strip()}"
                if response:
                    # If server header not found, return status line
                    status_line = response.split("\r\n")[0]
                    return f"HTTP Service ({status_line})"

            # 3. Redis Probe
            if port == 6379:
                sock.sendall(b"PING\r\n")
                res = sock.recv(1024).decode("utf-8", errors="ignore").strip()
                if "PONG" in res or "+PONG" in res:
                    return "Redis Key-Value Database (Responded to PING)"
                
            # Generic grab - send an empty line/greeting and check response
            sock.sendall(b"\r\n")
            banner = sock.recv(512).decode("utf-8", errors="ignore").strip()
            if banner:
                # Clean up non-printable characters
                cleaned = "".join(ch for ch in banner if ch.isprintable() or ch in "\r\n\t")
                return cleaned[:100]
                
        except (socket.timeout, socket.error):
            pass
        
        # Default name if no banner grabbed
        return self.COMMON_PORTS.get(port, "Unknown Service")

    def scan_port(self, port):
        """Scans a single TCP port."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            result = sock.connect_ex((self.ip, port))
            
            if result == 0:
                service = self.grab_banner(sock, port)
                with self.lock:
                    self.results.append((port, "OPEN", service))
            sock.close()
        except socket.error:
            pass

    def worker(self):
        """Thread worker function to pull ports from queue."""
        while not self.queue.empty():
            try:
                port = self.queue.get_nowait()
                self.scan_port(port)
                self.queue.task_done()
            except queue.Empty:
                break

    def run_scan(self):
        """Initializes and runs the multi-threaded port scanner."""
        self.ip = self.resolve_host()
        if not self.ip:
            print(f"{RED}Error: Host resolution failed for '{self.host}'. Check address.{RESET}")
            return False

        print(f"\n{BOLD}Starting Port Scan on Host:{RESET} {self.host} ({self.ip})")
        print(f"Scanning {len(self.ports)} ports using {self.threads} worker threads...\n")

        # Load queue
        for port in self.ports:
            self.queue.put(port)

        threads_list = []
        for _ in range(min(self.threads, len(self.ports))):
            t = threading.Thread(target=self.worker)
            t.daemon = True
            t.start()
            threads_list.append(t)

        for t in threads_list:
            t.join()

        self.results.sort(key=lambda x: x[0])
        return True

    def display_results(self):
        """Prints results in a clean, aligned table."""
        if not self.results:
            print(f"{YELLOW}Scan complete. No open TCP ports detected.{RESET}\n")
            return

        print(f"{BOLD}{'PORT':<8} {'STATUS':<8} {'SERVICE / BANNER':<50}{RESET}")
        print("-" * 70)
        for port, status, service in self.results:
            # Highlight common open ports in green
            port_str = f"{port}/tcp"
            print(f"{GREEN}{port_str:<8}{RESET} {GREEN}{status:<8}{RESET} {CYAN}{service:<50}{RESET}")
        print("-" * 70)
        print(f"\n{BOLD}Total Open Ports:{RESET} {len(self.results)}\n")


def parse_port_range(port_arg):
    """Parses port argument options (ranges '1-1024' or lists '22,80,443')."""
    ports = []
    
    if "-" in port_arg:
        try:
            start, end = map(int, port_arg.split("-"))
            if 0 < start <= 65535 and 0 < end <= 65535 and start <= end:
                ports = list(range(start, end + 1))
            else:
                raise ValueError
        except ValueError:
            print(f"{RED}Error: Invalid port range format. Use e.g. 1-1024.{RESET}")
            sys.exit(1)
            
    elif "," in port_arg:
        try:
            ports = [int(p.strip()) for p in port_arg.split(",") if 0 < int(p.strip()) <= 65535]
        except ValueError:
            print(f"{RED}Error: Invalid comma-separated ports list. Use e.g. 22,80,443.{RESET}")
            sys.exit(1)
            
    else:
        try:
            port = int(port_arg)
            if 0 < port <= 65535:
                ports = [port]
            else:
                raise ValueError
        except ValueError:
            print(f"{RED}Error: Invalid port number. Must be 1-65535.{RESET}")
            sys.exit(1)
            
    return ports


def main():
    parser = argparse.ArgumentParser(description="Multi-threaded TCP Port Scanner & Service Detector")
    parser.add_argument("host", nargs="?", default="localhost", help="Target hostname or IP address (default: localhost)")
    parser.add_argument("-p", "--ports", default="common", help="Ports to scan: 'common' (top standard ports), a range '1-1024', or list '22,80,443'")
    parser.add_argument("-t", "--threads", type=int, default=50, help="Number of concurrent scanning threads (default: 50)")
    parser.add_argument("-timeout", "--timeout", type=float, default=1.0, help="Connection timeout in seconds (default: 1.0)")
    args = parser.parse_args()

    # Determine ports list
    if args.ports == "common":
        ports_list = sorted(list(PortScanner.COMMON_PORTS.keys()))
    else:
        ports_list = parse_port_range(args.ports)

    scanner = PortScanner(args.host, ports_list, threads=args.threads, timeout=args.timeout)
    if scanner.run_scan():
        scanner.display_results()


if __name__ == "__main__":
    main()
