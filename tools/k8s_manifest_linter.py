#!/usr/bin/env python3
"""
Kubernetes Manifest Linter

Audits Kubernetes YAML or JSON manifests for security issues, missing resource limits,
insecure capabilities, lack of liveness/readiness probes, and other best practices.

Usage:
    python tools/k8s_manifest_linter.py deployment.yaml
    python tools/k8s_manifest_linter.py -d /path/to/manifests/
"""

import os
import sys
import re
import argparse
import json
from typing import Dict, Any, List, Tuple

# Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"

# Try importing yaml, fall back to basic line-by-line parser if unavailable
YAML_AVAILABLE = False
try:
    import yaml
    YAML_AVAILABLE = True
except ImportError:
    pass

class BasicYAMLParser:
    """A very basic YAML parser fallback that extracts simple key-value structures."""
    @staticmethod
    def parse(content: str) -> List[Dict[str, Any]]:
        docs = []
        current_doc = {}
        stack = []  # tracks indent levels and dicts
        
        # Split documents
        raw_docs = content.split("\n---")
        for raw in raw_docs:
            if not raw.strip():
                continue
            doc = {}
            # Extremely simplified YAML parser using indentation levels
            lines = raw.splitlines()
            for line in lines:
                # Skip comments and empty lines
                if not line.strip() or line.strip().startswith("#"):
                    continue
                # Match simple key-value
                match = re.match(r"^(\s*)([\w\-\.]+)\s*:\s*(.*)$", line)
                if match:
                    indent, key, val = match.groups()
                    val = val.strip()
                    # Strip outer quotes if any
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    # Parse basic values
                    if val.lower() == "true":
                        val = True
                    elif val.lower() == "false":
                        val = False
                    elif val.isdigit():
                        val = int(val)
                    
                    # Store at root of doc for flat validation fallback
                    doc[key] = val
            docs.append(doc)
        return docs

def print_colored(text: str, color: str):
    """Print text with ANSI color."""
    print(f"{color}{text}{RESET}")

