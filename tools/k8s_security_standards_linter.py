#!/usr/bin/env python3
"""
Kubernetes Pod Security Standards (PSS) Linter
---------------------------------------------
Parses Kubernetes manifests (YAML or JSON) and audits them against
the official Kubernetes Pod Security Standards:
1. Privileged (Unrestricted)
2. Baseline (Prevents known privilege escalations)
3. Restricted (Highly hardened)

Includes a standalone YAML-to-dict parser to ensure zero external dependencies.

Author: Antigravity
License: MIT
"""

import os
import sys
import re
import json
import argparse
from typing import Dict, List, Any, Tuple, Optional

# --- Standalone Minimal YAML Parser ---
def parse_yaml(content: str) -> List[Dict[str, Any]]:
    """
    Parses a basic YAML document string into Python dicts/lists.
    Handles standard Kubernetes manifests (mappings, nested items, and lists of mappings).
    Supports multiple documents separated by '---'.
    """
    documents = []
    lines = content.splitlines()
    
    current_doc_lines = []
    for line in lines:
        if line.strip() == "---":
            if current_doc_lines:
                doc = _parse_single_yaml_doc(current_doc_lines)
                if doc:
                    documents.append(doc)
                current_doc_lines = []
        else:
            current_doc_lines.append(line)
            
    if current_doc_lines:
        doc = _parse_single_yaml_doc(current_doc_lines)
        if doc:
            documents.append(doc)
            
    return documents

def _parse_single_yaml_doc(lines: List[str]) -> Optional[Dict[str, Any]]:
    """Helper to parse a single YAML document into a dictionary based on indentation."""
    # Clean up lines (remove comments, ignore blank lines)
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # Strip trailing comments if not inside string
        if " #" in line:
            line = line.split(" #")[0]
        cleaned_lines.append(line)

    if not cleaned_lines:
        return None

    # Stack to track indentation levels and parent elements
    # Each entry: (indent_level, key/index, parent_container)
    root = {}
    container_stack: List[Tuple[int, Any, Any]] = [(-1, None, root)]

    for line in cleaned_lines:
        # Calculate indentation
        indent = len(line) - len(line.lstrip())
        stripped = line.strip()
        
        # Pop stack until we find the parent container level
        while container_stack and container_stack[-1][0] >= indent:
            container_stack.pop()

        parent_container = container_stack[-1][2] if container_stack else root

        # Check if line is a list item
        if stripped.startswith("-"):
            val_part = stripped[1:].strip()
            # If item is empty, or has a key value pair
            if not val_part:
                # Nested list item (starts a new dict/list)
                new_item = {}
                if isinstance(parent_container, list):
                    parent_container.append(new_item)
                container_stack.append((indent, len(parent_container) - 1, new_item))
            elif ":" in val_part:
                # Inline key-value in list item, e.g., - name: nginx
                key, val = val_part.split(":", 1)
                key = key.strip()
                val = _parse_val(val.strip())
                new_item = {key: val}
                if isinstance(parent_container, list):
                    parent_container.append(new_item)
                else:
                    # In case of weird structure
                    parent_container[key] = val
                container_stack.append((indent + 2, key, new_item))
            else:
                # Primitive list item, e.g., - NET_ADMIN
                val = _parse_val(val_part)
                if isinstance(parent_container, list):
                    parent_container.append(val)
                elif isinstance(parent_container, dict):
                    # We might have defined a key but no list was initialized
                    # Find last key
                    if container_stack:
                        last_key = container_stack[-1][1]
                        if last_key in parent_container and parent_container[last_key] is None:
                            parent_container[last_key] = [val]
                        elif last_key in parent_container and isinstance(parent_container[last_key], list):
                            parent_container[last_key].append(val)
        else:
            # Key-value pair
            if ":" not in stripped:
                continue
            key, val_str = stripped.split(":", 1)
            key = key.strip()
            val_str = val_str.strip()
            
            if not val_str:
                # Nested mapping or list starts here
                # We don't know if it's a list or dict yet. Default to dict.
                # If next line is a list, we'll convert it.
                new_container = {}
                if isinstance(parent_container, list):
                    parent_container.append({key: new_container})
                else:
                    parent_container[key] = new_container
                container_stack.append((indent, key, new_container))
            else:
                # Primitive value
                val = _parse_val(val_str)
                if isinstance(parent_container, list):
                    # In case of inline nested list item
                    parent_container.append({key: val})
                else:
                    # Adjust if parent container was initialized as dict but needs to be list
                    # (Usually happens if the parent key expected a list and we see '-' on next line)
                    parent_container[key] = val
                container_stack.append((indent, key, parent_container))

    # Convert mapping keys that hold lists where appropriate
    # (Since we default nested structures to dict, we clean them if they contain list items)
    _normalize_lists(root)
    return root

