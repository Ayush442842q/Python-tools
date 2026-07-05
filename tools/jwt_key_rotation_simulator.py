#!/usr/bin/env python3
"""
JWT Key Rotation & Key-Ring Verification Simulator

Simulates JWT lifecycle, multi-key verification rings, key transition/rotation,
grace period expiration, and key revocation policies.

Usage:
    python tools/jwt_key_rotation_simulator.py --simulate
    python tools/jwt_key_rotation_simulator.py --token <JWT> --keyset-file keys.json
    python tools/jwt_key_rotation_simulator.py --generate-keyset
"""

import sys
import os
import time
import json
import hmac
import uuid
import hashlib
import base64
import argparse
from typing import Dict, Any, List, Tuple, Optional

# ANSI Colors
COLOR_HEADER = "\033[95m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"


def is_color_enabled() -> bool:
    return sys.stdout.isatty() and os.name != 'nt' or os.getenv('COLORTERM') is not None or os.name == 'nt'


def colorize(text: str, color_code: str) -> str:
    if is_color_enabled():
        return f"{color_code}{text}{COLOR_RESET}"
    return text


def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('utf-8')


def b64url_decode(s: str) -> bytes:
    padding = '=' * (4 - (len(s) % 4))
    return base64.urlsafe_b64decode((s + padding).encode('utf-8'))


def create_token(header: Dict[str, Any], payload: Dict[str, Any], secret: str) -> str:
    """Create a signed HMAC-SHA256 JWT."""
    header_bytes = json.dumps(header, separators=(',', ':')).encode('utf-8')
    payload_bytes = json.dumps(payload, separators=(',', ':')).encode('utf-8')

    encoded_header = b64url_encode(header_bytes)
    encoded_payload = b64url_encode(payload_bytes)

    signing_input = f"{encoded_header}.{encoded_payload}".encode('utf-8')
    signature = hmac.new(secret.encode('utf-8'), signing_input, hashlib.sha256).digest()
    encoded_signature = b64url_encode(signature)

    return f"{encoded_header}.{encoded_payload}.{encoded_signature}"


