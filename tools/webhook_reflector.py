#!/usr/bin/env python3
"""
Webhook Inspector & Payload Reflector
A local utility that acts as a webhook receiver, logging details, validating HMAC signatures,
and hosting a web dashboard to browse histories and replay payloads to local applications.
"""

import os
import sys
import time
import json
import argparse
import threading
import hmac
import hashlib
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.request
import urllib.error

# In-memory database to store captured webhooks
WEBHOOK_HISTORY = []
HISTORY_LOCK = threading.Lock()

# Basic ANSI colors for terminal logs
COLOR_CYAN = "\033[96m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_MAGENTA = "\033[95m"
COLOR_RESET = "\033[0m"

def colorize_json(data):
    """Adds ANSI escapes to format JSON strings with terminal colors."""
    try:
        formatted = json.dumps(data, indent=2)
        # Highlight keys
        formatted = re.sub(r'(".*?")(?=\s*:)', f"{COLOR_CYAN}\\1{COLOR_RESET}", formatted)
        # Highlight values
        # strings
        formatted = re.sub(r'(:\s*)(".*?")', f"\\1{COLOR_GREEN}\\2{COLOR_RESET}", formatted)
        # numbers
        formatted = re.sub(r'(:\s*)(\b\d+\.?\d*\b)', f"\\1{COLOR_YELLOW}\\2{COLOR_RESET}", formatted)
        # booleans/nulls
        formatted = re.sub(r'(:\s*)(\btrue\b|\bfalse\b|\bnull\b)', f"\\1{COLOR_MAGENTA}\\2{COLOR_RESET}", formatted)
        return formatted
    except Exception:
        return str(data)

import re

# HTML + CSS template for the dashboard
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Webhook Reflector Dashboard</title>
    <style>
        :root {
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent: #38bdf8;
            --accent-hover: #0ea5e9;
            --border-color: #334155;
            --success: #10b981;
            --danger: #ef4444;
        }
        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            margin: 0;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
        }
        header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 20px;
            margin-bottom: 20px;
        }
        h1 { margin: 0; font-size: 24px; color: var(--accent); }
        .stats { font-size: 14px; color: var(--text-secondary); }
        .grid {
            display: grid;
            grid-template-columns: 350px 1fr;
            gap: 20px;
        }
        .sidebar {
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            height: 70vh;
            overflow-y: auto;
            padding: 10px;
        }
        .webhook-list-item {
            padding: 12px;
            border-bottom: 1px solid var(--border-color);
            cursor: pointer;
            border-radius: 4px;
            transition: background-color 0.2s;
        }
        .webhook-list-item:hover {
            background-color: rgba(255, 255, 255, 0.05);
        }
        .webhook-list-item.active {
            background-color: rgba(56, 189, 248, 0.15);
            border-left: 4px solid var(--accent);
        }
        .item-meta {
            display: flex;
            justify-content: space-between;
            font-size: 12px;
            margin-bottom: 6px;
        }
        .method {
            font-weight: bold;
            color: var(--success);
        }
        .path {
            font-family: monospace;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
            max-width: 180px;
        }
        .time { color: var(--text-secondary); }
        .details-panel {
            background-color: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            padding: 20px;
            height: 70vh;
            overflow-y: auto;
        }
        pre {
            background-color: #0b0f19;
            padding: 15px;
            border-radius: 6px;
            overflow-x: auto;
            border: 1px solid var(--border-color);
            font-size: 13px;
        }
        .badge {
            display: inline-block;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: bold;
        }
        .badge-verified { background-color: rgba(16, 185, 129, 0.2); color: var(--success); }
        .badge-failed { background-color: rgba(239, 68, 68, 0.2); color: var(--danger); }
        .badge-none { background-color: rgba(148, 163, 184, 0.2); color: var(--text-secondary); }
        .btn {
            background-color: var(--accent);
            color: #000;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-weight: bold;
            transition: background-color 0.2s;
        }
        .btn:hover { background-color: var(--accent-hover); }
        .replay-form {
            display: flex;
            gap: 10px;
            margin-top: 15px;
            padding-top: 15px;
            border-top: 1px solid var(--border-color);
        }
        .replay-form input {
            flex-grow: 1;
            background-color: #0b0f19;
            border: 1px solid var(--border-color);
            color: #fff;
            padding: 8px;
            border-radius: 4px;
            font-family: monospace;
        }
        .no-data {
            text-align: center;
            color: var(--text-secondary);
            margin-top: 50px;
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>⚓ Webhook Reflector</h1>
                <p style="margin: 5px 0 0 0; color: var(--text-secondary)">Local dev tool for testing, signature auditing, and replaying webhooks</p>
            </div>
            <div class="stats">
                Total Captured: <span id="captured-count" style="font-weight: bold; color: var(--accent)">0</span>
            </div>
        </header>

        <div class="grid">
            <div class="sidebar" id="sidebar">
                <div class="no-data">Listening for incoming webhooks...</div>
            </div>
            <div class="details-panel" id="details-panel">
                <div class="no-data">Select a webhook to inspect details</div>
            </div>
        </div>
    </div>

    <script>
        let webhooks = [];
        let activeId = null;

        async function fetchHistory() {
            try {
                const res = await fetch('/__webhook_history__');
                const data = await res.json();
                webhooks = data;
                document.getElementById('captured-count').innerText = webhooks.length;
                renderList();
                if (activeId !== null) {
                    renderDetails(activeId);
                }
            } catch (err) {
                console.error("Error fetching webhooks:", err);
            }
        }

        function renderList() {
            const sidebar = document.getElementById('sidebar');
            if (webhooks.length === 0) {
                sidebar.innerHTML = '<div class="no-data">Listening for incoming webhooks...</div>';
                return;
            }

            sidebar.innerHTML = webhooks.map(wh => {
                const activeClass = wh.id === activeId ? 'active' : '';
                const timeStr = new Date(wh.timestamp * 1000).toLocaleTimeString();
                return `
                    <div class="webhook-list-item ${activeClass}" onclick="selectWebhook('${wh.id}')">
                        <div class="item-meta">
                            <span class="method">${wh.method}</span>
                            <span class="time">${timeStr}</span>
                        </div>
                        <div class="path">${wh.path}</div>
                    </div>
                `;
            }).join('');
        }

        function selectWebhook(id) {
            activeId = id;
            renderList();
            renderDetails(id);
        }

        function renderDetails(id) {
            const panel = document.getElementById('details-panel');
            const wh = webhooks.find(w => w.id === id);
            if (!wh) {
                panel.innerHTML = '<div class="no-data">Select a webhook to inspect details</div>';
                return;
            }

            let sigBadge = '<span class="badge badge-none">No Signature Checked</span>';
            if (wh.signature_status === 'valid') {
                sigBadge = '<span class="badge badge-verified">✓ Signature Verified</span>';
            } else if (wh.signature_status === 'invalid') {
                sigBadge = '<span class="badge badge-failed">✗ Signature Verification Failed</span>';
            }

            let headersText = '';
            for (const [key, val] of Object.entries(wh.headers)) {
                headersText += `<strong>${key}:</strong> ${val}\\n`;
            }

            panel.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:15px;">
                    <h2 style="margin:0; font-size:18px; color:var(--accent);">${wh.method} ${wh.path}</h2>
                    ${sigBadge}
                </div>
                <div style="font-size:12px; color:var(--text-secondary); margin-bottom:15px;">
                    Received: ${new Date(wh.timestamp * 1000).toLocaleString()} | Client IP: ${wh.client_ip}
                </div>
                
                <h3>HTTP Headers</h3>
                <pre style="white-space: pre-wrap; font-family: monospace;">${headersText}</pre>

                <h3>Payload</h3>
                <pre><code style="color: #a7f3d0;">${JSON.stringify(wh.body, null, 2)}</code></pre>

                <h3>Replay Webhook</h3>
                <p style="font-size:12px; color:var(--text-secondary);">Send this exact payload and headers to your local application endpoint:</p>
                <div class="replay-form">
                    <input type="text" id="replay-url" value="http://localhost:3000/webhook" placeholder="Target API URL">
                    <button class="btn" onclick="replayWebhook('${wh.id}')">Replay Request</button>
                </div>
                <div id="replay-status" style="margin-top:10px; font-size:13px; font-weight:bold;"></div>
            `;
        }

        async function replayWebhook(id) {
            const targetUrl = document.getElementById('replay-url').value;
            const statusDiv = document.getElementById('replay-status');
            statusDiv.style.color = 'var(--text-secondary)';
            statusDiv.innerText = 'Sending...';

            try {
                const res = await fetch('/__webhook_replay__', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ id: id, target_url: targetUrl })
                });
                const result = await res.json();
                if (result.success) {
                    statusDiv.style.color = 'var(--success)';
                    statusDiv.innerText = `Replay Successful: HTTP ${result.status}`;
                } else {
                    statusDiv.style.color = 'var(--danger)';
                    statusDiv.innerText = `Replay Failed: ${result.error}`;
                }
            } catch (err) {
                statusDiv.style.color = 'var(--danger)';
                statusDiv.innerText = `Network Error: ${err.message}`;
            }
        }

        // Poll history every 2 seconds
        setInterval(fetchHistory, 2000);
        fetchHistory();
    </script>
</body>
</html>
"""

class WebhookReflectorHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Prevent default stdout logs to avoid cluttering webhook inspections
        pass

    def verify_signature(self, body_bytes):
        """Verifies HMAC signature if key is specified."""
        if not self.server.secret_key:
            return 'none'

        # Check common webhook signature headers
        signature = None
        algo = hashlib.sha256
        
        # GitHub: X-Hub-Signature-256=sha256=xxx
        if 'x-hub-signature-256' in self.headers:
            sig_header = self.headers['x-hub-signature-256']
            if sig_header.startswith('sha256='):
                signature = sig_header[7:]
        # Shopify: X-Shopify-Hmac-SHA256: xxx
        elif 'x-shopify-hmac-sha256' in self.headers:
            signature = self.headers['x-shopify-hmac-sha256']
        # Stripe: stripe-signature: t=xxx,v1=xxx
        elif 'stripe-signature' in self.headers:
            sig_header = self.headers['stripe-signature']
            match = re.search(r'v1=([^,]+)', sig_header)
            if match:
                signature = match.group(1)
        # Custom header check
        elif self.server.sig_header and self.server.sig_header.lower() in self.headers:
            signature = self.headers[self.server.sig_header.lower()]

        if not signature:
            return 'invalid'  # Expected signature but none found

        # Validate signature
        try:
            expected = hmac.new(self.server.secret_key.encode('utf-8'), body_bytes, algo).hexdigest()
            # Compare using constant-time comparison
            if hmac.compare_digest(expected, signature):
                return 'valid'
        except Exception:
            pass
        return 'invalid'

    def do_GET(self):
        # Serve the Dashboard page
        if self.path == '/' or self.path == '/__webhook_dashboard__':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode('utf-8'))
            return

        # API: Get webhook history list
        if self.path == '/__webhook_history__':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            with HISTORY_LOCK:
                history_copy = list(reversed(WEBHOOK_HISTORY)) # Newest first
            self.wfile.write(json.dumps(history_copy).encode('utf-8'))
            return

        # Fallback 404
        self.send_error(404, "Not Found")

    def do_POST(self):
        # API: Replay webhook
        if self.path == '/__webhook_replay__':
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length).decode('utf-8')
            try:
                params = json.loads(post_data)
                webhook_id = params.get('id')
                target_url = params.get('target_url')
                
                # Retrieve the webhook payload
                webhook = None
                with HISTORY_LOCK:
                    for wh in WEBHOOK_HISTORY:
                        if wh['id'] == webhook_id:
                            webhook = wh
                            break
                            
                if not webhook:
                    self.send_response(400)
                    self.send_header('Content-Type', 'application/json')
                    self.end_headers()
                    self.wfile.write(json.dumps({'success': False, 'error': 'Webhook not found'}).encode('utf-8'))
                    return
                
                # Perform HTTP replay call
                replay_headers = webhook['headers'].copy()
                # Clean up host or connection parameters
                for header in ['Host', 'host', 'Connection', 'connection', 'Content-Length', 'content-length']:
                    replay_headers.pop(header, None)
                
                body_bytes = json.dumps(webhook['body']).encode('utf-8')
                req = urllib.request.Request(target_url, data=body_bytes, headers=replay_headers, method='POST')
                
                with urllib.request.urlopen(req, timeout=5) as response:
                    status = response.status
                    
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': True, 'status': status}).encode('utf-8'))
                
            except urllib.error.HTTPError as e:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': f"Target returned HTTP {e.code}"}).encode('utf-8'))
            except Exception as e:
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'error': str(e)}).encode('utf-8'))
            return

        # Normal Webhook Capture
        content_length = int(self.headers.get('Content-Length', 0))
        body_bytes = self.rfile.read(content_length) if content_length > 0 else b''
        
        # Try parsing JSON body
        body_data = {}
        if body_bytes:
            try:
                body_data = json.loads(body_bytes.decode('utf-8'))
            except Exception:
                body_data = {"raw_text": body_bytes.decode('utf-8', errors='ignore')}

        # Extract headers
        headers_dict = {key: val for key, val in self.headers.items()}
        
        # Verify signature
        sig_status = self.verify_signature(body_bytes)

        # Generate unique webhook ID
        webhook_id = hashlib.md5(f"{time.time()}-{self.client_address[0]}".encode('utf-8')).hexdigest()[:12]

        webhook_record = {
            "id": webhook_id,
            "timestamp": time.time(),
            "method": self.command,
            "path": self.path,
            "headers": headers_dict,
            "body": body_data,
            "client_ip": self.client_address[0],
            "signature_status": sig_status
        }

        # Store in list
        with HISTORY_LOCK:
            WEBHOOK_HISTORY.append(webhook_record)
            if len(WEBHOOK_HISTORY) > 100:  # Cap history size
                WEBHOOK_HISTORY.pop(0)

        # Print terminal representation of webhook
        print("\n" + "=" * 60)
        print(f"{COLOR_GREEN}[Webhook Received]{COLOR_RESET} at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"URL Path:  {COLOR_CYAN}{self.path}{COLOR_RESET}")
        print(f"Client IP: {self.client_address[0]}")
        if sig_status == 'valid':
            print(f"Signature: {COLOR_GREEN}Valid (Verified){COLOR_RESET}")
        elif sig_status == 'invalid':
            print(f"Signature: {COLOR_RED}Invalid / Failed Verification{COLOR_RESET}")
        else:
            print(f"Signature: None Checked")
        print("-" * 60)
        print("Payload:")
        print(colorize_json(body_data))
        print("=" * 60 + "\n")

        # Respond 200 OK to sender
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({"status": "captured", "id": webhook_id}).encode('utf-8'))


def main():
    parser = argparse.ArgumentParser(description="Webhook Inspector & Payload Reflector")
    parser.add_argument('--port', type=int, default=9000, help='Port to run webhook server on (default: 9000)')
    parser.add_argument('--bind', default='127.0.0.1', help='Host to bind server to (default: 127.0.0.1)')
    parser.add_argument('--secret', help='Secret key to verify incoming HMAC signature hashes')
    parser.add_argument('--header', help='Custom HTTP header containing the signature (e.g. X-My-Signature)')

    args = parser.parse_args()

    print("==================================================")
    print("⚓ Webhook Inspector & Payload Reflector Active")
    print(f"Server URL:     http://{args.bind}:{args.port}/")
    print(f"Dashboard URL:  http://{args.bind}:{args.port}/__webhook_dashboard__")
    if args.secret:
        print(f"HMAC Secret:    Active")
        if args.header:
            print(f"Sig Header:     {args.header}")
        else:
            print(f"Sig Header:     Autodetect (GitHub, Stripe, Shopify)")
    print("Press Ctrl+C to stop.")
    print("==================================================")

    server = HTTPServer((args.bind, args.port), WebhookReflectorHandler)
    server.secret_key = args.secret
    server.sig_header = args.header

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Webhook Reflector...")
    finally:
        server.server_close()
        print("Server stopped.")

if __name__ == '__main__':
    main()
