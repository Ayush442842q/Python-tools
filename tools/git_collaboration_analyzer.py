#!/usr/bin/env python3
"""
git_collaboration_analyzer.py - Git Co-authorship & Collaboration Analyzer

Analyzes Git commit logs and "Co-authored-by" metadata to trace developer
collaboration, file overlaps, commit timing, and compute an estimated "Bus Factor".
Generates a beautiful, standalone interactive HTML dashboard.

Requirements:
    - Git installed and run inside a Git repository.
    - Python 3.6+ (No external dependencies)
"""

import os
import sys
import argparse
import subprocess
import re
import json
from collections import defaultdict, Counter
from datetime import datetime

def run_git_command(args, cwd=None):
    """Runs a git command and returns the output string, or None on error."""
    try:
        result = subprocess.run(
            ["git"] + args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="ignore",
            cwd=cwd,
            check=True
        )
        return result.stdout.strip()
    except (subprocess.SubprocessError, FileNotFoundError):
        return None

def is_git_repo(path):
    """Checks if the path is inside a Git repository."""
    return run_git_command(["rev-parse", "--is-inside-work-tree"], cwd=path) == "true"

def parse_git_log(cwd=None):
    """
    Parses git log history to extract author, email, date, co-authors, and modified files.
    """
    # Format: Hash | Author Name | Author Email | Commit Date (ISO)
    # Followed by a list of modified files, separated by empty line per commit
    log_format = "%H|%an|%ae|%ad|%B"
    log_data = run_git_command(["log", f"--pretty=format:{log_format}", "--name-only", "--date=iso"], cwd=cwd)
    
    if not log_data:
        return []

    commits = []
    # Split by double newline or reconstruct commit chunks
    # Note: Commit message body can contain newlines, so we parse line by line
    lines = log_data.split('\n')
    current_commit = None
    parsing_files = False
    
    # Regex to find Co-authored-by tags
    co_author_rx = re.compile(r"Co-authored-by:\s*([^<]+)<([^>]+)>", re.IGNORECASE)

    for line in lines:
        if not line:
            if current_commit:
                parsing_files = True
            continue
            
        if not parsing_files and "|" in line and len(line.split("|", 4)) == 5:
            # New commit starting
            if current_commit:
                commits.append(current_commit)
            
            parts = line.split("|", 4)
            commit_hash = parts[0]
            author_name = parts[1].strip()
            author_email = parts[2].strip().lower()
            date_str = parts[3].strip()
            body = parts[4]
            
            # Parse Date
            try:
                # ISO date: 2026-06-29 13:31:08 +0530
                dt = datetime.strptime(date_str[:-6], "%Y-%m-%d %H:%M:%S")
                tz_offset = date_str[-5:]
            except ValueError:
                dt = datetime.now()
                tz_offset = "+0000"
                
            current_commit = {
                "hash": commit_hash,
                "author": f"{author_name} <{author_email}>",
                "author_name": author_name,
                "author_email": author_email,
                "datetime": dt,
                "hour": dt.hour,
                "weekday": dt.weekday(), # Monday = 0
                "tz": tz_offset,
                "co_authors": [],
                "files": []
            }
            
            # Parse co-authors in body
            for match in co_author_rx.finditer(body):
                ca_name = match.group(1).strip()
                ca_email = match.group(2).strip().lower()
                current_commit["co_authors"].append(f"{ca_name} <{ca_email}>")
                
            parsing_files = False
        else:
            if current_commit:
                # This line is a file path if parsing_files is True
                if parsing_files:
                    current_commit["files"].append(line.strip())
                else:
                    # Still in body, scan for co-authors if we missed any
                    for match in co_author_rx.finditer(line):
                        ca_name = match.group(1).strip()
                        ca_email = match.group(2).strip().lower()
                        current_commit["co_authors"].append(f"{ca_name} <{ca_email}>")

    if current_commit:
        commits.append(current_commit)
        
    return commits

