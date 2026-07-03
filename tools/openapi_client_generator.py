#!/usr/bin/env python3
"""
Parses OpenAPI (Swagger) 3.0/3.1 JSON or YAML specs and generates a standalone,
type-hinted Python API client SDK using only standard library modules.
"""

import sys
import os
import re
import json
import argparse

# Try importing yaml for YAML spec support
try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False

def to_snake_case(name):
    """Converts CamelCase or mixed strings to snake_case."""
    # Replace non-alphanumeric characters with underscores
    name = re.sub(r'[^a-zA-Z0-9]', '_', name)
    # Convert camelCase to snake_case
    s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
    s2 = re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
    return re.sub(r'_+', '_', s2).strip('_')

def sanitize_method_name(http_method, path, operation_id=None):
    """Creates a clean pythonic method name from operationId or path."""
    if operation_id:
        return to_snake_case(operation_id)
    
    # Otherwise, generate from HTTP method and path
    cleaned_path = path.replace('{', '').replace('}', '')
    parts = [http_method.lower()] + [p for p in cleaned_path.split('/') if p]
    return to_snake_case("_".join(parts))

def parse_spec(spec_content, is_yaml=False):
    """Parses JSON or YAML specification content."""
    if is_yaml:
        if not HAS_YAML:
            print("Error: PyYAML is required to parse YAML files. Run 'pip install pyyaml' or use a JSON specification.", file=sys.stderr)
            sys.exit(1)
        return yaml.safe_load(spec_content)
    else:
        return json.loads(spec_content)

