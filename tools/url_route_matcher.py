#!/usr/bin/env python3
"""
URL Route Pattern Matcher - Parses and tests URL route patterns (Flask, Django, Express-style)
against target paths. Extracts parameters, validates formats, and prints match details.
"""

import argparse
import re
import sys
import json

# Route converters and their regex equivalents
CONVERTERS = {
    'int': (r'\d+', int),
    'float': (r'\d+(?:\.\d+)?', float),
    'path': (r'.+', str),
    'string': (r'[^/]+', str),
    'uuid': (r'[a-fA-F0-9]{8}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{4}-[a-fA-F0-9]{12}', str),
    'any': (r'[^/]+', str)  # default
}

def parse_flask_pattern(pattern):
    """
    Converts Flask/Django-style route: /user/<int:id>/profile or /post/<title>
    to a regex pattern and parameter converters.
    """
    # Regex to find <converter:name> or <name>
    rule_re = re.compile(r'<(?:(?P<converter>[a-zA-Z_][a-zA-Z0-9_]*):)?(?P<name>[a-zA-Z_][a-zA-Z0-9_]*)>')
    
    parts = []
    converters = {}
    last = 0
    
    for match in rule_re.finditer(pattern):
        parts.append(re.escape(pattern[last:match.start()]))
        converter_name = match.group('converter') or 'any'
        param_name = match.group('name')
        
        if converter_name not in CONVERTERS:
            # Treat unknown converters as generic string
            converter_name = 'any'
            
        regex_str, cast_func = CONVERTERS[converter_name]
        parts.append(f'(?P<{param_name}>{regex_str})')
        converters[param_name] = cast_func
        last = match.end()
        
    parts.append(re.escape(pattern[last:]))
    # Match full string, ignoring trailing slash optionally
    regex_pattern = '^' + ''.join(parts) + '/?$'
    return re.compile(regex_pattern), converters

def parse_express_pattern(pattern):
    """
    Converts Express/Sinatra-style route: /user/:id/profile or /categories/*
    to a regex pattern and parameter converters.
    """
    parts = []
    converters = {}
    last = 0
    
    # Match :param or *
    rule_re = re.compile(r'(?::(?P<name>[a-zA-Z_][a-zA-Z0-9_]*))|(?P<wildcard>\*)')
    
    wildcard_count = 0
    for match in rule_re.finditer(pattern):
        parts.append(re.escape(pattern[last:match.start()]))
        if match.group('wildcard'):
            wildcard_count += 1
            param_name = f'wildcard_{wildcard_count}'
            parts.append(f'(?P<{param_name}>.*)')
            converters[param_name] = str
        else:
            param_name = match.group('name')
            parts.append(f'(?P<{param_name}>[^/]+)')
            converters[param_name] = str
        last = match.end()
        
    parts.append(re.escape(pattern[last:]))
    regex_pattern = '^' + ''.join(parts) + '/?$'
    return re.compile(regex_pattern), converters

def match_route(pattern, path, style='flask'):
    """
    Attempts to match path against pattern using selected style.
    Returns (is_match, parsed_params, error_msg).
    """
    try:
        # Clean path by stripping domain if fully qualified URL is passed
        if '://' in path:
            # Simple URL parser helper
            path_part = path.split('://', 1)[1]
            if '/' in path_part:
                path = '/' + path_part.split('/', 1)[1]
            else:
                path = '/'
        
        # Remove query parameters for matching
        if '?' in path:
            path = path.split('?', 1)[0]
            
        if style.lower() == 'flask':
            regex, converters = parse_flask_pattern(pattern)
        elif style.lower() == 'express':
            regex, converters = parse_express_pattern(pattern)
        else:
            return False, {}, f"Unsupported routing style: {style}"
            
        match = regex.match(path)
        if not match:
            return False, {}, "Path does not match pattern"
            
        params = {}
        for name, value in match.groupdict().items():
            if value is not None:
                # Convert the value using converter function
                cast_func = converters.get(name, str)
                try:
                    params[name] = cast_func(value)
                except ValueError:
                    return False, {}, f"Value '{value}' for parameter '{name}' could not be converted"
                    
        return True, params, None
    except Exception as e:
        return False, {}, f"Matching error: {str(e)}"

def main():
    parser = argparse.ArgumentParser(description="URL Route Pattern Matcher & API Router Debugger.")
    parser.add_argument("pattern", help="Route pattern to test (e.g. '/api/user/<int:id>' or '/api/user/:id')")
    parser.add_argument("path", help="Path or URL to match against the pattern")
    parser.add_argument("-s", "--style", choices=["flask", "express"], default="flask",
                        help="Routing pattern syntax style: flask (default, e.g. <int:id>) or express (e.g. :id, *)")
    parser.add_argument("-j", "--json", action="store_true", help="Output results in JSON format")
    
    args = parser.parse_args()
    
    is_match, params, error = match_route(args.pattern, args.path, args.style)
    
    if args.json:
        result = {
            "pattern": args.pattern,
            "path": args.path,
            "style": args.style,
            "matched": is_match,
            "parameters": params
        }
        if error:
            result["error"] = error
        print(json.dumps(result, indent=2))
    else:
        print(f"Route Matcher Report")
        print(f"====================")
        print(f"Pattern: {args.pattern}")
        print(f"Path:    {args.path}")
        print(f"Style:   {args.style}")
        print(f"--------------------")
        if is_match:
            print(" Result:  MATCHED \u2713")
            if params:
                print(" Parameters:")
                for k, v in params.items():
                    print(f"   - {k}: {repr(v)} ({type(v).__name__})")
            else:
                print(" Parameters: None (Static route)")
        else:
            print(" Result:  FAILED \u2717")
            print(f" Reason:  {error}")
            
    sys.exit(0 if is_match else 1)

if __name__ == "__main__":
    main()
