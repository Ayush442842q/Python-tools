#!/usr/bin/env python3
"""
GitHub Profile & Repository Analyzer

Fetches public data from the GitHub API for a given username and generates a
detailed statistics report, including repositories, programming languages, star counts,
and top repositories. Outputs as a beautiful ASCII card in console or a Markdown file.

Usage:
    python tools/github_profile_analyzer.py <username> [options]
"""

import sys
import os
import json
import argparse
import datetime
import urllib.request
import urllib.error

# Terminal colors
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"

def print_banner():
    banner = f"""
{CYAN}{BOLD}=========================================================
      🐙  GITHUB PROFILE & REPOSITORY ANALYZER  🐙
========================================================={RESET}
"""
    print(banner)


class GitHubAnalyzer:
    def __init__(self, username, token=None):
        self.username = username
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.headers = {
            "User-Agent": "Python-Tools-GitHub-Profile-Analyzer",
            "Accept": "application/vnd.github.v3+json"
        }
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

    def _fetch_url(self, url):
        """Sends HTTP request to GitHub API and parses JSON response."""
        req = urllib.request.Request(url, headers=self.headers)
        try:
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 403 and "rate limit exceeded" in e.reason.lower():
                raise RuntimeError("GitHub API rate limit exceeded. Try using a GITHUB_TOKEN.")
            elif e.code == 404:
                raise RuntimeError(f"User '{self.username}' not found on GitHub.")
            else:
                raise RuntimeError(f"HTTP Error {e.code}: {e.reason}")
        except Exception as e:
            raise RuntimeError(f"Connection Error: {e}")

    def analyze(self):
        """Orchestrates fetching and analyzing user stats."""
        # Fetch profile
        user_url = f"https://api.github.com/users/{self.username}"
        user_data = self._fetch_url(user_url)

        # Fetch repositories (handle pagination up to 3 pages / 300 repos)
        repos = []
        page = 1
        while page <= 3:
            repos_url = f"https://api.github.com/users/{self.username}/repos?per_page=100&page={page}"
            page_repos = self._fetch_url(repos_url)
            if not page_repos:
                break
            repos.extend(page_repos)
            if len(page_repos) < 100:
                break
            page += 1

        return self._process_stats(user_data, repos)

    def _process_stats(self, user, repos):
        """Aggregates raw profile and repo details."""
        total_stars = 0
        total_forks = 0
        languages = {}
        top_repos = []
        
        for r in repos:
            if not r["fork"]:  # Analyze only original repositories
                total_stars += r["stargazers_count"]
                total_forks += r["forks_count"]
                
                lang = r["language"]
                if lang:
                    languages[lang] = languages.get(lang, 0) + 1
                    
                top_repos.append({
                    "name": r["name"],
                    "stars": r["stargazers_count"],
                    "forks": r["forks_count"],
                    "url": r["html_url"],
                    "description": r["description"] or "No description"
                })

        # Sort top repos by stars
        top_repos.sort(key=lambda x: x["stars"], reverse=True)
        top_5_repos = top_repos[:5]

        # Calculate language percentages
        total_lang_repos = sum(languages.values())
        lang_percentages = {}
        if total_lang_repos > 0:
            for l, count in languages.items():
                lang_percentages[l] = (count / total_lang_repos) * 100
        # Sort languages by popularity
        sorted_languages = sorted(lang_percentages.items(), key=lambda x: x[1], reverse=True)

        return {
            "username": user["login"],
            "name": user["name"] or user["login"],
            "bio": user["bio"] or "No bio available.",
            "avatar_url": user["avatar_url"],
            "profile_url": user["html_url"],
            "company": user["company"] or "Not specified",
            "location": user["location"] or "Not specified",
            "created_at": user["created_at"],
            "public_repos": user["public_repos"],
            "followers": user["followers"],
            "following": user["following"],
            "total_stars": total_stars,
            "total_forks": total_forks,
            "languages": sorted_languages,
            "top_repos": top_5_repos
        }


