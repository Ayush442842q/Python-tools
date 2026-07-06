#!/usr/bin/env python3
"""
JWT Claim Diff Analyzer
Decodes and compares two JSON Web Tokens (JWTs) or token payloads.
Identifies header mismatches, claim drift, security algorithm changes, lifetime variations, and risk flags.
"""

import sys
import os
import json
import base64
import datetime
import argparse
from typing import Dict, Any, Tuple, List, Optional

# Console colors
COLOR_RESET = "\033[0m"
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"


def base64url_decode(segment: str) -> Dict[str, Any]:
    """Decodes a base64url-encoded JWT segment into a Python dictionary."""
    rem = len(segment) % 4
    if rem > 0:
        segment += "=" * (4 - rem)
    # Convert base64url to standard base64
    base64_str = segment.replace("-", "+").replace("_", "/")
    decoded_bytes = base64.b64decode(base64_str)
    return json.loads(decoded_bytes.decode("utf-8"))


def parse_jwt(token: str) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
    """Parses a JWT string into header, payload, and signature string."""
    parts = token.strip().split(".")
    if len(parts) == 3:
        header = base64url_decode(parts[0])
        payload = base64url_decode(parts[1])
        signature = parts[2]
        return header, payload, signature
    elif len(parts) == 1:
        # Assume input is a raw JSON payload string
        payload = json.loads(token)
        return {"alg": "UNKNOWN", "typ": "JWT"}, payload, ""
    else:
        raise ValueError("Invalid JWT token format. Must contain 3 dot-separated segments.")


def format_timestamp(ts: Optional[Any]) -> str:
    """Formats epoch timestamp into ISO format."""
    if isinstance(ts, (int, float)):
        try:
            dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc)
            return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
        except Exception:
            return str(ts)
    return str(ts)


def analyze_diff(
    header1: Dict[str, Any], payload1: Dict[str, Any],
    header2: Dict[str, Any], payload2: Dict[str, Any]
) -> Dict[str, Any]:
    """Analyzes differences between two decoded JWTs."""
    header_diff: Dict[str, Any] = {}
    all_header_keys = sorted(list(set(header1.keys()) | set(header2.keys())))
    for k in all_header_keys:
        val1 = header1.get(k)
        val2 = header2.get(k)
        if val1 != val2:
            header_diff[k] = {"token1": val1, "token2": val2}

    payload_diff: Dict[str, Any] = {}
    all_payload_keys = sorted(list(set(payload1.keys()) | set(payload2.keys())))
    for k in all_payload_keys:
        val1 = payload1.get(k)
        val2 = payload2.get(k)
        if val1 != val2:
            payload_diff[k] = {"token1": val1, "token2": val2}

    security_flags: List[str] = []

    # Check algorithm changes
    alg1 = header1.get("alg")
    alg2 = header2.get("alg")
    if alg1 != alg2:
        if str(alg2).lower() == "none":
            security_flags.append("CRITICAL: Token 2 algorithm downgraded to 'none'!")
        elif str(alg1).startswith("RS") and str(alg2).startswith("HS"):
            security_flags.append("WARNING: Algorithm changed from asymmetric (RS) to symmetric (HS). Risk of key confusion.")

    # Check expiration differences
    exp1 = payload1.get("exp")
    exp2 = payload2.get("exp")
    if exp1 and exp2 and isinstance(exp1, (int, float)) and isinstance(exp2, (int, float)):
        life1 = exp1 - payload1.get("iat", exp1)
        life2 = exp2 - payload2.get("iat", exp2)
        if life2 > life1 + 86400:
            security_flags.append(f"WARNING: Token 2 lifetime is significantly longer ({life2/86400:.1f} days vs {life1/86400:.1f} days).")

    # Check elevated permissions
    roles1 = str(payload1.get("role") or payload1.get("roles") or "")
    roles2 = str(payload2.get("role") or payload2.get("roles") or "")
    if "admin" not in roles1.lower() and "admin" in roles2.lower():
        security_flags.append("INFO: Token 2 has elevated 'admin' role/permission.")

    return {
        "header_diff": header_diff,
        "payload_diff": payload_diff,
        "security_flags": security_flags
    }


