#!/usr/bin/env python3
"""
Nginx Configuration Parser & Linter

An offline linter for Nginx configuration files to check for security vulnerabilities,
performance improvements, and structural issues.

Usage:
    python tools/nginx_config_linter.py /path/to/nginx.conf
"""

import re
import sys
import argparse
from pathlib import Path

# Colors for terminal output
COLOR_CRITICAL = "\033[91m[CRITICAL]\033[0m"
COLOR_WARNING = "\033[93m[WARNING]\033[0m"
COLOR_INFO = "\033[94m[INFO]\033[0m"
COLOR_SUCCESS = "\033[92m[OK]\033[0m"

class NginxLinter:
    def __init__(self, filepath):
        self.filepath = Path(filepath)
        self.lines = []
        self.errors = []
        self.warnings = []
        self.infos = []

    def load_config(self):
        """Load config lines, keeping line numbers."""
        if not self.filepath.exists():
            raise FileNotFoundError(f"Config file '{self.filepath}' not found.")
        with open(self.filepath, "r", encoding="utf-8", errors="ignore") as f:
            self.lines = [line.rstrip() for line in f]

    def add_issue(self, severity, line_num, content, message, recommendation):
        issue = {
            "line": line_num,
            "content": content.strip(),
            "message": message,
            "recommendation": recommendation
        }
        if severity == "CRITICAL":
            self.errors.append(issue)
        elif severity == "WARNING":
            self.warnings.append(issue)
        else:
            self.infos.append(issue)

    def lint(self):
        """Lint the configuration lines."""
        brace_count = 0
        server_block = False
        ssl_enabled = False
        has_hsts = False
        has_server_tokens_off = False
        has_x_frame_options = False
        has_x_content_type = False
        has_csp = False
        autoindex_on_lines = []
        
        # Keep track of location blocks and alias usage for path traversal checks
        location_path = None
        location_line = 0

        for idx, line in enumerate(self.lines):
            line_num = idx + 1
            line_clean = line.strip()
            
            # Skip empty lines or full comments
            if not line_clean or line_clean.startswith("#"):
                continue
                
            # Strip trailing comments for directives analysis
            line_code = re.sub(r"\s*#.*$", "", line_clean)
            
            # Simple brace matching tracker
            brace_count += line_code.count("{")
            brace_count -= line_code.count("}")

            # Detect server block boundaries
            if "server {" in line_code or line_code == "server":
                server_block = True
                ssl_enabled = False
                has_hsts = False
                has_x_frame_options = False
                has_x_content_type = False
                has_csp = False
                
            if server_block and brace_count == 0:
                server_block = False
                # Post-server-block validation
                if ssl_enabled:
                    if not has_hsts:
                        self.add_issue(
                            "WARNING", line_num, "server { ... }",
                            "SSL is enabled, but HTTP Strict Transport Security (HSTS) header is missing.",
                            "Add: add_header Strict-Transport-Security \"max-age=31536000; includeSubDomains\" always;"
                        )
                    if not has_x_frame_options:
                        self.add_issue(
                            "INFO", line_num, "server { ... }",
                            "Missing 'X-Frame-Options' header to prevent Clickjacking.",
                            "Add: add_header X-Frame-Options \"SAMEORIGIN\" always;"
                        )
                    if not has_x_content_type:
                        self.add_issue(
                            "INFO", line_num, "server { ... }",
                            "Missing 'X-Content-Type-Options' header to prevent MIME sniffing.",
                            "Add: add_header X-Content-Type-Options \"nosniff\" always;"
                        )
            
            # Check server tokens (signature disclosure)
            if "server_tokens" in line_code:
                if "server_tokens off" in line_code:
                    has_server_tokens_off = True
                elif "server_tokens on" in line_code:
                    self.add_issue(
                        "WARNING", line_num, line_clean,
                        "Server tokens are explicitly enabled, which leaks Nginx version details.",
                        "Change to: server_tokens off;"
                    )

            # Check directory listing
            if "autoindex on" in line_code:
                autoindex_on_lines.append((line_num, line_clean))

            # SSL/TLS Protocols Check
            if "ssl_protocols" in line_code:
                ssl_enabled = True
                # Detect old/unsafe protocols
                if any(proto in line_code for proto in ["SSLv2", "SSLv3", "TLSv1 ", "TLSv1;", "TLSv1.1"]):
                    self.add_issue(
                        "CRITICAL", line_num, line_clean,
                        "Insecure SSL/TLS protocols (SSLv2, SSLv3, TLSv1, TLSv1.1) are enabled.",
                        "Only support secure protocols: ssl_protocols TLSv1.2 TLSv1.3;"
                    )

            # SSL Ciphers Check (weak ciphers)
            if "ssl_ciphers" in line_code:
                ssl_enabled = True
                weak_ciphers = ["NULL", "MD5", "RC4", "3DES", "DES", "ADH", "EXPORT"]
                found_weak = [wc for wc in weak_ciphers if wc in line_code.upper()]
                if found_weak:
                    self.add_issue(
                        "CRITICAL", line_num, line_clean,
                        f"Weak/deprecated SSL ciphers detected: {', '.join(found_weak)}.",
                        "Update ssl_ciphers directive to modern secure suites (e.g., ECDHE-ECDSA-AES128-GCM-SHA256:...)."
                    )

            # Security Headers Check
            if "add_header" in line_code:
                header_name = line_code.lower()
                if "strict-transport-security" in header_name:
                    has_hsts = True
                elif "x-frame-options" in header_name:
                    has_x_frame_options = True
                elif "x-content-type-options" in header_name:
                    has_x_content_type = True
                elif "content-security-policy" in header_name:
                    has_csp = True
                
                # Check for overly broad CORS
                if "access-control-allow-origin" in header_name and "*" in line_code:
                    self.add_issue(
                        "WARNING", line_num, line_clean,
                        "Access-Control-Allow-Origin header is set to wildcard (*).",
                        "Restrict access to trusted domains for authenticated resources."
                    )

            # Location blocks alias path traversal check
            # e.g., location /img/ { alias /var/www/images/; } is safe.
            # but location /img/ { alias /var/www/images; } or location /img { alias /var/www/images/; } is vulnerable.
            loc_match = re.search(r"location\s+([^\s{]+)\s*\{", line_code)
            if loc_match:
                location_path = loc_match.group(1)
                location_line = line_num
                
            if location_path and "alias " in line_code:
                alias_match = re.search(r"alias\s+([^;]+);", line_code)
                if alias_match:
                    alias_path = alias_match.group(1).strip()
                    loc_ends_slash = location_path.endswith("/")
                    alias_ends_slash = alias_path.endswith("/")
                    if loc_ends_slash != alias_ends_slash:
                        self.add_issue(
                            "CRITICAL", line_num, line_clean,
                            f"Alias directive path traversal vulnerability (Location '{location_path}' and Alias '{alias_path}' slash mismatch).",
                            f"Ensure both have or do not have trailing slashes: e.g. location '{location_path.rstrip('/')}/' and alias '{alias_path.rstrip('/')}/'."
                        )
                # Reset tracking
                location_path = None

            # Check cleartext root/password configurations
            if "auth_basic_user_file" in line_code:
                if not any(x in line_code for x in ["htpasswd", "secret", "private"]):
                    self.add_issue(
                        "INFO", line_num, line_clean,
                        "Ensure the basic authentication password file is stored in a secure non-web-accessible directory.",
                        "Verify file permissions: chmod 600 /etc/nginx/conf.d/.htpasswd"
                    )

        # Global findings
        if not has_server_tokens_off:
            self.add_issue(
                "INFO", 0, "Global Scope",
                "Directive 'server_tokens off;' is missing in the global configuration.",
                "Add 'server_tokens off;' to the HTTP block to hide the Nginx server version."
            )
            
        for l_num, val in autoindex_on_lines:
            self.add_issue(
                "WARNING", l_num, val,
                "Directory indexing ('autoindex on;') is enabled, exposing directory structures.",
                "Ensure this is intentional. If not, set 'autoindex off;'."
            )

    def print_report(self):
        """Display finding results in a structured list."""
        total_issues = len(self.errors) + len(self.warnings) + len(self.infos)
        print(f"=== Nginx Linter Report: {self.filepath.name} ===")
        print(f"Found {total_issues} issue(s) ({len(self.errors)} Critical, {len(self.warnings)} Warning, {len(self.infos)} Info)\n")

        def print_items(items, label):
            for item in items:
                line_str = f"Line {item['line']}: " if item['line'] > 0 else ""
                print(f"{label} {line_str}{item['message']}")
                print(f"  Code:   {item['content']}")
                print(f"  Fix:    {item['recommendation']}\n")

        print_items(self.errors, COLOR_CRITICAL)
        print_items(self.warnings, COLOR_WARNING)
        print_items(self.infos, COLOR_INFO)
        
        if total_issues == 0:
            print(f"{COLOR_SUCCESS} Config looks clean and follows basic security standards!")

def main():
    parser = argparse.ArgumentParser(description="Offline Nginx configuration parser and security linter")
    parser.add_argument("config_file", help="Path to Nginx configuration file")
    args = parser.parse_args()

    linter = NginxLinter(args.config_file)
    try:
        linter.load_config()
        linter.lint()
        linter.print_report()
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0

if __name__ == "__main__":
    sys.exit(main())
