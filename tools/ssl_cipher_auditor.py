#!/usr/bin/env python3
"""
SSL/TLS Cipher Suite & Protocol Auditor

A security auditing tool to connect to a target server, analyze the negotiated SSL/TLS
protocol and cipher suite, evaluate their strength (Strong/Medium/Weak), and print key
certificate metadata.

Usage:
    python tools/ssl_cipher_auditor.py google.com
    python tools/ssl_cipher_auditor.py github.com -p 443
"""

import sys
import ssl
import socket
import argparse
from datetime import datetime

# Colors for terminal output
COLOR_STRONG = "\033[92m[STRONG]\033[0m"
COLOR_MEDIUM = "\033[93m[MEDIUM]\033[0m"
COLOR_WEAK = "\033[91m[WEAK/INSECURE]\033[0m"
COLOR_RESET = "\033[0m"

def evaluate_tls_version(version_str):
    """Evaluate the strength of the negotiated TLS version."""
    version_str = version_str.upper()
    if "TLSV1.3" in version_str:
        return COLOR_STRONG, "TLS 1.3 is the modern standard, offering optimal speed and security."
    elif "TLSV1.2" in version_str:
        return COLOR_STRONG, "TLS 1.2 is secure, but lacks some security features and performance enhancements of TLS 1.3."
    elif any(v in version_str for v in ["TLSV1.1", "TLSV1.0", "TLSV1"]):
        return COLOR_WEAK, "TLS 1.0/1.1 is deprecated globally and has known security flaws (e.g., BEAST, POODLE)."
    elif any(v in version_str for v in ["SSLV2", "SSLV3"]):
        return COLOR_WEAK, "SSLv2/SSLv3 is extremely insecure and obsolete. High vulnerability to attacks."
    else:
        return COLOR_MEDIUM, f"Unknown TLS version: {version_str}. Verify server config manually."

def evaluate_cipher_suite(cipher_name):
    """Evaluate the cryptographic strength of the negotiated cipher suite."""
    cipher_upper = cipher_name.upper()
    
    # Insecure elements
    weak_keywords = ["RC4", "3DES", "DES", "MD5", "NULL", "EXPORT", "ADH", "ANON", "anon"]
    if any(wk in cipher_upper for wk in weak_keywords):
        return COLOR_WEAK, "Cipher uses weak algorithms (e.g., RC4, 3DES, MD5) susceptible to interception or brute force."

    # Strong elements (AEAD ciphers)
    aead_keywords = ["GCM", "CHACHA20", "POLY1305"]
    is_aead = any(ak in cipher_upper for ak in aead_keywords)
    is_ephemeral = "ECDHE" in cipher_upper or "DHE" in cipher_upper
    
    if is_aead and is_ephemeral:
        return COLOR_STRONG, "Modern AEAD cipher suite with Perfect Forward Secrecy (PFS)."
    elif is_aead:
        return COLOR_MEDIUM, "AEAD cipher suite but lacks Ephemeral Key Exchange (PFS might be missing)."
    elif is_ephemeral:
        return COLOR_MEDIUM, "Offers Forward Secrecy, but uses older CBC-mode encryption which can be vulnerable to padding attacks."
    else:
        return COLOR_MEDIUM, "Acceptable cipher suite, but lacks Forward Secrecy and uses older CBC mode."

def format_cert_subject(dn):
    """Format subject/issuer distinguished name tuples into a readable string."""
    if not dn:
        return "N/A"
    parts = []
    for item in dn:
        if isinstance(item, tuple) and len(item) > 0:
            sub_item = item[0]
            if len(sub_item) >= 2:
                parts.append(f"{sub_item[0]}={sub_item[1]}")
    return ", ".join(parts)

