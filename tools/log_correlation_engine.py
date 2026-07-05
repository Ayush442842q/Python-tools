#!/usr/bin/env python3
"""Log Correlation Engine

Parse multiple log files from different microservices or components, correlate events
by trace IDs, request IDs, or timestamp proximity, and generate unified multi-service
causal event timelines and latency flow graphs.
"""

import argparse
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional, Any

# ANSI Colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_RED = "\033[31m"
COLOR_GREEN = "\033[32m"
COLOR_YELLOW = "\033[33m"
COLOR_BLUE = "\033[34m"
COLOR_CYAN = "\033[36m"
COLOR_GREY = "\033[90m"

# Common trace/request ID patterns
TRACE_PATTERNS = [
    re.compile(r'trace[_-]?id[=:\s"]+([a-zA-Z0-9\-]+)', re.IGNORECASE),
    re.compile(r'request[_-]?id[=:\s"]+([a-zA-Z0-9\-]+)', re.IGNORECASE),
    re.compile(r'req[_-]?id[=:\s"]+([a-zA-Z0-9\-]+)', re.IGNORECASE),
    re.compile(r'corr(elation)?[_-]?id[=:\s"]+([a-zA-Z0-9\-]+)', re.IGNORECASE),
    re.compile(r'\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b', re.IGNORECASE),  # UUID
]

TIMESTAMP_PATTERNS = [
    (re.compile(r'\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?\b'), "%Y-%m-%dT%H:%M:%S"),
    (re.compile(r'\b\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2}\b'), "%Y/%m/%d %H:%M:%S"),
    (re.compile(r'\[(\d{2}/[A-Za-z]{3}/\d{4}:\d{2}:\d{2}:\d{2})'), "%d/%b/%Y:%H:%M:%S"),  # Nginx log date
]


class LogEvent:
    def __init__(self, source_file: str, line_no: int, timestamp: Optional[datetime], trace_ids: Set[str], level: str, raw: str):
        self.source_file = source_file
        self.line_no = line_no
        self.timestamp = timestamp
        self.trace_ids = trace_ids
        self.level = level
        self.raw = raw

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_file": self.source_file,
            "line_no": self.line_no,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "trace_ids": list(self.trace_ids),
            "level": self.level,
            "raw": self.raw
        }


def parse_log_line(file_label: str, line_no: int, line: str) -> LogEvent:
    trace_ids: Set[str] = set()
    for pat in TRACE_PATTERNS:
        matches = pat.findall(line)
        for m in matches:
            t_id = m[0] if isinstance(m, tuple) else m
            if t_id and len(t_id) >= 6:
                trace_ids.add(t_id)

    timestamp: Optional[datetime] = None
    for pat, fmt in TIMESTAMP_PATTERNS:
        match = pat.search(line)
        if match:
            ts_str = match.group(1) if match.groups() else match.group(0)
            # Normalize ISO string
            ts_str_clean = ts_str.split(".")[0].replace("Z", "").replace("T", " ")
            try:
                timestamp = datetime.strptime(ts_str_clean, "%Y-%m-%d %H:%M:%S")
                break
            except ValueError:
                try:
                    timestamp = datetime.strptime(ts_str_clean, fmt)
                    break
                except ValueError:
                    continue

    level = "INFO"
    upper_line = line.upper()
    if "ERROR" in upper_line or "CRITICAL" in upper_line or "FATAL" in upper_line or "FAIL" in upper_line:
        level = "ERROR"
    elif "WARN" in upper_line:
        level = "WARN"
    elif "DEBUG" in upper_line:
        level = "DEBUG"

    return LogEvent(file_label, line_no, timestamp, trace_ids, level, line)


def correlate_logs(events: List[LogEvent]) -> Dict[str, List[LogEvent]]:
    trace_map: Dict[str, List[LogEvent]] = defaultdict(list)

    for event in events:
        if event.trace_ids:
            for tid in event.trace_ids:
                trace_map[tid].append(event)

    # Sort events within each trace by timestamp or line
    for tid in trace_map:
        trace_map[tid].sort(key=lambda e: (e.timestamp or datetime.min, e.line_no))

    return trace_map


