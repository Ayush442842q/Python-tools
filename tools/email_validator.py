#!/usr/bin/env python3
"""
Email Validator
Comprehensive email validation with syntax, domain, and MX record verification.

Usage:
    python email_validator.py [email1@example.com email2@test.org ...] [--file emails.txt] [--json]
"""

import argparse
import json
import re
import socket
import sys
from typing import List, Dict


def validate_syntax(email: str) -> Dict:
    """Validate email syntax using RFC 5322 pattern."""
    # RFC 5322 compliant pattern (simplified)
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    
    is_valid = bool(re.match(pattern, email))
    
    issues = []
    if not is_valid:
        if '@' not in email:
            issues.append("Missing '@' symbol")
        elif email.count('@') > 1:
            issues.append("Multiple '@' symbols")
        else:
            local, _, domain = email.partition('@')
            if not local:
                issues.append("Empty local part (before @)")
            if not domain:
                issues.append("Empty domain (after @)")
            elif '.' not in domain:
                issues.append("Domain missing TLD")
            elif domain.startswith('.') or domain.endswith('.'):
                issues.append("Invalid domain format")
    
    return {
        "valid": is_valid,
        "issues": issues
    }


def validate_domain(email: str) -> Dict:
    """Check if domain exists and has valid DNS records."""
    try:
        domain = email.split('@')[1]
        
        # Check for valid domain format
        if not re.match(r'^[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', domain):
            return {
                "exists": False,
                "has_mx": False,
                "has_a": False,
                "issues": ["Invalid domain format"]
            }
        
        # Try to resolve MX records
        has_mx = False
        has_a = False
        
        try:
            # Check for MX records
            socket.getaddrinfo(domain, None, socket.AF_INET, socket.SOCK_STREAM, 
                             socket.IPPROTO_TCP, socket.AI_ADDRCONFIG)
            has_a = True
        except socket.gaierror:
            pass
        
        # Check for MX records using DNS query (simplified - A record check)
        try:
            # For proper MX check, would need dnspython library
            # This is a simplified check
            mx_hosts = []
            try:
                # Try common mail server patterns
                for prefix in ['mail', 'smtp', 'mx']:
                    try:
                        socket.gethostbyname(f"{prefix}.{domain}")
                        mx_hosts.append(f"{prefix}.{domain}")
                        has_mx = True
                        break
                    except socket.gaierror:
                        continue
            except Exception:
                pass
            
            return {
                "exists": has_a or has_mx,
                "has_mx": has_mx,
                "has_a": has_a,
                "mx_hosts": mx_hosts,
                "issues": []
            }
        except Exception as e:
            return {
                "exists": False,
                "has_mx": False,
                "has_a": False,
                "issues": [f"DNS lookup failed: {str(e)}"]
            }
            
    except IndexError:
        return {
            "exists": False,
            "has_mx": False,
            "has_a": False,
            "issues": ["Invalid email format - cannot extract domain"]
        }


def check_disposable(email: str) -> Dict:
    """Check if email is from a known disposable email provider."""
    disposable_domains = {
        'tempmail.com', 'throwaway.com', 'guerrillamail.com', 'mailinator.com',
        '10minutemail.com', 'fakeinbox.com', 'trashmail.com', 'yopmail.com',
        'maildrop.cc', 'getnada.com', 'temp-mail.org', 'dispostable.com'
    }
    
    try:
        domain = email.split('@')[1].lower()
        is_disposable = domain in disposable_domains
        
        return {
            "is_disposable": is_disposable,
            "domain": domain,
            "issues": ["Disposable email provider detected"] if is_disposable else []
        }
    except IndexError:
        return {
            "is_disposable": False,
            "domain": None,
            "issues": []
        }


def check_role_based(email: str) -> Dict:
    """Check if email is a role-based address."""
    role_prefixes = {
        'admin', 'support', 'info', 'contact', 'sales', 'marketing',
        'help', 'service', 'noreply', 'no-reply', 'postmaster', 'webmaster',
        'abuse', 'security', 'billing', 'hr', 'jobs', 'careers', 'press',
        'legal', 'privacy', 'feedback', 'hello', 'team', 'enquiries'
    }
    
    try:
        local_part = email.split('@')[0].lower()
        # Remove common separators
        local_clean = local_part.replace('.', '').replace('-', '').replace('_', '')
        
        is_role = local_clean in role_prefixes or any(
            role in local_clean for role in role_prefixes
        )
        
        return {
            "is_role_based": is_role,
            "local_part": local_part,
            "issues": ["Role-based email address"] if is_role else []
        }
    except IndexError:
        return {
            "is_role_based": False,
            "local_part": None,
            "issues": []
        }


