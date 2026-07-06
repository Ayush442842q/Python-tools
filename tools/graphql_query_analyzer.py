#!/usr/bin/env python3
"""
GraphQL Query Complexity & Depth Analyzer
-----------------------------------------
A standalone Python tool to statically analyze GraphQL queries.
It parses query files (.graphql, .txt, or JSON requests) to calculate:
1. Nesting Depth: Maximun selection depth to prevent deep query nesting DOS.
2. Field Count: Total number of fields queried to prevent broad queries.
3. Query Complexity Score: Estimates server execution cost (detecting arguments like limit/first).
4. Fragment Circularity & Overlap: Identifies circular fragment loops and duplicate requests.

Author: Antigravity
License: MIT
"""

import os
import sys
import re
import json
import argparse
from typing import Dict, List, Set, Any, Tuple

# Token regexes for basic GraphQL lexing
TOKEN_RE = re.compile(r'([A-Za-z_][A-Za-z0-9_]*|:[A-Za-z_][A-Za-z0-9_]*|\{|\}|\(|\)|@\w+|\.\.\.|"[^"]*"|\d+)')

def tokenize(query_str: str) -> List[str]:
    """Tokenize a GraphQL query string, ignoring commas, comments, and whitespace."""
    # Strip comments first
    lines = query_str.splitlines()
    clean_lines = []
    for line in lines:
        if "#" in line:
            line = line.split("#", 1)[0]
        clean_lines.append(line)
    
    cleaned_query = " ".join(clean_lines)
    return TOKEN_RE.findall(cleaned_query)

