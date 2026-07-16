#!/usr/bin/env python3
"""
GitLab CI/CD Pipeline Config Linter

A standalone utility to lint local `.gitlab-ci.yml` files.
Includes:
1. A lightweight, native YAML parser to read structural config.
2. Syntax and validation checks (jobs vs. stages, allowed keywords).
3. Circular dependency detection in job execution graphs (using the `needs` attribute).
4. Text-based DAG flow representation of pipeline jobs.

Usage:
    python gitlab_ci_linter.py [path_to_gitlab_ci_yml]
"""

import sys
import os
import argparse
import re

# List of standard top-level keywords in GitLab CI
RESERVED_KEYS = {
    'stages', 'variables', 'before_script', 'after_script', 
    'include', 'cache', 'default', 'workflow', 'image', 'services'
}

DEFAULT_STAGES = ['.pre', 'build', 'test', 'deploy', '.post']

def parse_basic_yaml(text):
    """
    Simplistic line-by-line YAML parser to convert .gitlab-ci.yml structure
    into a nested Python dictionary. Handles simple key-value, lists, and indentation.
    """
    lines = text.splitlines()
    root = {}
    stack = [(-1, root)]
    
    current_key = None
    
    for line_num, raw_line in enumerate(lines, 1):
        # Ignore comments and empty lines
        clean_line = raw_line.split('#', 1)[0]
        if not clean_line.strip():
            continue
            
        indent = len(raw_line) - len(raw_line.lstrip())
        stripped = clean_line.strip()
        
        # Pop stack until we find the parent container level
        while stack and stack[-1][0] >= indent:
            stack.pop()
            
        if not stack:
            # Fallback to root
            stack = [(-1, root)]
            
        parent = stack[-1][1]
        
        # Case 1: List item "- item"
        if stripped.startswith('-'):
            val = stripped[1:].strip()
            # If value contains quotes, strip them
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
                
            if isinstance(parent, list):
                parent.append(val)
            elif isinstance(parent, dict):
                # If parent doesn't have a list for current key yet
                if current_key and current_key in parent:
                    if not isinstance(parent[current_key], list):
                        parent[current_key] = [parent[current_key]]
                    parent[current_key].append(val)
                else:
                    # Anonymous list under dictionary (uncommon)
                    pass
            continue

        # Case 2: Key-value pair "key: value" or block "key:"
        if ':' in stripped:
            key, val = stripped.split(':', 1)
            key = key.strip()
            val = val.strip()
            
            # Clean key/val quotes
            if (key.startswith('"') and key.endswith('"')) or (key.startswith("'") and key.endswith("'")):
                key = key[1:-1]
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
                
            current_key = key
            
            if val:
                # Leaf key-value pair
                parent[key] = val
            else:
                # Key maps to a nested container (dict or list)
                # Peek at the next non-empty, non-comment line to check if list or dict
                is_list = False
                for next_line in lines[line_num:]:
                    next_strip = next_line.split('#', 1)[0].strip()
                    if next_strip:
                        if next_strip.startswith('-'):
                            is_list = True
                        break
                        
                container = [] if is_list else {}
                parent[key] = container
                stack.append((indent, container))
            continue
            
    return root

def find_cycles(graph):
    """Detects cycles in a directed graph of job dependencies using DFS."""
    visited = {}  # 0: unvisited, 1: visiting, 2: visited
    cycle = []
    
    def dfs(node):
        visited[node] = 1
        for neighbor in graph.get(node, []):
            if visited.get(neighbor, 0) == 1:
                cycle.append(neighbor)
                cycle.append(node)
                return True
            if visited.get(neighbor, 0) == 0:
                if dfs(neighbor):
                    cycle.append(node)
                    return True
        visited[node] = 2
        return False
        
    for node in graph:
        if visited.get(node, 0) == 0:
            if dfs(node):
                return list(reversed(cycle))
    return None

