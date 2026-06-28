#!/usr/bin/env python3
"""
Structured JSON Log Viewer
Parses, filters, search, and pretty-prints JSON-structured logs in the terminal.
Supports reading from files or piping via stdin.
"""

import sys
import json
import argparse
import datetime
from typing import Dict, Any, Optional

# ANSI color codes for terminal formatting
COLORS = {
    "BLUE": "\033[94m",
    "CYAN": "\033[96m",
    "GREEN": "\033[92m",
    "YELLOW": "\033[93m",
    "RED": "\033[91m",
    "MAGENTA": "\033[95m",
    "BOLD": "\033[1m",
    "DIM": "\033[2m",
    "RESET": "\033[0m"
}

LEVEL_COLORS = {
    "DEBUG": COLORS["MAGENTA"],
    "TRACE": COLORS["DIM"] + COLORS["MAGENTA"],
    "INFO": COLORS["GREEN"],
    "WARN": COLORS["YELLOW"],
    "WARNING": COLORS["YELLOW"],
    "ERROR": COLORS["RED"],
    "CRITICAL": COLORS["RED"] + COLORS["BOLD"],
    "FATAL": COLORS["RED"] + COLORS["BOLD"]
}

# Common keys for standard fields in JSON logs
TIMESTAMP_KEYS = ["time", "ts", "timestamp", "@timestamp", "datetime", "date"]
LEVEL_KEYS = ["level", "lvl", "severity", "log.level", "status"]
MESSAGE_KEYS = ["message", "msg", "log", "text", "content", "msg_content"]
LOGGER_KEYS = ["logger", "name", "logger_name", "category", "component"]
EXCEPTION_KEYS = ["exception", "stack_trace", "traceback", "err", "error"]

def get_field(data: Dict[str, Any], keys: list) -> Optional[Any]:
    """Retrieve field value from dictionary trying a list of potential keys, including nested keys."""
    for key in keys:
        if "." in key:
            # Handle nested fields like log.level
            parts = key.split(".")
            val = data
            for part in parts:
                if isinstance(val, dict) and part in val:
                    val = val[part]
                else:
                    val = None
                    break
            if val is not None:
                return val
        elif key in data:
            return data[key]
    return None

def format_timestamp(ts: Any) -> str:
    """Format timestamp into a readable string."""
    if not ts:
        return ""
    if isinstance(ts, (int, float)):
        try:
            # Handle milliseconds vs seconds
            if ts > 1e11:
                ts /= 1000.0
            dt = datetime.datetime.fromtimestamp(ts)
            return dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        except Exception:
            pass
    return str(ts)

def match_query(data: Dict[str, Any], query_dict: Dict[str, str]) -> bool:
    """Check if all key=val conditions in query_dict match the data."""
    for q_key, q_val in query_dict.items():
        val = get_field(data, [q_key])
        if val is None:
            return False
        if str(q_val).lower() not in str(val).lower():
            return False
    return True

