#!/usr/bin/env python3
"""
GitHub Release Downloader
Downloads files, assets, or source code archives from GitHub Releases for a given repository.
Features:
- List releases/tags and assets
- Filter assets by glob pattern
- Pure Python implementation with zero external dependencies
- Dynamic download progress bar with speed and ETA calculations
"""

import argparse
import fnmatch
import json
import os
import sys
import time
import urllib.request
import urllib.error

GITHUB_API_URL = "https://api.github.com/repos"

def make_request(url, headers=None):
    """Make HTTP request with standard User-Agent to avoid blocking by GitHub."""
    req_headers = {"User-Agent": "Mozilla/5.0 (Python GitHub Release Downloader)"}
    if headers:
        req_headers.update(headers)
    
    req = urllib.request.Request(url, headers=req_headers)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"Error: Repository or release not found (404) at {url}", file=sys.stderr)
        elif e.code == 403:
            print("Error: Access forbidden (403). You might have hit the GitHub API rate limit.", file=sys.stderr)
        else:
            print(f"HTTP Error {e.code}: {e.reason}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Network error: {e}", file=sys.stderr)
        sys.exit(1)

def format_size(size_bytes):
    """Format size in bytes to human-readable format."""
    if size_bytes is None:
        return "Unknown"
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} TB"

