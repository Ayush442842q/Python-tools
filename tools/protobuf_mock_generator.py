#!/usr/bin/env python3
"""
Protobuf Mock Data Generator - A tool to parse .proto files and generate mock JSON data.
"""

import argparse
import sys
import re
import json
import random

# Mock database of realistic values
MOCK_NAMES = ["Alice Smith", "Bob Jones", "Charlie Brown", "Diana Prince", "Evan Wright", "Fiona Gallagher"]
MOCK_WORDS = ["awesome", "reliable", "scalable", "efficient", "secure", "dynamic", "flexible"]
MOCK_DOMAINS = ["example.com", "test.org", "api.net", "company.io", "cloud.dev"]

def parse_proto(content):
    """
    Parse a proto file content.
    Returns:
        messages: dict mapping message name to list of fields:
                  {'name': field_name, 'type': field_type, 'repeated': bool}
        enums: dict mapping enum name to list of string values
    """
    # Remove C-style line comments
    content = re.sub(r'//.*', '', content)
    # Remove C-style block comments
    content = re.sub(r'/\*.*?\*/', '', content, flags=re.DOTALL)
    
    # Tokenize words, punctuation, symbols
    tokens = re.findall(r'[a-zA-Z_][a-zA-Z0-9_]*|[{};=]|".*?"', content)
    
    messages = {}
    enums = {}
    
    i = 0
    while i < len(tokens):
        token = tokens[i]
        if token == 'message':
            i += 1
            if i >= len(tokens):
                break
            msg_name = tokens[i]
            i += 1
            if i < len(tokens) and tokens[i] == '{':
                i += 1
            # Parse message fields until matching closing brace
            brace_count = 1
            msg_tokens = []
            while i < len(tokens) and brace_count > 0:
                tok = tokens[i]
                if tok == '{':
                    brace_count += 1
                elif tok == '}':
                    brace_count -= 1
                
                if brace_count > 0:
                    msg_tokens.append(tok)
                i += 1
            messages[msg_name] = parse_message_fields(msg_tokens)
        elif token == 'enum':
            i += 1
            if i >= len(tokens):
                break
            enum_name = tokens[i]
            i += 1
            if i < len(tokens) and tokens[i] == '{':
                i += 1
            enum_values = []
            while i < len(tokens) and tokens[i] != '}':
                val_name = tokens[i]
                i += 1
                # Skip to next value or closing brace (skip '=' and number and ';')
                while i < len(tokens) and tokens[i] != ';' and tokens[i] != '}':
                    i += 1
                if i < len(tokens) and tokens[i] == ';':
                    i += 1
                enum_values.append(val_name)
            enums[enum_name] = enum_values
            if i < len(tokens) and tokens[i] == '}':
                i += 1
        else:
            i += 1
            
    return messages, enums

def parse_message_fields(tokens):
    """Parse fields from tokens inside a message block."""
    fields = []
    i = 0
    while i < len(tokens):
        if tokens[i] == ';':
            i += 1
            continue
            
        is_repeated = False
        if tokens[i] == 'repeated':
            is_repeated = True
            i += 1
            
        if i >= len(tokens):
            break
            
        field_type = tokens[i]
        i += 1
        
        # Support map<key, value> as a raw string type or skip
        if field_type == 'map' and i < len(tokens) and tokens[i] == '<':
            # Skip generics map<...> as it is complex, just call type map
            map_tokens = []
            brace_count = 0
            while i < len(tokens):
                tok = tokens[i]
                if tok == '<':
                    brace_count += 1
                elif tok == '>':
                    brace_count -= 1
                map_tokens.append(tok)
                i += 1
                if brace_count == 0:
                    break
            field_type = 'map' + "".join(map_tokens)
            
        if i >= len(tokens):
            break
            
        field_name = tokens[i]
        i += 1
        
        # Skip '=' and field number and optional options like '[default = x]'
        while i < len(tokens) and tokens[i] != ';':
            i += 1
            
        fields.append({
            'name': field_name,
            'type': field_type,
            'repeated': is_repeated
        })
    return fields

