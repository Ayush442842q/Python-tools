#!/usr/bin/env python3
"""
CIDR Aggregation, Division, and Membership Utility
-------------------------------------------------
A comprehensive IP networking tool to merge lists of IP addresses and subnets
into the smallest set of CIDR blocks, split subnets into smaller prefixes,
subtract subnets, and check membership of IPs.

Supports both IPv4 and IPv6 protocols using Python's built-in ipaddress module.

Author: Antigravity
License: MIT
"""

import sys
import argparse
import ipaddress
from typing import List, Set, Union


def clean_line(line: str) -> str:
    """Strip comments and surrounding whitespace."""
    if "#" in line:
        line = line.split("#", 1)[0]
    return line.strip()


def parse_ip_inputs(inputs: List[str]) -> List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]:
    """Parse list of IP strings/networks into network objects."""
    networks = []
    for raw_input in inputs:
        # Handle files if @path format is provided
        if raw_input.startswith("@"):
            filepath = raw_input[1:]
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    for line in f:
                        line_cleaned = clean_line(line)
                        if line_cleaned:
                            networks.append(ipaddress.ip_network(line_cleaned, strict=False))
            except Exception as e:
                print(f"Error reading file {filepath}: {e}", file=sys.stderr)
        else:
            cleaned = clean_line(raw_input)
            if cleaned:
                try:
                    # Convert single IP to a /32 or /128 network
                    networks.append(ipaddress.ip_network(cleaned, strict=False))
                except ValueError as e:
                    print(f"Skipping invalid IP/subnet: '{cleaned}' ({e})", file=sys.stderr)
    return networks


def aggregate_networks(networks: List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]) -> List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]:
    """Merge contiguous networks into the minimal aggregate set (CIDR summarization)."""
    return list(ipaddress.collapse_addresses(networks))


def split_network(network: Union[ipaddress.IPv4Network, ipaddress.IPv6Network], new_prefix: int) -> List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]:
    """Split a network into smaller subnets with a larger prefix length."""
    if new_prefix <= network.prefixlen:
        raise ValueError(f"New prefix length /{new_prefix} must be greater than network prefix /{network.prefixlen}")
    return list(network.subnets(new_prefix=new_prefix))


def subtract_networks(base_net: Union[ipaddress.IPv4Network, ipaddress.IPv6Network], exclude_net: Union[ipaddress.IPv4Network, ipaddress.IPv6Network]) -> List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]:
    """Subtract exclude_net from base_net, returning a list of remaining subnets."""
    if not base_net.overlaps(exclude_net):
        return [base_net]
    
    # ipaddress address_exclude requires exclude_net to be a subnet of base_net
    if exclude_net.subnet_of(base_net):
        return list(base_net.address_exclude(exclude_net))
    
    # If they overlap but exclude_net is not fully inside, calculate intersection
    # and exclude the intersection.
    # To do this, find the overlapping portion (which will be a subnet of the smaller of the two)
    # If base_net is smaller, subtracting exclude_net leaves nothing
    if base_net.subnet_of(exclude_net):
        return []
        
    # Otherwise, exclude_net overlaps but is not a subnet of base_net.
    # This means base_net is larger. Find the intersection.
    # The intersection of two overlapping subnets is simply the smaller one (exclude_net in this case)
    return list(base_net.address_exclude(exclude_net))


def check_membership(ips: List[str], subnets: List[Union[ipaddress.IPv4Network, ipaddress.IPv6Network]]) -> None:
    """Print whether each input IP belongs to any of the subnets."""
    for ip_str in ips:
        try:
            ip_obj = ipaddress.ip_address(ip_str)
            found = False
            for net in subnets:
                if ip_obj in net:
                    print(f"IP {ip_str} is INSIDE subnet {net}")
                    found = True
                    break
            if not found:
                print(f"IP {ip_str} is OUTSIDE all specified subnets")
        except ValueError:
            print(f"Invalid IP address format: '{ip_str}'", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="CIDR Aggregation, Splitter, Subtraction, and Membership checking tool."
    )
    
    # Subcommands
    subparsers = parser.add_subparsers(dest="command", required=True, help="Network operation to perform")
    
    # Aggregate Subcommand
    agg_parser = subparsers.add_parser("aggregate", aliases=["merge"], help="Summarize/collapse lists of IPs and subnets")
    agg_parser.add_argument("inputs", nargs="+", help="IPs/Subnets to aggregate. Use @filename to load from a file.")
    
    # Split Subcommand
    split_parser = subparsers.add_parser("split", aliases=["divide"], help="Divide a subnet into smaller CIDR blocks")
    split_parser.add_argument("subnet", help="The subnet to split (e.g. 192.168.1.0/24)")
    split_parser.add_argument("prefix", type=int, help="Target subnet prefix length (e.g. 26)")
    
    # Exclude/Subtract Subcommand
    sub_parser = subparsers.add_parser("exclude", aliases=["subtract"], help="Exclude subnets from a base subnet")
    sub_parser.add_argument("base", help="The base subnet (e.g. 10.0.0.0/8)")
    sub_parser.add_argument("exclude", nargs="+", help="Subnets to exclude (e.g. 10.1.0.0/16)")
    
    # Membership Subcommand
    mem_parser = subparsers.add_parser("contains", aliases=["check"], help="Check if IPs are inside subnets")
    mem_parser.add_argument("--subnets", nargs="+", required=True, help="Subnets to check membership against")
    mem_parser.add_argument("--ips", nargs="+", required=True, help="IP addresses to check")

    args = parser.parse_args()

    try:
        if args.command in ["aggregate", "merge"]:
            nets = parse_ip_inputs(args.inputs)
            if not nets:
                print("No valid networks parsed.", file=sys.stderr)
                return 1
            collapsed = aggregate_networks(nets)
            print(f"Collapsed {len(nets)} inputs into {len(collapsed)} CIDR blocks:")
            for net in collapsed:
                print(net)
                
        elif args.command in ["split", "divide"]:
            net = ipaddress.ip_network(args.subnet, strict=False)
            subnets = split_network(net, args.prefix)
            print(f"Split {net} into {len(subnets)} subnets of /{args.prefix}:")
            for sub in subnets:
                print(sub)
                
        elif args.command in ["exclude", "subtract"]:
            base = ipaddress.ip_network(args.base, strict=False)
            current_nets = [base]
            
            # Subscriptions can be multiple
            exclude_nets = parse_ip_inputs(args.exclude)
            for ex_net in exclude_nets:
                new_nets = []
                for active_net in current_nets:
                    new_nets.extend(subtract_networks(active_net, ex_net))
                current_nets = new_nets
                
            # Collapse results to clean up
            current_nets = aggregate_networks(current_nets)
            print(f"Result of excluding {len(exclude_nets)} subnets from {args.base}:")
            for net in current_nets:
                print(net)
                
        elif args.command in ["contains", "check"]:
            subnets = parse_ip_inputs(args.subnets)
            check_membership(args.ips, subnets)
            
    except Exception as e:
        print(f"Error executing command: {e}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
