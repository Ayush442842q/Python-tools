#!/usr/bin/env python3
"""
Subnet Calculator - A utility for calculating subnet ranges, network IDs,
broadcast addresses, netmasks, wildcards, and usable hosts from IP/CIDR inputs.
"""

import argparse
import sys
import ipaddress

def ip_to_binary(ip_obj):
    """Convert IPv4 or IPv6 address to binary string representation."""
    if ip_obj.version == 4:
        return ".".join(f"{int(octet):08b}" for octet in str(ip_obj).split('.'))
    else:
        # IPv6: split into 16-bit blocks
        # ip_obj.exploded yields the full representation (e.g. '2001:0db8:0000:...')
        blocks = ip_obj.exploded.split(':')
        binary_blocks = []
        for block in blocks:
            binary_blocks.append(f"{int(block, 16):016b}")
        return ":".join(binary_blocks)

def main():
    parser = argparse.ArgumentParser(
        description="Subnet Calculator - Calculate network properties from an IP address and CIDR prefix or netmask."
    )
    parser.add_argument(
        "cidr", 
        nargs="?", 
        help="IP address with CIDR prefix (e.g., 192.168.1.50/24 or 2001:db8::1/64)"
    )
    parser.add_argument(
        "-i", "--ip", 
        help="IP address (if CIDR prefix is not provided in positional argument)"
    )
    parser.add_argument(
        "-m", "--mask", 
        help="Subnet mask or CIDR prefix (e.g., 255.255.255.0 or 24)"
    )

    args = parser.parse_args()

    input_str = ""

    # Resolve inputs
    if args.cidr:
        input_str = args.cidr
    elif args.ip:
        if args.mask:
            # Check if mask is a CIDR number or a netmask string
            mask_val = args.mask.lstrip('/')
            input_str = f"{args.ip}/{mask_val}"
        else:
            input_str = args.ip
    else:
        # If no arguments provided, print help
        parser.print_help()
        sys.exit(0)

    try:
        # Parse interface (handles IP and prefix/netmask combined)
        interface = ipaddress.ip_interface(input_str)
        network = interface.network
        ip = interface.ip
    except ValueError as e:
        print(f"[ERROR] Invalid IP address or subnet mask: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"--- Subnet Details for: {input_str} ---")
    print(f"IP Version:        IPv{ip.version}")
    print(f"Input IP Address:  {ip}")
    
    if ip.version == 4:
        print(f"IP Binary:         {ip_to_binary(ip)}")
    
    print(f"Network ID:        {network.network_address}/{network.prefixlen}")
    
    if ip.version == 4:
        print(f"Network Binary:    {ip_to_binary(network.network_address)}")
        print(f"Subnet Mask:       {network.netmask}")
        print(f"Netmask Binary:    {ip_to_binary(network.netmask)}")
        print(f"Wildcard Mask:     {network.hostmask}")
        print(f"Broadcast Address: {network.broadcast_address}")
        
        # Calculate usable host range and counts
        total_hosts = network.num_addresses
        if network.prefixlen == 32:
            usable_hosts = 1
            first_host = network.network_address
            last_host = network.network_address
        elif network.prefixlen == 31:
            usable_hosts = 2
            first_host = network.network_address
            last_host = network.broadcast_address
        else:
            usable_hosts = total_hosts - 2
            first_host = network.network_address + 1
            last_host = network.broadcast_address - 1
            
        print(f"Usable Host Range: {first_host} - {last_host}")
        print(f"Total Hosts:       {total_hosts}")
        print(f"Usable Hosts:      {usable_hosts}")
        
    else:
        # IPv6 Details
        print(f"Netmask:           /{network.prefixlen}")
        print(f"Wildcard/Hostmask: {network.hostmask}")
        
        # In IPv6, broadcast does not exist in the same way, but network[-1] is the last address
        first_host = network[0]
        last_host = network[-1]
        print(f"Host Address Range:{first_host} - {last_host}")
        print(f"Total Hosts:       {network.num_addresses}")
        
    print("-" * (len(input_str) + 24))

if __name__ == "__main__":
    main()
