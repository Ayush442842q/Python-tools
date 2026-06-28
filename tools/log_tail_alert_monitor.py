#!/usr/bin/env python3
"""
Real-Time Log Tail Monitor with Action Triggers
Tails log files continuously and monitors for specified regex patterns.
When a pattern matches, it executes actions such as shell command execution,
writing to separate alert files, or dispatching HTTP webhooks, with built-in
rate-limiting (throttling) to prevent alert flooding.
"""

import os
import sys
import re
import time
import argparse
import json
import urllib.request
import urllib.error
import subprocess

class AlertTracker:
    def __init__(self, throttle_seconds=10):
        self.throttle_seconds = throttle_seconds
        self.last_triggered = {}

    def is_throttled(self, rule_name):
        """Check if rule has been triggered recently to prevent alert storms."""
        now = time.time()
        last = self.last_triggered.get(rule_name, 0)
        if now - last < self.throttle_seconds:
            return True
        self.last_triggered[rule_name] = now
        return False

def tail_file(filepath):
    """
    Generator that yields new lines added to a file, starting from the end.
    Handles file rotation / truncation gracefully.
    """
    try:
        # Seek to end of file initially
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(0, os.SEEK_END)
            last_size = os.path.getsize(filepath)
            
            while True:
                # Check for rotation/truncation
                try:
                    curr_size = os.path.getsize(filepath)
                except OSError:
                    # File might be temporarily unavailable during rotation
                    time.sleep(1)
                    continue

                if curr_size < last_size:
                    # File was truncated/rotated, start from the beginning
                    print(f"[*] Info: Log file {filepath} was truncated or rotated. Resetting tail.", file=sys.stderr)
                    f.seek(0)
                
                line = f.readline()
                if not line:
                    time.sleep(0.5)
                    continue
                
                last_size = os.path.getsize(filepath)
                yield line.rstrip('\r\n')
    except KeyboardInterrupt:
        return

def trigger_command(cmd_template, line):
    """Execute a shell command, replacing {line} placeholder with the matched log line."""
    cmd = cmd_template.replace("{line}", line)
    try:
        # Run asynchronously in background to not block the tailing process
        subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"[!] Error executing command: {e}", file=sys.stderr)

def trigger_webhook(webhook_url, rule_name, line):
    """Send alert details to an HTTP webhook endpoint as JSON."""
    payload = {
        "event": "log_alert",
        "rule": rule_name,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "log_line": line
    }
    data = json.dumps(payload).encode("utf-8")
    
    req = urllib.request.Request(
        webhook_url, 
        data=data, 
        headers={"Content-Type": "application/json", "User-Agent": "LogTailAlertMonitor/1.0"}
    )
    
    # Send asynchronously or quickly
    try:
        # We set a small timeout so it doesn't block tailing if the server is slow
        with urllib.request.urlopen(req, timeout=3.0) as response:
            pass
    except urllib.error.URLError as e:
        print(f"[!] Webhook error: {e.reason}", file=sys.stderr)
    except Exception as e:
        print(f"[!] Error sending webhook: {e}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(
        description="Real-Time Log Tail Monitor - Tail logs and trigger actions on pattern matches",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("file", help="Path to the log file to monitor")
    parser.add_argument("-p", "--pattern", required=True,
                        help="Regex pattern to search for in log lines")
    parser.add_argument("-n", "--name", default="alert_rule",
                        help="Name of the alert rule (default: alert_rule)")
    parser.add_argument("-c", "--command",
                        help="Shell command to run on alert. Use {line} placeholder to insert the matching log line.")
    parser.add_argument("-w", "--webhook",
                        help="HTTP Webhook URL to POST JSON alert payloads to")
    parser.add_argument("-a", "--alert-log",
                        help="Path to a dedicated output file to write matching alert lines")
    parser.add_argument("-t", "--throttle", type=int, default=10,
                        help="Minimum seconds between triggering actions for the same rule (default: 10s)")

    args = parser.parse_args()

    if not os.path.exists(args.file):
        # Create file if it doesn't exist, to tail it immediately
        print(f"[*] Info: File '{args.file}' does not exist. Creating empty file to tail...", file=sys.stderr)
        try:
            with open(args.file, "a") as f:
                pass
        except Exception as e:
            print(f"Error creating file: {e}", file=sys.stderr)
            sys.exit(1)

    try:
        compiled_regex = re.compile(args.pattern)
    except re.error as e:
        print(f"Error: Invalid regular expression pattern: {e}", file=sys.stderr)
        sys.exit(1)

    tracker = AlertTracker(throttle_seconds=args.throttle)

    print(f"[*] Monitoring log: {args.file}")
    print(f"[*] Matching rule: '{args.name}' with pattern: '{args.pattern}'")
    if args.command:
        print(f"[*] Action command: {args.command}")
    if args.webhook:
        print(f"[*] Action webhook: {args.webhook}")
    if args.alert_log:
        print(f"[*] Action alert log: {args.alert_log}")
    print("[*] Press Ctrl+C to stop monitoring.")
    print("-" * 60)

    for line in tail_file(args.file):
        if compiled_regex.search(line):
            # Check throttling
            if tracker.is_throttled(args.name):
                print(f"[THROTTLED] Match: {line}")
                continue

            print(f"\033[91m[ALERT: {args.name}]\033[0m {line}")

            # Trigger Actions
            # 1. Alert Log
            if args.alert_log:
                try:
                    with open(args.alert_log, "a", encoding="utf-8") as af:
                        timestamp = time.strftime("[%Y-%m-%d %H:%M:%S]")
                        af.write(f"{timestamp} [{args.name}] {line}\n")
                except Exception as e:
                    print(f"[!] Error writing alert to {args.alert_log}: {e}", file=sys.stderr)

            # 2. Shell Command
            if args.command:
                trigger_command(args.command, line)

            # 3. Webhook
            if args.webhook:
                # Run webhook in a separate thread so it doesn't hold up log processing
                import threading
                threading.Thread(target=trigger_webhook, args=(args.webhook, args.name, line), daemon=True).start()

if __name__ == "__main__":
    main()
