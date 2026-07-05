#!/usr/bin/env python3
"""
CSV Column Data Type Cast & Schema Compliance Validator

Audits CSV files against explicit or inferred column data types (int, float, bool,
date, datetime, email, uuid, ip, regex), reports invalid cell coordinates,
and optionally repairs/scrubs invalid cells to generate a cleaned CSV dataset.

Usage:
    python tools/csv_column_type_cast_validator.py data.csv
    python tools/csv_column_type_cast_validator.py data.csv --schema '{"age":"int","email":"email"}'
    python tools/csv_column_type_cast_validator.py data.csv --output cleaned_data.csv
"""

import csv
import sys
import os
import re
import json
import uuid
import datetime
import ipaddress
import argparse
from typing import Dict, Any, List, Tuple, Optional

# ANSI Colors
COLOR_HEADER = "\033[95m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"


def is_color_enabled() -> bool:
    return sys.stdout.isatty() and os.name != 'nt' or os.getenv('COLORTERM') is not None or os.name == 'nt'


def colorize(text: str, color_code: str) -> str:
    if is_color_enabled():
        return f"{color_code}{text}{COLOR_RESET}"
    return text


EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def validate_type_cast(val: str, expected_type: str) -> Tuple[bool, Any]:
    """Check if string value can be cast to expected data type."""
    val_stripped = val.strip()
    if not val_stripped:
        return True, None  # Empty cells treated as missing/null, not type failure

    t = expected_type.lower()

    if t in ("int", "integer"):
        try:
            return True, int(val_stripped)
        except ValueError:
            return False, f"Cannot cast '{val}' to integer"

    elif t in ("float", "double", "decimal", "number"):
        try:
            return True, float(val_stripped)
        except ValueError:
            return False, f"Cannot cast '{val}' to float"

    elif t in ("bool", "boolean"):
        if val_stripped.lower() in ("true", "1", "yes", "y", "t"):
            return True, True
        elif val_stripped.lower() in ("false", "0", "no", "n", "f"):
            return True, False
        return False, f"Cannot cast '{val}' to boolean"

    elif t == "email":
        if EMAIL_REGEX.match(val_stripped):
            return True, val_stripped
        return False, f"Invalid email format: '{val}'"

    elif t == "uuid":
        try:
            uuid.UUID(val_stripped)
            return True, val_stripped
        except ValueError:
            return False, f"Invalid UUID format: '{val}'"

    elif t in ("ip", "ipv4", "ipv6"):
        try:
            ipaddress.ip_address(val_stripped)
            return True, val_stripped
        except ValueError:
            return False, f"Invalid IP address: '{val}'"

    elif t == "date":
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
            try:
                dt = datetime.datetime.strptime(val_stripped, fmt).date()
                return True, dt.isoformat()
            except ValueError:
                pass
        return False, f"Invalid ISO date: '{val}'"

    elif t in ("datetime", "timestamp"):
        try:
            dt = datetime.datetime.fromisoformat(val_stripped.replace("Z", "+00:00"))
            return True, dt.isoformat()
        except ValueError:
            pass
        return False, f"Invalid ISO datetime: '{val}'"

    elif t == "str" or t == "string" or t == "text":
        return True, val

    return True, val


def infer_column_types(rows: List[Dict[str, str]], headers: List[str]) -> Dict[str, str]:
    """Infer likely data types for columns based on data rows."""
    inferred = {}
    sample_rows = rows[:100]

    for col in headers:
        values = [r[col].strip() for r in sample_rows if col in r and r[col].strip()]
        if not values:
            inferred[col] = "string"
            continue

        # Check types in order of specificity
        is_int = True
        is_float = True
        is_bool = True
        is_email = True
        is_uuid = True
        is_date = True

        for v in values:
            # int check
            try:
                int(v)
            except ValueError:
                is_int = False

            # float check
            try:
                float(v)
            except ValueError:
                is_float = False

            # bool check
            if v.lower() not in ("true", "false", "1", "0", "yes", "no"):
                is_bool = False

            # email check
            if not EMAIL_REGEX.match(v):
                is_email = False

            # uuid check
            try:
                uuid.UUID(v)
            except ValueError:
                is_uuid = False

            # date check
            d_ok = False
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
                try:
                    datetime.datetime.strptime(v, fmt)
                    d_ok = True
                    break
                except ValueError:
                    pass
            if not d_ok:
                is_date = False

        if is_uuid:
            inferred[col] = "uuid"
        elif is_email:
            inferred[col] = "email"
        elif is_bool:
            inferred[col] = "boolean"
        elif is_int:
            inferred[col] = "integer"
        elif is_float:
            inferred[col] = "float"
        elif is_date:
            inferred[col] = "date"
        else:
            inferred[col] = "string"

    return inferred


