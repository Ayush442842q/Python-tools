#!/usr/bin/env python3
"""
OAuth 2.0 Authorization Code Flow Simulator

This tool starts a local web server that simulates and visualizes the OAuth 2.0
Authorization Code Flow in real-time. It provides both terminal logging and a
beautiful web UI to guide developers step-by-step through:
    1. Client Redirect to Auth Server (Auth Request)
    2. User Authentication & Scope Consent
    3. Authorization Code Redirect (Callback)
    4. Server-to-Server Code Exchange for Access Token
    5. API Call to Resource Server using the Bearer Token

Requirements:
    - Pure Python 3 (no third-party dependencies)
"""

import sys
import os
import urllib.parse
import http.server
import socketserver
import json
import secrets
import argparse

# ANSI Terminal Colors
COLORS = {
    'green': '\033[32m',
    'yellow': '\033[33m',
    'red': '\033[31m',
    'cyan': '\033[36m',
    'blue': '\033[34m',
    'magenta': '\033[35m',
    'bold': '\033[1m',
    'reset': '\033[0m'
}

def colorize(text, color):
    if sys.stdout.isatty() and color in COLORS:
        return f"{COLORS[color]}{text}{COLORS['reset']}"
    return text

# Simulated Database in memory
CLIENT_ID = "simulated_client_12345"
CLIENT_SECRET = "simulated_client_secret_xyz789"
REDIRECT_URI = "http://localhost:{port}/callback"
USER_PROFILE = {
    "sub": "usr_987654321",
    "name": "Alice Developer",
    "email": "alice@example.com",
    "email_verified": True,
    "role": "Lead Architect",
    "avatar": "https://api.dicebear.com/7.x/bottts/svg?seed=Alice"
}

# Stores active authorization codes and tokens
db = {
    "auth_codes": {}, # code -> {client_id, redirect_uri, scope, state, user}
    "access_tokens": {} # token -> {scope, user}
}

# HTML templates with CSS styling
HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>OAuth 2.0 Simulator</title>
    <style>
        body {{
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #0f172a;
            color: #f8fafc;
            margin: 0;
            padding: 20px;
            display: flex;
            justify-content: center;
        }}
        .container {{
            max-width: 800px;
            width: 100%;
            background: #1e293b;
            border-radius: 12px;
            padding: 30px;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.5);
            border: 1px solid #334155;
        }}
        h1, h2, h3 {{
            color: #38bdf8;
            margin-top: 0;
        }}
        .step-indicator {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 30px;
            background: #0f172a;
            padding: 10px 15px;
            border-radius: 8px;
            font-size: 14px;
        }}
        .step {{
            color: #64748b;
        }}
        .step.active {{
            color: #38bdf8;
            font-weight: bold;
        }}
        .step.completed {{
            color: #4ade80;
        }}
        .code-box {{
            background: #090d16;
            color: #34d399;
            padding: 15px;
            border-radius: 6px;
            font-family: monospace;
            overflow-x: auto;
            border: 1px solid #1e293b;
            margin: 15px 0;
            white-space: pre-wrap;
            word-break: break-all;
        }}
        .btn {{
            display: inline-block;
            background: #0284c7;
            color: white;
            padding: 10px 20px;
            text-decoration: none;
            border-radius: 6px;
            font-weight: 600;
            border: none;
            cursor: pointer;
            transition: background 0.2s;
        }}
        .btn:hover {{
            background: #0369a1;
        }}
        .btn-success {{
            background: #16a34a;
        }}
        .btn-success:hover {{
            background: #15803d;
        }}
        .consent-item {{
            display: flex;
            align-items: center;
            margin: 10px 0;
        }}
        .consent-item input {{
            margin-right: 12px;
            transform: scale(1.2);
        }}
        .profile-card {{
            display: flex;
            align-items: center;
            background: #0f172a;
            padding: 20px;
            border-radius: 8px;
            margin-top: 15px;
        }}
        .profile-card img {{
            width: 80px;
            height: 80px;
            border-radius: 50%;
            margin-right: 20px;
            background: #334155;
            padding: 5px;
        }}
        .profile-info h3 {{
            margin: 0 0 5px 0;
            color: #f8fafc;
        }}
        .profile-info p {{
            margin: 0;
            color: #94a3b8;
        }}
        .info-panel {{
            background: #1e1b4b;
            border-left: 4px solid #6366f1;
            padding: 15px;
            margin: 20px 0;
            border-radius: 0 8px 8px 0;
            font-size: 14px;
            line-height: 1.5;
        }}
        .params-table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
            font-size: 14px;
        }}
        .params-table th, .params-table td {{
            text-align: left;
            padding: 8px 12px;
            border-bottom: 1px solid #334155;
        }}
        .params-table th {{
            color: #94a3b8;
        }}
        .param-name {{
            font-family: monospace;
            color: #f472b6;
        }}
    </style>
