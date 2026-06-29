#!/usr/bin/env python3
"""
Python Environment Security Auditor - Runtime diagnostic tool
Audits the current Python runtime settings, library search paths (sys.path),
environment variables, write permissions of install dirs, and SSL/TLS module configurations
for potential security vulnerabilities and misconfigurations.
"""

import argparse
import os
import sys
import ssl
import stat
import tempfile
from typing import Dict, List, Tuple, Any

def check_sys_path() -> List[Dict[str, Any]]:
    """Audit the sys.path search precedence for hijacking or shadowing risks."""
    findings = []
    
    # Check for empty string or dot at the start of sys.path (import shadowing risk)
    if sys.path and sys.path[0] in ('', '.'):
        findings.append({
            "level": "HIGH",
            "check": "Library Path Precedence",
            "details": "The current directory ('' or '.') is placed first in sys.path. A local script could shadow standard library modules and hijack imports.",
            "remediation": "Do not run Python scripts from directories with untrusted files, or remove '' from sys.path dynamically in security-critical applications."
        })
        
    # Check for write permissions in sys.path folders
    for path in sys.path:
        if not path or path == '.':
            continue
        if os.path.exists(path) and os.path.isdir(path):
            # Check if writeable by writing a dummy file and checking permissions
            try:
                temp_file = tempfile.TemporaryFile(dir=path)
                temp_file.close()
                # If we succeeded, it means the current user has write permissions to a search path folder
                # This is worth highlighting if the path is a system-wide path
                is_system_path = any(sys_dir in path for sys_dir in ["Python", "python", "lib", "Lib", "lib64"])
                if is_system_path and os.name == 'posix' and os.getuid() != 0:
                    findings.append({
                        "level": "MEDIUM",
                        "check": "Writable System Search Path",
                        "details": f"System search path '{path}' is writeable by the current non-root user. A local user could plant malicious code.",
                        "remediation": "Restrict write access to Python system directories to administrators or root."
                    })
            except (OSError, PermissionError):
                pass  # Safely not writeable (Good!)
                
    return findings

def check_env_variables() -> List[Dict[str, Any]]:
    """Scan environment variables for raw secrets or credentials."""
    findings = []
    suspicious_keys = ["PASSWORD", "SECRET", "KEY", "TOKEN", "CRED", "AUTH", "API_KEY", "AWS_", "PRIVATE"]
    
    found_secrets = []
    for key, val in os.environ.items():
        key_upper = key.upper()
        if any(s_key in key_upper for s_key in suspicious_keys):
            # Exclude standard/harmless env vars
            if any(exclude in key_upper for exclude in ["PATH", "KEYBOARD", "SESSION_KEY", "KEYRING", "LC_"]):
                continue
            # Basic entropy/length check to filter empty or trivial variables
            if len(val) > 4:
                masked_val = val[:2] + "*" * (len(val) - 4) + val[-2:] if len(val) > 4 else "****"
                found_secrets.append(f"{key}={masked_val}")
                
    if found_secrets:
        findings.append({
            "level": "MEDIUM",
            "check": "Secrets in Environment Variables",
            "details": f"Potential plain text secrets found in os.environ: {', '.join(found_secrets)}",
            "remediation": "Avoid storing passwords or static API keys in plaintext environment variables. Use vault systems or encrypted configurations."
        })
        
    return findings

def check_ssl_configuration() -> List[Dict[str, Any]]:
    """Audit the SSL/TLS configurations of the active ssl module."""
    findings = []
    
    try:
        # Check default context configurations
        context = ssl.create_default_context()
        
        # Verify mode check
        if context.verify_mode != ssl.CERT_REQUIRED:
            findings.append({
                "level": "HIGH",
                "check": "SSL Certificate Verification",
                "details": f"Default SSLContext verify_mode is set to {context.verify_mode} (CERT_REQUIRED expected). Remote connections are vulnerable to MITM attacks.",
                "remediation": "Ensure context.verify_mode = ssl.CERT_REQUIRED is enforced when building SSL contexts."
            })
            
        # Check TLS version support and protocols
        # Ensure older deprecated versions are disabled or unsupported
        deprecated_protocols = []
        
        # Check for SSLv2 / SSLv3 / TLSv1 / TLSv1.1 options
        if hasattr(ssl, "PROTOCOL_SSLv2") and (context.options & ssl.OP_NO_SSLv2) == 0:
            deprecated_protocols.append("SSLv2")
        if hasattr(ssl, "PROTOCOL_SSLv3") and (context.options & ssl.OP_NO_SSLv3) == 0:
            deprecated_protocols.append("SSLv3")
        if hasattr(ssl, "PROTOCOL_TLSv1") and (context.options & ssl.OP_NO_TLSv1) == 0:
            deprecated_protocols.append("TLSv1")
        if hasattr(ssl, "PROTOCOL_TLSv1_1") and (context.options & ssl.OP_NO_TLSv1_1) == 0:
            deprecated_protocols.append("TLSv1.1")
            
        if deprecated_protocols:
            findings.append({
                "level": "MEDIUM",
                "check": "Deprecated SSL/TLS Protocols Enabled",
                "details": f"Default context permits deprecated and vulnerable TLS protocols: {', '.join(deprecated_protocols)}",
                "remediation": "Restrict options to ssl.OP_NO_SSLv2 | ssl.OP_NO_SSLv3 | ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1 in active contexts."
            })
    except Exception as e:
        findings.append({
            "level": "LOW",
            "check": "SSL Module Verification Failed",
            "details": f"Unable to audit default SSL context: {e}",
            "remediation": "Verify that your OpenSSL installation and ssl bindings are correct."
        })
        
    return findings

