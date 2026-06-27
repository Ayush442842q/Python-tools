#!/usr/bin/env python3
r"""
Local SEO & Web Accessibility Auditor - Audits local HTML files or websites for SEO & Accessibility.
Generates an interactive console summary and a beautiful, styled, dark-themed HTML report.

Usage:
    python tools/seo_auditor.py [FILE_OR_DIR_OR_URL] [--output REPORT_PATH]

Example:
    python tools/seo_auditor.py index.html
    python tools/seo_auditor.py h:\my_project\ --output seo-report.html
    python tools/seo_auditor.py https://example.com
"""

import argparse
import os
import sys
import urllib.request
import urllib.parse
from html.parser import HTMLParser

class HTMLAuditor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title_text = ""
        self.meta_description = ""
        self.viewport_exists = False
        self.html_lang = None
        self.in_title = False
        self.headings = []          # List of (tag, text)
        self.images = []            # List of dicts (src, alt, line)
        self.links = []             # List of dicts (href, text, line)
        self.ids = []               # List of IDs seen
        self.duplicate_ids = []
        self.current_tag = None
        self.current_link_text = ""
        self.in_link = False

    def handle_starttag(self, tag, attrs):
        self.current_tag = tag
        attrs_dict = dict(attrs)
        
        if tag == 'html':
            self.html_lang = attrs_dict.get('lang')
            
        elif tag == 'title':
            self.in_title = True
            
        elif tag == 'meta':
            name = attrs_dict.get('name', '').lower()
            if name == 'description':
                self.meta_description = attrs_dict.get('content', '')
            elif name == 'viewport':
                self.viewport_exists = True
                
        elif tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6'):
            self.headings.append((tag, ""))
            
        elif tag == 'img':
            self.images.append({
                'src': attrs_dict.get('src', ''),
                'alt': attrs_dict.get('alt'),
                'line': self.getpos()[0]
            })
            
        elif tag == 'a':
            self.in_link = True
            self.current_link_text = ""
            self.links.append({
                'href': attrs_dict.get('href', ''),
                'text': '',
                'line': self.getpos()[0]
            })
            
        if 'id' in attrs_dict:
            el_id = attrs_dict['id']
            if el_id in self.ids:
                if el_id not in self.duplicate_ids:
                    self.duplicate_ids.append(el_id)
            else:
                self.ids.append(el_id)

    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False
        elif tag == 'a':
            self.in_link = False
            if self.links:
                self.links[-1]['text'] = self.current_link_text.strip()
                
    def handle_data(self, data):
        if self.in_title:
            self.title_text += data
        elif self.in_link and self.links:
            self.current_link_text += data
        elif self.headings and self.headings[-1][1] == "":
            tag, cur_text = self.headings[-1]
            self.headings[-1] = (tag, cur_text + data)