def generate_client(spec, class_name="APIClient"):
    """Generates the Python client source code from the parsed spec."""
    info = spec.get("info", {})
    title = info.get("title", "API Client")
    description = info.get("description", "Auto-generated Python client.")
    version = info.get("version", "1.0.0")

    # Get servers base URL
    servers = spec.get("servers", [])
    default_url = servers[0].get("url", "http://localhost") if servers else "http://localhost"

    code = []
    # Header & Imports
    code.append(f'# -*- coding: utf-8 -*-')
    code.append(f'"""')
    code.append(f'{title} - v{version}')
    code.append(f'{description}')
    code.append(f'"""')
    code.append(f'import json')
    code.append(f'import urllib.request')
    code.append(f'import urllib.parse')
    code.append(f'import urllib.error')
    code.append(f'from typing import Any, Dict, List, Optional, Union')
    code.append(f'')
    
    # Exceptions
    code.append(f'class APIError(Exception):')
    code.append(f'    """Base exception for API requests."""')
    code.append(f'    def __init__(self, status_code: int, response_body: str):')
    code.append(f'        self.status_code = status_code')
    code.append(f'        self.response_body = response_body')
    code.append(f'        super().__init__(f"HTTP {status_code}: {response_body[:200]}")')
    code.append(f'')
    
    # Class declaration
    code.append(f'class {class_name}:')
    code.append(f'    def __init__(self, base_url: str = "{default_url}", token: Optional[str] = None):')
    code.append(f'        self.base_url = base_url.rstrip("/")')
    code.append(f'        self.token = token')
    code.append(f'        self.headers = {{')
    code.append(f'            "Content-Type": "application/json",')
    code.append(f'            "Accept": "application/json"')
    code.append(f'        }}')
    code.append(f'        if token:')
    code.append(f'            self.headers["Authorization"] = f"Bearer {{token}}"')
    code.append(f'')
    
    # Core Request Method
    code.append(f'    def _request(self, method: str, path: str, query_params: Optional[Dict[str, Any]] = None, body_params: Optional[Any] = None) -> Any:')
    code.append(f'        # Clean query parameters')
    code.append(f'        if query_params:')
    code.append(f'            query_params = {{k: v for k, v in query_params.items() if v is not None}}')
    code.append(f'            query_str = urllib.parse.urlencode(query_params, doseq=True)')
    code.append(f'            url = f"{{self.base_url}}{{path}}?{{query_str}}"')
    code.append(f'        else:')
    code.append(f'            url = f"{{self.base_url}}{{path}}"')
    code.append(f'')
    code.append(f'        data = None')
    code.append(f'        headers = self.headers.copy()')
    code.append(f'        if body_params is not None:')
    code.append(f'            data = json.dumps(body_params).encode("utf-8")')
    code.append(f'')
    code.append(f'        req = urllib.request.Request(url, data=data, headers=headers, method=method.upper())')
    code.append(f'        try:')
    code.append(f'            with urllib.request.urlopen(req) as response:')
    code.append(f'                res_data = response.read().decode("utf-8")')
    code.append(f'                if response.status == 204 or not res_data:')
    code.append(f'                    return None')
    code.append(f'                try:')
    code.append(f'                    return json.loads(res_data)')
    code.append(f'                except json.JSONDecodeError:')
    code.append(f'                    return res_data')
    code.append(f'        except urllib.error.HTTPError as e:')
    code.append(f'            res_body = e.read().decode("utf-8")')
    code.append(f'            raise APIError(e.code, res_body) from e')
    code.append(f'        except urllib.error.URLError as e:')
    code.append(f'            raise APIError(0, str(e.reason)) from e')
    code.append(f'')

    # Endpoints
    paths = spec.get("paths", {})
    for path, path_info in paths.items():
        for http_method, op_info in path_info.items():
            if http_method.upper() not in ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]:
                continue
            
            method_name = sanitize_method_name(http_method, path, op_info.get("operationId"))
            summary = op_info.get("summary", f"{http_method.upper()} request to {path}")
            description = op_info.get("description", "")
            
            parameters = op_info.get("parameters", [])
            # Also fetch parameters at the path level
            parameters.extend(path_info.get("parameters", []))
            
            path_params = []
            query_params = []
            header_params = []
            
            for param in parameters:
                # Handle reference parameters (basic resolution)
                if "$ref" in param:
                    # Skips complex refs for simplicity
                    continue
                
                param_in = param.get("in")
                if param_in == "path":
                    path_params.append(param)
                elif param_in == "query":
                    query_params.append(param)
                elif param_in == "header":
                    header_params.append(param)
            
            # Request body definition
            has_body = "requestBody" in op_info
            
            # Build function signature arguments
            sig_args = ["self"]
            
            # Required path parameters first
            for param in path_params:
                name = to_snake_case(param.get("name"))
                sig_args.append(f"{name}: str")
                
            # Optional query parameters and body
            for param in query_params:
                name = to_snake_case(param.get("name"))
                required = param.get("required", False)
                if required:
                    sig_args.append(f"{name}: Any")
                else:
                    sig_args.append(f"{name}: Optional[Any] = None")
            
            if has_body:
                # Basic check for request body requirement
                req_body = op_info.get("requestBody", {})
                required = req_body.get("required", False)
                if required:
                    sig_args.append("body: Any")
                else:
                    sig_args.append("body: Optional[Any] = None")
                    
            # Build method body
            code.append(f'    def {method_name}({", ".join(sig_args)}) -> Any:')
            code.append(f'        """')
            code.append(f'        {summary}')
            if description:
                code.append(f'        ')
                code.append(f'        {description}')
            code.append(f'        """')
            
            # Format path parameters (replacing {param} with python format string)
            formatted_path = path
            for param in path_params:
                orig_name = param.get("name")
                snake_name = to_snake_case(orig_name)
                formatted_path = formatted_path.replace(f"{{{orig_name}}}", f"{{{snake_name}}}")
                
            if path_params:
                code.append(f'        path = f"{formatted_path}"')
            else:
                code.append(f'        path = "{formatted_path}"')
                
            # Query parameters dict builder
            if query_params:
                code.append(f'        query = {{')
                for param in query_params:
                    orig_name = param.get("name")
                    snake_name = to_snake_case(orig_name)
                    code.append(f'            "{orig_name}": {snake_name},')
                code.append(f'        }}')
            else:
                code.append(f'        query = None')
                
            body_arg = "body" if has_body else "None"
            
            code.append(f'        return self._request("{http_method.upper()}", path, query_params=query, body_params={body_arg})')
            code.append(f'')
            
    return "\n".join(code)

def main():
    parser = argparse.ArgumentParser(
        description="Auto-generate a pythonic REST API Client SDK from an OpenAPI / Swagger specification."
    )
    parser.add_argument(
        "spec", 
        help="Path to the OpenAPI JSON or YAML spec file."
    )
    parser.add_argument(
        "-o", "--output", 
        help="Output Python file path. If omitted, writes to stdout."
    )
    parser.add_argument(
        "--class-name", 
        default="APIClient", 
        help="Name of the generated client class (default: APIClient)."
    )
    
    args = parser.parse_args()
    
    if not os.path.exists(args.spec):
        print(f"Error: Specification file not found at {args.spec}", file=sys.stderr)
        sys.exit(1)
        
    is_yaml = args.spec.endswith(".yaml") or args.spec.endswith(".yml")
    
    try:
        with open(args.spec, "r", encoding="utf-8") as f:
            content = f.read()
        spec = parse_spec(content, is_yaml)
    except Exception as e:
        print(f"Error parsing spec file: {e}", file=sys.stderr)
        sys.exit(1)
        
    generated_code = generate_client(spec, args.class_name)
    
    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(generated_code)
            print(f"Client SDK successfully generated and saved to {args.output}", file=sys.stderr)
        except Exception as e:
            print(f"Error writing to output file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print(generated_code)

if __name__ == "__main__":
    main()
