#!/usr/bin/env python3
"""
Mock GraphQL Server & Schema Explorer

Launches a local, lightweight mock GraphQL server.
Features:
- Serve GraphQL endpoint over POST/GET on `/graphql` (or custom endpoint)
- Built-in schema (Users, Posts, Comments) with mock database state
- Basic GraphQL AST-like parser to resolve nested fields and arguments (e.g., query, variables)
- Auto-generates mock data or updates memory state for mutations
- Serves a graphical Query Explorer web dashboard at `http://localhost:port/`
- Logs all incoming GraphQL operations, variables, and status codes to the terminal
"""

import sys
import os
import argparse
import json
import re
import random
import http.server
import socketserver
import urllib.parse

# Default mock database state
MOCK_DB = {
    "users": [
        {"id": "1", "name": "Alice Vance", "email": "alice@example.com", "role": "ADMIN"},
        {"id": "2", "name": "Bob Miller", "email": "bob@example.com", "role": "USER"},
        {"id": "3", "name": "Charlie Brown", "email": "charlie@example.com", "role": "USER"},
    ],
    "posts": [
        {"id": "101", "title": "Introduction to GraphQL", "content": "GraphQL is a query language for APIs...", "authorId": "1"},
        {"id": "102", "title": "Building Mock Servers", "content": "Mock servers help speed up client development.", "authorId": "2"},
        {"id": "103", "title": "Python Standard Library Rocks", "content": "No dependencies required!", "authorId": "1"},
    ],
    "comments": [
        {"id": "201", "postId": "101", "authorId": "2", "text": "Great introduction!"},
        {"id": "202", "postId": "101", "authorId": "3", "text": "Very clean, thanks."},
        {"id": "203", "postId": "102", "authorId": "1", "text": "This mock server is fast."},
    ]
}

# Web query runner interface HTML/JS
EXPLORER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>GraphQL Mock Explorer</title>
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: #1e1e24;
            color: #e2e8f0;
            margin: 0;
            padding: 20px;
            display: flex;
            flex-direction: column;
            height: 100vh;
            box-sizing: border-box;
        }
        h1 {
            margin-top: 0;
            color: #805ad5;
            font-size: 24px;
            border-bottom: 1px solid #4a5568;
            padding-bottom: 10px;
        }
        .container {
            display: flex;
            flex: 1;
            gap: 20px;
            min-height: 0;
        }
        .panel {
            flex: 1;
            display: flex;
            flex-direction: column;
            background-color: #2d3748;
            border-radius: 8px;
            padding: 15px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.3);
        }
        .panel-title {
            font-weight: bold;
            margin-bottom: 10px;
            color: #a0aec0;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        textarea, pre {
            flex: 1;
            background-color: #1a202c;
            color: #48bb78;
            border: 1px solid #4a5568;
            border-radius: 4px;
            padding: 12px;
            font-family: "Fira Code", Monaco, Consolas, monospace;
            font-size: 14px;
            resize: none;
            outline: none;
            overflow-y: auto;
        }
        pre {
            color: #38bdf8;
            margin: 0;
        }
        button {
            background-color: #805ad5;
            color: white;
            border: none;
            border-radius: 4px;
            padding: 10px 20px;
            font-weight: bold;
            cursor: pointer;
            transition: background-color 0.2s;
        }
        button:hover {
            background-color: #9f7aea;
        }
        .schema-list {
            font-size: 12px;
            color: #cbd5e0;
            background-color: #1a202c;
            padding: 8px;
            border-radius: 4px;
            max-height: 120px;
            overflow-y: auto;
        }
    </style>
