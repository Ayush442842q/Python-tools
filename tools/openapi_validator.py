#!/usr/bin/env python3
"""
OpenAPI Schema Validator - Validate OpenAPI/Swagger specification files.

Validates OpenAPI 3.0/3.1 and Swagger 2.0 specifications for correctness,
completeness, and best practices.

Features:
- Validates OpenAPI 3.0, 3.1, and Swagger 2.0 formats
- Checks required fields and structure
- Validates path parameters match path templates
- Detects duplicate operation IDs
- Checks for missing descriptions and summaries
- Validates schema references ($ref)
- Identifies security definition issues
- Reports best practice violations

Usage:
    python openapi_validator.py <spec_file>
    python openapi_validator.py spec.yaml --strict --output report.json

Example:
    python openapi_validator.py openapi.yaml
    python openapi_validator.py swagger.json --strict
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


class OpenAPIValidator:
    """Validate OpenAPI/Swagger specifications."""

    REQUIRED_V3_FIELDS = ['openapi', 'info', 'paths']
    REQUIRED_V2_FIELDS = ['swagger', 'info', 'paths']
    REQUIRED_INFO_FIELDS = ['title', 'version']
    REQUIRED_PATH_ITEM_FIELDS = ['get', 'post', 'put', 'delete', 'patch', 'options', 'head', 'trace']

    HTTP_METHODS = {'get', 'post', 'put', 'delete', 'patch', 'options', 'head', 'trace'}

    def __init__(self, spec_path: Path, strict: bool = False):
        self.spec_path = spec_path
        self.spec: Optional[Dict] = None
        self.version: str = ''
        self.is_strict = strict
        self.errors: List[Dict] = []
        self.warnings: List[Dict] = []
        self.info: List[Dict] = []

    def load_spec(self) -> bool:
        """Load and parse the OpenAPI spec file."""
        if not self.spec_path.exists():
            self.errors.append({
                'level': 'error',
                'code': 'FILE_NOT_FOUND',
                'message': f"Specification file not found: {self.spec_path}"
            })
            return False

        try:
            content = self.spec_path.read_text(encoding='utf-8')
        except Exception as e:
            self.errors.append({
                'level': 'error',
                'code': 'READ_ERROR',
                'message': f"Failed to read file: {e}"
            })
            return False

        # Try JSON first
        if self.spec_path.suffix in ['.json', '']:
            try:
                self.spec = json.loads(content)
                return True
            except json.JSONDecodeError:
                pass

        # Try YAML
        if HAS_YAML and self.spec_path.suffix in ['.yaml', '.yml']:
            try:
                self.spec = yaml.safe_load(content)
                return True
            except yaml.YAMLError as e:
                self.errors.append({
                    'level': 'error',
                    'code': 'PARSE_ERROR',
                    'message': f"YAML parse error: {e}"
                })
                return False
        elif not HAS_YAML and self.spec_path.suffix in ['.yaml', '.yml']:
            self.errors.append({
                'level': 'error',
                'code': 'MISSING_DEPENDENCY',
                'message': "Install PyYAML (pip install pyyaml) to parse YAML files"
            })
            return False

        self.errors.append({
            'level': 'error',
            'code': 'UNSUPPORTED_FORMAT',
            'message': "File is neither valid JSON nor YAML"
        })
        return False

    def detect_version(self) -> str:
        """Detect OpenAPI/Swagger version."""
        if not self.spec:
            return ''

        if 'openapi' in self.spec:
            version = self.spec['openapi']
            self.version = '3.x' if str(version).startswith('3') else 'unknown'
        elif 'swagger' in self.spec:
            version = self.spec['swagger']
            self.version = '2.0'
        else:
            self.version = 'unknown'
            self.errors.append({
                'level': 'error',
                'code': 'NO_VERSION',
                'message': "Missing 'openapi' or 'swagger' version field"
            })

        return self.version

    def validate_structure(self) -> None:
        """Validate basic structure and required fields."""
        if not self.spec:
            return

        # Check required fields based on version
        if self.version == '3.x':
            required = self.REQUIRED_V3_FIELDS
        elif self.version == '2.0':
            required = self.REQUIRED_V2_FIELDS
        else:
            required = []

        for field in required:
            if field not in self.spec:
                self.errors.append({
                    'level': 'error',
                    'code': f'MISSING_{field.upper()}',
                    'message': f"Missing required field: '{field}'"
                })

        # Check info object
        if 'info' in self.spec:
            info = self.spec['info']
            for field in self.REQUIRED_INFO_FIELDS:
                if field not in info:
                    self.errors.append({
                        'level': 'error',
                        'code': f'MISSING_INFO_{field.upper()}',
                        'message': f"Missing required info field: '{field}'"
                    })
        elif self.is_strict:
            self.warnings.append({
                'level': 'warning',
                'code': 'MISSING_INFO',
                'message': "Missing 'info' object"
            })

    def validate_paths(self) -> None:
        """Validate paths and operations."""
        if not self.spec or 'paths' not in self.spec:
            return

        paths = self.spec['paths']
        operation_ids: Set[str] = set()

        for path, path_item in paths.items():
            # Validate path parameter format
            if '{' in path:
                path_params = set(p.strip('{}') for p in path.split('{') if '}' in p)
            else:
                path_params = set()

            if not isinstance(path_item, dict):
                self.errors.append({
                    'level': 'error',
                    'code': 'INVALID_PATH_ITEM',
                    'message': f"Path '{path}' must be an object",
                    'location': f'paths.{path}'
                })
                continue

            # Check each method
            for method in self.HTTP_METHODS:
                if method not in path_item:
                    continue

                operation = path_item[method]
                if not isinstance(operation, dict):
                    self.warnings.append({
                        'level': 'warning',
                        'code': 'INVALID_OPERATION',
                        'message': f"Operation '{method}' in '{path}' should be an object",
                        'location': f'paths.{path}.{method}'
                    })
                    continue

                # Check operationId uniqueness
                if 'operationId' in operation:
                    op_id = operation['operationId']
                    if op_id in operation_ids:
                        self.errors.append({
                            'level': 'error',
                            'code': 'DUPLICATE_OPERATION_ID',
                            'message': f"Duplicate operationId: '{op_id}'",
                            'location': f'paths.{path}.{method}'
                        })
                    operation_ids.add(op_id)

                # Check path parameters are defined
                op_params = {p['name'] for p in operation.get('parameters', []) if isinstance(p, dict)}
                for param in path_params:
                    if param not in op_params:
                        # Check path-level parameters
                        path_params_set = {p['name'] for p in path_item.get('parameters', []) if isinstance(p, dict)}
                        if param not in path_params_set:
                            self.errors.append({
                                'level': 'error',
                                'code': 'UNDEFINED_PATH_PARAM',
                                'message': f"Path parameter '{param}' used but not defined",
                                'location': f'paths.{path}.{method}'
                            })

                # Strict mode: check for descriptions
                if self.is_strict:
                    if 'summary' not in operation and 'description' not in operation:
                        self.warnings.append({
                            'level': 'warning',
                            'code': 'MISSING_SUMMARY',
                            'message': f"Operation '{method} {path}' missing summary or description",
                            'location': f'paths.{path}.{method}'
                        })

    def validate_references(self) -> None:
        """Validate $ref references."""
        if not self.spec:
            return

        # Collect all component keys
        components = set()
        if 'components' in self.spec:
            for comp_type, comp_items in self.spec['components'].items():
                if isinstance(comp_items, dict):
                    for key in comp_items:
                        components.add(f'#/components/{comp_type}/{key}')

        # Find all $refs
        self._find_refs(self.spec, components)

    def _find_refs(self, obj: Any, valid_refs: Set[str], path: str = '') -> None:
        """Recursively find and validate $ref values."""
        if isinstance(obj, dict):
            if '$ref' in obj:
                ref = obj['$ref']
                if not ref.startswith('#/'):
                    # External reference - skip validation
                    return

                if ref not in valid_refs:
                    self.warnings.append({
                        'level': 'warning',
                        'code': 'BROKEN_REF',
                        'message': f"Reference '{ref}' may be broken",
                        'location': path
                    })
            else:
                for key, value in obj.items():
                    self._find_refs(value, valid_refs, f'{path}.{key}')
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                self._find_refs(item, valid_refs, f'{path}[{i}]')

    def validate_security(self) -> None:
        """Validate security definitions/schemes."""
        if not self.spec:
            return

        # Check for global security requirements
        if 'security' in self.spec:
            for sec_req in self.spec['security']:
                if not isinstance(sec_req, dict):
                    self.errors.append({
                        'level': 'error',
                        'code': 'INVALID_SECURITY',
                        'message': "Security requirement must be an object"
                    })
                    continue

                for sec_name in sec_req:
                    self._check_security_definition(sec_name)

        # Check operation-level security
        if 'paths' in self.spec:
            for path, path_item in self.spec['paths'].items():
                if isinstance(path_item, dict):
                    for method in self.HTTP_METHODS:
                        if method in path_item:
                            op = path_item[method]
                            if isinstance(op, dict) and 'security' in op:
                                for sec_req in op['security']:
                                    if isinstance(sec_req, dict):
                                        for sec_name in sec_req:
                                            self._check_security_definition(sec_name)

    def _check_security_definition(self, name: str) -> None:
        """Check if a security definition exists."""
        if not self.spec:
            return

        # Check OpenAPI 3.x
        if 'components' in self.spec and 'securitySchemes' in self.spec['components']:
            schemes = self.spec['components']['securitySchemes']
            if name not in schemes:
                self.errors.append({
                    'level': 'error',
                    'code': 'MISSING_SECURITY_SCHEME',
                    'message': f"Security scheme '{name}' is not defined"
                })

        # Check Swagger 2.0
        if 'securityDefinitions' in self.spec:
            if name not in self.spec['securityDefinitions']:
                self.errors.append({
                    'level': 'error',
                    'code': 'MISSING_SECURITY_DEFINITION',
                    'message': f"Security definition '{name}' is not defined"
                })

    def generate_report(self) -> Dict:
        """Generate validation report."""
        return {
            'file': str(self.spec_path),
            'version': self.version,
            'valid': len(self.errors) == 0,
            'summary': {
                'errors': len(self.errors),
                'warnings': len(self.warnings),
                'info': len(self.info)
            },
            'errors': self.errors,
            'warnings': self.warnings,
            'info': self.info
        }

    def print_report(self) -> None:
        """Print validation report to console."""
        report = self.generate_report()

        print(f"\n{'='*60}")
        print(f"OpenAPI Validation Report")
        print(f"{'='*60}")
        print(f"File: {self.spec_path.absolute()}")
        print(f"Version: {self.version}")
        print()

        if report['valid']:
            print("✓ Specification is VALID")
        else:
            print("✗ Specification has ERRORS")

        print(f"\nSummary:")
        print(f"  Errors:   {report['summary']['errors']}")
        print(f"  Warnings: {report['summary']['warnings']}")
        print(f"  Info:     {report['summary']['info']}")

        if self.errors:
            print(f"\n{'='*60}")
            print("ERRORS:")
            print(f"{'='*60}")
            for error in self.errors:
                loc = error.get('location', '')
                loc_str = f" ({loc})" if loc else ''
                print(f"  ✗ [{error['code']}]{loc_str}")
                print(f"    {error['message']}")

        if self.warnings:
            print(f"\n{'='*60}")
            print("WARNINGS:")
            print(f"{'='*60}")
            for warning in self.warnings[:10]:
                loc = warning.get('location', '')
                loc_str = f" ({loc})" if loc else ''
                print(f"  ⚠ [{warning['code']}]{loc_str}")
                print(f"    {warning['message']}")
            if len(self.warnings) > 10:
                print(f"  ... and {len(self.warnings) - 10} more warnings")

        print(f"\n{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Validate OpenAPI/Swagger specification files'
    )
    parser.add_argument('spec_file', type=Path,
                        help='OpenAPI/Swagger spec file (YAML or JSON)')
    parser.add_argument('--strict', action='store_true',
                        help='Enable strict validation (descriptions required)')
    parser.add_argument('-o', '--output',
                        help='Output report to file (JSON format)')
    parser.add_argument('-q', '--quiet', action='store_true',
                        help='Suppress console output')

    args = parser.parse_args()

    validator = OpenAPIValidator(args.spec_file, strict=args.strict)

    if not validator.load_spec():
        validator.print_report()
        return 1

    validator.detect_version()
    validator.validate_structure()
    validator.validate_paths()
    validator.validate_references()
    validator.validate_security()

    if not args.quiet:
        validator.print_report()

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(
            json.dumps(validator.generate_report(), indent=2),
            encoding='utf-8'
        )
        print(f"Report saved to: {output_path.absolute()}")

    return 0 if not validator.errors else 1


if __name__ == '__main__':
    sys.exit(main())