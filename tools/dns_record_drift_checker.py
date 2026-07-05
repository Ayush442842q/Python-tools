#!/usr/bin/env python3
"""
DNS Record Drift & Multi-Resolver Auditor
Queries DNS records (A, AAAA, CNAME, MX, TXT, NS) across multiple DNS-over-HTTPS (DoH) global resolvers
(Cloudflare, Google, Quad9, AdGuard) to detect propagation drift, inconsistent IP answers, or missing records.

Uses only standard Python libraries.
"""

import argparse
import json
import os
import socket
import sys
import urllib.parse
import urllib.request

DOH_RESOLVERS = {
    "Cloudflare": "https://cloudflare-dns.com/dns-query",
    "Google": "https://dns.google/resolve",
    "Quad9": "https://dns.quad9.net:5053/dns-query",
    "AdGuard": "https://dns.adguard-dns.com/resolve"
}

RECORD_TYPES = {"A": 1, "NS": 2, "CNAME": 5, "MX": 15, "TXT": 16, "AAAA": 28}


def query_doh(domain, record_type="A", provider="Cloudflare", timeout=5):
    """
    Query DNS record via DNS-over-HTTPS (DoH) API.
    """
    endpoint = DOH_RESOLVERS.get(provider)
    if not endpoint:
        return {"error": f"Unknown provider {provider}"}

    params = {"name": domain, "type": record_type}
    url = f"{endpoint}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Accept": "application/dns-json", "User-Agent": "DNSDriftChecker/1.0"})

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                answers = []
                if "Answer" in data:
                    for ans in data["Answer"]:
                        answers.append({
                            "name": ans.get("name"),
                            "type": record_type,
                            "ttl": ans.get("TTL"),
                            "data": ans.get("data")
                        })
                return {"status": data.get("Status", 0), "answers": answers}
    except Exception as e:
        return {"error": str(e), "answers": []}

    return {"answers": []}


def query_system_local(domain):
    """Fallback query using local socket resolution for A records."""
    try:
        addrs = socket.getaddrinfo(domain, None)
        ips = sorted(list(set(item[4][0] for item in addrs)))
        return [{"name": domain, "type": "A", "ttl": "N/A", "data": ip} for ip in ips]
    except Exception as e:
        return []


def audit_domain(domain, record_types=None):
    if record_types is None:
        record_types = ["A", "MX", "TXT"]

    results = {}
    
    for rtype in record_types:
        rtype_results = {}
        all_answers_set = set()
        
        for provider in DOH_RESOLVERS.keys():
            res = query_doh(domain, record_type=rtype, provider=provider)
            answers = res.get("answers", [])
            data_list = sorted([a["data"].strip('"') for a in answers if "data" in a])
            
            rtype_results[provider] = {
                "answers": data_list,
                "count": len(data_list),
                "error": res.get("error")
            }
            if data_list:
                all_answers_set.add(tuple(data_list))

        # Check drift condition
        has_drift = len(all_answers_set) > 1
        results[rtype] = {
            "has_drift": has_drift,
            "providers": rtype_results,
            "unique_answer_sets": len(all_answers_set)
        }

    return results


def print_audit_report(domain, audit_results):
    print("=" * 70)
    print(f" DNS RECORD DRIFT & MULTI-RESOLVER AUDIT: {domain}")
    print("=" * 70)

    for rtype, data in audit_results.items():
        drift_status = "DRIFT DETECTED!" if data["has_drift"] else "CONSISTENT"
        print(f"\nRecord Type [{rtype}] - Status: {drift_status}")
        print("-" * 70)
        print(f"{'Provider':<15} {'Count':<7} {'Resolved Records'}")
        print("-" * 70)
        
        for provider, pdata in data["providers"].items():
            if pdata.get("error"):
                records_str = f"[Error: {pdata['error']}]"
            elif pdata["count"] == 0:
                records_str = "[No Records / NXDOMAIN]"
            else:
                records_str = ", ".join(pdata["answers"])
            print(f"{provider:<15} {pdata['count']:<7} {records_str}")

    print("\n" + "=" * 70)


def run_demo():
    print("=== Running DNS Record Drift Checker Demo ===")
    sample_domain = "google.com"
    print(f"Auditing DNS records for '{sample_domain}' across DoH providers...\n")
    audit_res = audit_domain(sample_domain, record_types=["A", "MX"])
    print_audit_report(sample_domain, audit_res)


def main():
    parser = argparse.ArgumentParser(
        description="DNS Record Drift & Multi-Resolver Auditor - Query DNS records across DoH providers to check propagation drift."
    )
    parser.add_argument("domain", nargs="?", help="Domain name to audit (e.g. example.com)")
    parser.add_argument("-t", "--types", default="A,MX,TXT", help="Comma-separated list of record types (A, AAAA, MX, TXT, CNAME, NS)")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--demo", action="store_true", help="Run demonstration")

    args = parser.parse_args()

    if args.demo or not args.domain:
        run_demo()
        return

    rtype_list = [t.strip().upper() for t in args.types.split(",") if t.strip()]
    audit_res = audit_domain(args.domain, record_types=rtype_list)

    if args.json:
        print(json.dumps({args.domain: audit_res}, indent=2))
    else:
        print_report = print_audit_report(args.domain, audit_res)


if __name__ == "__main__":
    main()
