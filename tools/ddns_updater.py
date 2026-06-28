#!/usr/bin/env python3
"""
Dynamic DNS (DDNS) Update Client
Monitors the public IP of the machine and updates DNS records on public providers
(Cloudflare, DuckDNS) or invokes custom webhooks.
"""

import os
import sys
import time
import json
import urllib.request
import urllib.parse
import argparse

IP_CHECK_SERVICES = [
    "https://api.ipify.org",
    "https://ifconfig.me/ip",
    "https://icanhazip.com",
    "https://ipinfo.io/ip"
]

CACHE_FILE_NAME = ".ddns_ip.cache"

def get_public_ip():
    """Gets the public IP of the machine with failover across multiple check services."""
    for service in IP_CHECK_SERVICES:
        try:
            req = urllib.request.Request(
                service, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) DDNS Client'}
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                ip = response.read().decode('utf-8').strip()
                # Basic validation for IP format
                if len(ip.split('.')) == 4 or len(ip.split(':')) >= 3:
                    return ip
        except Exception as e:
            print(f"[-] Check service {service} failed: {e}", file=sys.stderr)
            continue
    raise RuntimeError("Failed to retrieve public IP address from all check services")


def load_cached_ip(cache_path):
    if os.path.exists(cache_path):
        try:
            with open(cache_path, 'r') as f:
                return f.read().strip()
        except Exception:
            pass
    return None


def save_cached_ip(cache_path, ip):
    try:
        with open(cache_path, 'w') as f:
            f.write(ip)
    except Exception as e:
        print(f"[-] Failed to write to cache file: {e}", file=sys.stderr)


def update_duckdns(domain, token, ip):
    print(f"[*] Updating DuckDNS domain '{domain}' with IP {ip}...")
    url = f"https://www.duckdns.org/update?domains={domain}&token={token}&ip={ip}"
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'DDNS Client'})
        with urllib.request.urlopen(req, timeout=10) as response:
            res = response.read().decode('utf-8').strip()
            if res == "OK":
                print("[+] DuckDNS update successful!")
                return True
            else:
                print(f"[-] DuckDNS update failed. Response: {res}", file=sys.stderr)
                return False
    except Exception as e:
        print(f"[-] Error updating DuckDNS: {e}", file=sys.stderr)
        return False


def update_cloudflare(zone_id, token, record_name, ip):
    print(f"[*] Updating Cloudflare record '{record_name}' in zone '{zone_id}' with IP {ip}...")
    
    # 1. Fetch record ID first
    list_url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records?name={record_name}&type=A"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    try:
        # Request DNS Record info
        req = urllib.request.Request(list_url, headers=headers, method="GET")
        with urllib.request.urlopen(req, timeout=10) as response:
            data = json.loads(response.read().decode('utf-8'))
            if not data.get("success"):
                errors = data.get("errors", [])
                print(f"[-] Cloudflare API list record failed: {errors}", file=sys.stderr)
                return False
            
            results = data.get("result", [])
            if not results:
                print(f"[-] Cloudflare record '{record_name}' of type A not found in zone.", file=sys.stderr)
                return False
            
            record_id = results[0]["id"]
            current_ip = results[0]["content"]
            proxied = results[0].get("proxied", False)

        if current_ip == ip:
            print("[+] Cloudflare record matches current IP. No update needed.")
            return True

        # 2. Update record
        update_url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records/{record_id}"
        payload = {
            "type": "A",
            "name": record_name,
            "content": ip,
            "ttl": 1, # Auto TTL
            "proxied": proxied
        }
        
        req_update = urllib.request.Request(
            update_url, 
            data=json.dumps(payload).encode('utf-8'),
            headers=headers,
            method="PUT"
        )
        
        with urllib.request.urlopen(req_update, timeout=10) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            if res_data.get("success"):
                print("[+] Cloudflare DNS record updated successfully!")
                return True
            else:
                print(f"[-] Cloudflare record update failed: {res_data.get('errors')}", file=sys.stderr)
                return False
                
    except Exception as e:
        print(f"[-] Error calling Cloudflare API: {e}", file=sys.stderr)
        return False