def perform_audit(html_content, source_name):
    parser = HTMLAuditor()
    parser.feed(html_content)
    
    results = {}
    
    # 1. Title Tag Audit
    title = parser.title_text.strip()
    title_len = len(title)
    if not title:
        results['title'] = {'score': 0, 'status': 'Error', 'msg': 'Missing or empty <title> tag.'}
    elif title_len < 10:
        results['title'] = {'score': 50, 'status': 'Warning', 'msg': f'Title too short ({title_len} chars). Target: 10-60 chars.', 'val': title}
    elif title_len > 60:
        results['title'] = {'score': 50, 'status': 'Warning', 'msg': f'Title too long ({title_len} chars). Target: 10-60 chars.', 'val': title}
    else:
        results['title'] = {'score': 100, 'status': 'Passed', 'msg': f'Title has optimal length ({title_len} chars).', 'val': title}

    # 2. Meta Description Audit
    desc = parser.meta_description.strip()
    desc_len = len(desc)
    if not desc:
        results['description'] = {'score': 0, 'status': 'Error', 'msg': 'Missing or empty <meta name="description"> tag.'}
    elif desc_len < 50:
        results['description'] = {'score': 50, 'status': 'Warning', 'msg': f'Meta description too short ({desc_len} chars). Target: 50-160 chars.', 'val': desc}
    elif desc_len > 160:
        results['description'] = {'score': 50, 'status': 'Warning', 'msg': f'Meta description too long ({desc_len} chars). Target: 50-160 chars.', 'val': desc}
    else:
        results['description'] = {'score': 100, 'status': 'Passed', 'msg': f'Meta description has optimal length ({desc_len} chars).', 'val': desc}

    # 3. Viewport Audit
    if parser.viewport_exists:
        results['viewport'] = {'score': 100, 'status': 'Passed', 'msg': 'Responsive viewport meta tag is present.'}
    else:
        results['viewport'] = {'score': 0, 'status': 'Error', 'msg': 'Missing <meta name="viewport"> tag. Vital for mobile scaling.'}

    # 4. Language Attribute Audit
    if parser.html_lang:
        results['lang'] = {'score': 100, 'status': 'Passed', 'msg': f'HTML lang attribute is set to "{parser.html_lang}".'}
    else:
        results['lang'] = {'score': 0, 'status': 'Error', 'msg': 'Missing "lang" attribute on the <html> tag. Crucial for accessibility.'}

    # 5. H1 Audit
    h1s = [text for tag, text in parser.headings if tag == 'h1']
    h1_count = len(h1s)
    if h1_count == 0:
        results['h1'] = {'score': 0, 'status': 'Error', 'msg': 'No <h1> tag found. Each page must have exactly one main header.'}
    elif h1_count > 1:
        results['h1'] = {'score': 50, 'status': 'Warning', 'msg': f'Multiple ({h1_count}) <h1> tags found. Avoid multiple primary headings.'}
    else:
        results['h1'] = {'score': 100, 'status': 'Passed', 'msg': 'Exactly one <h1> tag found.', 'val': h1s[0]}

    # 6. Heading Hierarchy Audit
    heading_hierarchy = []
    level_warnings = []
    prev_level = 0
    for tag, text in parser.headings:
        level = int(tag[1])
        heading_hierarchy.append(f"{tag}: {text[:30]}...")
        if prev_level > 0 and level > prev_level + 1:
            level_warnings.append(f"Jumped from <h{prev_level}> to <h{level}> without intermediate level.")
        prev_level = level
    
    if level_warnings:
        results['headings_hierarchy'] = {
            'score': 60,
            'status': 'Warning',
            'msg': 'Heading levels are out of order.',
            'details': level_warnings,
            'val': heading_hierarchy
        }
    else:
        results['headings_hierarchy'] = {
            'score': 100,
            'status': 'Passed',
            'msg': 'Heading hierarchy follows sequential ordering.',
            'val': heading_hierarchy
        }

    # 7. Images Alt Attributes Audit
    total_imgs = len(parser.images)
    missing_alt = [img for img in parser.images if img['alt'] is None or img['alt'].strip() == '']
    missing_count = len(missing_alt)
    if total_imgs == 0:
        results['img_alts'] = {'score': 100, 'status': 'Passed', 'msg': 'No images found on this page.'}
    else:
        pct = int(((total_imgs - missing_count) / total_imgs) * 100)
        details = [f"Line {img['line']}: Image '{img['src']}' is missing an alt attribute." for img in missing_alt]
        if missing_count > 0:
            results['img_alts'] = {
                'score': pct,
                'status': 'Warning' if pct > 50 else 'Error',
                'msg': f'{missing_count} of {total_imgs} images are missing alternative text.',
                'details': details
            }
        else:
            results['img_alts'] = {'score': 100, 'status': 'Passed', 'msg': 'All images have alternative text.'}

    # 8. Duplicate IDs Audit
    dup_count = len(parser.duplicate_ids)
    if dup_count > 0:
        results['unique_ids'] = {
            'score': max(0, 100 - (dup_count * 10)),
            'status': 'Error',
            'msg': f'Duplicate element IDs found: {", ".join(parser.duplicate_ids)}'
        }
    else:
        results['unique_ids'] = {'score': 100, 'status': 'Passed', 'msg': 'All element ID attributes are unique.'}

    # 9. Descriptive Link Text Audit
    bad_phrases = ('click here', 'read more', 'more', 'link', 'go', 'here', 'button', 'learn more')
    non_descriptive_links = []
    for link in parser.links:
        t = link['text'].lower()
        if any(phrase in t for phrase in bad_phrases) or len(t) <= 2:
            non_descriptive_links.append(f"Line {link['line']}: Link to '{link['href']}' has non-descriptive label '{link['text']}'")
    
    bad_count = len(non_descriptive_links)
    if bad_count > 0:
        results['link_text'] = {
            'score': max(50, 100 - (bad_count * 10)),
            'status': 'Warning',
            'msg': f'{bad_count} links have non-descriptive text (e.g. "click here").',
            'details': non_descriptive_links
        }
    else:
        results['link_text'] = {'score': 100, 'status': 'Passed', 'msg': 'All link anchor texts appear descriptive.'}

    # Calculate overall audit score
    overall = int(sum(item['score'] for item in results.values()) / len(results))
    results['overall_score'] = overall
    return results


