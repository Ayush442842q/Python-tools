#!/usr/bin/env python3
"""
GitHub Star History Visualizer - Fetches star history for a GitHub repository
and renders an ASCII star-growth chart in the terminal or exports an HTML/SVG line chart.
Uses only standard Python libraries (urllib, json, datetime).
"""

import argparse
from datetime import datetime
import json
import math
import sys
import urllib.request


def fetch_repo_stars(repo_path, token=None):
    """Fetches general repository information to check total star count."""
    url = f"https://api.github.com/repos/{repo_path}"
    headers = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"token {token}"
        
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as res:
            data = json.loads(res.read().decode())
            return data.get("stargazers_count", 0), data.get("created_at")
    except Exception as e:
        print(f"[-] Error fetching repo info: {e}", file=sys.stderr)
        return None, None


def fetch_stargazers_page(repo_path, page, token=None):
    """Fetches a single page of stargazers with their starred_at timestamps."""
    url = f"https://api.github.com/repos/{repo_path}/stargazers?per_page=100&page={page}"
    # Header required to get starred_at timestamps
    headers = {
        "Accept": "application/vnd.github.v3.star+json",
        "User-Agent": "Python-urllib"
    }
    if token:
        headers["Authorization"] = f"token {token}"
        
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req) as res:
            return json.loads(res.read().decode())
    except Exception as e:
        # Check for rate limiting
        if hasattr(e, "status") and e.status == 403:
            print("[-] API Rate Limit Exceeded. Use a GitHub token with --token to increase limits.", file=sys.stderr)
        else:
            print(f"[-] Error fetching page {page}: {e}", file=sys.stderr)
        return None


def collect_star_history(repo_path, total_stars, created_at_str, token=None, max_samples=30):
    """Collects star timestamps. Samples pages if repo is large to stay within rate limits."""
    created_at = datetime.strptime(created_at_str, "%Y-%m-%dT%H:%M:%SZ")
    
    # Calculate pages needed
    total_pages = math.ceil(total_stars / 100)
    print(f"[*] Total stars: {total_stars} (~{total_pages} pages of data)")
    
    star_history = []
    # Always insert initial state
    star_history.append((created_at, 0))
    
    if total_pages == 0:
        return star_history
        
    # If the repository is small or we have a token, we can get full history.
    # Otherwise, we sample to avoid rate limits (60 requests/hr unauthenticated).
    pages_to_fetch = list(range(1, total_pages + 1))
    
    if len(pages_to_fetch) > max_samples:
        # Sample pages evenly
        step = len(pages_to_fetch) / max_samples
        sampled_indices = [int(i * step) for i in range(max_samples)]
        # Ensure the last page is fetched
        sampled_indices.append(len(pages_to_fetch) - 1)
        pages_to_fetch = [pages_to_fetch[i] for i in sorted(list(set(sampled_indices)))]
        print(f"[*] Sampling {len(pages_to_fetch)} pages to stay within GitHub API rate limits.")
    else:
        print(f"[*] Fetching all {len(pages_to_fetch)} pages sequentially.")
        
    for count, page in enumerate(pages_to_fetch, 1):
        print(f"[*] Requesting page {page}/{total_pages} ({count}/{len(pages_to_fetch)})...")
        stargazers = fetch_stargazers_page(repo_path, page, token)
        if not stargazers:
            break
            
        # Get timestamp of the first stargazer on this page
        first_starred = stargazers[0]["starred_at"]
        dt = datetime.strptime(first_starred, "%Y-%m-%dT%H:%M:%SZ")
        
        # Approximate star count at this page timestamp
        approx_stars = (page - 1) * 100
        star_history.append((dt, approx_stars))
        
    # Append final state
    star_history.append((datetime.now(), total_stars))
    # Sort chronologically
    star_history.sort(key=lambda x: x[0])
    return star_history


def draw_ascii_chart(history, width=60, height=15):
    """Draws an ASCII line graph of the star history in the terminal."""
    if len(history) < 2:
        return "Not enough data to plot chart."
        
    # Find mins and maxs
    min_time = history[0][0].timestamp()
    max_time = history[-1][0].timestamp()
    max_stars = history[-1][1]
    
    if max_time == min_time:
        max_time += 1
        
    # Setup canvas grid
    grid = [[" " for _ in range(width)] for _ in range(height)]
    
    # Map history points to coordinates
    prev_x, prev_y = None, None
    for dt, stars in history:
        t = dt.timestamp()
        
        # Scale coords
        x = int(((t - min_time) / (max_time - min_time)) * (width - 1))
        y = int((stars / max_stars) * (height - 1))
        
        # Invert y because 0 is top of terminal grid
        y = height - 1 - y
        
        # Clamp bounds
        x = max(0, min(x, width - 1))
        y = max(0, min(y, height - 1))
        
        grid[y][x] = "*"
        
        # Draw linear interpolation lines
        if prev_x is not None:
            # Simple line drawing
            dx = x - prev_x
            dy = y - prev_y
            steps = max(abs(dx), abs(dy))
            if steps > 0:
                for s in range(1, steps):
                    ix = int(prev_x + (dx * s / steps))
                    iy = int(prev_y + (dy * s / steps))
                    if 0 <= ix < width and 0 <= iy < height:
                        grid[iy][ix] = "."
                        
        prev_x, prev_y = x, y
        
    # Build chart string with axes
    out_lines = []
    for h_idx in range(height):
        # Y-axis label (star count)
        val = int(((height - 1 - h_idx) / (height - 1)) * max_stars)
        label = f"{val:5d} | "
        out_lines.append(label + "".join(grid[h_idx]))
        
    # X-axis timeline
    out_lines.append("      " + "-" * (width + 1))
    
    # X-axis dates
    start_date = history[0][0].strftime("%Y-%m")
    end_date = history[-1][0].strftime("%Y-%m")
    mid_date = datetime.fromtimestamp(min_time + (max_time - min_time) / 2).strftime("%Y-%m")
    
    dates_line = "      " + start_date
    spacing = (width - len(start_date) - len(end_date)) // 2
    dates_line += " " * spacing + mid_date
    dates_line += " " * (width - len(dates_line) + 6 - len(end_date)) + end_date
    out_lines.append(dates_line)
    
    return "\n".join(out_lines)