def audit_host(host, port):
    """Connect to host:port and audit SSL/TLS parameters."""
    print(f"Auditing SSL/TLS configuration for {host}:{port}...")
    
    # Create default SSL context
    context = ssl.create_default_context()
    
    try:
        # Resolve address first to give a nice socket message
        addr_info = socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
        ip_addr = addr_info[0][4][0]
        print(f"Resolved {host} to {ip_addr}")
        
        # Connect and wrap socket
        with socket.create_connection((host, port), timeout=5.0) as sock:
            with context.wrap_socket(sock, server_hostname=host) as ssock:
                # 1. Get Negotiated Connection details
                negotiated_version = ssock.version()
                cipher_info = ssock.cipher()
                cipher_name, ssl_ver, key_bits = cipher_info
                
                print("\n=== Connection Audit ===")
                # Protocol Version
                color_ver, desc_ver = evaluate_tls_version(negotiated_version)
                print(f"Protocol Version:  {negotiated_version} {color_ver}")
                print(f"  Info:            {desc_ver}")
                
                # Cipher Suite
                color_cipher, desc_cipher = evaluate_cipher_suite(cipher_name)
                print(f"Negotiated Cipher: {cipher_name} ({key_bits} bits) {color_cipher}")
                print(f"  Info:            {desc_cipher}")
                
                # 2. Get Certificate Details
                cert = ssock.getpeercert()
                if cert:
                    print("\n=== Certificate Metadata ===")
                    
                    # Common Name / Subject
                    subject = format_cert_subject(cert.get('subject'))
                    print(f"Subject:           {subject}")
                    
                    # Issuer
                    issuer = format_cert_subject(cert.get('issuer'))
                    print(f"Issuer:            {issuer}")
                    
                    # Validity
                    not_before_str = cert.get('notBefore')
                    not_after_str = cert.get('notAfter')
                    
                    try:
                        # SSL date format: 'Jun 28 14:00:00 2026 GMT'
                        fmt = "%b %d %H:%M:%S %Y %Z"
                        not_before = datetime.strptime(not_before_str, fmt)
                        not_after = datetime.strptime(not_after_str, fmt)
                        now = datetime.utcnow()
                        
                        days_left = (not_after - now).days
                        
                        print(f"Issued On:         {not_before.strftime('%Y-%m-%d %H:%M:%S')} UTC")
                        print(f"Expires On:        {not_after.strftime('%Y-%m-%d %H:%M:%S')} UTC")
                        
                        if now < not_before:
                            print(f"Status:            \033[91m[NOT YET VALID]\033[0m Starts in {(not_before - now).days} days.")
                        elif now > not_after:
                            print(f"Status:            \033[91m[EXPIRED]\033[0m Expired {-days_left} days ago.")
                        else:
                            print(f"Status:            \033[92m[VALID]\033[0m (Expires in {days_left} days)")
                    except Exception:
                        print(f"Not Before:        {not_before_str}")
                        print(f"Not After:         {not_after_str}")
                        
                    # SAN (Subject Alternative Names)
                    san = cert.get('subjectAltName', [])
                    san_dns = [val for name, val in san if name.upper() == 'DNS']
                    if san_dns:
                        dns_list = ", ".join(san_dns[:5])
                        if len(san_dns) > 5:
                            dns_list += f" ... (+{len(san_dns)-5} more)"
                        print(f"Subject Alt Names: {dns_list}")
                else:
                    print("\n[WARNING] No certificate details returned by socket. (Is it self-signed or using SNI mismatch?)")
                    
    except socket.timeout:
        print(f"Error: Connection to {host}:{port} timed out.")
        return False
    except ssl.SSLError as e:
        print(f"SSL/TLS Handshake Error: {e}")
        return False
    except Exception as e:
        print(f"Failed to audit server: {e}")
        return False
    return True

def main():
    parser = argparse.ArgumentParser(description="SSL/TLS Cipher Suite & Protocol Auditor")
    parser.add_argument("host", help="Target hostname/domain to audit (e.g. google.com)")
    parser.add_argument("-p", "--port", type=int, default=443, help="Port to connect (default 443)")
    
    args = parser.parse_args()
    
    success = audit_host(args.host, args.port)
    return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())
