#!/usr/bin/env python3
"""
JWKS Generator & Inspector - Generate and inspect JSON Web Key Sets (JWKS) for OAuth2/OIDC.
"""

import sys
import json
import base64
import argparse
import hashlib
from datetime import datetime

# Try importing cryptography, fail gracefully with installation instructions
try:
    from cryptography.hazmat.primitives.asymmetric import rsa, ec
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend
    HAS_CRYPTOGRAPHY = True
except ImportError:
    HAS_CRYPTOGRAPHY = False

# ANSI colors
def get_color(color_name):
    colors = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'bold': '\033[1m',
        'reset': '\033[0m'
    }
    if sys.platform == 'win32':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            return ''
    return colors.get(color_name, '')

def bytes_to_b64url(b: bytes) -> str:
    """Encode bytes to base64url string without padding."""
    return base64.urlsafe_b64encode(b).rstrip(b'=').decode('ascii')

def int_to_b64url(val: int) -> str:
    """Convert integer to minimum-byte big-endian representation and encode to base64url."""
    if val == 0:
        return bytes_to_b64url(b'\x00')
    # Calculate byte length
    byte_len = (val.bit_length() + 7) // 8
    b = val.to_bytes(byte_len, byteorder='big')
    return bytes_to_b64url(b)

def generate_key_id(public_bytes: bytes) -> str:
    """Generate a stable key ID (kid) based on public key bytes sha256 hash."""
    return hashlib.sha256(public_bytes).hexdigest()[:16]

def rsa_to_jwk(pub_key, kid=None, use="sig", alg="RS256") -> dict:
    """Convert an RSA public key object to JWK dictionary."""
    numbers = pub_key.public_numbers()
    n = int_to_b64url(numbers.n)
    e = int_to_b64url(numbers.e)
    
    # Generate stable kid if not provided
    if not kid:
        der = pub_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        kid = generate_key_id(der)

    return {
        "kty": "RSA",
        "use": use,
        "alg": alg,
        "kid": kid,
        "n": n,
        "e": e
    }

def ec_to_jwk(pub_key, kid=None, use="sig", alg=None) -> dict:
    """Convert an EC public key object to JWK dictionary."""
    numbers = pub_key.public_numbers()
    curve_name = pub_key.curve.name
    
    # Map curve to standard names and algorithms
    curve_map = {
        "secp256r1": ("P-256", "ES256"),
        "secp384r1": ("P-384", "ES384"),
        "secp521r1": ("P-521", "ES512"),
    }
    
    crv, default_alg = curve_map.get(curve_name, (curve_name, "ES256"))
    if not alg:
        alg = default_alg

    # Get coordinate bytes
    # Coordinates must be zero-padded to key size
    key_size_bytes = (pub_key.key_size + 7) // 8
    x_bytes = numbers.x.to_bytes(key_size_bytes, byteorder='big')
    y_bytes = numbers.y.to_bytes(key_size_bytes, byteorder='big')
    
    x = bytes_to_b64url(x_bytes)
    y = bytes_to_b64url(y_bytes)

    if not kid:
        der = pub_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        kid = generate_key_id(der)

    return {
        "kty": "EC",
        "use": use,
        "alg": alg,
        "kid": kid,
        "crv": crv,
        "x": x,
        "y": y
    }

def inspect_jwks(jwks_data: dict, colors: dict):
    """Pretty-print JWKS keys information."""
    keys = jwks_data.get("keys", [])
    if not keys:
        print(f"{colors['yellow']}No keys found in JWKS.{colors['reset']}")
        return
        
    print(f"\n{colors['bold']}{colors['blue']}=== JWKS Keys Inspector ({len(keys)} key(s) found) ==={colors['reset']}")
    for i, key in enumerate(keys, 1):
        kid = key.get("kid", "N/A")
        kty = key.get("kty", "N/A")
        alg = key.get("alg", "N/A")
        use = key.get("use", "N/A")
        
        print(f"\n{colors['bold']}Key #{i}:{colors['reset']}")
        print(f"  {colors['bold']}Key ID (kid):{colors['reset']} {colors['green']}{kid}{colors['reset']}")
        print(f"  {colors['bold']}Key Type (kty):{colors['reset']} {kty}")
        print(f"  {colors['bold']}Algorithm (alg):{colors['reset']} {colors['yellow']}{alg}{colors['reset']}")
        print(f"  {colors['bold']}Key Use (use):{colors['reset']} {use}")
        
        if kty == "RSA":
            n = key.get("n", "")
            # Estimate bit size from base64 length of modulus
            n_decoded = base64.urlsafe_b64decode(n + "==")
            bit_size = len(n_decoded) * 8
            print(f"  {colors['bold']}Modulus Size:{colors['reset']} {bit_size} bits")
            print(f"  {colors['bold']}Exponent (e):{colors['reset']} {key.get('e', 'N/A')}")
        elif kty == "EC":
            print(f"  {colors['bold']}Curve (crv):{colors['reset']} {key.get('crv', 'N/A')}")
            print(f"  {colors['bold']}Coordinates (x, y):{colors['reset']} x={key.get('x')[:10]}... y={key.get('y')[:10]}...")
        elif kty == "oct":
            print(f"  {colors['bold']}Symmetric Key (oct):{colors['reset']} Hidden")
        else:
            print(f"  {colors['bold']}Details:{colors['reset']} Unknown kty details")

