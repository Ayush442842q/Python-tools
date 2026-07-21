# URL Validator

A Python tool to validate and check if URLs are accessible.

## Features

- Validates URL format
- Checks HTTP status codes
- Batch processing from file input
- Command-line interface

## Usage

```bash
# Validate a single URL
python url_validator.py https://example.com

# Validate a URL with explicit flag
python url_validator.py --url https://example.com

# Validate URLs from a file
python url_validator.py -f urls.txt
```

## Installation

1. Clone the repository
2. Navigate to the tools directory
3. Run the script directly or install as a module

## Requirements

- Python 3.x
- requests library

Install requirements with:
```bash
pip install requests
```

## Example Output

```
Validating: https://example.com
✓ Valid URL format
✓ Status: 200 - Success

Validating: https://nonexistentdomain12345.com
✓ Valid URL format
✗ Error: Name or service not known
```