def print_ascii_dashboard(stats):
    """Prints a beautiful retro ASCII dashboard to the terminal."""
    created_date = datetime.datetime.strptime(stats["created_at"], "%Y-%m-%dT%H:%M:%SZ").strftime("%b %d, %Y")
    
    # Outer frame
    width = 65
    print("┌" + "─" * (width - 2) + "┐")
    
    # Header block
    name_title = f"{stats['name']} (@{stats['username']})"
    print(f"│ {BOLD}{CYAN}{name_title:<61}{RESET} │")
    print(f"│ {stats['bio'][:59]:<61} │")
    print("├" + "─" * (width - 2) + "┤")
    
    # Profile Quick Stats
    print(f"│ {BOLD}Company:{RESET} {stats['company']:<20} | {BOLD}Location:{RESET} {stats['location']:<22} │")
    print(f"│ {BOLD}Created:{RESET} {created_date:<20} | {BOLD}Followers:{RESET} {stats['followers']:<9} Following: {stats['following']:<3} │")
    print("├" + "─" * (width - 2) + "┤")
    
    # Code Stats
    print(f"│ {BOLD}{YELLOW}Repository & Code Analytics{RESET}{'':<37} │")
    print(f"│   - Public Repos: {stats['public_repos']:<10} |   - Total Stars: {stats['total_stars']:<11} │")
    print(f"│   - Total Forks:  {stats['total_forks']:<10} | {'':<35} │")
    
    # Languages Bar
    if stats["languages"]:
        print("│" + " " * (width - 2) + "│")
        print(f"│ {BOLD}Top Programming Languages:{RESET}{'':<37} │")
        for lang, pct in stats["languages"][:4]:
            bar_len = int(pct / 5)  # Max 20 chars bar
            bar = "█" * bar_len + "░" * (20 - bar_len)
            print(f"│   {lang:<15} [{bar}] {pct:>5.1f}%{'':<18} │")
            
    print("├" + "─" * (width - 2) + "┤")
    
    # Top Repositories
    print(f"│ {BOLD}{GREEN}Top 5 Repositories (by Stars){RESET}{'':<34} │")
    for idx, repo in enumerate(stats["top_repos"]):
        repo_line = f"  {idx+1}. {repo['name']} (★ {repo['stars']} | 🍴 {repo['forks']})"
        print(f"│ {repo_line:<61} │")
        desc = repo['description'][:55] + "..." if len(repo['description']) > 55 else repo['description']
        print(f"│    {desc:<58} │")
        
    print("└" + "─" * (width - 2) + "┘")


def save_markdown_report(stats, filepath):
    """Saves profile analytics as a Markdown report."""
    created_date = datetime.datetime.strptime(stats["created_at"], "%Y-%m-%dT%H:%M:%SZ").strftime("%B %d, %Y")
    
    md_content = f"""# GitHub Profile Analysis: {stats['name']}

Generated on: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

## Profile Summary

| Metric | Value |
| :--- | :--- |
| **Username** | [@{stats['username']}]({stats['profile_url']}) |
| **Bio** | {stats['bio']} |
| **Company** | {stats['company']} |
| **Location** | {stats['location']} |
| **Joined GitHub** | {created_date} |
| **Followers** | {stats['followers']} |
| **Following** | {stats['following']} |

## Code Statistics

- **Public Repositories**: {stats['public_repos']}
- **Total Stars Received**: {stats['total_stars']}
- **Total Forks Received**: {stats['total_forks']}

## Primary Languages

"""
    for lang, pct in stats["languages"]:
        md_content += f"- **{lang}**: {pct:.1f}%\n"

    md_content += "\n## Top Repositories\n\n"
    for idx, repo in enumerate(stats["top_repos"]):
        md_content += f"### {idx+1}. [{repo['name']}]({repo['url']})\n"
        md_content += f"- **Stars**: ★ {repo['stars']} | **Forks**: 🍴 {repo['forks']}\n"
        md_content += f"- **Description**: {repo['description']}\n\n"

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(md_content)
    print(f"\nSaved Markdown report to: {BOLD}{GREEN}{filepath}{RESET}")


def main():
    print_banner()
    parser = argparse.ArgumentParser(
        description="Fetch and analyze GitHub profiles",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("username", help="GitHub username to analyze")
    parser.add_argument("--token", help="GitHub Personal Access Token (for higher rate limits)")
    parser.add_argument("-o", "--output", help="Path to save stats as a Markdown file")

    args = parser.parse_args()

    try:
        print(f"Querying GitHub API for user: {BOLD}{args.username}{RESET}...")
        analyzer = GitHubAnalyzer(args.username, args.token)
        stats = analyzer.analyze()
        
        # Display Dashboard
        print_ascii_dashboard(stats)
        
        # Save output if requested
        if args.output:
            save_markdown_report(stats, args.output)

    except RuntimeError as e:
        print(f"{RED}Error: {e}{RESET}")
        return 1
    except Exception as e:
        print(f"{RED}An unexpected error occurred: {e}{RESET}")
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
