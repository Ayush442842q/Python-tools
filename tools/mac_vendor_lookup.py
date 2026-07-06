"""
MAC Address Vendor Lookup Tool
Parses and checks MAC addresses against an offline database of popular OUIs (Organizationally Unique Identifier)
with a fallback to a free public API for online lookups.
"""
import argparse
import json
import os
import re
import sys
import urllib.request
import urllib.error

# Offline dictionary of common OUI prefixes (normalized to 6 hex digits, lowercase)
OUI_DATABASE = {
    "00000c": "Cisco Systems, Inc.",
    "00001c": "Bell Industries",
    "0001c9": "Shanghai Radian Telecom",
    "00037f": "Atheros Communications",
    "00040e": "AVM GmbH",
    "0005b5": "Broadcom Corporation",
    "0007e9": "Intel Corporation",
    "00095b": "Netgear Inc.",
    "000a95": "Apple, Inc.",
    "000c29": "VMware, Inc.",
    "000d65": "Sagem",
    "000e3b": "Sandisk Corporation",
    "000f60": "D-Link Corporation",
    "00107a": "Aopen Inc.",
    "00110a": "Hewlett-Packard",
    "001122": "CIMSYS Inc.",
    "00116b": "Microsoft Corporation",
    "001217": "Samsung Electronics Co.,Ltd",
    "0013e8": "Intel Corporation",
    "001422": "Dell Inc.",
    "001438": "Motorola Solutions",
    "00155d": "Microsoft Mobile Oy",
    "00163e": "XenSource Inc. (Xen Virtual NIC)",
    "0017f2": "Apple, Inc.",
    "001861": "TP-Link Technologies Co., Ltd.",
    "00199d": "Visteon Corporation",
    "001a11": "Google Inc.",
    "001b21": "ASUSTek Computer Inc.",
    "001cbf": "Intel Corporation",
    "001d60": "ASUSTek Computer Inc.",
    "001e06": "Wistron InfoComm (Kunshan) Co.Ltd.",
    "001f3c": "Intel Corporation",
    "002170": "Dell Inc.",
    "002241": "Intel Corporation",
    "002354": "ASUSTek Computer Inc.",
    "0024e8": "Dell Inc.",
    "002590": "Super Micro Computer, Inc.",
    "00268a": "Intel Corporation",
    "0028f8": "Huawei Technologies Co., Ltd.",
    "005056": "VMware, Inc.",
    "0050f2": "Microsoft Corporation",
    "0090a9": "Western Digital Technologies, Inc.",
    "0090f5": "CLEVO CO.",
    "00a0cc": "Lite-On Technology Corp.",
    "00a0d1": "Intel Corporation",
    "00a28a": "Amazon Technologies Inc.",
    "00d02b": "Nvidia Corporation",
    "10604b": "Hewlett Packard Enterprise",
    "107b44": "Apple, Inc.",
    "109027": "Intel Corporation",
    "10ddb1": "Apple, Inc.",
    "14205b": "Intel Corporation",
    "1458d0": "GIGA-BYTE TECHNOLOGY CO., LTD.",
    "180373": "Dell Inc.",
    "18af61": "Apple, Inc.",
    "1c1adf": "Linksys LLC",
    "204747": "Dell Inc.",
    "244bfe": "Intel Corporation",
    "245ebb": "Hewlett Packard",
    "247703": "Huawei Technologies Co., Ltd.",
    "28cfda": "Apple, Inc.",
    "2c26c5": "Intel Corporation",
    "3085a9": "ASUSTek Computer Inc.",
    "309c23": "Hewlett Packard Enterprise",
    "3417eb": "Intel Corporation",
    "34e12d": "Intel Corporation",
    "3c15c2": "Intel Corporation",
    "3c5ab4": "Google Inc.",
    "3cd92b": "Hewlett Packard",
    "408d5c": "GIGA-BYTE TECHNOLOGY CO., LTD.",
    "40a8f8": "Intel Corporation",
    "448500": "Intel Corporation",
    "44d9e7": "Ubiquiti Networks, Inc.",
    "4851b7": "Intel Corporation",
    "4c5e0c": "Intel Corporation",
    "503eae": "Intel Corporation",
    "5076af": "ASUSTek Computer Inc.",
    "525400": "QEMU Virtual NIC",
    "54e1ad": "Intel Corporation",
    "605718": "Intel Corporation",
    "64006a": "Huawei Technologies Co., Ltd.",
    "6c198f": "Intel Corporation",
    "7054d2": "ASUSTek Computer Inc.",
    "708bcd": "Intel Corporation",
    "74867a": "Intel Corporation",
    "74d435": "Apple, Inc.",
    "7c0507": "Intel Corporation",
    "802aa8": "Ubiquiti Networks, Inc.",
    "80fa5b": "Intel Corporation",
    "843497": "Intel Corporation",
    "847beb": "Apple, Inc.",
    "88532e": "Intel Corporation",
    "8c1645": "Intel Corporation",
    "8c8590": "Apple, Inc.",
    "90e2ba": "Intel Corporation",
    "94c691": "Intel Corporation",
    "9c7bef": "Intel Corporation",
    "a08cfd": "Intel Corporation",
    "a43135": "Intel Corporation",
    "a45011": "Intel Corporation",
    "a4c3f0": "Intel Corporation",
    "ac3743": "Intel Corporation",
    "ac8247": "Intel Corporation",
    "acbc32": "Apple, Inc.",
    "b0c559": "Intel Corporation",
    "b42e99": "Intel Corporation",
    "b4a9fc": "Intel Corporation",
    "b827eb": "Raspberry Pi Foundation",
    "c85b76": "Intel Corporation",
    "c8d9d2": "Intel Corporation",
    "cc2d21": "Intel Corporation",
    "cc96e5": "Intel Corporation",
    "d05099": "Intel Corporation",
    "d07f35": "Intel Corporation",
    "d481d7": "Intel Corporation",
    "d85de2": "Intel Corporation",
    "e03f49": "ASUSTek Computer Inc.",
    "e0d55e": "Intel Corporation",
    "e4a8df": "Intel Corporation",
    "e8b1fc": "Intel Corporation",
    "f0761c": "Intel Corporation",
    "f0def1": "Intel Corporation",
    "f44d30": "Intel Corporation",
    "f875a4": "Intel Corporation",
    "fc3497": "Intel Corporation"
}