def _parse_val(val_str: str) -> Any:
    """Parse string value into integer, boolean, null, or clean string."""
    if not val_str:
        return None
    val_upper = val_str.upper()
    if val_upper in ("TRUE", "YES", "ON"):
        return True
    if val_upper in ("FALSE", "NO", "OFF"):
        return False
    if val_upper in ("NULL", "~"):
        return None
    
    # Try parsing int or float
    try:
        if "." in val_str:
            return float(val_str)
        return int(val_str)
    except ValueError:
        pass
        
    # Strip quotes if present
    if (val_str.startswith('"') and val_str.endswith('"')) or (val_str.startswith("'") and val_str.endswith("'")):
        return val_str[1:-1]
    return val_str

def _normalize_lists(node: Any):
    """Recursively traverses parsed tree to clean up lists represented as dicts with integer keys."""
    if isinstance(node, dict):
        # If dict has integer keys starting from 0, it might be a list
        # In this simple parser, we verify children
        for k, v in list(node.items()):
            _normalize_lists(v)
            # If children keys are lists of values, convert them
            if isinstance(v, dict) and all(isinstance(x, int) for x in v.keys()):
                node[k] = [v[i] for i in sorted(v.keys())]
            elif isinstance(v, dict) and len(v) == 1 and "" in v:
                # Nested list empty placeholder
                node[k] = []
    elif isinstance(node, list):
        for item in node:
            _normalize_lists(item)