def lint_pipeline(config):
    """Validates the structural dictionary configuration of GitLab CI."""
    errors = []
    warnings = []
    
    # 1. Determine active stages
    stages = config.get('stages', [])
    if not stages:
        stages = DEFAULT_STAGES
        warnings.append("No 'stages' key defined. Defaulting to standard stages: " + ", ".join(DEFAULT_STAGES))
    elif not isinstance(stages, list):
        errors.append("'stages' configuration must be a list.")
        stages = DEFAULT_STAGES
        
    # 2. Identify jobs and validate keywords
    jobs = {}
    dependency_graph = {}
    
    for key, value in config.items():
        if key in RESERVED_KEYS:
            continue
        # Non-reserved key is treated as a job if it maps to a dictionary
        if isinstance(value, dict):
            jobs[key] = value
        else:
            warnings.append(f"Ignored top-level key '{key}' because it does not map to a job block.")

    print(f"Detected {len(jobs)} pipeline jobs and {len(stages)} pipeline stages.\n")

    # 3. Validate each job
    for job_name, job_data in jobs.items():
        # Validate stage mapping
        job_stage = job_data.get('stage', 'test')  # default stage is test
        if job_stage not in stages:
            errors.append(f"Job '{job_name}' references undefined stage '{job_stage}'.")

        # Validate scripts defined
        if 'script' not in job_data and 'before_script' not in job_data and 'trigger' not in job_data:
            warnings.append(f"Job '{job_name}' has no execution 'script' or downstream trigger defined.")

        # Extract and validate needs/dependencies
        needs = job_data.get('needs', [])
        # 'needs' can be a list of strings or list of dicts. We clean it to strings.
        cleaned_needs = []
        if isinstance(needs, list):
            for n in needs:
                if isinstance(n, dict):
                    if 'job' in n:
                        cleaned_needs.append(n['job'])
                elif isinstance(n, str):
                    cleaned_needs.append(n)
        elif isinstance(needs, str):
            cleaned_needs = [needs]
            
        dependency_graph[job_name] = cleaned_needs
        
        # Verify needed jobs exist
        for need in cleaned_needs:
            if need not in jobs:
                errors.append(f"Job '{job_name}' needs undefined job reference '{need}'.")

    # 4. Check for cycles in dependencies
    cycle = find_cycles(dependency_graph)
    if cycle:
        cycle_str = " -> ".join(cycle)
        errors.append(f"Circular dependency cycle detected in pipeline execution path: {cycle_str}")

    # 5. Visual Pipeline DAG Overview
    if not errors:
        print("PIPELINE DAG FLOW VISUALIZATION")
        print("=" * 65)
        # Group jobs by stage
        jobs_by_stage = {s: [] for s in stages}
        for job_name, job_data in jobs.items():
            s = job_data.get('stage', 'test')
            if s in jobs_by_stage:
                jobs_by_stage[s].append(job_name)
                
        for s in stages:
            stage_jobs = jobs_by_stage[s]
            if stage_jobs:
                print(f"Stage: [{s}]")
                for j in stage_jobs:
                    dep = dependency_graph.get(j, [])
                    dep_str = f" (needs: {', '.join(dep)})" if dep else ""
                    try:
                        print(f"  └── {j}{dep_str}")
                    except UnicodeEncodeError:
                        print(f"  \\-- {j}{dep_str}")
        print("=" * 65)

    return errors, warnings

def main():
    parser = argparse.ArgumentParser(
        description="Lint and analyze GitLab CI pipeline configurations (.gitlab-ci.yml) natively.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "yaml_file",
        nargs="?",
        default=".gitlab-ci.yml",
        help="Path to the .gitlab-ci.yml file (default: .gitlab-ci.yml)"
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.yaml_file):
        print(f"Error: File '{args.yaml_file}' not found.", file=sys.stderr)
        return 1
        
    try:
        with open(args.yaml_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading file '{args.yaml_file}': {e}", file=sys.stderr)
        return 1

    print(f"Linting Config: {args.yaml_file}")
    config = parse_basic_yaml(content)
    
    errors, warnings = lint_pipeline(config)
    
    if warnings:
        print("\033[93mWarnings:\033[0m")
        for w in warnings:
            print(f"  [!] {w}")
        print()
            
    if errors:
        print("\033[91mLinting Failed! Errors detected:\033[0m")
        for err in errors:
            print(f"  [-] {err}")
        return 1
    else:
        try:
            print("\033[92m[✓] GitLab CI config structure is valid and cycle-free.\033[0m")
        except UnicodeEncodeError:
            print("\033[92m[ok] GitLab CI config structure is valid and cycle-free.\033[0m")
        return 0

if __name__ == "__main__":
    sys.exit(main())