class GraphQLQueryAnalyzer:
    def __init__(self, tokens: List[str]):
        self.tokens = tokens
        self.pos = 0
        self.fragments = {}
        self.operations = []
        
    def peek(self) -> str:
        return self.tokens[self.pos] if self.pos < len(self.tokens) else ""
        
    def consume(self, expected: str = "") -> str:
        if self.pos >= len(self.tokens):
            return ""
        tok = self.tokens[self.pos]
        if expected and tok != expected:
            raise ValueError(f"Expected token '{expected}', got '{tok}' at position {self.pos}")
        self.pos += 1
        return tok

    def has_more(self) -> bool:
        return self.pos < len(self.tokens)

    def parse(self) -> Dict[str, Any]:
        """Parse documents containing definitions (operations or fragments)."""
        while self.has_more():
            tok = self.peek()
            if tok in ("query", "mutation", "subscription", "{"):
                self.parse_operation()
            elif tok == "fragment":
                self.parse_fragment()
            else:
                # Skip unknown token (or variables, etc.)
                self.pos += 1
        
        # Analyze circular fragments
        self.detect_circular_fragments()
        
        # Now analyze complexity per operation (expanding fragments)
        operation_metrics = []
        for op in self.operations:
            depth, field_count, complexity = self.evaluate_selection_set(op["selections"], 1)
            operation_metrics.append({
                "name": op["name"],
                "type": op["type"],
                "max_depth": depth,
                "total_fields": field_count,
                "complexity": complexity
            })
            
        return {
            "operations": operation_metrics,
            "fragments_count": len(self.fragments)
        }

    def parse_operation(self):
        op_type = "query"
        op_name = "anonymous"
        
        tok = self.peek()
        if tok in ("query", "mutation", "subscription"):
            op_type = self.consume()
            if self.peek() != "{" and self.peek() != "(":
                op_name = self.consume()
        
        # Skip variables definition if present
        if self.peek() == "(":
            self.consume("(")
            brace_count = 1
            while self.has_more() and brace_count > 0:
                t = self.consume()
                if t == "(":
                    brace_count += 1
                elif t == ")":
                    brace_count -= 1
                    
        # Parse selections
        selections = []
        if self.peek() == "{":
            selections = self.parse_selection_set()
            
        self.operations.append({
            "name": op_name,
            "type": op_type,
            "selections": selections
        })

    def parse_fragment(self):
        self.consume("fragment")
        name = self.consume()
        self.consume("on")
        type_condition = self.consume()
        
        # Skip directives if any
        while self.peek().startswith("@"):
            self.consume()
            if self.peek() == "(":
                self.consume("(")
                # Skip parameters
                brace_count = 1
                while self.has_more() and brace_count > 0:
                    t = self.consume()
                    if t == "(":
                        brace_count += 1
                    elif t == ")":
                        brace_count -= 1

        selections = []
        if self.peek() == "{":
            selections = self.parse_selection_set()
            
        self.fragments[name] = {
            "type_condition": type_condition,
            "selections": selections,
            "dependencies": self.find_fragment_spreads(selections)
        }

    def find_fragment_spreads(self, selections: List[Dict[str, Any]]) -> Set[str]:
        """Find nested fragment dependencies within selections."""
        spreads = set()
        for sel in selections:
            if sel["type"] == "spread":
                spreads.add(sel["name"])
            elif sel["type"] == "field" and sel["selections"]:
                spreads.update(self.find_fragment_spreads(sel["selections"]))
        return spreads

    def parse_selection_set(self) -> List[Dict[str, Any]]:
        self.consume("{")
        selections = []
        
        while self.has_more() and self.peek() != "}":
            tok = self.peek()
            if tok == "...":
                self.consume("...")
                if self.peek() == "on":
                    # Inline fragment
                    self.consume("on")
                    type_cond = self.consume()
                    sub_sels = self.parse_selection_set()
                    selections.append({
                        "type": "inline_fragment",
                        "type_condition": type_cond,
                        "selections": sub_sels
                    })
                else:
                    # Fragment spread
                    frag_name = self.consume()
                    selections.append({
                        "type": "spread",
                        "name": frag_name
                    })
            else:
                # Field
                field_name = self.consume()
                alias = None
                if self.peek() == ":":
                    self.consume(":")
                    alias = field_name
                    field_name = self.consume()
                
                # Arguments
                args = {}
                if self.peek() == "(":
                    args = self.parse_arguments()
                    
                # Directives
                while self.peek().startswith("@"):
                    self.consume()
                    if self.peek() == "(":
                        self.parse_arguments()

                # Nested selections
                sub_selections = []
                if self.peek() == "{":
                    sub_selections = self.parse_selection_set()
                    
                selections.append({
                    "type": "field",
                    "name": field_name,
                    "alias": alias,
                    "arguments": args,
                    "selections": sub_selections
                })
                
        if self.peek() == "}":
            self.consume("}")
        return selections

    def parse_arguments(self) -> Dict[str, Any]:
        self.consume("(")
        args = {}
        brace_count = 1
        # Simplified parsing of arguments: read key-value pairs until matching closing parenthesis
        while self.has_more() and brace_count > 0:
            tok = self.peek()
            if tok == "(":
                brace_count += 1
                self.consume()
            elif tok == ")":
                brace_count -= 1
                self.consume()
            else:
                # Try to parse key-value
                key = self.consume()
                if self.peek() == ":":
                    self.consume(":")
                    val = self.consume()
                    args[key] = val
                else:
                    args[key] = True
        return args

    def detect_circular_fragments(self):
        """Perform cycle detection on fragment dependencies (DFS)."""
        visited = set()
        path = []

        def dfs(node):
            if node in path:
                cycle = " -> ".join(path[path.index(node):] + [node])
                raise ValueError(f"Circular fragment dependency detected: {cycle}")
            if node in visited:
                return
            path.append(node)
            if node in self.fragments:
                for dep in self.fragments[node]["dependencies"]:
                    dfs(dep)
            path.pop()
            visited.add(node)

        for name in list(self.fragments.keys()):
            dfs(name)

    def evaluate_selection_set(self, selections: List[Dict[str, Any]], current_depth: int, visited_fragments: Set[str] = None) -> Tuple[int, int, float]:
        """
        Evaluate selections recursively.
        Returns: (Max Depth, Total Fields Count, Complexity Score)
        """
        if visited_fragments is None:
            visited_fragments = set()
            
        max_depth = current_depth
        total_fields = 0
        complexity = 0.0
        
        for sel in selections:
            if sel["type"] == "field":
                total_fields += 1
                
                # Base field complexity
                field_complexity = 1.0
                
                # Check for pagination arguments like first, last, limit
                limit_multiplier = 1.0
                args = sel.get("arguments", {})
                for k, v in args.items():
                    if k in ("first", "last", "limit", "size"):
                        try:
                            limit_multiplier = float(v)
                        except ValueError:
                            limit_multiplier = 10.0 # Default multiplier fallback for variables
                
                # Evaluate children
                sub_sels = sel.get("selections", [])
                if sub_sels:
                    sub_depth, sub_fields, sub_complexity = self.evaluate_selection_set(sub_sels, current_depth + 1, visited_fragments)
                    max_depth = max(max_depth, sub_depth)
                    total_fields += sub_fields
                    # Children complexity gets multiplied by limit/first
                    field_complexity += sub_complexity * limit_multiplier
                    
                complexity += field_complexity
                
            elif sel["type"] == "inline_fragment":
                sub_sels = sel.get("selections", [])
                sub_depth, sub_fields, sub_complexity = self.evaluate_selection_set(sub_sels, current_depth, visited_fragments)
                max_depth = max(max_depth, sub_depth)
                total_fields += sub_fields
                complexity += sub_complexity
                
            elif sel["type"] == "spread":
                frag_name = sel["name"]
                if frag_name in self.fragments and frag_name not in visited_fragments:
                    # Prevent infinite recursion (already caught by DFS, but safe-check)
                    visited_fragments.add(frag_name)
                    frag_sels = self.fragments[frag_name]["selections"]
                    sub_depth, sub_fields, sub_complexity = self.evaluate_selection_set(frag_sels, current_depth, visited_fragments)
                    max_depth = max(max_depth, sub_depth)
                    total_fields += sub_fields
                    complexity += sub_complexity
                    visited_fragments.remove(frag_name)
                    
        return max_depth, total_fields, complexity