# --- Kubernetes Security Auditing Engine ---
class K8sSecurityAuditor:
    def __init__(self):
        self.findings = []

    def log_finding(self, filepath: str, resource: str, name: str, severity: str, profile: str, check: str, remediation: str):
        self.findings.append({
            "file": filepath,
            "resource": resource,
            "name": name,
            "severity": severity,
            "profile": profile,
            "check": check,
            "remediation": remediation
        })

    def audit_pod_spec(self, pod_spec: Dict[str, Any], filepath: str, resource_kind: str, resource_name: str):
        if not isinstance(pod_spec, dict):
            return

        # 1. Host namespaces (Baseline)
        if pod_spec.get("hostNetwork") is True:
            self.log_finding(
                filepath, resource_kind, resource_name, "High", "Baseline",
                "hostNetwork is enabled",
                "Set spec.hostNetwork to false to prevent sharing node network namespace."
            )
        if pod_spec.get("hostPID") is True:
            self.log_finding(
                filepath, resource_kind, resource_name, "High", "Baseline",
                "hostPID is enabled",
                "Set spec.hostPID to false to isolate container process namespace from host."
            )
        if pod_spec.get("hostIPC") is True:
            self.log_finding(
                filepath, resource_kind, resource_name, "High", "Baseline",
                "hostIPC is enabled",
                "Set spec.hostIPC to false to isolate inter-process communication namespaces."
            )

        # 2. Volumes: check hostPath volumes (Baseline)
        volumes = pod_spec.get("volumes", [])
        if isinstance(volumes, list):
            for vol in volumes:
                if isinstance(vol, dict) and "hostPath" in vol:
                    self.log_finding(
                        filepath, resource_kind, resource_name, "Medium", "Baseline",
                        f"hostPath volume '{vol.get('name')}' is mounted",
                        "Avoid hostPath volumes; use local, PVC, or configMaps instead to protect node integrity."
                    )

        # 3. Containers security contexts
        containers = pod_spec.get("containers", [])
        init_containers = pod_spec.get("initContainers", [])
        all_containers = []
        if isinstance(containers, list):
            all_containers.extend(containers)
        if isinstance(init_containers, list):
            all_containers.extend(init_containers)

        for container in all_containers:
            if not isinstance(container, dict):
                continue
                
            c_name = container.get("name", "unknown")
            sec_ctx = container.get("securityContext", {})
            if not isinstance(sec_ctx, dict):
                sec_ctx = {}

            # Baseline checks
            # Privileged containers
            if sec_ctx.get("privileged") is True:
                self.log_finding(
                    filepath, resource_kind, resource_name, "High", "Baseline",
                    f"Container '{c_name}' runs as privileged",
                    f"Set securityContext.privileged to false for container '{c_name}'."
                )

            # Capabilities added
            caps = sec_ctx.get("capabilities", {})
            if isinstance(caps, dict):
                added_caps = caps.get("add", [])
                if isinstance(added_caps, list) and added_caps:
                    for cap in added_caps:
                        if cap in ("ALL", "SYS_ADMIN", "NET_ADMIN", "SYS_RAWIO"):
                            self.log_finding(
                                filepath, resource_kind, resource_name, "High", "Baseline",
                                f"Container '{c_name}' adds sensitive capability '{cap}'",
                                f"Remove '{cap}' from securityContext.capabilities.add in container '{c_name}'."
                            )

            # Restricted checks
            # AllowPrivilegeEscalation
            if sec_ctx.get("allowPrivilegeEscalation") is not False:
                self.log_finding(
                    filepath, resource_kind, resource_name, "Medium", "Restricted",
                    f"Container '{c_name}' allows privilege escalation",
                    f"Set securityContext.allowPrivilegeEscalation to false in container '{c_name}'."
                )

            # Read-only Root Filesystem
            if sec_ctx.get("readOnlyRootFilesystem") is not True:
                self.log_finding(
                    filepath, resource_kind, resource_name, "Low", "Restricted",
                    f"Container '{c_name}' lacks a read-only root filesystem",
                    f"Set securityContext.readOnlyRootFilesystem to true in container '{c_name}'."
                )

            # Run as Non-Root / User Checks
            run_as_non_root = sec_ctx.get("runAsNonRoot")
            pod_sec_ctx = pod_spec.get("securityContext", {})
            if not isinstance(pod_sec_ctx, dict):
                pod_sec_ctx = {}
                
            pod_non_root = pod_sec_ctx.get("runAsNonRoot")

            if run_as_non_root is not True and pod_non_root is not True:
                self.log_finding(
                    filepath, resource_kind, resource_name, "Medium", "Restricted",
                    f"Container '{c_name}' is not set to runAsNonRoot",
                    f"Set securityContext.runAsNonRoot to true in either pod-level or container-level securityContext."
                )

            # Check capabilities dropped
            if isinstance(caps, dict):
                dropped_caps = caps.get("drop", [])
                if not isinstance(dropped_caps, list) or "ALL" not in dropped_caps:
                    self.log_finding(
                        filepath, resource_kind, resource_name, "Low", "Restricted",
                        f"Container '{c_name}' does not drop ALL capabilities",
                        f"Add 'ALL' to securityContext.capabilities.drop in container '{c_name}'."
                    )

    def audit_resource(self, doc: Dict[str, Any], filepath: str):
        if not isinstance(doc, dict):
            return

        kind = doc.get("kind")
        metadata = doc.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        name = metadata.get("name", "unnamed")

        if not kind:
            return

        # Pod directly
        if kind == "Pod":
            self.audit_pod_spec(doc.get("spec", {}), filepath, kind, name)

        # Resources containing Pod templates
        elif kind in ("Deployment", "StatefulSet", "DaemonSet", "Job", "ReplicaSet"):
            spec = doc.get("spec", {})
            if isinstance(spec, dict):
                template = spec.get("template", {})
                if isinstance(template, dict):
                    self.audit_pod_spec(template.get("spec", {}), filepath, kind, name)

        # CronJobs have a double spec nesting: spec.jobTemplate.spec.template.spec
        elif kind == "CronJob":
            spec = doc.get("spec", {})
            if isinstance(spec, dict):
                job_tmpl = spec.get("jobTemplate", {})
                if isinstance(job_tmpl, dict):
                    job_spec = job_tmpl.get("spec", {})
                    if isinstance(job_spec, dict):
                        tmpl = job_spec.get("template", {})
                        if isinstance(tmpl, dict):
                            self.audit_pod_spec(tmpl.get("spec", {}), filepath, kind, name)

