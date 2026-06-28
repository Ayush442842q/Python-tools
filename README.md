# Python Tools Collection

A comprehensive collection of 300+ useful Python tools and utilities for various tasks including file organization, data processing, web scraping, automation, development, security, and productivity.

Each tool is a standalone Python script located in the `tools/` directory and can be run independently.

## Features

- **Standalone Tools**: Each tool is a single, executable Python script
- **No Installation Required**: Just Python 3.6+ (some tools may need additional packages)
- **Cross-Platform**: Works on Windows, macOS, and Linux
- **Well Documented**: Each tool includes help text and usage examples
- **MIT License**: Free to use, modify, and distribute

## Tools List

### File System & Utilities
- **Backup Tool** (`tools/backup_tool.py`) - Create timestamped backups of files and directories
- **Batch File Renamer** (`tools/batch_file_renamer.py`) - Rename multiple files using patterns and rules
- **Batch Renamer** (`tools/batch_renamer.py`) - Alternative batch renaming utility
- **Data Cleaner** (`tools/data_cleaner.py`) - Clean and preprocess messy datasets
- **Directory Compare** (`tools/dir_compare.py`) - Compare two directories recursively for differences
- **Disk Analyzer** (`tools/disk_analyzer.py`) - Analyze disk space usage and find large files
- **Disk Space Analyzer** (`tools/disk_space_analyzer.py`) - Detailed disk usage analysis tool
- **Duplicate File Finder** (`tools/duplicate_file_finder.py`) - Find and remove duplicate files
- **Duplicate Finder** (`tools/duplicate_finder.py`) - Alternative duplicate file detection utility
- **File Backup Automation** (`tools/file_backup_automation.py`) - Automated file backup system
- **File Compressor** (`tools/file_compressor.py`) - Compress and decompress files and directories using ZIP and TAR formats
- **File Converter** (`tools/file_converter.py`) - Convert files between different formats
- **File Organizer** (`tools/file_organizer.py`) - Automatically organize files in a directory by type
- **File Splitter** (`tools/file_splitter.py`) - Split large files into smaller parts
- **File Watcher** (`tools/file_watcher.py`) - Monitor directory changes in real-time
- **Firewall Config Tool** (`tools/firewall_config_tool.py`) - Manage firewall rules and configurations
- **Image Processor** (`tools/image_processor.py`) - Process and manipulate images in batches
- **Invoice Automation** (`tools/invoice_automation.py`) - Automate invoice creation and sending
- **Job Listing Scraper** (`tools/job_listing_scraper.py`) - Scrape job listings from job boards
- **JSON Transformer** (`tools/json_transformer.py`) - Transform and manipulate JSON data structures
- **Log Analyzer** (`tools/log_analyzer.py`) - Analyze and parse log files for insights
- **Log Parser** (`tools/log_parser.py`) - Parse various log formats and extract structured data
- **Log Rotate Tool** (`tools/log_rotate_tool.py`) - Manage, rotate, compress, and prune log files with size and retention limits
- **Morse Code Converter** (`tools/morse_converter.py`) - Encode and decode Morse code with audio feedback
- **Network Scanner** (`tools/network_scanner.py`) - Scan network for connected devices and open ports
- **News Scraper** (`tools/news_scraper.py`) - Scrape news articles from multiple news websites
- **Password Generator** (`tools/password_generator.py`) - Generate secure passwords
- **Password Manager** (`tools/password_manager.py`) - Secure password generation and management tool
- **PDF Toolkit** (`tools/pdf_toolkit.py`) - Extract text, merge, split, and manipulate PDF files
- **Pomodoro Timer** (`tools/pomodoro_timer.py`) - Terminal-based productivity timer with custom work/break intervals, live progress bar, sound alerts, and session logging
- **Price Comparison Scraper** (`tools/price_comparison_scraper.py`) - Compare product prices across e-commerce websites
- **Process Manager** (`tools/process_manager.py`) - Manage and monitor system processes
- **QR Code Generator** (`tools/qr_code_generator.py`) - Generate QR codes for various use cases
- **Real Estate Scraper** (`tools/real_estate_scraper.py`) - Scrape real estate listings from property websites
- **Recipe Scraper** (`tools/recipe_scraper.py`) - Scrape recipes from cooking websites
- **Report Generator** (`tools/report_generator.py`) - Generate automated reports from various data sources
- **Social Media Analyzer** (`tools/social_media_analyzer.py`) - Analyze social media engagement and metrics
- **Social Media Poster** (`tools/social_media_poster.py`) - Automatically post to social media platforms
- **Social Media Scraper** (`tools/social_media_scraper.py`) - Scrape public data from social media platforms
- **SSL Certificate Checker** (`tools/ssl_certificate_checker.py`) - Check SSL certificate validity and expiration
- **Stock Data Scraper** (`tools/stock_data_scraper.py`) - Scrape stock market data and financial information
- **System Benchmark** (`tools/system_benchmark.py`) - Test CPU, Memory, and Disk I/O performance
- **System Info & Diagnostics Reporter** (`tools/system_info_reporter.py`) - Gather hardware, OS, network, and Python environment diagnostics
- **System Load Generator** (`tools/system_load_generator.py`) - Simulate CPU and Memory load for system testing and monitoring validation
- **System Monitor** (`tools/system_monitor.py`) - Monitor system resources and performance
- **Task Scheduler** (`tools/task_scheduler.py`) - Schedule and automate repetitive tasks
- **Text Expander** (`tools/text_expander.py`) - Text expansion tool for frequently used phrases
- **Travel Info Scraper** (`tools/travel_info_scraper.py`) - Scrape travel information and hotel prices
- **Tree Printer** (`tools/tree_printer.py`) - Print directory structures in tree format
- **URL Shortener** (`tools/url_shortener.py`) - Create and manage shortened URLs
- **Weather Scraper** (`tools/weather_scraper.py`) - Scrape weather data from weather websites
- **Web Form Filler** (`tools/web_form_filler.py`) - Automate filling and submitting web forms
- **Web Scraper Basic** (`tools/web_scraper_basic.py`) - Basic web scraper for extracting data from websites
- **Website Monitor** (`tools/website_monitor.py`) - Monitor website uptime and performance
- **Log Grepper** (`tools/log_grepper.py`) - Advanced search and filter utility for plain and compressed logs (.gz/.zip)
- **Archive File Searcher** (`tools/archive_searcher.py`) - Search for text patterns or regular expressions inside ZIP and TAR archives without extracting them
- **Directory Syncer** (`tools/directory_syncer.py`) - One-way directory synchronization utility comparing sizes, times, and MD5 checksums
- **Log Merger** (`tools/log_merger.py`) - Chronologically merge multiple log files with different formats using low-memory merge sort
- **Text File Sorter** (`tools/text_file_sorter.py`) - Sort lines in text files using alphabetical, numerical, length, or field‑based rules
- **Terminal Markdown Viewer** (`tools/terminal_markdown_viewer.py`) - Renders Markdown files beautifully in the terminal with color, code highlighting, lists, and blockquotes
- **Indented Text to Mindmap & Diagram Generator** (`tools/text_to_mindmap.py`) - Converts structured indented outlines or Markdown lists into Unicode trees, Mermaid mindmaps, or interactive HTML files
- **Markdown Wiki & Backlink Analyzer** (`tools/markdown_wiki_manager.py`) - Scan a folder of markdown files, resolve wiki and standard links, map tags, trace backlinks, and output Mermaid.js graphs
- **Terminal Kanban Board** (`tools/cli_kanban.py`) - A CLI Kanban board manager with visual column layouts in the terminal using Unicode characters
- **Duplicate File Linker** (`tools/duplicate_file_linker.py`) - Scan for duplicate files recursively and consolidate them using hard links, symlinks, or deletion to save disk space
- **CLI Directory Size Browser** (`tools/cli_dir_size_browser.py`) - Interactive command-line directory size browser and disk space cleanup utility with size sorting and deletion capability
- **Directory Template Generator** (`tools/directory_template_generator.py`) - Generate directories and files from a text outline or tree diagram
- **Flashcard CLI Study Tool** (`tools/flashcard_study_tool.py`) - An interactive CLI flashcard system using spaced repetition (Leitner boxes) with progress persistence and Anki export
- **Directory Merkle Tree Generator** (`tools/directory_merkle_tree.py`) - Cryptographic directory tree hasher, integrity checker, and fast difference locator

