#!/usr/bin/env python3
"""
OpenAPI to Markdown Documentation Generator
A standalone CLI utility that parses OpenAPI 3.0/3.1 JSON definitions
(local files or remote URLs) and produces styled, publication-ready Markdown documentation.
"""

import os
import sys
import json
import urllib.request
import urllib.error
import argparse

# Enable ANSI escape sequences on Windows if possible
if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        stdout_handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_ulong()
        if kernel32.GetConsoleMode(stdout_handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(stdout_handle, mode.value | 0x0004)
    except Exception:
        pass

# Configure stdout/stderr encoding to UTF-8 to prevent charmap errors on Windows console redirection
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        try:
            stream.reconfigure(encoding='utf-8')
        except Exception:
            pass


def resolve_ref(ref_str, spec):
    """Resolves local OpenAPI JSON references (e.g. #/components/schemas/User)."""
    if not ref_str:
        return None
    if not ref_str.startswith("#/"):
        # We don't support external document reference resolution in this standalone script
        return {"type": "object", "description": f"External reference: {ref_str}"}
    
    parts = ref_str.lstrip("#/").split("/")
    curr = spec
    for p in parts:
        if isinstance(curr, dict) and p in curr:
            curr = curr[p]
        else:
            return None
    return curr

def extract_schema_details(schema, spec, parent_name=""):
    """Recursively extracts fields, types, required flags, and descriptions from schemas."""
    if not isinstance(schema, dict):
        return []
        
    if "$ref" in schema:
        resolved = resolve_ref(schema["$ref"], spec)
        if resolved:
            return extract_schema_details(resolved, spec, parent_name)
        return []
        
    rows = []
    
    # Handle object properties
    properties = schema.get("properties", {})
    required_fields = schema.get("required", [])
    
    for prop_name, prop_val in properties.items():
        if not isinstance(prop_val, dict):
            continue
            
        # Resolve ref if present
        if "$ref" in prop_val:
            resolved = resolve_ref(prop_val["$ref"], spec)
            if resolved:
                # Merge keys
                merged = prop_val.copy()
                del merged["$ref"]
                for k, v in resolved.items():
                    if k not in merged:
                        merged[k] = v
                prop_val = merged
                
        p_type = prop_val.get("type", "any")
        
        # Handle array items
        if p_type == "array" and "items" in prop_val:
            items_schema = prop_val["items"]
            if isinstance(items_schema, dict) and "$ref" in items_schema:
                items_resolved = resolve_ref(items_schema["$ref"], spec)
                if items_resolved:
                    items_schema = items_resolved
            items_type = items_schema.get("type", "any") if isinstance(items_schema, dict) else "any"
            p_type = f"Array<{items_type}>"
            
        p_req = "Yes" if prop_name in required_fields else "No"
        p_desc = prop_val.get("description", "").replace("\n", " ").strip()
        
        full_name = f"{parent_name}.{prop_name}" if parent_name else prop_name
        rows.append((full_name, p_type, p_req, p_desc))
        
        # Recurse if nested object
        if prop_val.get("type") == "object":
            rows.extend(extract_schema_details(prop_val, spec, full_name))
        elif "items" in prop_val and isinstance(prop_val["items"], dict) and prop_val["items"].get("type") == "object":
            rows.extend(extract_schema_details(prop_val["items"], spec, f"{full_name}[]"))
            
    # Handle oneOf / anyOf / allOf
    for combiner in ["oneOf", "anyOf", "allOf"]:
        if combiner in schema and isinstance(schema[combiner], list):
            for i, sub_schema in enumerate(schema[combiner]):
                rows.extend(extract_schema_details(sub_schema, spec, f"{parent_name}({combiner}[{i}])" if parent_name else f"({combiner}[{i}])"))
                
    return rows

def generate_markdown(spec):
    """Generates the Markdown output from parsed OpenAPI JSON spec."""
    lines = []
    
    # Title & Metadata
    info = spec.get("info", {})
    lines.append(f"# {info.get('title', 'API Documentation')}")
    if info.get("version"):
        lines.append(f"**Version:** {info.get('version')}  ")
    if info.get("description"):
        lines.append(f"\n{info.get('description')}\n")
        
    # Servers
    servers = spec.get("servers", [])
    if servers:
        lines.append("## Servers")
        for s in servers:
            desc = f" ({s.get('description')})" if s.get('description') else ""
            lines.append(f"- `{s.get('url')}`{desc}")
        lines.append("")
        
    # Group Endpoints by Tag
    paths = spec.get("paths", {})
    tagged_endpoints = {}  # tag -> list of (path, method, operation)
    untagged_endpoints = []
    
    for path, path_item in paths.items():
        if not isinstance(path_item, dict):
            continue
        for method in ["get", "post", "put", "delete", "options", "head", "patch", "trace"]:
            if method in path_item:
                op = path_item[method]
                if not isinstance(op, dict):
                    continue
                tags = op.get("tags", [])
                if tags:
                    for t in tags:
                        if t not in tagged_endpoints:
                            tagged_endpoints[t] = []
                        tagged_endpoints[t].append((path, method, op))
                else:
                    untagged_endpoints.append((path, method, op))
                    
    # Generate Table of Contents / Summary Table
    lines.append("## Table of Endpoints\n")
    lines.append("| Method | Path | Summary |")
    lines.append("|---|---|---|")
    
    all_sorted_endpoints = []
    for tag, endpoints in sorted(tagged_endpoints.items()):
        for path, method, op in endpoints:
            all_sorted_endpoints.append((path, method, op, tag))
    for path, method, op in untagged_endpoints:
        all_sorted_endpoints.append((path, method, op, "General"))
        
    for path, method, op, tag in all_sorted_endpoints:
        anchor_name = f"{method.upper()}-{path}".lower().replace("{", "").replace("}", "").replace("/", "").replace(" ", "-")
        summary = op.get("summary", "").replace("\n", " ").strip()
        lines.append(f"| `{method.upper()}` | [{path}](#{anchor_name}) | {summary} |")
    lines.append("")
    
    # Detail Sections grouped by Tag
    current_tag = None
    for path, method, op, tag in all_sorted_endpoints:
        if tag != current_tag:
            current_tag = tag
            lines.append(f"\n# {current_tag} Endpoints\n")
            
        lines.append(f"### {method.upper()} `{path}`")
        if op.get("summary"):
            lines.append(f"**{op.get('summary')}**\n")
        if op.get("description"):
            lines.append(f"{op.get('description')}\n")
            
        # Parameters
        params = op.get("parameters", [])
        # Also inherit path item level parameters if any
        path_item = paths.get(path, {})
        inherited_params = path_item.get("parameters", [])
        all_params = params + inherited_params
        
        if all_params:
            lines.append("#### Parameters\n")
            lines.append("| Name | Located In | Type | Required | Description |")
            lines.append("|---|---|---|---|---|")
            for p in all_params:
                if isinstance(p, dict) and "$ref" in p:
                    p = resolve_ref(p["$ref"], spec)
                if not isinstance(p, dict):
                    continue
                p_name = p.get("name", "")
                p_in = p.get("in", "")
                p_req = "Yes" if p.get("required") else "No"
                p_desc = p.get("description", "").replace("\n", " ").strip()
                p_schema = p.get("schema", {})
                p_type = p_schema.get("type", "any") if isinstance(p_schema, dict) else "any"
                lines.append(f"| **{p_name}** | `{p_in}` | `{p_type}` | {p_req} | {p_desc} |")
            lines.append("")
            
        # Request Body
        req_body = op.get("requestBody")
        if req_body:
            if isinstance(req_body, dict) and "$ref" in req_body:
                req_body = resolve_ref(req_body["$ref"], spec)
            if isinstance(req_body, dict):
                lines.append("#### Request Body\n")
                if req_body.get("description"):
                    lines.append(f"{req_body.get('description')}\n")
                content = req_body.get("content", {})
                for mime_type, media_type in content.items():
                    lines.append(f"- **Content-Type:** `{mime_type}`")
                    schema = media_type.get("schema")
                    if schema:
                        rows = extract_schema_details(schema, spec)
                        if rows:
                            lines.append("\n| Field | Type | Required | Description |")
                            lines.append("|---|---|---|---|")
                            for r in rows:
                                lines.append(f"| `{r[0]}` | `{r[1]}` | {r[2]} | {r[3]} |")
                            lines.append("")
                            
        # Responses
        responses = op.get("responses", {})
        if responses:
            lines.append("#### Responses\n")
            lines.append("| Status Code | Description | Content Schema |")
            lines.append("|---|---|---|")
            for code, resp in responses.items():
                if isinstance(resp, dict) and "$ref" in resp:
                    resp = resolve_ref(resp["$ref"], spec)
                if not isinstance(resp, dict):
                    continue
                desc = resp.get("description", "").replace("\n", " ").strip()
                
                content = resp.get("content", {})
                schema_repr = "None"
                for mime, media in content.items():
                    schema = media.get("schema")
                    if schema:
                        if isinstance(schema, dict) and "$ref" in schema:
                            ref_path = schema["$ref"].split("/")[-1]
                            schema_repr = f"`{mime}` (ref: `{ref_path}`)"
                        else:
                            s_type = schema.get("type", "object") if isinstance(schema, dict) else "object"
                            schema_repr = f"`{mime}` (`{s_type}`)"
                        break # Show first matching content schema
                lines.append(f"| `{code}` | {desc} | {schema_repr} |")
            lines.append("")
            
            # Response schemas detail
            for code, resp in responses.items():
                if isinstance(resp, dict) and "$ref" in resp:
                    resp = resolve_ref(resp["$ref"], spec)
                if not isinstance(resp, dict):
                    continue
                content = resp.get("content", {})
                for mime, media in content.items():
                    schema = media.get("schema")
                    if schema:
                        rows = extract_schema_details(schema, spec)
                        if rows:
                            lines.append(f"**Response schema details for status `{code}` (`{mime}`):**\n")
                            lines.append("| Field | Type | Required | Description |")
                            lines.append("|---|---|---|---|")
                            for r in rows:
                                lines.append(f"| `{r[0]}` | `{r[1]}` | {r[2]} | {r[3]} |")
                            lines.append("")
            
        lines.append("---\n")
        
    return "\n".join(lines)

def load_spec(source):
    """Loads OpenAPI spec from JSON file or remote HTTP URL."""
    # Check if remote URL
    if source.startswith("http://") or source.endswith(".json") and source.startswith("https://"):
        try:
            print(f"Fetching remote schema: {source}")
            req = urllib.request.Request(
                source, 
                headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            )
            with urllib.request.urlopen(req) as response:
                return json.loads(response.read().decode('utf-8'))
        except urllib.error.URLError as e:
            raise ValueError(f"Failed to fetch remote URL: {e}")
    else:
        # Local file
        if not os.path.exists(source):
            raise FileNotFoundError(f"Local file not found: {source}")
        with open(source, 'r', encoding='utf-8') as f:
            return json.load(f)

def main():
    parser = argparse.ArgumentParser(
        description="OpenAPI to Markdown Documentation Generator: Convert OpenAPI JSON schema specs to publication-ready Markdown docs.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python tools/openapi_to_markdown.py --input openapi.json --output API_DOCS.md
  python tools/openapi_to_markdown.py --input https://petstore.swagger.io/v2/swagger.json -o petstore.md
"""
    )
    parser.add_argument("--input", "-i", required=True, help="Path to local JSON OpenAPI file or HTTP URL")
    parser.add_argument("--output", "-o", help="Path to write the generated Markdown file (writes to stdout if not specified)")

    args = parser.parse_args()

    try:
        spec = load_spec(args.input)
        
        # Verify it's an OpenAPI definition
        is_swagger = "swagger" in spec
        is_openapi = "openapi" in spec
        if not (is_swagger or is_openapi):
            print("\033[33mWarning: Input JSON does not appear to contain 'openapi' or 'swagger' version fields.\033[0m", file=sys.stderr)
            
        markdown_content = generate_markdown(spec)
        
        if args.output:
            out_dir = os.path.dirname(args.output)
            if out_dir and not os.path.exists(out_dir):
                os.makedirs(out_dir, exist_ok=True)
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(markdown_content)
            print(f"\033[32mSuccessfully generated documentation to '{args.output}'.\033[0m")
        else:
            sys.stdout.write(markdown_content)
            
    except Exception as e:
        print(f"\033[31mError generating OpenAPI documentation: {e}\033[0m", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