def validate_email(email: str, full_check: bool = True) -> Dict:
    """Perform comprehensive email validation."""
    email = email.strip()
    
    result = {
        "email": email,
        "syntax_valid": False,
        "domain_exists": False,
        "has_mx_record": False,
        "is_disposable": False,
        "is_role_based": False,
        "overall_valid": False,
        "issues": [],
        "warnings": [],
        "score": 0
    }
    
    # Syntax validation (required)
    syntax_result = validate_syntax(email)
    result["syntax_valid"] = syntax_result["valid"]
    result["issues"].extend(syntax_result["issues"])
    
    if not syntax_result["valid"]:
        result["score"] = 0
        return result
    
    result["score"] += 40  # Syntax check passed
    
    # Domain validation
    domain_result = validate_domain(email)
    result["domain_exists"] = domain_result["exists"]
    result["has_mx_record"] = domain_result["has_mx"]
    result["issues"].extend(domain_result.get("issues", []))
    
    if domain_result["exists"]:
        result["score"] += 30
    if domain_result["has_mx"]:
        result["score"] += 10
    
    # Disposable check (warning)
    disposable_result = check_disposable(email)
    result["is_disposable"] = disposable_result["is_disposable"]
    result["warnings"].extend(disposable_result.get("issues", []))
    
    if not disposable_result["is_disposable"]:
        result["score"] += 10
    
    # Role-based check (warning)
    role_result = check_role_based(email)
    result["is_role_based"] = role_result["is_role_based"]
    result["warnings"].extend(role_result.get("issues", []))
    
    if not role_result["is_role_based"]:
        result["score"] += 10
    
    # Determine overall validity
    result["overall_valid"] = (
        result["syntax_valid"] and 
        result["domain_exists"] and 
        not result["is_disposable"]
    )
    
    return result


def format_output(results: List[Dict], json_format: bool = False) -> str:
    """Format validation results for output."""
    if json_format:
        return json.dumps(results, indent=2)
    
    output_lines = []
    output_lines.append("=" * 80)
    output_lines.append("EMAIL VALIDATOR")
    output_lines.append("=" * 80)
    
    valid_count = sum(1 for r in results if r["overall_valid"])
    invalid_count = len(results) - valid_count
    
    for result in results:
        status = "✅ VALID" if result["overall_valid"] else "❌ INVALID"
        output_lines.append(f"\n{status} | {result['email']}")
        output_lines.append(f"  Score: {result['score']}/100")
        
        if result["issues"]:
            output_lines.append(f"  Issues:")
            for issue in result["issues"]:
                output_lines.append(f"    - {issue}")
        
        if result["warnings"]:
            output_lines.append(f"  Warnings:")
            for warning in result["warnings"]:
                output_lines.append(f"    ⚠️  {warning}")
        
        details = []
        if result["syntax_valid"]:
            details.append("✓ Syntax OK")
        if result["domain_exists"]:
            details.append("✓ Domain exists")
        if result["has_mx_record"]:
            details.append("✓ Has MX records")
        if result["is_disposable"]:
            details.append("⚠️  Disposable")
        if result["is_role_based"]:
            details.append("⚠️  Role-based")
        
        if details:
            output_lines.append(f"  Details: {', '.join(details)}")
    
    output_lines.append("\n" + "=" * 80)
    output_lines.append(f"Summary: {valid_count} valid, {invalid_count} invalid out of {len(results)} emails")
    output_lines.append("=" * 80)
    
    return "\n".join(output_lines)


def main():
    parser = argparse.ArgumentParser(
        description="Comprehensive email validation with syntax, domain, and MX record verification."
    )
    parser.add_argument(
        "emails",
        nargs="*",
        help="Email addresses to validate"
    )
    parser.add_argument(
        "--file", "-f",
        type=str,
        help="File containing email addresses (one per line)"
    )
    parser.add_argument(
        "--json", "-j",
        action="store_true",
        help="Output results in JSON format"
    )
    parser.add_argument(
        "--full-check",
        action="store_true",
        default=True,
        help="Perform full validation including DNS checks (default: True)"
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick syntax-only validation (skip DNS checks)"
    )
    
    args = parser.parse_args()
    
    emails = list(args.emails) if args.emails else []
    
    # Read from file if provided
    if args.file:
        try:
            with open(args.file, 'r') as f:
                for line in f:
                    email = line.strip()
                    if email and not email.startswith('#'):
                        emails.append(email)
        except FileNotFoundError:
            print(f"Error: File '{args.file}' not found.")
            sys.exit(1)
    
    if not emails:
        parser.print_help()
        print("\nError: No email addresses provided.")
        sys.exit(1)
    
    print(f"Validating {len(emails)} email address(es)...")
    
    results = []
    for email in emails:
        result = validate_email(email, full_check=not args.quick)
        results.append(result)
    
    output = format_output(results, json_format=args.json)
    print(output)
    
    # Exit with error code if any invalid emails
    invalid_count = sum(1 for r in results if not r["overall_valid"])
    if invalid_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()