def audit_csv(
    filepath: str,
    schema_dict: Optional[Dict[str, str]] = None,
    output_clean_path: Optional[str] = None
) -> Dict[str, Any]:
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        rows = list(reader)

    if schema_dict:
        schema = {k: v for k, v in schema_dict.items() if k in headers}
        # Default unmentioned headers to string
        for h in headers:
            if h not in schema:
                schema[h] = "string"
    else:
        schema = infer_column_types(rows, headers)

    violations = []
    cleaned_rows = []

    for row_idx, row in enumerate(rows, start=2):  # 1-indexed, line 1 is header
        clean_row = {}
        for col_name in headers:
            val = row.get(col_name, "")
            expected_t = schema.get(col_name, "string")
            ok, cast_res = validate_type_cast(val, expected_t)

            if not ok:
                violations.append({
                    "row": row_idx,
                    "column": col_name,
                    "value": val,
                    "expected_type": expected_t,
                    "error": cast_res
                })
                clean_row[col_name] = ""  # scrub invalid cell in output
            else:
                clean_row[col_name] = val
        cleaned_rows.append(clean_row)

    if output_clean_path:
        with open(output_clean_path, "w", encoding="utf-8", newline="") as f_out:
            writer = csv.DictWriter(f_out, fieldnames=headers)
            writer.writeheader()
            writer.writerows(cleaned_rows)

    return {
        "filepath": filepath,
        "total_rows": len(rows),
        "total_columns": len(headers),
        "schema": schema,
        "total_violations": len(violations),
        "violations": violations,
        "clean_output_saved": output_clean_path
    }


def print_report(results: Dict[str, Any]):
    print("=" * 72)
    print(colorize("  CSV Column Data Type Cast & Schema Validation Report", COLOR_BOLD + COLOR_HEADER))
    print("=" * 72)
    print(f"  File Path:      {results['filepath']}")
    print(f"  Total Rows:     {results['total_rows']}")
    print(f"  Total Columns:  {results['total_columns']}")
    print(f"  Type Errors:    {results['total_violations']}")
    print("-" * 72)

    print(f"\n[{colorize('SCHEMA', COLOR_CYAN)}] Configured / Inferred Column Schema:")
    for col, stype in results["schema"].items():
        print(f"  • {colorize(col, COLOR_BOLD)}: {colorize(stype, COLOR_YELLOW)}")

    if results["violations"]:
        print(f"\n[{colorize('VIOLATIONS', COLOR_RED)}] Data Type Mismatches Found:")
        for v in results["violations"][:50]:  # Limit output
            print(f"  └─ Row {v['row']}, Col '{colorize(v['column'], COLOR_CYAN)}': Value '{colorize(v['value'], COLOR_RED)}' -> {v['error']} (Expected {v['expected_type']})")
        if len(results["violations"]) > 50:
            print(f"  ... and {len(results['violations']) - 50} more violations.")
    else:
        print(colorize("\n  ✓ All rows match the expected column schemas perfectly!\n", COLOR_GREEN + COLOR_BOLD))

    if results["clean_output_saved"]:
        print(colorize(f"\n  Cleaned dataset saved to: {results['clean_output_saved']}", COLOR_GREEN))
    print("=" * 72 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Audit CSV files for column data type casting violations and generate clean datasets."
    )
    parser.add_argument("csv_file", help="Path to input CSV file")
    parser.add_argument("--schema", help="JSON string of column to type mappings, e.g. '{\"age\":\"int\",\"email\":\"email\"}'")
    parser.add_argument("--output", "-o", help="Path to save cleaned CSV with invalid cells scrubbed")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    args = parser.parse_args()

    schema_dict = None
    if args.schema:
        try:
            schema_dict = json.loads(args.schema)
        except json.JSONDecodeError as ex:
            print(colorize(f"Error parsing --schema JSON: {ex}", COLOR_RED), file=sys.stderr)
            sys.exit(1)

    results = audit_csv(args.csv_file, schema_dict=schema_dict, output_clean_path=args.output)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_report(results)

    sys.exit(0 if results["total_violations"] == 0 else 1)


if __name__ == "__main__":
    main()
