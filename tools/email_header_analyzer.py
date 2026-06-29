#!/usr/bin/env python3
"""
email_header_analyzer.py - Email Header Analyzer & Hop Tracer

Parses raw email headers to trace the hop-by-hop delivery path, calculates
relaying delays, extracts SPF/DKIM/DMARC authentication records, and flags
suspicious headers or mismatches. Outputs a beautiful terminal report and
optional HTML report.

Requirements:
    - Python 3.6+ (No external dependencies)
"""

import sys
import os
import re
import argparse
from email.parser import HeaderParser
from datetime import datetime
import email.utils

# ANSI Terminal Colors
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"
COLOR_RESET = "\033[0m"

def has_color_support():
    """Checks if the output stream supports ANSI colors."""
    if os.name == 'nt':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
            return True
        except Exception:
            return False
    return sys.stdout.isatty()

def clean_header_val(val):
    """Clean whitespace and newlines from a header value."""
    if not val:
        return ""
    return re.sub(r'\s+', ' ', str(val)).strip()

def parse_received_header(received_str):
    """
    Parses a single 'Received' header to extract 'from', 'by', and the timestamp.
    Example received header:
    from mail.example.com (mail.example.com [192.0.2.1]) by mx.google.com with ESMTPS id x123; Mon, 29 Jun 2026 13:00:00 -0700 (PDT)
    """
    received_str = clean_header_val(received_str)
    
    # Extract 'from'
    from_match = re.search(r'from\s+([^\s;]+(?:\s+\[[^\]]+\])?)', received_str, re.IGNORECASE)
    from_server = from_match.group(1) if from_match else "Unknown"
    
    # Extract 'by'
    by_match = re.search(r'by\s+([^\s;]+)', received_str, re.IGNORECASE)
    by_server = by_match.group(1) if by_match else "Unknown"
    
    # Extract timestamp (usually follows a semicolon at the end)
    parts = received_str.split(';')
    dt = None
    if len(parts) > 1:
        date_str = parts[-1].strip()
        # Clean up timezone comments (e.g. "(PDT)")
        date_str = re.sub(r'\s*\([^)]*\)\s*$', '', date_str)
        try:
            parsed_date = email.utils.parsedate_to_datetime(date_str)
            dt = parsed_date
        except (ValueError, TypeError):
            pass
            
    return {
        "from": from_server,
        "by": by_server,
        "datetime": dt,
        "raw": received_str
    }

def extract_auth_results(headers_dict):
    """Extracts SPF, DKIM, and DMARC results from Authentication-Results or specific headers."""
    auth_results = {"spf": "Unknown", "dkim": "Unknown", "dmarc": "Unknown"}
    
    # 1. Search Authentication-Results
    auth_headers = headers_dict.get_all("Authentication-Results", [])
    for ah in auth_headers:
        ah_clean = clean_header_val(ah).lower()
        
        # Look for spf=pass/fail/etc.
        spf_m = re.search(r'\bspf=(\w+)', ah_clean)
        if spf_m:
            auth_results["spf"] = spf_m.group(1).upper()
            
        # Look for dkim=pass/fail/etc.
        dkim_m = re.search(r'\bdkim=(\w+)', ah_clean)
        if dkim_m:
            auth_results["dkim"] = dkim_m.group(1).upper()
            
        # Look for dmarc=pass/fail/etc.
        dmarc_m = re.search(r'\bdmarc=(\w+)', ah_clean)
        if dmarc_m:
            auth_results["dmarc"] = dmarc_m.group(1).upper()
            
    # 2. Backup check for Received-SPF
    received_spf = headers_dict.get("Received-SPF", "")
    if received_spf and auth_results["spf"] == "Unknown":
        rspf_clean = clean_header_val(received_spf).lower()
        if "pass" in rspf_clean:
            auth_results["spf"] = "PASS"
        elif "fail" in rspf_clean:
            auth_results["spf"] = "FAIL"
        elif "softfail" in rspf_clean:
            auth_results["spf"] = "SOFTFAIL"
            
    return auth_results

