#!/usr/bin/env python3
"""
Website Link Network Mapper - Crawls pages of a website recursively (domain-restricted)
and maps out internal links. It generates a Mermaid.js diagram or an interactive HTML graph.
Uses only Python standard libraries (urllib, html.parser).
"""

import argparse
from html.parser import HTMLParser
import sys
from urllib.parse import urljoin, urlparse
import urllib.request


class LinkParser(HTMLParser):
    """Simple HTMLParser to extract all hyperlinks from page content."""
    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.links = []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for name, value in attrs:
                if name == 'href' and value:
                    # Clean fragment identifiers
                    cleaned_val = value.split('#')[0].strip()
                    if cleaned_val:
                        # Convert relative path to absolute
                        abs_url = urljoin(self.base_url, cleaned_val)
                        self.links.append(abs_url)


def crawl_site(start_url, max_depth=2, max_pages=50):
    """Recursively crawls pages starting from start_url up to max_depth and max_pages."""
    parsed_start = urlparse(start_url)
    allowed_domain = parsed_start.netloc
    
    # Graphs: page -> list of links found
    internal_graph = {}
    external_links = {}
    broken_links = {}
    
    visited = set()
    queue = [(start_url, 0)]  # (url, depth)
    
    # Standard headers to prevent blocking by generic servers
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36'
    }
    
    print(f"[*] Starting crawl on: {start_url} (Domain: {allowed_domain})")
    
    while queue and len(visited) < max_pages:
        current_url, depth = queue.pop(0)
        
        # Normalize trailing slash
        norm_url = current_url.rstrip('/')
        if norm_url in visited:
            continue
            
        visited.add(norm_url)
        print(f"[*] Crawling ({len(visited)}/{max_pages}): {current_url} (Depth: {depth})")
        
        try:
            req = urllib.request.Request(current_url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as response:
                content_type = response.info().get_content_type()
                if "html" not in content_type:
                    # Skip non-HTML documents (images, PDFs, CSS, etc.)
                    continue
                    
                html_data = response.read().decode('utf-8', errors='ignore')
                
            parser = LinkParser(current_url)
            parser.feed(html_data)
            extracted_links = parser.links
            
            internal_graph[norm_url] = []
            
            for link in extracted_links:
                parsed_link = urlparse(link)
                link_norm = link.rstrip('/')
                
                # Check if same domain
                if parsed_link.netloc == allowed_domain:
                    if link_norm not in internal_graph[norm_url]:
                        internal_graph[norm_url].append(link_norm)
                    
                    if depth < max_depth and link_norm not in visited:
                        # Append to queue
                        queue.append((link, depth + 1))
                else:
                    # External Link
                    if norm_url not in external_links:
                        external_links[norm_url] = []
                    if link_norm not in external_links[norm_url]:
                        external_links[norm_url].append(link_norm)
                        
        except Exception as e:
            print(f"[-] Failed to crawl {current_url}: {e}")
            broken_links[norm_url] = str(e)
            
    return internal_graph, external_links, broken_links


def generate_mermaid(graph):
    """Converts the internal crawl graph into a Mermaid.js diagram definition."""
    lines = ["flowchart TD"]
    # We assign short IDs to avoid long URLs breaking Mermaid nodes
    node_ids = {}
    id_counter = 1
    
    for page in graph.keys():
        if page not in node_ids:
            node_ids[page] = f"N{id_counter}"
            id_counter += 1
            
    for page, targets in graph.items():
        p_id = node_ids[page]
        # Clean path for node title
        p_parsed = urlparse(page)
        p_label = p_parsed.path if p_parsed.path else "/"
        lines.append(f'  {p_id}["{p_label}"]')
        
        for target in targets:
            if target not in node_ids:
                node_ids[target] = f"N{id_counter}"
                id_counter += 1
            t_id = node_ids[target]
            t_parsed = urlparse(target)
            t_label = t_parsed.path if t_parsed.path else "/"
            # Create connection
            lines.append(f"  {p_id} --> {t_id}")
            
    return "\n".join(lines)


def generate_html_view(start_url, graph, external, broken):
    """Produces a responsive, interactive page showing the link relationships with a Mermaid graph."""
    mermaid_def = generate_mermaid(graph)
    
    # Build details summaries
    graph_rows = ""
    for page, targets in graph.items():
        graph_rows += f"<tr><td><code>{page}</code></td><td>{len(targets)}</td><td><ul>"
        for t in targets:
            graph_rows += f"<li><a href=\"{t}\" target=\"_blank\">{urlparse(t).path or '/'}</a></li>"
        graph_rows += "</ul></td></tr>"
        
    ext_rows = ""
    for page, links in external.items():
        ext_rows += f"<tr><td><code>{page}</code></td><td>{len(links)}</td><td><ul>"
        for l in links:
            ext_rows += f"<li><a href=\"{l}\" target=\"_blank\">{l}</a></li>"
        ext_rows += "</ul></td></tr>"

    broken_rows = ""
    for page, err in broken.items():
        broken_rows += f"<tr><td><code>{page}</code></td><td><span class=\"err\">{err}</span></td></tr>"

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Website Link Network Map</title>
  <style>
    body {{
      font-family: 'Segoe UI', Arial, sans-serif;
      background-color: #1e1e2e;
      color: #cdd6f4;
      margin: 0;
      padding: 20px;
    }}
    h1, h2 {{
      color: #89b4fa;
    }}
    .container {{
      max-width: 1200px;
      margin: 0 auto;
    }}
    .card {{
      background-color: #313244;
      border: 1px solid #45475a;
      border-radius: 8px;
      padding: 20px;
      margin-bottom: 25px;
      box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3);
    }}
    .mermaid-box {{
      display: flex;
      justify-content: center;
      background-color: #11111b;
      padding: 20px;
      border-radius: 6px;
      overflow-x: auto;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin-top: 15px;
    }}
    th, td {{
      padding: 10px;
      border: 1px solid #45475a;
      text-align: left;
    }}
    th {{
      background-color: #45475a;
      color: #f5c2e7;
    }}
    tr:nth-child(even) {{
      background-color: #181825;
    }}
    ul {{
      margin: 0;
      padding-left: 20px;
    }}
    a {{
      color: #f9e2af;
      text-decoration: none;
    }}
    a:hover {{
      text-decoration: underline;
    }}
    .err {{
      color: #f38ba8;
      font-weight: bold;
    }}
  </style>
  <script type="module">
    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
    mermaid.initialize({{ startOnLoad: true, theme: 'dark' }});
  </script>
