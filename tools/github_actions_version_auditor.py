#!/usr/bin/env python3
"""
GitHub Actions Version Auditor - Audit GitHub Actions workflow dependency versions and security pinning.
"""

import argparse
import json
import os
import re
import urllib.error
import urllib.request
from typing import Dict, List, Set, Tuple

# Regex to match 'uses: owner/repo@ref' or 'uses: owner/repo/path@ref'
# Ignore local actions like 'uses: ./.github/actions/my-action'
USES_PATTERN = re.compile(r"^\s*uses:\s*([\w\-]+/[\w\-]+)(?:/[\w\-]+)*@([\w\.\-/]+)(?:\s+#\s*(.+))?$")

class ActionAuditor:
    def __init__(self, token: str = None, check_online: bool = True):
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.check_online = check_online
        self.cache: Dict[str, Dict] = {}

    def fetch_latest_github_data(self, action_name: str) -> Dict:
        """Fetches the latest release and tags for a repository from GitHub API."""
        if action_name in self.cache:
            return self.cache[action_name]

        result = {"latest_release": None, "latest_tag": None, "error": None}
        if not self.check_online:
            return result

        headers = {
            "User-Agent": "GitHub-Actions-Version-Auditor/1.0",
            "Accept": "application/vnd.github.v3+json"
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"

        # 1. Fetch latest release
        release_url = f"https://api.github.com/repos/{action_name}/releases/latest"
        try:
            req = urllib.request.Request(release_url, headers=headers)
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())
                result["latest_release"] = data.get("tag_name")
        except urllib.error.HTTPError as e:
            if e.code == 404:
                # No formal release, we will rely on tags
                pass
            else:
                result["error"] = f"HTTP Error {e.code}"
        except Exception as e:
            result["error"] = str(e)

        # 2. Fetch tags list
        tags_url = f"https://api.github.com/repos/{action_name}/tags?per_page=1"
        try:
            req = urllib.request.Request(tags_url, headers=headers)
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode())
                if data and isinstance(data, list):
                    result["latest_tag"] = data[0].get("name")
        except Exception as e:
            if not result["error"]:
                result["error"] = str(e)

        self.cache[action_name] = result
        return result

    def audit_workflow(self, filepath: str) -> List[Dict]:
        results = []
        if not os.path.exists(filepath):
            return results

        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for idx, line in enumerate(lines, 1):
            match = USES_PATTERN.match(line)
            if match:
                action, ref, comment = match.groups()
                is_sha = len(ref) == 40 and all(c in "0123456789abcdefABCDEF" for c in ref)
                
                # Check comment for tag reference if pinned to SHA
                # e.g., uses: actions/checkout@v3.1.0 # v3
                friendly_ref = ref
                if is_sha and comment:
                    comment_match = re.search(r"(v\d+[\w\.]*)", comment)
                    if comment_match:
                        friendly_ref = comment_match.group(1)

                results.append({
                    "file": filepath,
                    "line": idx,
                    "action": action,
                    "ref": ref,
                    "is_sha": is_sha,
                    "friendly_ref": friendly_ref,
                    "comment": comment
                })
        return results

def main():
    parser = argparse.ArgumentParser(description="Audit GitHub Actions workflow versions.")
    parser.add_argument("path", nargs="?", default=".github/workflows", 
                        help="Path to workflow file or directory of workflows (default: .github/workflows)")
    parser.add_argument("--offline", action="store_true", help="Perform static configuration check only (no API requests).")
    parser.add_argument("--token", help="GitHub Personal Access Token to avoid API rate limits.")
    args = parser.parse_args()

    auditor = ActionAuditor(token=args.token, check_online=not args.offline)

    # Resolve files
    files = []
    if os.path.isfile(args.path):
        files.append(args.path)
    elif os.path.isdir(args.path):
        for root, _, filenames in os.walk(args.path):
            for f in filenames:
                if f.endswith((".yml", ".yaml")):
                    files.append(os.path.join(root, f))
    else:
        print(f"Path '{args.path}' not found.")
        exit(1)

    all_audits = []
    for f in files:
        all_audits.extend(auditor.audit_workflow(f))

    if not all_audits:
        print("No GitHub Actions workflows found or no actions dependencies detected.")
        return

    print(f"Auditing {len(all_audits)} actions dependencies across {len(files)} files...")
    print("-" * 80)
    print(f"{'FILE:LINE':<35} | {'ACTION':<25} | {'VERSION':<10} | {'STATUS / SECURITY':<30}")
    print("-" * 80)

    warnings_count = 0
    insecure_count = 0

    for item in all_audits:
        action = item["action"]
        ref = item["ref"]
        file_line = f"{os.path.basename(item['file'])}:{item['line']}"
        
        status_parts = []
        
        # Check security pinning
        if not item["is_sha"]:
            status_parts.append("[UNPINNED (Use SHA)]")
            insecure_count += 1
            
        # Check online updates
        latest_ver = None
        if not args.offline:
            print(f"Fetching updates for {action}...", end="\r")
            data = auditor.fetch_latest_github_data(action)
            latest_ver = data["latest_release"] or data["latest_tag"]
            if latest_ver:
                current = item["friendly_ref"]
                # Clean up versions for comparison (e.g., strip 'v' prefix)
                curr_clean = current.lstrip("v")
                late_clean = latest_ver.lstrip("v")
                
                if curr_clean != late_clean and current not in ref:
                    status_parts.append(f"[OUTDATED -> {latest_ver}]")
                    warnings_count += 1
            elif data["error"]:
                status_parts.append(f"[API Error: {data['error']}]")

        status_str = " ".join(status_parts) if status_parts else "OK"
        print(f"{file_line:<35} | {action:<25} | {ref[:10]:<10} | {status_str}")

    print("-" * 80)
    print("Summary:")
    print(f"  Unpinned Action Tags (Insecure): {insecure_count}")
    if not args.offline:
        print(f"  Outdated Actions: {warnings_count}")
    else:
        print("  Online version check skipped (--offline).")

if __name__ == "__main__":
    main()
