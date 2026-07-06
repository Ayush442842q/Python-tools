#!/usr/bin/env python3
"""
SQLite Table Pivot Generator
Dynamically constructs and executes SQL `CASE...WHEN` cross-tabulation / pivot queries on SQLite database tables
or custom SQL queries. Formats pivoted data as CLI tables, CSV, or Markdown.
"""

import sqlite3
import sys
import os
import argparse
from typing import List, Dict, Any, Tuple, Optional

# Console colors
COLOR_RESET = "\033[0m"
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"


def build_pivot_sql(
    conn: sqlite3.Connection,
    source_table: str,
    index_col: str,
    pivot_col: str,
    value_col: str,
    agg_func: str = "SUM",
    where_clause: Optional[str] = None
) -> Tuple[str, List[str]]:
    """
    Scans distinct column pivot values and constructs an aggregated SQL CASE-WHEN query.
    """
    agg_func = agg_func.upper()
    if agg_func not in ("SUM", "COUNT", "AVG", "MIN", "MAX"):
        agg_func = "SUM"

    # Get distinct pivot column values
    distinct_query = f"SELECT DISTINCT [{pivot_col}] FROM ({source_table}) WHERE [{pivot_col}] IS NOT NULL ORDER BY [{pivot_col}]"
    cursor = conn.cursor()
    cursor.execute(distinct_query)
    pivot_values = [row[0] for row in cursor.fetchall()]

    case_clauses = []
    col_names = [index_col]

    for val in pivot_values:
        val_str = str(val).replace("'", "''")
        col_alias = f"{pivot_col}_{val}"
        col_names.append(col_alias)

        if agg_func == "COUNT":
            case_expr = f"COUNT(CASE WHEN [{pivot_col}] = '{val_str}' THEN 1 END)"
        else:
            case_expr = f"{agg_func}(CASE WHEN [{pivot_col}] = '{val_str}' THEN [{value_col}] END)"

        case_clauses.append(f"  {case_expr} AS [{col_alias}]")

    where_sql = f" WHERE {where_clause}" if where_clause else ""
    select_cases = ",\n".join(case_clauses)

    sql_query = f"""SELECT
  [{index_col}],
{select_cases}
FROM ({source_table})
{where_sql}
GROUP BY [{index_col}]
ORDER BY [{index_col}];"""

    return sql_query, col_names


def format_table(headers: List[str], rows: List[List[Any]]) -> str:
    """Formats rows into an ASCII table string."""
    col_widths = [len(str(h)) for h in headers]
    for row in rows:
        for idx, val in enumerate(row):
            str_val = str(val) if val is not None else ""
            if len(str_val) > col_widths[idx]:
                col_widths[idx] = len(str_val)

    header_line = " | ".join(f"{str(h):<{col_widths[i]}}" for i, h in enumerate(headers))
    separator = "-+-".join("-" * col_widths[i] for i in range(len(headers)))
    row_lines = [
        " | ".join(f"{(str(val) if val is not None else ''):<{col_widths[i]}}" for i, val in enumerate(row))
        for row in rows
    ]

    return f"{header_line}\n{separator}\n" + "\n".join(row_lines)


def format_markdown(headers: List[str], rows: List[List[Any]]) -> str:
    """Formats rows into Markdown table syntax."""
    header_line = "| " + " | ".join(str(h) for h in headers) + " |"
    separator = "| " + " | ".join("---" for _ in headers) + " |"
    row_lines = [
        "| " + " | ".join((str(val) if val is not None else "") for val in row) + " |"
        for row in rows
    ]
    return "\n".join([header_line, separator] + row_lines)


