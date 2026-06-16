#!/usr/bin/env python3
"""
Mock Log Generator

A tool to generate realistic log files (Apache, Nginx, Syslog, or JSON) 
for testing log analyzers, parsers, or monitoring pipelines.

Usage:
    python tools/log_generator.py --format nginx --count 100 --output test_nginx.log
    python tools/log_generator.py --format json --count 10 --delay 0.5
"""

import argparse
import datetime
import json
import random
import sys
import time
from typing import List, Dict, Any

# Mock Data for generating logs
METHODS = ["GET", "POST", "PUT", "DELETE", "PATCH"]
RESOURCES = [
    "/", "/index.html", "/login", "/register", "/dashboard", "/api/v1/users",
    "/api/v1/products", "/api/v1/orders", "/static/css/style.css",
    "/static/js/app.js", "/images/logo.png", "/search?q=python", "/blog/posts/42"
]
STATUS_CODES = [200, 200, 200, 200, 201, 204, 301, 302, 400, 401, 403, 404, 500, 503]
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2.1 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Mobile/15E148 Safari/604.1",
    "curl/7.81.0"
]
REFERRERS = [
    "-", "https://www.google.com", "https://github.com",
    "https://news.ycombinator.com", "https://stackoverflow.com"
]

def generate_ip() -> str:
    """Generates a random IPv4 address, sometimes a private one, mostly public."""
    if random.random() < 0.1:
        return f"192.168.{random.randint(0, 255)}.{random.randint(1, 254)}"
    return f"{random.randint(1, 223)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"

def generate_log_entry(fmt: str, timestamp: datetime.datetime) -> str:
    """Generates a single log entry in the specified format."""
    ip = generate_ip()
    method = random.choice(METHODS)
    resource = random.choice(RESOURCES)
    status = random.choice(STATUS_CODES)
    size = random.randint(100, 8500) if status == 200 else random.randint(0, 500)
    user_agent = random.choice(USER_AGENTS)
    referrer = random.choice(REFERRERS)
    
    if fmt == 'apache_common':
        # 127.0.0.1 - - [10/Oct/2000:13:55:36 -0700] "GET /apache_pb.gif HTTP/1.0" 200 2326
        time_str = timestamp.strftime("%d/%b/%Y:%H:%M:%S +0000")
        return f'{ip} - - [{time_str}] "{method} {resource} HTTP/1.1" {status} {size}'
        
    elif fmt == 'apache_combined' or fmt == 'nginx':
        # 127.0.0.1 - - [10/Oct/2000:13:55:36 -0700] "GET /apache_pb.gif HTTP/1.0" 200 2326 "http://www.example.com/" "Mozilla/4.08 [en] (Win98; I ;Nav)"
        time_str = timestamp.strftime("%d/%b/%Y:%H:%M:%S +0000")
        return f'{ip} - - [{time_str}] "{method} {resource} HTTP/1.1" {status} {size} "{referrer}" "{user_agent}"'
        
    elif fmt == 'json':
        log_obj = {
            "timestamp": timestamp.isoformat() + "Z",
            "remote_ip": ip,
            "method": method,
            "uri": resource,
            "status": status,
            "bytes_sent": size,
            "referrer": referrer,
            "user_agent": user_agent,
            "request_time": round(random.uniform(0.01, 2.5), 3)
        }
        return json.dumps(log_obj)
        
    elif fmt == 'syslog':
        # <34>1 2003-10-11T22:14:15.003Z mymachine.example.com su - ID47 - BOM'An application log message...'
        time_str = timestamp.isoformat() + "Z"
        levels = ["info", "warning", "error", "debug"]
        level = random.choices(levels, weights=[0.8, 0.1, 0.05, 0.05])[0]
        services = ["web-server", "auth-service", "db-pool", "worker-process"]
        service = random.choice(services)
        pid = random.randint(1000, 9999)
        
        messages = {
            "info": f"Connection accepted from {ip} for {method} {resource}",
            "warning": f"Slow response detected for {resource} ({random.uniform(1.0, 5.0):.2f}s)",
            "error": f"Failed request from {ip}: HTTP status {status} for {method} {resource}",
            "debug": f"Session verified for token {random.randint(100000, 999999)}"
        }
        
        return f"{time_str} localhost {service}[{pid}]: [{level.upper()}] {messages[level]}"
        
    return ""

def main() -> int:
    parser = argparse.ArgumentParser(description="Mock Log Generator")
    parser.add_argument('--format', choices=['nginx', 'apache_common', 'apache_combined', 'json', 'syslog'], 
                        default='nginx', help="Log format (default: nginx)")
    parser.add_argument('--count', type=int, default=100, help="Number of log entries to generate (0 for infinite)")
    parser.add_argument('--delay', type=float, default=0.0, help="Delay in seconds between logs (default: 0.0)")
    parser.add_argument('--output', help="File path to write logs to (default: stdout)")
    args = parser.parse_args()
    
    file_handle = sys.stdout
    if args.output:
        try:
            file_handle = open(args.output, 'w', encoding='utf-8')
        except IOError as e:
            print(f"Error opening output file: {e}", file=sys.stderr)
            return 1
            
    try:
        count = 0
        now = datetime.datetime.now(datetime.timezone.utc)
        
        while True:
            # If delay is set, we use the current time, otherwise we decrement back in time so we generate historical logs
            if args.delay > 0:
                log_time = datetime.datetime.now(datetime.timezone.utc)
            else:
                log_time = now - datetime.timedelta(seconds=(args.count - count))
                
            log_line = generate_log_entry(args.format, log_time)
            file_handle.write(log_line + "\n")
            file_handle.flush()
            
            count += 1
            
            if args.count > 0 and count >= args.count:
                break
                
            if args.delay > 0:
                time.sleep(args.delay)
                
    except KeyboardInterrupt:
        print("\nLog generation stopped by user.", file=sys.stderr)
    finally:
        if args.output:
            file_handle.close()
            
    return 0

if __name__ == "__main__":
    sys.exit(main())