def print_console_report(results, source_name):
    # ANSI color helpers
    C_GREEN = "\033[92m"
    C_YELLOW = "\033[93m"
    C_RED = "\033[91m"
    C_RESET = "\033[0m"
    C_BOLD = "\033[1m"
    
    score = results['overall_score']
    color = C_GREEN if score >= 85 else (C_YELLOW if score >= 50 else C_RED)
    
    print("=" * 60)
    print(f"{C_BOLD}SEO & ACCESSIBILITY AUDIT FOR:{C_RESET} {source_name}")
    print(f"{C_BOLD}OVERALL SCORE:{C_RESET} {color}{score}/100{C_RESET}")
    print("=" * 60)
    
    for key, audit in results.items():
        if key == 'overall_score':
            continue
            
        status = audit['status']
        a_color = C_GREEN if status == 'Passed' else (C_YELLOW if status == 'Warning' else C_RED)
        symbol = "✓" if status == 'Passed' else ("⚠" if status == 'Warning' else "✗")
        
        print(f"[{a_color}{symbol}{C_RESET}] {C_BOLD}{key.upper()}{C_RESET} (Score: {audit['score']}/100)")
        print(f"    {audit['msg']}")
        
        if 'details' in audit and audit['details']:
            print("    Details:")
            for detail in audit['details'][:5]:
                print(f"      - {detail}")
            if len(audit['details']) > 5:
                print(f"      - ... and {len(audit['details']) - 5} more items.")
        print("-" * 60)


