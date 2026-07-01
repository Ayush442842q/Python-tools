#!/usr/bin/env python3
"""
HTTP Capabilities & Protocol Auditor
Probes a target web server or URL to audit transport and protocol capabilities.
Detects:
- HTTP/2 support via native SSL Application-Layer Protocol Negotiation (ALPN)
- Supported compression algorithms (Gzip, Brotli, Deflate, Zstandard)
- Connection persistence (Keep-Alive)
- Security and transport optimization headers
- Server response latency differences
"""

import argparse
import socket
import ssl
import sys
import time
import urllib.request
import urllib.parse
from typing import Dict, List, Tuple, Optional

# Color constants
RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
MAGENTA = "\033[95m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

class HTTPCapabilitiesAuditor:
    def __init__(self, url: str, timeout: float = 5.0):
        self.url = url
        self.timeout = timeout
        parsed = urllib.parse.urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            # Try prepending http://
            self.url = "http://" + url
            parsed = urllib.parse.urlparse(self.url)
        
        self.scheme = parsed.scheme
        self.host = parsed.netloc.split(':')[0]
        # Resolve port
        if parsed.port:
            self.port = parsed.port
        else:
            self.port = 443 if self.scheme == "https" else 80
        
        self.path = parsed.path if parsed.path else "/"
        if parsed.query:
            self.path += f"?{parsed.query}"

    def audit_http2(self) -> Tuple[bool, str]:
        """Probes the host using SSL ALPN to determine if HTTP/2 is negotiated."""
        if self.scheme != "https":
            return False, "N/A (Requires HTTPS/TLS)"

        context = ssl.create_default_context()
        # Enable HTTP/2 and HTTP/1.1 protocols for negotiation
        context.set_alpn_protocols(['h2', 'http/1.1'])
        
        try:
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
                with context.wrap_socket(sock, server_hostname=self.host) as ssock:
                    negotiated = ssock.selected_alpn_protocol()
                    if negotiated == 'h2':
                        return True, "Supported (h2 negotiated)"
                    elif negotiated == 'http/1.1':
                        return False, "Not Supported (negotiated http/1.1)"
                    else:
                        return False, f"Not Supported (negotiated: {negotiated or 'None'})"
        except Exception as e:
            return False, f"Failed connection: {str(e)}"

    def test_compression(self) -> Dict[str, Tuple[bool, Optional[str]]]:
        """
        Sends requests testing for different compression schemes.
        Returns compression scheme -> (supported, returned content-encoding).
        """
        encodings = {
            "gzip": "gzip",
            "deflate": "deflate",
            "br (Brotli)": "br",
            "zstd (Zstandard)": "zstd"
        }
        results = {}

        for display, encoding_val in encodings.items():
            req = urllib.request.Request(
                self.url,
                headers={"Accept-Encoding": encoding_val, "User-Agent": "HTTPCapabilitiesAuditor/1.0"}
            )
            try:
                start_time = time.perf_counter()
                with urllib.request.urlopen(req, timeout=self.timeout) as response:
                    latency = (time.perf_counter() - start_time) * 1000
                    content_encoding = response.headers.get("Content-Encoding", "").strip().lower()
                    if content_encoding == encoding_val or encoding_val in content_encoding:
                        results[display] = (True, f"Supported ({content_encoding}, latency: {latency:.1f}ms)")
                    else:
                        results[display] = (False, f"Not Supported (Returned: '{content_encoding or 'identity'}')")
            except Exception as e:
                results[display] = (False, f"Request failed: {str(e)}")
        
        return results

    def audit_headers(self) -> Tuple[Dict[str, Tuple[bool, str]], Dict[str, str]]:
        """
        Audits response headers for security, optimization, and server configuration.
        """
        security_headers = {
            "Strict-Transport-Security": "Protects against MITM attacks (HSTS)",
            "Content-Security-Policy": "Mitigates XSS and injection risks",
            "X-Frame-Options": "Prevents clickjacking",
            "X-Content-Type-Options": "Prevents MIME-sniffing",
            "Referrer-Policy": "Controls referrer leakage",
            "Permissions-Policy": "Restricts device APIs/features"
        }
        
        caching_headers = ["Cache-Control", "Expires", "ETag", "Last-Modified"]
        
        header_results = {}
        server_info = {}

        req = urllib.request.Request(self.url, headers={"User-Agent": "HTTPCapabilitiesAuditor/1.0"})
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as response:
                headers = response.headers
                
                # Check server software
                server_info["Server"] = headers.get("Server", "Undisclosed")
                server_info["Powered-By"] = headers.get("X-Powered-By", "Undisclosed")
                server_info["Connection"] = headers.get("Connection", "Undisclosed")
                
                # Audit security headers
                for header, desc in security_headers.items():
                    val = headers.get(header)
                    if val:
                        header_results[header] = (True, f"Found: `{val}`")
                    else:
                        header_results[header] = (False, "Missing")

                # Audit caching
                caching_found = []
                for h in caching_headers:
                    if headers.get(h):
                        caching_found.append(h)
                server_info["Caching Capabilities"] = ", ".join(caching_found) if caching_found else "None detected"

        except Exception as e:
            for header in security_headers:
                header_results[header] = (False, f"Probe failed: {str(e)}")
            server_info["Error"] = str(e)
            
        return header_results, server_info

    def run_audit(self):
        print(f"{BOLD}{BLUE}=================================================={RESET}")
        print(f"{BOLD}{BLUE}         HTTP CAPABILITIES AUDIT REPORT           {RESET}")
        print(f"{BOLD}{BLUE}=================================================={RESET}")
        print(f"{BOLD}Target URL:{RESET} {self.url}")
        print(f"{BOLD}Resolved Host:{RESET} {self.host}:{self.port}\n")

        # 1. HTTP/2 Audit
        print(f"{BOLD}{CYAN}1. Protocol Capabilities{RESET}")
        print("-" * 50)
        h2_supported, h2_msg = self.audit_http2()
        h2_status = f"{GREEN}PASS{RESET}" if h2_supported else f"{YELLOW}INFO{RESET}"
        print(f"HTTP/2 Support: [{h2_status}] {h2_msg}")
        
        # 2. Compression Audit
        print(f"\n{BOLD}{CYAN}2. Content Compression Support{RESET}")
        print("-" * 50)
        compression_results = self.test_compression()
        score = 0
        for display, (supported, msg) in compression_results.items():
            status = f"{GREEN}YES{RESET}" if supported else f"{RED}NO{RESET}"
            if supported:
                score += 1
            print(f"{display:<18} : [{status}] {msg}")
        
        # 3. Security Headers Audit
        print(f"\n{BOLD}{CYAN}3. Security Header Audit{RESET}")
        print("-" * 50)
        header_results, server_info = self.audit_headers()
        sec_score = 0
        for header, (found, val) in header_results.items():
            status = f"{GREEN}OK  {RESET}" if found else f"{RED}MISS{RESET}"
            if found:
                sec_score += 1
            print(f"{header:<30} : [{status}] {val}")
            
        # 4. Server Details
        print(f"\n{BOLD}{CYAN}4. Server Info & Transport Details{RESET}")
        print("-" * 50)
        for k, v in server_info.items():
            print(f"{k:<25}: {v}")

        # Scorecard Calculation
        print(f"\n{BOLD}{BLUE}=================================================={RESET}")
        print(f"{BOLD}{BLUE}                 SCORECARD                        {RESET}")
        print(f"{BOLD}{BLUE}=================================================={RESET}")
        
        comp_grade = "Excellent" if score >= 3 else "Moderate" if score >= 1 else "Poor"
        sec_grade = "Excellent" if sec_score >= 5 else "Moderate" if sec_score >= 2 else "Poor"
        
        print(f"Compression Grade: {BOLD}{MAGENTA}{comp_grade}{RESET} ({score}/4 supported)")
        print(f"Security Headers:  {BOLD}{MAGENTA}{sec_grade}{RESET} ({sec_score}/6 present)")
        
        overall_rating = "A" if h2_supported and sec_score >= 4 and score >= 2 else "B" if h2_supported or sec_score >= 3 else "C"
        print(f"Overall Capability Rating: {BOLD}{GREEN if overall_rating in ['A', 'B'] else YELLOW}{overall_rating}{RESET}")
        print(f"{BOLD}{BLUE}=================================================={RESET}")

def main():
    parser = argparse.ArgumentParser(
        description="Audit HTTP protocols, compression algorithms, and security headers of a target URL."
    )
    parser.add_argument(
        "url",
        help="Target URL or hostname to audit (e.g. google.com or https://example.com)."
    )
    parser.add_argument(
        "-t", "--timeout",
        type=float,
        default=5.0,
        help="Timeout in seconds for network connections (default: 5.0)."
    )

    args = parser.parse_args()
    
    try:
        auditor = HTTPCapabilitiesAuditor(args.url, args.timeout)
        auditor.run_audit()
    except Exception as e:
        print(f"{RED}Error executing audit: {e}{RESET}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
