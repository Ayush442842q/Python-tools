#!/usr/bin/env python3
"""
GitHub Folder Downloader - Download specific folders or files from GitHub without cloning the repo

This tool downloads a specific subdirectory or file from a GitHub repository
using the GitHub REST API. This is extremely useful for retrieving only
the files/folders you need from large repositories without full checkouts.

Usage:
    python tools/github_folder_downloader.py "https://github.com/owner/repo/tree/branch/path/to/folder" [-o OUTPUT_DIR] [-t TOKEN]
    python tools/github_folder_downloader.py --repo "owner/repo" --path "path/to/folder" [-b BRANCH] [-o OUTPUT_DIR]
"""

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from typing import Dict, List, Optional, Tuple


def parse_github_url(url: str) -> Tuple[str, str, str, str]:
    """
    Parses a GitHub URL to extract owner, repo, branch/ref, and path.
    Example: https://github.com/psf/requests/tree/main/requests
    Returns: (owner/repo, branch_or_sha, path, type) where type is 'tree' or 'blob'
    """
    # Clean URL
    url = url.rstrip('/')
    parsed = urllib.parse.urlparse(url)
    if parsed.netloc != 'github.com':
        raise ValueError("URL must be a github.com link")

    path_parts = [p for p in parsed.path.split('/') if p]
    if len(path_parts) < 2:
        raise ValueError("Invalid GitHub URL structure. Needs at least owner and repository.")

    repo_identifier = f"{path_parts[0]}/{path_parts[1]}"
    
    if len(path_parts) == 2:
        # Root of repo
        return repo_identifier, "", "", ""

    # Check if tree or blob
    # Format: /owner/repo/tree/branch/path... or /owner/repo/blob/branch/path...
    url_type = path_parts[2]
    if url_type not in ('tree', 'blob'):
        # Fallback to no branch/path if url structure is unexpected
        return repo_identifier, "", "", ""

    if len(path_parts) < 4:
        raise ValueError(f"GitHub URL points to {url_type} but contains no branch/ref specification")

    branch = path_parts[3]
    repo_path = "/".join(path_parts[4:])
    
    return repo_identifier, branch, repo_path, url_type


def make_api_request(url: str, token: Optional[str] = None) -> Tuple[bytes, Dict[str, str]]:
    """Makes an HTTP request to the GitHub API, handling auth headers."""
    req = urllib.request.Request(url)
    req.add_header('User-Agent', 'Python-GitHub-Folder-Downloader')
    req.add_header('Accept', 'application/vnd.github.v3+json')
    
    if token:
        req.add_header('Authorization', f'token {token}')
        
    try:
        with urllib.request.urlopen(req) as response:
            headers = {k.lower(): v for k, v in response.getheaders()}
            return response.read(), headers
    except urllib.error.HTTPError as e:
        # Try to read error body for detail
        try:
            err_body = e.read().decode('utf-8')
            err_json = json.loads(err_body)
            msg = err_json.get('message', str(e))
        except Exception:
            msg = str(e)
            
        if e.code == 403 and 'rate limit' in msg.lower():
            print(f"Error: GitHub API rate limit exceeded. Please use a Personal Access Token (-t/--token).", file=sys.stderr)
        raise RuntimeError(f"GitHub API Error ({e.code}): {msg}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Network error trying to contact GitHub: {e.reason}")


def download_file(download_url: str, dest_path: str, token: Optional[str] = None) -> None:
    """Downloads a raw file from GitHub to the destination path."""
    os.makedirs(os.path.dirname(dest_path), exist_ok=True)
    
    # Raw download URLs don't need authentication if public, but using API is safer for private repos or rate limits
    # However, if download_url is a raw.githubusercontent.com URL, we cannot send the API Accept headers easily.
    # Fortunately, GitHub's API can fetch file content directly via standard request if authentication is needed,
    # but for simplicity, we do standard download.
    
    req = urllib.request.Request(download_url)
    req.add_header('User-Agent', 'Python-GitHub-Folder-Downloader')
    if token and "github.com" in download_url:
        req.add_header('Authorization', f'token {token}')
        
    try:
        with urllib.request.urlopen(req) as response:
            with open(dest_path, 'wb') as f:
                f.write(response.read())
    except Exception as e:
        raise RuntimeError(f"Failed to download file to {dest_path}: {e}")