def process_line(line: str, args: argparse.Namespace) -> None:
    """Parse, filter, and pretty-print a single line of log input."""
    line = line.strip()
    if not line:
        return

    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        # Fallback for non-JSON logs: print in dim/gray text if not filtering
        if not args.json_only and not args.level and not args.query and not args.search:
            print(f"{COLORS['DIM']}{line}{COLORS['RESET']}")
        return

    # Extract core fields
    level_val = get_field(data, LEVEL_KEYS)
    level = str(level_val).upper() if level_val is not None else "INFO"
    
    # Filter by minimum level
    if args.level:
        target_level_idx = args.level_val_map.get(args.level.upper(), 0)
        curr_level_idx = args.level_val_map.get(level, 20)  # Default to info level if unknown
        if curr_level_idx < target_level_idx:
            return

    # Filter by key=value query
    if args.query_dict and not match_query(data, args.query_dict):
        return

    message = get_field(data, MESSAGE_KEYS) or ""
    message_str = str(message)
    
    # Filter by text search
    if args.search and args.search.lower() not in message_str.lower():
        return

    timestamp = format_timestamp(get_field(data, TIMESTAMP_KEYS))
    logger = get_field(data, LOGGER_KEYS)
    exception = get_field(data, EXCEPTION_KEYS)

    # Clean up standard keys from the rest of the metadata
    meta = data.copy()
    for keys in [TIMESTAMP_KEYS, LEVEL_KEYS, MESSAGE_KEYS, LOGGER_KEYS, EXCEPTION_KEYS]:
        for k in keys:
            if "." in k:
                parts = k.split(".")
                curr = meta
                for part in parts[:-1]:
                    if isinstance(curr, dict) and part in curr:
                        curr = curr[part]
                if isinstance(curr, dict) and parts[-1] in curr:
                    del curr[parts[-1]]
            elif k in meta:
                del meta[k]

    # Format output parts
    output_parts = []
    
    # 1. Timestamp
    if timestamp:
        output_parts.append(f"{COLORS['BLUE']}{timestamp}{COLORS['RESET']}")
        
    # 2. Level (Color-coded)
    lvl_color = LEVEL_COLORS.get(level, COLORS['RESET'])
    output_parts.append(f"{lvl_color}[{level:5}]{COLORS['RESET']}")
    
    # 3. Logger/Component
    if logger:
        output_parts.append(f"{COLORS['CYAN']}[{logger}]{COLORS['RESET']}")
        
    # 4. Message
    output_parts.append(message_str)
    
    print(" ".join(output_parts))

    # 5. Metadata (Optional)
    if args.show_meta and meta:
        # Filter metadata by specified fields if any
        if args.fields:
            meta = {k: v for k, v in meta.items() if k in args.fields}
        if meta:
            meta_json = json.dumps(meta, indent=2)
            # Indent metadata for readability
            indented = "\n".join("  " + l for l in meta_json.split("\n"))
            print(f"{COLORS['DIM']}{indented}{COLORS['RESET']}")

    # 6. Exception Stack Trace
    if exception:
        exc_str = ""
        if isinstance(exception, dict):
            exc_str = exception.get("message", "") or exception.get("detail", "") or json.dumps(exception, indent=2)
            stack = exception.get("stack", "") or exception.get("stack_trace", "") or exception.get("traceback", "")
            if stack:
                exc_str += f"\n{stack}"
        else:
            exc_str = str(exception)
            
        indented_exc = "\n".join("  " + l for l in exc_str.split("\n"))
        print(f"{COLORS['RED']}{indented_exc}{COLORS['RESET']}")

def main():
    parser = argparse.ArgumentParser(
        description="Structured JSON Log Viewer. Read, filter, and pretty-print JSON logs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  cat app.log | python tools/json_log_viewer.py --show-meta
  python tools/json_log_viewer.py app.log --level error
  python tools/json_log_viewer.py app.log --query userId=42 --search "database"
        """
    )
    parser.add_argument("file", nargs="?", help="Log file to read (reads from stdin if omitted)")
    parser.add_argument("-l", "--level", help="Minimum log level to show (DEBUG, INFO, WARN, ERROR, CRITICAL)")
    parser.add_argument("-s", "--search", help="Substring search query for the message field")
    parser.add_argument("-q", "--query", action="append", help="Filter by metadata key=value pair (can be repeated)")
    parser.add_argument("-m", "--show-meta", action="store_true", help="Print extra JSON metadata fields")
    parser.add_argument("-f", "--fields", help="Comma-separated metadata fields to include (requires -m)")
    parser.add_argument("--json-only", action="store_true", help="Ignore lines that are not valid JSON")

    args = parser.parse_args()

    # Log level values for comparison
    args.level_val_map = {
        "TRACE": 5,
        "DEBUG": 10,
        "INFO": 20,
        "WARN": 30,
        "WARNING": 30,
        "ERROR": 40,
        "CRITICAL": 50,
        "FATAL": 50
    }

    # Parse query arguments into dictionary
    args.query_dict = {}
    if args.query:
        for q in args.query:
            if "=" in q:
                k, v = q.split("=", 1)
                args.query_dict[k.strip()] = v.strip()
            else:
                print(f"Warning: Invalid query filter '{q}', must be in key=value format.", file=sys.stderr)

    # Parse fields to show
    args.fields = [f.strip() for f in args.fields.split(",")] if args.fields else []

    # Read log lines
    try:
        if args.file:
            with open(args.file, "r", encoding="utf-8") as f:
                for line in f:
                    process_line(line, args)
        else:
            # Check if stdin is a TTY
            if sys.stdin.isatty():
                parser.print_help()
                return
            for line in sys.stdin:
                process_line(line, args)
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