### Development Tools
- **Time Tool** (`tools/time.py`) - Displays current local time in ISO format
- **File Hash Tool** (`tools/file_hash.py`) - Computes SHA256 hash of a file
- **JSON Validate Tool** (`tools/json_validate.py`) - Validates JSON file and pretty‑prints if valid
- **JSON Diff Tool** (`tools/json_diff_tool.py`) - Compare two JSON files recursively and display key-by-key changes
- **Ping Tool** (`tools/ping_tool.py`) - Simple wrapper around system ping
- **Banner Tool** (`tools/banner.py`) - Prints text with optional ANSI color
- **Base64 Image Encoder/Decoder** (`tools/base64_image_tool.py`) - Encode images to Base64/Data URIs and decode Base64 strings back to image files
- **Binary File Analyzer** (`tools/binary_analyzer.py`) - Generate hex dumps, calculate entropy, and extract printable ASCII strings
- **API Tester** (`tools/api_tester.py`) - Test and validate REST APIs
- **API Request Snippet Generator** (`tools/api_code_generator.py`) - Generate copy-pasteable HTTP client request snippets for curl, Python, JavaScript, and Go
- **ASCII Art Generator** (`tools/ascii_art_generator.py`) - Create terminal text banners in various font styles
- **Text Case Converter** (`tools/case_converter.py`) - Convert text casing between common programmer formats
- **Interactive CLI Cheat Sheet** (`tools/cli_cheat_sheet.py`) - Local interactive search tool and guide for command lines (Git, Docker, Bash, etc.)
- **Code Comment Stripper** (`tools/comment_stripper.py`) - Strip comments, docstrings, and blank lines from source code files
- **Code Line Counter** (`tools/code_line_counter.py`) - Count lines of code, comments, and blank lines grouped by language in a directory
- **Code Quality Checker** (`tools/code_quality_checker.py`) - Analyze code quality and suggest improvements
- **Code Spell Checker** (`tools/code_spell_checker.py`) - Scan source code comments and string literals for typos using split identifier checks
- **Codec Utility** (`tools/codec_utility.py`) - Encode and decode data using Base64, URL, Hex, Binary, and HTML formats
- **Color Converter & Contrast Checker** (`tools/color_converter.py`) - Convert colors (HEX, RGB, HSL, CMYK) and check WCAG contrast compliance
- **Cron Expression Parser** (`tools/cron_parser.py`) - Parse cron schedule expressions and list next run times
- **Environment Variable Manager** (`tools/env_manager.py`) - Check consistency and sync environment files (.env vs .env.example)
- **File Diff Tool** (`tools/file_diff_tool.py`) - Compare files line by line with colored console outputs or interactive HTML diff reports
- **File Patch Applicator & Diff Generator** (`tools/file_patcher.py`) - Generate unified diff patches and apply them to base files with dry-run and backup options
- **File Regex Replacer** (`tools/file_regex_replacer.py`) - Search and replace text in multiple files using regular expressions
- **Git Commit Message Linter** (`tools/git_commit_linter.py`) - Lint git commit messages for Conventional Commits compliance
- **Git Repository Summarizer** (`tools/git_repo_summarizer.py`) - Generate activity and contribution reports for a local Git repository
- **Git Branch Cleaner** (`tools/git_branch_cleaner.py`) - Clean up local Git branches that have been merged or whose upstream tracking branches have been deleted
- **Git Large File Finder & History Analyzer** (`tools/git_large_file_finder.py`) - Scan repository history to find large files, calculate cumulative bloat, and get instructions to prune them
- **Git Churn Analyzer** (`tools/git_churn_analyzer.py`) - Measure and rank code churn of files in a Git repository to identify development hotspots
- **HTML to Markdown Converter** (`tools/html_to_markdown.py`) - Convert HTML documents or snippets into clean, structured Markdown
- **HTML Formatter & Minifier** (`tools/html_formatter.py`) - Format, beautify, or minify HTML documents using standard parser
- **Markdown Link Checker** (`tools/markdown_link_checker.py`) - Scan markdown files for broken local and external links
- **Markdown Linter** (`tools/markdown_linter.py`) - Scan and validate Markdown file formatting and structure
- **Markdown to HTML Converter** (`tools/markdown_to_html.py`) - Compiles Markdown documents into styled, responsive standalone HTML pages
- **Markdown Table of Contents Generator** (`tools/markdown_toc_generator.py`) - Generate tables of contents with anchor links for Markdown files
- **Regex Tester & Matcher** (`tools/regex_tester.py`) - Test regex patterns against text or files with colored highlights
- **Regex Data Extractor** (`tools/regex_extractor.py`) - Extract pattern matches (emails, URLs, IPs, dates, UUIDs) and custom regexes from files or directories
- **Terminal Slideshow Player** (`tools/terminal_slideshow.py`) - Render Markdown files as interactive console slides with colors and navigation controls
- **Python Code Complexity Analyzer** (`tools/code_complexity_analyzer.py`) - Compute cyclomatic complexity and structural metrics of Python source files using AST parsing
- **Python Performance Profiler** (`tools/python_performance_profiler.py`) - Profile CPU execution time and memory allocations of a Python script using standard libraries
- **Terminal Chart Generator** (`tools/terminal_chart_generator.py`) - Generate visual charts in the terminal using Unicode blocks and ANSI colors
- **Markdown Checklist Tracker** (`tools/markdown_todo_tracker.py`) - Scan a Markdown file for task checklists, compute completion statistics, and print a progress report grouped by section
- **UUID/GUID Generator** (`tools/uuid_generator.py`) - Generate secure and standardized UUIDs (v1, v3, v4, v5) with various formatting options
- **Log Colorizer & Highlight Tool** (`tools/log_colorizer.py`) - Colorize log levels and highlight custom regex patterns in stdin or log files
- **Developer's Unit Converter** (`tools/unit_converter.py`) - Convert digital storage sizes, network speeds, base systems, and epoch timestamps
- **.gitignore Generator** (`tools/gitignore_generator.py`) - Generate standard .gitignore files from gitignore.io or offline templates
- **Safe Math Evaluator** (`tools/safe_math_evaluator.py`) - Safely evaluate mathematical expressions using AST analysis
- **CSS Formatter & Minifier** (`tools/css_formatter.py`) - Clean, format, sort properties, or compress and minify CSS files
- **Code TODO Scanner** (`tools/code_todo_scanner.py`) - Scan directories recursively for developer task comments (TODO, FIXME, HACK, BUG, REVIEW) across multiple programming languages
- **SVG Vector Graphic Optimizer** (`tools/svg_optimizer.py`) - Clean editor metadata, strip empty groups, and reduce path coordinate precision to compress SVG files
- **Markdown Table Formatter** (`tools/markdown_table_formatter.py`) - Format and align columns in Markdown tables for neat text alignment
- **Unicode & Character Inspector** (`tools/unicode_inspector.py`) - Inspect strings or files for Unicode code points, character names, UTF-8 byte sequences, and category summaries
- **Lorem Ipsum Generator** (`tools/lorem_ipsum_generator.py`) - Generate customizable placeholder text (words, sentences, paragraphs, lists, and HTML) for development and design
- **Timezone Converter** (`tools/timezone_converter.py`) - Convert dates/times across timezones, list world clocks, and compare time offsets
- **PyPI Version Checker** (`tools/pypi_version_checker.py`) - Check listed packages against PyPI for newer versions and update availability
- **Code Duplicate Detector** (`tools/code_duplicate_detector.py`) - Find duplicate or copied code blocks recursively using sliding window hash comparison
- **Binary Hex Diff** (`tools/binary_diff.py`) - Compare two binary files side-by-side with colored hex differences
- **ANSI Color Explorer** (`tools/ansi_color_explorer.py`) - Visualizer for terminal color support (16-color, 256-color, TrueColor/24-bit) and ANSI escape code generation
- **Text-to-ASCII Flowchart Generator** (`tools/ascii_flowchart_generator.py`) - Render flowchart diagrams in console using ASCII/Unicode box-drawing characters
- **Code Snippet Manager** (`tools/code_snippet_manager.py`) - Command-line database utility to save, search, view with syntax highlighting, and copy code snippets
- **Python Import Visualizer** (`tools/python_import_visualizer.py`) - Map internal Python import dependency networks and display module hierarchies or generate Mermaid diagrams
- **Huffman Text Compressor** (`tools/text_compressor_huffman.py`) - Standalone Huffman Coding text compressor and decompressor that generates a custom binary .huff format
- **Python Import Cleaner & Sorter** (`tools/python_import_cleaner.py`) - Parses Python files using AST to safely detect unused imports and generate organized, PEP-8 compliant import blocks
- **LLM Context Packer** (`tools/llm_context_packer.py`) - Recursively packages a local codebase/directory into a single, clean Markdown context file for LLM prompts
- **Git Changelog & Release Notes Generator** (`tools/git_changelog_generator.py`) - Parses Git history and groups commits by conventional types into a structured Markdown changelog
- **Markdown HTML Slide Generator** (`tools/markdown_slide_generator.py`) - Compiles a Markdown file separated by horizontal rules into a standalone, interactive HTML slideshow
- **Git Commit Heatmap & Stats** (`tools/git_commit_heatmap.py`) - Generate a GitHub-style ASCII/Unicode contribution calendar heatmap for commits, with streaks and detailed activity stats
- **JSON to Python Dataclass & Pydantic Model Generator** (`tools/json_to_dataclasses.py`) - Converts JSON structures into nested Python dataclasses or Pydantic models with type inference
- **Python Codebase Documentation Server** (`tools/python_doc_server.py`) - Statically parses Python modules using AST, generates a modern responsive dark-themed documentation website, and hosts it on a local HTTP server
- **SVG Status Badge Generator** (`tools/markdown_badge_generator.py`) - Create custom shields.io style SVG badges locally for use in markdown documents
- **System PATH Doctor** (`tools/env_path_doctor.py`) - Diagnose, optimize, and clean system environment PATH variables with safety warnings and shell commands
- **Python Virtual Environment Inspector** (`tools/venv_inspector.py`) - Scan directories for virtual environments, calculate disk space usage, and list installed packages without running a pip subprocess
- **Conventional Commit Builder & Gitmoji helper** (`tools/git_commit_builder.py`) - Interactive CLI helper to construct Conventional Commit messages with optional Gitmojis, check formatting constraints, and run git commit
- **Color Palette Generator & Harmony Visualizer** (`tools/color_palette_generator.py`) - Generate monochromatic, analogous, complementary, triadic, and tetradic color palettes, visualize true colors in terminal, and export to CSS, JSON, or Tailwind
- **Regex Synthesizer & Pattern Inferrer** (`tools/regex_synthesizer.py`) - Infer and generate regular expressions based on positive and negative string examples using rule-based heuristics
- **Markdown Resume Compiler** (`tools/markdown_resume_compiler.py`) - Compile plain Markdown resumes to beautiful, responsive, and print-ready HTML documents with built-in design themes
- **Brainfuck Interpreter & Debugger** (`tools/brainfuck_interpreter.py`) - Run and trace esoteric Brainfuck code with a visual memory tape representation
- **Command Benchmarker** (`tools/command_benchmarker.py`) - Benchmark shell command execution times with detailed statistics (min, max, mean, median, stddev)
- **Glob Pattern Tester** (`tools/glob_tester.py`) - Validate and debug glob patterns interactively or in batch mode against local directories or simulated path files
- **ISBN Validator & Converter** (`tools/isbn_validator.py`) - Validate and format ISBN-10/13 identifiers, extract book code segments, and convert formats
- **Dockerfile Linter & Best Practices Checker** (`tools/dockerfile_linter.py`) - Parse Dockerfiles to validate syntax and identify anti-patterns (unpinned tags, missing package manager cleanups, root usage) with colored suggestions
- **XML Validator, Beautifier & Minifier** (`tools/xml_formatter.py`) - Validate, pretty-print with configurable indentation, or minify XML payloads with precise syntax error line and column reports
- **Git Branch Commit Tree Visualizer** (`tools/git_branch_visualizer.py`) - Render local Git repository commit histories as colored ASCII/Unicode graphs with author, relative date, and reference tags
- **CSS Design System & Style Guide Generator** (`tools/css_style_guide_generator.py`) - Parses CSS files to extract color codes, custom properties (variables), typography settings, media queries, and generates a responsive visual design system style guide
- **Python Script Bundler** (`tools/python_script_bundler.py`) - Trace local import dependencies of a Python script recursively using AST and bundle them into a single executable standalone script
- **Hex & Binary Patch Editor** (`tools/hex_patch_editor.py`) - View, search, and patch binary files using customizable hex dump formats, pattern matching (hex/ASCII), and safe backups
- **CSS Unused Selector Scanner** (`tools/css_unused_scanner.py`) - Scan templates and scripts recursively to find dead/unused CSS classes and IDs
- **Git Merge Conflict Resolver** (`tools/git_conflict_resolver.py`) - Scans for Git merge conflicts and provides interactive side-by-side comparison and resolution options
- **Python Dead Code Finder** (`tools/python_dead_code_finder.py`) - Scan Python source files recursively and identify unused functions, classes, and global variables using AST analysis
- **ASCII & Unicode Sequence Diagram Generator** (`tools/ascii_sequence_diagram.py`) - Compile text-based sequence descriptions (similar to PlantUML) into formatted Unicode or ASCII charts in the console