def download_github_contents(
    repo: str,
    path: str,
    ref: str,
    output_dir: str,
    token: Optional[str] = None,
    current_depth: int = 0
) -> int:
    """
    Recursively queries the GitHub API and downloads matching contents.
    Returns the total count of files downloaded.
    """
    indent = "  " * current_depth
    
    # Construct API contents URL
    # API: https://api.github.com/repos/{owner}/{repo}/contents/{path}
    encoded_path = urllib.parse.quote(path.lstrip('/'))
    api_url = f"https://api.github.com/repos/{repo}/contents/{encoded_path}"
    if ref:
        api_url += f"?ref={urllib.parse.quote(ref)}"
        
    try:
        data, headers = make_api_request(api_url, token)
        contents = json.loads(data.decode('utf-8'))
    except Exception as e:
        print(f"Error fetching path metadata: {e}", file=sys.stderr)
        return 0

    download_count = 0

    # If it's a single file (returns a dict instead of a list of items)
    if isinstance(contents, dict):
        if contents.get('type') == 'file':
            filename = contents['name']
            dest = os.path.join(output_dir, filename)
            print(f"{indent}Downloading file: {contents['path']} -> {dest}")
            download_file(contents['download_url'], dest, token)
            return 1
        else:
            raise ValueError(f"Path '{path}' did not return a file list.")

    # If it's a directory (returns a list of items)
    for item in contents:
        item_type = item['type']
        item_path = item['path']
        item_name = item['name']
        
        # Calculate relative path from the initial download root
        # If we download "src/utils", then item_path is "src/utils/helpers.py"
        # We want the destination to preserve subdirectories under output_dir
        
        # Let's clean paths to align properly
        # Find prefix path to strip. E.g., if we target 'src/utils', strip 'src/utils'
        prefix_to_strip = os.path.dirname(path.strip('/'))
        if prefix_to_strip:
            rel_path = os.path.relpath(item_path, prefix_to_strip)
        else:
            rel_path = item_path
            
        dest_path = os.path.join(output_dir, rel_path)

        if item_type == 'file':
            print(f"{indent}Downloading: {item_path} -> {dest_path}")
            download_file(item['download_url'], dest_path, token)
            download_count += 1
        elif item_type == 'dir':
            print(f"{indent}Entering directory: {item_path}/")
            download_count += download_github_contents(
                repo=repo,
                path=item_path,
                ref=ref,
                output_dir=output_dir,
                token=token,
                current_depth=current_depth + 1
            )
            
    return download_count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Download specific folders or files from GitHub without cloning the entire repository."
    )
    parser.add_argument(
        "url",
        nargs="?",
        help="GitHub URL of the folder or file (e.g. https://github.com/owner/repo/tree/branch/path)"
    )
    parser.add_argument(
        "-r", "--repo",
        help="Repository owner/name (alternative to URL, e.g. 'psf/requests')"
    )
    parser.add_argument(
        "-p", "--path",
        default="",
        help="Directory path or filename within the repository (used with --repo)"
    )
    parser.add_argument(
        "-b", "--branch",
        default="",
        help="Branch or commit SHA (used with --repo)"
    )
    parser.add_argument(
        "-o", "--output",
        default=".",
        help="Target output directory (default: current directory)"
    )
    parser.add_argument(
        "-t", "--token",
        help="GitHub Personal Access Token to authenticate requests and increase rate limit"
    )

    args = parser.parse_args()

    repo = args.repo
    path = args.path
    branch = args.branch

    # If URL is provided, parse it
    if args.url:
        try:
            repo, url_branch, url_path, url_type = parse_github_url(args.url)
            # Use branch and path from URL if they weren't explicitly overridden by flags
            if not branch:
                branch = url_branch
            if not path:
                path = url_path
        except Exception as e:
            parser.error(f"Error parsing GitHub URL: {e}")
    elif not repo:
        parser.error("You must provide either a GitHub URL or specify --repo")

    # Clean target output directory
    output_dir = os.path.abspath(args.output)
    
    print("=" * 60)
    print("GitHub Folder/File Downloader")
    print("=" * 60)
    print(f"Repository: {repo}")
    print(f"Path:       {path if path else '(root)'}")
    print(f"Branch/Ref: {branch if branch else '(default)'}")
    print(f"Output to:  {output_dir}")
    print("-" * 60)

    try:
        total_files = download_github_contents(
            repo=repo,
            path=path,
            ref=branch,
            output_dir=output_dir,
            token=args.token
        )
        print("-" * 60)
        print(f"Success! Downloaded {total_files} files.")
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
