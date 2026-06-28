#!/usr/bin/env python3
"""
GitHub Actions Workflow Dependency Visualizer
Parses GitHub Actions workflow YAML files and generates a visual execution pipeline in ASCII
or Mermaid.js format, tracing jobs, triggers, and execution dependencies (via the 'needs' key).
"""

import os
import sys
import re
import argparse

def parse_simple_yaml(yaml_content):
    """
    A lightweight, zero-dependency YAML parser for GitHub Actions workflows.
    Parses indentation-based structures to extract 'name', 'on', and 'jobs'.
    """
    lines = yaml_content.splitlines()
    data = {}
    current_path = []  # List of tuples (indent_level, key)
    
    # Simple regexes to match key-value, list item, or block key
    key_val_pattern = re.compile(r'^(\s*)([\w\-]+)\s*:\s*(.*)$')
    list_item_pattern = re.compile(r'^(\s*)-\s*(.*)$')
    
    for line_idx, line in enumerate(lines):
        # Skip empty lines and comment lines
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue
            
        # Determine indentation level
        indent = len(line) - len(line.lstrip())
        
        # Pop path elements that have greater or equal indentation
        while current_path and current_path[-1][0] >= indent:
            current_path.pop()
            
        key_val_match = key_val_pattern.match(line)
        list_match = list_item_pattern.match(line)
        
        if key_val_match:
            _, key, val = key_val_match.groups()
            val = val.strip()
            
            # Remove inline comments
            if '#' in val:
                val = val.split('#')[0].strip()
                
            # Strip quotes
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
                
            # Build current dictionary reference
            ref = data
            for _, p_key in current_path:
                if p_key not in ref or not isinstance(ref[p_key], dict):
                    ref[p_key] = {}
                ref = ref[p_key]
                
            if val:
                # Leaf key-value
                ref[key] = val
            else:
                # Block key
                ref[key] = {}
                current_path.append((indent, key))
                
        elif list_match:
            _, val = list_match.groups()
            val = val.strip()
            if '#' in val:
                val = val.split('#')[0].strip()
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
                
            # Find parent list in data structure
            if current_path:
                ref = data
                for _, p_key in current_path[:-1]:
                    ref = ref[p_key]
                parent_key = current_path[-1][1]
                
                # Convert dict to list if we find a list item
                if parent_key not in ref or isinstance(ref[parent_key], dict) and not ref[parent_key]:
                    ref[parent_key] = []
                
                if isinstance(ref[parent_key], list):
                    ref[parent_key].append(val)
                elif isinstance(ref[parent_key], dict):
                    # Fallback
                    ref[parent_key][f"item_{len(ref[parent_key])}"] = val

    return data

def extract_workflow_info(yaml_data):
    """Extract workflow name, triggers, and jobs with their needs/runs-on."""
    info = {
        "name": yaml_data.get("name", "Unnamed Workflow"),
        "triggers": [],
        "jobs": {}
    }
    
    # Process triggers ('on' key)
    on_trigger = yaml_data.get("on")
    if isinstance(on_trigger, str):
        info["triggers"].append(on_trigger)
    elif isinstance(on_trigger, list):
        info["triggers"].extend(on_trigger)
    elif isinstance(on_trigger, dict):
        info["triggers"].extend(on_trigger.keys())
        
    # Process jobs
    jobs = yaml_data.get("jobs", {})
    if isinstance(jobs, dict):
        for job_id, job_data in jobs.items():
            if not isinstance(job_data, dict):
                continue
                
            needs = job_data.get("needs", [])
            if isinstance(needs, str):
                needs = [needs]
                
            runs_on = job_data.get("runs-on", "unknown")
            name = job_data.get("name", job_id)
            
            info["jobs"][job_id] = {
                "name": name,
                "needs": needs,
                "runs_on": runs_on
            }
            
    return info

def generate_mermaid(info):
    """Generate Mermaid.js syntax for workflow job dependencies."""
    lines = ["graph TD"]
    
    # Add triggers as top node
    triggers_label = "\\n".join(info["triggers"])
    lines.append(f"    Triggers[\"⚡ Triggers:\\n{triggers_label}\"]")
    
    # Define job nodes
    for job_id, job_meta in info["jobs"].items():
        label = f"{job_meta['name']}\\n({job_meta['runs_on']})"
        lines.append(f"    {job_id}[\"{label}\"]")
        
    # Add trigger connections to independent jobs (jobs that don't need any other job)
    for job_id, job_meta in info["jobs"].items():
        if not job_meta["needs"]:
            lines.append(f"    Triggers --> {job_id}")
            
    # Add job-to-job dependencies
    for job_id, job_meta in info["jobs"].items():
        for needed_job in job_meta["needs"]:
            if needed_job in info["jobs"]:
                lines.append(f"    {needed_job} --> {job_id}")
            else:
                # External dependency not defined in this workflow
                lines.append(f"    {needed_job}[\"{needed_job} (External)\"] --> {job_id}")
                
    return "\n".join(lines)

