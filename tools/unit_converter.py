#!/usr/bin/env python3
"""
Developer's Unit Converter
Converts between common developer unit systems: digital storage, data transfer rates, 
number systems, and epoch timestamps.
"""

import argparse
import sys
import datetime
import math

# Digital Storage mapping
STORAGE_DECIMAL = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
STORAGE_BINARY = ['B', 'KiB', 'MiB', 'GiB', 'TiB', 'PiB']

# Bandwidth mapping
BANDWIDTH_UNITS = ['bps', 'Kbps', 'Mbps', 'Gbps', 'Tbps']

def convert_storage(value, from_unit, to_unit, binary=False):
    units = STORAGE_BINARY if binary else STORAGE_DECIMAL
    base = 1024 if binary else 1000
    
    # Normalize inputs
    from_idx = -1
    to_idx = -1
    
    # Allow loose matching (e.g. "kb" to "KB" or "KiB")
    for i, u in enumerate(units):
        if u.lower() == from_unit.lower():
            from_idx = i
        if u.lower() == to_unit.lower():
            to_idx = i
            
    # Fallback to check prefix if no exact match (e.g. from="kb" on binary mode)
    if from_idx == -1:
        prefix = from_unit.rstrip('iB').rstrip('B').upper()
        for i, u in enumerate(units):
            if u.startswith(prefix):
                from_idx = i
                break
                
    if to_idx == -1:
        prefix = to_unit.rstrip('iB').rstrip('B').upper()
        for i, u in enumerate(units):
            if u.startswith(prefix):
                to_idx = i
                break

    if from_idx == -1 or to_idx == -1:
        raise ValueError(f"Invalid units: '{from_unit}' or '{to_unit}'. Supported: {', '.join(units)}")
        
    # Convert to bytes first, then to target
    bytes_val = value * (base ** from_idx)
    target_val = bytes_val / (base ** to_idx)
    return target_val, units[to_idx]

def convert_bandwidth(value, from_unit, to_unit):
    # Bandwidth standard is base-1000
    try:
        from_idx = [u.lower() for u in BANDWIDTH_UNITS].index(from_unit.lower())
        to_idx = [u.lower() for u in BANDWIDTH_UNITS].index(to_unit.lower())
    except ValueError:
        raise ValueError(f"Invalid bandwidth units. Supported: {', '.join(BANDWIDTH_UNITS)}")
        
    bps_val = value * (1000 ** from_idx)
    target_val = bps_val / (1000 ** to_idx)
    return target_val, BANDWIDTH_UNITS[to_idx]

def convert_bases(val_str, from_base, to_base):
    # Parse inputs
    try:
        if from_base.lower() in ('dec', '10'):
            num = int(val_str)
        elif from_base.lower() in ('hex', '16'):
            num = int(val_str, 16)
        elif from_base.lower() in ('bin', '2'):
            num = int(val_str, 2)
        elif from_base.lower() in ('oct', '8'):
            num = int(val_str, 8)
        elif from_base.lower() in ('ascii', 'char'):
            if len(val_str) != 1:
                raise ValueError("ASCII input must be a single character.")
            num = ord(val_str)
        else:
            raise ValueError(f"Unsupported from-base: '{from_base}'")
    except ValueError as e:
        raise ValueError(f"Failed to parse input '{val_str}' with base '{from_base}': {e}")

    # Format output
    if to_base.lower() in ('dec', '10'):
        return str(num)
    elif to_base.lower() in ('hex', '16'):
        return hex(num)
    elif to_base.lower() in ('bin', '2'):
        return bin(num)
    elif to_base.lower() in ('oct', '8'):
        return oct(num)
    elif to_base.lower() in ('ascii', 'char'):
        if 0 <= num <= 0x10FFFF:
            return chr(num)
        else:
            return f"Out of ASCII/Unicode range: {num}"
    else:
        raise ValueError(f"Unsupported to-base: '{to_base}'")

