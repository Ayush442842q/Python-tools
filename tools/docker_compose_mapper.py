#!/usr/bin/env python3
"""
Docker Compose Network Mapper & Port Collision Auditor
Parses docker-compose.yml files, checks for duplicate external port exposures,
validates container dependencies, and maps service networks to a Mermaid.js diagram.

Usage:
    python tools/docker_compose_mapper.py .
    python tools/docker_compose_mapper.py /path/to/project --mermaid
"""

import argparse
import os
import re
import sys
from typing import Any, Dict, List, Set, Tuple

# ANSI Escape Codes for colorized output
COLOR_HEADER = "\033[95m"
COLOR_BLUE = "\033[94m"
COLOR_CYAN = "\033[96m"
COLOR_GREEN = "\033[92m"
COLOR_WARNING = "\033[93m"
COLOR_FAIL = "\033[91m"
COLOR_END = "\033[0m"
COLOR_BOLD = "\033[1m"


def print_colored(text: str, color: str):
    """Print text with ANSI color codes if output is a TTY."""
    if sys.stdout.isatty():
        print(f"{color}{text}{COLOR_END}")
    else:
        print(text)


def parse_yaml_fallback(content: str) -> Dict[str, Any]:
    """
    A lightweight, indentation-based YAML parser fallback to avoid PyYAML dependency.
    Extracts version, services, networks, and key service blocks (ports, depends_on, networks).
    """
    lines = content.splitlines()
    data: Dict[str, Any] = {"services": {}}
    
    current_service = None
    current_key = None
    indent_level = 0
    
    service_block_indent = -1
    property_indent = -1
    
    for line in lines:
        # Strip comments and whitespace
        strip_line = line.strip()
        if not strip_line or strip_line.startswith("#"):
            continue
            
        # Determine indentation
        indent = len(line) - len(line.lstrip())
        
        # Detect top-level services block
        if strip_line.startswith("services:"):
            service_block_indent = indent
            continue
            
        if service_block_indent != -1:
            # If we exit the services block, reset
            if indent <= service_block_indent and indent != 0:
                service_block_indent = -1
                current_service = None
                continue
                
            # Inside services block
            if indent > service_block_indent:
                # Detect a service name declaration (e.g., "web:")
                match = re.match(r"^([a-zA-Z0-9_-]+)\s*:$", strip_line)
                if match and (indent == service_block_indent + 2 or service_block_indent == 0):
                    current_service = match.group(1)
                    data["services"][current_service] = {
                        "ports": [],
                        "depends_on": [],
                        "networks": []
                    }
                    property_indent = -1
                    continue
                    
                if current_service:
                    # Inside a service declaration
                    # Check for lists (ports, depends_on, networks)
                    list_match = re.match(r"^-\s*(.+)$", strip_line)
                    if list_match:
                        val = list_match.group(1).strip().strip('"\'')
                        if current_key == "ports":
                            data["services"][current_service]["ports"].append(val)
                        elif current_key == "depends_on":
                            data["services"][current_service]["depends_on"].append(val)
                        elif current_key == "networks":
                            data["services"][current_service]["networks"].append(val)
                        continue
                        
                    # Key-value or list header declaration (e.g., "ports:")
                    key_match = re.match(r"^([a-zA-Z0-9_-]+)\s*:(.*)$", strip_line)
                    if key_match:
                        key = key_match.group(1)
                        val = key_match.group(2).strip().strip('"\'')
                        current_key = key
                        
                        # Handle inline lists if any
                        if val:
                            if key == "depends_on":
                                # depends_on: [db, redis]
                                inline_list = re.findall(r"[a-zA-Z0-9_-]+", val)
                                data["services"][current_service]["depends_on"].extend(inline_list)
                            elif key == "networks":
                                inline_list = re.findall(r"[a-zA-Z0-9_-]+", val)
                                data["services"][current_service]["networks"].extend(inline_list)
    return data