### Data Processing
- **CSV Processor** (`tools/csv_processor.py`) - Process and manipulate CSV files with various operations
- **Data Entry Automation** (`tools/data_entry_automation.py`) - Automate repetitive data entry tasks
- **Database Tool** (`tools/database_tool.py`) - Utility for database operations and migrations
- **SQLite Database Explorer** (`tools/sqlite_explorer.py`) - Inspect database schemas, tables, and execute queries in tabular format
- **SQL Formatter** (`tools/sql_formatter.py`) - Standardize, format, and beautify SQL queries
- **Excel Automation** (`tools/excel_automation.py`) - Automate Excel file operations and data extraction
- **Config Format Converter** (`tools/config_converter.py`) - Convert configuration files between JSON, INI, XML, YAML, and TOML
- **JSON Schema Generator** (`tools/json_schema_generator.py`) - Infer Draft-07 JSON Schema from a sample JSON data payload
- **JSON Flattener & Unflattener** (`tools/json_flattener.py`) - Flatten nested JSON objects or unflatten them back using dotted-key paths
- **Mock Data Generator** (`tools/mock_data_generator.py`) - Generate mock user profiles in JSON, CSV, or XML format
- **Markdown Table Generator** (`tools/markdown_table_generator.py`) - Convert CSV, JSON, or delimited text into clean, aligned Markdown tables
- **Markdown Table Parser** (`tools/markdown_table_parser.py`) - Parse Markdown tables and convert them to CSV, TSV, or JSON formats
- **Extractive Text Summarizer** (`tools/text_summarizer.py`) - Generate concise summaries and compute text analytics/reading metrics from documents or standard input
- **Sentiment Analyzer** (`tools/sentiment_analyzer.py`) - Standalone lexicon-based text sentiment analyzer that computes sentiment scores and classifications
- **Log Visualizer** (`tools/log_visualizer.py`) - Parse log files (JSON-Lines, CSV, or raw text), aggregate metrics, and print a horizontal progress/severity histogram in the terminal
- **CSV to SQLite Converter** (`tools/csv_to_sqlite.py`) - Convert CSV files into SQLite databases with automatic type inference and run SQL queries
- **GPX Route Analyzer** (`tools/gpx_analyzer.py`) - Parse GPX tracks and calculate route distance, duration, elevation profile, and speeds
- **Word Frequency Analyzer** (`tools/word_frequency_analyzer.py`) - Calculate word frequencies, filter stop words, compute text metrics, and render terminal bar charts or tag clouds
- **CSV Data Profiler** (`tools/csv_profiler.py`) - Profile CSV file columns to infer data types and compute detailed statistics without pandas
- **JSON Schema Validator** (`tools/json_schema_validator.py`) - Validate JSON data payloads against JSON Schema draft-07 specifications
- **Text Similarity Detector** (`tools/text_similarity_detector.py`) - Compare documents or code files to compute similarity scores using Jaccard, Cosine, and TF-IDF metrics
- **Configuration Merger** (`tools/config_merger.py`) - Deep merge multiple JSON, INI, XML, YAML, or TOML configuration files with hierarchical overrides
- **SQLite Database Schema Visualizer** (`tools/db_schema_visualizer.py`) - Extract SQLite table structures and generate text reports or Mermaid ER diagrams
- **SQLite Query Profiler** (`tools/sqlite_query_profiler.py`) - Profile SQLite query execution time, explain query plans, and suggest optimization indexes
- **CSV/JSON Template Renderer** (`tools/template_renderer.py`) - Merge JSON or CSV data with text templates containing variables, conditionals, loops, and filters
- **OpenAPI to Markdown Generator** (`tools/openapi_to_markdown.py`) - Parse OpenAPI 3.0/3.1 JSON schemas and produce publication-ready Markdown docs
- **Structured Data Tree Visualizer** (`tools/structured_data_visualizer.py`) - Renders JSON, XML, TOML, or YAML files as interactive-looking, color-coded terminal trees
- **Markdown to EPUB E-book Compiler** (`tools/markdown_to_epub.py`) - Convert a directory of markdown files or a single markdown document into a standard, fully-validated EPUB e-book using only standard libraries
- **SQLite Database Dumper** (`tools/sql_dumper.py`) - SQLite database backup/dump utility that exports schema and data as standard SQL statements
- **CSV Pivot Table Generator** (`tools/csv_pivot_table.py`) - Generate pivot summaries and tables from CSV data without external libraries
- **Configuration Path Query Utility** (`tools/config_query.py`) - Query and extract values from JSON, YAML, TOML, XML, and INI configuration files using dot-notation path queries
- **CSV Validator** (`tools/csv_validator.py`) - Validate CSV structure, column count matches, and verify data types using standard schema rules
- **JSON Lines Query Tool** (`tools/jsonl_query.py`) - Query, filter, slice, and reformat JSON Lines (JSONL / NDJSON) files
- **SQLite Schema Diff Tool** (`tools/sqlite_schema_diff.py`) - Compare SQLite database schemas and generate migration SQL scripts
- **CSV Diff & Reconciliation Tool** (`tools/csv_diff.py`) - Perform row-by-row reconciliation between two CSV files using a unique primary key, highlighting added, deleted, and modified columns
- **Interactive SQL REPL & SQLite Playground** (`tools/sqlite_playground.py`) - Run SQL queries interactively in a SQLite REPL with multi-line input, execution timer, dot commands, schema visualizer, and CSV/JSON exporters
- **SQL DDL Dialect Translator** (`tools/sql_schema_converter.py`) - Translate DDL SQL schemas between PostgreSQL, MySQL, SQLite, and Microsoft SQL Server dialects, converting data types, identifier quoting, auto-increments, and table constraints
- **JSON Schema Mock Data Generator** (`tools/json_schema_mock_generator.py`) - Generate mock data records (supporting emails, dates, numbers, objects) conforming to a JSON Schema draft-07 file
- **SQLite Data Anonymizer** (`tools/sqlite_data_anonymizer.py`) - Detect potential PII in SQLite databases and interactively mask, hash, nullify, or fake the fields
- **Structured Data to SQL Insert Generator** (`tools/data_to_sql_insert.py`) - Convert CSV, JSON, or JSONL files into SQL INSERT statements with datatype inference, single-quote escaping, and batching