def update_webhook(webhook_url, ip, extra_data=None):
    print(f"[*] Invoking custom webhook {webhook_url}...")
    payload = {
        "ip": ip,
        "timestamp": int(time.time()),
        "event": "ddns_update"
    }
    if extra_data:
        payload.update(extra_data)
        
    try:
        req = urllib.request.Request(
            webhook_url,
            data=json.dumps(payload).encode('utf-8'),
            headers={"Content-Type": "application/json", "User-Agent": "DDNS Client"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            code = response.getcode()
            print(f"[+] Webhook invoked. Server responded with HTTP status {code}")
            return 200 <= code < 300
    except Exception as e:
        print(f"[-] Error invoking webhook: {e}", file=sys.stderr)
        return False


def run_ddns_update(config, cache_path, force=False):
    try:
        ip = get_public_ip()
    except RuntimeError as re:
        print(f"[-] Error: {re}", file=sys.stderr)
        return False

    cached_ip = load_cached_ip(cache_path)
    if cached_ip == ip and not force:
        print(f"[*] IP address has not changed: {ip}. Skipping updates.")
        return True

    print(f"[+] IP address changed from {cached_ip or 'None'} to {ip}")
    success = False
    
    provider = config.get("provider")
    if provider == "duckdns":
        domain = config.get("duckdns_domain")
        token = config.get("duckdns_token")
        if not domain or not token:
            print("[-] Error: Missing duckdns_domain or duckdns_token in configuration.", file=sys.stderr)
            return False
        success = update_duckdns(domain, token, ip)
        
    elif provider == "cloudflare":
        zone_id = config.get("cloudflare_zone_id")
        token = config.get("cloudflare_token")
        record_name = config.get("cloudflare_record_name")
        if not zone_id or not token or not record_name:
            print("[-] Error: Missing Cloudflare zone_id, token, or record_name in configuration.", file=sys.stderr)
            return False
        success = update_cloudflare(zone_id, token, record_name, ip)
        
    elif provider == "webhook":
        url = config.get("webhook_url")
        if not url:
            print("[-] Error: Missing webhook_url in configuration.", file=sys.stderr)
            return False
        success = update_webhook(url, ip, config.get("webhook_extra_data"))
    else:
        print(f"[-] Error: Unknown provider '{provider}' configured.", file=sys.stderr)
        return False

    if success:
        save_cached_ip(cache_path, ip)
        return True
    return False


def main():
    parser = argparse.ArgumentParser(description="Zero-dependency Dynamic DNS Update Client")
    parser.add_argument("--config", help="Path to config JSON file")
    parser.add_argument("--provider", choices=["duckdns", "cloudflare", "webhook"], help="DNS Provider")
    parser.add_argument("--force", action="store_true", help="Force update even if cached IP matches")
    parser.add_argument("--daemon", action="store_true", help="Run in a background check loop (daemon)")
    parser.add_argument("--interval", type=int, default=300, help="Check interval in seconds for daemon mode (default: 300s)")
    parser.add_argument("--cache", help="Custom path for IP cache file")
    
    # Provider options
    parser.add_argument("--duckdns-domain", help="DuckDNS domain name")
    parser.add_argument("--duckdns-token", help="DuckDNS API Token")
    parser.add_argument("--cf-zone", help="Cloudflare Zone ID")
    parser.add_argument("--cf-token", help="Cloudflare Bearer Token")
    parser.add_argument("--cf-record", help="Cloudflare A-record name (e.g. sub.mydomain.com)")
    parser.add_argument("--webhook-url", help="Webhook POST URL")

    args = parser.parse_args()

    config = {}
    if args.config:
        try:
            with open(args.config, 'r') as f:
                config = json.load(f)
        except Exception as e:
            print(f"[-] Failed to load config file: {e}", file=sys.stderr)
            sys.exit(1)

    # CLI overrides
    if args.provider: config["provider"] = args.provider
    if args.duckdns_domain: config["duckdns_domain"] = args.duckdns_domain
    if args.duckdns_token: config["duckdns_token"] = args.duckdns_token
    if args.cf_zone: config["cloudflare_zone_id"] = args.cf_zone
    if args.cf_token: config["cloudflare_token"] = args.cf_token
    if args.cf_record: config["cloudflare_record_name"] = args.cf_record
    if args.webhook_url: config["webhook_url"] = args.webhook_url

    if not config.get("provider"):
        print("[-] Error: No provider specified. Use --provider or a configuration file.", file=sys.stderr)
        parser.print_help()
        sys.exit(1)

    cache_path = args.cache or os.path.join(os.path.dirname(os.path.abspath(__file__)), CACHE_FILE_NAME)

    if args.daemon:
        print(f"[*] Starting DDNS Client daemon. Checking every {args.interval} seconds...")
        while True:
            run_ddns_update(config, cache_path, force=args.force)
            # Reset force after first run
            args.force = False
            time.sleep(args.interval)
    else:
        success = run_ddns_update(config, cache_path, force=args.force)
        sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