def main():
    parser = argparse.ArgumentParser(
        description="JWKS Generator & Inspector - Generate RSA/EC keys, output JWKS, or inspect JWKS files."
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Subcommand to execute")
    
    # Generate subcommand
    gen_parser = subparsers.add_parser("generate", help="Generate a new key pair and output JWK/JWKS")
    gen_parser.add_argument("--kty", choices=["RSA", "EC"], default="RSA", help="Key type (default: RSA)")
    gen_parser.add_argument("--size", type=int, default=2048, help="RSA key size in bits (1024, 2048, 4096; default: 2048)")
    gen_parser.add_argument("--curve", choices=["P-256", "P-384", "P-521"], default="P-256", help="EC Curve (default: P-256)")
    gen_parser.add_argument("--kid", help="Optional key ID (kid). If omitted, a stable ID is derived from key bytes.")
    gen_parser.add_argument("--use", choices=["sig", "enc"], default="sig", help="Key usage: sig (signature) or enc (encryption) (default: sig)")
    gen_parser.add_argument("--alg", help="Override JWT algorithm header (e.g. RS256, RS512, ES256, ES384)")
    gen_parser.add_argument("--out-private", help="Save private key PEM to this file path")
    gen_parser.add_argument("--out-public", help="Save public key PEM to this file path")
    gen_parser.add_argument("--out-jwks", help="Save JWKS JSON to this file path")

    # Import PEM subcommand
    import_parser = subparsers.add_parser("import", help="Convert an existing public or private PEM key to JWK/JWKS")
    import_parser.add_argument("pem_file", help="Path to PEM file (public or private key)")
    import_parser.add_argument("--kid", help="Optional key ID (kid). If omitted, a stable ID is derived from key bytes.")
    import_parser.add_argument("--use", choices=["sig", "enc"], default="sig", help="Key usage: sig or enc (default: sig)")
    import_parser.add_argument("--alg", help="Override JWT algorithm header")
    import_parser.add_argument("--out-jwks", help="Save JWKS JSON to this file path")

    # Inspect subcommand
    inspect_parser = subparsers.add_parser("inspect", help="Inspect an existing JWKS file or URL")
    inspect_parser.add_argument("source", help="Path to JWKS JSON file, or HTTP/HTTPS URL, or '-' to read from stdin")

    args = parser.parse_args()
    
    colors = {
        'red': get_color('red'),
        'green': get_color('green'),
        'yellow': get_color('yellow'),
        'blue': get_color('blue'),
        'bold': get_color('bold'),
        'reset': get_color('reset')
    }

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Inspect source command (does not strictly require cryptography if inspecting basic JSON)
    if args.command == "inspect":
        source = args.source
        jwks_content = ""
        
        try:
            if source == "-":
                jwks_content = sys.stdin.read()
            elif source.startswith("http://") or source.startswith("https://"):
                import urllib.request
                with urllib.request.urlopen(source, timeout=10) as response:
                    jwks_content = response.read().decode('utf-8')
            else:
                with open(source, "r", encoding="utf-8") as f:
                    jwks_content = f.read()
                    
            jwks_data = json.loads(jwks_content)
            # Standardize single JWK to JWKS format
            if "keys" not in jwks_data and "kty" in jwks_data:
                jwks_data = {"keys": [jwks_data]}
                
            inspect_jwks(jwks_data, colors)
        except Exception as e:
            print(f"{colors['red']}Error inspecting JWKS source '{source}': {e}{colors['reset']}", file=sys.stderr)
            sys.exit(1)
        sys.exit(0)

    # Subcommands below require cryptography
    if not HAS_CRYPTOGRAPHY:
        print(f"{colors['red']}Error: 'cryptography' library is required for key generation and imports.{colors['reset']}", file=sys.stderr)
        print(f"Please install it using: {colors['bold']}pip install cryptography{colors['reset']}", file=sys.stderr)
        sys.exit(1)

    if args.command == "generate":
        try:
            if args.kty == "RSA":
                print(f"Generating RSA private key ({args.size} bits)...", file=sys.stderr)
                priv_key = rsa.generate_private_key(
                    public_exponent=65537,
                    key_size=args.size,
                    backend=default_backend()
                )
                pub_key = priv_key.public_key()
                alg = args.alg or "RS256"
                jwk = rsa_to_jwk(pub_key, kid=args.kid, use=args.use, alg=alg)
            else:  # EC
                curve_class = {"P-256": ec.SECP256R1, "P-384": ec.SECP384R1, "P-521": ec.SECP521R1}.get(args.curve)
                print(f"Generating EC private key ({args.curve})...", file=sys.stderr)
                priv_key = ec.generate_private_key(curve_class(), backend=default_backend())
                pub_key = priv_key.public_key()
                jwk = ec_to_jwk(pub_key, kid=args.kid, use=args.use, alg=args.alg)

            # Format private/public PEMs
            private_pem = priv_key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption()
            )
            public_pem = pub_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )

            jwks = {"keys": [jwk]}
            jwks_json = json.dumps(jwks, indent=2)

            # Write outputs if requested
            if args.out_private:
                with open(args.out_private, "wb") as f:
                    f.write(private_pem)
                print(f"Saved private key to: {args.out_private}", file=sys.stderr)
            if args.out_public:
                with open(args.out_public, "wb") as f:
                    f.write(public_pem)
                print(f"Saved public key to: {args.out_public}", file=sys.stderr)
            if args.out_jwks:
                with open(args.out_jwks, "w", encoding="utf-8") as f:
                    f.write(jwks_json)
                print(f"Saved JWKS to: {args.out_jwks}", file=sys.stderr)

            # If no file outputs specified, print everything to stdout
            if not (args.out_private or args.out_public or args.out_jwks):
                print(f"\n{colors['bold']}# PRIVATE KEY (PEM):{colors['reset']}")
                print(private_pem.decode('ascii'))
                print(f"{colors['bold']}# PUBLIC KEY (PEM):{colors['reset']}")
                print(public_pem.decode('ascii'))
                print(f"{colors['bold']}# JWKS JSON:{colors['reset']}")
                print(jwks_json)

        except Exception as e:
            print(f"{colors['red']}Key generation failed: {e}{colors['reset']}", file=sys.stderr)
            sys.exit(1)

    elif args.command == "import":
        try:
            with open(args.pem_file, "rb") as f:
                pem_data = f.read()

            # Attempt to parse as private key first, then public key
            pub_key = None
            try:
                priv_key = serialization.load_pem_private_key(pem_data, password=None, backend=default_backend())
                pub_key = priv_key.public_key()
            except ValueError:
                try:
                    pub_key = serialization.load_pem_public_key(pem_data, backend=default_backend())
                except Exception as ex:
                    raise ValueError(f"Could not load PEM file as private or public key: {ex}")

            if isinstance(pub_key, rsa.RSAPublicKey):
                alg = args.alg or "RS256"
                jwk = rsa_to_jwk(pub_key, kid=args.kid, use=args.use, alg=alg)
            elif isinstance(pub_key, ec.EllipticCurvePublicKey):
                jwk = ec_to_jwk(pub_key, kid=args.kid, use=args.use, alg=args.alg)
            else:
                raise TypeError("Unsupported key type. Only RSA and EC keys are supported.")

            jwks = {"keys": [jwk]}
            jwks_json = json.dumps(jwks, indent=2)

            if args.out_jwks:
                with open(args.out_jwks, "w", encoding="utf-8") as f:
                    f.write(jwks_json)
                print(f"Saved JWKS to: {args.out_jwks}", file=sys.stderr)
            else:
                print(jwks_json)

        except Exception as e:
            print(f"{colors['red']}Import failed: {e}{colors['reset']}", file=sys.stderr)
            sys.exit(1)

if __name__ == '__main__':
    main()