def analyze_headers(raw_headers_str):
    """Parses and analyzes raw email headers."""
    parser = HeaderParser()
    headers = parser.parsestr(raw_headers_str)
    
    metadata = {
        "Subject": clean_header_val(headers.get("Subject", "No Subject")),
        "From": clean_header_val(headers.get("From", "Unknown")),
        "To": clean_header_val(headers.get("To", "Unknown")),
        "Cc": clean_header_val(headers.get("Cc", "")),
        "Date": clean_header_val(headers.get("Date", "Unknown")),
        "Message-ID": clean_header_val(headers.get("Message-ID", "None")),
        "Return-Path": clean_header_val(headers.get("Return-Path", "None")),
        "X-Mailer": clean_header_val(headers.get("X-Mailer", "Unknown"))
    }
    
    # Process Received hops (Received headers are top-to-bottom, i.e., last-to-first)
    # We want to reverse them to trace from origin to destination
    received_headers = headers.get_all("Received", [])
    hops = []
    
    for rh in reversed(received_headers):
        hop_info = parse_received_header(rh)
        hops.append(hop_info)
        
    # Calculate delays between hops
    for i in range(len(hops)):
        if i == 0:
            hops[i]["delay_sec"] = 0
            continue
            
        dt_current = hops[i]["datetime"]
        dt_prev = hops[i-1]["datetime"]
        
        if dt_current and dt_prev:
            diff = (dt_current - dt_prev).total_seconds()
            hops[i]["delay_sec"] = max(0.0, diff)
        else:
            hops[i]["delay_sec"] = None

    auth = extract_auth_results(headers)
    
    # Basic Security Warnings
    warnings = []
    
    # Warning 1: Return-Path and From Domain mismatch
    from_match = re.search(r'@([a-zA-Z0-9.\-]+)', metadata["From"])
    rp_match = re.search(r'@([a-zA-Z0-9.\-]+)', metadata["Return-Path"])
    
    if from_match and rp_match:
        from_domain = from_match.group(1).lower()
        rp_domain = rp_match.group(1).lower()
        if from_domain != rp_domain:
            warnings.append(f"Return-Path domain ({rp_domain}) does not match From domain ({from_domain})")
            
    # Warning 2: Failed Auth Checks
    if auth["spf"] == "FAIL":
        warnings.append("SPF verification failed: Sender IP is not authorized")
    if auth["dkim"] == "FAIL":
        warnings.append("DKIM signature validation failed: Email body or headers may have been modified")
    if auth["dmarc"] == "FAIL":
        warnings.append("DMARC alignment failed: Sender spoofing risk is high")
        
    # Warning 3: Long Hop Delays
    for idx, hop in enumerate(hops):
        delay = hop["delay_sec"]
        if delay and delay > 600: # Over 10 minutes
            warnings.append(f"Hop {idx+1} experienced a significant delay of {delay/60:.1f} minutes")

    return {
        "metadata": metadata,
        "hops": hops,
        "auth": auth,
        "warnings": warnings
    }

def print_terminal_report(analysis, use_color=True):
    """Renders the email header analysis as a beautiful terminal report."""
    def color(text, color_code):
        return f"{color_code}{text}{COLOR_RESET}" if use_color else text

    print(color("\n=== EMAIL METADATA ===", COLOR_BOLD + COLOR_CYAN))
    for k, v in analysis["metadata"].items():
        if v:
            print(f"  {color(k + ':', COLOR_BOLD)} {v}")
            
    print(color("\n=== AUTHENTICATION CHECKS ===", COLOR_BOLD + COLOR_CYAN))
    for check, res in analysis["auth"].items():
        res_color = COLOR_GREEN
        if res in ("FAIL", "SOFTFAIL"):
            res_color = COLOR_RED
        elif res == "Unknown":
            res_color = COLOR_YELLOW
        print(f"  {color(check.upper() + ':', COLOR_BOLD)} {color(res, res_color)}")

    print(color("\n=== SECURITY WARNINGS ===", COLOR_BOLD + COLOR_CYAN))
    if analysis["warnings"]:
        for w in analysis["warnings"]:
            print(f"  [{color('WARNING', COLOR_RED)}] {w}")
    else:
        print(f"  {color('No immediate security anomalies detected.', COLOR_GREEN)}")

    print(color("\n=== RELAY Hops TIMELINE (Origin -> Destination) ===", COLOR_BOLD + COLOR_CYAN))
    if not analysis["hops"]:
        print("  No 'Received' header hops found.")
        return
        
    for i, hop in enumerate(analysis["hops"]):
        hop_num = f"Hop #{i+1}"
        print(f"  {color(hop_num, COLOR_BOLD)}")
        print(f"    From: {hop['from']}")
        print(f"    By:   {hop['by']}")
        
        dt_str = hop["datetime"].strftime("%Y-%m-%d %H:%M:%S %z") if hop["datetime"] else "Unknown"
        print(f"    Time: {dt_str}")
        
        if i > 0:
            delay = hop["delay_sec"]
            if delay is not None:
                delay_str = f"{delay:.1f} seconds"
                if delay > 60:
                    delay_str = f"{delay/60:.1f} minutes"
                
                delay_color = COLOR_YELLOW if delay > 300 else COLOR_RESET
                print(f"    Delay: {color('+' + delay_str, delay_color)}")
            else:
                print("    Delay: Unknown (Timestamp parsing failed or missing)")
        print()

