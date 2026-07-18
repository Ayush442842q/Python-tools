#!/usr/bin/env python3
"""
SSL/TLS Certificate CRL & OCSP Revocation Prober

A standalone utility to inspect TLS certificate revocation architectures.
1. Establishes a socket/SSL connection to retrieve a target's binary DER certificate.
2. Natively scans DER structures for Authority Information Access (AIA) OCSP URIs
   and CRL Distribution Points (CDP) URLs.
3. Probes the identified OCSP/CRL endpoints to verify if they are online and responsive.

Usage:
    python crl_ocsp_prober.py example.com
    python crl_ocsp_prober.py google.com
"""

import sys
import os
import argparse
import socket
import ssl
import urllib.request
import urllib.error
import re

# OID byte representations for searching DER structure
# OID: 2.5.29.31 (CRL Distribution Points)
CRL_DP_OID_BYTES = b'\x55\x1d\x1f'
# OID: 1.3.6.1.5.5.7.1.1 (Authority Info Access)
AIA_OID_BYTES = b'\x2b\x06\x01\x05\x05\x07\x01\x01'
# OID: 1.3.6.1.5.5.7.48.1 (OCSP Responder)
OCSP_OID_BYTES = b'\x2b\x06\x01\x05\x05\x07\x30\x01'

def parse_asn1_length(data, offset):
    """Parses DER length octets, returning (length, next_offset)."""
    if offset >= len(data):
        return 0, offset
    byte = data[offset]
    if byte & 0x80 == 0:
        return byte, offset + 1
    num_octets = byte & 0x7F
    if offset + 1 + num_octets > len(data):
        return 0, len(data)
    val = 0
    for i in range(num_octets):
        val = (val << 8) | data[offset + 1 + i]
    return val, offset + 1 + num_octets

def extract_urls(der_data):
    """
    Scans the DER byte array for http/https URLs using ASN.1 IA5String tag parsing
    and context-specific GeneralName URI tag (0x86) parsing.
    Falls back to regex scanning if no URLs are found.
    """
    urls = []
    
    # 1. Parse via ASN.1 tags (0x16 for IA5String, 0x86 for context-specific GeneralName URI)
    offset = 0
    while offset < len(der_data):
        tag = der_data[offset]
        if tag in (0x16, 0x86):
            length, val_offset = parse_asn1_length(der_data, offset + 1)
            if val_offset + length <= len(der_data):
                val = der_data[val_offset:val_offset + length]
                if val.startswith(b'http://') or val.startswith(b'https://'):
                    url_str = val.decode('ascii', errors='ignore').strip()
                    if url_str not in urls:
                        urls.append(url_str)
            offset = val_offset + length
        else:
            offset += 1

    # 2. Fallback to regex if no URLs resolved
    if not urls:
        url_pattern = re.compile(b'https?://[a-zA-Z0-9\\.\\-_/\\?=&%~]+')
        matches = url_pattern.findall(der_data)
        for m in matches:
            url_str = m.decode('ascii', errors='ignore').strip()
            # Clean trailing non-standard URL characters
            url_str = re.sub(r'[^a-zA-Z0-9\-_/\?=&~]$', '', url_str)
            if url_str not in urls:
                urls.append(url_str)
            
    # Classify based on string heuristics
    ocsp_urls = []
    crl_urls = []
    
    for u in urls:
        u_lower = u.lower()
        if 'ocsp' in u_lower:
            ocsp_urls.append(u)
        elif 'crl' in u_lower or u_lower.endswith('.crl'):
            crl_urls.append(u)
        else:
            # Fallback checks (e.g. PKI / cert path)
            if 'pki' in u_lower:
                crl_urls.append(u)
                
    return ocsp_urls, crl_urls

def probe_revocation_endpoint(url):
    """Sends a basic GET/HEAD query to verify if the server is online."""
    try:
        req = urllib.request.Request(
            url,
            method='HEAD',
            headers={'User-Agent': 'Mozilla/5.0 (Revocation Prober)'}
        )
        with urllib.request.urlopen(req, timeout=3.0) as response:
            return True, response.status, "HEAD Succeeded"
    except urllib.error.HTTPError as e:
        # Some responders don't allow HEAD, so check if GET works
        try:
            req_get = urllib.request.Request(
                url,
                method='GET',
                headers={'User-Agent': 'Mozilla/5.0 (Revocation Prober)'}
            )
            with urllib.request.urlopen(req_get, timeout=3.0) as response:
                return True, response.status, "GET Succeeded"
        except Exception as e_get:
            return False, None, str(e_get)
    except Exception as e:
        return False, None, str(e)

def get_certificate_der(hostname, port=443):
    """Connects to server and retrieves DER-encoded certificate."""
    context = ssl.create_default_context()
    # Disable certificate verification errors so we can probe self-signed/expired certs!
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(4.0)
        ssl_sock = context.wrap_socket(sock, server_hostname=hostname)
        ssl_sock.connect((hostname, port))
        der_data = ssl_sock.getpeercert(binary_form=True)
        ssl_sock.close()
        return der_data, None
    except Exception as e:
        return None, f"Failed establishing connection: {e}"

def run_probe(hostname, port=443):
    """Runs the CRL/OCSP audit logic on the host."""
    der_data, err = get_certificate_der(hostname, port)
    if err:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    ocsp_urls, crl_urls = extract_urls(der_data)

    print("SSL/TLS Certificate Revocation Auditor")
    print("=" * 75)
    print(f"Target Host    : {hostname}:{port}")
    print(f"DER Cert Size  : {len(der_data)} bytes")
    print("=" * 75)

    print("\n[Identified OCSP Responders]")
    print("-" * 75)
    if ocsp_urls:
        for url in ocsp_urls:
            print(f"  URL : {url}")
            print(f"  Ping: Probing responder ... ", end="")
            sys.stdout.flush()
            online, code, msg = probe_revocation_endpoint(url)
            if online:
                print(f"\033[92mONLINE (HTTP {code})\033[0m")
            else:
                print(f"\033[91mOFFLINE ({msg})\033[0m")
    else:
        print("  No OCSP Responder URIs found in certificate extensions.")

    print("\n[Identified CRL Distribution Points]")
    print("-" * 75)
    if crl_urls:
        for url in crl_urls:
            print(f"  URL : {url}")
            print(f"  Ping: Probing endpoint  ... ", end="")
            sys.stdout.flush()
            online, code, msg = probe_revocation_endpoint(url)
            if online:
                print(f"\033[92mONLINE (HTTP {code})\033[0m")
            else:
                print(f"\033[91mOFFLINE ({msg})\033[0m")
    else:
        print("  No CRL distribution point URLs found in certificate extensions.")

    print("=" * 75)
    return 0

def main():
    parser = argparse.ArgumentParser(
        description="Verify HTTPS certificate revocation endpoints (CDPs and OCSPs) natively.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("host", help="Hostname of target server (e.g. google.com).")
    parser.add_argument("-p", "--port", type=int, default=443, help="HTTPS port number. Defaults to 443.")
    args = parser.parse_args()

    # Normalize hostname by stripping protocol prefix if entered
    host = args.host
    if host.startswith('https://'):
        host = host[8:]
    elif host.startswith('http://'):
        host = host[7:]
        
    # Strip URL path or query params if input was full URL
    host = host.split('/')[0].split('?')[0]

    return run_probe(host, args.port)

if __name__ == "__main__":
    sys.exit(main())
