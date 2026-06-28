#!/usr/bin/env python3
"""
Self-Signed SSL/TLS Certificate Generator

Generates self-signed SSL/TLS certificates and private key pairs for local
testing and development servers. Supports specifying domains, IP addresses,
wildcard domains, and certificate validity duration.

Features:
    - Automatically uses `cryptography` library if installed.
    - Fallbacks to system `openssl` command-line utility if cryptography is not available.
    - Configures Subject Alternative Name (SAN) so browsers don't reject it with ERR_CERT_COMMON_NAME_INVALID.

Usage:
    python tools/self_signed_cert_generator.py localhost -d example.com,*.example.com -ip 127.0.0.1
"""

import os
import sys
import subprocess
import tempfile
import argparse

# ANSI color codes
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
RESET = "\033[0m"

def print_colored(text, color):
    """Print text with ANSI color."""
    print(f"{color}{text}{RESET}")

def has_cryptography() -> bool:
    """Check if the cryptography module is available."""
    try:
        import cryptography
        return True
    except ImportError:
        return False

def has_openssl_cli() -> bool:
    """Check if openssl command-line tool is in PATH."""
    try:
        subprocess.run(["openssl", "version"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except (FileNotFoundError, PermissionError):
        return False

def generate_via_cryptography(common_name: str, domains: list, ips: list, days: int, key_path: str, cert_path: str):
    """Generate self-signed certificate using Python's cryptography library."""
    from datetime import datetime, timedelta, timezone
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives import serialization
    import ipaddress

    print_colored("[*] Generating 2048-bit RSA private key...", BLUE)
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048
    )

    print_colored("[*] Constructing X.509 certificate subject details...", BLUE)
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
        x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "State"),
        x509.NameAttribute(NameOID.LOCALITY_NAME, "City"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "Local Development"),
        x509.NameAttribute(NameOID.COMMON_NAME, common_name),
    ])

    # Construct Subject Alternative Names (SAN)
    san_list = []
    
    # Common name must be in SAN as well per modern standards
    san_list.append(x509.DNSName(common_name))
    
    for d in domains:
        if d != common_name:
            san_list.append(x509.DNSName(d))
            
    for ip in ips:
        try:
            san_list.append(x509.IPAddress(ipaddress.ip_address(ip)))
        except ValueError:
            print_colored(f"[!] Warning: Invalid IP address '{ip}' ignored.", YELLOW)

    cert_builder = x509.CertificateBuilder()
    cert_builder = cert_builder.subject_name(subject)
    cert_builder = cert_builder.issuer_name(issuer)
    cert_builder = cert_builder.public_key(private_key.public_key())
    cert_builder = cert_builder.serial_number(x509.random_serial_number())
    
    # Validity times (UTC timezone-aware)
    start_time = datetime.now(timezone.utc)
    cert_builder = cert_builder.not_valid_before(start_time)
    cert_builder = cert_builder.not_valid_after(start_time + timedelta(days=days))
    
    # Add SAN extension
    cert_builder = cert_builder.add_extension(
        x509.SubjectAlternativeName(san_list),
        critical=False
    )
    
    # Add basic constraints (CA is false)
    cert_builder = cert_builder.add_extension(
        x509.BasicConstraints(ca=False, path_length=None),
        critical=True
    )

    print_colored("[*] Signing certificate with RSA private key...", BLUE)
    certificate = cert_builder.sign(
        private_key,
        hashes.SHA256()
    )

    # Write private key
    with open(key_path, "wb") as f:
        f.write(
            private_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            )
        )

    # Write certificate
    with open(cert_path, "wb") as f:
        f.write(
            certificate.public_bytes(
                encoding=serialization.Encoding.PEM
            )
        )