</head>
<body>
    <h1>⚡ GraphQL Mock Server Explorer</h1>
    <div style="margin-bottom: 15px;">
        <strong>API Endpoint:</strong> <code>/graphql</code> (POST)
    </div>
    <div class="container">
        <div class="panel">
            <div class="panel-title">
                <span>GraphQL Query</span>
                <button onclick="runQuery()">Run Query</button>
            </div>
            <textarea id="query" placeholder="Enter GraphQL query here...">query GetUsersAndPosts {
  users {
    id
    name
    email
  }
  posts {
    id
    title
    author {
      name
    }
  }
}</textarea>
            <div style="margin-top: 10px;">
                <div class="panel-title">Query Variables (JSON)</div>
                <textarea id="variables" style="height: 60px; flex: none;">{}</textarea>
            </div>
        </div>
        
        <div class="panel">
            <div class="panel-title">Response JSON</div>
            <pre id="response">// Response will load here...</pre>
            <div style="margin-top: 10px;">
                <div class="panel-title">Available Mock Schema Types</div>
                <div class="schema-list">
                    <strong>Query:</strong> users, user(id: ID), posts, post(id: ID)<br>
                    <strong>Mutation:</strong> createUser(name: String!, email: String!, role: String)<br>
                    <strong>Types:</strong> User { id, name, email, role, posts }, Post { id, title, content, author, comments }, Comment { id, text, author }
                </div>
            </div>
        </div>
    </div>

    <script>
        async function runQuery() {
            const queryText = document.getElementById('query').value;
            let variablesText = document.getElementById('variables').value;
            const responseBlock = document.getElementById('response');
            
            responseBlock.textContent = "Running query...";
            
            let variablesObj = {};
            try {
                if (variablesText.trim()) {
                    variablesObj = JSON.parse(variablesText);
                }
            } catch(e) {
                responseBlock.textContent = "Error parsing variables JSON:\\n" + e.message;
                return;
            }
            
            try {
                const response = await fetch('/graphql', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        query: queryText,
                        variables: variablesObj
                    })
                });
                
                const data = await response.json();
                responseBlock.textContent = JSON.stringify(data, null, 2);
            } catch(e) {
                responseBlock.textContent = "Network Error:\\n" + e.message;
            }
        }
    </script>