def main():
    parser = argparse.ArgumentParser(description="Kubernetes Pod Security Standards (PSS) Linter - Audit K8s configurations.")
    parser.add_argument("path", help="Path to a directory containing manifests or a single YAML/JSON file")
    parser.add_argument("--json", action="store_true", help="Output audit findings in JSON format")
    args = parser.parse_args()

    target_path = os.path.abspath(args.path)
    if not os.path.exists(target_path):
        print(f"Error: Path '{target_path}' does not exist.", file=sys.stderr)
        sys.exit(1)

    auditor = K8sSecurityAuditor()
    files_scanned = 0

    def process_file(filepath: str):
        nonlocal files_scanned
        _, ext = os.path.splitext(filepath.lower())
        if ext not in (".yaml", ".yml", ".json"):
            return
            
        files_scanned += 1
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()

            documents = []
            if ext == ".json":
                try:
                    data = json.loads(content)
                    if isinstance(data, list):
                        documents.extend(data)
                    else:
                        documents.append(data)
                except Exception as e:
                    print(f"Error parsing JSON {filepath}: {e}", file=sys.stderr)
            else:
                documents = parse_yaml(content)

            for doc in documents:
                auditor.audit_resource(doc, filepath)
        except Exception as e:
            print(f"Error reading {filepath}: {e}", file=sys.stderr)

    if os.path.isdir(target_path):
        for root, _, files in os.walk(target_path):
            for file in files:
                process_file(os.path.join(root, file))
    else:
        process_file(target_path)

    if args.json:
        print(json.dumps({
            "files_scanned": files_scanned,
            "findings_count": len(auditor.findings),
            "findings": auditor.findings
        }, indent=2))
        return

    # Visual Output
    print("=" * 105)
    print(f"KUBERNETES POD SECURITY STANDARDS AUDIT")
    print(f"Scanned {files_scanned} files. Found {len(auditor.findings)} security issues.")
    print("=" * 105)

    if auditor.findings:
        # Group by severity
        by_severity = {"High": [], "Medium": [], "Low": []}
        for f in auditor.findings:
            sev = f["severity"]
            if sev in by_severity:
                by_severity[sev].append(f)
            else:
                by_severity["Low"].append(f)

        for severity in ("High", "Medium", "Low"):
            findings = by_severity[severity]
            if not findings:
                continue

            color = "\033[91m" if severity == "High" else ("\033[93m" if severity == "Medium" else "\033[94m")
            reset = "\033[0m"
            
            print(f"\n{color}{severity.upper()} SEVERITY ISSUES:{reset}")
            print("-" * 105)
            for f in findings:
                rel_file = os.path.relpath(f["file"])
                print(f"File:      {rel_file}")
                print(f"Resource:  {f['resource']} ({f['name']})")
                print(f"Standard:  {f['profile']} Profile Violation")
                print(f"Finding:   \033[1m{f['check']}\033[0m")
                print(f"Fix:       {f['remediation']}")
                print("-" * 105)
    else:
        print("\n\033[92m[SUCCESS] No Pod Security Standards issues found! Your manifests comply with the Restricted profile.\033[0m")

if __name__ == "__main__":
    main()
