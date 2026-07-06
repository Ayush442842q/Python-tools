#!/usr/bin/env python3
"""
dockerfile_size_optimizer - Dockerfile Size & Layer Optimizer

Analyzes Dockerfile instructions to detect layer inflation anti-patterns, missing cache cleanups,
unoptimized package installs, and unnecessary file additions, outputting concrete layer reduction recommendations.

Usage:
    python tools/dockerfile_size_optimizer.py <dockerfile_path> [options]

Examples:
    python tools/dockerfile_size_optimizer.py Dockerfile
    python tools/dockerfile_size_optimizer.py Dockerfile --format json --output dockerfile_audit.json
    python tools/dockerfile_size_optimizer.py Dockerfile --suggest-fix
"""

import argparse
import json
import os
import re
import sys
from typing import List, Dict, Any, Tuple


class DockerfileOptimizer:
    def __init__(self, content: str):
        self.raw_content = content
        self.lines = content.splitlines()
        self.parsed_instructions: List[Tuple[int, str, str]] = []
        self.issues: List[Dict[str, Any]] = []
        self.score = 100
        self._parse()

    def _parse(self):
        """Parse Dockerfile taking multiline backslash line continuations into account."""
        current_inst = ""
        start_line = 0

        for line_idx, line in enumerate(self.lines, 1):
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue

            if not current_inst:
                start_line = line_idx

            if stripped.endswith('\\'):
                current_inst += " " + stripped[:-1].strip()
            else:
                current_inst += " " + stripped
                parts = current_inst.strip().split(maxsplit=1)
                cmd = parts[0].upper()
                args = parts[1] if len(parts) > 1 else ""
                self.parsed_instructions.append((start_line, cmd, args))
                current_inst = ""

    def analyze(self):
        """Run diagnostic checks on parsed instructions."""
        self._check_base_image()
        self._check_consecutive_runs()
        self._check_package_manager_cleanups()
        self._check_pip_no_cache()
        self._check_copy_all()
        self._check_multi_stage()

    def _add_issue(self, severity: str, category: str, line_no: int, message: str, recommendation: str, penalty: int):
        self.issues.append({
            'severity': severity,
            'category': category,
            'line': line_no,
            'message': message,
            'recommendation': recommendation
        })
        self.score = max(0, self.score - penalty)

    def _check_base_image(self):
        for line_no, cmd, args in self.parsed_instructions:
            if cmd == 'FROM':
                image = args.lower().split()[0]
                if image in ('ubuntu:latest', 'debian:latest', 'node:latest', 'python:latest'):
                    self._add_issue(
                        'WARNING', 'Base Image', line_no,
                        f"Unpinned or heavy base image '{image}' detected.",
                        "Use lightweight slim/alpine variants or explicit tag versions (e.g. python:3.11-slim).", 10
                    )
                elif not any(variant in image for variant in ['slim', 'alpine', 'distroless', 'scratch']):
                    self._add_issue(
                        'INFO', 'Base Image', line_no,
                        f"Base image '{image}' may be larger than necessary.",
                        "Consider using alpine or slim image variants if binaries permit.", 5
                    )

    def _check_consecutive_runs(self):
        consecutive_runs = []
        for line_no, cmd, args in self.parsed_instructions:
            if cmd == 'RUN':
                consecutive_runs.append((line_no, args))
            else:
                if len(consecutive_runs) > 2:
                    lines_str = ", ".join(str(l) for l, _ in consecutive_runs)
                    self._add_issue(
                        'WARNING', 'Layer Count', consecutive_runs[0][0],
                        f"Found {len(consecutive_runs)} consecutive RUN instructions at lines ({lines_str}).",
                        "Chain consecutive RUN commands using '&& \\' to avoid creating unnecessary intermediate image layers.", 15
                    )
                consecutive_runs = []

    def _check_package_manager_cleanups(self):
        for line_no, cmd, args in self.parsed_instructions:
            if cmd == 'RUN':
                if 'apt-get install' in args and 'rm -rf /var/lib/apt/lists/*' not in args:
                    self._add_issue(
                        'CRITICAL', 'Cache Inflation', line_no,
                        "apt-get install without cache cleanup detected.",
                        "Append '&& rm -rf /var/lib/apt/lists/*' in the same RUN layer to delete package manager index files.", 20
                    )
                if 'apk add' in args and '--no-cache' not in args and 'rm -rf /var/cache/apk/*' not in args:
                    self._add_issue(
                        'WARNING', 'Cache Inflation', line_no,
                        "apk add without '--no-cache' flag detected.",
                        "Use 'apk add --no-cache' to prevent storing repository indices.", 15
                    )

    def _check_pip_no_cache(self):
        for line_no, cmd, args in self.parsed_instructions:
            if cmd == 'RUN' and 'pip install' in args:
                if '--no-cache-dir' not in args:
                    self._add_issue(
                        'WARNING', 'Cache Inflation', line_no,
                        "pip install without '--no-cache-dir' option detected.",
                        "Add '--no-cache-dir' flag to pip install commands to prevent wheel caching in image layers.", 15
                    )

    def _check_copy_all(self):
        for line_no, cmd, args in self.parsed_instructions:
            if cmd in ('COPY', 'ADD'):
                if args.strip().startswith('. .') or args.strip().startswith('./ .'):
                    self._add_issue(
                        'INFO', 'Build Cache', line_no,
                        f"Instruction '{cmd} . .' copies entire directory into root.",
                        "Ensure a '.dockerignore' file exists to exclude node_modules, .git, venv, and cache folders.", 10
                    )

    def _check_multi_stage(self):
        from_count = sum(1 for _, cmd, _ in self.parsed_instructions if cmd == 'FROM')
        if from_count == 1:
            self._add_issue(
                'INFO', 'Multi-Stage Build', 1,
                "Single-stage build detected.",
                "Consider leveraging multi-stage builds (FROM ... AS builder) to separate build dependencies from runtime artifacts.", 5
            )