</head>
<body>
  <div class="container">
    <h1>Website Link Network Map</h1>
    <p>Crawled starting from: <a href="{start_url}" target="_blank">{start_url}</a></p>
    
    <div class="card">
      <h2>Visual Flowchart (Mermaid)</h2>
      <div class="mermaid-box">
        <pre class="mermaid">
{mermaid_def}
        </pre>
      </div>
    </div>
    
    <div class="card">
      <h2>Internal Links ({len(graph)})</h2>
      <table>
        <thead>
          <tr>
            <th>Page URL</th>
            <th>Outbound Links</th>
            <th>Target Internal Pages</th>
          </tr>
        </thead>
        <tbody>
          {graph_rows}
        </tbody>
      </table>
    </div>

    {f'''
    <div class="card">
      <h2>External Connections</h2>
      <table>
        <thead>
          <tr>
            <th>Origin Page</th>
            <th>Count</th>
            <th>External URLs</th>
          </tr>
        </thead>
        <tbody>
          {ext_rows}
        </tbody>
      </table>
    </div>
    ''' if external else ''}

    {f'''
    <div class="card">
      <h2>Crawling Failures / Broken Paths</h2>
      <table>
        <thead>
          <tr>
            <th>Failed URL</th>
            <th>Details / Error</th>
          </tr>
        </thead>
        <tbody>
          {broken_rows}
        </tbody>
      </table>
    </div>
    ''' if broken else ''}
    
  </div>
</body>
</html>
"""
    return html_content


def main():
    parser = argparse.ArgumentParser(
        description="Website Link Network Mapper - Recursively crawl website internal links and visualize paths."
    )
    parser.add_argument("url", help="Initial root URL of the website to crawl")
    parser.add_argument("-d", "--depth", type=int, default=2, help="Max recursion depth (default: 2)")
    parser.add_argument("-p", "--pages", type=int, default=50, help="Max total pages to crawl (default: 50)")
    parser.add_argument("-m", "--mermaid", action="store_true", help="Print raw Mermaid.js chart code directly")
    parser.add_argument("-o", "--output", help="Save interactive HTML visual report path")
    
    args = parser.parse_args()
    
    graph, external, broken = crawl_site(args.url, args.depth, args.pages)
    
    if args.mermaid:
        print("\n=== MERMAID CODE ===")
        print(generate_mermaid(graph))
        
    if args.output:
        html_report = generate_html_view(args.url, graph, external, broken)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(html_report)
        print(f"\n[+] Interactive map successfully exported to: {args.output}")
    else:
        # Default text report summary
        print("\n" + "=" * 60)
        print("                 CRAWL SUMMARY REPORT")
        print("=" * 60)
        print(f"Total crawled pages: {len(graph)}")
        print(f"Total pages with errors: {len(broken)}")
        
        print("\nSite hierarchy:")
        for page, targets in graph.items():
            print(f"- {page}")
            for t in targets:
                print(f"  --> {urlparse(t).path or '/'}")
                
        if not args.output:
            print("\n[!] Tip: run with --output <file.html> to generate a beautiful interactive diagram.")


if __name__ == "__main__":
    sys.exit(main())
