# Python Tools Collection

This repository contains various useful Python tools and utilities.

## Current Tools

### File Organizer (`file_organizer.py`)

A utility to automatically organize files in a directory by type (images, documents, videos, etc.).

#### Features:
- Organizes files by category (images, documents, videos, audio, archives, code, executables, fonts)
- Creates category folders automatically
- Dry-run mode to preview changes
- Verbose output for detailed logging
- Handles files without extensions
- Skips already organized files
- Preserves original filenames
- Handles filename conflicts by adding numbers

#### Usage:
```bash
# Basic usage
python file_organizer.py /path/to/directory

# Dry run to see what would happen
python file_organizer.py /path/to/directory --dry-run

# Verbose output
python file_organizer.py /path/to/directory --verbose

# Combine options
python file_organizer.py ~/Downloads --dry-run --verbose
```

#### Supported File Types:
- **Images**: jpg, jpeg, png, gif, bmp, tiff, webp, svg, ico, raw
- **Documents**: pdf, doc, docx, txt, rtf, odt, pages, tex, md, csv, xls, xlsx, ppt, pptx, ods, odp
- **Videos**: mp4, avi, mkv, mov, wmv, flv, webm, m4v, mpg, mpeg, 3gp, ts, vob
- **Audio**: mp3, wav, flac, aac, ogg, wma, m4a, aiff, alac, mid, midi
- **Archives**: zip, rar, 7z, tar, gz, bz2, xz, iso, dmg, cab, apk
- **Code**: py, js, html, css, java, cpp, c, h, cs, php, rb, go, rs, swift, kt, scala, pl, sh, bash, zsh, fish, sql, xml, json, yaml, yml, toml, ini, cfg, conf
- **Executables**: exe, msi, deb, rpm, dmg, app, bin, run
- **Fonts**: ttf, otf, woff, woff2, eot, pfb, pfm
### Markdown Image Inliner (`markdown_image_inliner.py`)
A utility to scan Markdown files and inline local/remote images as Base64 Data URIs to make files fully self-contained.

#### Usage:
```bash
python tools/markdown_image_inliner.py /path/to/markdown_or_dir --remote --backup
```

### Code Refactoring Candidate Finder (`code_refactoring_candidate_finder.py`)
Analyzes Python codebases recursively using AST parsing to compute cyclomatic complexity, nesting depth, and document/TODO coverage to rank files needing refactoring.

#### Usage:
```bash
python tools/code_refactoring_candidate_finder.py /path/to/project --limit 10
```

### CLI Financial Projection Calculator (`cli_financial_projection_calculator.py`)
Simulates long-term compound growth with custom event schedules, inflation adjustments, tax rates, and outputs a visual ASCII/Unicode chart.

#### Usage:
```bash
python tools/cli_financial_projection_calculator.py --start 10000 --contrib 500 --years 20 --details
```

### Git Developer Pace Analyzer (`git_developer_pace_analyzer.py`)
Analyzes commit pacing, active hours, weekend workloads, path entropy, and burnout risk metrics, rendering a daily velocity timeline.

#### Usage:
```bash
python tools/git_developer_pace_analyzer.py --days 90
```

### DNS Zone File Generator (`dns_zone_file_generator.py`)
Generates standardized BIND zone files from a simple JSON configuration, with automatic serial incrementing and record validation.

#### Usage:
```bash
python tools/dns_zone_file_generator.py config.json -o example.com.zone --increment
```

### NPM Dependency Auditor (`npm_dependency_auditor.py`)
Audits `package.json` and `package-lock.json` files for dependency trees, outdated packages, license compliance, and security advisories with zero third-party dependencies.

#### Usage:
```bash
python tools/npm_dependency_auditor.py /path/to/project --online --json
```

### Web Bundle Size Auditor (`web_bundle_size_auditor.py`)
Scans production build folders (e.g., `dist/`, `build/`) to analyze file sizes (raw and gzipped), evaluate minification, check for source map exposures, and flag assets that exceed configurable size budgets.

#### Usage:
```bash
python tools/web_bundle_size_auditor.py /path/to/dist --js-budget 200 --css-budget 50
```

### Kubernetes Pod Security Standards Linter (`k8s_security_standards_linter.py`)
Parses Kubernetes manifests (YAML or JSON) recursively and audits them against official Kubernetes Pod Security Standards (Privileged, Baseline, Restricted).

#### Usage:
```bash
python tools/k8s_security_standards_linter.py /path/to/manifests/ --json
```