def main():
    parser = argparse.ArgumentParser(
        description="Analyzes Dockerfiles for layer inflation, unneeded caches, and image size optimizations."
    )
    parser.add_argument("dockerfile", nargs="?", default="Dockerfile", help="Path to Dockerfile (default: ./Dockerfile)")
    parser.add_argument("-f", "--format", choices=['text', 'json'], default='text', help="Output format (default: text)")
    parser.add_argument("-o", "--output", help="Save audit result to file")

    args = parser.parse_args()

    if not os.path.exists(args.dockerfile):
        print(f"Error: Dockerfile '{args.dockerfile}' not found.", file=sys.stderr)
        sys.exit(1)

    with open(args.dockerfile, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    optimizer = DockerfileOptimizer(content)
    optimizer.analyze()

    result = {
        'dockerfile': args.dockerfile,
        'optimization_score': optimizer.score,
        'total_issues': len(optimizer.issues),
        'issues': optimizer.issues
    }

    if args.format == 'json':
        output_str = json.dumps(result, indent=2)
    else:
        lines = []
        lines.append("=" * 70)
        lines.append(f"DOCKERFILE OPTIMIZATION AUDIT: {args.dockerfile}")
        lines.append("=" * 70)
        lines.append(f"Optimization Score: {optimizer.score}/100")
        lines.append(f"Issues Found: {len(optimizer.issues)}")
        lines.append("-" * 70)

        if not optimizer.issues:
            lines.append("[+] Excellent! No major layer optimization issues detected.")
        else:
            for issue in optimizer.issues:
                sev_color = f"[{issue['severity']}]"
                lines.append(f"{sev_color:<10} Line {issue['line']}: {issue['message']}")
                lines.append(f"           -> Suggestion: {issue['recommendation']}")
                lines.append("")

        lines.append("=" * 70)
        output_str = "\n".join(lines)

    print(output_str)

    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(output_str)
        print(f"[+] Audit report saved to: {args.output}")


if __name__ == "__main__":
    main()
