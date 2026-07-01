#!/usr/bin/env python3
"""
JSONPath Evaluator & Query Tool
Query JSON structures using standard JSONPath expressions.
Supports:
- Root selection ($)
- Dot-notation child selector ($.store.book)
- Bracket-notation child selector ($['store']['book'])
- Wildcard selector (*)
- Array indices and slicing ($[0], $[1:4], $[-1])
- Recursive descent (..price or $..author)
- Pretty-prints query results as JSON
"""

import argparse
import json
import re
import sys
from typing import Any, List, Union

# Regex to parse JSONPath query segments
# Matches:
# 1. Recursive descent operator: '..'
# 2. Bracket selector: '\[(.*?)\]'
# 3. Dot selector: '\.([a-zA-Z0-9_-]+)'
SEGMENT_REGEX = re.compile(r'(\.\.)|\[(.*?)\]|\.([a-zA-Z0-9_-]+)')

class JSONPathEvaluator:
    def __init__(self, expression: str):
        self.expression = expression.strip()
        self.segments = self._tokenize(self.expression)

    def _tokenize(self, expr: str) -> List[Union[str, int, slice]]:
        """Parses a JSONPath expression string into evaluation steps."""
        if not expr.startswith('$'):
            raise ValueError("JSONPath expression must start with '$'")
        
        # Remove the leading '$'
        expr = expr[1:]
        if not expr:
            return []

        tokens: List[Any] = []
        pos = 0
        
        while pos < len(expr):
            # 1. Match recursive descent '..'
            if expr[pos:].startswith('..'):
                tokens.append('..')
                pos += 2
                continue
                
            # 2. Match standard segments
            match = SEGMENT_REGEX.match(expr, pos)
            if not match:
                # Fallback / Error check: if we have leftover chars we couldn't parse
                remaining = expr[pos:]
                # Try simple dot notation for remaining if it doesn't match SEGMENT_REGEX
                if remaining.startswith('.'):
                    # Skip dot and parse next word
                    remaining = remaining[1:]
                word_match = re.match(r'^([a-zA-Z0-9_-]+)', remaining)
                if word_match:
                    tokens.append(word_match.group(1))
                    pos += len(word_match.group(0)) + (1 if expr[pos] == '.' else 0)
                    continue
                else:
                    raise ValueError(f"Unable to parse expression starting at position {pos + 1}: '{expr[pos:]}'")
            
            rec, bracket, dot = match.groups()
            
            if rec:
                tokens.append('..')
                pos += 2
            elif bracket:
                # Handle bracket contents (can be string, index, slice, or wildcard)
                bracket = bracket.strip()
                if (bracket.startswith("'") and bracket.endswith("'")) or (bracket.startswith('"') and bracket.endswith('"')):
                    # String key e.g. ['store']
                    tokens.append(bracket[1:-1])
                elif bracket == '*':
                    # Wildcard e.g. [*]
                    tokens.append('*')
                elif ':' in bracket:
                    # Slice e.g. [1:4] or [:] or [::2]
                    parts = bracket.split(':')
                    start = int(parts[0]) if parts[0] else None
                    end = int(parts[1]) if len(parts) > 1 and parts[1] else None
                    step = int(parts[2]) if len(parts) > 2 and parts[2] else None
                    tokens.append(slice(start, end, step))
                else:
                    # Single index e.g. [0] or [-1]
                    try:
                        tokens.append(int(bracket))
                    except ValueError:
                        # Fallback as string key without quotes
                        tokens.append(bracket)
                pos += len(match.group(0))
            elif dot:
                # Dot property name e.g. .store
                tokens.append(dot)
                pos += len(match.group(0))

        return tokens

    def evaluate(self, data: Any) -> List[Any]:
        """Evaluates the parsed segments against the JSON data structure."""
        current_nodes = [data]
        i = 0
        
        while i < len(self.segments):
            seg = self.segments[i]
            next_nodes = []
            
            if seg == '..':
                # Recursive descent: collect all nodes and subnodes, then apply the next token
                if i + 1 >= len(self.segments):
                    raise ValueError("Recursive descent '..' cannot be at the end of expression")
                
                next_seg = self.segments[i + 1]
                # Gather all nodes recursively
                all_descendants = []
                for node in current_nodes:
                    self._collect_all_nodes(node, all_descendants)
                
                # Apply the next segment to all descendants
                for node in all_descendants:
                    next_nodes.extend(self._apply_segment(node, next_seg))
                
                i += 2  # Skip '..' and the next segment we just processed
                current_nodes = next_nodes
                continue

            for node in current_nodes:
                next_nodes.extend(self._apply_segment(node, seg))
            
            current_nodes = next_nodes
            i += 1

        return current_nodes

    def _apply_segment(self, node: Any, seg: Union[str, int, slice]) -> List[Any]:
        """Applies a single token segment to a JSON node."""
        results = []
        
        if isinstance(seg, str):
            if seg == '*':
                # Wildcard: return all dict values or list elements
                if isinstance(node, dict):
                    results.extend(node.values())
                elif isinstance(node, list):
                    results.extend(node)
            elif isinstance(node, dict) and seg in node:
                # Standard key look up
                results.append(node[seg])
                
        elif isinstance(seg, int):
            if isinstance(node, list):
                try:
                    results.append(node[seg])
                except IndexError:
                    pass
                    
        elif isinstance(seg, slice):
            if isinstance(node, list):
                try:
                    results.extend(node[seg])
                except (IndexError, TypeError):
                    pass
                    
        return results

    def _collect_all_nodes(self, node: Any, collection: List[Any]) -> None:
        """Helper to recursively collect all dictionary values and array items."""
        # Include current node
        collection.append(node)
        
        if isinstance(node, dict):
            for val in node.values():
                self._collect_all_nodes(val, collection)
        elif isinstance(node, list):
            for item in node:
                self._collect_all_nodes(item, collection)


def main():
    parser = argparse.ArgumentParser(
        description="Filter and query JSON structures using standard JSONPath expressions."
    )
    parser.add_argument(
        "expression",
        help="JSONPath query expression (e.g. '$.store.book[*].author' or '$..price')."
    )
    parser.add_argument(
        "file",
        nargs="?",
        type=argparse.FileType("r", encoding="utf-8"),
        default=sys.stdin,
        help="Path to JSON file. Reads from standard input if omitted."
    )
    parser.add_argument(
        "-p", "--pretty",
        action="store_true",
        help="Format output JSON with indentation (default: single-line output)."
    )

    args = parser.parse_args()

    # Read and parse input JSON
    try:
        raw_data = args.file.read().strip()
        if not raw_data:
            print("Error: Empty input JSON.", file=sys.stderr)
            sys.exit(1)
        data = json.loads(raw_data)
    except json.JSONDecodeError as e:
        print(f"Error parsing JSON: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error reading input: {e}", file=sys.stderr)
        sys.exit(1)

    # Evaluate JSONPath
    try:
        evaluator = JSONPathEvaluator(args.expression)
        results = evaluator.evaluate(data)
        
        # Format output
        indent = 2 if args.pretty else None
        output = json.dumps(results, indent=indent, ensure_ascii=False)
        print(output)
        
    except ValueError as e:
        print(f"Query Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Execution Error: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
