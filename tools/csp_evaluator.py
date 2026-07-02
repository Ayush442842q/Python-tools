#!/usr/bin/env python3
"""
Content Security Policy (CSP) Evaluator - Parse and audit CSP configurations for security issues.
"""

import sys
import re
import argparse
from urllib.request import Request, urlopen
from urllib.error import URLError

def get_color(color_name):
    """Return ANSI escape code for terminal color if supported."""
    colors = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'bold': '\033[1m',
        'reset': '\033[0m'
    }
    if sys.platform == 'win32':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            return ''
    return colors.get(color_name, '')

def parse_csp(csp_string):
    """Parse CSP string into a dictionary of directives."""
    directives = {}
    # Split by semicolon, clean up whitespace
    raw_directives = [d.strip() for d in csp_string.split(';') if d.strip()]
    
    for raw in raw_directives:
        parts = raw.split()
        if not parts:
            continue
        name = parts[0].lower()
        values = parts[1:]
        directives[name] = values
    return directives

def fetch_csp_from_url(url):
    """Fetch CSP headers and meta tags from a URL."""
    req = Request(url, headers={'User-Agent': 'Mozilla/5.0 (CSP-Evaluator)'})
    try:
        with urlopen(req, timeout=10) as response:
            headers = response.info()
            csp_header = headers.get('Content-Security-Policy')
            
            html_content = response.read().decode('utf-8', errors='ignore')
            # Extract meta tags
            meta_csps = re.findall(
                r'<meta\s+http-equiv=["\']Content-Security-Policy["\']\s+content=["\'](.*?)["\']',
                html_content,
                re.IGNORECASE
            )
            
            return {
                'csp_header': csp_header,
                'meta_csps': meta_csps
            }
    except URLError as e:
        print(f"Error fetching URL: {e}", file=sys.stderr)
        sys.exit(1)

def evaluate_csp(directives):
    """Evaluate directives and return a list of findings."""
    findings = []
    
    # Critical directives to check
    sensitive_directives = ['script-src', 'object-src', 'base-uri', 'default-src']
    
    # 1. Check if default-src or script-src is present
    if 'default-src' not in directives:
        findings.append({
            'severity': 'HIGH',
            'directive': 'default-src',
            'issue': 'Missing default-src directive.',
            'description': 'Without default-src, unspecified directives fallback to "*" (allow everything).',
            'recommendation': "Define 'default-src 'none'' or 'default-src 'self'' as a fallback."
        })
        
    if 'object-src' not in directives and 'default-src' in directives:
        default_val = directives.get('default-src')
        if '*' in default_val or 'http:' in default_val or 'https:' in default_val:
            findings.append({
                'severity': 'HIGH',
                'directive': 'object-src',
                'issue': 'Missing object-src directive and default-src is permissive.',
                'description': 'Allows execution of plugins like Flash or Silverlight, which can lead to XSS.',
                'recommendation': "Define 'object-src 'none''."
            })
    elif 'object-src' not in directives:
        findings.append({
            'severity': 'HIGH',
            'directive': 'object-src',
            'issue': 'Missing object-src directive.',
            'description': 'Plugin execution is not restricted. Flash/Java/Silverlight plugins can be injected.',
            'recommendation': "Define 'object-src 'none''."
        })

    if 'base-uri' not in directives:
        findings.append({
            'severity': 'MEDIUM',
            'directive': 'base-uri',
            'issue': 'Missing base-uri directive.',
            'description': 'Allows injection of <base> tags to redirect relative script/style loads to malicious domains.',
            'recommendation': "Define 'base-uri 'none'' or 'base-uri 'self''."
        })

    # Evaluate each directive values
    for dir_name, values in directives.items():
        # Check for unsafe-inline
        if "'unsafe-inline'" in values:
            if dir_name == 'script-src' or (dir_name == 'default-src' and 'script-src' not in directives):
                findings.append({
                    'severity': 'HIGH',
                    'directive': dir_name,
                    'issue': "Use of 'unsafe-inline' detected.",
                    'description': "Allows inline scripts to execute, rendering CSP ineffective against classic XSS.",
                    'recommendation': "Remove 'unsafe-inline' and use Nonces or Hashes instead."
                })
            elif dir_name == 'style-src':
                findings.append({
                    'severity': 'LOW',
                    'directive': dir_name,
                    'issue': "Use of 'unsafe-inline' detected in styles.",
                    'description': "Allows inline styles, which can lead to visual defacement or data exfiltration via CSS selectors.",
                    'recommendation': "Avoid inline styles or restrict using hashes/nonces if possible."
                })

        # Check for unsafe-eval
        if "'unsafe-eval'" in values:
            if dir_name in ['script-src', 'default-src']:
                findings.append({
                    'severity': 'MEDIUM',
                    'directive': dir_name,
                    'issue': "Use of 'unsafe-eval' detected.",
                    'description': "Allows string-to-code execution functions like eval(), setTimeout(string), etc.",
                    'recommendation': "Refactor application to avoid dynamically evaluated strings."
                })

        # Check for wildcards and insecure schemes
        for val in values:
            if val in ['*', 'http:', 'https:', 'data:'] and dir_name in sensitive_directives:
                findings.append({
                    'severity': 'HIGH',
                    'directive': dir_name,
                    'issue': f"Permissive scheme or wildcard '{val}' in source list.",
                    'description': f"Using '{val}' allows resources to be loaded from anywhere, bypassing domain whitelist restrictions.",
                    'recommendation': "Specify trusted, strict domains instead of wildcards or broad protocols."
                })
            elif val.startswith('http://') and dir_name in sensitive_directives:
                findings.append({
                    'severity': 'MEDIUM',
                    'directive': dir_name,
                    'issue': f"Insecure HTTP source '{val}'.",
                    'description': "Allows loading assets over HTTP, exposing connection to Man-in-the-Middle (MitM) attacks.",
                    'recommendation': f"Upgrade to secure protocol: '{val.replace('http://', 'https://')}'."
                })

    return findings

