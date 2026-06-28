#!/usr/bin/env python3
"""
JWT Generator & Signer

Generates and signs JSON Web Tokens (JWT) using HMAC-SHA algorithms (HS256, HS384, HS512)
without any external dependencies. Supports customizable headers, payloads, standard claims,
and key parameters.

Usage:
    python tools/jwt_generator.py --secret "my-super-secret-key" --payload '{"user_id": 123, "role": "admin"}'
    python tools/jwt_generator.py -s "secret" --iss "auth-service" --sub "12345" --exp-mins 60
    echo '{"data": "info"}' | python tools/jwt_generator.py -s "secret"
"""

import argparse
import base64
import hashlib
import hmac
import json
import sys
import time

def base64url_encode(data: bytes) -> str:
    """Encode bytes to base64url string (stripping padding and replacing chars)."""
    return base64.urlsafe_b64encode(data).decode('utf-8').rstrip('=')

def generate_jwt(header: dict, payload: dict, secret: str, algorithm: str) -> str:
    """
    Generates a signed JWT using the provided header, payload, secret, and algorithm.
    """
    # 1. Serialize and encode header
    header_json = json.dumps(header, separators=(',', ':')).encode('utf-8')
    header_encoded = base64url_encode(header_json)

    # 2. Serialize and encode payload
    payload_json = json.dumps(payload, separators=(',', ':')).encode('utf-8')
    payload_encoded = base64url_encode(payload_json)

    # 3. Create signature base string
    signing_input = f"{header_encoded}.{payload_encoded}".encode('utf-8')

    # 4. Determine hash algorithm
    hash_algos = {
        'HS256': hashlib.sha256,
        'HS384': hashlib.sha384,
        'HS512': hashlib.sha512
    }
    
    if algorithm not in hash_algos:
        raise ValueError(f"Unsupported algorithm: {algorithm}. Choose HS256, HS384, or HS512.")

    # 5. Sign the signature base using HMAC
    key = secret.encode('utf-8')
    signature = hmac.new(key, signing_input, hash_algos[algorithm]).digest()
    signature_encoded = base64url_encode(signature)

    # 6. Combine
    return f"{header_encoded}.{payload_encoded}.{signature_encoded}"

def main():
    parser = argparse.ArgumentParser(
        description="JWT Generator & Signer - Generate signed JWTs with custom claims (pure Python)."
    )
    
    # Required arguments
    parser.add_argument(
        '-s', '--secret',
        required=True,
        help='Secret key used to sign the JWT'
    )
    
    # Payload options
    parser.add_argument(
        '-p', '--payload',
        help='Raw JSON payload string. If not provided and no other claims are set, reads from stdin.'
    )
    
    # Algorithm options
    parser.add_argument(
        '-a', '--algo',
        default='HS256',
        choices=['HS256', 'HS384', 'HS512'],
        help='HMAC algorithm to use for signing (default: HS256)'
    )
    
    # Quick claim helpers
    parser.add_argument('--iss', help='Issuer (iss claim)')
    parser.add_argument('--sub', help='Subject (sub claim)')
    parser.add_argument('--aud', help='Audience (aud claim)')
    parser.add_argument('--exp-mins', type=float, help='Expiration duration in minutes from now (sets exp claim)')
    parser.add_argument('--nbf-mins', type=float, help='Not Before duration in minutes from now (sets nbf claim)')
    parser.add_argument('--no-iat', action='store_true', help='Do not include default Issued At (iat claim)')
    
    # Header overrides
    parser.add_argument('--kid', help='Key ID (kid) to include in header')
    parser.add_argument('--header-extra', help='Extra header fields as a JSON string')
    
    # Output formatting
    parser.add_argument('-v', '--verbose', action='store_true', help='Print detailed breakdowns along with the token')

    args = parser.parse_args()

    # Build Header
    header = {
        "alg": args.algo,
        "typ": "JWT"
    }
    if args.kid:
        header["kid"] = args.kid
        
    if args.header_extra:
        try:
            extra = json.loads(args.header_extra)
            if isinstance(extra, dict):
                header.update(extra)
            else:
                print("[ERROR] --header-extra must be a valid JSON object.", file=sys.stderr)
                return 1
        except Exception as e:
            print(f"[ERROR] Failed to parse --header-extra JSON: {e}", file=sys.stderr)
            return 1

    # Build Payload
    payload = {}
    
    # Check if we should read from stdin
    if not args.payload and not any([args.iss, args.sub, args.aud, args.exp_mins, args.nbf_mins]):
        if not sys.stdin.isatty():
            try:
                stdin_data = sys.stdin.read().strip()
                if stdin_data:
                    payload = json.loads(stdin_data)
                    if not isinstance(payload, dict):
                        print("[ERROR] Piped input must be a valid JSON object.", file=sys.stderr)
                        return 1
            except Exception as e:
                print(f"[ERROR] Failed to parse JSON from stdin: {e}", file=sys.stderr)
                return 1
        else:
            print("[ERROR] No payload provided. Use -p/--payload or pipe a JSON object to stdin.", file=sys.stderr)
            return 1
    
    # If explicit payload string was provided
    if args.payload:
        try:
            payload = json.loads(args.payload)
            if not isinstance(payload, dict):
                print("[ERROR] --payload must be a valid JSON object.", file=sys.stderr)
                return 1
        except Exception as e:
            print(f"[ERROR] Failed to parse --payload JSON: {e}", file=sys.stderr)
            return 1

    # Apply quick claim helpers
    now = int(time.time())
    if not args.no_iat and 'iat' not in payload:
        payload['iat'] = now

    if args.iss:
        payload['iss'] = args.iss
    if args.sub:
        payload['sub'] = args.sub
    if args.aud:
        payload['aud'] = args.aud
        
    if args.exp_mins is not None:
        payload['exp'] = now + int(args.exp_mins * 60)
    if args.nbf_mins is not None:
        payload['nbf'] = now + int(args.nbf_mins * 60)

    try:
        token = generate_jwt(header, payload, args.secret, args.algo)
    except Exception as e:
        print(f"[ERROR] Token generation failed: {e}", file=sys.stderr)
        return 1

    if args.verbose:
        print("=" * 60)
        print("JWT GENERATOR & SIGNER")
        print("=" * 60)
        print("\n[1] HEADER:")
        print(json.dumps(header, indent=4))
        print("\n[2] PAYLOAD:")
        print(json.dumps(payload, indent=4))
        print("\n[3] GENERATED TOKEN:")
        print("-" * 60)
        print(token)
        print("-" * 60)
    else:
        print(token)

    return 0

if __name__ == '__main__':
    sys.exit(main())