def load_docker_compose(file_path: str) -> Tuple[bool, Dict[str, Any], str]:
    """Loads and parses a docker-compose.yml file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        return False, {}, f"Read error: {e}"
        
    try:
        import yaml
        try:
            data = yaml.safe_load(content)
            if not isinstance(data, dict):
                data = {}
            if "services" not in data or not isinstance(data["services"], dict):
                data["services"] = {}
            return True, data, "PyYAML"
        except Exception:
            pass
    except ImportError:
        pass
        
    # Use fallback parser
    data = parse_yaml_fallback(content)
    return True, data, "Fallback Parser"


def scan_directory(path: str) -> List[Tuple[str, Dict[str, Any]]]:
    """Finds and parses all docker-compose files in the path."""
    compose_files = []
    compose_names = {"docker-compose.yml", "docker-compose.yaml"}
    
    if os.path.isfile(path):
        if os.path.basename(path).lower() in compose_names:
            success, data, parser = load_docker_compose(path)
            if success:
                compose_files.append((path, data))
        return compose_files
        
    for root, _, files in os.walk(path):
        for file in files:
            if file.lower() in compose_names:
                full_path = os.path.join(root, file)
                success, data, parser = load_docker_compose(full_path)
                if success and data.get("services"):
                    compose_files.append((full_path, data))
                    
    return compose_files


def audit_ports(compose_files: List[Tuple[str, Dict[str, Any]]]) -> Dict[str, List[Tuple[str, str]]]:
    """Detects duplicate host port bindings across all services."""
    # host_port -> list of (file_path, service_name)
    port_bindings: Dict[str, List[Tuple[str, str]]] = {}
    
    for file_path, data in compose_files:
        rel_path = os.path.relpath(file_path)
        services = data.get("services", {})
        for svc_name, svc_data in services.items():
            if not isinstance(svc_data, dict):
                continue
            ports = svc_data.get("ports", [])
            if not isinstance(ports, list):
                continue
                
            for port in ports:
                port_str = str(port)
                # Handle formats: "80:80", "127.0.0.1:80:80", "80" (no host binding), "8080-8085:80-8085"
                # We focus on the host port part
                parts = port_str.split(":")
                host_part = None
                if len(parts) == 3: # ip:host_port:container_port
                    host_part = parts[1]
                elif len(parts) == 2: # host_port:container_port
                    host_part = parts[0]
                    
                if host_part:
                    # Handle range: e.g. "8080-8082"
                    if "-" in host_part:
                        try:
                            start, end = map(int, host_part.split("-"))
                            for p in range(start, end + 1):
                                port_bindings.setdefault(str(p), []).append((rel_path, svc_name))
                        except ValueError:
                            port_bindings.setdefault(host_part, []).append((rel_path, svc_name))
                    else:
                        port_bindings.setdefault(host_part, []).append((rel_path, svc_name))
                        
    # Filter only duplicates
    collisions = {port: mappings for port, mappings in port_bindings.items() if len(mappings) > 1}
    return collisions


def generate_mermaid(compose_files: List[Tuple[str, Dict[str, Any]]]) -> str:
    """Generates a Mermaid.js diagram representing service relationships and networks."""
    lines = ["graph TD"]
    
    # Track defined networks and services to group them
    # service -> set of networks
    service_networks: Dict[str, Set[str]] = {}
    all_networks: Set[str] = set()
    dependencies: List[Tuple[str, str]] = []
    
    for file_path, data in compose_files:
        dir_name = os.path.basename(os.path.dirname(file_path)) or "root"
        services = data.get("services", {})
        
        for svc_name, svc_data in services.items():
            if not isinstance(svc_data, dict):
                continue
            unique_svc_id = f"{dir_name}_{svc_name}".replace("-", "_").replace(".", "_")
            
            # Label node with port info if available
            ports = svc_data.get("ports", [])
            port_label = ""
            if ports:
                port_label = f"<br/>Ports: {', '.join(map(str, ports))}"
            lines.append(f'    {unique_svc_id}["{svc_name}{port_label}"]')
            
            # Map depends_on
            depends = svc_data.get("depends_on", [])
            # depends_on can be a list or a dict
            if isinstance(depends, dict):
                depends = list(depends.keys())
            elif not isinstance(depends, list):
                depends = []
                
            for dep in depends:
                dep_id = f"{dir_name}_{dep}".replace("-", "_").replace(".", "_")
                dependencies.append((unique_svc_id, dep_id))
                
            # Map networks
            nets = svc_data.get("networks", [])
            if isinstance(nets, list):
                for net in nets:
                    net_name = str(net)
                    service_networks.setdefault(unique_svc_id, set()).add(net_name)
                    all_networks.add(net_name)
            elif isinstance(nets, dict):
                for net in nets.keys():
                    net_name = str(net)
                    service_networks.setdefault(unique_svc_id, set()).add(net_name)
                    all_networks.add(net_name)
                    
    # Generate network subgraphs/relationships
    for net in all_networks:
        lines.append(f'\n    subgraph network_{net} ["Network: {net}"]')
        for svc_id, nets in service_networks.items():
            if net in nets:
                lines.append(f"        {svc_id}")
        lines.append("    end")
        
    # Render dependency arrows
    lines.append("\n    %% Dependencies")
    for src, dest in dependencies:
        lines.append(f"    {src} -->|depends on| {dest}")
        
    return "\n".join(lines)


def display_report(compose_files: List[Tuple[str, Dict[str, Any]]], collisions: Dict[str, List[Tuple[str, str]]]):
    """Prints a structured text report of the services and port mappings."""
    print_colored(f"\n{COLOR_BOLD}=== Docker Compose Audit Report ==={COLOR_END}", COLOR_HEADER)
    print(f"Scanned {len(compose_files)} docker-compose file(s).\n")
    
    for file_path, data in compose_files:
        rel_path = os.path.relpath(file_path)
        print_colored(f"File: {rel_path}", COLOR_BOLD + COLOR_BLUE)
        services = data.get("services", {})
        if not services:
            print("  No services defined.")
            continue
            
        for svc_name, svc_data in services.items():
            print(f"  Service: {svc_name}")
            if not isinstance(svc_data, dict):
                continue
            ports = svc_data.get("ports", [])
            if ports:
                print(f"    Ports:     {', '.join(map(str, ports))}")
            depends = svc_data.get("depends_on", [])
            if depends:
                if isinstance(depends, dict):
                    depends = list(depends.keys())
                print(f"    Depends:   {', '.join(depends)}")
            nets = svc_data.get("networks", [])
            if nets:
                if isinstance(nets, dict):
                    nets = list(nets.keys())
                print(f"    Networks:  {', '.join(nets)}")
        print()
        
    # Report Collisions
    print_colored(f"{COLOR_BOLD}=== Port Collision Analysis ==={COLOR_END}", COLOR_HEADER)
    if not collisions:
        print_colored("[+] No host port conflicts detected.", COLOR_GREEN)
    else:
        print_colored(f"[!] Warning: Detected {len(collisions)} host port conflicts!", COLOR_WARNING)
        for port, mappings in collisions.items():
            print_colored(f"  Conflict on Host Port {port}:", COLOR_FAIL)
            for file_path, svc in mappings:
                print(f"    - Service '{svc}' in {file_path}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Docker Compose Network Mapper & Port Collision Auditor.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("path", nargs="?", default=".", help="Directory or file path to scan (default: current directory)")
    parser.add_argument("--mermaid", "-m", action="store_true", help="Generate and output Mermaid.js diagram definition")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.path):
        print_colored(f"[!] Path does not exist: {args.path}", COLOR_FAIL)
        sys.exit(1)
        
    compose_files = scan_directory(args.path)
    
    if not compose_files:
        print_colored("[*] No docker-compose.yml or docker-compose.yaml files found.", COLOR_WARNING)
        sys.exit(0)
        
    if args.mermaid:
        mermaid_code = generate_mermaid(compose_files)
        print(mermaid_code)
    else:
        collisions = audit_ports(compose_files)
        display_report(compose_files, collisions)


if __name__ == "__main__":
    main()
