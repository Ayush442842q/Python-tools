"""
MAC Address Generator Tool
Generates random, valid MAC addresses with custom prefixes, formats, and properties.
"""
import argparse
import random
import re
import sys

# Common vendor prefixes (OUI)
VENDORS = {
    "cisco": "00:00:0C",
    "apple": "00:17:F2",
    "dell": "00:14:22",
    "intel": "00:13:E8",
    "hp": "00:11:0A",
    "microsoft": "00:50:F2",
    "google": "3C:5A:B4"
}

def clean_hex(s):
    return re.sub(r'[^0-9a-fA-F]', '', s)

def generate_mac(prefix_hex, delimiter, uppercase, local, multicast):
    # We need 12 hex digits (6 bytes)
    hex_digits = list(prefix_hex)
    
    # If we need to set local/multicast bits, we do it on the first byte (first 2 hex digits)
    # only if the prefix is empty. If a prefix is provided, we respect the prefix as-is.
    if len(hex_digits) < 2:
        # Generate the first byte
        first_byte = random.randint(0, 255)
        # LSB of first byte: multicast (0x01)
        # Second LSB of first byte: locally administered (0x02)
        if local:
            first_byte |= 0x02
        else:
            first_byte &= ~0x02
            
        if multicast:
            first_byte |= 0x01
        else:
            first_byte &= ~0x01
            
        first_byte_hex = f"{first_byte:02x}"
        hex_digits = list(first_byte_hex) + hex_digits
        
    # Fill up the rest to 12 digits
    while len(hex_digits) < 12:
        hex_digits.append(f"{random.randint(0, 15):x}")
        
    mac_str = "".join(hex_digits[:12]).lower()
    
    # Formatting
    if delimiter == ':':
        formatted = ":".join(mac_str[i:i+2] for i in range(0, 12, 2))
    elif delimiter == '-':
        formatted = "-".join(mac_str[i:i+2] for i in range(0, 12, 2))
    elif delimiter == '.':
        formatted = ".".join(mac_str[i:i+4] for i in range(0, 12, 4))
    else:  # none
        formatted = mac_str
        
    if uppercase:
        formatted = formatted.upper()
        
    return formatted

def main():
    parser = argparse.ArgumentParser(
        description="Generate random, valid MAC addresses with custom formatting and vendor prefixes."
    )
    
    parser.add_argument(
        "-c", "--count",
        type=int,
        default=1,
        help="Number of MAC addresses to generate (default: 1)."
    )
    parser.add_argument(
        "-p", "--prefix",
        help="Specific OUI prefix (e.g. '00:1A:2B', '00-1A-2B' or '001A2B') or a vendor name: "
             f"{', '.join(VENDORS.keys())}."
    )
    parser.add_argument(
        "-d", "--delimiter",
        choices=[":", "-", ".", "none"],
        default=":",
        help="Delimiter for MAC address formatting (default: ':')."
    )
    parser.add_argument(
        "-u", "--uppercase",
        action="store_true",
        help="Output MAC addresses in uppercase (default is lowercase)."
    )
    parser.add_argument(
        "--local",
        action="store_true",
        help="Set locally administered address bit (U/L bit = 1)."
    )
    parser.add_argument(
        "--multicast",
        action="store_true",
        help="Set multicast/group address bit (I/G bit = 1)."
    )

    args = parser.parse_args()

    # Determine prefix hex digits
    prefix_hex = ""
    if args.prefix:
        p_lower = args.prefix.lower()
        if p_lower in VENDORS:
            prefix_hex = clean_hex(VENDORS[p_lower])
        else:
            prefix_hex = clean_hex(args.prefix)
            if not prefix_hex or any(c not in '0123456789abcdefABCDEF' for c in prefix_hex):
                print(f"[ERROR] Invalid prefix format: '{args.prefix}'. Must be hex characters.")
                sys.exit(1)
            if len(prefix_hex) > 12:
                print(f"[ERROR] Prefix is too long: '{args.prefix}'. Max 12 hex digits (6 bytes).")
                sys.exit(1)

    print(f"Generating {args.count} MAC address(es)...")
    print("-" * 40)
    for _ in range(args.count):
        mac = generate_mac(prefix_hex, args.delimiter, args.uppercase, args.local, args.multicast)
        print(mac)
    print("-" * 40)
    print(f"[OK] Successfully generated {args.count} MAC address(es).")
    sys.exit(0)

if __name__ == "__main__":
    main()
