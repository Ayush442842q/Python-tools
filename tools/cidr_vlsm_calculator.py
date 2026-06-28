#!/usr/bin/env python3
"""
Variable Length Subnet Masking (VLSM) Calculator
Partitions a parent IP network dynamically into subnets based on host capacity requirements.
Prevents subnet overlaps and maximizes IP allocation efficiency.
"""

import argparse
import ipaddress
import sys
import math

# ANSI Colors for terminal output
COLOR_HEADER = "\033[95m"
COLOR_BLUE = "\033[94m"
COLOR_GREEN = "\033[92m"
COLOR_WARNING = "\033[93m"
COLOR_FAIL = "\033[91m"
COLOR_END = "\033[0m"
COLOR_BOLD = "\033[1m"


def print_banner():
    banner = f"""{COLOR_HEADER}{COLOR_BOLD}
  _    _ _      _____ __  __    _____      _            _       _             
 | |  | | |    / ____|  \/  |  / ____|    | |          | |     | |            
 | |  | | |   | (___ | \  / | | |     __ _| | ___ _   _| | __ _| |_ ___  _ __ 
 | |  | | |    \___ \| |\/| | | |    / _` | |/ __| | | | |/ _` | __/ _ \| '__|
 | |__| | |________) | |  | | | |___| (_| | | (__| |_| | | (_| | || (_) | |   
  \____/|______|_____/|_|  |_|  \_____\__,_|_|\___|\__,_|_|\__,_|\__\___/|_|   
                                                                              
{COLOR_END}{COLOR_BLUE}          Variable Length Subnet Masking (VLSM) Designer & Optimizer{COLOR_END}
"""
    print(banner, file=sys.stderr)


def get_required_bits(hosts):
    """Calculate the number of host bits needed for a given number of hosts."""
    # We need +2 for network address and broadcast address
    total_ips = hosts + 2
    bits = math.ceil(math.log2(total_ips))
    # Minimum size is /30 (2 usable hosts) which requires 2 bits
    return max(2, bits)