def main():
    parser = argparse.ArgumentParser(
        description="Content Security Policy (CSP) Evaluator - Scan and audit CSP headers/meta tags."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--csp', help="Raw CSP string to evaluate.")
    group.add_argument('--url', help="URL of a webpage to fetch and evaluate.")
    group.add_argument('--file', help="Local HTML file containing meta tags/CSP details.")
    
    args = parser.parse_args()
    
    c_red = get_color('red')
    c_green = get_color('green')
    c_yellow = get_color('yellow')
    c_blue = get_color('blue')
    c_bold = get_color('bold')
    c_reset = get_color('reset')
    
    policies_to_check = []
    
    if args.csp:
        policies_to_check.append(("Manual CLI Input", args.csp))
    elif args.url:
        print(f"Fetching CSP from URL: {args.url} ...")
        result = fetch_csp_from_url(args.url)
        if result['csp_header']:
            policies_to_check.append(("HTTP Response Header", result['csp_header']))
        for idx, meta_csp in enumerate(result['meta_csps'], 1):
            policies_to_check.append((f"Meta Tag #{idx}", meta_csp))
        if not policies_to_check:
            print(f"{c_red}No CSP headers or meta tag policies found at the URL.{c_reset}")
            return
    elif args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                content = f.read()
                # Find CSP meta tags
                meta_csps = re.findall(
                    r'<meta\s+http-equiv=["\']Content-Security-Policy["\']\s+content=["\'](.*?)["\']',
                    content,
                    re.IGNORECASE
                )
                for idx, meta_csp in enumerate(meta_csps, 1):
                    policies_to_check.append((f"File Meta Tag #{idx}", meta_csp))
        except FileNotFoundError:
            print(f"{c_red}File not found: {args.file}{c_reset}", file=sys.stderr)
            sys.exit(1)
            
        if not policies_to_check:
            # Try to read the whole file as a raw CSP
            with open(args.file, 'r', encoding='utf-8') as f:
                raw_csp = f.read().strip()
                if raw_csp:
                    policies_to_check.append(("File Raw Content", raw_csp))
                else:
                    print(f"{c_red}No CSP policy found in file: {args.file}{c_reset}")
                    return

    for source_name, csp_str in policies_to_check:
        print("\n" + "=" * 60)
        print(f"{c_bold}Auditing CSP Source: {source_name}{c_reset}")
        print("-" * 60)
        print(f"{c_blue}Raw CSP Policy:{c_reset}\n{csp_str}\n")
        
        directives = parse_csp(csp_str)
        
        print(f"{c_bold}Directives Parsed ({len(directives)}):{c_reset}")
        for dir_name, values in sorted(directives.items()):
            print(f"  - {c_blue}{dir_name}{c_reset}: {', '.join(values)}")
        print("-" * 60)
        
        findings = evaluate_csp(directives)
        
        if not findings:
            print(f"{c_green}[PASS] No security issues found in this policy! Excellent work.{c_reset}")
        else:
            findings_by_severity = {'HIGH': [], 'MEDIUM': [], 'LOW': [], 'INFO': []}
            for f in findings:
                findings_by_severity[f['severity']].append(f)
            
            # Print findings
            for severity in ['HIGH', 'MEDIUM', 'LOW', 'INFO']:
                list_f = findings_by_severity[severity]
                if not list_f:
                    continue
                
                color = c_red if severity == 'HIGH' else (c_yellow if severity == 'MEDIUM' else c_blue)
                for f in list_f:
                    print(f"[{color}{severity}{c_reset}] Directive: {c_bold}{f['directive']}{c_reset}")
                    print(f"  * Issue: {f['issue']}")
                    print(f"  * Details: {f['description']}")
                    print(f"  * Remedy: {c_green}{f['recommendation']}{c_reset}\n")

if __name__ == '__main__':
    main()
