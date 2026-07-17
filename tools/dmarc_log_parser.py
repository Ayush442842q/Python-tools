#!/usr/bin/env python3
"""
DMARC XML Log Parser & Reporter

A standalone utility to parse and summarize DMARC XML aggregate feedback reports.
1. Auto-detects and extracts compressed reports natively (.xml or .zip).
2. Parses XML data using python's built-in `xml.etree.ElementTree`.
3. Reports metadata: reporting org, date range, published SPF/DKIM policy.
4. Generates a summary table: source IP, message counts, DMARC policy evaluations
   (pass/fail/disposition), SPF/DKIM authentication and alignment results.

Usage:
    python dmarc_log_parser.py google.com!example.com!1580000000!1580100000.xml
    python dmarc_log_parser.py dmarc_report.xml.zip
"""

import sys
import os
import argparse
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime

def parse_epoch(epoch_str):
    """Converts epoch string to human readable YYYY-MM-DD timestamp."""
    try:
        return datetime.fromtimestamp(int(epoch_str)).strftime('%Y-%m-%d %H:%M:%S')
    except Exception:
        return epoch_str

def parse_dmarc_xml(xml_content):
    """Parses DMARC XML content and returns structured report data."""
    try:
        root = ET.fromstring(xml_content)
    except Exception as e:
        return None, f"Failed parsing XML content: {e}"

    # 1. Metadata
    metadata = {}
    meta_node = root.find('report_metadata')
    if meta_node is not None:
        metadata['org'] = meta_node.findtext('org_name', 'N/A')
        metadata['email'] = meta_node.findtext('email', 'N/A')
        metadata['report_id'] = meta_node.findtext('report_id', 'N/A')
        
        date_range = meta_node.find('date_range')
        if date_range is not None:
            metadata['start'] = parse_epoch(date_range.findtext('begin', '0'))
            metadata['end'] = parse_epoch(date_range.findtext('end', '0'))
            
    # 2. Published Policy
    policy = {}
    policy_node = root.find('policy_published')
    if policy_node is not None:
        policy['domain'] = policy_node.findtext('domain', 'N/A')
        policy['adkim'] = policy_node.findtext('adkim', 'r')  # r = relaxed, s = strict
        policy['aspf'] = policy_node.findtext('aspf', 'r')
        policy['p'] = policy_node.findtext('p', 'none')
        policy['sp'] = policy_node.findtext('sp', 'none')
        policy['pct'] = policy_node.findtext('pct', '100')

    # 3. Records List
    records = []
    for record in root.findall('record'):
        row = record.find('row')
        if row is None:
            continue
            
        source_ip = row.findtext('source_ip', 'N/A')
        count = int(row.findtext('count', '0'))
        
        policy_eval = row.find('policy_evaluated')
        disposition = 'none'
        dkim_align = 'fail'
        spf_align = 'fail'
        
        if policy_eval is not None:
            disposition = policy_eval.findtext('disposition', 'none')
            dkim_align = policy_eval.findtext('dkim', 'fail')
            spf_align = policy_eval.findtext('spf', 'fail')
            
        # Raw Auth Results
        dkim_auth_list = []
        spf_auth_list = []
        
        auth_results = record.find('auth_results')
        if auth_results is not None:
            for d in auth_results.findall('dkim'):
                domain = d.findtext('domain', '')
                result = d.findtext('result', '')
                if domain and result:
                    dkim_auth_list.append(f"{domain}:{result}")
                    
            for s in auth_results.findall('spf'):
                domain = s.findtext('domain', '')
                result = s.findtext('result', '')
                if domain and result:
                    spf_auth_list.append(f"{domain}:{result}")
                    
        records.append({
            'source_ip': source_ip,
            'count': count,
            'disposition': disposition,
            'dkim_align': dkim_align,
            'spf_align': spf_align,
            'dkim_auth': ", ".join(dkim_auth_list) if dkim_auth_list else "none",
            'spf_auth': ", ".join(spf_auth_list) if spf_auth_list else "none"
        })
        
    return {
        'metadata': metadata,
        'policy': policy,
        'records': records
    }, None