def generate_via_openssl_cli(common_name: str, domains: list, ips: list, days: int, key_path: str, cert_path: str):
    """Generate self-signed certificate using system openssl CLI binary."""
    print_colored("[*] Falling back to system OpenSSL command-line tool...", YELLOW)
    
    # Create OpenSSL config file to support SAN extensions
    config_lines = [
        "[req]",
        "distinguished_name = req_distinguished_name",
        "x509_extensions = v3_req",
        "prompt = no",
        "",
        "[req_distinguished_name]",
        "C = US",
        "ST = State",
        "L = City",
        "O = Local Development",
        f"CN = {common_name}",
        "",
        "[v3_req]",
        "keyUsage = keyEncipherment, dataEncipherment",
        "extendedKeyUsage = serverAuth",
        "subjectAltName = @alt_names",
        "",
        "[alt_names]"
    ]
    
    alt_name_idx = 1
    # Add common name as first DNS
    config_lines.append(f"DNS.{alt_name_idx} = {common_name}")
    alt_name_idx += 1
    
    for d in domains:
        if d != common_name:
            config_lines.append(f"DNS.{alt_name_idx} = {d}")
            alt_name_idx += 1
            
    ip_idx = 1
    for ip in ips:
        config_lines.append(f"IP.{ip_idx} = {ip}")
        ip_idx += 1
        
    with tempfile.NamedTemporaryFile("w", suffix=".conf", delete=False) as f:
        f.write("\n".join(config_lines))
        config_file_path = f.name
        
    try:
        cmd = [
            "openssl", "req", "-x509", 
            "-nodes", 
            "-days", str(days), 
            "-newkey", "rsa:2048", 
            "-keyout", key_path, 
            "-out", cert_path, 
            "-config", config_file_path
        ]
        
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if result.returncode != 0:
            print_colored(f"[-] OpenSSL command failed: {result.stderr}", RED)
            sys.exit(1)
            
    finally:
        # Clean up temporary config file
        if os.path.exists(config_file_path):
            os.remove(config_file_path)

def main():
    parser = argparse.ArgumentParser(
        description="Self-Signed SSL/TLS Certificate Generator - Generate local development credentials."
    )
    parser.add_argument("common_name", help="Common Name (CN) for the certificate (e.g. localhost).")
    parser.add_argument("-d", "--domains", default="", 
                        help="Comma-separated Subject Alternative Name (SAN) DNS domains.")
    parser.add_argument("-ip", "--ips", default="", 
                        help="Comma-separated Subject Alternative Name (SAN) IP addresses.")
    parser.add_argument("--days", type=int, default=365, 
                        help="Number of days the certificate is valid (default: 365).")
    parser.add_argument("-k", "--key-out", default="key.pem", 
                        help="Output path for the private key file (default: key.pem).")
    parser.add_argument("-c", "--cert-out", default="cert.pem", 
                        help="Output path for the certificate file (default: cert.pem).")
                        
    args = parser.parse_args()
    
    # Process domains and ips
    domains_list = [d.strip() for d in args.domains.split(",") if d.strip()]
    ips_list = [ip.strip() for ip in args.ips.split(",") if ip.strip()]
    
    if has_cryptography():
        try:
            generate_via_cryptography(
                args.common_name, domains_list, ips_list, 
                args.days, args.key_out, args.cert_out
            )
            success = True
        except Exception as e:
            print_colored(f"[-] Python Cryptography generation failed: {e}", RED)
            success = False
    elif has_openssl_cli():
        try:
            generate_via_openssl_cli(
                args.common_name, domains_list, ips_list, 
                args.days, args.key_out, args.cert_out
            )
            success = True
        except Exception as e:
            print_colored(f"[-] OpenSSL CLI generation failed: {e}", RED)
            success = False
    else:
        print_colored("[-] Error: No method to generate certificates is available.", RED)
        print_colored("    Please install python cryptography library: `pip install cryptography`", RED)
        print_colored("    Or make sure the `openssl` command line utility is installed and in your PATH.", RED)
        sys.exit(1)
        
    if success:
        print()
        print_colored(f"[+] Success! Self-signed certificate generated successfully.", GREEN)
        print(f"    - Certificate: {os.path.abspath(args.cert_out)}")
        print(f"    - Private Key: {os.path.abspath(args.key_out)}")
        print(f"    - Valid for:   {args.days} days")
        print(f"    - CN Name:     {args.common_name}")
        if domains_list:
            print(f"    - SAN Domains: {', '.join(domains_list)}")
        if ips_list:
            print(f"    - SAN IPs:     {', '.join(ips_list)}")

if __name__ == "__main__":
    main()