### Network & Web
- **API Mock Server** (`tools/api_mock_server.py`) - A lightweight HTTP/REST API mock server
- **Clipboard Manager** (`tools/clipboard_manager.py`) - Enhanced clipboard management with history
- **DNS Lookup Tool** (`tools/dns_lookup_tool.py`) - Perform DNS lookups and network diagnostics
- **DNS Propagation Checker** (`tools/dns_propagation_checker.py`) - Query multiple DNS providers for domain records to check propagation
- **DNS Zone File Parser & Validator** (`tools/dns_zone_validator.py`) - Parse and validate RFC 1035 DNS zone files for syntax and logical configuration errors
- **Email Automation** (`tools/email_automation.py`) - Automate sending emails with attachments
- **Hosts File Manager** (`tools/hosts_manager.py`) - List, add, remove, enable, or disable domain resolution mappings in the system hosts file
- **HTML Link Extractor** (`tools/html_link_extractor.py`) - Parse HTML to extract and export hyperlinks, images, stylesheets, and scripts
- **HTML Table Extractor** (`tools/html_table_extractor.py`) - Extract tables from HTML files, raw HTML, or URLs and format them as CSV, JSON, or Markdown
- **HTTP Load Tester** (`tools/http_load_tester.py`) - Benchmark web servers and APIs with concurrent HTTP requests
- **IP Geolocation Finder** (`tools/ip_geolocation_finder.py`) - Find geographic details of an IP address or domain name
- **IP Subnet Calculator** (`tools/ip_subnet_calculator.py`) - Calculate network subnetting details and binary representations
- **TCP Port Forwarder** (`tools/port_forwarder.py`) - Forward TCP traffic from a local port to a target host and port with real-time statistics
- **TCP Port Scanner** (`tools/port_scanner.py`) - Scan target host TCP ports and retrieve service banners
- **Socket Debugger** (`tools/socket_debugger.py`) - TCP/UDP socket diagnostics, testing, client/server modes, and hex dump utility (Netcat-like)
- **URL Parser & Query Inspector** (`tools/url_parser.py`) - Parse URLs and inspect components and query parameters
- **URL Validator** (`tools/url_validator.py`) - Validate and check if URLs are accessible
- **User-Agent String Analyzer & Web Log Parser** (`tools/user_agent_analyzer.py`) - Parse HTTP User-Agent strings and aggregate browser/OS/device stats from Apache/Nginx web logs
- **Web Archiver** (`tools/web_archiver.py`) - Bundle a web page and its assets into a single self-contained HTML file
- **HTTP Security Headers Checker** (`tools/http_headers_checker.py`) - Fetch a URL and analyze response headers for missing, misconfigured, or recommended security settings
- **Markdown Image Localizer** (`tools/markdown_image_localizer.py`) - Scan a Markdown file for remote image references, download them locally, and update paths to reference them
- **Local Port Finder & Inspector** (`tools/port_finder.py`) - Find free local TCP ports and inspect active port statuses
- **Sitemap Generator** (`tools/sitemap_generator.py`) - Crawl websites recursively to generate SEO-compliant XML or text sitemaps
- **Local File Sharing Server** (`tools/file_sharing_server.py`) - Standalone local HTTP server with uploading and downloading capabilities under a responsive dark web UI
- **Mock DNS Server** (`tools/dns_server_mock.py`) - Local UDP DNS stub server for resolving domain names using custom JSON files
- **Subdomain Enumerator** (`tools/subdomain_enumerator.py`) - Fast multi-threaded DNS subdomain discovery utility using a wordlist
- **DNS Benchmarker** (`tools/dns_benchmarker.py`) - Benchmark latencies and success rates of multiple public DNS resolvers using raw UDP queries
- **RSS & Atom Feed Reader** (`tools/rss_feed_reader.py`) - Terminal-based feed reader and aggregator with HTML report exporting
- **Port Listener & Request Dumper** (`tools/request_dumper.py`) - Listen on TCP/UDP ports and dump incoming request payloads, headers, and hex bytes
- **URL Route Pattern Matcher** (`tools/url_route_matcher.py`) - Parse and test routing patterns (Flask, Express styles) against paths to extract parameters
- **Web Broken Link Checker** (`tools/web_broken_link_checker.py`) - Recursively crawls a website up to a specified depth and identifies broken links
- **HTTP Downloader** (`tools/http_downloader.py`) - Download files over HTTP/HTTPS with progress bar, resume support, and checksum checks
- **Web Asset Extractor & Downloader** (`tools/web_asset_downloader.py`) - Crawls a webpage, downloads CSS, JS, and image assets into organized local folders, and rewrites the HTML locally
- **DNS over HTTPS Client** (`tools/dns_over_https_client.py`) - Resolve DNS records over HTTPS using Cloudflare or Google DoH endpoints
- **Web Performance Analyzer** (`tools/web_performance_analyzer.py`) - Audits HTTP connection latency phases (DNS, TCP, SSL, TTFB, transfer) and lists webpage assets (CSS, JS, images)
- **Mock SMTP Server** (`tools/mock_smtp_server.py`) - A lightweight, local SMTP mail server for developer testing that displays incoming mails and captures them as .eml files
- **Web Speed Tester & Request Timeline Analyzer** (`tools/web_speed_tester.py`) - Measure request execution phases (DNS resolution, TCP connection, SSL handshake, TTFB, transfer time) and render an ASCII waterfall timeline chart
- **Domain WHOIS Expiry Scanner** (`tools/domain_whois_scanner.py`) - Query domain registration records (WHOIS) directly over raw sockets, parsing expiration dates and registrar info
- **HTTP Proxy Debugger** (`tools/http_proxy_debugger.py`) - A local intercepting and tunneling HTTP/HTTPS proxy server logging requests, headers, and traffic details
- **GitHub Folder Downloader** (`tools/github_folder_downloader.py`) - Download specific folders or files from GitHub without cloning the entire repository
- **Mock S3 Server** (`tools/mock_s3_server.py`) - Launch a lightweight mock Amazon S3 HTTP server locally for testing
- **Mock Redis Server** (`tools/mock_redis_server.py`) - A lightweight, in-memory, TCP-based Redis mock server implementing the RESP protocol for local development and testing
- **Local SEO & Web Accessibility Auditor** (`tools/seo_auditor.py`) - Audits local HTML files or remote URLs for SEO issues and accessibility standards, generating interactive console summaries and styled HTML reports
- **Frontend Live Reload Server** (`tools/live_reload_server.py`) - Lightweight HTTP development server for static files that injects a Server-Sent Events (SSE) client to auto-reload browsers on file edits
- **HTTP Traffic Speed Shaper & Rate Limiter Proxy** (`tools/rate_limiter_proxy.py`) - Threaded HTTP/HTTPS proxy to simulate bandwidth throttling, latencies, packet delays, and HTTP 429 rate-limiting responses
- **Webhook Inspector & Payload Reflector** (`tools/webhook_reflector.py`) - Capture incoming POST webhooks, log request structures, verify HMAC signatures (GitHub, Stripe, Shopify), and replay payloads via an interactive dashboard
- **API Rate Limit Prober & Analyzer** (`tools/api_rate_limit_analyzer.py`) - Safely probe endpoints to test rate limits and extract key details from response headers (Retry-After, X-RateLimit-*)
- **HTTP Redirect Tracer & Loop Detector** (`tools/http_redirect_tracer.py`) - Trace redirect chains step-by-step, checking status codes, times, cookies, security headers, and open redirects
- **Network Throughput & Performance Tester** (`tools/network_throughput_tester.py`) - Benchmark network bandwidth, packet loss, and jitter using TCP or UDP sockets (iperf-like client/server)
- **Web Content Extractor & Reader Mode** (`tools/web_content_extractor.py`) - Extract the core article text from a webpage, omitting navigation, sidebars, and ads using scoring heuristics


