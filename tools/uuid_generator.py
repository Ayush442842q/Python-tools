#!/usr/bin/env python3
"""
UUID/GUID Generator
Generates various versions of UUIDs (v1, v3, v4, v5) with options for formatting, 
quantity, and namespaces.
"""

import argparse
import sys
import uuid

def generate_uuids(version, count, name=None, namespace=None, uppercase=False, raw=False, urn=False, braces=False):
    uuids = []
    
    # Parse namespace if v3 or v5 is selected
    ns_id = None
    if version in (3, 5):
        if not namespace:
            print("Error: Namespace (--namespace or -s) is required for UUID v3 and v5.", file=sys.stderr)
            sys.exit(1)
        if not name:
            print("Error: Name (--name or -m) is required for UUID v3 and v5.", file=sys.stderr)
            sys.exit(1)
            
        ns_map = {
            'dns': uuid.NAMESPACE_DNS,
            'url': uuid.NAMESPACE_URL,
            'oid': uuid.NAMESPACE_OID,
            'x500': uuid.NAMESPACE_X500
        }
        
        if namespace.lower() in ns_map:
            ns_id = ns_map[namespace.lower()]
        else:
            try:
                ns_id = uuid.UUID(namespace)
            except ValueError:
                print(f"Error: Invalid namespace UUID: {namespace}", file=sys.stderr)
                sys.exit(1)

    for _ in range(count):
        if version == 1:
            val = uuid.uuid1()
        elif version == 3:
            val = uuid.uuid3(ns_id, name)
        elif version == 4:
            val = uuid.uuid4()
        elif version == 5:
            val = uuid.uuid5(ns_id, name)
        else:
            val = uuid.uuid4()
            
        uuids.append(val)
        
    formatted_uuids = []
    for u in uuids:
        s = str(u)
        if raw:
            s = u.hex
        if uppercase:
            s = s.upper()
        if urn:
            s = u.urn
            if uppercase:
                s = s.upper()
        elif braces:
            s = f"{{{s}}}"
            
        formatted_uuids.append(s)
        
    return formatted_uuids

def main():
    parser = argparse.ArgumentParser(description='Generate secure and standardized UUIDs/GUIDs.')
    parser.add_argument('-v', '--version', type=int, choices=[1, 3, 4, 5], default=4,
                        help='UUID version to generate (default: 4)')
    parser.add_argument('-n', '--count', type=int, default=1,
                        help='Number of UUIDs to generate (default: 1)')
    parser.add_argument('-u', '--uppercase', action='store_true',
                        help='Output UUIDs in uppercase')
    parser.add_argument('-r', '--raw', action='store_true',
                        help='Output raw hex string without hyphens')
    parser.add_argument('--urn', action='store_true',
                        help='Output in URN format (e.g., urn:uuid:...)')
    parser.add_argument('-b', '--braces', action='store_true',
                        help='Enclose UUIDs in curly braces {...}')
    
    # Arguments for v3 and v5
    parser.add_argument('-s', '--namespace', type=str, default=None,
                        help='Namespace UUID or preset name ("dns", "url", "oid", "x500") for v3/v5')
    parser.add_argument('-m', '--name', type=str, default=None,
                        help='Name string to hash for v3/v5')

    args = parser.parse_args()

    # Generate and print UUIDs
    results = generate_uuids(
        version=args.version,
        count=args.count,
        name=args.name,
        namespace=args.namespace,
        uppercase=args.uppercase,
        raw=args.raw,
        urn=args.urn,
        braces=args.braces
    )
    
    for item in results:
        print(item)

if __name__ == '__main__':
    main()
