#!/usr/bin/env python3
"""
JWT Debugger & Offline Token Tool - Decodes, parses, and generates JSON Web Tokens (JWT) locally.
Includes HMAC-SHA256 (HS256) signature verification and date conversions.
"""

import argparse
import base64
import datetime
import hmac
import hashlib
import json
import sys

def base64url_decode(payload_str):
    """Decodes a base64url-encoded string, restoring necessary padding."""
    # Ensure correct padding length
    rem = len(payload_str) % 4
    if rem > 0:
        payload_str += '=' * (4 - rem)
    # base64url replaces + with - and / with _
    std_base64 = payload_str.replace('-', '+').replace('_', '/')
    return base64.b64decode(std_base64)

def base64url_encode(bytes_data):
    """Encodes bytes into a base64url string with padding removed."""
    std_base64 = base64.b64encode(bytes_data).decode('utf-8')
    return std_base64.replace('+', '-').replace('/', '_').rstrip('=')

def format_timestamp(ts):
    """Formats a Unix epoch timestamp into local date time string."""
    try:
        dt = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).astimezone()
        return f"{ts} ({dt.strftime('%Y-%m-%d %H:%M:%S %Z')})"
    except Exception:
        return str(ts)

def decode_token(token_str, secret_key=None):
    """Decodes a JWT and verifies signature if a secret key is provided."""
    parts = token_str.strip().split('.')
    if len(parts) != 3:
        raise ValueError("JWT must consist of three parts separated by dots (header.payload.signature)")

    header_segment, payload_segment, crypto_segment = parts

    # Decode Header
    try:
        header_bytes = base64url_decode(header_segment)
        header = json.loads(header_bytes.decode('utf-8'))
    except Exception as e:
        raise ValueError(f"Failed to decode header: {e}")

    # Decode Payload
    try:
        payload_bytes = base64url_decode(payload_segment)
        payload = json.loads(payload_bytes.decode('utf-8'))
    except Exception as e:
        raise ValueError(f"Failed to decode payload: {e}")

    # Decode Signature bytes
    try:
        signature = base64url_decode(crypto_segment)
    except Exception as e:
        raise ValueError(f"Failed to decode signature: {e}")

    # Format output dictionary
    result = {
        'header': header,
        'payload': payload,
        'signature_hex': signature.hex(),
        'signature_verified': None
    }

    # Format human readable times for standard claims
    time_claims = ['exp', 'iat', 'nbf', 'auth_time']
    result['readable_claims'] = {}
    for claim in time_claims:
        if claim in payload:
            result['readable_claims'][claim] = format_timestamp(payload[claim])

    # Signature verification
    if secret_key:
        alg = header.get('alg', 'HS256')
        if alg != 'HS256':
            result['signature_verified'] = False
            result['verification_error'] = f"Unsupported signature algorithm '{alg}'. Only HS256 is supported."
        else:
            # Verify using HMAC-SHA256
            signing_input = f"{header_segment}.{payload_segment}".encode('utf-8')
            expected_sig = hmac.new(
                secret_key.encode('utf-8'),
                signing_input,
                hashlib.sha256
            ).digest()
            
            if hmac.compare_digest(expected_sig, signature):
                result['signature_verified'] = True
            else:
                result['signature_verified'] = False
                result['verification_error'] = "Invalid signature - Token has been tampered with or key is incorrect."

    return result

def encode_token(payload_dict, secret_key, alg='HS256'):
    """Generates a signed JWT using HS256 algorithm."""
    if alg != 'HS256':
        raise ValueError("Only HS256 (HMAC-SHA256) is supported for encoding.")

    header = {
        'alg': alg,
        'typ': 'JWT'
    }

    header_segment = base64url_encode(json.dumps(header, separators=(',', ':')).encode('utf-8'))
    payload_segment = base64url_encode(json.dumps(payload_dict, separators=(',', ':')).encode('utf-8'))

    signing_input = f"{header_segment}.{payload_segment}".encode('utf-8')
    signature = hmac.new(
        secret_key.encode('utf-8'),
        signing_input,
        hashlib.sha256
    ).digest()

    crypto_segment = base64url_encode(signature)
    return f"{header_segment}.{payload_segment}.{crypto_segment}"

def main():
    parser = argparse.ArgumentParser(
        description="JWT Debugger: Locally parse and generate HS256 JSON Web Tokens without network requests.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Decode a token
  python tools/jwt_debugger.py -d eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c
  
  # Decode and verify signature with key
  python tools/jwt_debugger.py -d <token> -k my_secret_key
  
  # Encode a payload into a new token
  python tools/jwt_debugger.py -e '{"sub":"user123","role":"admin"}' -k my_secret_key --expiry-seconds 3600
"""
    )
    
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-d", "--decode", help="JWT token string to decode")
    group.add_argument("-e", "--encode", help="JSON string representing the payload to encode")
    
    parser.add_argument("-k", "--key", help="Secret key for signature verification (decode) or generation (encode)")
    parser.add_argument("--expiry-seconds", type=int, help="Optional duration in seconds to add as an 'exp' claim to the encoded payload")

    args = parser.parse_args()

    if args.decode:
        try:
            result = decode_token(args.decode, args.key)
            print("=" * 60)
            print("HEADER:")
            print(json.dumps(result['header'], indent=2))
            print("-" * 60)
            print("PAYLOAD:")
            print(json.dumps(result['payload'], indent=2))
            
            if result['readable_claims']:
                print("-" * 60)
                print("HUMAN READABLE CLAIMS:")
                for claim, val in result['readable_claims'].items():
                    print(f"  {claim:<10}: {val}")
                    
            print("-" * 60)
            print("SIGNATURE:")
            print(f"  Hex: {result['signature_hex']}")
            if args.key:
                if result['signature_verified']:
                    print("  Status: [PASS] Signature verified successfully!")
                else:
                    print(f"  Status: [FAIL] {result.get('verification_error', 'Invalid signature.')}")
            else:
                print("  Status: [WARNING] Signature not checked (provide -k/--key to verify).")
            print("=" * 60)
        except Exception as e:
            print(f"[!] Error: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.encode:
        if not args.key:
            print("[!] Error: Encoding a token requires a secret key (-k/--key).", file=sys.stderr)
            sys.exit(1)
            
        try:
            payload = json.loads(args.encode)
        except Exception as e:
            print(f"[!] Error: Failed to parse payload JSON: {e}", file=sys.stderr)
            sys.exit(1)
            
        # Add expiry if requested
        if args.expiry_seconds:
            now_ts = int(datetime.datetime.now(datetime.timezone.utc).timestamp())
            payload['iat'] = now_ts
            payload['exp'] = now_ts + args.expiry_seconds
            print(f"[*] Added 'iat' ({format_timestamp(payload['iat'])}) and 'exp' ({format_timestamp(payload['exp'])}) to payload.")
            
        try:
            token = encode_token(payload, args.key)
            print("=" * 60)
            print("GENERATED JWT TOKEN:")
            print(token)
            print("=" * 60)
        except Exception as e:
            print(f"[!] Error encoding token: {e}", file=sys.stderr)
            sys.exit(1)

if __name__ == "__main__":
    main()
