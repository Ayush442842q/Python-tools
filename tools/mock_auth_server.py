#!/usr/bin/env python3
"""
Mock OIDC & JWKS Authentication Server - A local mock OAuth2 / OpenID Connect Identity Provider.
Generates an RSA keypair on startup and serves OIDC metadata, JWKS public keys, and issues RS256-signed JWTs.

Usage:
    python tools/mock_auth_server.py [--host HOST] [--port PORT]

Example:
    python tools/mock_auth_server.py --port 8080
"""

import argparse
import base64
import hashlib
import hmac
import json
import random
import sys
import time
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

# --- Lightweight RSA Key Generation ---
def is_prime(n, k=5):
    if n < 2: return False
    for p in [2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47]:
        if n == p: return True
        if n % p == 0: return False
    r, s = 0, n - 1
    while s % 2 == 0:
        r += 1
        s //= 2
    for _ in range(k):
        a = random.randint(2, n - 1)
        x = pow(a, s, n)
        if x == 1 or x == n - 1:
            continue
        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                break
        else:
            return False
    return True

def get_prime(bits):
    while True:
        n = random.getrandbits(bits)
        n |= (1 << (bits - 1)) | 1
        if is_prime(n):
            return n

def generate_rsa_keypair(bits=1024):
    print("[*] Generating dynamic cryptographic RSA keys for token signing...")
    t0 = time.time()
    p = get_prime(bits // 2)
    q = get_prime(bits // 2)
    n = p * q
    phi = (p - 1) * (q - 1)
    e = 65537
    
    # Extended Euclidean Algorithm
    def egcd(a, b):
        if a == 0: return (b, 0, 1)
        g, y, x = egcd(b % a, a)
        return (g, x - (b // a) * y, y)
        
    _, x, _ = egcd(e, phi)
    d = x % phi
    print(f"[+] RSA keys generated in {time.time() - t0:.3f} seconds.")
    return n, e, d

# Global keys
RSA_N, RSA_E, RSA_D = generate_rsa_keypair(1024)
KEY_ID = "mock-jwt-signing-key-id-999"

# Helper to base64url encode bytes
def base64url_encode(data):
    if isinstance(data, str):
        data = data.encode('utf-8')
    return base64.urlsafe_b64encode(data).replace(b'=', b'').decode('utf-8')

# Helper to base64url encode large integers (JWK Modulus/Exponent)
def int_to_base64url(val):
    hex_str = format(val, 'x')
    if len(hex_str) % 2 != 0:
        hex_str = '0' + hex_str
    val_bytes = bytes.fromhex(hex_str)
    return base64url_encode(val_bytes)

# --- RS256 JWT Token Issuer ---
def sign_jwt(header, payload, n, d):
    # 1. Prepare unsigned token segment
    header_enc = base64url_encode(json.dumps(header, separators=(',', ':')))
    payload_enc = base64url_encode(json.dumps(payload, separators=(',', ':')))
    unsigned_token = f"{header_enc}.{payload_enc}"
    
    # 2. Hash message
    hashed = hashlib.sha256(unsigned_token.encode('utf-8')).digest()
    
    # 3. PKCS#1 v1.5 padding for 1024-bit key (128 bytes)
    # Header for SHA256: 19 bytes
    sha256_header = b"\x30\x31\x30\x0d\x06\x09\x60\x86\x48\x01\x65\x03\x04\x02\x01\x05\x00\x04\x20"
    # Pad size: 128 - 3 - 19 - 32 = 74
    padded = b"\x00\x01" + (b"\xff" * 74) + b"\x00" + sha256_header + hashed
    
    # 4. Sign using RSA private exponent
    m = int.from_bytes(padded, 'big')
    s = pow(m, d, n)
    sig_bytes = s.to_bytes(128, 'big')
    
    # 5. Build signed token
    return f"{unsigned_token}.{base64url_encode(sig_bytes)}"


class MockAuthHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Format logs cleanly
        print(f"[HTTP] {self.address_string()} - {format % args}")

    def do_GET(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        query = parse_qs(parsed_url.query)
        
        # OIDC Discovery
        if path == "/.well-known/openid-configuration":
            self.send_json_response({
                "issuer": f"http://{self.headers.get('Host', 'localhost:8080')}",
                "authorization_endpoint": f"http://{self.headers.get('Host', 'localhost:8080')}/authorize",
                "token_endpoint": f"http://{self.headers.get('Host', 'localhost:8080')}/token",
                "userinfo_endpoint": f"http://{self.headers.get('Host', 'localhost:8080')}/userinfo",
                "jwks_uri": f"http://{self.headers.get('Host', 'localhost:8080')}/.well-known/jwks.json",
                "response_types_supported": ["code", "token", "id_token"],
                "subject_types_supported": ["public"],
                "id_token_signing_alg_values_supported": ["RS256"],
                "scopes_supported": ["openid", "profile", "email"],
                "token_endpoint_auth_methods_supported": ["client_secret_post", "client_secret_basic"]
            })
            
        # JWKS Endpoint
        elif path == "/.well-known/jwks.json":
            self.send_json_response({
                "keys": [
                    {
                        "kty": "RSA",
                        "alg": "RS256",
                        "use": "sig",
                        "kid": KEY_ID,
                        "n": int_to_base64url(RSA_N),
                        "e": int_to_base64url(RSA_E)
                    }
                ]
            })
            
        # User Info Endpoint
        elif path == "/userinfo":
            # Check Authorization Header
            auth_header = self.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                self.send_response(401)
                self.end_headers()
                self.wfile.write(b"Unauthorized")
                return
            
            self.send_json_response({
                "sub": "mock-user-12345",
                "name": "Jane Doe",
                "given_name": "Jane",
                "family_name": "Doe",
                "email": "jane.doe@example.com",
                "email_verified": True,
                "picture": "https://avatar.iran.liara.run/public/girl"
            })

        # Mock Authorization Endpoint (Consent Page)
        elif path == "/authorize":
            redirect_uri = query.get("redirect_uri", [""])[0]
            state = query.get("state", [""])[0]
            client_id = query.get("client_id", ["mock-client"])[0]
            
            if not redirect_uri:
                self.send_error_response(400, "Missing redirect_uri")
                return
                
            self.send_html_consent_page(client_id, redirect_uri, state)
            
        else:
            self.send_error_response(404, "Not Found")

    def do_POST(self):
        parsed_url = urlparse(self.path)
        path = parsed_url.path
        
        # Token Exchange Endpoint
        if path == "/token":
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            params = parse_qs(post_data)
            
            grant_type = params.get("grant_type", [""])[0]
            client_id = params.get("client_id", ["mock-client"])[0]
            
            # Simple mock token issue
            now = int(time.time())
            header = {
                "alg": "RS256",
                "typ": "JWT",
                "kid": KEY_ID
            }
            
            id_token_payload = {
                "iss": f"http://{self.headers.get('Host', 'localhost:8080')}",
                "sub": "mock-user-12345",
                "aud": client_id,
                "exp": now + 3600,
                "iat": now,
                "auth_time": now - 10,
                "name": "Jane Doe",
                "email": "jane.doe@example.com",
                "email_verified": True
            }
            
            access_token_payload = {
                "iss": f"http://{self.headers.get('Host', 'localhost:8080')}",
                "sub": "mock-user-12345",
                "aud": client_id,
                "exp": now + 3600,
                "iat": now,
                "scope": "openid profile email"
            }
            
            id_token = sign_jwt(header, id_token_payload, RSA_N, RSA_D)
            access_token = sign_jwt(header, access_token_payload, RSA_N, RSA_D)
            
            self.send_json_response({
                "access_token": access_token,
                "token_type": "Bearer",
                "expires_in": 3600,
                "id_token": id_token,
                "scope": "openid profile email",
                "refresh_token": "mock-refresh-token-123456789"
            })
        else:
            self.send_error_response(404, "Not Found")

    def send_json_response(self, data):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode('utf-8'))

    def send_error_response(self, code, message):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"error": message}).encode('utf-8'))

    def send_html_consent_page(self, client_id, redirect_uri, state):
        # Render a beautiful UI for the login screen
        callback_url = f"{redirect_uri}?code=mock-auth-code-777&state={state}"
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Mock Identity Provider - Authorize</title>
    <style>
        :root {{
            --bg-color: #0b0f19;
            --card-bg: rgba(22, 30, 49, 0.7);
            --border-color: rgba(255, 255, 255, 0.08);
            --primary: #4f46e5;
            --primary-hover: #4338ca;
            --text-color: #f3f4f6;
            --text-muted: #9ca3af;
        }}
        body {{
            font-family: -apple-system, sans-serif;
            background-color: var(--bg-color);
            background-image: radial-gradient(circle at 50% 50%, rgba(79, 70, 229, 0.15) 0%, transparent 60%);
            color: var(--text-color);
            margin: 0;
            padding: 20px;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 90vh;
        }}
        .card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            backdrop-filter: blur(16px);
            border-radius: 20px;
            padding: 40px;
            max-width: 420px;
            width: 100%;
            text-align: center;
            box-shadow: 0 10px 30px rgba(0, 0, 0, 0.5);
        }}
        .logo {{
            width: 60px;
            height: 60px;
            background: linear-gradient(135deg, #6366f1, #4f46e5);
            border-radius: 16px;
            margin: 0 auto 20px auto;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            font-size: 1.8rem;
            color: #fff;
            box-shadow: 0 0 15px rgba(99, 102, 241, 0.5);
        }}
        h2 {{
            margin: 0 0 10px 0;
            font-size: 1.5rem;
        }}
        p {{
            color: var(--text-muted);
            font-size: 0.95rem;
            line-height: 1.5;
            margin-bottom: 30px;
        }}
        .user-box {{
            display: flex;
            align-items: center;
            background: rgba(0,0,0,0.2);
            border: 1px solid var(--border-color);
            padding: 12px 16px;
            border-radius: 12px;
            margin-bottom: 30px;
            text-align: left;
        }}
        .avatar {{
            width: 40px;
            height: 40px;
            border-radius: 50%%;
            background: #cbd5e1;
            margin-right: 12px;
        }}
        .user-name {{
            font-weight: 600;
            font-size: 0.95rem;
        }}
        .user-email {{
            font-size: 0.8rem;
            color: var(--text-muted);
        }}
        .btn {{
            display: block;
            width: 100%%;
            background: var(--primary);
            color: #fff;
            padding: 12px 0;
            border: none;
            border-radius: 10px;
            font-weight: 600;
            font-size: 1rem;
            cursor: pointer;
            text-decoration: none;
            transition: background 0.2s;
            box-shadow: 0 4px 12px rgba(79, 70, 229, 0.3);
        }}
        .btn:hover {{
            background: var(--primary-hover);
        }}
        .cancel-btn {{
            display: block;
            margin-top: 15px;
            color: var(--text-muted);
            text-decoration: none;
            font-size: 0.85rem;
            transition: color 0.2s;
        }}
        .cancel-btn:hover {{
            color: var(--text-color);
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="logo">ID</div>
        <h2>Sign In & Authorize</h2>
        <p>Client Application <b>{client_id}</b> is requesting permission to access your profile and email address.</p>
        
        <div class="user-box">
            <img class="avatar" src="https://avatar.iran.liara.run/public/girl" alt="Avatar">
            <div>
                <div class="user-name">Jane Doe</div>
                <div class="user-email">jane.doe@example.com</div>
            </div>
        </div>

        <a class="btn" href="{callback_url}">Accept & Authorize</a>
        <a class="cancel-btn" href="#">Cancel</a>
    </div>
</body>
</html>
"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))


def main():
    parser = argparse.ArgumentParser(description="Mock OIDC / OAuth2 & JWKS server")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind to")
    parser.add_argument("--port", type=int, default=8080, help="Port to listen on")
    args = parser.parse_args()

    server = HTTPServer((args.host, args.port), MockAuthHandler)
    print(f"[*] Mock OIDC Server running on http://{args.host}:{args.port}")
    print(f"[*] Discovery URL: http://{args.host}:{args.port}/.well-known/openid-configuration")
    print(f"[*] JWKS URI:      http://{args.host}:{args.port}/.well-known/jwks.json")
    print("[*] Press Ctrl+C to stop.")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Stopping Mock OIDC Server...")
    finally:
        server.server_close()
    return 0

if __name__ == "__main__":
    sys.exit(main())