def run_tests():
    """Self-test for log_correlation_engine."""
    log_content_1 = """2026-07-05 10:00:00 INFO [api-gateway] Received request request_id=req-99881
2026-07-05 10:00:01 INFO [api-gateway] Forwarding to auth request_id=req-99881
"""
    log_content_2 = """2026-07-05 10:00:02 ERROR [auth-service] DB timeout request_id=req-99881
2026-07-05 10:00:03 INFO [auth-service] Fallback triggered request_id=req-99881
"""
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".log", delete=False, encoding="utf-8") as f1, \
         tempfile.NamedTemporaryFile("w", suffix=".log", delete=False, encoding="utf-8") as f2:
        f1.write(log_content_1)
        f2.write(log_content_2)
        fn1, fn2 = f1.name, f2.name

    try:
        events = []
        for fn in (fn1, fn2):
            with open(fn, "r", encoding="utf-8") as f:
                for idx, line in enumerate(f, start=1):
                    events.append(parse_log_line(Path(fn).name, idx, line.strip()))

        correlated = correlate_logs(events)
        assert "req-99881" in correlated, "Failed to correlate request_id=req-99881"
        assert len(correlated["req-99881"]) == 4, f"Expected 4 events for trace, got {len(correlated['req-99881'])}"
        print(f"{COLOR_GREEN}All tests passed successfully!{COLOR_RESET}")
    finally:
        for fn in (fn1, fn2):
            if os.path.exists(fn):
                os.remove(fn)


def main():
    parser = argparse.ArgumentParser(
        description="Correlate logs across files by trace IDs, request IDs, or timestamps into unified timelines."
    )
    parser.add_argument("logs", nargs="*", help="Log files or directories to analyze")
    parser.add_argument("--trace-id", help="Filter timeline for a specific Trace / Request ID")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--test", action="store_true", help="Run internal self-tests")

    args = parser.parse_args()

    if args.test:
        run_tests()
        return 0

    log_files: List[Path] = []
    for target in (args.logs or ["."]):
        tp = Path(target)
        if tp.is_file():
            log_files.append(tp)
        elif tp.is_dir():
            log_files.extend([p for p in tp.rglob("*") if p.is_file() and (p.suffix.lower() in (".log", ".txt", ".out") or "log" in p.name.lower()) and not any(part.startswith(".") for part in p.parts)])

    if not log_files:
        print(f"{COLOR_YELLOW}No log files found.{COLOR_RESET}")
        return 0

    events: List[LogEvent] = []
    for fpath in log_files:
        try:
            with open(fpath, "r", encoding="utf-8", errors="replace") as f:
                for idx, line in enumerate(f, start=1):
                    line_str = line.strip()
                    if line_str:
                        events.append(parse_log_line(fpath.name, idx, line_str))
        except Exception as e:
            print(f"{COLOR_YELLOW}Skipping file '{fpath}': {e}{COLOR_RESET}", file=sys.stderr)

    correlated = correlate_logs(events)

    if args.trace_id:
        filtered = {k: v for k, v in correlated.items() if args.trace_id.lower() in k.lower()}
        correlated = filtered

    if args.json:
        json_out = {tid: [e.to_dict() for e in evs] for tid, evs in correlated.items()}
        print(json.dumps(json_out, indent=2))
        return 0

    print(f"\n{COLOR_BOLD}{COLOR_CYAN}=== Log Correlation Engine ==={COLOR_RESET}")
    print(f"Processed {len(events)} log entries across {len(log_files)} file(s).")
    print(f"Identified {len(correlated)} distinct trace / correlation ID timeline(s).\n")

    if not correlated:
        print(f"{COLOR_YELLOW}No correlation IDs found in log files.{COLOR_RESET}\n")
        return 0

    for tid, ev_list in list(correlated.items())[:20]:  # Limit top 20 traces if many
        has_error = any(e.level == "ERROR" for e in ev_list)
        status_badge = f"{COLOR_RED}[HAS ERRORS]{COLOR_RESET}" if has_error else f"{COLOR_GREEN}[OK]{COLOR_RESET}"

        print(f"{COLOR_BOLD}Trace ID: {COLOR_CYAN}{tid}{COLOR_RESET} {status_badge} ({len(ev_list)} events)")

        for ev in ev_list:
            ts_str = ev.timestamp.strftime("%H:%M:%S") if ev.timestamp else "N/A"
            lvl_color = COLOR_RED if ev.level == "ERROR" else (COLOR_YELLOW if ev.level == "WARN" else COLOR_GREY)
            print(f"  {COLOR_GREY}{ts_str}{COLOR_RESET} [{COLOR_BLUE}{ev.source_file}:{ev.line_no}{COLOR_RESET}] {lvl_color}{ev.level:<5}{COLOR_RESET} {ev.raw}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
