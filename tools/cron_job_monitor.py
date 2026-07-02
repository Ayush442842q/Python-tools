#!/usr/bin/env python3
"""
Cron Job Execution Monitor & Alerting Wrapper
A CLI wrapper utility for monitoring scheduled scripts. Executes commands,
monitors execution duration, enforces timeout constraints, and dispatches JSON
webhooks or creates local error reports upon failure or timeout.
"""

import argparse
import datetime
import os
import socket
import subprocess
import sys
import urllib.request
import urllib.error
import json

# Formatting colors
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BOLD = "\033[1m"
RESET = "\033[0m"


def send_webhook(url, payload):
    """Sends a JSON webhook alert natively using urllib."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "CronJobMonitor/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.status == 200 or response.status == 204
    except urllib.error.URLError as e:
        sys.stderr.write(f"Webhook dispatch failed: {e}\n")
        return False


def run_command(command_list, timeout_sec):
    """Runs a command as a subprocess, captures output, and handles timeouts."""
    start_time = datetime.datetime.now()
    timed_out = False
    stdout, stderr = "", ""
    return_code = -1

    try:
        # Run using subprocess shell or list representation depending on system
        process = subprocess.Popen(
            command_list,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            shell=True if isinstance(command_list, str) else False
        )
        
        try:
            stdout, stderr = process.communicate(timeout=timeout_sec)
            return_code = process.returncode
        except subprocess.TimeoutExpired:
            process.kill()
            stdout, stderr = process.communicate()
            timed_out = True
            return_code = -9  # Signal terminated
            
    except Exception as e:
        stderr = f"Subprocess invocation failure: {str(e)}"
        return_code = -127

    end_time = datetime.datetime.now()
    duration = (end_time - start_time).total_seconds()
    
    return {
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "duration_seconds": duration,
        "return_code": return_code,
        "stdout": stdout,
        "stderr": stderr,
        "timed_out": timed_out
    }


def main():
    parser = argparse.ArgumentParser(
        description="Cron Job Wrapper & Alerting Monitor",
        epilog="Example: cron_job_monitor.py --name 'BackupTask' --timeout 60 -- python backup.py --force"
    )
    parser.add_argument("-n", "--name", default="Unnamed Job", help="Identifying name for the cron job")
    parser.add_argument("-t", "--timeout", type=float, default=3600.0, help="Maximum execution time in seconds (default: 3600)")
    parser.add_argument("-w", "--webhook", help="URL endpoint for HTTP POST JSON notifications on failure")
    parser.add_argument("-l", "--log-dir", help="Directory path to save execution report files")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress standard output forwarding unless error occurs")
    parser.add_argument("cmd", nargs="+", help="Command and arguments to execute")
    args = parser.parse_args()

    job_name = args.name
    timeout_limit = args.timeout
    command_to_run = args.cmd

    # Execute target process
    result = run_command(command_to_run, timeout_limit)

    is_failed = result["return_code"] != 0 or result["timed_out"]

    # Forward stdout/stderr to parent shell unless quiet
    if not args.quiet or is_failed:
        if result["stdout"]:
            sys.stdout.write(result["stdout"])
        if result["stderr"]:
            sys.stderr.write(result["stderr"])

    # Prepare diagnostic report
    hostname = socket.gethostname()
    username = os.environ.get("USER") or os.environ.get("USERNAME") or "unknown"
    
    report = {
        "job_name": job_name,
        "command": " ".join(command_to_run),
        "status": "FAILED" if is_failed else "SUCCESS",
        "return_code": result["return_code"],
        "timed_out": result["timed_out"],
        "start_time": result["start_time"],
        "end_time": result["end_time"],
        "duration_seconds": result["duration_seconds"],
        "hostname": hostname,
        "run_as_user": username,
        "stderr_snippet": result["stderr"][-1000:] if result["stderr"] else "",
        "stdout_snippet": result["stdout"][-500:] if result["stdout"] else ""
    }

    # If the execution failed, trigger alerting workflows
    if is_failed:
        sys.stderr.write(
            f"\n{RED}{BOLD}=== CRON JOB FAILURE DETECTED ==={RESET}\n"
            f"Job Name: {job_name}\n"
            f"Exit Code: {result['return_code']} | Timeout: {result['timed_out']}\n"
            f"Duration: {result['duration_seconds']:.2f} seconds\n"
        )
        
        # Save log report locally if specified
        if args.log_dir:
            if not os.path.exists(args.log_dir):
                os.makedirs(args.log_dir)
            filename = f"error_{job_name.replace(' ', '_')}_{datetime.datetime.now().strftime('%Y%md-%H%M%S')}.json"
            log_filepath = os.path.join(args.log_dir, filename)
            try:
                with open(log_filepath, "w") as f:
                    json.dump(report, f, indent=2)
                sys.stderr.write(f"Logged details to: {log_filepath}\n")
            except IOError as e:
                sys.stderr.write(f"Failed to write log file: {e}\n")

        # Send Webhook Alert
        if args.webhook:
            sys.stderr.write(f"Sending webhook alert to {args.webhook}...\n")
            success = send_webhook(args.webhook, report)
            if success:
                sys.stderr.write(f"{GREEN}Alert sent successfully.{RESET}\n")
            else:
                sys.stderr.write(f"{RED}Failed to send alert via webhook.{RESET}\n")
        
        # Propagate the failed exit code
        sys.exit(result["return_code"] if result["return_code"] != -9 else 124)
    else:
        if not args.quiet:
            print(f"\n{GREEN}{BOLD}✓ Cron Job '{job_name}' completed successfully in {result['duration_seconds']:.2f}s.{RESET}")


if __name__ == "__main__":
    main()
