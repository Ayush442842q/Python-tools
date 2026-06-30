#!/usr/bin/env python3
"""
Robots.txt Tester & Analyzer

Parses robots.txt files (from local file or remote URL) and analyzes the rules.
Tests whether a specific User-Agent is allowed to access certain URL paths.

Usage:
    python robots_txt_analyzer.py [source] -u [user_agent] -p [path]
"""

import sys
import os
import argparse
import urllib.request
import urllib.parse
import re
import ssl

def fetch_robots_txt(url_or_path):
    """Fetches robots.txt from a URL or reads it from a local file path."""
    if url_or_path.startswith(('http://', 'https://')):
        # Ensure it points to the robots.txt file specifically
        parsed = urllib.parse.urlparse(url_or_path)
        if not parsed.path.endswith('robots.txt'):
            # Reconstruct URL with /robots.txt
            url_or_path = urllib.parse.urlunparse((
                parsed.scheme,
                parsed.netloc,
                '/robots.txt',
                '', '', ''
            ))
            
        print(f"Fetching remote robots.txt from: {url_or_path}")
        
        # Bypass SSL verification issues in case of self-signed certs
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        req = urllib.request.Request(
            url_or_path, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) RobotsTxtAnalyzer/1.0'}
        )
        
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
                return response.read().decode('utf-8', errors='ignore')
        except Exception as e:
            print(f"Error fetching robots.txt: {e}", file=sys.stderr)
            return None
    else:
        # Local file
        if not os.path.exists(url_or_path):
            print(f"Error: Local file '{url_or_path}' does not exist.", file=sys.stderr)
            return None
        print(f"Reading local robots.txt from: {url_or_path}")
        try:
            with open(url_or_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception as e:
            print(f"Error reading local file: {e}", file=sys.stderr)
            return None

def parse_robots_txt(content):
    """
    Parses the robots.txt content into structured rules.
    Returns a dict with:
        'sitemaps': list of sitemap URLs
        'groups': dict mapping normalized User-Agents to list of (directive, path) tuples
        'crawl_delays': dict mapping normalized User-Agents to float delay
    """
    sitemaps = []
    groups = {}
    crawl_delays = {}
    
    current_agents = []
    
    # Strip comments and process line by line
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
            
        # Split directive and value at the first colon
        if ':' not in line:
            continue
        directive, value = line.split(':', 1)
        directive = directive.strip().lower()
        value = value.strip()
        
        if directive == 'sitemap':
            sitemaps.append(value)
        elif directive == 'user-agent':
            # User-agents can be listed consecutively for the same rule block
            agent = value.lower()
            current_agents.append(agent)
            if agent not in groups:
                groups[agent] = []
        elif directive in ('allow', 'disallow'):
            # Apply directive to all current User-Agents
            for agent in current_agents:
                groups[agent].append((directive, value))
        elif directive == 'crawl-delay':
            try:
                delay = float(value)
                for agent in current_agents:
                    crawl_delays[agent] = delay
            except ValueError:
                pass
        else:
            # Other non-standard directives (e.g. Host, Request-rate) can be ignored
            pass
            
        # Reset current agents if a new block starts, but wait!
        # Consecutive User-Agent: lines build up the current_agents list.
        # Directives (allow/disallow) apply to current_agents.
        # If we see another User-Agent line AFTER seeing directives, we start a new group.
        # So we need to detect state transitions.
        # Let's handle state: if we saw a directive, and now see another user-agent, reset the current_agents.
    
    # A cleaner parsing algorithm that handles state correctly:
    groups = {}
    crawl_delays = {}
    sitemaps = []
    
    current_agents = []
    last_was_directive = False
    
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
            
        if ':' not in line:
            continue
        directive, value = line.split(':', 1)
        directive = directive.strip().lower()
        value = value.strip()
        
        if directive == 'sitemap':
            sitemaps.append(value)
            continue
            
        if directive == 'user-agent':
            if last_was_directive:
                current_agents = []
                last_was_directive = False
            agent = value.lower()
            current_agents.append(agent)
            if agent not in groups:
                groups[agent] = []
            continue
            
        if directive in ('allow', 'disallow', 'crawl-delay'):
            last_was_directive = True
            for agent in current_agents:
                if directive == 'crawl-delay':
                    try:
                        crawl_delays[agent] = float(value)
                    except ValueError:
                        pass
                else:
                    groups[agent].append((directive, value))
                    
    return {
        'sitemaps': sitemaps,
        'groups': groups,
        'crawl_delays': crawl_delays
    }

def match_path(rule_path, test_path):
    """
    Checks if test_path matches the robots.txt rule_path pattern.
    Supports basic wildcards * and line-end anchor $.
    """
    # Escape special regex characters except * and $
    pattern = re.escape(rule_path)
    # Replace escaped * with .*
    pattern = pattern.replace(r'\*', '.*')
    # Replace escaped $ at the end with $
    if pattern.endswith(r'\$'):
        pattern = pattern[:-2] + '$'
    else:
        # Standard robots.txt prefix matching means it matches anything starting with rule_path
        # so we don't anchor it at the end unless $ was specified
        pass
        
    # Ensure it matches from the start of the path
    pattern = '^' + pattern
    
    try:
        return re.match(pattern, test_path) is not None
    except Exception:
        # Fallback to simple starts-with prefix matching
        return test_path.startswith(rule_path)

def check_permission(parsed_rules, user_agent, path):
    """
    Evaluates whether user_agent is allowed to access path.
    Precedence rules (Google/standard robots.txt RFC):
      1. More specific matches (longer rule path) take precedence.
      2. If matching paths have the same length, 'allow' takes precedence over 'disallow'.
      3. If no rules match, the path is allowed.
    """
    user_agent = user_agent.lower()
    path = urllib.parse.unquote(path)
    
    # 1. Identify which agent group applies.
    # We look for exact match first (e.g. 'googlebot'), then fallback to '*' wildcard group.
    matching_agent = None
    if user_agent in parsed_rules['groups']:
        matching_agent = user_agent
    elif '*' in parsed_rules['groups']:
        matching_agent = '*'
        
    if not matching_agent:
        return True, "No matching user-agent rules found. Default allowed."
        
    rules = parsed_rules['groups'][matching_agent]
    
    # Filter matching rules
    matching_rules = []
    for directive, rule_path in rules:
        if match_path(rule_path, path):
            matching_rules.append((directive, rule_path))
            
    if not matching_rules:
        return True, f"No rules matched path '{path}'. Default allowed."
        
    # Standard RFC Rule evaluation:
    # Google standard: Rules are sorted by length of rule path (descending).
    # If lengths are equal, 'allow' beats 'disallow'.
    # If length is 0 (empty disallow), it means Allow all.
    matching_rules.sort(key=lambda r: (len(r[1]), r[0] == 'allow'), reverse=True)
    
    longest_match = matching_rules[0]
    directive, rule_path = longest_match
    
    if directive == 'allow':
        return True, f"Allowed by rule: '{directive}: {rule_path}'"
    else:
        return False, f"Disallowed by rule: '{directive}: {rule_path}'"

def main():
    parser = argparse.ArgumentParser(
        description="Fetch, parse, and analyze robots.txt files. Test crawler path permissions.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "source",
        nargs="?",
        default="https://google.com/robots.txt",
        help="URL (e.g. https://example.com) or local file path to robots.txt"
    )
    
    parser.add_argument(
        "-u", "--user-agent",
        default="*",
        help="User-agent crawler name to test (default: '*')"
    )
    
    parser.add_argument(
        "-p", "--path",
        default="/",
        help="URL path to check (default: '/')"
    )
    
    parser.add_argument(
        "--show-rules",
        action="store_true",
        help="Print all parsed rules, sitemaps, and crawl delays"
    )
    
    args = parser.parse_args()
    
    content = fetch_robots_txt(args.source)
    if not content:
        return 1
        
    parsed = parse_robots_txt(content)
    
    if args.show_rules:
        print("\n" + "=" * 50)
        print("PARSED ROBOTS.TXT RULES")
        print("=" * 50)
        
        if parsed['sitemaps']:
            print("Sitemaps:")
            for s in parsed['sitemaps']:
                print(f"  - {s}")
            print()
            
        print("User-Agent Groups:")
        for agent, rules in parsed['groups'].items():
            delay_str = f" (Crawl-delay: {parsed['crawl_delays'][agent]}s)" if agent in parsed['crawl_delays'] else ""
            print(f"  User-Agent: {agent}{delay_str}")
            if not rules:
                print("    (No directives)")
            for directive, path in rules:
                print(f"    {directive.capitalize()}: {path}")
        print("=" * 50 + "\n")
        
    # Check permissions
    allowed, reason = check_permission(parsed, args.user_agent, args.path)
    
    print("Testing Permission:")
    print(f"  User-Agent:  {args.user_agent}")
    print(f"  Path:        {args.path}")
    print(f"  Result:      " + ("\033[92mALLOWED\033[0m" if allowed else "\033[91mDISALLOWED\033[0m"))
    print(f"  Reason:      {reason}")
    
    if args.user_agent != '*' and args.user_agent in parsed['crawl_delays']:
        print(f"  Crawl Delay: {parsed['crawl_delays'][args.user_agent]} seconds")
    elif '*' in parsed['crawl_delays']:
        print(f"  Crawl Delay: {parsed['crawl_delays']['*']} seconds (inherited from '*')")
        
    return 0 if allowed else 1

if __name__ == "__main__":
    sys.exit(main())
