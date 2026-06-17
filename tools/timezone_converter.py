#!/usr/bin/env python3
"""
Timezone Converter & Global Clock Utility
Provides timezone conversions, local/GMT comparisons, and world clocks.
"""
import argparse
from datetime import datetime, timedelta, timezone
import sys
import re

# Fallback database of common timezones with standard offsets (in hours from UTC)
# and DST offsets if applicable. Used if zoneinfo is not available or has no data.
COMMON_TIMEZONES = {
    "UTC": {"offset": 0, "name": "Coordinated Universal Time"},
    "GMT": {"offset": 0, "name": "Greenwich Mean Time"},
    "BST": {"offset": 1, "name": "British Summer Time"},
    "CET": {"offset": 1, "name": "Central European Time"},
    "CEST": {"offset": 2, "name": "Central European Summer Time"},
    "EET": {"offset": 2, "name": "Eastern European Time"},
    "EEST": {"offset": 3, "name": "Eastern European Summer Time"},
    "MSK": {"offset": 3, "name": "Moscow Standard Time"},
    "IST": {"offset": 5.5, "name": "Indian Standard Time"},
    "PKT": {"offset": 5, "name": "Pakistan Standard Time"},
    "BST-BD": {"offset": 6, "name": "Bangladesh Standard Time"},
    "ICT": {"offset": 7, "name": "Indochina Time"},
    "CST-CN": {"offset": 8, "name": "China Standard Time"},
    "SGT": {"offset": 8, "name": "Singapore Standard Time"},
    "JST": {"offset": 9, "name": "Japan Standard Time"},
    "KST": {"offset": 9, "name": "Korea Standard Time"},
    "AEST": {"offset": 10, "name": "Australian Eastern Standard Time"},
    "AEDT": {"offset": 11, "name": "Australian Eastern Daylight Time"},
    "NZST": {"offset": 12, "name": "New Zealand Standard Time"},
    "NZDT": {"offset": 13, "name": "New Zealand Daylight Time"},
    "HST": {"offset": -10, "name": "Hawaii Standard Time"},
    "AKST": {"offset": -9, "name": "Alaska Standard Time"},
    "AKDT": {"offset": -8, "name": "Alaska Daylight Time"},
    "PST": {"offset": -8, "name": "Pacific Standard Time"},
    "PDT": {"offset": -7, "name": "Pacific Daylight Time"},
    "MST": {"offset": -7, "name": "Mountain Standard Time"},
    "MDT": {"offset": -6, "name": "Mountain Daylight Time"},
    "CST": {"offset": -6, "name": "Central Standard Time"},
    "CDT": {"offset": -5, "name": "Central Daylight Time"},
    "EST": {"offset": -5, "name": "Eastern Standard Time"},
    "EDT": {"offset": -4, "name": "Eastern Daylight Time"},
    "AST": {"offset": -4, "name": "Atlantic Standard Time"},
    "ADT": {"offset": -3, "name": "Atlantic Daylight Time"},
    "ART": {"offset": -3, "name": "Argentina Time"},
    "BRT": {"offset": -3, "name": "Brasilia Time"},
    "BRST": {"offset": -2, "name": "Brasilia Summer Time"},
}

# Mapping of region/city patterns to common offsets
CITY_TIMEZONES = [
    (r"london", "GMT", "BST"),
    (r"paris|berlin|rome|madrid|amsterdam|brussels|vienna|warsaw", "CET", "CEST"),
    (r"athens|cairo|helsinki|istanbul|kyiv|bucharest", "EET", "EEST"),
    (r"moscow|st Petersburg", "MSK", "MSK"),
    (r"dubai|abu dhabi", "GST", None, 4),
    (r"mumbai|delhi|kolkata|bangalore", "IST", "IST"),
    (r"karachi", "PKT", "PKT"),
    (r"dhaka", "BST-BD", "BST-BD"),
    (r"bangkok|hanoi|jakarta", "ICT", "ICT"),
    (r"beijing|shanghai|hong kong|singapore|taipei|perth", "CST-CN", "CST-CN"),
    (r"tokyo|osaka|seoul", "JST", "JST"),
    (r"sydney|melbourne|brisbane", "AEST", "AEDT"),
    (r"auckland|wellington", "NZST", "NZDT"),
    (r"honolulu", "HST", "HST"),
    (r"anchorage", "AKST", "AKDT"),
    (r"los angeles|san francisco|seattle|vancouver", "PST", "PDT"),
    (r"denver|phoenix|salt lake city|calgary", "MST", "MDT"),
    (r"chicago|houston|mexico city|winnipeg", "CST", "CDT"),
    (r"new york|boston|washington|miami|montreal|toronto", "EST", "EDT"),
    (r"halifax", "AST", "ADT"),
    (r"buenos aires|sao paulo|rio de janeiro", "ART", "BRST"),
]