def run_demo() -> None:
    """Runs demonstration mode with two sample JWT tokens."""
    print(f"{COLOR_BOLD}{COLOR_CYAN}=== JWT Claim Diff Analyzer Demo ==={COLOR_RESET}\n")

    # Sample JWT Token 1 (Standard User, RS256)
    h1 = base64.b64encode(json.dumps({"alg": "RS256", "typ": "JWT", "kid": "key-2026-v1"}).encode()).decode().rstrip("=")
    p1 = base64.b64encode(json.dumps({
        "sub": "user_12345",
        "name": "Alice Smith",
        "role": "developer",
        "iss": "https://auth.company.com",
        "aud": "api.company.com",
        "iat": 1770000000,
        "exp": 1770003600
    }).encode()).decode().rstrip("=")
    token1 = f"{h1}.{p1}.dummy_signature_1"

    # Sample JWT Token 2 (Elevated Admin User, HS256, Extended Exp)
    h2 = base64.b64encode(json.dumps({"alg": "HS256", "typ": "JWT", "kid": "key-2026-v2"}).encode()).decode().rstrip("=")
    p2 = base64.b64encode(json.dumps({
        "sub": "user_12345",
        "name": "Alice Smith",
        "role": "admin",
        "scope": "read write admin:*",
        "iss": "https://auth.company.com",
        "aud": "api.company.com",
        "iat": 1770000000,
        "exp": 1770604800
    }).encode()).decode().rstrip("=")
    token2 = f"{h2}.{p2}.dummy_signature_2"

    print(f"{COLOR_BOLD}Token 1:{COLOR_RESET} RS256 Standard User Token")
    print(f"{COLOR_BOLD}Token 2:{COLOR_RESET} HS256 Admin User Token\n")

    hdr1, pay1, _ = parse_jwt(token1)
    hdr2, pay2, _ = parse_jwt(token2)

    diff_result = analyze_diff(hdr1, pay1, hdr2, pay2)

    print(f"{COLOR_BOLD}{COLOR_GREEN}--- Header Differences ---{COLOR_RESET}")
    for k, v in diff_result["header_diff"].items():
        print(f"  {COLOR_BOLD}{k:<10}{COLOR_RESET}: Token 1 = '{v['token1']}' | Token 2 = '{v['token2']}'")
    print()

    print(f"{COLOR_BOLD}{COLOR_GREEN}--- Payload Claim Differences ---{COLOR_RESET}")
    for k, v in diff_result["payload_diff"].items():
        val1_str = format_timestamp(v['token1']) if k in ('exp', 'iat', 'nbf') else str(v['token1'])
        val2_str = format_timestamp(v['token2']) if k in ('exp', 'iat', 'nbf') else str(v['token2'])
        print(f"  {COLOR_BOLD}{k:<10}{COLOR_RESET}: Token 1 = {val1_str} | Token 2 = {val2_str}")
    print()

    if diff_result["security_flags"]:
        print(f"{COLOR_BOLD}{COLOR_YELLOW}--- Security Risk Diagnostics ---{COLOR_RESET}")
        for flag in diff_result["security_flags"]:
            print(f"  • {flag}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Decodes and compares two JSON Web Tokens (JWTs) or token payloads."
    )
    parser.add_argument("-t1", "--token1", help="First JWT token string or JSON payload file/string")
    parser.add_argument("-t2", "--token2", help="Second JWT token string or JSON payload file/string")
    parser.add_argument("--json", action="store_true", help="Output raw diff in JSON format")
    parser.add_argument("--demo", action="store_true", help="Run self-contained demonstration mode")

    args = parser.parse_args()

    if args.demo or not (args.token1 and args.token2):
        if not args.demo:
            print(f"{COLOR_YELLOW}Missing tokens. Running demo mode...{COLOR_RESET}\n")
        run_demo()
        return

    try:
        t1_str = open(args.token1, "r").read() if os.path.exists(args.token1) else args.token1
        t2_str = open(args.token2, "r").read() if os.path.exists(args.token2) else args.token2

        h1, p1, _ = parse_jwt(t1_str)
        h2, p2, _ = parse_jwt(t2_str)

        diff = analyze_diff(h1, p1, h2, p2)

        if args.json:
            print(json.dumps(diff, indent=2))
        else:
            print(f"{COLOR_BOLD}{COLOR_GREEN}=== JWT Claim Differences ==={COLOR_RESET}\n")
            print(f"{COLOR_BOLD}Header Differences:{COLOR_RESET}")
            for k, v in diff["header_diff"].items():
                print(f"  {k}: Token 1 = '{v['token1']}' | Token 2 = '{v['token2']}'")
            print(f"\n{COLOR_BOLD}Payload Differences:{COLOR_RESET}")
            for k, v in diff["payload_diff"].items():
                print(f"  {k}: Token 1 = '{v['token1']}' | Token 2 = '{v['token2']}'")
            if diff["security_flags"]:
                print(f"\n{COLOR_BOLD}{COLOR_YELLOW}Security Risk Diagnostics:{COLOR_RESET}")
                for f in diff["security_flags"]:
                    print(f"  • {f}")

    except Exception as e:
        print(f"{COLOR_RED}Error analyzing JWTs: {e}{COLOR_RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
