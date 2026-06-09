"""
Epoch Converter Tool
Converts Unix timestamps (epoch) to human-readable datetime formats (UTC and local) and vice versa.
"""
import argparse
from datetime import datetime, timezone
import sys

def parse_datetime(dt_str, fmt=None):
    # Try custom format first if provided
    if fmt:
        try:
            return datetime.strptime(dt_str, fmt)
        except ValueError:
            pass
            
    # Try list of common formats
    formats = [
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%d",
        "%d/%m/%Y %H:%M:%S",
        "%m/%d/%Y %H:%M:%S",
    ]
    
    for f in formats:
        try:
            return datetime.strptime(dt_str, f)
        except ValueError:
            continue
            
    # ISO 8601 parsing fallback using fromisoformat if available
    try:
        cleaned = dt_str.replace('Z', '+00:00')
        return datetime.fromisoformat(cleaned)
    except ValueError:
        pass
        
    return None

def main():
    parser = argparse.ArgumentParser(
        description="Convert Unix timestamps (epoch) to human-readable datetime and vice versa."
    )
    
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "-t", "--timestamp",
        type=float,
        help="Unix timestamp to convert. Supports seconds, milliseconds, or microseconds."
    )
    group.add_argument(
        "-d", "--datetime",
        help="Datetime string to convert. e.g. '2026-06-09 12:00:00'."
    )
    
    parser.add_argument(
        "-f", "--format",
        help="Custom format for output or input datetime string (e.g. '%%Y-%%m-%%d %%H:%%M:%%S')."
    )
    parser.add_argument(
        "-u", "--utc",
        action="store_true",
        help="Assume UTC timezone for datetime inputs. By default, local timezone is assumed."
    )
    
    args = parser.parse_args()

    default_fmt = args.format if args.format else "%Y-%m-%d %H:%M:%S"

    # If neither timestamp nor datetime is provided, default to current time
    if args.timestamp is None and args.datetime is None:
        now = datetime.now()
        args.timestamp = now.timestamp()
        print("[INFO] No input specified. Using current system time.")

    if args.timestamp is not None:
        ts = args.timestamp
        # Detect if milliseconds or microseconds
        # If timestamp is very large (e.g., > 3e10, which corresponds to year 2920+ in seconds),
        # it might be in milliseconds (or microseconds)
        original_ts = ts
        unit = "seconds"
        if ts > 1e14:  # Microseconds
            ts = ts / 1e6
            unit = "microseconds"
        elif ts > 3e10:  # Milliseconds
            ts = ts / 1e3
            unit = "milliseconds"

        try:
            # Create timezone-aware UTC datetime
            dt_utc = datetime.fromtimestamp(ts, tz=timezone.utc)
            # Create local datetime
            dt_local = datetime.fromtimestamp(ts)
            
            print("[OK] Conversion complete:")
            print(f"  Input Epoch: {original_ts} ({unit})")
            print(f"  Normalized Epoch (sec): {ts:.6f}")
            print(f"  UTC Time:    {dt_utc.strftime(default_fmt)} UTC")
            print(f"  Local Time:  {dt_local.strftime(default_fmt)}")
        except Exception as e:
            print(f"[ERROR] Failed to convert timestamp: {e}")
            sys.exit(1)

    elif args.datetime is not None:
        dt = parse_datetime(args.datetime, args.format)
        if dt is None:
            print(f"[ERROR] Could not parse datetime string: '{args.datetime}'")
            print("Try specifying a custom format using --format.")
            sys.exit(1)
            
        # Check if the parsed datetime has timezone info
        if dt.tzinfo is not None:
            # Timezone-aware
            ts = dt.timestamp()
            tz_str = str(dt.tzinfo)
        else:
            # Naive datetime
            if args.utc:
                dt = dt.replace(tzinfo=timezone.utc)
                ts = dt.timestamp()
                tz_str = "UTC"
            else:
                # Assume local time
                ts = dt.timestamp()
                tz_str = "Local (system)"

        print("[OK] Conversion complete:")
        print(f"  Input Datetime: {args.datetime} ({tz_str})")
        print(f"  Epoch (seconds): {int(ts)}")
        print(f"  Epoch (milliseconds): {int(ts * 1000)}")
        print(f"  Epoch (microseconds): {int(ts * 1000000)}")

    sys.exit(0)

if __name__ == "__main__":
    main()
