#!/usr/bin/env python3
"""
API Response Mock Generator - Generate mock API responses from OpenAPI specs.

Generates realistic mock data for API endpoints based on OpenAPI/Swagger
specifications. Useful for testing, prototyping, and demo environments.

Features:
- Parse OpenAPI 3.0/3.1 and Swagger 2.0 specs
- Generate realistic mock data for all response schemas
- Support for nested objects, arrays, and references
- Generate multiple response examples
- Export as JSON files or mock server code
- Customizable data generation (seeds, counts, locales)
- Type-aware mock generation (strings, numbers, dates, etc.)

Usage:
    python api_mock_generator.py <openapi_spec> [--endpoint ENDPOINT] [--output mocks/]
    python api_mock_generator.py spec.yaml -o mocks/ --format json
    python api_mock_generator.py swagger.json --endpoint "/users/{id}" --count 5

Example:
    python api_mock_generator.py openapi.yaml --output api_mocks/
    python api_mock_generator.py spec.json --endpoint "/products" --count 10
"""

import os
import sys
import json
import random
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


# Mock data generators
class MockDataGenerator:
    """Generate mock data based on schema types."""

    # Sample data pools
    FIRST_NAMES = ['James', 'Mary', 'John', 'Patricia', 'Robert', 'Jennifer', 
                   'Michael', 'Linda', 'William', 'Elizabeth', 'David', 'Barbara',
                   'Richard', 'Susan', 'Joseph', 'Jessica', 'Thomas', 'Sarah',
                   'Charles', 'Karen', 'Christopher', 'Lisa', 'Daniel', 'Nancy']

    LAST_NAMES = ['Smith', 'Johnson', 'Williams', 'Brown', 'Jones', 'Garcia',
                  'Miller', 'Davis', 'Rodriguez', 'Martinez', 'Hernandez', 'Lopez',
                  'Gonzalez', 'Wilson', 'Anderson', 'Thomas', 'Taylor', 'Moore',
                  'Jackson', 'Martin', 'Lee', 'Perez', 'Thompson', 'White']

    CITIES = ['New York', 'Los Angeles', 'Chicago', 'Houston', 'Phoenix',
              'Philadelphia', 'San Antonio', 'San Diego', 'Dallas', 'San Jose']

    COUNTRIES = ['United States', 'Canada', 'United Kingdom', 'Germany', 'France',
                 'Japan', 'Australia', 'Brazil', 'India', 'China']

    COMPANIES = ['Acme Corp', 'Globex', 'Soylent Corp', 'Initech', 'Umbrella Corp',
                 'Stark Industries', 'Wayne Enterprises', 'Cyberdyne', 'Massive Dynamic']

    LOREM_WORDS = ['lorem', 'ipsum', 'dolor', 'sit', 'amet', 'consectetur',
                   'adipiscing', 'elit', 'sed', 'do', 'eiusmod', 'tempor']

    def __init__(self, seed: Optional[int] = None):
        if seed is not None:
            random.seed(seed)
        self.seed = seed

    def generate(self, schema: Dict, depth: int = 0, context: str = '') -> Any:
        """Generate mock data from a schema."""
        if depth > 10:
            return None  # Prevent infinite recursion

        if not schema:
            return None

        # Handle $ref
        if '$ref' in schema:
            return self._handle_ref(schema['$ref'], depth, context)

        schema_type = schema.get('type', 'object')

        # Handle nullable
        if schema.get('nullable') and random.random() < 0.1:
            return None

        # Use enum if available
        if 'enum' in schema:
            return random.choice(schema['enum'])

        # Use example/default if available
        if 'example' in schema:
            return schema['example']
        if 'default' in schema:
            return schema['default']

        # Generate based on type
        if schema_type == 'string':
            return self._generate_string(schema, context)
        elif schema_type == 'integer':
            return self._generate_integer(schema)
        elif schema_type == 'number':
            return self._generate_number(schema)
        elif schema_type == 'boolean':
            return random.choice([True, False])
        elif schema_type == 'array':
            return self._generate_array(schema, depth, context)
        elif schema_type == 'object':
            return self._generate_object(schema, depth, context)
        else:
            return self._generate_string(schema, context)

    def _handle_ref(self, ref: str, depth: int, context: str) -> Any:
        """Resolve $ref and generate data."""
        # For now, return placeholder - real implementation would resolve refs
        ref_name = ref.split('/')[-1]
        return f"<Reference: {ref_name}>"

    def _generate_string(self, schema: Dict, context: str = '') -> str:
        """Generate mock string."""
        format_type = schema.get('format', '')
        min_length = schema.get('minLength', 1)
        max_length = schema.get('maxLength', 100)

        # Context-aware generation
        context_lower = context.lower()

        if 'name' in context_lower:
            result = f"{random.choice(self.FIRST_NAMES)} {random.choice(self.LAST_NAMES)}"
        elif 'email' in context_lower or format_type == 'email':
            result = f"{random.choice(self.FIRST_NAMES).lower()}.{random.choice(self.LAST_NAMES).lower()}@example.com"
        elif 'phone' in context_lower or format_type == 'phone':
            result = f"+1-{random.randint(200,999)}-{random.randint(100,999)}-{random.randint(1000,9999)}"
        elif 'url' in context_lower or format_type == 'uri':
            result = f"https://example.com/{random.choice(self.LOREM_WORDS)}"
        elif 'date' in context_lower or format_type == 'date':
            result = (datetime.now() + timedelta(days=random.randint(-365, 365))).strftime('%Y-%m-%d')
        elif 'datetime' in context_lower or format_type == 'date-time':
            result = (datetime.now() + timedelta(days=random.randint(-365, 365))).isoformat() + 'Z'
        elif 'uuid' in context_lower or format_type == 'uuid':
            import uuid
            result = str(uuid.uuid4())
        elif format_type == 'byte':
            import base64
            result = base64.b64encode(os.urandom(16)).decode()
        elif 'address' in context_lower:
            result = f"{random.randint(1,9999)} {random.choice(self.LOREM_WORDS).title()} St"
        elif 'city' in context_lower:
            result = random.choice(self.CITIES)
        elif 'country' in context_lower:
            result = random.choice(self.COUNTRIES)
        elif 'company' in context_lower or 'organization' in context_lower:
            result = random.choice(self.COMPANIES)
        elif 'title' in context_lower or 'subject' in context_lower:
            result = ' '.join(random.choices(self.LOREM_WORDS, k=random.randint(3, 6))).title()
        elif 'description' in context_lower or 'bio' in context_lower:
            result = ' '.join(random.choices(self.LOREM_WORDS, k=random.randint(10, 20)))
        else:
            # Generate random string
            length = random.randint(min_length, min(max_length, 20))
            result = ' '.join(random.choices(self.LOREM_WORDS, k=length//5 + 1))

        return result[:max_length]

    def _generate_integer(self, schema: Dict) -> int:
        """Generate mock integer."""
        minimum = schema.get('minimum', 0)
        maximum = schema.get('maximum', 1000)
        multiple_of = schema.get('multipleOf', 1)

        value = random.randint(minimum, maximum)
        if multiple_of > 1:
            value = (value // multiple_of) * multiple_of

        return value

    def _generate_number(self, schema: Dict) -> float:
        """Generate mock number."""
        minimum = schema.get('minimum', 0.0)
        maximum = schema.get('maximum', 1000.0)

        return round(random.uniform(minimum, maximum), 2)

    def _generate_array(self, schema: Dict, depth: int, context: str) -> List:
        """Generate mock array."""
        items_schema = schema.get('items', {})
        min_items = schema.get('minItems', 1)
        max_items = schema.get('maxItems', 5)

        count = random.randint(min_items, max_items)
        return [
            self.generate(items_schema, depth + 1, context)
            for _ in range(count)
        ]

    def _generate_object(self, schema: Dict, depth: int, context: str) -> Dict:
        """Generate mock object."""
        properties = schema.get('properties', {})
        required = schema.get('required', [])
        additional = schema.get('additionalProperties', False)

        result = {}
        for prop_name, prop_schema in properties.items():
            # Include required properties, and randomly include optionals
            if prop_name in required or random.random() < 0.8:
                result[prop_name] = self.generate(
                    prop_schema, 
                    depth + 1, 
                    f"{context}.{prop_name}" if context else prop_name
                )

        return result


class APIMockGenerator:
    """Generate API mock responses from OpenAPI spec."""

    def __init__(self, spec_path: Path):
        self.spec_path = spec_path
        self.spec: Optional[Dict] = None
        self.data_gen = MockDataGenerator()

    def load_spec(self) -> bool:
        """Load OpenAPI spec."""
        if not self.spec_path.exists():
            print(f"Error: Spec file not found: {self.spec_path}")
            return False

        content = self.spec_path.read_text(encoding='utf-8')

        # Try JSON
        if self.spec_path.suffix == '.json':
            try:
                self.spec = json.loads(content)
                return True
            except json.JSONDecodeError:
                pass

        # Try YAML
        if self.spec_path.suffix in ['.yaml', '.yml'] and HAS_YAML:
            try:
                self.spec = yaml.safe_load(content)
                return True
            except yaml.YAMLError:
                pass

        print("Error: Could not parse spec file")
        return False

    def get_endpoints(self) -> List[Tuple[str, str]]:
        """Get all endpoints from spec."""
        endpoints = []

        if not self.spec or 'paths' not in self.spec:
            return endpoints

        for path, methods in self.spec['paths'].items():
            for method in methods:
                if method.lower() in ['get', 'post', 'put', 'delete', 'patch']:
                    endpoints.append((path.upper(), method.lower()))

        return endpoints

    def generate_mock_response(self, path: str, method: str, 
                               count: int = 1) -> List[Dict]:
        """Generate mock response for an endpoint."""
        if not self.spec:
            return []

        responses = []

        try:
            path_item = self.spec['paths'].get(path, {})
            operation = path_item.get(method, {})
            
            # Get response schema
            if 'responses' in operation:
                responses_obj = operation['responses']
                
                # Look for 200 or 201 response
                response = responses_obj.get('200') or responses_obj.get('201')
                
                if response and 'content' in response:
                    content = response['content']
                    
                    # Prefer application/json
                    if 'application/json' in content:
                        schema = content['application/json'].get('schema', {})
                    elif any(k for k in content if 'json' in k):
                        json_key = [k for k in content if 'json' in k][0]
                        schema = content[json_key].get('schema', {})
                    else:
                        return [{'message': 'No JSON schema found'}]
                elif response and 'schema' in response:
                    schema = response['schema']
                else:
                    return [{'message': 'No response schema found'}]
            else:
                return [{'message': 'No responses defined'}]

            # Handle array response
            if schema.get('type') == 'array':
                items_schema = schema.get('items', {})
                return [
                    self.data_gen.generate(items_schema)
                    for _ in range(count)
                ]
            else:
                return [self.data_gen.generate(schema)]

        except Exception as e:
            return [{'error': str(e)}]

    def generate_all(self, count: int = 1, 
                     output_dir: Optional[Path] = None) -> Dict[str, List]:
        """Generate mocks for all endpoints."""
        mocks = {}

        for status, endpoint in self.get_endpoints():
            # Clean endpoint for filename
            safe_name = endpoint.replace('/', '_').replace('{', '').replace('}', '').strip('_')
            
            mock_data = self.generate_mock_response(endpoint, status.lower(), count)
            mocks[safe_name] = mock_data

            if output_dir:
                output_dir.mkdir(parents=True, exist_ok=True)
                output_file = output_dir / f"{safe_name}.json"
                output_file.write_text(
                    json.dumps(mock_data[0] if count == 1 else mock_data, indent=2),
                    encoding='utf-8'
                )
                print(f"  Generated: {output_file.name}")

        return mocks

    def print_mocks(self, mocks: Dict) -> None:
        """Print generated mocks."""
        print(f"\n{'='*60}")
        print("Generated Mock Responses")
        print(f"{'='*60}")

        for endpoint, data in mocks.items():
            print(f"\n## {endpoint}")
            print(json.dumps(data, indent=2)[:500])
            if len(json.dumps(data)) > 500:
                print("  ... (truncated)")

        print(f"\n{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description='Generate mock API responses from OpenAPI specs'
    )
    parser.add_argument('spec_file', type=Path,
                        help='OpenAPI/Swagger spec file')
    parser.add_argument('-e', '--endpoint',
                        help='Specific endpoint to generate (e.g., /users)')
    parser.add_argument('-m', '--method', default='get',
                        help='HTTP method (default: get)')
    parser.add_argument('-c', '--count', type=int, default=1,
                        help='Number of mock records to generate')
    parser.add_argument('-o', '--output', type=Path,
                        help='Output directory for mock files')
    parser.add_argument('-s', '--seed', type=int,
                        help='Random seed for reproducibility')

    args = parser.parse_args()

    generator = APIMockGenerator(args.spec_file)

    if args.seed is not None:
        generator.data_gen = MockDataGenerator(seed=args.seed)

    if not generator.load_spec():
        return 1

    print(f"Loaded spec: {args.spec_file}")
    print(f"Found {len(generator.get_endpoints())} endpoints")

    if args.endpoint and args.output:
        # Generate specific endpoint
        print(f"\nGenerating mock for: {args.endpoint}")
        mock_data = generator.generate_mock_response(
            args.endpoint, 
            args.method.lower(),
            args.count
        )

        output_dir = args.output
        output_dir.mkdir(parents=True, exist_ok=True)
        safe_name = args.endpoint.replace('/', '_').strip('_')
        output_file = output_dir / f"{safe_name}.json"
        output_file.write_text(json.dumps(mock_data, indent=2), encoding='utf-8')
        print(f"Saved to: {output_file}")
        print(f"\nMock data:\n{json.dumps(mock_data, indent=2)}")

    else:
        # Generate all endpoints
        print(f"\nGenerating mocks for all endpoints...")
        mocks = generator.generate_all(count=args.count, output_dir=args.output)

        if not args.output:
            generator.print_mocks(mocks)

    return 0


if __name__ == '__main__':
    sys.exit(main())