#!/usr/bin/env python3
"""
JWT Decoder & Debugger

Decodes and inspects JSON Web Tokens (JWT) header, payload, and signature
metadata, formatting epoch timestamps to human-readable datetime formats.

Usage:
    python tools/jwt_decoder.py <JWT_TOKEN>
    echo <JWT_TOKEN> | python tools/jwt_decoder.py
"""

import argparse
import base64
import json
import sys
from datetime import datetime, timezone

def clean_base64_payload(data):
    """Add padding to base64 string if missing."""
    data = data.replace('-', '+').replace('_', '/')
    padding = len(data) % 4
    if padding:
        data += '=' * (4 - padding)
    return data

def decode_part(part):
    """Decode base64url encoded JWT part to dictionary."""
    try:
        cleaned = clean_base64_payload(part)
        decoded_bytes = base64.b64decode(cleaned)
        return json.loads(decoded_bytes.decode('utf-8'))
    except Exception as e:
        return {"error": f"Failed to decode or parse JSON: {str(e)}"}

def format_timestamp(epoch):
    """Convert epoch timestamp to local and UTC datetime strings."""
    try:
        dt_utc = datetime.fromtimestamp(epoch, tz=timezone.utc)
        dt_local = datetime.fromtimestamp(epoch)
        return f"{dt_utc.strftime('%Y-%m-%d %H:%M:%S')} UTC / {dt_local.strftime('%Y-%m-%d %H:%M:%S')} Local"
    except Exception:
        return "Invalid timestamp"

def decode_jwt(token):
    """Deconstruct and decode the JWT."""
    token = token.strip()
    parts = token.split('.')
    
    if len(parts) != 3:
        print("Error: Invalid JWT format. A JWT must consist of three parts separated by dots (header.payload.signature).", file=sys.stderr)
        return 1

    header_raw, payload_raw, signature_raw = parts
    
    header = decode_part(header_raw)
    payload = decode_part(payload_raw)

    print("=" * 60)
    print("JWT DECODER & DEBUGGER")
    print("=" * 60)
    
    # 1. Header
    print("\n[1] HEADER (Algorithm & Token Type)")
    print("-" * 40)
    print(json.dumps(header, indent=4))
    
    # 2. Payload
    print("\n[2] PAYLOAD (Claims)")
    print("-" * 40)
    print(json.dumps(payload, indent=4))
    
    # 3. Signature Metadata
    print("\n[3] SIGNATURE METADATA")
    print("-" * 40)
    print(f"Raw Signature (Base64url): {signature_raw[:30]}... ({len(signature_raw)} chars)")
    
    # 4. Decoded Claim Details
    print("\n[4] KEY CLAIMS DETAILS")
    print("-" * 40)
    
    claim_found = False
    for claim, label in [
        ('iss', 'Issuer (iss)'),
        ('sub', 'Subject (sub)'),
        ('aud', 'Audience (aud)'),
        ('exp', 'Expiration Time (exp)'),
        ('nbf', 'Not Before (nbf)'),
        ('iat', 'Issued At (iat)'),
        ('jti', 'JWT ID (jti)')
    ]:
        if claim in payload:
            claim_found = True
            val = payload[claim]
            if claim in ('exp', 'nbf', 'iat') and isinstance(val, (int, float)):
                # Check status
                status = ""
                if claim == 'exp':
                    now = datetime.now(timezone.utc).timestamp()
                    if val < now:
                        status = " ⚠️ [EXPIRED]"
                    else:
                        status = " ✅ [ACTIVE]"
                print(f"{label:<22}: {val} ({format_timestamp(val)}){status}")
            else:
                print(f"{label:<22}: {val}")
                
    if not claim_found:
        print("No standard claims found in payload.")
        
    print("=" * 60)
    return 0

def main():
    parser = argparse.ArgumentParser(description="Decode and inspect JSON Web Tokens (JWT) without external dependencies.")
    parser.add_argument('token', nargs='?', help='The JWT token string to decode')
    args = parser.parse_args()

    token = args.token
    if not token:
        # Check if piped data is available
        if not sys.stdin.isatty():
            token = sys.stdin.read()
        else:
            parser.print_help()
            print("\nError: Please provide a token as an argument or via standard input.", file=sys.stderr)
            return 1
            
    if not token or not token.strip():
        print("Error: Empty token provided.", file=sys.stderr)
        return 1
        
    return decode_jwt(token)

if __name__ == "__main__":
    sys.exit(main())