def generate_html_report(results, source_name, report_path):
    score = results['overall_score']
    theme_color = "#10b981" if score >= 85 else ("#f59e0b" if score >= 50 else "#ef4444")
    
    cards_html = ""
    for key, audit in results.items():
        if key == 'overall_score':
            continue
        status = audit['status']
        card_class = status.lower()
        badge_color = "bg-green" if status == 'Passed' else ("bg-warning" if status == 'Warning' else "bg-danger")
        
        details_html = ""
        if 'details' in audit and audit['details']:
            details_items = "".join(f"<li>{item}</li>" for item in audit['details'])
            details_html = f"<ul class='detail-list'>{details_items}</ul>"
            
        val_html = ""
        if 'val' in audit and audit['val']:
            if isinstance(audit['val'], list):
                val_items = "".join(f"<code>{item}</code><br/>" for item in audit['val'])
                val_html = f"<div class='value-display'>{val_items}</div>"
            else:
                val_html = f"<div class='value-display'><code>{audit['val']}</code></div>"

        cards_html += f"""
        <div class="card card-{card_class}">
            <div class="card-header">
                <span class="card-title">{key.replace('_', ' ').upper()}</span>
                <span class="badge {badge_color}">{status} ({audit['score']}/100)</span>
            </div>
            <p class="card-desc">{audit['msg']}</p>
            {val_html}
            {details_html}
        </div>
        """

    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SEO & Accessibility Audit - {source_name}</title>
    <style>
        :root {{
            --bg-color: #0f172a;
            --card-bg: rgba(30, 41, 59, 0.7);
            --border-color: rgba(255, 255, 255, 0.08);
            --text-color: #f1f5f9;
            --text-muted: #94a3b8;
        }}
        body {{
            font-family: 'Outfit', -apple-system, sans-serif;
            background-color: var(--bg-color);
            background-image: radial-gradient(circle at 10% 20%, rgba(120, 119, 198, 0.1) 0%, transparent 50%),
                              radial-gradient(circle at 90% 80%, rgba(16, 185, 129, 0.05) 0%, transparent 50%);
            color: var(--text-color);
            margin: 0;
            padding: 40px 20px;
            display: flex;
            justify-content: center;
        }}
        .container {{
            max-width: 900px;
            width: 100%;
        }}
        header {{
            text-align: center;
            margin-bottom: 40px;
            padding: 20px;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            backdrop-filter: blur(12px);
            border-radius: 20px;
        }}
        h1 {{
            margin: 0 0 10px 0;
            font-size: 2.2rem;
            letter-spacing: -0.025em;
        }}
        .source-name {{
            color: var(--text-muted);
            font-size: 1rem;
            word-break: break-all;
        }}
        .score-circle {{
            width: 120px;
            height: 120px;
            border-radius: 50%;
            border: 8px solid {theme_color};
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            margin: 20px auto;
            background: rgba(15, 23, 42, 0.6);
            box-shadow: 0 0 25px rgba({",".join(map(str, bytes.fromhex(theme_color[1:])))}, 0.2);
        }}
        .score-num {{
            font-size: 2.5rem;
            font-weight: 700;
        }}
        .score-label {{
            font-size: 0.8rem;
            color: var(--text-muted);
            text-transform: uppercase;
        }}
        .grid {{
            display: grid;
            grid-template-columns: 1fr;
            gap: 20px;
        }}
        .card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            backdrop-filter: blur(10px);
            border-radius: 16px;
            padding: 24px;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 10px 20px rgba(0,0,0,0.2);
        }}
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid rgba(255,255,255,0.05);
            padding-bottom: 12px;
            margin-bottom: 12px;
        }}
        .card-title {{
            font-weight: 600;
            font-size: 1.1rem;
            letter-spacing: 0.05em;
        }}
        .badge {{
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 600;
            color: #fff;
        }}
        .bg-green {{ background-color: #10b981; }}
        .bg-warning {{ background-color: #f59e0b; }}
        .bg-danger {{ background-color: #ef4444; }}
        
        .card-desc {{
            font-size: 0.95rem;
            line-height: 1.5;
            color: #cbd5e1;
        }}
        .value-display {{
            background: rgba(0,0,0,0.3);
            border: 1px solid rgba(255,255,255,0.05);
            padding: 10px;
            border-radius: 8px;
            margin-top: 10px;
            font-size: 0.85rem;
        }}
        code {{
            color: #60a5fa;
        }}
        .detail-list {{
            margin: 12px 0 0 0;
            padding-left: 20px;
            font-size: 0.85rem;
            color: #94a3b8;
            line-height: 1.6;
        }}
        .detail-list li {{
            margin-bottom: 6px;
        }}
        footer {{
            text-align: center;
            margin-top: 50px;
            color: var(--text-muted);
            font-size: 0.85rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>SEO & Accessibility Audit</h1>
            <div class="source-name">{source_name}</div>
            <div class="score-circle">
                <span class="score-num">{score}</span>
                <span class="score-label">Score</span>
            </div>
        </header>
        <div class="grid">
            {cards_html}
        </div>
        <footer>
            Generated by Local SEO & Web Accessibility Auditor &bull; Open-source tools collection
        </footer>
    </div>
</body>
</html>
"""
    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(html_template)
        print(f"\n[+] Interactive HTML report saved to: {report_path}")
    except Exception as e:
        print(f"[!] Error writing HTML report: {e}", file=sys.stderr)


def scan_directory(dir_path):
    html_files = []
    for root, _, files in os.walk(dir_path):
        for file in files:
            if file.lower().endswith(('.html', '.htm')):
                html_files.append(os.path.join(root, file))
    return html_files


def main():
    parser = argparse.ArgumentParser(description="Audit SEO and Web Accessibility parameters for HTML files or websites")
    parser.add_argument("target", nargs="?", default=".", help="HTML file, Directory, or URL to audit (defaults to current dir)")
    parser.add_argument("-o", "--output", help="Output file path for the interactive HTML report (default: seo_audit_report.html)")
    args = parser.parse_args()

    target = args.target
    output_report = args.output or "seo_audit_report.html"
    
    # 1. Fetch / Read Content
    if target.startswith(("http://", "https://")):
        print(f"[*] Crawling and parsing remote URL: {target}...")
        try:
            req = urllib.request.Request(
                target, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) SEOAuditor/1.0'}
            )
            with urllib.request.urlopen(req, timeout=15) as response:
                content = response.read().decode('utf-8', errors='ignore')
            results = perform_audit(content, target)
            print_console_report(results, target)
            generate_html_report(results, target, output_report)
        except Exception as e:
            print(f"[!] Error crawling URL: {e}", file=sys.stderr)
            return 1
            
    elif os.path.isdir(target):
        print(f"[*] Scanning directory '{target}' for HTML files...")
        files = scan_directory(target)
        if not files:
            print(f"[!] No HTML files found in directory: {target}")
            return 1
        print(f"[+] Found {len(files)} HTML files. Auditing first file/overview...")
        # For simplicity, audit the main file (index.html or the first sorted file)
        files.sort(key=lambda x: ("index.html" not in x.lower(), x))
        primary_file = files[0]
        print(f"[*] Auditing primary file: {primary_file}")
        try:
            with open(primary_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            results = perform_audit(content, primary_file)
            print_console_report(results, primary_file)
            generate_html_report(results, primary_file, output_report)
        except Exception as e:
            print(f"[!] Error reading file '{primary_file}': {e}", file=sys.stderr)
            return 1
            
    elif os.path.isfile(target):
        print(f"[*] Auditing local file: {target}")
        try:
            with open(target, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
            results = perform_audit(content, target)
            print_console_report(results, target)
            generate_html_report(results, target, output_report)
        except Exception as e:
            print(f"[!] Error reading file '{target}': {e}", file=sys.stderr)
            return 1
    else:
        print(f"[!] Target '{target}' is not a valid file, directory, or URL.", file=sys.stderr)
        return 1
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