def run_demo() -> None:
    """Runs demonstration mode using an in-memory SQLite sales database."""
    print(f"{COLOR_BOLD}{COLOR_CYAN}=== SQLite Table Pivot Generator Demo ==={COLOR_RESET}\n")

    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE sales (
            id INTEGER PRIMARY KEY,
            region TEXT,
            quarter TEXT,
            revenue REAL
        );
    """)

    sample_sales = [
        ("North", "Q1", 12000.0),
        ("North", "Q2", 15500.0),
        ("North", "Q3", 14000.0),
        ("North", "Q4", 18000.0),
        ("South", "Q1", 9000.0),
        ("South", "Q2", 11000.0),
        ("South", "Q3", 10500.0),
        ("South", "Q4", 13000.0),
        ("East", "Q1", 16000.0),
        ("East", "Q2", 17500.0),
        ("East", "Q3", 19000.0),
        ("East", "Q4", 22000.0),
    ]

    cursor.executemany("INSERT INTO sales (region, quarter, revenue) VALUES (?, ?, ?);", sample_sales)
    conn.commit()

    print(f"{COLOR_BOLD}Base Table: `sales` (Region x Quarter x Revenue){COLOR_RESET}\n")

    pivot_sql, col_names = build_pivot_sql(
        conn=conn,
        source_table="SELECT * FROM sales",
        index_col="region",
        pivot_col="quarter",
        value_col="revenue",
        agg_func="SUM"
    )

    print(f"{COLOR_BOLD}{COLOR_GREEN}Generated SQL Pivot Query:{COLOR_RESET}")
    print(pivot_sql)
    print()

    cursor.execute(pivot_sql)
    rows = cursor.fetchall()

    print(f"{COLOR_BOLD}Pivoted Result Table (Terminal Output):{COLOR_RESET}")
    print(format_table(col_names, [list(r) for r in rows]))
    print()

    print(f"{COLOR_BOLD}Pivoted Result Table (Markdown Output):{COLOR_RESET}")
    print(format_markdown(col_names, [list(r) for r in rows]))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generates dynamic SQL CASE-WHEN pivot queries and executes cross-tabulations on SQLite tables."
    )
    parser.add_argument("-d", "--database", help="Path to SQLite database file")
    parser.add_argument("-t", "--table", help="Source table name or SQL subquery (e.g. 'sales' or 'SELECT * FROM orders')")
    parser.add_argument("-i", "--index", help="Row dimension column name (e.g. 'region')")
    parser.add_argument("-p", "--pivot", help="Column pivot dimension column name (e.g. 'quarter')")
    parser.add_argument("-v", "--values", help="Measure field column name (e.g. 'revenue')")
    parser.add_argument("-a", "--agg", default="SUM", choices=["SUM", "COUNT", "AVG", "MIN", "MAX"], help="Aggregation function")
    parser.add_argument("-w", "--where", help="Optional WHERE filter clause")
    parser.add_argument("-f", "--format", default="table", choices=["table", "csv", "markdown"], help="Output format")
    parser.add_argument("--demo", action="store_true", help="Run demonstration mode with sample in-memory database")

    args = parser.parse_args()

    if args.demo or not (args.database and args.table and args.index and args.pivot and args.values):
        if not args.demo:
            print(f"{COLOR_YELLOW}Missing required parameters. Running demo mode...{COLOR_RESET}\n")
        run_demo()
        return

    if not os.path.exists(args.database):
        print(f"{COLOR_RED}Error: Database file '{args.database}' not found.{COLOR_RESET}")
        sys.exit(1)

    conn = sqlite3.connect(args.database)
    source = args.table if " " in args.table else f"SELECT * FROM [{args.table}]"

    try:
        pivot_sql, col_names = build_pivot_sql(
            conn=conn,
            source_table=source,
            index_col=args.index,
            pivot_col=args.pivot,
            value_col=args.values,
            agg_func=args.agg,
            where_clause=args.where
        )

        cursor = conn.cursor()
        cursor.execute(pivot_sql)
        rows = [list(r) for r in cursor.fetchall()]

        if args.format == "csv":
            import csv
            writer = csv.writer(sys.stdout)
            writer.writerow(col_names)
            writer.writerows(rows)
        elif args.format == "markdown":
            print(format_markdown(col_names, rows))
        else:
            print(f"{COLOR_BOLD}{COLOR_GREEN}SQL Query Executed:{COLOR_RESET}\n{pivot_sql}\n")
            print(format_table(col_names, rows))

    except sqlite3.Error as e:
        print(f"{COLOR_RED}SQLite Error: {e}{COLOR_RESET}")
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