def generate_html_report(analysis, email_subject, output_path):
    """Generates a premium, responsive HTML report of the analysis."""
    
    warnings_list = "".join(
        f'<div class="warning-item">⚠️ {w}</div>' for w in analysis["warnings"]
    ) if analysis["warnings"] else '<div class="no-warning">✓ No security alerts detected</div>'
    
    hops_rows = []
    for i, hop in enumerate(analysis["hops"]):
        delay_val = "-"
        if i > 0 and hop["delay_sec"] is not None:
            sec = hop["delay_sec"]
            delay_val = f"+{sec:.1f}s" if sec < 60 else f"+{sec/60:.1f}m"
            
        time_val = hop["datetime"].strftime("%Y-%m-%d %H:%M:%S %z") if hop["datetime"] else "Unknown"
        hops_rows.append(f"""<tr>
            <td style="font-weight: bold; color: #6366f1;">#{i+1}</td>
            <td class="code-font">{hop['from']}</td>
            <td class="code-font">{hop['by']}</td>
            <td>{time_val}</td>
            <td style="font-weight: 600; color: {'#f59e0b' if i > 0 and hop['delay_sec'] and hop['delay_sec'] > 300 else '#94a3b8'};">{delay_val}</td>
        </tr>""")

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Email Header Analysis Report</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;700&family=Space+Grotesk:wght@500;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #080c14;
            --card-bg: rgba(17, 24, 39, 0.7);
            --border-color: rgba(255, 255, 255, 0.08);
            --text-primary: #f1f5f9;
            --text-secondary: #94a3b8;
            --primary: #6366f1;
            --danger: #ef4444;
            --success: #10b981;
        }}
        
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        
        body {{
            background-color: var(--bg-color);
            color: var(--text-primary);
            font-family: 'Outfit', sans-serif;
            padding: 3rem 1.5rem;
            line-height: 1.5;
        }}
        
        .container {{
            max-width: 1200px;
            margin: 0 auto;
        }}
        
        header {{
            margin-bottom: 2.5rem;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 1.5rem;
        }}
        
        h1 {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 2.25rem;
            font-weight: 700;
            background: linear-gradient(to right, #818cf8, #c084fc);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        
        .grid {{
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 2rem;
        }}
        
        @media (max-width: 900px) {{
            .grid {{
                grid-template-columns: 1fr;
            }}
        }}
        
        .card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 1rem;
            padding: 2rem;
            backdrop-filter: blur(12px);
            margin-bottom: 2rem;
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.3);
        }}
        
        .card-title {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 1.25rem;
            font-weight: 700;
            margin-bottom: 1.5rem;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 0.5rem;
            color: #a5b4fc;
        }}
        
        .meta-list {{
            display: flex;
            flex-direction: column;
            gap: 0.75rem;
        }}
        
        .meta-item {{
            display: flex;
            border-bottom: 1px solid rgba(255,255,255,0.03);
            padding-bottom: 0.5rem;
        }}
        
        .meta-label {{
            width: 120px;
            font-weight: 600;
            color: var(--text-secondary);
        }}
        
        .meta-val {{
            flex-grow: 1;
            word-break: break-all;
        }}
        
        .auth-badges {{
            display: flex;
            gap: 1rem;
            margin-top: 1rem;
        }}
        
        .badge {{
            flex: 1;
            padding: 1rem;
            border-radius: 0.5rem;
            text-align: center;
            font-weight: bold;
            font-size: 1.1rem;
        }}
        
        .badge-label {{
            display: block;
            font-size: 0.75rem;
            text-transform: uppercase;
            color: var(--text-secondary);
            font-weight: normal;
            margin-bottom: 0.25rem;
        }}
        
        .pass {{
            background: rgba(16, 185, 129, 0.15);
            border: 1px solid rgba(16, 185, 129, 0.3);
            color: var(--success);
        }}
        
        .fail {{
            background: rgba(239, 68, 68, 0.15);
            border: 1px solid rgba(239, 68, 68, 0.3);
            color: var(--danger);
        }}
        
        .unknown {{
            background: rgba(245, 158, 11, 0.15);
            border: 1px solid rgba(245, 158, 11, 0.3);
            color: #f59e0b;
        }}
        
        .warning-item {{
            background: rgba(239, 68, 68, 0.08);
            border: 1px solid rgba(239, 68, 68, 0.2);
            color: #fca5a5;
            padding: 0.75rem 1rem;
            border-radius: 0.5rem;
            margin-bottom: 0.75rem;
            font-size: 0.9rem;
        }}
        
        .no-warning {{
            background: rgba(16, 185, 129, 0.08);
            border: 1px solid rgba(16, 185, 129, 0.2);
            color: #a7f3d0;
            padding: 0.75rem 1rem;
            border-radius: 0.5rem;
            font-size: 0.9rem;
            text-align: center;
        }}
        
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 0.9rem;
        }}
        
        th {{
            text-align: left;
            padding: 0.75rem 1rem;
            color: var(--text-secondary);
            border-bottom: 2px solid var(--border-color);
        }}
        
        td {{
            padding: 0.75rem 1rem;
            border-bottom: 1px solid var(--border-color);
        }}
        
        .code-font {{
            font-family: monospace;
            font-size: 0.8rem;
            color: #cbd5e1;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Email Header Analysis Report</h1>
            <p style="color: var(--text-secondary); margin-top: 0.25rem;">Subject: {email_subject}</p>
        </header>
        
        <div class="grid">
            <div class="left-col">
                <div class="card">
                    <div class="card-title">Routing Hops & Latency Timeline</div>
                    <div style="overflow-x: auto;">
                        <table>
                            <thead>
                                <tr>
                                    <th>Hop</th>
                                    <th>From (Relay)</th>
                                    <th>By (Receiver)</th>
                                    <th>Receive Time</th>
                                    <th>Delay</th>
                                </tr>
                            </thead>
                            <tbody>
                                {"".join(hops_rows)}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
            
            <div class="right-col">
                <div class="card">
                    <div class="card-title">Security Warnings</div>
                    {warnings_list}
                </div>
                
                <div class="card">
                    <div class="card-title">Authentication Overview</div>
                    <div class="auth-badges">
                        <div class="badge {analysis['auth']['spf'].lower()}">
                            <span class="badge-label">SPF</span>
                            {analysis['auth']['spf']}
                        </div>
                        <div class="badge {analysis['auth']['dkim'].lower()}">
                            <span class="badge-label">DKIM</span>
                            {analysis['auth']['dkim']}
                        </div>
                        <div class="badge {analysis['auth']['dmarc'].lower()}">
                            <span class="badge-label">DMARC</span>
                            {analysis['auth']['dmarc']}
                        </div>
                    </div>
                </div>

                <div class="card">
                    <div class="card-title">Key Headers</div>
                    <div class="meta-list">
                        <div class="meta-item"><span class="meta-label">From</span><span class="meta-val">{analysis['metadata']['From']}</span></div>
                        <div class="meta-item"><span class="meta-label">To</span><span class="meta-val">{analysis['metadata']['To']}</span></div>
                        <div class="meta-item"><span class="meta-label">Return-Path</span><span class="meta-val">{analysis['metadata']['Return-Path']}</span></div>
                        <div class="meta-item"><span class="meta-label">Date</span><span class="meta-val">{analysis['metadata']['Date']}</span></div>
                        <div class="meta-item"><span class="meta-label">Message-ID</span><span class="meta-val">{analysis['metadata']['Message-ID']}</span></div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)

def main():
    parser = argparse.ArgumentParser(description="Parse raw email headers to analyze relay hops and security flags.")
    parser.add_argument("header_file", nargs="?", help="Path to raw email headers text file (reads from stdin if omitted)")
    parser.add_argument("-o", "--output-html", help="Path to write the HTML analysis dashboard")
    parser.add_argument("--no-color", action="store_true", help="Disable color output in terminal")
    
    args = parser.parse_args()
    
    if args.header_file:
        try:
            with open(args.header_file, "r", encoding="utf-8") as f:
                raw_headers = f.read()
        except FileNotFoundError:
            print(f"Error: Header file '{args.header_file}' not found.", file=sys.stderr)
            sys.exit(1)
    else:
        # Check if stdin has data
        if sys.stdin.isatty():
            print(f"{COLOR_CYAN}--- Email Header Analyzer ---{COLOR_RESET}")
            print("Paste raw email headers below, then press Ctrl+D (or Ctrl+Z on Windows) followed by Enter:")
            raw_headers = sys.stdin.read()
        else:
            raw_headers = sys.stdin.read()

    if not raw_headers.strip():
        print("Error: No email headers provided.", file=sys.stderr)
        sys.exit(1)

    print("Analyzing email headers...")
    analysis = analyze_headers(raw_headers)
    
    use_color = not args.no_color and has_color_support()
    print_terminal_report(analysis, use_color)
    
    if args.output_html:
        subject = analysis["metadata"]["Subject"]
        output_path = os.path.abspath(args.output_html)
        print(f"Writing HTML report: {output_path}")
        generate_html_report(analysis, subject, output_path)
        print("Done!")

if __name__ == "__main__":
    main()
