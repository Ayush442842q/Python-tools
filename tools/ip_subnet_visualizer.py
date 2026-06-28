#!/usr/bin/env python3
"""
CIDR Subnet Grid Visualizer
---------------------------
Visualizes IP address allocations of a CIDR block. Displays network subnets,
hosts, gateways, broadcast IPs, and renders a colored console grid representing
how the IP address space is partitioned.

Dependencies:
    - python 3.6+ (uses standard ipaddress module)

Usage:
    python tools/ip_subnet_visualizer.py 192.168.1.0/24 -s 192.168.1.0/26 192.168.1.64/27 192.168.1.128/25
"""

import sys
import argparse
import ipaddress
from typing import List, Tuple, Dict, Optional

# ANSI Escape Sequences
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_CYAN = "\033[36m"
COLOR_YELLOW = "\033[33m"
COLOR_GREEN = "\033[32m"
COLOR_RED = "\033[31m"
COLOR_GRAY = "\033[90m"
COLOR_BG_DARK = "\033[40m"

SUBNET_COLORS = [
    "\033[92m",  # Light Green
    "\033[94m",  # Light Blue
    "\033[93m",  # Light Yellow
    "\033[95m",  # Light Magenta
    "\033[96m",  # Light Cyan
    "\033[32m",  # Dark Green
    "\033[34m",  # Dark Blue
    "\033[35m",  # Dark Magenta
]

def render_grid_24(parent_net: ipaddress.IPv4Network, subnets: List[Tuple[ipaddress.IPv4Network, str, str]]) -> None:
    """
    Renders a 16x16 grid for a /24 parent network.
    Each cell in the grid represents 1 IP address.
    """
    grid = [['.' for _ in range(16)] for _ in range(16)]
    colors = [[COLOR_GRAY for _ in range(16)] for _ in range(16)]
    
    parent_start = int(parent_net.network_address)
    
    # Fill grid with subnet data
    for idx, (sub, name, color) in enumerate(subnets):
        sub_start = int(sub.network_address)
        sub_len = sub.num_addresses
        
        for offset in range(sub_len):
            ip_val = sub_start + offset
            grid_offset = ip_val - parent_start
            
            if 0 <= grid_offset < 256:
                row = grid_offset // 16
                col = grid_offset % 16
                
                # Label specific IPs
                if offset == 0:
                    grid[row][col] = 'N'  # Network address
                elif offset == sub_len - 1:
                    grid[row][col] = 'B'  # Broadcast address
                elif offset == 1:
                    grid[row][col] = 'G'  # Typical Gateway / first host
                else:
                    grid[row][col] = 'H'  # Usable Host
                    
                colors[row][col] = color

    # Print grid
    print(f"\n{COLOR_BOLD}IP Grid Visualization (16x16 representation for {parent_net}):{COLOR_RESET}")
    print("    " + " ".join(f"{c:X}" for c in range(16)))
    print("  ┌" + "─" * 32)
    
    for r in range(16):
        row_label = f"{r:X}0"
        row_cells = []
        for c in range(16):
            cell_char = grid[r][c]
            cell_color = colors[r][c]
            row_cells.append(f"{cell_color}{cell_char}{COLOR_RESET}")
        print(f"{row_label}│ " + " ".join(row_cells))
        
    print("\nLegend: "
          f"{COLOR_BOLD}N{COLOR_RESET} = Network Addr, "
          f"{COLOR_BOLD}B{COLOR_RESET} = Broadcast, "
          f"{COLOR_BOLD}G{COLOR_RESET} = Gateway/First Host, "
          f"{COLOR_BOLD}H{COLOR_RESET} = Usable Host, "
          f"{COLOR_GRAY}.{COLOR_RESET} = Unallocated")

def render_linear_map(parent_net: ipaddress.IPv4Network, subnets: List[Tuple[ipaddress.IPv4Network, str, str]], map_width: int = 60) -> None:
    """
    Renders a linear horizontal visual map representing IP layout for networks larger/smaller than /24.
    """
    parent_start = int(parent_net.network_address)
    parent_size = parent_net.num_addresses
    
    # 0 for unallocated, otherwise ID of the subnet (1-indexed)
    allocation_map = [0] * map_width
    
    for idx, (sub, name, color) in enumerate(subnets, 1):
        sub_start = int(sub.network_address)
        sub_size = sub.num_addresses
        
        # Calculate offset and span in the map width
        start_ratio = (sub_start - parent_start) / parent_size
        size_ratio = sub_size / parent_size
        
        start_cell = int(start_ratio * map_width)
        num_cells = max(1, int(size_ratio * map_width))
        
        for c in range(start_cell, min(map_width, start_cell + num_cells)):
            allocation_map[c] = (idx, color)
            
    print(f"\n{COLOR_BOLD}Linear Allocation Map ({map_width} segments):{COLOR_RESET}")
    sys.stdout.write(" [")
    for val in allocation_map:
        if val == 0:
            sys.stdout.write(f"{COLOR_GRAY}░{COLOR_RESET}")
        else:
            idx, color = val
            sys.stdout.write(f"{color}█{COLOR_RESET}")
    print("]\n")