def generate_ascii_tree(info):
    """Generate a textual ASCII representation of the execution levels."""
    jobs = info["jobs"]
    if not jobs:
        return "No jobs defined in workflow."
        
    # Compute levels (resolve dependencies)
    levels = {}
    resolved = set()
    pending = set(jobs.keys())
    
    # Safeguard against circular dependencies
    iterations = 0
    max_iterations = len(jobs) * 2
    
    while pending and iterations < max_iterations:
        iterations += 1
        for job_id in list(pending):
            job_needs = set(jobs[job_id]["needs"])
            # Resolve if all dependencies are in resolved
            if job_needs.issubset(resolved):
                # Level is 1 + max level of dependencies
                dep_levels = [levels[dep] for dep in job_needs if dep in levels]
                job_level = max(dep_levels) + 1 if dep_levels else 0
                levels[job_id] = job_level
                resolved.add(job_id)
                pending.remove(job_id)
                
    if pending:
        # Loop detected or unresolved dependencies
        for job_id in pending:
            levels[job_id] = 99  # Fallback level
            
    # Group jobs by levels
    grouped_levels = {}
    for job_id, lvl in levels.items():
        grouped_levels.setdefault(lvl, []).append(job_id)
        
    output = []
    output.append(f"Workflow: {info['name']}")
    triggers_str = ", ".join(info['triggers'])
    output.append(f"Triggers: {triggers_str}")
    output.append("=" * 60)
    
    # Print ASCII Flow
    sorted_levels = sorted(grouped_levels.keys())
    for lvl in sorted_levels:
        level_jobs = grouped_levels[lvl]
        lvl_header = f"Level {lvl}" if lvl != 99 else "Unresolved / Circular Level"
        output.append(f"[{lvl_header}]")
        
        for job_id in level_jobs:
            meta = jobs[job_id]
            needs_str = f" (needs: {', '.join(meta['needs'])})" if meta['needs'] else ""
            output.append(f"  └── {job_id} [{meta['name']}] (runs-on: {meta['runs_on']}){needs_str}")
        output.append("")
        
    return "\n".join(output)

def main():
    parser = argparse.ArgumentParser(
        description="GitHub Actions Workflow Dependency Visualizer - Parse yml workflows and draw pipeline hierarchies",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("file", nargs="?", help="Path to a GitHub Actions workflow YAML file (searches .github/workflows if omitted)")
    parser.add_argument("-m", "--mermaid", action="store_true",
                        help="Output in Mermaid.js flowchart syntax instead of ASCII tree")
    parser.add_argument("-o", "--output", help="Path to write the output visualization (prints to stdout by default)")

    args = parser.parse_args()

    target_file = args.file

    # If no file is specified, try to find one in .github/workflows/
    if not target_file:
        workflow_dir = ".github/workflows"
        if os.path.isdir(workflow_dir):
            files = [os.path.join(workflow_dir, f) for f in os.listdir(workflow_dir) if f.endswith((".yml", ".yaml"))]
            if files:
                target_file = files[0]
                print(f"Auto-detected workflow file: {target_file}\n", file=sys.stderr)
            else:
                print(f"Error: No workflow files found in {workflow_dir}.", file=sys.stderr)
                parser.print_help()
                sys.exit(1)
        else:
            print("Error: No file specified and .github/workflows/ directory does not exist.", file=sys.stderr)
            parser.print_help()
            sys.exit(1)

    if not os.path.exists(target_file):
        print(f"Error: File '{target_file}' does not exist.", file=sys.stderr)
        sys.exit(1)

    try:
        with open(target_file, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)

    # Parse and extract
    yaml_data = parse_simple_yaml(content)
    info = extract_workflow_info(yaml_data)
    
    # Generate visualization
    if args.mermaid:
        visualization = generate_mermaid(info)
    else:
        visualization = generate_ascii_tree(info)

    # Output results
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(visualization)
            print(f"Visualization successfully written to {args.output}", file=sys.stderr)
        except Exception as e:
            print(f"Error writing output file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(visualization)

if __name__ == "__main__":
    main()