class K8sLinter:
    def __init__(self):
        self.findings = []
        self.warnings_count = 0
        self.errors_count = 0

    def add_finding(self, severity: str, message: str, path: str = ""):
        self.findings.append({"severity": severity, "message": message, "path": path})
        if severity == "ERROR":
            self.errors_count += 1
        else:
            self.warnings_count += 1

    def audit_container(self, container: Dict[str, Any], parent_path: str):
        c_name = container.get("name", "unnamed")
        c_path = f"{parent_path}.containers[{c_name}]"
        
        # 1. Image checks
        image = container.get("image", "")
        if not image:
            self.add_finding("ERROR", f"Container '{c_name}' does not specify an image", c_path)
        else:
            if ":" not in image or image.endswith(":latest"):
                self.add_finding("WARNING", f"Container '{c_name}' uses the ':latest' image tag or no tag", f"{c_path}.image")

        # 2. SecurityContext checks
        sec_ctx = container.get("securityContext", {})
        if not sec_ctx:
            self.add_finding("WARNING", f"Container '{c_name}' has no securityContext defined", c_path)
        else:
            # privileged mode
            if sec_ctx.get("privileged", False) is True:
                self.add_finding("ERROR", f"Container '{c_name}' is running as privileged", f"{c_path}.securityContext.privileged")
            
            # runAsNonRoot
            if sec_ctx.get("runAsNonRoot") is not True and sec_ctx.get("runAsUser", 1000) == 0:
                self.add_finding("ERROR", f"Container '{c_name}' is configured to run as root user", f"{c_path}.securityContext.runAsNonRoot")
            
            # allowPrivilegeEscalation
            if sec_ctx.get("allowPrivilegeEscalation") is not False:
                self.add_finding("WARNING", f"Container '{c_name}' allows privilege escalation", f"{c_path}.securityContext.allowPrivilegeEscalation")
                
            # readOnlyRootFilesystem
            if sec_ctx.get("readOnlyRootFilesystem") is not True:
                self.add_finding("WARNING", f"Container '{c_name}' root filesystem is not read-only", f"{c_path}.securityContext.readOnlyRootFilesystem")

        # 3. CPU/Memory Limits & Requests
        resources = container.get("resources", {})
        limits = resources.get("limits", {})
        requests = resources.get("requests", {})
        
        if not limits:
            self.add_finding("ERROR", f"Container '{c_name}' has no resource limits defined", f"{c_path}.resources.limits")
        else:
            if "cpu" not in limits:
                self.add_finding("WARNING", f"Container '{c_name}' has no CPU limit defined", f"{c_path}.resources.limits")
            if "memory" not in limits:
                self.add_finding("ERROR", f"Container '{c_name}' has no memory limit defined", f"{c_path}.resources.limits")

        if not requests:
            self.add_finding("WARNING", f"Container '{c_name}' has no resource requests defined", f"{c_path}.resources.requests")
            
        # 4. Probes
        if parent_path.endswith("spec.template.spec") or parent_path.endswith("spec"):
            # Only check probes for long-running workloads (Deployment, StatefulSet, DaemonSet)
            if "livenessProbe" not in container:
                self.add_finding("WARNING", f"Container '{c_name}' has no livenessProbe defined", c_path)
            if "readinessProbe" not in container:
                self.add_finding("WARNING", f"Container '{c_name}' has no readinessProbe defined", c_path)

    def audit_pod_spec(self, spec: Dict[str, Any], path: str):
        if not isinstance(spec, dict):
            return
            
        # Host namespaces checks
        if spec.get("hostNetwork", False) is True:
            self.add_finding("ERROR", "Pod shares host network namespace", f"{path}.hostNetwork")
        if spec.get("hostPID", False) is True:
            self.add_finding("ERROR", "Pod shares host PID namespace", f"{path}.hostPID")
        if spec.get("hostIPC", False) is True:
            self.add_finding("ERROR", "Pod shares host IPC namespace", f"{path}.hostIPC")

        # Check containers
        containers = spec.get("containers", [])
        if not containers:
            self.add_finding("ERROR", "No containers defined in pod spec", path)
        else:
            for c in containers:
                self.audit_container(c, path)

        # Check init containers
        init_containers = spec.get("initContainers", [])
        for c in init_containers:
            self.audit_container(c, f"{path}.initContainers")

    def audit_manifest(self, doc: Dict[str, Any], filename: str):
        if not doc:
            return
            
        kind = doc.get("kind", "")
        api_version = doc.get("apiVersion", "")
        metadata = doc.get("metadata", {})
        name = metadata.get("name", "unnamed")
        
        if not kind:
            self.add_finding("WARNING", "Missing 'kind' field in manifest", "kind")
        if not api_version:
            self.add_finding("WARNING", "Missing 'apiVersion' field in manifest", "apiVersion")

        # Namespace check
        if kind and kind not in ("Namespace", "ClusterRole", "ClusterRoleBinding", "CustomResourceDefinition", "PersistentVolume"):
            if not metadata.get("namespace"):
                self.add_finding("WARNING", f"{kind} '{name}' does not specify a namespace explicitly", "metadata.namespace")

        # Route audit based on workload kind
        if kind in ("Deployment", "StatefulSet", "DaemonSet", "Job", "ReplicaSet"):
            spec = doc.get("spec", {})
            template = spec.get("template", {})
            pod_spec = template.get("spec", {})
            self.audit_pod_spec(pod_spec, "spec.template.spec")
        elif kind == "Pod":
            self.audit_pod_spec(doc.get("spec", {}), "spec")
        elif kind == "CronJob":
            spec = doc.get("spec", {})
            job_template = spec.get("jobTemplate", {})
            job_spec = job_template.get("spec", {})
            pod_spec = job_spec.get("template", {}).get("spec", {})
            self.audit_pod_spec(pod_spec, "spec.jobTemplate.spec.template.spec")
        elif kind == "Service":
            spec = doc.get("spec", {})
            ports = spec.get("ports", [])
            for i, p in enumerate(ports):
                target_port = p.get("targetPort")
                port = p.get("port")
                if not target_port:
                    self.add_finding("WARNING", f"Service port {port} has no targetPort specified", f"spec.ports[{i}]")

    def print_report(self, filename: str):
        print_colored(f"\n{'='*60}\nLinting File: {filename}\n{'='*60}", CYAN)
        
        if not self.findings:
            print_colored("[+] No issues found! Clean manifest.", GREEN)
            return

        for f in self.findings:
            sev = f["severity"]
            color = RED if sev == "ERROR" else YELLOW
            path_str = f" [Path: {f['path']}]" if f["path"] else ""
            print(f"[{color}{sev}{RESET}] {f['message']}{path_str}")

        print_colored(f"\nSummary: {self.errors_count} Error(s), {self.warnings_count} Warning(s)", RED if self.errors_count > 0 else (YELLOW if self.warnings_count > 0 else GREEN))

def lint_file(filepath: str, linter: K8sLinter):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print_colored(f"[-] Failed to read {filepath}: {e}", RED)
        return

    # Determine if JSON or YAML
    is_json = False
    try:
        data = json.loads(content)
        is_json = True
        docs = [data] if isinstance(data, dict) else data
    except json.JSONDecodeError:
        pass

    if not is_json:
        if YAML_AVAILABLE:
            try:
                # Load all documents
                docs = list(yaml.safe_load_all(content))
            except Exception as e:
                print_colored(f"[-] YAML Parsing Error in {filepath}: {e}", RED)
                return
        else:
            # Fallback parser
            docs = BasicYAMLParser.parse(content)
            print_colored("[!] Warning: PyYAML is not installed. Using fallback basic parser.", YELLOW)

    for doc in docs:
        if isinstance(doc, dict):
            linter.audit_manifest(doc, filepath)

def main():
    parser = argparse.ArgumentParser(description="Lint Kubernetes manifests for security and best practices.")
    parser.add_argument("path", nargs="?", help="Path to manifest file or directory")
    parser.add_argument("-d", "--dir", help="Directory containing manifests to lint")
    
    args = parser.parse_args()
    
    target_path = args.path or args.dir
    if not target_path:
        parser.print_help()
        sys.exit(1)

    linter = K8sLinter()

    if os.path.isdir(target_path):
        for root, _, files in os.walk(target_path):
            for file in files:
                if file.endswith((".yaml", ".yml", ".json")):
                    lint_file(os.path.join(root, file), linter)
        linter.print_report(f"Directory: {target_path}")
    elif os.path.isfile(target_path):
        lint_file(target_path, linter)
        linter.print_report(target_path)
    else:
        print_colored(f"[-] Path not found: {target_path}", RED)
        sys.exit(1)

if __name__ == "__main__":
    main()