def analyze_collaboration(commits):
    """Computes stats from parsed commits."""
    if not commits:
        return {}

    total_commits = len(commits)
    authors_commit_count = Counter()
    co_authors_count = Counter()
    
    # Track file modifications
    file_authors = defaultdict(set)
    file_commits = Counter()
    
    # Co-authorship relationships
    co_author_network = defaultdict(lambda: defaultdict(int))
    
    # Hourly & weekday distributions
    hourly_distribution = [0] * 24
    weekday_distribution = [0] * 7 # Mon-Sun
    
    # Collaboration pairs
    all_developers = set()

    for c in commits:
        primary = c["author"]
        primary_name = c["author_name"]
        authors_commit_count[primary] += 1
        all_developers.add(primary)
        
        hourly_distribution[c["hour"]] += 1
        weekday_distribution[c["weekday"]] += 1
        
        for f in c["files"]:
            file_authors[f].add(primary)
            file_commits[f] += 1
            
        for ca in c["co_authors"]:
            co_authors_count[ca] += 1
            all_developers.add(ca)
            # Add bidirectional relation
            co_author_network[primary][ca] += 1
            co_author_network[ca][primary] += 1
            
            # File co-ownership
            for f in c["files"]:
                file_authors[f].add(ca)

    # Calculate Bus Factor (simple heuristic)
    # The minimum number of developers who make up > 50% of the commits
    sorted_authors = authors_commit_count.most_common()
    cumulative_commits = 0
    bus_factor = 0
    majority_developers = []
    
    for auth, count in sorted_authors:
        cumulative_commits += count
        bus_factor += 1
        majority_developers.append((auth, count))
        if cumulative_commits >= total_commits / 2:
            break
            
    # Shared files vs Solely owned files
    solely_owned = 0
    collaboratively_owned = 0
    file_ownership_counts = Counter()
    
    for f, devs in file_authors.items():
        dev_count = len(devs)
        file_ownership_counts[dev_count] += 1
        if dev_count == 1:
            solely_owned += 1
        elif dev_count > 1:
            collaboratively_owned += 1

    # Dev file overlap matrix
    # Compute how many files are shared between pairs of developers
    devs_list = sorted(list(all_developers))
    overlap_matrix = defaultdict(lambda: defaultdict(int))
    
    for f, devs in file_authors.items():
        devs_sorted = sorted(list(devs))
        for i in range(len(devs_sorted)):
            for j in range(i + 1, len(devs_sorted)):
                d1 = devs_sorted[i]
                d2 = devs_sorted[j]
                overlap_matrix[d1][d2] += 1
                overlap_matrix[d2][d1] += 1

    # Top files by contributor count
    shared_files = []
    for f, devs in file_authors.items():
        if len(devs) > 1:
            shared_files.append({
                "file": f,
                "contributors": len(devs),
                "commits": file_commits[f]
            })
    shared_files.sort(key=lambda x: x["contributors"], reverse=True)

    return {
        "total_commits": total_commits,
        "unique_developers": len(all_developers),
        "author_commits": dict(authors_commit_count),
        "co_author_commits": dict(co_authors_count),
        "bus_factor": bus_factor,
        "majority_developers": majority_developers,
        "solely_owned_files": solely_owned,
        "collaboratively_owned_files": collaboratively_owned,
        "file_ownership_distribution": dict(file_ownership_counts),
        "hourly_distribution": hourly_distribution,
        "weekday_distribution": weekday_distribution,
        "co_author_network": {k: dict(v) for k, v in co_author_network.items()},
        "file_overlap_matrix": {k: dict(v) for k, v in overlap_matrix.items()},
        "top_shared_files": shared_files[:20]
    }

