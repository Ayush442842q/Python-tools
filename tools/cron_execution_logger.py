#!/usr/bin/env python3
"""
cron_execution_logger - Monitor, Log, and Alert on Cron/System Job Executions

Runs a specified shell command as a subprocess, records execution details
(start time, end time, duration, exit code, outputs), logs them to a structured
log file, and triggers notification alerts if the command fails (non-zero exit code).

Features:
1. Captures stdout and stderr separately or combined
2. Logs execution stats to a JSON/text log file
3. Alerts on failure (custom script, webhook, or mail configurations)
4. Enforces timeouts on running tasks
5. Dry-run option to preview execution configuration

Usage:
    python tools/cron_execution_logger.py -c "command to run" [options]

Example:
    python tools/cron_execution_logger.py -c "python tools/hello.py Alice" -l cron_jobs.log
"""

import argparse
import datetime
import json
import os
import subprocess
import sys
import time
from typing import Dict, Any, Optional


def run_command(cmd: str, timeout: Optional[float] = None) -> Dict[str, Any]:
    """Execute shell command and capture metrics and outputs."""
    start_time = datetime.datetime.now(datetime.timezone.utc)
    start_perf = time.perf_counter()
    
    stdout = ""
    stderr = ""
    exit_code = -1
    status = "completed"
    
    try:
        # Run command via system shell
        proc = subprocess.run(
            cmd,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout
        )
        stdout = proc.stdout
        stderr = proc.stderr
        exit_code = proc.returncode
        if exit_code != 0:
            status = "failed"
    except subprocess.TimeoutExpired as te:
        status = "timeout"
        stdout = te.stdout if te.stdout else ""
        stderr = f"Command timed out after {timeout} seconds.\n{te.stderr if te.stderr else ''}"
        exit_code = -2
    except Exception as e:
        status = "error"
        stderr = f"Execution failed to start: {str(e)}"
        exit_code = -3
        
    duration = time.perf_counter() - start_perf
    end_time = datetime.datetime.now(datetime.timezone.utc)
    
    return {
        "command": cmd,
        "status": status,
        "exit_code": exit_code,
        "start_time": start_time.isoformat(),
        "end_time": end_time.isoformat(),
        "duration_seconds": round(duration, 4),
        "stdout": stdout,
        "stderr": stderr
    }


def write_log(log_path: str, result: Dict[str, Any], json_format: bool = False) -> None:
    """Save execution result to log file."""
    try:
        # Create directories if they do not exist
        log_dir = os.path.dirname(log_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
            
        with open(log_path, "a", encoding="utf-8") as f:
            if json_format:
                log_entry = {
                    "timestamp": result["start_time"],
                    "command": result["command"],
                    "status": result["status"],
                    "exit_code": result["exit_code"],
                    "duration_seconds": result["duration_seconds"],
                    "stdout_len": len(result["stdout"]),
                    "stderr_len": len(result["stderr"]),
                    "stderr": result["stderr"] if result["stderr"] else None
                }
                f.write(json.dumps(log_entry) + "\n")
            else:
                border = "=" * 60
                f.write(f"{border}\n")
                f.write(f"Timestamp:  {result['start_time']}\n")
                f.write(f"Command:    {result['command']}\n")
                f.write(f"Status:     {result['status'].upper()}\n")
                f.write(f"Exit Code:  {result['exit_code']}\n")
                f.write(f"Duration:   {result['duration_seconds']}s\n")
                if result["stdout"].strip():
                    f.write(f"Stdout:\n{result['stdout']}\n")
                if result["stderr"].strip():
                    f.write(f"Stderr:\n{result['stderr']}\n")
                f.write(f"{border}\n\n")
    except Exception as e:
        print(f"Error writing to log file {log_path}: {e}", file=sys.stderr)


def trigger_alert(result: Dict[str, Any], alert_script: Optional[str]) -> None:
    """Execute custom alert handler/script on job failure."""
    if not alert_script:
        return
        
    print(f"[*] Triggering failure alert handler: {alert_script}")
    
    # Pack job metrics in JSON format for the alert handler
    payload = json.dumps({
        "alert": "CronJobFailure",
        "command": result["command"],
        "status": result["status"],
        "exit_code": result["exit_code"],
        "duration": result["duration_seconds"],
        "stderr": result["stderr"]
    })
    
    try:
        proc = subprocess.Popen(
            alert_script,
            shell=True,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = proc.communicate(input=payload, timeout=10)
        if proc.returncode != 0:
            print(f"[!] Alert script exited with code {proc.returncode}. Stderr: {stderr}", file=sys.stderr)
    except Exception as e:
        print(f"[!] Failed to invoke alert handler: {e}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Cron Job Execution Logger & Alerting Utility",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("-c", "--command", required=True, help="Shell command to execute")
    parser.add_argument("-l", "--log", default="cron_job_runs.log", help="Path to write log records")
    parser.add_argument("-j", "--json", action="store_true", help="Log output in JSON Lines format")
    parser.add_argument("-t", "--timeout", type=float, help="Timeout in seconds before terminating command")
    parser.add_argument("-a", "--alert-script", help="Path/command of script to execute on failure. Receives JSON metrics via stdin.")
    parser.add_argument("--dry-run", action="store_true", help="Preview run parameters without executing")
    
    args = parser.parse_args()
    
    if args.dry_run:
        print("--- Dry-Run Mode ---")
        print(f"Command to execute: {args.command}")
        print(f"Logging to:         {args.log} (JSON: {args.json})")
        print(f"Timeout:            {args.timeout}s")
        print(f"Alert Script:       {args.alert_script if args.alert_script else 'None'}")
        return 0

    print(f"[*] Executing task: {args.command}")
    result = run_command(args.command, timeout=args.timeout)
    
    # Print console feedback
    if result["status"] == "completed":
        print(f"[+] Command completed successfully in {result['duration_seconds']}s (Exit code: 0).")
    else:
        print(f"[!] Command failed/timed out in {result['duration_seconds']}s (Status: {result['status']}, Exit: {result['exit_code']}).", file=sys.stderr)
        if result["stderr"].strip():
            print(f"Error detail:\n{result['stderr']}", file=sys.stderr)
            
    # Save log
    write_log(args.log, result, json_format=args.json)
    
    # Trigger alert if failed
    if result["exit_code"] != 0:
        trigger_alert(result, args.alert_script)
        
    return result["exit_code"]


if __name__ == "__main__":
    sys.exit(main())
