#!/usr/bin/env python3
"""
IP Subnet Calculator

Takes an IP address and CIDR prefix (e.g. 192.168.1.10/24)
and calculates network address, broadcast address, mask, wildcard,
first/last usable IP, and total hosts.

Usage:
    python ip_subnet_calculator.py 192.168.1.10/24
"""

import sys
import argparse
import ipaddress

def to_binary(ip_obj):
    """Convert an IPv4Address to a binary string grouped by octets."""
    parts = f"{int(ip_obj):032b}"
    return ".".join(parts[i:i+8] for i in range(0, 32, 8))

def calculate_subnet(ip_cidr):
    """Calculates network properties and displays them."""
    try:
        # Strict=False allows supplying a host IP address (like 192.168.1.15/24)
        # instead of just the network address (192.168.1.0/24)
        interface = ipaddress.IPv4Interface(ip_cidr)
        network = interface.network
    except Exception as e:
        print(f"Error parsing IP/Subnet: {e}", file=sys.stderr)
        return False
        
    netmask = interface.netmask
    wildcard = ipaddress.IPv4Address(int(netmask) ^ 0xFFFFFFFF)
    
    # Calculate usable host range
    hosts = list(network.hosts())
    
    if hosts:
        first_usable = hosts[0]
        last_usable = hosts[-1]
        usable_hosts_count = len(hosts)
    else:
        # For /31 and /32 subnets, usable hosts behavior differs
        first_usable = "N/A"
        last_usable = "N/A"
        usable_hosts_count = network.num_addresses

    print(f"\nSubnet Details for: {ip_cidr}")
    print("=" * 45)
    
    # Display table of values
    row_format = "{:<20} {:<18} {:<35}"
    print(row_format.format("Property", "Value", "Binary Representation"))
    print("-" * 75)
    
    print(row_format.format("IP Address", str(interface.ip), to_binary(interface.ip)))
    print(row_format.format("Network Address", str(network.network_address), to_binary(network.network_address)))
    print(row_format.format("Netmask (Subnet)", str(netmask), to_binary(netmask)))
    print(row_format.format("Wildcard Mask", str(wildcard), to_binary(wildcard)))
    print(row_format.format("Broadcast Address", str(network.broadcast_address), to_binary(network.broadcast_address)))
    
    print("-" * 75)
    print(f"First Usable IP:     {first_usable}")
    print(f"Last Usable IP:      {last_usable}")
    print(f"Total Usable Hosts:  {usable_hosts_count} (2^{32 - network.prefixlen} - 2 if CIDR <= 30)")
    print(f"CIDR Prefix:         /{network.prefixlen}")
    print("=" * 45)
    return True

def main():
    parser = argparse.ArgumentParser(
        description="Calculate IPv4 subnetting details from an IP/CIDR input.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "subnet",
        nargs="?",
        help="IP address with CIDR suffix (e.g., 192.168.1.50/24 or 10.0.0.1/8)."
    )
    
    args = parser.parse_args()
    
    if args.subnet:
        success = calculate_subnet(args.subnet)
        return 0 if success else 1
        
    # Interactive mode if no subnet passed
    print("IP Subnet Calculator (Interactive Mode)")
    print("Type 'exit' or press Ctrl+C to quit.")
    
    while True:
        try:
            user_input = input("\nEnter IP/CIDR (e.g. 192.168.1.57/24): ").strip()
            if not user_input:
                continue
            if user_input.lower() in ('exit', 'quit'):
                break
            calculate_subnet(user_input)
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break
            
    return 0

if __name__ == "__main__":
    sys.exit(main())