def generate_html_report(stats, repo_name, output_path):
    """Generates a beautiful HTML dashboard using the parsed statistics."""
    
    # Format developer names for JSON insertion
    developers = sorted(list(stats["author_commits"].keys() | stats["co_author_commits"].keys()))
    
    # Build co-author network nodes and links
    nodes = []
    links = []
    node_id_map = {}
    
    for i, dev in enumerate(developers):
        # Extract clean name
        clean_name = dev.split("<")[0].strip()
        commit_val = stats["author_commits"].get(dev, 0)
        co_commit_val = stats["co_author_commits"].get(dev, 0)
        nodes.append({
            "id": i,
            "name": clean_name,
            "commits": commit_val,
            "co_commits": co_commit_val,
            "total_influence": commit_val + co_commit_val
        })
        node_id_map[dev] = i
        
    for d1, targets in stats["co_author_network"].items():
        for d2, weight in targets.items():
            if node_id_map[d1] < node_id_map[d2]: # Avoid duplicates
                links.append({
                    "source": node_id_map[d1],
                    "target": node_id_map[d2],
                    "weight": weight
                })

    html_template = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Git Collaboration Dashboard - {repo_name}</title>
    <link href="https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=Space+Grotesk:wght@400;700&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg-color: #0b0f19;
            --card-bg: rgba(22, 28, 45, 0.6);
            --border-color: rgba(255, 255, 255, 0.08);
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --primary: #4f46e5;
            --primary-gradient: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
            --accent-green: #10b981;
            --accent-pink: #ec4899;
            --accent-orange: #f59e0b;
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
            padding: 2rem;
            line-height: 1.5;
            overflow-x: hidden;
        }}
        
        .container {{
            max-width: 1400px;
            margin: 0 auto;
        }}
        
        header {{
            margin-bottom: 3rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 1.5rem;
        }}
        
        h1 {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 2.5rem;
            font-weight: 700;
            background: linear-gradient(to right, #a5b4fc, #6366f1);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}
        
        .repo-badge {{
            background: rgba(99, 102, 241, 0.15);
            border: 1px solid rgba(99, 102, 241, 0.3);
            color: #a5b4fc;
            padding: 0.4rem 1rem;
            border-radius: 9999px;
            font-size: 0.9rem;
            font-weight: 600;
        }}
        
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
            gap: 1.5rem;
            margin-bottom: 3rem;
        }}
        
        .stat-card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 1rem;
            padding: 1.5rem;
            backdrop-filter: blur(12px);
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.2);
            transition: transform 0.2s, border-color 0.2s;
        }}
        
        .stat-card:hover {{
            transform: translateY(-4px);
            border-color: rgba(99, 102, 241, 0.4);
        }}
        
        .stat-label {{
            color: var(--text-secondary);
            font-size: 0.875rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.5rem;
        }}
        
        .stat-value {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 2.25rem;
            font-weight: 700;
            margin-bottom: 0.25rem;
        }}
        
        .stat-desc {{
            font-size: 0.8rem;
            color: var(--text-secondary);
        }}
        
        .main-layout {{
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 2rem;
        }}
        
        @media (max-width: 1024px) {{
            .main-layout {{
                grid-template-columns: 1fr;
            }}
        }}
        
        .card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 1.25rem;
            padding: 2rem;
            backdrop-filter: blur(12px);
            margin-bottom: 2rem;
            box-shadow: 0 4px 30px rgba(0, 0, 0, 0.2);
        }}
        
        .card-title {{
            font-family: 'Space Grotesk', sans-serif;
            font-size: 1.25rem;
            font-weight: 700;
            margin-bottom: 1.5rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}
        
        /* Interactive Network Chart placeholder using CSS/JS */
        .network-container {{
            width: 100%;
            height: 450px;
            background: rgba(10, 12, 20, 0.8);
            border-radius: 0.75rem;
            border: 1px solid var(--border-color);
            position: relative;
            overflow: hidden;
        }}
        
        .network-node {{
            position: absolute;
            border-radius: 50%;
            transform: translate(-50%, -50%);
            display: flex;
            justify-content: center;
            align-items: center;
            font-size: 0.7rem;
            font-weight: 600;
            color: #fff;
            text-align: center;
            cursor: pointer;
            box-shadow: 0 0 15px rgba(99, 102, 241, 0.4);
            transition: width 0.3s, height 0.3s;
        }}
        
        .network-node .tooltip {{
            visibility: hidden;
            background-color: #1e293b;
            color: #fff;
            text-align: center;
            padding: 5px 10px;
            border-radius: 6px;
            position: absolute;
            z-index: 10;
            bottom: 125%;
            left: 50%;
            transform: translateX(-50%);
            width: max-content;
            max-width: 200px;
            border: 1px solid var(--border-color);
            font-family: 'Outfit', sans-serif;
            box-shadow: 0 4px 10px rgba(0, 0, 0, 0.3);
        }}
        
        .network-node:hover .tooltip {{
            visibility: visible;
        }}
        
        .bar-chart-container {{
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }}
        
        .bar-row {{
            display: flex;
            align-items: center;
            gap: 1rem;
        }}
        
        .bar-label {{
            width: 150px;
            font-size: 0.9rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            color: var(--text-secondary);
        }}
        
        .bar-track {{
            flex-grow: 1;
            background: rgba(255, 255, 255, 0.05);
            height: 12px;
            border-radius: 6px;
            overflow: hidden;
        }}
        
        .bar-fill {{
            height: 100%;
            background: var(--primary-gradient);
            border-radius: 6px;
            transition: width 1s ease-out;
        }}
        
        .bar-val {{
            width: 50px;
            text-align: right;
            font-weight: 600;
            font-size: 0.9rem;
        }}
        
        /* Table styles */
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
            font-weight: 600;
        }}
        
        td {{
            padding: 0.75rem 1rem;
            border-bottom: 1px solid var(--border-color);
        }}
        
        tr:hover td {{
            background: rgba(255, 255, 255, 0.02);
        }}
        
        .file-path {{
            font-family: monospace;
            color: #c7d2fe;
            word-break: break-all;
        }}
        
        .grid-2col {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 2rem;
        }}
        
        @media (max-width: 768px) {{
            .grid-2col {{
                grid-template-columns: 1fr;
            }}
        }}
        
        .hour-grid {{
            display: grid;
            grid-template-columns: repeat(24, 1fr);
            gap: 2px;
            height: 120px;
            align-items: flex-end;
            margin-top: 1rem;
        }}
        
        .hour-bar {{
            background: rgba(99, 102, 241, 0.3);
            border-radius: 2px 2px 0 0;
            position: relative;
            cursor: pointer;
        }}
        
        .hour-bar:hover {{
            background: var(--primary);
        }}
        
        .hour-bar::after {{
            content: attr(data-tooltip);
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            background: #1e293b;
            color: #fff;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.7rem;
            white-space: nowrap;
            visibility: hidden;
            z-index: 5;
            box-shadow: 0 2px 5px rgba(0,0,0,0.5);
            border: 1px solid var(--border-color);
        }}
        
        .hour-bar:hover::after {{
            visibility: visible;
        }}
        
        .hour-labels {{
            display: grid;
            grid-template-columns: repeat(24, 1fr);
            text-align: center;
            font-size: 0.7rem;
            color: var(--text-secondary);
            margin-top: 0.5rem;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>Git Collaboration Dashboard</h1>
                <p style="color: var(--text-secondary); margin-top: 0.25rem;">Visualizing team metrics, overlap networks, and co-authorship</p>
            </div>
            <span class="repo-badge">{repo_name}</span>
        </header>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-label">Total Commits</div>
                <div class="stat-value">{stats["total_commits"]}</div>
                <div class="stat-desc">Entire repository history</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Unique Developers</div>
                <div class="stat-value">{stats["unique_developers"]}</div>
                <div class="stat-desc">Authors & co-authors</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Bus Factor</div>
                <div class="stat-value" style="color: { 'var(--accent-pink)' if stats['bus_factor'] <= 1 else 'var(--accent-green)' }">{stats["bus_factor"]}</div>
                <div class="stat-desc">Devs accounting for >50% of commits</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">Collaborative Files</div>
                <div class="stat-value" style="color: var(--accent-orange)">{stats["collaboratively_owned_files"]}</div>
                <div class="stat-desc">Files modified by >1 developer</div>
            </div>
        </div>
        
        <div class="main-layout">
            <div class="left-col">
                <div class="card">
                    <div class="card-title">Co-authorship Network <span style="font-size: 0.8rem; font-weight: normal; color: var(--text-secondary);">Drag nodes to reorganize (Double-click to lock)</span></div>
                    <div class="network-container" id="networkContainer">
                        <!-- Node visualization will be generated dynamically here -->
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-title">Top 15 Most Collaborated Files</div>
                    <div style="overflow-x: auto;">
                        <table>
                            <thead>
                                <tr>
                                    <th>File Path</th>
                                    <th style="text-align: center;">Contributors</th>
                                    <th style="text-align: center;">Total Commits</th>
                                </tr>
                            </thead>
                            <tbody>
                                {"".join(f'<tr><td class="file-path">{item["file"]}</td><td style="text-align: center; font-weight: bold; color: var(--accent-orange);">{item["contributors"]}</td><td style="text-align: center;">{item["commits"]}</td></tr>' for item in stats["top_shared_files"])}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
            
            <div class="right-col">
                <div class="card">
                    <div class="card-title">Top Contributors</div>
                    <div class="bar-chart-container">
                        {"".join(f'<div class="bar-row"><div class="bar-label" title="{auth}">{auth.split("<")[0].strip()}</div><div class="bar-track"><div class="bar-fill" style="width: {(count/stats["total_commits"])*100:.1f}%;"></div></div><div class="bar-val">{count}</div></div>' for auth, count in sorted(stats["author_commits"].items(), key=lambda x: x[1], reverse=True)[:10])}
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-title">Bus Factor Impact</div>
                    <p style="font-size: 0.9rem; color: var(--text-secondary); margin-bottom: 1rem;">
                        The minimum group of authors that completed half of all commits in this repository:
                    </p>
                    <ul style="list-style-position: inside; font-size: 0.9rem; display: flex; flex-direction: column; gap: 0.5rem;">
                        {"".join(f'<li style="color: var(--text-primary);"><strong style="color: var(--accent-green);">{count} commits</strong> - {auth.split("<")[0].strip()}</li>' for auth, count in stats["majority_developers"])}
                    </ul>
                </div>
                
                <div class="card">
                    <div class="card-title">Commit Activity by Hour (Local Time)</div>
                    <div class="hour-grid">
                        {"".join(f'<div class="hour-bar" style="height: {(count/max(stats["hourly_distribution"] or [1]))*100}%;" data-tooltip="{count} commits at {h:02d}:00"></div>' for h, count in enumerate(stats["hourly_distribution"]))}
                    </div>
                    <div class="hour-labels">
                        {"".join(f'<span>{h}</span>' for h in [0, 4, 8, 12, 16, 20])}
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Simple force-directed network layout in pure JS/HTML5 Canvas or Absolute Divs
        const nodes = {json.dumps(nodes)};
        const links = {json.dumps(links)};
        const container = document.getElementById('networkContainer');
        const width = container.clientWidth;
        const height = container.clientHeight;
        
        // Initialize positions in a circle
        nodes.forEach((node, i) => {{
            const angle = (i / nodes.length) * 2 * Math.PI;
            node.x = width / 2 + Math.cos(angle) * (Math.min(width, height) / 3);
            node.y = height / 2 + Math.sin(angle) * (Math.min(width, height) / 3);
            node.vx = 0;
            node.vy = 0;
            node.size = Math.max(12, Math.min(60, 10 + Math.sqrt(node.total_influence) * 5));
        }});
        
        // Render loop
        function tick() {{
            // Apply forces
            // 1. Repulsion between nodes
            for (let i = 0; i < nodes.length; i++) {{
                for (let j = i + 1; j < nodes.length; j++) {{
                    const n1 = nodes[i];
                    const n2 = nodes[j];
                    const dx = n2.x - n1.x;
                    const dy = n2.y - n1.y;
                    const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                    const minDist = n1.size + n2.size + 40;
                    
                    if (dist < minDist) {{
                        const force = (minDist - dist) / dist * 0.15;
                        n1.vx -= dx * force;
                        n1.vy -= dy * force;
                        n2.vx += dx * force;
                        n2.vy += dy * force;
                    }}
                }}
            }}
            
            // 2. Attraction along links
            links.forEach(link => {{
                const source = nodes[link.source];
                const target = nodes[link.target];
                const dx = target.x - source.x;
                const dy = target.y - source.y;
                const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                const force = 0.015 * (link.weight || 1); // stronger link = stronger pull
                
                source.vx += dx * force;
                source.vy += dy * force;
                target.vx -= dx * force;
                target.vy -= dy * force;
            }});
            
            // 3. Gravity towards center
            nodes.forEach(node => {{
                const dx = width / 2 - node.x;
                const dy = height / 2 - node.y;
                const dist = Math.sqrt(dx * dx + dy * dy) || 1;
                node.vx += dx * 0.005;
                node.vy += dy * 0.005;
            }});
            
            // Update positions and clamp to boundaries
            nodes.forEach(node => {{
                if (node.dragged) return;
                node.x += node.vx;
                node.y += node.vy;
                node.vx *= 0.85; // friction
                node.vy *= 0.85;
                
                node.x = Math.max(node.size, Math.min(width - node.size, node.x));
                node.y = Math.max(node.size, Math.min(height - node.size, node.y));
            }});
            
            draw();
        }}
        
        // Set up SVG canvas overlays
        const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
        svg.style.position = 'absolute';
        svg.style.width = '100%';
        svg.style.height = '100%';
        svg.style.top = '0';
        svg.style.left = '0';
        svg.style.zIndex = '1';
        container.appendChild(svg);
        
        // Create elements
        const divs = [];
        nodes.forEach(node => {{
            const div = document.createElement('div');
            div.className = 'network-node';
            div.style.width = node.size + 'px';
            div.style.height = node.size + 'px';
            div.style.zIndex = '2';
            div.style.background = node.commits > 0 ? 'var(--primary-gradient)' : 'linear-gradient(135deg, #ec4899 0%, #be185d 100%)';
            div.innerText = node.name.substring(0, 3).toUpperCase();
            
            // Create tooltip
            const tooltip = document.createElement('span');
            tooltip.className = 'tooltip';
            tooltip.innerHTML = `<strong>${{node.name}}</strong><br>Commits: ${{node.commits}}<br>Co-authored: ${{node.co_commits}}`;
            div.appendChild(tooltip);
            
            // Drag-and-drop logic
            div.addEventListener('mousedown', (e) => {{
                node.dragged = true;
                const rect = container.getBoundingClientRect();
                function onMouseMove(moveEvent) {{
                    node.x = moveEvent.clientX - rect.left;
                    node.y = moveEvent.clientY - rect.top;
                    draw();
                }}
                function onMouseUp() {{
                    node.dragged = false;
                    window.removeEventListener('mousemove', onMouseMove);
                    window.removeEventListener('mouseup', onMouseUp);
                }}
                window.addEventListener('mousemove', onMouseMove);
                window.addEventListener('mouseup', onMouseUp);
            }});
            
            container.appendChild(div);
            divs.push(div);
        }});
        
        function draw() {{
            // Clear SVG lines
            while (svg.firstChild) {{
                svg.removeChild(svg.firstChild);
            }}
            
            // Draw links
            links.forEach(link => {{
                const s = nodes[link.source];
                const t = nodes[link.target];
                const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
                line.setAttribute("x1", s.x);
                line.setAttribute("y1", s.y);
                line.setAttribute("x2", t.x);
                line.setAttribute("y2", t.y);
                line.setAttribute("stroke", "rgba(99, 102, 241, " + Math.min(0.8, 0.15 + link.weight * 0.1) + ")");
                line.setAttribute("stroke-width", Math.min(6, 1 + link.weight / 2));
                svg.appendChild(line);
            }});
            
            // Position divs
            nodes.forEach((node, i) => {{
                divs[i].style.left = node.x + 'px';
                divs[i].style.top = node.y + 'px';
            }});
        }}
        
        // Simulation loop
        setInterval(tick, 30);
    </script>
</body>
</html>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_template)

def main():
    parser = argparse.ArgumentParser(description="Analyze Git repository collaboration networks.")
    parser.add_argument("--repo-path", default=".", help="Path to the Git repository (default: current directory)")
    parser.add_argument("--output", default="git_collaboration_report.html", help="Path to the output HTML file")
    
    args = parser.parse_args()
    
    abs_repo_path = os.path.abspath(args.repo_path)
    
    if not is_git_repo(abs_repo_path):
        print(f"Error: '{abs_repo_path}' is not a Git repository or git is not installed.", file=sys.stderr)
        sys.exit(1)
        
    print(f"Scanning Git logs in '{abs_repo_path}'...")
    commits = parse_git_log(abs_repo_path)
    
    if not commits:
        print("No commits found or unable to parse git log.", file=sys.stderr)
        sys.exit(1)
        
    print(f"Parsed {len(commits)} commits. Analyzing collaboration stats...")
    stats = analyze_collaboration(commits)
    
    repo_name = os.path.basename(abs_repo_path)
    if repo_name == "" or repo_name == ".":
        repo_name = "Python-tools"
        
    output_file = os.path.abspath(args.output)
    print(f"Generating HTML report: {output_file}")
    generate_html_report(stats, repo_name, output_file)
    print("Done!")

if __name__ == "__main__":
    main()