</body>
</html>
"""

def parse_graphql_fields(query_str):
    """
    Super simple regex/token parser to extract requested fields from a GraphQL query.
    Extracts high-level queries, arguments, and curly-bracket children module structures.
    """
    # Clean whitespace and comments
    cleaned = re.sub(r'#.*', '', query_str)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    
    # Extract query/mutation type and operations
    # Simple extraction of everything between the outer braces
    braces_match = re.search(r'\{(.*)\}', cleaned)
    if not braces_match:
        return {}
        
    inner = braces_match.group(1).strip()
    return parse_selection_set(inner)

def parse_selection_set(selection_str):
    """Parses a selection string e.g. 'id name email posts { title }' into a tree structure."""
    tokens = []
    # Tokenize by tracking nested structures
    depth = 0
    current_token = []
    
    for char in selection_str:
        if char == '{':
            depth += 1
            current_token.append(char)
        elif char == '}':
            depth -= 1
            current_token.append(char)
        elif char in (',', ' ') and depth == 0:
            if current_token:
                tokens.append("".join(current_token).strip())
                current_token = []
        else:
            current_token.append(char)
            
    if current_token:
        tokens.append("".join(current_token).strip())
        
    tokens = [t for t in tokens if t]
    
    fields = {}
    i = 0
    while i < len(tokens):
        token = tokens[i]
        
        # Check if field has arguments e.g., user(id: "1")
        arg_match = re.match(r'([a-zA-Z_0-9]+)\(([^)]+)\)', token)
        field_name = token
        args = {}
        
        if arg_match:
            field_name = arg_match.group(1)
            raw_args = arg_match.group(2)
            # Parse simple argument pairs (key: value)
            for pair in re.split(r',\s*', raw_args):
                if ':' in pair:
                    k, v = pair.split(':', 1)
                    # Strip quotes from arguments
                    args[k.strip()] = v.strip().strip('"').strip("'")
                    
        # Check if next token is a nested selection block
        nested = {}
        if i + 1 < len(tokens) and tokens[i+1].startswith('{'):
            nested_str = tokens[i+1][1:-1].strip()
            nested = parse_selection_set(nested_str)
            i += 1
            
        fields[field_name] = {"args": args, "fields": nested}
        i += 1
        
    return fields

def resolve_query(query_tree, variables=None):
    """Executes mock resolvers based on the query tree representation."""
    data = {}
    errors = []
    
    if variables is None:
        variables = {}
        
    for op_name, op_details in query_tree.items():
        args = op_details.get("args", {})
        # Resolve variables in args
        for k, v in args.items():
            if v.startswith('$'):
                var_name = v[1:]
                args[k] = variables.get(var_name, None)
                
        sub_fields = op_details.get("fields", {})
        
        # Resolver: users
        if op_name == 'users':
            user_list = []
            for u in MOCK_DB["users"]:
                user_list.append(resolve_user(u, sub_fields))
            data[op_name] = user_list
            
        # Resolver: user(id)
        elif op_name == 'user':
            user_id = args.get('id')
            user_obj = next((u for u in MOCK_DB["users"] if u["id"] == str(user_id)), None)
            if user_obj:
                data[op_name] = resolve_user(user_obj, sub_fields)
            else:
                data[op_name] = None
                
        # Resolver: posts
        elif op_name == 'posts':
            post_list = []
            for p in MOCK_DB["posts"]:
                post_list.append(resolve_post(p, sub_fields))
            data[op_name] = post_list
            
        # Resolver: post(id)
        elif op_name == 'post':
            post_id = args.get('id')
            post_obj = next((p for p in MOCK_DB["posts"] if p["id"] == str(post_id)), None)
            if post_obj:
                data[op_name] = resolve_post(post_obj, sub_fields)
            else:
                data[op_name] = None
                
        # Resolver: Mutation createUser
        elif op_name == 'createUser':
            new_id = str(len(MOCK_DB["users"]) + 1)
            new_user = {
                "id": new_id,
                "name": args.get('name', 'Unnamed User'),
                "email": args.get('email', 'unknown@example.com'),
                "role": args.get('role', 'USER')
            }
            MOCK_DB["users"].append(new_user)
            data[op_name] = resolve_user(new_user, sub_fields)
            
        else:
            # Catch-all fallback default resolver
            errors.append({"message": f"Cannot resolve field '{op_name}' on Query type."})
            
    return data, errors

def resolve_user(user_dict, sub_fields):
    """Resolves fields on User type, including relational fields (posts)."""
    res = {}
    for f in sub_fields:
        if f in user_dict:
            res[f] = user_dict[f]
        elif f == 'posts':
            # Author's posts relation
            user_posts = [p for p in MOCK_DB["posts"] if p["authorId"] == user_dict["id"]]
            nested_fields = sub_fields[f].get("fields", {})
            res[f] = [resolve_post(p, nested_fields) for p in user_posts]
    # If no fields requested, fallback
    return res if res else user_dict

def resolve_post(post_dict, sub_fields):
    """Resolves fields on Post type, including relations (author, comments)."""
    res = {}
    for f in sub_fields:
        if f in post_dict:
            res[f] = post_dict[f]
        elif f == 'author':
            # Author relation
            author = next((u for u in MOCK_DB["users"] if u["id"] == post_dict["authorId"]), None)
            nested_fields = sub_fields[f].get("fields", {})
            res[f] = resolve_user(author, nested_fields) if author else None
        elif f == 'comments':
            # Post comments relation
            comments = [c for c in MOCK_DB["comments"] if c["postId"] == post_dict["id"]]
            nested_fields = sub_fields[f].get("fields", {})
            res[f] = [resolve_comment(c, nested_fields) for c in comments]
    return res if res else post_dict

def resolve_comment(comment_dict, sub_fields):
    """Resolves fields on Comment type, including relation (author)."""
    res = {}
    for f in sub_fields:
        if f in comment_dict:
            res[f] = comment_dict[f]
        elif f == 'author':
            author = next((u for u in MOCK_DB["users"] if u["id"] == comment_dict["authorId"]), None)
            nested_fields = sub_fields[f].get("fields", {})
            res[f] = resolve_user(author, nested_fields) if author else None
    return res if res else comment_dict

class GraphQLHTTPServerHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Prevent default console logs to output neat colored execution messages
        pass
        
    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        
        # Render Schema Explorer Web Interface on Root
        if parsed_path.path == '/':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(EXPLORER_HTML.encode('utf-8'))
            return
            
        # Support GraphQL over GET requests (queries in query parameters)
        if parsed_path.path == '/graphql':
            query_params = urllib.parse.parse_qs(parsed_path.query)
            query_str = query_params.get('query', [''])[0]
            
            if not query_str:
                self.send_graphql_error("Missing query parameter")
                return
                
            variables_str = query_params.get('variables', ['{}'])[0]
            try:
                variables = json.loads(variables_str)
            except Exception:
                variables = {}
                
            self.execute_and_respond(query_str, variables)
            return
            
        # 404 fallback
        self.send_response(404)
        self.end_headers()
        self.wfile.write(b"Not Found")

    def do_POST(self):
        parsed_path = urllib.parse.urlparse(self.path)
        
        if parsed_path.path == '/graphql':
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_graphql_error("Empty request body")
                return
                
            body_bytes = self.rfile.read(content_length)
            
            # Support application/json Content-Type
            content_type = self.headers.get('Content-Type', '')
            query_str = ""
            variables = {}
            
            if 'application/json' in content_type:
                try:
                    payload = json.loads(body_bytes.decode('utf-8'))
                    query_str = payload.get('query', '')
                    variables = payload.get('variables', {})
                    if not isinstance(variables, dict):
                        variables = {}
                except Exception as e:
                    self.send_graphql_error(f"Malformed JSON request payload: {e}")
                    return
            # Support application/graphql content type (raw query in body)
            elif 'application/graphql' in content_type:
                query_str = body_bytes.decode('utf-8')
            else:
                self.send_graphql_error("Unsupported Content-Type. Please use application/json")
                return
                
            self.execute_and_respond(query_str, variables)
            return
            
        self.send_response(404)
        self.end_headers()
        self.wfile.write(b"Not Found")

    def execute_and_respond(self, query_str, variables):
        """Helper to run query, print log, and format JSON response."""
        # Simple logging output
        clean_op = "Query"
        if "mutation" in query_str.lower():
            clean_op = "Mutation"
            
        print(f"\033[94m[GraphQL {clean_op}]\033[0m Operations & Selection parsing...")
        
        try:
            tree = parse_graphql_fields(query_str)
            data, errors = resolve_query(tree, variables)
            
            # Format JSON envelope
            resp_data = {"data": data}
            if errors:
                resp_data["errors"] = errors
                print(f"  \033[91mErrors: {errors}\033[0m")
                
            # Log fields executed
            for field in tree:
                print(f"  → Resolved: \033[92m{field}\033[0m (Arguments: {tree[field]['args']})")
                
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type')
            self.end_headers()
            self.wfile.write(json.dumps(resp_data).encode('utf-8'))
            print("  Status: \033[92m200 OK\033[0m\n")
        except Exception as e:
            print(f"  \033[91mExecution Failure: {e}\033[0m\n")
            self.send_graphql_error(f"Internal GraphQL Server Resolver Error: {e}")

    def send_graphql_error(self, message):
        resp = {"data": None, "errors": [{"message": message}]}
        self.send_response(400)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(resp).encode('utf-8'))
        print(f"  Status: \033[91m400 Bad Request ({message})\033[0m\n")

    def do_OPTIONS(self):
        """CORS preflight handling."""
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

def main():
    parser = argparse.ArgumentParser(
        description="Local Mock GraphQL Server & Schema Explorer."
    )
    parser.add_argument('-p', '--port', type=int, default=8000, help="Port to run the mock server on (default: 8000)")
    parser.add_argument('-b', '--bind', default='127.0.0.1', help="Interface address to bind (default: 127.0.0.1)")
    args = parser.parse_args()

    class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True

    server = ThreadingHTTPServer((args.bind, args.port), GraphQLHTTPServerHandler)
    
    print("\033[95m========================================================\033[0m")
    print(f"⚡ GraphQL Mock Server running at http://{args.bind}:{args.port}/")
    print(f"⚡ Graphical Web UI Explorer:   http://{args.bind}:{args.port}/")
    print(f"⚡ GraphQL API Endpoint:        http://{args.bind}:{args.port}/graphql")
    print("\033[95m========================================================\033[0m")
    print("Listening for GraphQL POST/GET queries (Ctrl+C to terminate)...\n")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nGraphQL Server shut down.")
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
