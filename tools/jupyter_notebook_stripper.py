#!/usr/bin/env python3
"""
Jupyter Notebook Stripper
Sanitizes Jupyter Notebook (.ipynb) files by removing cell outputs, execution counts,
and metadata. This is highly useful for clean version control, reducing repo size,
and preventing git diff noise.
"""

import argparse
import json
import os
import sys

# ANSI Colors for terminal output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
BOLD = "\033[1m"
END = "\033[0m"

def log_info(msg):
    print(f"{BLUE}[INFO]{END} {msg}")

def log_success(msg):
    print(f"{GREEN}[SUCCESS]{END} {msg}")

def log_warning(msg):
    print(f"{YELLOW}[WARNING]{END} {msg}")

def log_error(msg):
    print(f"{RED}[ERROR]{END} {msg}", file=sys.stderr)

def strip_notebook(file_path, keep_metadata=False, dry_run=False, output_path=None):
    """Strips execution counts, outputs, and metadata from a notebook."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            original_size = os.path.getsize(file_path)
            data = json.load(f)
    except Exception as e:
        log_error(f"Failed to read/parse {file_path}: {e}")
        return False

    if "cells" not in data:
        log_error(f"Invalid notebook format: {file_path} (missing 'cells' key)")
        return False

    cells_modified = 0
    total_cells = len(data["cells"])
    outputs_removed = 0

    for cell in data["cells"]:
        modified = False
        
        # Strip code cells
        if cell.get("cell_type") == "code":
            if cell.get("execution_count") is not None:
                cell["execution_count"] = None
                modified = True
            
            if cell.get("outputs"):
                outputs_removed += len(cell["outputs"])
                cell["outputs"] = []
                modified = True

        # Strip cell metadata
        if not keep_metadata and "metadata" in cell and cell["metadata"]:
            # Keep collapsed/scrolled state as they affect UI visibility, strip others
            keys_to_keep = {"collapsed", "scrolled"}
            cleaned_metadata = {k: v for k, v in cell["metadata"].items() if k in keys_to_keep}
            if cleaned_metadata != cell["metadata"]:
                cell["metadata"] = cleaned_metadata
                modified = True

        if modified:
            cells_modified += 1

    # Strip notebook-level metadata
    if not keep_metadata and "metadata" in data:
        original_metadata = data["metadata"]
        # Keep essential kernel info if possible, but drop IDE-specific metadata
        essential_keys = {"kernelspec", "language_info"}
        cleaned_metadata = {k: v for k, v in original_metadata.items() if k in essential_keys}
        
        # Clean kernelspec metadata of workspace paths
        if "kernelspec" in cleaned_metadata:
            ks = cleaned_metadata["kernelspec"]
            for k in list(ks.keys()):
                if k not in {"name", "display_name", "language"}:
                    del ks[k]
                    
        if cleaned_metadata != original_metadata:
            data["metadata"] = cleaned_metadata
            cells_modified += 1

    if cells_modified == 0:
        log_info(f"No changes needed for {file_path}")
        return True

    # Prepare output text
    output_text = json.dumps(data, indent=1, ensure_ascii=False) + "\n"
    
    # In JSON serialization, Python standard formats null with no space sometimes,
    # let's normalize formatting to match common formatters.
    
    target = output_path if output_path else file_path
    new_size = len(output_text.encode("utf-8"))
    saved_bytes = original_size - new_size

    if dry_run:
        log_info(f"[DRY-RUN] Would sanitize {file_path}")
        log_info(f"[DRY-RUN] Cells affected: {cells_modified}/{total_cells}, outputs removed: {outputs_removed}")
        if saved_bytes > 0:
            log_info(f"[DRY-RUN] Estimated space saved: {saved_bytes} bytes (from {original_size} to {new_size})")
        return True

    try:
        with open(target, "w", encoding="utf-8") as f:
            f.write(output_text)
        
        log_success(f"Sanitized {file_path} -> {target}")
        log_success(f"  - Cells modified: {cells_modified}/{total_cells}")
        log_success(f"  - Outputs cleared: {outputs_removed}")
        if saved_bytes > 0:
            log_success(f"  - Size reduced by {saved_bytes} bytes ({original_size} -> {new_size})")
        elif saved_bytes < 0:
            log_info(f"  - Formatting updated, size increased by {abs(saved_bytes)} bytes")
        return True
    except Exception as e:
        log_error(f"Failed to write to {target}: {e}")
        return False

def scan_directory(dir_path, keep_metadata=False, dry_run=False):
    """Walks directory recursively to strip all notebooks."""
    log_info(f"Scanning directory: {dir_path}")
    count = 0
    success_count = 0
    
    for root, _, files in os.walk(dir_path):
        for file in files:
            if file.endswith(".ipynb") and not ".ipynb_checkpoints" in root:
                full_path = os.path.join(root, file)
                count += 1
                if strip_notebook(full_path, keep_metadata, dry_run):
                    success_count += 1
                    
    log_success(f"Completed! Checked {count} notebooks. Successfully processed {success_count} notebooks.")

def main():
    parser = argparse.ArgumentParser(
        description="Jupyter Notebook Git-Friendly Sanitizer/Stripper. Clears output cells and metadata."
    )
    parser.add_argument("path", help="Path to a .ipynb file or a directory to scan recursively")
    parser.add_argument("-k", "--keep-metadata", action="store_true", 
                        help="Keep notebook and cell metadata (only clear outputs and execution counts)")
    parser.add_argument("-d", "--dry-run", action="store_true",
                        help="Analyze file(s) and print potential changes without modifying them")
    parser.add_argument("-o", "--output", type=str, default=None,
                        help="Output path for the sanitized notebook (valid only when scanning a single file)")

    args = parser.parse_args()

    # Enable colored logs on Windows if supported
    if sys.platform == "win32":
        os.system("")

    target_path = args.path
    if not os.path.exists(target_path):
        log_error(f"Path does not exist: {target_path}")
        sys.exit(1)

    if os.path.isfile(target_path):
        if not target_path.endswith(".ipynb"):
            log_warning("Target file does not have .ipynb extension, continuing anyway.")
        success = strip_notebook(
            target_path, 
            keep_metadata=args.keep_metadata, 
            dry_run=args.dry_run, 
            output_path=args.output
        )
        sys.exit(0 if success else 1)
    elif os.path.isdir(target_path):
        if args.output:
            log_error("Cannot use --output when target is a directory.")
            sys.exit(1)
        scan_directory(target_path, keep_metadata=args.keep_metadata, dry_run=args.dry_run)

if __name__ == "__main__":
    main()
