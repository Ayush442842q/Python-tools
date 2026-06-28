#!/usr/bin/env python3
"""
SSL Certificate Chain Analyzer
Audit and visualize SSL/TLS certificate chains, validation status, and key properties.

Usage:
    python tools/ssl_chain_analyzer.py google.com
    python tools/ssl_chain_analyzer.py github.com --port 443
"""

import argparse
import datetime
import re
import socket
import ssl
import subprocess
import sys
from typing import Dict, List, Optional, Tuple


# ANSI Escape Codes for colorized output
COLOR_HEADER = "\033[95m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"
COLOR_GREEN = "\033[92m"
COLOR_WARNING = "\033[93m"
COLOR_FAIL = "\033[91m"
COLOR_END = "\033[0m"
COLOR_BOLD = "\033[1m"


def print_colored(text: str, color: str):
    """Print text with ANSI color codes if output is a TTY."""
    if sys.stdout.isatty():
        print(f"{color}{text}{COLOR_END}")
    else:
        print(text)


class SSLChainAnalyzer:
    def __init__(self, host: str, port: int = 443, timeout: float = 5.0):
        self.host = host
        self.port = port
        self.timeout = timeout

    def get_leaf_cert_built_in(self) -> Optional[Dict]:
        """Fetch the leaf certificate dictionary using Python's built-in ssl module."""
        try:
            context = ssl.create_default_context()
            # Disable hostname check and cert verification if we just want to inspect whatever is sent
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            
            with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
                with context.wrap_socket(sock, server_hostname=self.host) as ssock:
                    cert = ssock.getpeercert()
                    # If verify_mode is CERT_NONE, getpeercert() is empty, so we get binary DER and parse it.
                    # Instead, let's connect normally first.
                    try:
                        normal_context = ssl.create_default_context()
                        with socket.create_connection((self.host, self.port), timeout=self.timeout) as n_sock:
                            with normal_context.wrap_socket(n_sock, server_hostname=self.host) as n_ssock:
                                return n_ssock.getpeercert()
                    except Exception:
                        # Fallback to unverified binary retrieval (parsed format not easily available without cryptography)
                        pass
                    
                    # Try to retrieve verified peer cert again
                    context_verify = ssl.create_default_context()
                    with socket.create_connection((self.host, self.port), timeout=self.timeout) as v_sock:
                        with context_verify.wrap_socket(v_sock, server_hostname=self.host) as v_ssock:
                            return v_ssock.getpeercert()
        except Exception as e:
            print_colored(f"[!] Warning: Failed to retrieve leaf cert via Python ssl module: {e}", COLOR_WARNING)
        return None

    def get_chain_via_openssl_cli(self) -> List[str]:
        """Use OpenSSL CLI tool if available to fetch the raw certificate chain."""
        try:
            # Run openssl s_client to get certificates
            cmd = ["openssl", "s_client", "-connect", f"{self.host}:{self.port}", "-showcerts", "-servername", self.host]
            # Use input=EOF to terminate the interactive prompt immediately
            process = subprocess.run(
                cmd,
                input="",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=self.timeout,
                check=False
            )
            
            if process.returncode != 0 and "openssl" not in process.stderr.lower():
                return []
                
            # Extract certificates in PEM format
            pem_blocks = re.findall(
                r"(-----BEGIN CERTIFICATE-----\n.*?-----END CERTIFICATE-----)",
                process.stdout,
                re.DOTALL
            )
            return pem_blocks
        except (subprocess.SubprocessError, FileNotFoundError):
            # openssl command not found or failed
            return []

    def parse_cert_via_openssl(self, pem_content: str) -> Dict:
        """Parse certificate attributes using OpenSSL CLI utility."""
        details = {}
        try:
            # Query multiple attributes
            queries = {
                "subject": ["-subject", "-noout"],
                "issuer": ["-issuer", "-noout"],
                "dates": ["-dates", "-noout"],
                "san": ["-ext", "subjectAltName"],
                "algo": ["-checkend", "0"],  # Just a placeholder to check validity
            }
            
            # Helper to run openssl x509
            def run_x509(args: List[str]) -> str:
                proc = subprocess.run(
                    ["openssl", "x509"] + args,
                    input=pem_content,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=False
                )
                return proc.stdout.strip()

            subject_raw = run_x509(["-subject", "-noout"])
            issuer_raw = run_x509(["-issuer", "-noout"])
            dates_raw = run_x509(["-dates", "-noout"])
            
            # Extract CN from Subject
            cn_match = re.search(r"CN\s*=\s*([^,\n/]+)", subject_raw)
            details["common_name"] = cn_match.group(1).strip() if cn_match else "Unknown CN"
            details["subject"] = subject_raw.replace("subject=", "").strip()
            details["issuer"] = issuer_raw.replace("issuer=", "").strip()
            
            # Dates
            not_before = re.search(r"notBefore=(.*)", dates_raw)
            not_after = re.search(r"notAfter=(.*)", dates_raw)
            details["not_before"] = not_before.group(1).strip() if not_before else ""
            details["not_after"] = not_after.group(1).strip() if not_after else ""
            
            # Expiration assessment
            if details["not_after"]:
                try:
                    # OpenSSL date format e.g. "Jun 28 09:30:36 2026 GMT"
                    # Remove GMT/UTC to make it timezone naive
                    date_str = re.sub(r"\s+[A-Z]{3,4}$", "", details["not_after"]).strip()
                    expiry_dt = datetime.datetime.strptime(date_str, "%b %d %H:%M:%S %Y")
                    details["expiry_datetime"] = expiry_dt
                except ValueError:
                    pass

            # Signature algorithm & key details
            text_out = run_x509(["-text", "-noout"])
            sig_match = re.search(r"Signature Algorithm:\s*([a-zA-Z0-9-with]+)", text_out, re.IGNORECASE)
            details["sig_algo"] = sig_match.group(1).strip() if sig_match else "Unknown"

            key_match = re.search(r"Public-Key:\s*\((\d+)\s+bit\)", text_out)
            details["key_size"] = int(key_match.group(1)) if key_match else None
            
            key_type_match = re.search(r"Public Key Algorithm:\s*([a-zA-Z0-9-]+)", text_out, re.IGNORECASE)
            details["key_type"] = key_type_match.group(1).strip() if key_type_match else "RSA"

            # SANs
            san_lines = run_x509(["-ext", "subjectAltName"])
            sans = []
            for line in san_lines.split("\n"):
                matches = re.findall(r"(?:DNS|IP Address):([a-zA-Z0-9.*-]+)", line)
                sans.extend(matches)
            details["sans"] = sans

            # Check if it's a CA
            ca_match = re.search(r"CA:TRUE", text_out, re.IGNORECASE)
            details["is_ca"] = bool(ca_match)
            
        except Exception as e:
            details["error"] = str(e)
            
        return details

    def parse_built_in_cert(self, cert_dict: Dict) -> Dict:
        """Parse standard Python cert dictionary output into common details format."""
        details = {}
        try:
            # Extract Common Name
            subject = cert_dict.get("subject", ())
            cn = "Unknown CN"
            for rdn in subject:
                for key, val in rdn:
                    if key == "commonName":
                        cn = val
                        break
            details["common_name"] = cn
            details["subject"] = str(subject)
            
            issuer = cert_dict.get("issuer", ())
            details["issuer"] = str(issuer)
            
            # Dates
            details["not_before"] = cert_dict.get("notBefore", "")
            details["not_after"] = cert_dict.get("notAfter", "")
            
            if details["not_after"]:
                try:
                    # e.g., "Jun 28 09:30:36 2026 GMT"
                    date_str = re.sub(r"\s+[A-Z]{3,4}$", "", details["not_after"]).strip()
                    expiry_dt = datetime.datetime.strptime(date_str, "%b %d %H:%M:%S %Y")
                    details["expiry_datetime"] = expiry_dt
                except ValueError:
                    pass
            
            details["sans"] = [alt[1] for alt in cert_dict.get("subjectAltName", ()) if alt[0] == "DNS"]
            details["sig_algo"] = "Unknown (Python standard SSL does not expose Signature Algorithm)"
            details["key_type"] = "RSA/EC (unspecified)"
            details["key_size"] = None
            details["is_ca"] = False
        except Exception as e:
            details["error"] = str(e)
        return details

    def run_audit(self):
        """Execute SSL chain audit and print the findings."""
        print_colored(f"[*] Auditing SSL/TLS Certificate Chain for {self.host}:{self.port}...", COLOR_CYAN)
        
        # 1. Fetch chain using OpenSSL (preferred for full hierarchy details)
        pems = self.get_chain_via_openssl_cli()
        parsed_chain = []
        
        if pems:
            print_colored("[+] Retrieved full certificate chain via OpenSSL CLI.", COLOR_GREEN)
            for idx, pem in enumerate(pems):
                info = self.parse_cert_via_openssl(pem)
                info["level"] = idx
                parsed_chain.append(info)
        else:
            # Fallback: get leaf cert via built-in SSL
            print_colored("[!] OpenSSL CLI not available or failed. Falling back to built-in Python ssl (leaf only).", COLOR_WARNING)
            leaf_dict = self.get_leaf_cert_built_in()
            if leaf_dict:
                info = self.parse_built_in_cert(leaf_dict)
                info["level"] = 0
                parsed_chain.append(info)
            else:
                print_colored(f"[!] Critical Error: Could not connect or retrieve certificates from {self.host}.", COLOR_FAIL)
                sys.exit(1)

        # 2. Render Chain Tree
        print_colored(f"\n{COLOR_BOLD}Certificate Chain Structure:{COLOR_END}", COLOR_CYAN)
        for idx, cert in enumerate(parsed_chain):
            indent = "    " * idx
            branch = "└── " if idx > 0 else ""
            cn = cert.get("common_name", "Unknown")
            is_ca = " [CA]" if cert.get("is_ca") else ""
            key_info = f" ({cert.get('key_type')} {cert.get('key_size')} bits)" if cert.get("key_size") else ""
            print_colored(f"{indent}{branch}{cn}{is_ca}{key_info}", COLOR_BOLD + COLOR_BLUE if idx == 0 else COLOR_BLUE)

        # 3. Analyze each certificate in details
        print_colored(f"\n{COLOR_BOLD}Certificate Auditing Details:{COLOR_END}", COLOR_CYAN)
        now = datetime.datetime.utcnow()
        
        for idx, cert in enumerate(parsed_chain):
            level_name = "Leaf Certificate" if idx == 0 else f"Intermediate Certificate #{idx}"
            print_colored(f"\n--- {level_name} ---", COLOR_BOLD + COLOR_CYAN)
            print(f"  Subject:     {cert.get('subject')}")
            print(f"  Issuer:      {cert.get('issuer')}")
            print(f"  Valid From:  {cert.get('not_before')}")
            print(f"  Valid Until: {cert.get('not_after')}")
            print(f"  Signature:   {cert.get('sig_algo')}")
            if cert.get("sans"):
                print(f"  SANs:        {', '.join(cert.get('sans')[:5])} ... ({len(cert['sans'])} total)")
                
            # Perform Security Checks
            issues = []
            
            # Expiration
            expiry_dt = cert.get("expiry_datetime")
            if expiry_dt:
                if expiry_dt < now:
                    issues.append((f"❌ EXPIRED: Certificate expired on {expiry_dt}", COLOR_FAIL))
                elif (expiry_dt - now).days < 30:
                    issues.append((f"⚠️  EXPIRING SOON: Certificate expires in {(expiry_dt - now).days} days", COLOR_WARNING))
                else:
                    issues.append((f"✅ Valid for {(expiry_dt - now).days} more days", COLOR_GREEN))
            else:
                issues.append(("⚠️  Could not determine expiration datetime", COLOR_WARNING))

            # Signature Weakness
            sig_algo = cert.get("sig_algo", "").lower()
            if "sha1" in sig_algo or "md5" in sig_algo:
                issues.append((f"❌ WEAK SIGNATURE: Uses deprecated hash algorithm ({cert.get('sig_algo')})", COLOR_FAIL))

            # Key Length Weakness
            key_size = cert.get("key_size")
            key_type = cert.get("key_type", "").upper()
            if key_size and key_type == "RSA" and key_size < 2048:
                issues.append((f"❌ WEAK KEY SIZE: RSA key length is {key_size} bits (minimum 2048 required)", COLOR_FAIL))
            elif key_size and key_type == "EC" and key_size < 256:
                issues.append((f"❌ WEAK EC KEY: Elliptic Curve key size is {key_size} bits (minimum 256 required)", COLOR_FAIL))

            # Leaf specifics
            if idx == 0:
                # SAN verification
                if not cert.get("sans"):
                    issues.append(("❌ MISSING SANs: No Subject Alternative Names declared", COLOR_FAIL))
                else:
                    # Check if host matches any SAN pattern
                    host_match = False
                    host_clean = self.host.lower()
                    for san in cert.get("sans", []):
                        san_clean = san.lower()
                        # Handle wildcard matching, e.g. *.google.com matches mail.google.com
                        if san_clean.startswith("*."):
                            pattern = "^[^.]+\\." + re.escape(san_clean[2:]) + "$"
                            if re.match(pattern, host_clean):
                                host_match = True
                                break
                        elif san_clean == host_clean:
                            host_match = True
                            break
                    if not host_match:
                        issues.append((f"❌ HOSTNAME MISMATCH: Hostname '{self.host}' is not covered by SANs", COLOR_FAIL))

            # Print audited states
            for msg, color in issues:
                print_colored(f"  {msg}", color)


def main():
    parser = argparse.ArgumentParser(
        description="Audit and visualize SSL/TLS certificate chains.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("domain", help="Target domain name or IP address (e.g. google.com)")
    parser.add_argument("--port", "-p", type=int, default=443, help="Target TCP port (default: 443)")
    parser.add_argument("--timeout", "-t", type=float, default=5.0, help="Socket timeout in seconds (default: 5.0)")

    args = parser.parse_args()

    analyzer = SSLChainAnalyzer(args.domain, args.port, args.timeout)
    analyzer.run_audit()


if __name__ == "__main__":
    main()