def get_zoneinfo_tz(tz_name):
    """Attempt to load timezone via zoneinfo module (Python 3.9+)."""
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(tz_name)
    except Exception:
        try:
            import pytz
            return pytz.timezone(tz_name)
        except Exception:
            return None

def parse_timezone_offset(tz_str):
    """
    Parse a timezone string which could be:
    - Name/abbreviation (e.g. UTC, EST, JST)
    - City/region (e.g. America/New_York, Europe/London)
    - Custom offset (e.g. +5.5, -8, +05:30)
    """
    tz_str = tz_str.strip()
    
    # Check if it is a numeric offset (+5, -8.5, +05:30, etc.)
    offset_match = re.match(r"^([+-]?)(\d{1,2})(?::(\d{2}))?$", tz_str)
    if offset_match:
        sign = -1 if offset_match.group(1) == "-" else 1
        hours = int(offset_match.group(2))
        minutes = int(offset_match.group(3)) if offset_match.group(3) else 0
        total_minutes = sign * (hours * 60 + minutes)
        return timezone(timedelta(minutes=total_minutes)), f"UTC{tz_str}"

    # Try zoneinfo or pytz first
    tz_obj = get_zoneinfo_tz(tz_str)
    if tz_obj:
        return tz_obj, tz_str

    # Look up in standard abbreviation database
    tz_upper = tz_str.upper()
    if tz_upper in COMMON_TIMEZONES:
        info = COMMON_TIMEZONES[tz_upper]
        offset_hours = info["offset"]
        tz_delta = timedelta(hours=offset_hours)
        return timezone(tz_delta), tz_upper

    # Look up by searching cities
    tz_lower = tz_str.lower()
    for pattern, std_tz, dst_tz in CITY_TIMEZONES:
        if re.search(pattern, tz_lower):
            # Check if current date would use DST (simplified estimate)
            # Standard US/EU DST is roughly Mar - Nov.
            now = datetime.now()
            use_dst = dst_tz and (3 <= now.month <= 10)
            target_tz = dst_tz if use_dst else std_tz
            if target_tz in COMMON_TIMEZONES:
                info = COMMON_TIMEZONES[target_tz]
                return timezone(timedelta(hours=info["offset"])), f"{tz_str} ({target_tz})"

    # Handle raw integers like 5 or -8 directly as hours
    try:
        hours = float(tz_str)
        return timezone(timedelta(hours=hours)), f"UTC{'+' if hours >= 0 else ''}{hours}"
    except ValueError:
        pass

    return None, None

def get_current_time_in_tz(tz_obj):
    """Get the current time localized to a specific timezone object."""
    now_utc = datetime.now(timezone.utc)
    try:
        return now_utc.astimezone(tz_obj)
    except Exception:
        # Fallback for manual timezone info objects
        return now_utc.astimezone(tz_obj)

def print_world_clock():
    """Display current time in major cities around the world."""
    cities = [
        ("London", "Europe/London", "GMT/BST"),
        ("Paris", "Europe/Paris", "CET/CEST"),
        ("Moscow", "Europe/Moscow", "MSK"),
        ("New Delhi", "Asia/Kolkata", "IST"),
        ("Singapore", "Asia/Singapore", "SGT"),
        ("Tokyo", "Asia/Tokyo", "JST"),
        ("Sydney", "Australia/Sydney", "AEST/AEDT"),
        ("New York", "America/New_York", "EST/EDT"),
        ("Chicago", "America/Chicago", "CST/CDT"),
        ("Los Angeles", "America/Los_Angeles", "PST/PDT"),
    ]
    
    print("\n=== World Clock ===")
    print(f"{'City':<15} | {'Timezone':<20} | {'Current Date & Time':<25} | {'Offset':<10}")
    print("-" * 78)
    
    now_utc = datetime.now(timezone.utc)
    
    for city, tz_name, abbrev in cities:
        tz_obj, _ = parse_timezone_offset(tz_name)
        if not tz_obj:
            # Fallback to direct abbrev lookup
            tz_obj, _ = parse_timezone_offset(abbrev.split('/')[0])
            
        if tz_obj:
            dt = now_utc.astimezone(tz_obj)
            offset = dt.utcoffset()
            offset_hours = offset.total_seconds() / 3600
            offset_str = f"UTC{'+' if offset_hours >= 0 else ''}{offset_hours:g}"
            print(f"{city:<15} | {tz_name:<20} | {dt.strftime('%Y-%m-%d %H:%M:%S'):<25} | {offset_str:<10}")
        else:
            print(f"{city:<15} | {tz_name:<20} | {'Unavailable':<25} | N/A")
    print()