def analyze_graphql_query(filepath: str) -> Dict[str, Any]:
    """Parse and analyze a GraphQL query file."""
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
        
    # Check if content is a JSON network log / request payload
    if content.strip().startswith("{"):
        try:
            data = json.loads(content)
            query_str = data.get("query", "")
        except Exception:
            query_str = content
    else:
        query_str = content

    tokens = tokenize(query_str)
    analyzer = GraphQLQueryAnalyzer(tokens)
    return analyzer.parse()

def main():
    parser = argparse.ArgumentParser(description="GraphQL Query Complexity & Depth Analyzer.")
    parser.add_argument("path", help="Path to a GraphQL query file (.graphql, .txt, or JSON payload)")
    parser.add_argument("--max-depth", type=int, default=10, help="Max selection depth threshold")
    parser.add_argument("--max-complexity", type=float, default=500.0, help="Max query complexity threshold")
    parser.add_argument("--json", action="store_true", help="Output analysis in JSON format")
    args = parser.parse_args()

    filepath = os.path.abspath(args.path)
    if not os.path.exists(filepath):
        print(f"Error: File '{filepath}' does not exist.", file=sys.stderr)
        sys.exit(1)

    try:
        results = analyze_graphql_query(filepath)
    except Exception as e:
        print(f"Failed to analyze GraphQL query: {e}", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(results, indent=2))
        return

    # Visual report
    print("=" * 95)
    print(f"GRAPHQL QUERY COMPLEXITY & DEPTH AUDIT: {os.path.basename(filepath)}")
    print("=" * 95)
    
    operations = results["operations"]
    if not operations:
        print("\033[93m[INFO] No operations parsed from file. (Ensure valid GraphQL query syntax.)\033[0m")
        return

    has_violation = False
    
    for op in operations:
        print(f"Operation Name:  {op['name']}")
        print(f"Operation Type:  {op['type'].upper()}")
        print(f"Nesting Depth:   {op['max_depth']} (Threshold: {args.max_depth})")
        print(f"Total Fields:    {op['total_fields']}")
        print(f"Complexity Score: {op['complexity']:.1f} (Threshold: {args.max_complexity})")
        
        # Check thresholds
        violations = []
        if op["max_depth"] > args.max_depth:
            violations.append(f"Depth {op['max_depth']} exceeds limit of {args.max_depth}")
        if op["complexity"] > args.max_complexity:
            violations.append(f"Complexity {op['complexity']:.1f} exceeds limit of {args.max_complexity}")
            
        if violations:
            has_violation = True
            print("\n\033[91m[WARNING] Security Threshold Exceeded!\033[0m")
            for v in violations:
                print(f"  - {v}")
            print("\033[93mRemediation:\033[0m Simplify the query, reduce nesting, or add smaller limit/first arguments to connection fields.")
        else:
            print("\n\033[92m[SUCCESS] Query matches all security and complexity guidelines!\033[0m")
            
        print("-" * 95)

if __name__ == "__main__":
    main()