def check_python_startup() -> List[Dict[str, Any]]:
    """Audit startup variables that automatically execute files."""
    findings = []
    
    # Check PYTHONSTARTUP variable
    startup = os.environ.get("PYTHONSTARTUP")
    if startup:
        findings.append({
            "level": "MEDIUM",
            "check": "PYTHONSTARTUP Configured",
            "details": f"PYTHONSTARTUP environment variable is configured to load: '{startup}'. This script executes automatically when starting interactive shells.",
            "remediation": "Ensure this file cannot be written to by unauthorized users to prevent privilege escalation or persistent hijacking."
        })
        
    # Check PYTHONPATH variable
    pythonpath = os.environ.get("PYTHONPATH")
    if pythonpath:
        findings.append({
            "level": "LOW",
            "check": "PYTHONPATH Configured",
            "details": f"PYTHONPATH is configured: '{pythonpath}'. Custom library search paths are appended to sys.path, which might shadow default packages.",
            "remediation": "Review paths defined in PYTHONPATH to verify they only point to trusted directories."
        })
        
    return findings

def run_audit() -> List[Dict[str, Any]]:
    """Execute all security audits and return findings."""
    all_findings = []
    all_findings.extend(check_sys_path())
    all_findings.extend(check_env_variables())
    all_findings.extend(check_ssl_configuration())
    all_findings.extend(check_python_startup())
    return all_findings

def print_report(findings: List[Dict[str, Any]], format_type: str) -> None:
    """Print the audit results in the requested format."""
    # Count totals
    high = sum(1 for f in findings if f["level"] == "HIGH")
    med = sum(1 for f in findings if f["level"] == "MEDIUM")
    low = sum(1 for f in findings if f["level"] == "LOW")
    
    if format_type == "json":
        report_data = {
            "summary": {"high_risk": high, "medium_risk": med, "low_risk": low, "total": len(findings)},
            "findings": findings
        }
        print(json.dumps(report_data, indent=2))
        return
        
    # Color constants for terminal
    RED = "\033[91m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    RESET = "\033[0m"
    BOLD = "\033[1m"
    
    # Standard terminal reporting
    print(f"\n{BOLD}Python Environment Security Audit Report{RESET}")
    print("=" * 70)
    print(f"Diagnostics summary: "
          f"{RED}{high} High Risk{RESET} | "
          f"{YELLOW}{med} Medium Risk{RESET} | "
          f"{BLUE}{low} Low Risk{RESET}")
    print("=" * 70)
    
    if not findings:
        print(f"\n{GREEN}✔ No security issues or misconfigurations detected! Your environment looks clean.{RESET}\n")
        return
        
    for idx, f in enumerate(findings, 1):
        lvl = f["level"]
        if lvl == "HIGH":
            lvl_fmt = f"{RED}{BOLD}[HIGH RISK]{RESET}"
        elif lvl == "MEDIUM":
            lvl_fmt = f"{YELLOW}{BOLD}[MEDIUM RISK]{RESET}"
        else:
            lvl_fmt = f"{BLUE}{BOLD}[LOW RISK]{RESET}"
            
        print(f"{idx}. {lvl_fmt} {BOLD}{f['check']}{RESET}")
        print(f"   {BOLD}Details:{RESET}     {f['details']}")
        print(f"   {BOLD}Remediation:{RESET} {f['remediation']}")
        print("-" * 70)
        
    print(f"\nAudit complete. Found {len(findings)} items to review.\n")

def main():
    parser = argparse.ArgumentParser(
        description="Python Environment Security Auditor - Runtime diagnostic tool",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "-f", "--format",
        choices=["text", "json"],
        default="text",
        help="Output report format (default: text)"
    )
    
    args = parser.parse_args()
    
    # Verify if terminal supports ANSI colors
    if args.format == "text" and not sys.stdout.isatty():
        # Disable ANSI color escape sequences if piping output
        global RED, YELLOW, BLUE, GREEN, RESET, BOLD
        RED = YELLOW = BLUE = GREEN = RESET = BOLD = ""
        
    findings = run_audit()
    print_report(findings, args.format)
    
    # Exit with code if high risk items are found
    if any(f["level"] == "HIGH" for f in findings):
        sys.exit(2)
    elif findings:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == '__main__':
    main()