</head>
<body>
    <div class="container">
        {content}
    </div>
</body>
</html>
"""

class SimulatorHTTPHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress standard HTTP logger output to keep stdout clean for our own step logs
        pass

    def send_html(self, content, status=200):
        self.send_response(status)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        full_html = HTML_TEMPLATE.format(content=content)
        self.wfile.write(full_html.encode('utf-8'))

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)
        port = self.server.server_address[1]

        if path == "/":
            self.show_client_landing(port)
        elif path == "/auth":
            self.show_auth_consent(query, port)
        elif path == "/consent":
            self.process_consent(query, port)
        elif path == "/callback":
            self.show_callback(query, port)
        elif path == "/api/user":
            self.handle_api_user()
        else:
            self.send_html("<h2>404 Not Found</h2>", 404)

    def do_POST(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        
        if path == "/oauth/token":
            self.handle_token_exchange()
        else:
            self.send_response(404)
            self.end_headers()

    def show_client_landing(self, port):
        state = secrets.token_hex(8)
        auth_url = f"/auth?response_type=code&client_id={CLIENT_ID}&redirect_uri={urllib.parse.quote(REDIRECT_URI.format(port=port))}&scope=profile+email+read:repo&state={state}"
        
        content = f"""
        <div class="step-indicator">
            <span class="step active">1. Client Initiation</span>
            <span class="step">2. Auth & Consent</span>
            <span class="step">3. Authorization Code</span>
            <span class="step">4. Token Exchange</span>
            <span class="step">5. API Request</span>
        </div>
        
        <h2>Step 1: Client Landing Page & Auth Request</h2>
        <p>The client application (this simulator) initiates the OAuth flow by redirecting the user to the Authorization Server with parameters in the query string.</p>
        
        <div class="info-panel">
            <strong>What's happening:</strong><br>
            The user clicks "Login with OAuth". The application generates a unique <code>state</code> parameter to prevent CSRF attacks, specifies the required <code>scope</code> (permissions), and includes its <code>client_id</code> and registered <code>redirect_uri</code>.
        </div>
        
        <h3>Parameters inside Authorization Request URI:</h3>
        <table class="params-table">
            <tr><th>Parameter</th><th>Value</th><th>Description</th></tr>
            <tr><td class="param-name">response_type</td><td><code>code</code></td><td>Requests an Authorization Code flow.</td></tr>
            <tr><td class="param-name">client_id</td><td><code>{CLIENT_ID}</code></td><td>The client's public identifier.</td></tr>
            <tr><td class="param-name">redirect_uri</td><td><code>{REDIRECT_URI.format(port=port)}</code></td><td>Where the auth server redirects the code.</td></tr>
            <tr><td class="param-name">scope</td><td><code>profile email read:repo</code></td><td>The permissions requested by client.</td></tr>
            <tr><td class="param-name">state</td><td><code>{state}</code></td><td>Anti-CSRF random token.</td></tr>
        </table>
        
        <div style="margin-top: 30px;">
            <a href="{auth_url}" class="btn">Initiate OAuth Login Flow &rarr;</a>
        </div>
        """
        self.send_html(content)

    def show_auth_consent(self, query, port):
        # Extract params
        client_id = query.get("client_id", [""])[0]
        redirect_uri = query.get("redirect_uri", [""])[0]
        scope = query.get("scope", [""])[0]
        state = query.get("state", [""])[0]

        print(colorize("\n[Step 1] Received Authorization Request at Server:", 'green'))
        print(f"  client_id:    {client_id}")
        print(f"  redirect_uri: {redirect_uri}")
        print(f"  scope:        {scope}")
        print(f"  state:        {state}")

        if client_id != CLIENT_ID:
            self.send_html("<h2>OAuth Error: Invalid Client ID</h2>", 400)
            return

        consent_url = f"/consent?client_id={client_id}&redirect_uri={urllib.parse.quote(redirect_uri)}&scope={urllib.parse.quote(scope)}&state={state}"

        content = f"""
        <div class="step-indicator">
            <span class="step completed">1. Client Initiation</span>
            <span class="step active">2. Auth & Consent</span>
            <span class="step">3. Authorization Code</span>
            <span class="step">4. Token Exchange</span>
            <span class="step">5. API Request</span>
        </div>
        
        <h2>Step 2: User Login & Scope Consent</h2>
        <p>The user has landed on the <strong>Authorization Server</strong>. Usually, they would enter credentials here. Since this is a simulation, we represent the user session directly.</p>
        
        <div class="info-panel">
            <strong>What's happening:</strong><br>
            The Authorization Server verifies the <code>client_id</code> and matching <code>redirect_uri</code>. It then prompts the user to grant the requested permissions (scopes) to the client application.
        </div>
        
        <div style="background: #0f172a; padding: 20px; border-radius: 8px; margin: 20px 0;">
            <h3 style="color: white; margin-bottom: 15px;">App Permissions Request</h3>
            <p style="font-size: 14px; margin-top: 0; color: #94a3b8;"><strong>Simulator App</strong> wants to access your account details:</p>
            
            <form action="/consent" method="GET">
                <input type="hidden" name="client_id" value="{client_id}">
                <input type="hidden" name="redirect_uri" value="{redirect_uri}">
                <input type="hidden" name="state" value="{state}">
                
                <div class="consent-item">
                    <input type="checkbox" name="scope" value="profile" checked disabled>
                    <label><strong>profile</strong> (Read your profile username, avatar, and metadata)</label>
                </div>
                <div class="consent-item">
                    <input type="checkbox" name="scope" value="email" checked disabled>
                    <label><strong>email</strong> (Access your primary email: <code>{USER_PROFILE['email']}</code>)</label>
                </div>
                <div class="consent-item">
                    <input type="checkbox" name="scope" value="read:repo" checked>
                    <label><strong>read:repo</strong> (Read-only access to your code repositories)</label>
                </div>
                
                <div style="margin-top: 25px; display: flex; gap: 15px;">
                    <button type="submit" class="btn btn-success">Authorize & Approve Access</button>
                    <a href="/" class="btn" style="background: #ef4444;">Deny</a>
                </div>
            </form>
        </div>
        """
        self.send_html(content)

    def process_consent(self, query, port):
        client_id = query.get("client_id", [""])[0]
        redirect_uri = query.get("redirect_uri", [""])[0]
        state = query.get("state", [""])[0]
        
        # Scopes selected (profile & email are guaranteed)
        scopes = ["profile", "email"]
        if "read:repo" in query.get("scope", []):
            scopes.append("read:repo")
        scope_str = " ".join(scopes)

        print(colorize("\n[Step 2] User Granted Consent:", 'green'))
        print(f"  Scopes approved: {scope_str}")

        # Generate a temporary Authorization Code (good for 1 exchange, short lifespan)
        auth_code = f"auth_code_{secrets.token_hex(12)}"
        db["auth_codes"][auth_code] = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope_str,
            "state": state,
            "user": USER_PROFILE
        }

        print(colorize("  Generated Authorization Code: ", 'cyan') + auth_code)

        # Redirect user back to callback with code and state
        redirect_target = f"{redirect_uri}?code={auth_code}&state={state}"
        self.send_response(302)
        self.send_header("Location", redirect_target)
        self.end_headers()

    def show_callback(self, query, port):
        code = query.get("code", [""])[0]
        state = query.get("state", [""])[0]

        print(colorize("\n[Step 3] Client Callback Endpoint Triggered:", 'green'))
        print(f"  code:  {code}")
        print(f"  state: {state}")

        # Check if the code exists in our database
        code_data = db["auth_codes"].get(code)
        if not code_data:
            self.send_html("<h2>OAuth Error: Invalid/Expired Authorization Code</h2>", 400)
            return

        content = f"""
        <div class="step-indicator">
            <span class="step completed">1. Client Initiation</span>
            <span class="step completed">2. Auth & Consent</span>
            <span class="step active">3. Authorization Code</span>
            <span class="step">4. Token Exchange</span>
            <span class="step">5. API Request</span>
        </div>
        
        <h2>Step 3: Authorization Code Callback</h2>
        <p>The Authorization Server redirected the user's browser back to the client's callback URL (this page) with the temporary code.</p>
        
        <div class="info-panel">
            <strong>What's happening:</strong><br>
            The client application validates the returned <code>state</code> to verify the request originated from its session.
            Now, the client will make a secure <strong>server-to-server POST request</strong> to the Token Endpoint to trade the <code>code</code> for an <code>access_token</code>.
        </div>
        
        <h3>Callback URL Parameters:</h3>
        <div class="code-box">
