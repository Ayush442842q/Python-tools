#!/usr/bin/env python3
"""
Git Repository Archive & Space Saver
Cleans build artifacts, runs git gc, compresses the repository,
and generates a space-savings report.
"""

import os
import sys
import time
import shutil
import tarfile
import zipfile
import argparse
import subprocess
from typing import List, Tuple, Dict, Any

# ANSI Colors
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
CYAN = "\033[36m"
RED = "\033[31m"

CLEAN_TARGETS = [
    'node_modules',
    '.venv',
    'venv',
    'env',
    '__pycache__',
    '.pytest_cache',
    '.mypy_cache',
    '.sass-cache',
    '.ipynb_checkpoints',
    'build',
    'dist',
    '*.pyc',
    '*.pyo',
    '*.pyd'
]

def remove_readonly(func, path, excinfo):
    """Helper to remove read-only attribute on Windows during rmtree."""
    import stat
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except Exception:
        pass

def get_dir_size(path: str) -> int:
    """Calculate total size of a directory in bytes."""
    total = 0
    try:
        for root, dirs, files in os.walk(path):
            for f in files:
                fp = os.path.join(root, f)
                if os.path.exists(fp):
                    total += os.path.getsize(fp)
    except Exception:
        pass
    return total

def format_size(size_bytes: int) -> str:
    """Format size in bytes to human-readable string."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.2f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.2f} PB"

def find_cleanable_items(repo_path: str) -> List[Tuple[str, str, int]]:
    """Scan the repository for build items and calculate their size."""
    cleanable = []
    
    # We walk the repo
    for root, dirs, files in os.walk(repo_path):
        # Don't walk inside .git or already matched dirs
        if '.git' in dirs:
            dirs.remove('.git')
            
        # Check directories
        for d in list(dirs):
            if d in CLEAN_TARGETS:
                full_path = os.path.join(root, d)
                size = get_dir_size(full_path)
                cleanable.append((full_path, 'dir', size))
                # Remove from walk so we don't traverse inside it
                dirs.remove(d)
                
        # Check files
        for f in files:
            for target in CLEAN_TARGETS:
                if target.startswith('*.'):
                    ext = target[1:]
                    if f.endswith(ext):
                        full_path = os.path.join(root, f)
                        size = os.path.getsize(full_path)
                        cleanable.append((full_path, 'file', size))
                        break
                        
    return cleanable

def run_git_gc(repo_path: str) -> Tuple[bool, str]:
    """Run git garbage collection to shrink the git database."""
    if not shutil.which('git'):
        return False, "Git is not installed on system path."
    try:
        res = subprocess.run(
            ['git', 'gc', '--prune=now', '--aggressive'],
            cwd=repo_path,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        if res.returncode == 0:
            return True, res.stdout
        return False, res.stderr
    except Exception as e:
        return False, str(e)

def archive_repo(repo_path: str, output_path: str) -> bool:
    """Compress the directory to a tarball (.tar.gz)."""
    try:
        with tarfile.open(output_path, "w:gz") as tar:
            tar.add(repo_path, arcname=os.path.basename(repo_path))
        return True
    except Exception as e:
        print(f"{RED}Archiving failed: {e}{RESET}", file=sys.stderr)
        return False

def save_report(report_path: str, data: Dict[str, Any]):
    """Save the space saving report to a markdown file."""
    try:
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f"# Git Repository Archive Report\n\n")
            f.write(f"- **Repository:** `{data['name']}`\n")
            f.write(f"- **Path:** `{data['path']}`\n")
            f.write(f"- **Archive Date:** {data['date']}\n\n")
            
            f.write(f"## Storage Summary\n\n")
            f.write(f"| State | Size |\n")
            f.write(f"| --- | --- |\n")
            f.write(f"| Original Size | {format_size(data['orig_size'])} |\n")
            f.write(f"| After Cleaning | {format_size(data['clean_size'])} |\n")
            if 'archive_size' in data:
                f.write(f"| Compressed Size | {format_size(data['archive_size'])} |\n")
                savings = data['orig_size'] - data['archive_size']
                savings_pct = (savings / data['orig_size'] * 100) if data['orig_size'] > 0 else 0
                f.write(f"| **Total Savings** | **{format_size(savings)} ({savings_pct:.1f}%)** |\n")
            f.write(f"\n")
            
            if data['cleaned_items']:
                f.write(f"## Cleaned Items\n\n")
                f.write(f"| Path | Type | Size |\n")
                f.write(f"| --- | --- | --- |\n")
                for path, item_type, size in data['cleaned_items']:
                    rel = os.path.relpath(path, data['path'])
                    f.write(f"| `{rel}` | {item_type} | {format_size(size)} |\n")
                f.write(f"\n")
                
            if data['git_gc_run']:
                f.write(f"## Git Garbage Collection\n\n")
                f.write(f"Git GC was run successfully to shrink the internal repository objects database.\n")
                
        print(f"{GREEN}Saved archive report: {report_path}{RESET}")
    except Exception as e:
        print(f"{RED}Error writing report: {e}{RESET}", file=sys.stderr)

def main():
    parser = argparse.ArgumentParser(
        description="Clean and archive a Git repository, shrinking space requirements.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/git_repo_archiver.py --repo-path . --output-dir ../archives/
  python tools/git_repo_archiver.py --clean-only
        """
    )
    parser.add_argument("-r", "--repo-path", default=".", help="Path to the git repository (default: current directory)")
    parser.add_argument("-o", "--output-dir", help="Directory where archive will be saved (default: parent directory)")
    parser.add_argument("--clean-only", action="store_true", help="Only clean build items and run git gc (do not generate compressed archive)")
    parser.add_argument("--dry-run", action="store_true", help="Perform scan and list sizes without actually deleting or archiving anything")
    
    args = parser.parse_args()
    
    repo_path = os.path.abspath(args.repo_path)
    if not os.path.exists(os.path.join(repo_path, '.git')):
        print(f"{RED}Error: {repo_path} is not a valid Git repository root.{RESET}", file=sys.stderr)
        sys.exit(1)
        
    repo_name = os.path.basename(repo_path)
    
    # Calculate original size
    print(f"{BOLD}{CYAN}Scanning repository: {repo_path}...{RESET}")
    orig_size = get_dir_size(repo_path)
    print(f"Original size: {format_size(orig_size)}")
    
    cleanable = find_cleanable_items(repo_path)
    cleanable_total_size = sum(item[2] for item in cleanable)
    
    print(f"Found {len(cleanable)} build items that can be cleaned ({format_size(cleanable_total_size)})")
    
    if args.dry_run:
        print(f"\n{BOLD}{YELLOW}Dry run matches:{RESET}")
        for path, item_type, size in cleanable:
            print(f"  - [{item_type}] {os.path.relpath(path, repo_path)} ({format_size(size)})")
        print(f"\nTotal potential savings: {format_size(cleanable_total_size)}")
        sys.exit(0)
        
    # Delete cleanable items
    cleaned_items = []
    if cleanable:
        print(f"\n{YELLOW}Cleaning build files...{RESET}")
        for path, item_type, size in cleanable:
            try:
                if item_type == 'dir':
                    shutil.rmtree(path, onerror=remove_readonly)
                else:
                    os.chmod(path, 0o777)
                    os.unlink(path)
                cleaned_items.append((path, item_type, size))
                print(f"  {GREEN}✓{RESET} Deleted {os.path.relpath(path, repo_path)}")
            except Exception as e:
                print(f"  {RED}×{RESET} Failed to delete {os.path.relpath(path, repo_path)}: {e}")
                
    # Run Git GC
    print(f"\n{YELLOW}Running git garbage collection...{RESET}")
    gc_ok, gc_msg = run_git_gc(repo_path)
    if gc_ok:
        print(f"  {GREEN}✓{RESET} Git GC finished successfully.")
    else:
        print(f"  {YELLOW}⚠{RESET} Git GC skipped/failed: {gc_msg}")
        
    post_clean_size = get_dir_size(repo_path)
    print(f"\nSize after cleaning: {format_size(post_clean_size)}")
    
    report_data = {
        'name': repo_name,
        'path': repo_path,
        'date': time.strftime("%Y-%m-%d %H:%M:%S"),
        'orig_size': orig_size,
        'clean_size': post_clean_size,
        'cleaned_items': cleaned_items,
        'git_gc_run': gc_ok
    }
    
    if not args.clean_only:
        # Determine output archive path
        out_dir = args.output_dir or os.path.dirname(repo_path)
        os.makedirs(out_dir, exist_ok=True)
        
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        archive_filename = f"{repo_name}_{timestamp}.tar.gz"
        archive_path = os.path.join(out_dir, archive_filename)
        
        print(f"\n{YELLOW}Archiving repository to {archive_path}...{RESET}")
        if archive_repo(repo_path, archive_path):
            archive_size = os.path.getsize(archive_path)
            print(f"  {GREEN}✓{RESET} Archive created. Size: {format_size(archive_size)}")
            report_data['archive_size'] = archive_size
            
            # Save report
            report_filename = f"{repo_name}_{timestamp}_report.md"
            report_path = os.path.join(out_dir, report_filename)
            save_report(report_path, report_data)
            
            savings = orig_size - archive_size
            savings_pct = (savings / orig_size * 100) if orig_size > 0 else 0
            print(f"\n{BOLD}{GREEN}Archive complete! Saved {format_size(savings)} ({savings_pct:.1f}% space savings).{RESET}")
        else:
            print(f"\n{BOLD}{RED}Archive failed.{RESET}")
    else:
        # Just clean
        savings = orig_size - post_clean_size
        savings_pct = (savings / orig_size * 100) if orig_size > 0 else 0
        print(f"\n{BOLD}{GREEN}Cleanup complete! Reclaimed {format_size(savings)} ({savings_pct:.1f}% size reduction).{RESET}")

if __name__ == "__main__":
    main()