def convert_time(val_str):
    # Try converting timestamp to date
    try:
        # Check if float or int timestamp
        ts = float(val_str)
        dt_utc = datetime.datetime.fromtimestamp(ts, datetime.timezone.utc)
        dt_local = datetime.datetime.fromtimestamp(ts)
        return (f"Unix Timestamp: {ts}\n"
                f"UTC Datetime:   {dt_utc.isoformat()}\n"
                f"Local Datetime: {dt_local.isoformat()}")
    except ValueError:
        pass
        
    # Try converting ISO string to timestamp
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.datetime.strptime(val_str, fmt)
            ts = dt.timestamp()
            return (f"ISO/Date Input: {val_str}\n"
                    f"Unix Timestamp: {ts}\n"
                    f"UTC Datetime:   {dt.astimezone(datetime.timezone.utc).isoformat()}")
        except ValueError:
            continue
            
    raise ValueError(f"Could not parse '{val_str}' as Unix timestamp or YYYY-MM-DD [HH:MM:SS] format.")

def main():
    parser = argparse.ArgumentParser(description="Developer's conversion utility for digital storage, bandwidth, number systems, and time.")
    
    subparsers = parser.add_subparsers(dest='category', help='Category of conversion')
    
    # 1. Digital Storage
    p_storage = subparsers.add_parser('storage', help='Convert between digital storage sizes (e.g. KB to GB)')
    p_storage.add_argument('value', type=float, help='Numeric value to convert')
    p_storage.add_argument('from_unit', type=str, help='Source unit (e.g. B, KB, MB, GB, TB, KiB, MiB, GiB)')
    p_storage.add_argument('to_unit', type=str, help='Target unit (e.g. GB, GiB)')
    p_storage.add_argument('-b', '--binary', action='store_true', help='Use base-1024 binary units (KiB, MiB) instead of base-1000 decimal (KB, MB)')
    
    # 2. Bandwidth
    p_band = subparsers.add_parser('bandwidth', help='Convert network data rates (e.g. Mbps to Gbps)')
    p_band.add_argument('value', type=float, help='Numeric value to convert')
    p_band.add_argument('from_unit', type=str, help='Source unit (e.g. bps, Kbps, Mbps, Gbps)')
    p_band.add_argument('to_unit', type=str, help='Target unit (e.g. Gbps)')
    
    # 3. Number Systems
    p_base = subparsers.add_parser('base', help='Convert numbers between base representation (2, 8, 10, 16, ASCII)')
    p_base.add_argument('value', type=str, help='Value to convert (prefix hex with 0x, bin with 0b if converting from dec/hex/etc.)')
    p_base.add_argument('from_base', type=str, help='Source base (bin, oct, dec, hex, ascii)')
    p_base.add_argument('to_base', type=str, help='Target base (bin, oct, dec, hex, ascii)')
    
    # 4. Epoch Time
    p_time = subparsers.add_parser('time', help='Convert Unix epoch timestamps to ISO datetimes and vice-versa')
    p_time.add_argument('value', type=str, help='Epoch timestamp or ISO-like string (e.g. "1687000000" or "2026-06-17 12:00:00")')

    args = parser.parse_args()

    if not args.category:
        parser.print_help()
        sys.exit(1)

    try:
        if args.category == 'storage':
            res, target_u = convert_storage(args.value, args.from_unit, args.to_unit, args.binary)
            print(f"{args.value} {args.from_unit} = {res:.6f} {target_u}")
        elif args.category == 'bandwidth':
            res, target_u = convert_bandwidth(args.value, args.from_unit, args.to_unit)
            print(f"{args.value} {args.from_unit} = {res:.6f} {target_u}")
        elif args.category == 'base':
            res = convert_bases(args.value, args.from_base, args.to_base)
            print(f"Input ({args.from_base}): {args.value} -> Output ({args.to_base}): {res}")
        elif args.category == 'time':
            res = convert_time(args.value)
            print(res)
    except Exception as e:
        print(f"Error during conversion: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
