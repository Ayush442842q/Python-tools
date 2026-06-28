#!/usr/bin/env python3
"""
Command Retry Runner
Executes shell commands with configurable retries, delays, exponential backoff, jitter, timeouts,
and custom retry triggers based on exit codes or output patterns.
"""

import sys
import os
import time
import argparse
import subprocess
import random
import re
import shlex

def run_command(command, timeout=None):
    """Run a system command and return exit code, stdout, and stderr"""
    # On Windows, we need shell=True to run standard CLI builtins or bat scripts
    use_shell = sys.platform == "win32" or isinstance(command, str)
    
    try:
        process = subprocess.Popen(
            command,
            shell=use_shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        stdout, stderr = process.communicate(timeout=timeout)
        return process.returncode, stdout, stderr
    except subprocess.TimeoutExpired as e:
        # Kill process and its children if timeout expires
        process.kill()
        stdout, stderr = process.communicate()
        return -1, stdout, stderr + f"\n[TimeoutExpired]: Command execution timed out after {timeout}s."
    except Exception as e:
        return -2, "", str(e)

def main():
    parser = argparse.ArgumentParser(description="Run a command and retry if it fails.")
    parser.add_argument("command", help="Command to run (surround with quotes if it contains arguments)")
    parser.add_argument("-r", "--retries", type=int, default=3, help="Max number of retries (default: 3)")
    parser.add_argument("-d", "--delay", type=float, default=1.0, help="Initial delay in seconds (default: 1.0)")
    parser.add_argument("-b", "--backoff", type=float, default=2.0, help="Exponential backoff factor (default: 2.0)")
    parser.add_argument("-j", "--jitter", action="store_true", help="Apply random jitter to backoff delay")
    parser.add_argument("-t", "--timeout", type=float, default=None, help="Execution timeout per attempt in seconds")
    parser.add_argument("--retry-on-code", type=int, nargs="+", help="Retry only if exit code matches these values")
    parser.add_argument("--fail-on-code", type=int, nargs="+", help="Immediately fail if exit code matches these values")
    parser.add_argument("--retry-on-pattern", type=str, help="Retry only if stdout/stderr matches this regex pattern")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress runner logging (keeps command output)")
    
    args = parser.parse_args()
    
    # Parse the command line safely
    if sys.platform == "win32":
        cmd_args = args.command
    else:
        cmd_args = shlex.split(args.command)
        
    retries = args.retries
    delay = args.delay
    backoff = args.backoff
    
    attempt = 0
    success = False
    final_returncode = 0
    
    while attempt <= retries:
        attempt += 1
        if not args.quiet:
            print(f"\n[RetryRunner] Attempt {attempt}/{retries + 1} for: '{args.command}'", file=sys.stderr)
            if attempt > 1:
                print(f"[RetryRunner] Waiting {delay:.2f} seconds before retrying...", file=sys.stderr)
                time.sleep(delay)
                # Calculate next delay
                if args.jitter:
                    # Jitter adds up to 50% random variation
                    delay = (delay * backoff) * (0.5 + random.random())
                else:
                    delay = delay * backoff
        
        returncode, stdout, stderr = run_command(cmd_args, timeout=args.timeout)
        
        # Display the stdout/stderr of the command
        if stdout:
            sys.stdout.write(stdout)
            sys.stdout.flush()
        if stderr:
            sys.stderr.write(stderr)
            sys.stderr.flush()
            
        if not args.quiet:
            print(f"[RetryRunner] Command returned code: {returncode}", file=sys.stderr)
            
        # Determine if we should retry
        should_retry = False
        
        if returncode == 0:
            success = True
            final_returncode = 0
            break
            
        # Check fail-on-code list
        if args.fail_on_code and returncode in args.fail_on_code:
            if not args.quiet:
                print(f"[RetryRunner] Failed with critical exit code {returncode}. Aborting retries.", file=sys.stderr)
            final_returncode = returncode
            break
            
        # Check if we should retry based on code
        if args.retry_on_code:
            if returncode in args.retry_on_code:
                should_retry = True
        else:
            # Default is to retry on any non-zero exit code
            should_retry = True
            
        # Check if we should retry based on pattern matching
        if args.retry_on_pattern:
            combined_output = stdout + "\n" + stderr
            pattern_match = re.search(args.retry_on_pattern, combined_output)
            if pattern_match:
                should_retry = True
            else:
                should_retry = False
                if not args.quiet:
                    print(f"[RetryRunner] Output pattern '{args.retry_on_pattern}' not found. Aborting retries.", file=sys.stderr)
                    
        # If we decided not to retry or we've run out of attempts
        if not should_retry:
            final_returncode = returncode
            break
            
        final_returncode = returncode
        
    if success:
        if not args.quiet:
            print(f"\n[RetryRunner] SUCCESS: Command finished successfully on attempt {attempt}.", file=sys.stderr)
        sys.exit(0)
    else:
        if not args.quiet:
            print(f"\n[RetryRunner] FAILURE: Command failed after {attempt} attempts. Final code: {final_returncode}", file=sys.stderr)
        sys.exit(final_returncode)

if __name__ == "__main__":
    main()