def generate_html_report(repo_path, history):
    """Generates an HTML/SVG line chart mapping out star growth over time."""
    data_points = []
    for dt, stars in history:
        # Convert date to string format for javascript
        date_str = dt.strftime("%Y-%m-%d")
        data_points.append(f"{{ x: '{date_str}', y: {stars} }}")
        
    points_js = ",\n        ".join(data_points)
    
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>GitHub Star History - {repo_path}</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chartjs-adapter-date-fns"></script>
  <style>
    body {{
      font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      background-color: #0d1117;
      color: #c9d1d9;
      margin: 0;
      padding: 40px;
      display: flex;
      flex-direction: column;
      align-items: center;
    }}
    h1 {{
      color: #58a6ff;
      margin-bottom: 5px;
    }}
    p {{
      color: #8b949e;
      margin-bottom: 30px;
    }}
    .chart-container {{
      position: relative;
      width: 80%;
      max-width: 900px;
      background-color: #161b22;
      border: 1px solid #30363d;
      border-radius: 8px;
      padding: 25px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.4);
    }}
    a {{
      color: #58a6ff;
      text-decoration: none;
    }}
    a:hover {{
      text-decoration: underline;
    }}
  </style>
</head>
<body>
  <h1>Star History Visualizer</h1>
  <p>Repository: <a href="https://github.com/{repo_path}" target="_blank">{repo_path}</a></p>
  
  <div class="chart-container">
    <canvas id="starChart"></canvas>
  </div>

  <script>
    const ctx = document.getElementById('starChart').getContext('2d');
    new Chart(ctx, {{
      type: 'line',
      data: {{
        datasets: [{{
          label: 'GitHub Stars',
          data: [
            {points_js}
          ],
          borderColor: '#ffdf5d',
          backgroundColor: 'rgba(255, 223, 93, 0.1)',
          borderWidth: 3,
          fill: true,
          tension: 0.1
        }}]
      }},
      options: {{
        scales: {{
          x: {{
            type: 'time',
            time: {{
              unit: 'month'
            }},
            grid: {{
              color: '#30363d'
            }},
            ticks: {{
              color: '#8b949e'
            }}
          }},
          y: {{
            grid: {{
              color: '#30363d'
            }},
            ticks: {{
              color: '#8b949e'
            }}
          }}
        }},
        plugins: {{
          legend: {{
            labels: {{
              color: '#c9d1d9'
            }}
          }}
        }}
      }}
    }});
  </script>
</body>
</html>
"""
    return html_content


def main():
    parser = argparse.ArgumentParser(
        description="GitHub Star History Visualizer - Plot cumulative star growth of a repository."
    )
    parser.add_argument("repo", help="Target GitHub repository (format: owner/repo)")
    parser.add_argument("-t", "--token", help="Optional GitHub Personal Access Token to bypass rate limits")
    parser.add_argument("-w", "--width", type=int, default=60, help="Width of ASCII chart (default: 60)")
    parser.add_argument("-h", "--height", type=int, default=15, help="Height of ASCII chart (default: 15)")
    parser.add_argument("-s", "--samples", type=int, default=30, help="Max number of page samples to pull (default: 30)")
    parser.add_argument("-o", "--output", help="Save interactive HTML visual chart path")
    
    args = parser.parse_args()
    
    repo_path = args.repo.strip()
    if "/" not in repo_path:
        print("[-] Invalid repository format. Please specify 'owner/repo' (e.g. google/jax).", file=sys.stderr)
        return 1
        
    print(f"[*] Fetching metadata for {repo_path}...")
    total_stars, created_at = fetch_repo_stars(repo_path, args.token)
    
    if total_stars is None:
        return 1
        
    history = collect_star_history(repo_path, total_stars, created_at, args.token, args.samples)
    
    print("\nStar growth curve:")
    print(draw_ascii_chart(history, args.width, args.height))
    
    if args.output:
        html = generate_html_report(repo_path, history)
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(html)
            print(f"\n[+] Interactive star chart saved to: {args.output}")
        except Exception as e:
            print(f"[-] Error saving HTML chart: {e}", file=sys.stderr)
            return 1
            
    return 0


if __name__ == "__main__":
    sys.exit(main())