def download_file(url, output_path):
    """Download a file showing progress bar, speed, and ETA."""
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req) as response:
            total_size = response.getheader('Content-Length')
            if total_size is not None:
                total_size = int(total_size)
            
            bytes_downloaded = 0
            block_size = 8192
            start_time = time.time()
            
            # Ensure output directory exists
            os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
            
            print(f"Downloading to: {output_path}")
            with open(output_path, 'wb') as f:
                while True:
                    buffer = response.read(block_size)
                    if not buffer:
                        break
                    
                    f.write(buffer)
                    bytes_downloaded += len(buffer)
                    
                    # Calculate stats
                    elapsed_time = time.time() - start_time
                    speed = bytes_downloaded / elapsed_time if elapsed_time > 0 else 0
                    
                    # Print progress bar
                    if total_size:
                        percent = (bytes_downloaded / total_size) * 100
                        bar_len = 40
                        filled_len = int(bar_len * bytes_downloaded // total_size)
                        bar = '█' * filled_len + '-' * (bar_len - filled_len)
                        
                        eta = (total_size - bytes_downloaded) / speed if speed > 0 else 0
                        eta_str = f"{eta:.1f}s" if eta < 60 else f"{int(eta//60)}m {int(eta%60)}s"
                        
                        sys.stdout.write(
                            f"\r|{bar}| {percent:.1f}% ({format_size(bytes_downloaded)}/{format_size(total_size)}) "
                            f"@ {format_size(speed)}/s | ETA: {eta_str}"
                        )
                    else:
                        sys.stdout.write(
                            f"\rDownloaded: {format_size(bytes_downloaded)} @ {format_size(speed)}/s"
                        )
                    sys.stdout.flush()
            print("\n✅ Download completed successfully.")
    except Exception as e:
        print(f"\n❌ Error downloading file: {e}", file=sys.stderr)
        if os.path.exists(output_path):
            os.remove(output_path)

def list_releases(repo):
    """List releases for the repository."""
    url = f"{GITHUB_API_URL}/{repo}/releases"
    releases = make_request(url)
    
    if not releases:
        print(f"No releases found for repository '{repo}'.")
        return
    
    print(f"\nReleases for {repo}:")
    print("=" * 60)
    for r in releases[:15]:  # Show top 15
        draft_pre = []
        if r.get('draft'): draft_pre.append("Draft")
        if r.get('prerelease'): draft_pre.append("Pre-release")
        status = f" [{', '.join(draft_pre)}]" if draft_pre else ""
        
        print(f"🏷️  Tag: {r['tag_name']}{status}")
        print(f"   Name: {r.get('name') or 'N/A'}")
        print(f"   Published: {r.get('published_at')}")
        print(f"   Assets count: {len(r.get('assets', []))}")
        print("-" * 60)

def list_assets(repo, tag):
    """List assets for a specific release."""
    if tag.lower() == 'latest':
        url = f"{GITHUB_API_URL}/{repo}/releases/latest"
    else:
        url = f"{GITHUB_API_URL}/{repo}/releases/tags/{tag}"
    
    release = make_request(url)
    
    print(f"\nRelease: {release['name']} ({release['tag_name']})")
    print(f"Published: {release.get('published_at')}")
    print("=" * 60)
    
    assets = release.get('assets', [])
    if not assets:
        print("No assets uploaded for this release (only source code archive available).")
    else:
        print("Assets:")
        for idx, asset in enumerate(assets, 1):
            print(f"{idx}. {asset['name']} ({format_size(asset['size'])})")
            print(f"   Downloads: {asset.get('download_count', 0)} | URL: {asset['browser_download_url']}")
            print("-" * 60)
            
    print(f"Source Archives:")
    print(f"📦 Zipball: {release.get('zipball_url')}")
    print(f"📦 Tarball: {release.get('tarball_url')}")

def main():
    parser = argparse.ArgumentParser(description="GitHub Release Downloader - list and download release assets")
    parser.add_argument('repo', help="GitHub repository in 'owner/repo' format (e.g. 'python/cpython')")
    parser.add_argument('-t', '--tag', default='latest', help="Release tag to target (default: 'latest')")
    parser.add_argument('-p', '--pattern', help="Glob pattern to filter assets to download (e.g., '*.tar.gz')")
    parser.add_argument('-o', '--output-dir', default='.', help="Directory to save downloaded files (default: current directory)")
    parser.add_argument('--list-releases', action='store_true', help="List releases for the repository and exit")
    parser.add_argument('--list-assets', action='store_true', help="List assets of the targeted release and exit")
    parser.add_argument('--source', choices=['zip', 'tar'], help="Download source archive ('zip' or 'tar') instead of release assets")
    
    args = parser.parse_args()
    
    # Clean repo name
    repo = args.repo.strip('/')
    if '/' not in repo:
        print("Error: Repository must be in 'owner/repo' format (e.g. 'django/django').", file=sys.stderr)
        return 1
        
    if args.list_releases:
        list_releases(repo)
        return 0
        
    if args.list_assets:
        list_assets(repo, args.tag)
        return 0

    # Fetch release
    if args.tag.lower() == 'latest':
        url = f"{GITHUB_API_URL}/{repo}/releases/latest"
    else:
        url = f"{GITHUB_API_URL}/{repo}/releases/tags/{args.tag}"
    
    print(f"Fetching release details for '{repo}' ({args.tag})...")
    release = make_request(url)
    tag_name = release['tag_name']
    
    # Handle source download option
    if args.source:
        archive_type = args.source
        source_url = release['zipball_url'] if archive_type == 'zip' else release['tarball_url']
        ext = 'zip' if archive_type == 'zip' else 'tar.gz'
        repo_name_only = repo.split('/')[-1]
        out_name = f"{repo_name_only}-{tag_name}.{ext}"
        out_path = os.path.join(args.output_dir, out_name)
        
        print(f"Downloading source archive ({archive_type})...")
        download_file(source_url, out_path)
        return 0

    assets = release.get('assets', [])
    if not assets:
        print("No assets found for this release. Downloading zip source archive instead...")
        source_url = release['zipball_url']
        repo_name_only = repo.split('/')[-1]
        out_path = os.path.join(args.output_dir, f"{repo_name_only}-{tag_name}.zip")
        download_file(source_url, out_path)
        return 0

    # Filter assets
    matching_assets = []
    for asset in assets:
        if args.pattern:
            if fnmatch.fnmatch(asset['name'].lower(), args.pattern.lower()):
                matching_assets.append(asset)
        else:
            matching_assets.append(asset)
            
    if not matching_assets:
        print(f"No assets matched pattern '{args.pattern}' in release {tag_name}.")
        print("Available assets:")
        for asset in assets:
            print(f" - {asset['name']} ({format_size(asset['size'])})")
        return 1
        
    print(f"Found {len(matching_assets)} matching asset(s) in release {tag_name}.")
    for asset in matching_assets:
        out_path = os.path.join(args.output_dir, asset['name'])
        print(f"\nAsset: {asset['name']} ({format_size(asset['size'])})")
        download_file(asset['browser_download_url'], out_path)
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