def generate_mock_field(field_name, field_type, messages, enums, depth=0, max_depth=3):
    """Generate mock data for a single field based on name and type."""
    if depth > max_depth:
        return None

    # Normalization
    name_lower = field_name.lower()
    
    # 1. Custom Enums
    if field_type in enums:
        return random.choice(enums[field_type])
        
    # 2. Nested Messages
    if field_type in messages:
        return generate_mock_message(field_type, messages, enums, depth + 1, max_depth)
        
    # 3. Standard Protobuf Scalar Types
    if field_type == 'string':
        if 'email' in name_lower:
            name_part = random.choice(MOCK_NAMES).lower().replace(" ", ".")
            return f"{name_part}@{random.choice(MOCK_DOMAINS)}"
        elif 'name' in name_lower:
            return random.choice(MOCK_NAMES)
        elif 'url' in name_lower or 'uri' in name_lower:
            return f"https://{random.choice(MOCK_DOMAINS)}/{random.choice(MOCK_WORDS)}"
        elif 'id' in name_lower or 'uuid' in name_lower:
            return f"uuid-{random.randint(100000, 999999)}-{random.randint(1000, 9999)}"
        elif 'phone' in name_lower:
            return f"+1-{random.randint(200, 999)}-555-01{random.randint(10, 99)}"
        else:
            return f"mock_{field_name}_{random.choice(MOCK_WORDS)}"
            
    elif field_type in ('int32', 'int64', 'uint32', 'uint64', 'sint32', 'sint64', 'fixed32', 'fixed64', 'sfixed32', 'sfixed64'):
        if 'age' in name_lower:
            return random.randint(18, 90)
        elif 'year' in name_lower:
            return random.randint(2000, 2026)
        elif 'port' in name_lower:
            return random.choice([80, 443, 8080, 3000, 5000])
        elif 'count' in name_lower or 'size' in name_lower or 'quantity' in name_lower:
            return random.randint(1, 100)
        else:
            return random.randint(1000, 9999)
            
    elif field_type == 'bool':
        return random.choice([True, False])
        
    elif field_type in ('float', 'double'):
        if 'price' in name_lower or 'amount' in name_lower:
            return round(random.uniform(5.0, 500.0), 2)
        elif 'rate' in name_lower or 'score' in name_lower:
            return round(random.uniform(0.0, 5.0), 1)
        else:
            return round(random.uniform(-100.0, 100.0), 4)
            
    elif field_type == 'bytes':
        # Return a simple mock base64 string
        return "bW9ja19ieXRlc19kYXRh"
        
    # Fallback/Maps
    if field_type.startswith('map'):
        # Extract map types map<key, val>
        match = re.match(r'map<(\w+),\s*(\w+)>', field_type)
        if match:
            k_type, v_type = match.groups()
            mock_map = {}
            for _ in range(random.randint(1, 3)):
                k = generate_mock_field(f"{field_name}_key", k_type, messages, enums, depth, max_depth)
                v = generate_mock_field(f"{field_name}_val", v_type, messages, enums, depth, max_depth)
                if k is not None:
                    mock_map[str(k)] = v
            return mock_map
        return {"mock_key": "mock_value"}
        
    return f"unsupported_type_{field_type}"

def generate_mock_message(msg_name, messages, enums, depth=0, max_depth=3):
    """Generate mock data dictionary for a parsed message structure."""
    if msg_name not in messages:
        return {}
        
    mock_data = {}
    fields = messages[msg_name]
    
    for field in fields:
        name = field['name']
        f_type = field['type']
        
        if field['repeated']:
            mock_data[name] = [
                generate_mock_field(name, f_type, messages, enums, depth, max_depth)
                for _ in range(random.randint(1, 3))
            ]
        else:
            mock_data[name] = generate_mock_field(name, f_type, messages, enums, depth, max_depth)
            
    return mock_data

def main():
    parser = argparse.ArgumentParser(
        description="Protobuf Mock Data Generator - Generate mock JSON records from a proto file schema."
    )
    parser.add_argument(
        "proto_file",
        help="Path to the .proto file"
    )
    parser.add_argument(
        "-m", "--message",
        help="Root message name to generate mock data for (if omitted, uses first message in file)"
    )
    parser.add_argument(
        "-n", "--count",
        type=int,
        default=1,
        help="Number of mock records to generate (default: 1)"
    )
    parser.add_argument(
        "-o", "--output",
        help="Save output to a JSON file instead of printing"
    )
    parser.add_argument(
        "--indent",
        type=int,
        default=2,
        help="JSON indentation spaces (default: 2)"
    )

    args = parser.parse_args()

    try:
        with open(args.proto_file, 'r', encoding='utf-8') as f:
            content = f.read()
    except FileNotFoundError:
        print(f"Error: File '{args.proto_file}' not found.", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {e}", file=sys.stderr)
        sys.exit(1)

    messages, enums = parse_proto(content)
    
    if not messages:
        print("Error: No messages found in the proto file.", file=sys.stderr)
        sys.exit(1)

    # Determine root message
    root_msg = args.message
    if not root_msg:
        root_msg = list(messages.keys())[0]
        print(f"No root message specified. Defaulting to first message: '{root_msg}'")

    if root_msg not in messages:
        print(f"Error: Root message '{root_msg}' not found in proto. Available messages: {', '.join(messages.keys())}", file=sys.stderr)
        sys.exit(1)

    # Generate mock records
    records = []
    for _ in range(args.count):
        records.append(generate_mock_message(root_msg, messages, enums))

    # Output formatting
    output_data = records[0] if args.count == 1 else records
    json_output = json.dumps(output_data, indent=args.indent)

    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(json_output)
            print(f"✓ Saved {args.count} mock records to {args.output}")
        except Exception as e:
            print(f"Error saving to output file: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        print("\nGenerated Mock Data:")
        print(json_output)

if __name__ == "__main__":
    main()
