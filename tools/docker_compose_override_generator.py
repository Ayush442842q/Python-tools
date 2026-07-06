#!/usr/bin/env python3
"""
Docker Compose Override Generator
Generates environment-specific Docker Compose override files (e.g., docker-compose.override.yml,
docker-compose.dev.yml) from base compose files or service definitions without modifying original files.
"""

import os
import sys
import json
import re
import argparse
from typing import Dict, List, Any, Optional

# Console colors for CLI output
COLOR_RESET = "\033[0m"
COLOR_RED = "\033[91m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_CYAN = "\033[96m"
COLOR_BOLD = "\033[1m"


def parse_simple_yaml(text: str) -> Dict[str, Any]:
    """
    Lightweight fallback YAML parser for standard Docker Compose structure
    when PyYAML is not installed. Handles services, ports, environment, volumes.
    """
    try:
        import yaml
        return yaml.safe_load(text) or {}
    except ImportError:
        pass

    # Basic structural line-by-line parser for standard compose files
    result: Dict[str, Any] = {"version": "3.8", "services": {}}
    current_service: Optional[str] = None
    current_section: Optional[str] = None
    in_services = False

    lines = text.splitlines()
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        indent = len(line) - len(line.lstrip())

        if indent == 0:
            if stripped.startswith("version:"):
                result["version"] = stripped.split(":", 1)[1].strip().strip("\"'")
            elif stripped.startswith("services:"):
                in_services = True
            else:
                in_services = False
        elif in_services:
            if indent == 2 and stripped.endswith(":"):
                current_service = stripped[:-1].strip()
                result["services"][current_service] = {}
                current_section = None
            elif indent == 4 and current_service:
                if ":" in stripped:
                    key, val = stripped.split(":", 1)
                    key = key.strip()
                    val = val.strip()
                    if val:
                        result["services"][current_service][key] = val.strip("\"'")
                    else:
                        current_section = key
                        result["services"][current_service][current_section] = []
            elif indent == 6 and current_service and current_section:
                if stripped.startswith("- "):
                    item = stripped[2:].strip().strip("\"'")
                    if not isinstance(result["services"][current_service].get(current_section), list):
                        result["services"][current_service][current_section] = []
                    result["services"][current_service][current_section].append(item)
                elif ":" in stripped:
                    key, val = stripped.split(":", 1)
                    if not isinstance(result["services"][current_service].get(current_section), dict):
                        result["services"][current_service][current_section] = {}
                    result["services"][current_service][current_section][key.strip()] = val.strip().strip("\"'")

    return result


def dump_simple_yaml(data: Dict[str, Any]) -> str:
    """Formats Docker Compose dictionary into a clean YAML string representation."""
    try:
        import yaml
        return yaml.dump(data, sort_keys=False, default_flow_style=False)
    except ImportError:
        pass

    lines = []
    if "version" in data:
        lines.append(f"version: '{data['version']}'")
        lines.append("")

    lines.append("services:")
    services = data.get("services", {})
    for svc_name, svc_data in services.items():
        lines.append(f"  {svc_name}:")
        for key, val in svc_data.items():
            if isinstance(val, list):
                lines.append(f"    {key}:")
                for item in val:
                    lines.append(f"      - {item}")
            elif isinstance(val, dict):
                lines.append(f"    {key}:")
                for k, v in val.items():
                    lines.append(f"      {k}: {v}")
            else:
                lines.append(f"    {key}: {val}")
        lines.append("")

    return "\n".join(lines).strip() + "\n"


def generate_override(
    base_data: Dict[str, Any],
    services_target: List[str],
    env_vars: Dict[str, str],
    port_mappings: List[str],
    volume_mounts: List[str],
    disable_restart: bool = False,
    disable_healthcheck: bool = False,
    command_override: Optional[str] = None
) -> Dict[str, Any]:
    """Generates an override data structure based on CLI options."""
    override_data: Dict[str, Any] = {
        "version": base_data.get("version", "3.8"),
        "services": {}
    }

    all_services = list(base_data.get("services", {}).keys())
    if not all_services and not services_target:
        all_services = ["app"]

    targets = services_target if services_target else all_services

    for svc in targets:
        svc_override: Dict[str, Any] = {}

        if env_vars:
            svc_override["environment"] = [f"{k}={v}" for k, v in env_vars.items()]

        if port_mappings:
            svc_override["ports"] = port_mappings

        if volume_mounts:
            svc_override["volumes"] = volume_mounts

        if disable_restart:
            svc_override["restart"] = "no"

        if disable_healthcheck:
            svc_override["healthcheck"] = {"disable": True}

        if command_override:
            svc_override["command"] = command_override

        if svc_override:
            override_data["services"][svc] = svc_override

    return override_data


def run_demo() -> None:
    """Runs a self-contained demonstration of Docker Compose override generation."""
    print(f"{COLOR_BOLD}{COLOR_CYAN}=== Docker Compose Override Generator Demo ==={COLOR_RESET}\n")
    sample_compose = """version: '3.8'
services:
  web:
    image: nginx:latest
    ports:
      - "80:80"
  api:
    image: node:18
    environment:
      NODE_ENV: production
"""
    print(f"{COLOR_BOLD}Base docker-compose.yml:{COLOR_RESET}")
    print(sample_compose)

    base_data = parse_simple_yaml(sample_compose)
    override = generate_override(
        base_data=base_data,
        services_target=["api"],
        env_vars={"NODE_ENV": "development", "DEBUG": "true", "LOG_LEVEL": "trace"},
        port_mappings=["9229:9229"],
        volume_mounts=["./src:/app/src"],
        disable_restart=True,
        command_override="npm run dev"
    )

    result_yaml = dump_simple_yaml(override)
    print(f"{COLOR_BOLD}{COLOR_GREEN}Generated docker-compose.override.yml:{COLOR_RESET}")
    print(result_yaml)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate Docker Compose override files for dev, debug, and local testing."
    )
    parser.add_argument("-f", "--file", help="Path to base docker-compose.yml file")
    parser.add_argument("-o", "--output", help="Output override file path (default: stdout or docker-compose.override.yml)")
    parser.add_argument("-s", "--services", nargs="+", help="Target specific service names")
    parser.add_argument("-e", "--env", nargs="+", help="Environment variables to set (KEY=VALUE format)")
    parser.add_argument("-p", "--ports", nargs="+", help="Port mappings (e.g. 8080:8080 9229:9229)")
    parser.add_argument("-v", "--volumes", nargs="+", help="Volume mounts (e.g. ./src:/app/src)")
    parser.add_argument("--no-restart", action="store_true", help="Set restart policy to 'no' for targeted services")
    parser.add_argument("--disable-healthcheck", action="store_true", help="Disable healthchecks for targeted services")
    parser.add_argument("--command", help="Override container start command")
    parser.add_argument("--demo", action="store_true", help="Run demonstration mode with sample compose input")

    args = parser.parse_args()

    if args.demo or not args.file:
        if not args.demo and not args.file:
            print(f"{COLOR_YELLOW}No compose file specified. Running demo mode...{COLOR_RESET}\n")
        run_demo()
        return

    if not os.path.exists(args.file):
        print(f"{COLOR_RED}Error: File '{args.file}' does not exist.{COLOR_RESET}")
        sys.exit(1)

    with open(args.file, "r", encoding="utf-8") as f:
        content = f.read()

    base_data = parse_simple_yaml(content)
    env_dict = {}
    if args.env:
        for item in args.env:
            if "=" in item:
                k, v = item.split("=", 1)
                env_dict[k.strip()] = v.strip()

    override_data = generate_override(
        base_data=base_data,
        services_target=args.services or [],
        env_vars=env_dict,
        port_mappings=args.ports or [],
        volume_mounts=args.volumes or [],
        disable_restart=args.no_restart,
        disable_healthcheck=args.disable_healthcheck,
        command_override=args.command
    )

    out_yaml = dump_simple_yaml(override_data)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out_yaml)
        print(f"{COLOR_GREEN}Successfully wrote override file to '{args.output}'.{COLOR_RESET}")
    else:
        print(f"{COLOR_BOLD}{COLOR_GREEN}Generated Override YAML:{COLOR_RESET}")
        print(out_yaml)


if __name__ == "__main__":
    main()