def load_file_content(filepath):
    """Loads file bytes, unpacking ZIP if needed."""
    if not os.path.exists(filepath):
        return None, f"File '{filepath}' not found."

    # Handle ZIP files
    if zipfile.is_zipfile(filepath):
        try:
            with zipfile.ZipFile(filepath, 'r') as z:
                # Find XML file inside zip
                xml_files = [name for name in z.namelist() if name.lower().endswith('.xml')]
                if not xml_files:
                    return None, "No XML files found inside the ZIP archive."
                # Extract first XML content
                return z.read(xml_files[0]), None
        except Exception as e:
            return None, f"Failed reading ZIP archive: {e}"

    # Handle raw XML files
    try:
        with open(filepath, 'rb') as f:
            return f.read(), None
    except Exception as e:
        return None, f"Failed reading file: {e}"

def generate_report(data):
    """Prints a structured summary of the DMARC report."""
    meta = data['metadata']
    policy = data['policy']
    records = data['records']
    
    print("DMARC XML Feedback Report Summary")
    print("=" * 75)
    print(f"Reporting Org : {meta.get('org', 'N/A')}")
    print(f"Report ID     : {meta.get('report_id', 'N/A')}")
    print(f"Date Range    : {meta.get('start', 'N/A')} to {meta.get('end', 'N/A')}")
    print(f"Contact Email : {meta.get('email', 'N/A')}")
    print("=" * 75)
    
    print("\n[Published SPF/DKIM Policy]")
    print("-" * 75)
    print(f"  Target Domain  : {policy.get('domain', 'N/A')}")
    print(f"  Primary Policy : p={policy.get('p', 'none')} | sp={policy.get('sp', 'none')} | pct={policy.get('pct', '100')}%")
    print(f"  Alignment Rules: DKIM={policy.get('adkim', 'relaxed')} | SPF={policy.get('aspf', 'relaxed')}")
    print("-" * 75)
    
    if not records:
        print("\nNo traffic data records found in feedback report.")
        return
        
    print("\n[Mail Traffic Records]")
    print("=" * 75)
    row_fmt = "  {:<18} | {:<6} | {:<12} | {:<7} | {:<7}"
    print(row_fmt.format("Sender IP", "Volume", "Disposition", "DKIM", "SPF"))
    print("  " + "-" * 71)
    
    total_volume = 0
    dmarc_pass = 0
    dmarc_fail = 0
    
    for r in records:
        total_volume += r['count']
        
        # Check alignment passes
        dk_p = r['dkim_align'] == 'pass'
        sf_p = r['spf_align'] == 'pass'
        
        # DMARC requires either SPF or DKIM to pass and align
        if dk_p or sf_p:
            dmarc_pass += r['count']
            align_desc = "pass"
        else:
            dmarc_fail += r['count']
            align_desc = "fail"
            
        print(row_fmt.format(
            r['source_ip'], 
            r['count'], 
            r['disposition'], 
            r['dkim_align'], 
            r['spf_align']
        ))
        
        # Output sub-details of authentication checks
        try:
            print(f"    └── DKIM Auth: {r['dkim_auth']}")
            print(f"    └── SPF Auth : {r['spf_auth']}")
        except UnicodeEncodeError:
            print(f"    \\-- DKIM Auth: {r['dkim_auth']}")
            print(f"    \\-- SPF Auth : {r['spf_auth']}")
        print()
        
    print("=" * 75)
    print("DMARC AUTHENTICATION COMPLIANCE SUMMARY")
    print("=" * 75)
    print(f"  Total Message Volume    : {total_volume}")
    print(f"  DMARC Compliant (Pass)  : {dmarc_pass} ({(dmarc_pass/total_volume)*100:.2f}%)" if total_volume > 0 else "0 (0.00%)")
    print(f"  DMARC Non-compliant (Fail): {dmarc_fail} ({(dmarc_fail/total_volume)*100:.2f}%)" if total_volume > 0 else "0 (0.00%)")
    print("=" * 75)

def main():
    parser = argparse.ArgumentParser(
        description="Decode, summarize, and audit DMARC XML aggregate feedback reports.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument("report_file", help="Path to the DMARC XML file or ZIP report archive.")
    args = parser.parse_args()
    
    content, err = load_file_content(args.report_file)
    if err:
        print(f"Error loading report: {err}", file=sys.stderr)
        return 1
        
    data, err = parse_dmarc_xml(content)
    if err:
        print(f"Error parsing XML content: {err}", file=sys.stderr)
        return 1
        
    generate_report(data)
    return 0

if __name__ == "__main__":
    sys.exit(main())