def verify_token(token: str, key_ring: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Verify JWT against a key ring containing multiple keys with status:
    active, grace_period, retired, revoked.
    """
    parts = token.split(".")
    if len(parts) != 3:
        return {"valid": False, "reason": "Malformed JWT structure (must have 3 parts)"}

    try:
        header_json = json.loads(b64url_decode(parts[0]).decode('utf-8'))
        payload_json = json.loads(b64url_decode(parts[1]).decode('utf-8'))
    except Exception as ex:
        return {"valid": False, "reason": f"Header or Payload decode error: {str(ex)}"}

    alg = header_json.get("alg")
    kid = header_json.get("kid")

    if alg != "HS256":
        return {"valid": False, "reason": f"Unsupported algorithm '{alg}'. Only HS256 supported"}

    if not kid:
        return {"valid": False, "reason": "Missing 'kid' (Key ID) header"}

    # Find matching key in key ring
    matched_key_info = None
    for k in key_ring:
        if k["kid"] == kid:
            matched_key_info = k
            break

    if not matched_key_info:
        return {"valid": False, "reason": f"Unknown Key ID 'kid={kid}' not found in active key ring"}

    status = matched_key_info.get("status", "active")

    if status == "revoked":
        return {
            "valid": False,
            "reason": f"Security Error: Token signed with revoked key 'kid={kid}'",
            "key_status": status
        }

    # Verify signature
    signing_input = f"{parts[0]}.{parts[1]}".encode('utf-8')
    expected_sig = hmac.new(
        matched_key_info["secret"].encode('utf-8'),
        signing_input,
        hashlib.sha256
    ).digest()
    actual_sig = b64url_decode(parts[2])

    if not hmac.compare_digest(expected_sig, actual_sig):
        return {"valid": False, "reason": "Signature verification failed", "key_status": status}

    # Verify time claims
    now = int(time.time())
    exp = payload_json.get("exp")
    if exp and now > exp:
        return {"valid": False, "reason": f"Token expired at exp={exp} (current time {now})", "key_status": status}

    nbf = payload_json.get("nbf")
    if nbf and now < nbf:
        return {"valid": False, "reason": f"Token not valid until nbf={nbf}", "key_status": status}

    return {
        "valid": True,
        "key_id": kid,
        "key_status": status,
        "header": header_json,
        "payload": payload_json,
        "warnings": ["Key is in grace period / retirement schedule"] if status == "grace_period" else []
    }


def generate_sample_keyset() -> List[Dict[str, Any]]:
    return [
        {
            "kid": "key-2026-v2",
            "status": "active",
            "algorithm": "HS256",
            "secret": "super_secret_key_v2_active_2026",
            "created_at": "2026-06-01T00:00:00Z"
        },
        {
            "kid": "key-2026-v1",
            "status": "grace_period",
            "algorithm": "HS256",
            "secret": "previous_secret_key_v1_grace",
            "created_at": "2026-01-01T00:00:00Z"
        },
        {
            "kid": "key-2025-legacy",
            "status": "revoked",
            "algorithm": "HS256",
            "secret": "compromised_legacy_secret_2025",
            "created_at": "2025-01-01T00:00:00Z"
        }
    ]


def run_rotation_simulation() -> Dict[str, Any]:
    key_ring = generate_sample_keyset()
    results = []

    now = int(time.time())

    # Case 1: Active Key
    t1 = create_token(
        {"alg": "HS256", "typ": "JWT", "kid": "key-2026-v2"},
        {"sub": "user_123", "name": "Alice", "iat": now, "exp": now + 3600},
        "super_secret_key_v2_active_2026"
    )
    v1 = verify_token(t1, key_ring)
    results.append({"scenario": "Token signed with active primary key (v2)", "token": t1, "verification": v1})

    # Case 2: Grace Period Key (older key during migration)
    t2 = create_token(
        {"alg": "HS256", "typ": "JWT", "kid": "key-2026-v1"},
        {"sub": "user_456", "name": "Bob", "iat": now, "exp": now + 3600},
        "previous_secret_key_v1_grace"
    )
    v2 = verify_token(t2, key_ring)
    results.append({"scenario": "Token signed with key in grace period (v1)", "token": t2, "verification": v2})

    # Case 3: Revoked Key
    t3 = create_token(
        {"alg": "HS256", "typ": "JWT", "kid": "key-2025-legacy"},
        {"sub": "user_789", "name": "Eve", "iat": now, "exp": now + 3600},
        "compromised_legacy_secret_2025"
    )
    v3 = verify_token(t3, key_ring)
    results.append({"scenario": "Token signed with revoked key (2025-legacy)", "token": t3, "verification": v3})

    # Case 4: Key ID not in ring
    t4 = create_token(
        {"alg": "HS256", "typ": "JWT", "kid": "unknown-kid-999"},
        {"sub": "user_000", "iat": now, "exp": now + 3600},
        "unknown_secret"
    )
    v4 = verify_token(t4, key_ring)
    results.append({"scenario": "Token signed with unknown key ID", "token": t4, "verification": v4})

    return {
        "key_ring": key_ring,
        "scenarios": results
    }


def print_simulation_report(sim_data: Dict[str, Any]):
    print("=" * 72)
    print(colorize("  JWT Key Rotation & Key-Ring Verification Simulation", COLOR_BOLD + COLOR_HEADER))
    print("=" * 72)

    print(f"\n[{colorize('KEY RING', COLOR_CYAN)}] Active Key Ring:")
    for k in sim_data["key_ring"]:
        st = k["status"]
        color = COLOR_GREEN if st == "active" else (COLOR_YELLOW if st == "grace_period" else COLOR_RED)
        print(f"  • kid='{colorize(k['kid'], COLOR_BOLD)}' | Status={colorize(st.upper(), color)} | Alg={k['algorithm']}")

    print("\n" + "-" * 72)
    print(colorize("  Key Rotation Scenario Test Results:", COLOR_BOLD))
    print("-" * 72)

    for i, sc in enumerate(sim_data["scenarios"], start=1):
        v = sc["verification"]
        is_ok = v["valid"]
        status_tag = colorize("[ACCEPTED]", COLOR_GREEN) if is_ok else colorize("[REJECTED]", COLOR_RED)
        print(f"\nScenario {i}: {colorize(sc['scenario'], COLOR_BOLD)}")
        print(f"  Result: {status_tag}")
        if is_ok:
            print(f"  Key ID:     {v.get('key_id')} (Status: {v.get('key_status')})")
            print(f"  Subject:    {v.get('payload', {}).get('sub')}")
            if v.get("warnings"):
                print(f"  Warning:    {colorize(v['warnings'][0], COLOR_YELLOW)}")
        else:
            print(f"  Reason:     {colorize(v.get('reason', 'Unknown failure'), COLOR_RED)}")

    print("\n" + "=" * 72 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Simulate JWT key rotation, key-ring validation, and grace period handling."
    )
    parser.add_argument("--simulate", action="store_true", help="Run full key rotation simulation scenarios")
    parser.add_argument("--generate-keyset", action="store_true", help="Output a sample JSON Key Set configuration")
    parser.add_argument("--token", help="Single JWT string to verify against key ring")
    parser.add_argument("--keyset-file", help="JSON file containing list of keys for verification")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    args = parser.parse_args()

    if args.generate_keyset:
        print(json.dumps(generate_sample_keyset(), indent=2))
        sys.exit(0)

    if args.token and args.keyset_file:
        with open(args.keyset_file, "r") as f:
            keyset = json.load(f)
        res = verify_token(args.token, keyset)
        if args.json:
            print(json.dumps(res, indent=2))
        else:
            print(f"Valid: {res['valid']}, Details: {res}")
        sys.exit(0 if res["valid"] else 1)

    # Default to simulation mode
    sim_data = run_rotation_simulation()
    if args.json:
        print(json.dumps(sim_data, indent=2))
    else:
        print_simulation_report(sim_data)

    sys.exit(0)


if __name__ == "__main__":
    main()