def calculate_vlsm(base_net_str, subnet_requirements):
    """
    Perform the VLSM allocation.
    subnet_requirements: list of tuples (name, requested_hosts)
    """
    try:
        parent_net = ipaddress.ip_network(base_net_str, strict=True)
    except ValueError as e:
        print(f"{COLOR_FAIL}Invalid base IP network: {e}{COLOR_END}", file=sys.stderr)
        sys.exit(1)

    # Sort subnets by requested hosts descending (VLSM rule: largest first)
    sorted_reqs = sorted(subnet_requirements, key=lambda x: x[1], reverse=True)
    
    allocations = []
    current_ip = int(parent_net.network_address)
    parent_end_ip = int(parent_net.broadcast_address)
    
    # Track overall IP availability
    parent_size = parent_net.num_addresses
    allocated_ips = 0

    for name, hosts in sorted_reqs:
        host_bits = get_required_bits(hosts)
        subnet_prefix = 32 - host_bits
        subnet_size = 1 << host_bits
        
        # Align the current IP pointer to the subnet boundary
        # Subnet address must be a multiple of its size
        if current_ip % subnet_size != 0:
            current_ip = ((current_ip // subnet_size) + 1) * subnet_size
            
        # Check if we fit in the parent network
        if current_ip + subnet_size - 1 > parent_end_ip:
            print(f"{COLOR_WARNING}Warning: Subnet '{name}' requiring {hosts} hosts does not fit in the remaining IP space.{COLOR_END}", file=sys.stderr)
            allocations.append({
                "name": name,
                "hosts": hosts,
                "allocated": False,
                "error": "IP space exhausted"
            })
            continue

        subnet_addr = ipaddress.ip_address(current_ip)
        allocated_net = ipaddress.ip_network(f"{subnet_addr}/{subnet_prefix}")
        
        allocations.append({
            "name": name,
            "hosts": hosts,
            "allocated": True,
            "network": allocated_net,
            "usable_range": (allocated_net.network_address + 1, allocated_net.broadcast_address - 1),
            "gateway": allocated_net.network_address + 1, # Common standard: first usable IP
            "broadcast": allocated_net.broadcast_address,
            "netmask": allocated_net.netmask,
            "subnet_size": subnet_size,
            "usable_hosts": subnet_size - 2
        })
        
        allocated_ips += subnet_size
        current_ip += subnet_size

    return parent_net, allocations, allocated_ips


def main():
    parser = argparse.ArgumentParser(
        description="Calculate Variable Length Subnet Masking (VLSM) allocations for IPv4 networks."
    )
    parser.add_argument(
        "network",
        nargs="?",
        default="192.168.1.0/24",
        help="The parent network block in CIDR notation (e.g. 192.168.1.0/24)."
    )
    parser.add_argument(
        "-s", "--subnets",
        nargs="+",
        help="List of subnet requirements in format Name:Hosts (e.g. LAN1:100 WAN:2 DMZ:12).",
        default=["LAN_A:100", "LAN_B:50", "Office:25", "IT_Support:10", "WAN_Link:2"]
    )
    parser.add_argument(
        "--no-banner",
        action="store_true",
        help="Suppress the CLI graphical banner."
    )

    args = parser.parse_args()

    if not args.no_banner:
        print_banner()

    # Parse subnet requirements
    requirements = []
    for s in args.subnets:
        if ":" not in s:
            print(f"{COLOR_FAIL}Invalid subnet argument format '{s}'. Must be Name:Hosts (e.g. SubnetA:50){COLOR_END}", file=sys.stderr)
            sys.exit(1)
        name, hosts_str = s.split(":", 1)
        try:
            hosts = int(hosts_str)
            if hosts <= 0:
                raise ValueError()
        except ValueError:
            print(f"{COLOR_FAIL}Invalid hosts count for subnet '{name}': '{hosts_str}'. Must be a positive integer.{COLOR_END}", file=sys.stderr)
            sys.exit(1)
        requirements.append((name, hosts))

    parent_net, allocations, total_allocated_ips = calculate_vlsm(args.network, requirements)

    # Print Parent Details
    print(f"{COLOR_BOLD}Base Network:{COLOR_END} {parent_net}")
    print(f"{COLOR_BOLD}Total IPs Available:{COLOR_END} {parent_net.num_addresses}")
    print(f"{COLOR_BOLD}Netmask:{COLOR_END} {parent_net.netmask}")
    print("-" * 115)
    
    # Table Header
    print(f"{COLOR_BOLD}{'Subnet Name':<15} {'Req. Hosts':<10} {'Allocated':<12} {'CIDR Network':<18} {'Usable IP Range':<31} {'Gateway':<15} {'Broadcast':<15}{COLOR_END}")
    print("-" * 115)
    
    success_count = 0
    for alloc in allocations:
        if not alloc["allocated"]:
            print(f"{COLOR_FAIL}{alloc['name']:<15} {alloc['hosts']:<10} {'0 (Failed)':<12} {'N/A':<18} {'N/A':<31} {'N/A':<15} {'N/A':<15} [EXHAUSTED]{COLOR_END}")
        else:
            success_count += 1
            range_str = f"{alloc['usable_range'][0]} - {alloc['usable_range'][1]}"
            print(f"{COLOR_GREEN if success_count % 2 == 0 else COLOR_BLUE}{alloc['name']:<15}{COLOR_END} "
                  f"{alloc['hosts']:<10} "
                  f"{alloc['usable_hosts']:<12} "
                  f"{str(alloc['network']):<18} "
                  f"{range_str:<31} "
                  f"{str(alloc['gateway']):<15} "
                  f"{str(alloc['broadcast']):<15}")
            
    print("-" * 115)
    
    # Print statistics
    efficiency = (total_allocated_ips / parent_net.num_addresses) * 100
    print(f"{COLOR_BOLD}Allocation Summary:{COLOR_END}")
    print(f"  Allocated subnets: {success_count} / {len(allocations)}")
    print(f"  Total Allocated IPs: {total_allocated_ips} / {parent_net.num_addresses} ({efficiency:.1f}% space efficiency)")
    print(f"  Remaining Free IPs: {parent_net.num_addresses - total_allocated_ips}")

    # Generate quick visual map
    print(f"\n{COLOR_BOLD}IP Allocation Visual Map:{COLOR_END}")
    total_blocks = 32
    print("[", end="")
    allocated_blocks = round((total_allocated_ips / parent_net.num_addresses) * total_blocks)
    for b in range(total_blocks):
        if b < allocated_blocks:
            print(f"{COLOR_GREEN}█{COLOR_END}", end="")
        else:
            print(f"░", end="")
    print("] (Green = Allocated, Gray = Unallocated)")


if __name__ == "__main__":
    main()