CACHE_FILE = os.path.expanduser("~/.mac_vendor_cache.json")

def load_cache():
    """Load local cached lookups."""
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_cache(cache):
    """Save lookups to local cache."""
    try:
        with open(CACHE_FILE, 'w') as f:
            json.dump(cache, f)
    except Exception:
        pass

def normalize_mac(mac_str):
    """Clean MAC address string and return standard OUI and full normalized string."""
    clean = re.sub(r'[^0-9a-fA-F]', '', mac_str).lower()
    if len(clean) < 6:
        return None, None
    oui = clean[:6]
    # Return formatted canonical mac too
    if len(clean) == 12:
        formatted = ":".join(clean[i:i+2] for i in range(0, 12, 2))
    else:
        formatted = clean
    return oui, formatted

def extract_macs_from_text(text):
    """Find all MAC-like patterns in a text string."""
    # Matches common hex patterns separated by colons, hyphens, dots or contiguous
    pattern = r'(?:[0-9a-fA-F]{2}[:.-]){5}[0-9a-fA-F]{2}|[0-9a-fA-F]{4}\.[0-9a-fA-F]{4}\.[0-9a-fA-F]{4}|[0-9a-fA-F]{12}'
    return re.findall(pattern, text)

def lookup_online(mac_str):
    """Fallback to public API for online vendor lookup."""
    url = f"https://api.macvendors.com/{urllib.parse.quote(mac_str)}"
    req = urllib.request.Request(
        url,
        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.read().decode('utf-8').strip()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return "Unknown Vendor"
        raise
    except Exception:
        return None

def main():
    parser = argparse.ArgumentParser(
        description="Lookup manufacturer/vendor of MAC addresses offline or online."
    )
    parser.add_argument(
        "macs",
        nargs="*",
        help="One or more MAC addresses to lookup."
    )
    parser.add_argument(
        "-f", "--file",
        help="Path to file containing MAC addresses (one per line or arbitrary text containing MACs)."
    )
    parser.add_argument(
        "--online",
        action="store_true",
        help="Enable online API lookup fallback for unknown OUIs."
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Disable local caching of online lookup results."
    )
    
    args = parser.parse_args()
    
    input_macs = []
    
    # Collect MACs from positional arguments
    if args.macs:
        for m in args.macs:
            input_macs.append(m)
            
    # Collect MACs from file
    if args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                content = f.read()
                input_macs.extend(extract_macs_from_text(content))
        except Exception as e:
            print(f"[ERROR] Failed to read file: {e}")
            sys.exit(1)
            
    # Read from stdin if no MACs are provided
    if not input_macs and sys.stdin.isatty() is False:
        stdin_content = sys.stdin.read()
        input_macs.extend(extract_macs_from_text(stdin_content))
        
    if not input_macs:
        print("[INFO] No MAC addresses provided. Please specify positional arguments, use -f/--file, or pipe input.")
        parser.print_help()
        sys.exit(0)
        
    # Load cache if online is enabled
    cache = {} if args.no_cache else load_cache()
    cache_dirty = False
    
    print(f"{'MAC Address':<20} | {'OUI':<8} | {'Manufacturer/Vendor'}")
    print("-" * 70)
    
    for raw_mac in input_macs:
        oui, norm_mac = normalize_mac(raw_mac)
        if not oui:
            print(f"{raw_mac:<20} | {'N/A':<8} | [ERROR] Invalid MAC address format")
            continue
            
        vendor = OUI_DATABASE.get(oui)
        source = "Offline DB"
        
        if not vendor and args.online:
            # Check cache first
            if oui in cache:
                vendor = cache[oui]
                source = "Cache"
            else:
                try:
                    # Slow down requests slightly to respect API rate limits
                    import time
                    time.sleep(1.0)
                    
                    online_vendor = lookup_online(norm_mac)
                    if online_vendor:
                        vendor = online_vendor
                        source = "Online API"
                        cache[oui] = vendor
                        cache_dirty = True
                except Exception:
                    pass
                    
        if not vendor:
            vendor = "Unknown Vendor (Try running with --online)"
            
        canonical_mac = norm_mac if len(norm_mac) == 17 else raw_mac
        print(f"{canonical_mac:<20} | {oui:<8} | {vendor} ({source})" if "Offline" in source or "Cache" in source or "Online" in source
              else f"{canonical_mac:<20} | {oui:<8} | {vendor}")
              
    if cache_dirty and not args.no_cache:
        save_cache(cache)
        
    sys.exit(0)

if __name__ == "__main__":
    main()