def main():
    parser = argparse.ArgumentParser(description="Convert and display dates/times across different timezones.")
    
    # Subcommands
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # world clock parser
    subparsers.add_parser("world", help="Show current time in major global cities")
    
    # convert parser
    convert_parser = subparsers.add_parser("convert", help="Convert a datetime from one timezone to another")
    convert_parser.add_argument("datetime", nargs="?", default="now",
                                 help="Datetime to convert (format: 'YYYY-MM-DD HH:MM:S' or 'now')")
    convert_parser.add_argument("--from-tz", "-f", default="local",
                                 help="Source timezone (default: local)")
    convert_parser.add_argument("--to-tz", "-t", required=True, nargs="+",
                                 help="Target timezone(s) to convert to (can list multiple)")
    
    # list/search parser
    list_parser = subparsers.add_parser("list", help="List or search available timezones")
    list_parser.add_argument("query", nargs="?", default="", help="Search term for timezones")

    # If no arguments, print help
    if len(sys.argv) == 1:
        parser.print_help()
        sys.exit(0)
        
    args = parser.parse_args()
    
    if args.command == "world":
        print_world_clock()
        
    elif args.command == "list":
        print("\n=== Common Timezones & Offsets ===")
        query = args.query.upper()
        count = 0
        for code, info in sorted(COMMON_TIMEZONES.items()):
            if not query or query in code or query in info["name"].upper():
                offset = info["offset"]
                offset_str = f"UTC{'+' if offset >= 0 else ''}{offset:g}"
                print(f"  {code:<10} | {offset_str:<10} | {info['name']}")
                count += 1
        print(f"\nFound {count} matching common timezones.\n")
        
    elif args.command == "convert":
        # Determine source timezone
        if args.from_tz.lower() == "local":
            src_tz = datetime.now().astimezone().tzinfo
            src_name = "Local Time"
        else:
            src_tz, src_name = parse_timezone_offset(args.from_tz)
            if not src_tz:
                print(f"Error: Unknown source timezone '{args.from_tz}'", file=sys.stderr)
                sys.exit(1)
                
        # Parse source datetime
        if args.datetime.lower() == "now":
            src_dt = datetime.now(src_tz)
        else:
            # Try multiple parsing formats
            parsed_dt = None
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d", "%H:%M:%S", "%H:%M"):
                try:
                    parsed_dt = datetime.strptime(args.datetime, fmt)
                    break
                except ValueError:
                    continue
            
            if not parsed_dt:
                print(f"Error: Invalid datetime format '{args.datetime}'. Use YYYY-MM-DD HH:MM:S", file=sys.stderr)
                sys.exit(1)
                
            # If only time was provided, use today's date
            if parsed_dt.year == 1900:
                today = datetime.now()
                parsed_dt = parsed_dt.replace(year=today.year, month=today.month, day=today.day)
                
            src_dt = parsed_dt.replace(tzinfo=src_tz)

        # Print conversion results
        print("\n=== Timezone Conversion ===")
        print(f"Source: {src_dt.strftime('%Y-%m-%d %H:%M:%S')} {src_name}")
        print("-" * 55)
        
        for target_name in args.to_tz:
            tgt_tz, tgt_resolved_name = parse_timezone_offset(target_name)
            if not tgt_tz:
                print(f"Target '{target_name}': UNKNOWN TIMEZONE", file=sys.stderr)
                continue
                
            tgt_dt = src_dt.astimezone(tgt_tz)
            offset_diff = (tgt_dt.utcoffset() - src_dt.utcoffset()).total_seconds() / 3600
            diff_str = f"{'+' if offset_diff >= 0 else ''}{offset_diff:g}h" if offset_diff != 0 else "same"
            
            print(f"Target: {tgt_dt.strftime('%Y-%m-%d %H:%M:%S')} {tgt_resolved_name:<20} (Offset: {diff_str})")
        print()

if __name__ == "__main__":
    main()