### Security & Cryptography
- **Password Strength Checker** (`tools/password_strength_checker.py`) - Check password strength and generate secure passwords
- **Password Analyzer** (`tools/password_analyzer.py`) - Analyze and evaluate password strength with detailed feedback
- **EXIF Metadata Inspector & Cleaner** (`tools/exif_cleaner.py`) - Inspect and strip EXIF metadata from images to preserve privacy
- **Offline JWT Debugger** (`tools/jwt_debugger.py`) - Decode, inspect, verify, and encode HS256 JSON Web Tokens locally and offline
- **Log Anonymizer & PII Masker** (`tools/log_anonymizer.py`) - Scrub sensitive PII, credentials, and IP addresses from logs and text files
- **Time-based One-Time Password (TOTP) Generator** (`tools/totp_generator.py`) - Secure, offline multi-factor authentication (MFA) client with visual countdown progress bars
- **Hash Generator & Verifier** (`tools/hash_generator.py`) - Generate cryptographic hashes (MD5, SHA-1, SHA-256, etc.) for text strings or files, and verify them against expected values
- **Wi-Fi Password Retriever** (`tools/wifi_password_retriever.py`) - Retrieve saved Wi-Fi profiles and passwords cross-platform
- **Text Steganography Tool** (`tools/text_steganography.py`) - Invisibly hide and extract secret messages in cover text using Unicode zero-width characters
- **Secure File Shredder** (`tools/file_shredder.py`) - Overwrites files and directories with random data/zeroes to prevent recovery
- **Classic Cipher Utility** (`tools/cipher_utility.py`) - Encrypt and decrypt text using classical ciphers (Caesar, Vigenère, ROT13, Atbash, XOR)
- **CSV PII Anonymizer & Masker** (`tools/csv_anonymizer.py`) - Anonymize and mask sensitive personal identifiers (PII) in structured CSV datasets
- **Security Log Anomaly Detector** (`tools/log_anomaly_detector.py`) - Scans application logs for SQL injection, XSS, traversals, and volumetric outliers
- **File Signature Detector** (`tools/file_signature_detector.py`) - Detect file type by checking magic bytes and finding mismatches with file extension
- **Password Breach Checker** (`tools/password_breach_checker.py`) - Checks if a password has been leaked in data breaches using the HIBP API anonymously (K-anonymity privacy model)
- **Source Code Secrets & API Key Scanner** (`tools/secrets_scanner.py`) - Recursively scans files/folders for API keys, tokens, private keys, and high-entropy secret strings with masked reporting
- **Luhn Algorithm Validator & Mock Generator** (`tools/card_validator.py`) - Validate credit cards and IMEIs, identify issuer networks (Visa, Mastercard, Amex, etc.), and generate valid test numbers
- **Mock OIDC / OAuth2 & JWKS Token Server** (`tools/mock_auth_server.py`) - Launch a local OpenID Connect mock identity provider that serves OIDC configuration, JWKS key sets, and signs RS256/HS256 tokens
- **Git Commit Signature Auditor** (`tools/git_signature_auditor.py`) - Audit GPG/SSH/S-MIME commit signature compliance and match keys to developers
- **Offline JWT HS256 Secret Cracker** (`tools/jwt_secret_cracker.py`) - Offline dictionary and brute-force cracking tool for HS256 JSON Web Tokens (JWTs)



## Usage

Each tool can be run individually:

```bash
python tools/tool_name.py [options]
```

Most tools include help documentation:

```bash
python tools/tool_name.py --help
```

## Requirements

- Python 3.6+
- Some tools may require additional packages (listed in their headers)

## Contributing

Feel free to submit issues, fork the repository, and send pull requests!

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.