### Git Ownership Entropy & Fragmentation Analyzer (`git_ownership_entropy_analyzer.py`)
Calculates the ownership entropy (Shannon Entropy) and contribution inequality (Gini Coefficient) on a per-file basis using Git history to identify code hotspots with fragmented developer ownership.

#### Usage:
```bash
python tools/git_ownership_entropy_analyzer.py /path/to/repo --limit 10
```

### GraphQL Query Complexity & Depth Analyzer (`graphql_query_analyzer.py`)
Statically analyzes GraphQL query files (.graphql, .txt, or JSON payloads) to measure selection nesting depth, field counts, fragment spreads, and overall execution complexity to prevent Denial of Service (DoS) attacks.

#### Usage:
```bash
python tools/graphql_query_analyzer.py query.graphql --max-depth 8 --max-complexity 300.0
```

### Tailwind CSS Conflict Detector & Optimizer (`tailwind_conflict_detector.py`)
Statically audits HTML, JSX, TSX, JS, TS, and Vue files for conflicting Tailwind CSS utility classes (e.g. `p-4 p-5`, `text-red-500 text-blue-500`, `flex block`) within the same element and groups them by responsive breakpoints or state modifiers.

#### Usage:
```bash
python tools/tailwind_conflict_detector.py /path/to/project/src --verbose
```

### HTML DOM Depth & Payload Size Analyzer (`html_dom_depth_analyzer.py`)
Statically parses HTML files to measure DOM complexity, maximum nesting depth, total node count, and payload size (inline script/style bytes and SVG paths), providing warnings and performance recommendations.

#### Usage:
```bash
python tools/html_dom_depth_analyzer.py index.html --threshold 20 --verbose
```

### Python Exception Shadowing & Dead Catch Detector (`python_dead_catch_detector.py`)
Statically parses Python source code using AST to detect exception handling errors, including shadowed/dead catch blocks (catching a subclass exception after a parent class), duplicate catch blocks, and overly broad exceptions.

#### Usage:
```bash
python tools/python_dead_catch_detector.py /path/to/project
```

### SQL Schema Circular Dependency Detector (`sql_circular_dependency_detector.py`)
Parses SQL DDL schema files to extract table relationships and FOREIGN KEY constraints, builds a directed dependency graph, identifies circular reference cycles, and outputs cycle paths and Mermaid diagrams.

#### Usage:
```bash
python tools/sql_circular_dependency_detector.py schema.sql --mermaid
```

### Markdown API Sync & Specification Auditor (`markdown_api_sync_checker.py`)
Cross-references Python web server route configurations (FastAPI, Flask) with Markdown API documentation, identifying missing documentation, obsolete docs, or HTTP method mismatches.

#### Usage:
```bash
python tools/markdown_api_sync_checker.py src/ docs/
```

### GitHub Actions Workflow Matrix & Cache Optimizer (`github_workflow_matrix_optimizer.py`)
Statically analyzes GitHub Actions workflow files to optimize matrix setups, configure dependency caching, set job timeouts, and audit security permissions.

#### Usage:
```bash
python tools/github_workflow_matrix_optimizer.py .github/workflows/
```

### JSON Schema to TypeScript Zod Schema Converter (`json_schema_to_zod.py`)
Converts standard JSON Schema definitions into TypeScript Zod validation schemas.

#### Usage:
```bash
python tools/json_schema_to_zod.py schema.json -o schema.ts
```

### HTTP Connection Pool & Keep-Alive Latency Analyzer (`http_connection_pool_analyzer.py`)
Measures and compares request latency differences between connection pooling (HTTP Keep-Alive reuse) and fresh TCP/TLS connection creation for each request.

#### Usage:
```bash
python tools/http_connection_pool_analyzer.py https://httpbin.org/status/200 --count 10
```

### Python PEP 8 Naming Style Auditor (`python_pep8_naming_auditor.py`)
Statically inspects Python files using AST parsing to verify that class, function, method, variable, parameter, and constant names strictly comply with PEP 8 styling conventions.

#### Usage:
```bash
python tools/python_pep8_naming_auditor.py /path/to/python/file.py
```

### SQL Schema Normalization & Quality Auditor (`sql_normalization_auditor.py`)
Audits database SQL DDL schemas for relational normalization violations (1NF/2NF/3NF) and database schema design anti-patterns.

#### Usage:
```bash
python tools/sql_normalization_auditor.py schema.sql
```

#### Requirements:
- Python 3.6+

#### License:
MIT License - feel free to use, modify, and distribute.

#### Contributing:
Feel free to submit issues, fork the repository, and send pull requests!