URL: {REDIRECT_URI.format(port=port)}
code:  {code}
state: {state}
        </div>
        
        <form action="/callback" method="GET" id="exchange-form">
            <!-- Hidden inputs to carry state to make next visual step simulation easy -->
            <input type="hidden" name="trigger_exchange" value="true">
            <input type="hidden" name="code" value="{code}">
            <button type="button" onclick="exchangeToken()" class="btn">Perform Server-to-Server Code Exchange &rarr;</button>
        </form>

        <div id="exchange-result" style="margin-top: 30px; display: none;">
            <!-- Will be populated dynamically to make the flow easy to see -->
        </div>

        <script>
            function exchangeToken() {{
                const resultDiv = document.getElementById("exchange-result");
                resultDiv.style.display = "block";
                resultDiv.innerHTML = "<h3>Exchanging code...</h3>";
                
                // Make a secure token request via client mock endpoint
                const params = new URLSearchParams();
                params.append("grant_type", "authorization_code");
                params.append("code", "{code}");
                params.append("redirect_uri", "{REDIRECT_URI.format(port=port)}");
                params.append("client_id", "{CLIENT_ID}");
                params.append("client_secret", "{CLIENT_SECRET}");
                
                fetch("/oauth/token", {{
                    method: "POST",
                    headers: {{
                        "Content-Type": "application/x-www-form-urlencoded"
                    }},
                    body: params
                }})
                .then(res => res.json())
                .then(data => {{
                    resultDiv.innerHTML = `
                        <div class="step-indicator" style="margin-top: 20px;">
                            <span class="step completed">1. Client Initiation</span>
                            <span class="step completed">2. Auth & Consent</span>
                            <span class="step completed">3. Authorization Code</span>
                            <span class="step active">4. Token Exchange</span>
                            <span class="step">5. API Request</span>
                        </div>
                        <h2>Step 4: Token Response</h2>
                        <p>The client application securely traded the code. The token server returned a JSON payload with the token details.</p>
                        
                        <div class="info-panel">
                            <strong>What's happening:</strong><br>
                            The Token Server verified the client credentials (secret) and code. It invalidated the code so it cannot be used again, and returned a fresh <strong>Access Token</strong>.
                        </div>

                        <h3>Access Token Response Payload (JSON):</h3>
                        <div class="code-box">${{JSON.stringify(data, null, 2)}}</div>

                        <div style="margin-top: 20px;">
                            <button onclick="fetchProfile('${{data.access_token}}')" class="btn">Use Access Token to Fetch User Profile &rarr;</button>
                        </div>
                    `;
                }});
            }}

            function fetchProfile(token) {{
                const resultDiv = document.getElementById("exchange-result");
                fetch("/api/user", {{
                    headers: {{
                        "Authorization": "Bearer " + token
                    }}
                }})
                .then(res => res.json())
                .then(profile => {{
                    resultDiv.innerHTML = `
                        <div class="step-indicator" style="margin-top: 20px;">
                            <span class="step completed">1. Client Initiation</span>
                            <span class="step completed">2. Auth & Consent</span>
                            <span class="step completed">3. Authorization Code</span>
                            <span class="step completed">4. Token Exchange</span>
                            <span class="step active">5. API Request</span>
                        </div>
                        <h2>Step 5: Resource Server Response (User Profile)</h2>
                        <p>The client sent the HTTP GET request to the userinfo endpoint, passing the access token in the <code>Authorization: Bearer [token]</code> header.</p>
                        
                        <div class="info-panel">
                            <strong>Flow Completed Successfully!</strong><br>
                            The Resource Server verified the access token and returned the authorized user profile data.
                        </div>

                        <div class="profile-card">
                            <img src="${{profile.avatar}}" alt="User Avatar">
                            <div class="profile-info">
                                <h3>${{profile.name}}</h3>
                                <p>Email: <code>${{profile.email}}</code></p>
                                <p>Role: <strong>${{profile.role}}</strong></p>
                                <p>User ID: <code>${{profile.sub}}</code></p>
                            </div>
                        </div>

                        <div style="margin-top: 30px; display: flex; gap: 15px;">
                            <a href="/" class="btn">Restart Simulator</a>
                        </div>
                    `;
                }});
            }}
        </script>
        """
        self.send_html(content)

    def handle_token_exchange(self):
        # Parse post body
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length).decode('utf-8')
        params = urllib.parse.parse_qs(post_data)

        grant_type = params.get("grant_type", [""])[0]
        code = params.get("code", [""])[0]
        redirect_uri = params.get("redirect_uri", [""])[0]
        client_id = params.get("client_id", [""])[0]
        client_secret = params.get("client_secret", [""])[0]

        print(colorize("\n[Step 4] Received Token Exchange POST request on /oauth/token:", 'green'))
        print(f"  grant_type:    {grant_type}")
        print(f"  code:          {code}")
        print(f"  client_id:     {client_id}")
        print(f"  client_secret: {client_secret}")

        # Validate client credentials
        if client_id != CLIENT_ID or client_secret != CLIENT_SECRET:
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "invalid_client"}).encode('utf-8'))
            return

        # Validate code
        code_data = db["auth_codes"].pop(code, None) # Remove it so it is single-use
        if not code_data or code_data["redirect_uri"] != redirect_uri:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "invalid_grant"}).encode('utf-8'))
            return

        # Generate access token
        access_token = f"at_{secrets.token_hex(24)}"
        db["access_tokens"][access_token] = {
            "scope": code_data["scope"],
            "user": code_data["user"]
        }

        print(colorize("  Generated Access Token: ", 'cyan') + access_token)

        token_response = {
            "access_token": access_token,
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": code_data["scope"]
        }

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(token_response).encode('utf-8'))

    def handle_api_user(self):
        auth_header = self.headers.get("Authorization", "")
        print(colorize("\n[Step 5] Received API Request on /api/user:", 'green'))
        print(f"  Authorization Header: {auth_header}")

        if not auth_header.startswith("Bearer "):
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "unauthorized"}).encode('utf-8'))
            return

        token = auth_header.split(" ")[1]
        token_data = db["access_tokens"].get(token)
        if not token_data:
            self.send_response(401)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "invalid_token"}).encode('utf-8'))
            return

        print(colorize("  Token is valid. Returning Userinfo payload.", 'cyan'))
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(token_data["user"]).encode('utf-8'))

def get_free_port():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    return port

def main():
    parser = argparse.ArgumentParser(description="Simulate and visualize the OAuth 2.0 Authorization Code flow.")
    parser.add_argument("-p", "--port", type=int, default=8080, help="Port to run the mock server on (default: 8080)")
    args = parser.parse_args()

    port = args.port
    handler = SimulatorHTTPHandler
    
    # Try starting the server on specified port, retry on free port if occupied
    try:
        server = socketserver.TCPServer(("", port), handler)
    except OSError:
        print(colorize(f"Port {port} is occupied. Finding an available port...", 'yellow'))
        port = get_free_port()
        server = socketserver.TCPServer(("", port), handler)

    url = f"http://localhost:{port}"
    print(colorize("=== OAuth 2.0 Authorization Code Flow Simulator ===", 'bold'))
    print(f"Server is running at: {colorize(url, 'cyan')}")
    print("Open the link above in your browser to interactively trace the OAuth flow.")
    print("Press Ctrl+C to stop the simulator.")
    print("=" * 51)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(colorize("\nShutting down OAuth simulator server...", 'yellow'))
        server.server_close()
        sys.exit(0)

if __name__ == "__main__":
    main()