def main():
    parser = argparse.ArgumentParser(
        description="CIDR Subnet Grid Visualizer: Maps out and displays IP allocations within a parent network."
    )
    parser.add_argument("parent_cidr", help="The parent network block in CIDR notation (e.g. 192.168.1.0/24)")
    parser.add_argument("-s", "--subnets", nargs="+", default=[], 
                        help="Sub-allocated networks inside the parent network (e.g. 192.168.1.0/26)")
    
    args = parser.parse_args()
    
    try:
        parent_net = ipaddress.IPv4Network(args.parent_cidr, strict=False)
    except ValueError as e:
        print(f"Error: Invalid parent CIDR format: {e}", file=sys.stderr)
        sys.exit(1)
        
    parsed_subnets = []
    
    # Validate and parse subnets
    for idx, sub_str in enumerate(args.subnets):
        try:
            sub_net = ipaddress.IPv4Network(sub_str, strict=False)
        except ValueError as e:
            print(f"Error: Invalid subnet CIDR format '{sub_str}': {e}", file=sys.stderr)
            sys.exit(1)
            
        if not sub_net.subnet_of(parent_net):
            print(f"Error: Subnet {sub_net} is not a valid subset of parent network {parent_net}", file=sys.stderr)
            sys.exit(1)
            
        # Check overlaps
        for existing_sub, name, _ in parsed_subnets:
            if sub_net.overlaps(existing_sub):
                print(f"Error: Subnet {sub_net} overlaps with existing subnet {existing_sub} ({name})", file=sys.stderr)
                sys.exit(1)
                
        color = SUBNET_COLORS[idx % len(SUBNET_COLORS)]
        name = f"Subnet_{idx+1}"
        parsed_subnets.append((sub_net, name, color))
        
    # Sort subnets by network address
    parsed_subnets.sort(key=lambda x: x[0].network_address)
    
    # Print details table
    print(f"\n{COLOR_BOLD}Subnet Allocation Details:{COLOR_RESET}")
    print(f"{'Subnet':<20} | {'Network Range':<32} | {'Netmask':<15} | {'Hosts':<8}")
    print("-" * 83)
    
    for sub, name, color in parsed_subnets:
        usable_hosts = max(0, sub.num_addresses - 2) if sub.prefixlen < 31 else sub.num_addresses
        hosts_range = f"{sub.network_address} - {sub.broadcast_address}"
        print(f"{color}{name:<20}{COLOR_RESET} | {hosts_range:<32} | {sub.netmask:<15} | {usable_hosts:<8}")
        
    # Find gaps (free space)
    gaps = []
    current_ip = int(parent_net.network_address)
    parent_end = int(parent_net.broadcast_address)
    
    for sub, _, _ in parsed_subnets:
        sub_start = int(sub.network_address)
        if sub_start > current_ip:
            # We found a gap
            gap_net = ipaddress.summarize_address_range(
                ipaddress.IPv4Address(current_ip),
                ipaddress.IPv4Address(sub_start - 1)
            )
            gaps.extend(gap_net)
        current_ip = int(sub.broadcast_address) + 1
        
    if current_ip <= parent_end:
        gap_net = ipaddress.summarize_address_range(
            ipaddress.IPv4Address(current_ip),
            ipaddress.IPv4Address(parent_end)
        )
        gaps.extend(gap_net)
        
    if gaps:
        print(f"\n{COLOR_YELLOW}Unallocated IP space (Gaps):{COLOR_RESET}")
        for gap in gaps:
            print(f"  - {gap} ({gap.num_addresses} addresses)")
    else:
        print(f"\n{COLOR_GREEN}All IP spaces fully allocated (No gaps).{COLOR_RESET}")
        
    # Render layout
    if parent_net.prefixlen == 24:
        render_grid_24(parent_net, parsed_subnets)
    else:
        render_linear_map(parent_net, parsed_subnets)

if __name__ == "__main__":
    main()
