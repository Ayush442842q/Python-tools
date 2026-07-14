#!/usr/bin/env python3
"""
Server-Sent Events (SSE) Mock Server & Tester

This tool runs a lightweight HTTP server in pure Python that broadcasts Server-Sent
Events (SSE / EventSource protocol) to connected clients. It includes:
    1. An event stream endpoint (/events) broadcasting JSON telemetry events
    2. Dynamic streaming parameters (?interval=3&event=metrics)
    3. A beautiful, built-in HTML dashboard at '/' that connects to the stream,
       displays events in real-time, and logs metrics.

Requirements:
    - Pure Python 3 (no third-party dependencies)
"""

import sys
import os
import time
import json
import random
import urllib.parse
import http.server
import socketserver
import argparse

# ANSI Terminal Colors
COLORS = {
    'green': '\033[32m',
    'yellow': '\033[33m',
    'red': '\033[31m',
    'cyan': '\033[36m',
    'blue': '\033[34m',
    'bold': '\033[1m',
    'reset': '\033[0m'
}

def colorize(text, color):
    if sys.stdout.isatty() and color in COLORS:
        return f"{COLORS[color]}{text}{COLORS['reset']}"
    return text

# Dashboard HTML template
DASHBOARD_HTML = """<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Server-Sent Events (SSE) Mock Dashboard</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #0f172a;
            color: #f8fafc;
            margin: 0;
            padding: 20px;
            display: flex;
            justify-content: center;
        }
        .container {
            max-width: 1000px;
            width: 100%;
            display: grid;
            grid-template-columns: 350px 1fr;
            gap: 20px;
        }
        .panel {
            background: #1e293b;
            border-radius: 12px;
            padding: 20px;
            box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.4);
            border: 1px solid #334155;
        }
        h1, h2, h3 {
            color: #38bdf8;
            margin-top: 0;
        }
        .status-container {
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 20px;
        }
        .status-dot {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            background-color: #ef4444; /* Default red */
            box-shadow: 0 0 8px #ef4444;
        }
        .status-dot.connected {
            background-color: #22c55e;
            box-shadow: 0 0 8px #22c55e;
        }
        .status-dot.connecting {
            background-color: #eab308;
            box-shadow: 0 0 8px #eab308;
        }
        .form-group {
            margin-bottom: 15px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            color: #94a3b8;
            font-size: 14px;
        }
        input, select {
            width: 100%;
            padding: 8px 12px;
            background: #0f172a;
            border: 1px solid #475569;
            border-radius: 6px;
            color: white;
            box-sizing: border-box;
        }
        .btn {
            background: #0284c7;
            color: white;
            padding: 10px 15px;
            border: none;
            border-radius: 6px;
            cursor: pointer;
            font-weight: bold;
            width: 100%;
        }
        .btn:hover {
            background: #0369a1;
        }
        .event-log-container {
            display: flex;
            flex-direction: column;
            height: 500px;
        }
        .event-log {
            flex-grow: 1;
            background: #090d16;
            border: 1px solid #1e293b;
            border-radius: 6px;
            padding: 15px;
            font-family: monospace;
            overflow-y: auto;
            display: flex;
            flex-direction: column-reverse; /* Newest events at top */
            gap: 10px;
        }
        .event-item {
            border-left: 3px solid #38bdf8;
            padding-left: 10px;
            margin-bottom: 5px;
            font-size: 13px;
        }
        .event-item.custom-event {
            border-left-color: #a855f7;
        }
        .event-meta {
            color: #64748b;
            font-size: 11px;
            margin-bottom: 3px;
        }
        .event-data {
            color: #34d399;
            white-space: pre-wrap;
            word-break: break-all;
        }
        .clear-btn {
            background: #334155;
            color: #f8fafc;
            border: none;
            padding: 5px 10px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 12px;
            margin-left: auto;
        }
        .clear-btn:hover {
            background: #475569;
        }
        .flex-header {
            display: flex;
            align-items: center;
            margin-bottom: 10px;
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Configuration Panel -->
        <div class="panel">
            <h2>SSE Configurator</h2>
            <div class="status-container">
                <div id="status-dot" class="status-dot"></div>
                <span id="status-text">Disconnected</span>
            </div>
            
            <div class="form-group">
                <label for="interval-input">Event Interval (Seconds)</label>
                <input type="number" id="interval-input" min="0.5" step="0.5" value="2">
            </div>
            
            <div class="form-group">
                <label for="event-name-input">SSE Event Name (optional)</label>
                <input type="text" id="event-name-input" placeholder="message" value="metrics">
            </div>
            
            <button onclick="reconnectStream()" class="btn">Update & Reconnect</button>
            
            <div style="margin-top: 30px; font-size: 13px; color: #94a3b8; line-height: 1.5;">
                <h3>Active Endpoint:</h3>
                <code id="endpoint-url" style="color: #f472b6; word-break: break-all;">/events?interval=2&event=metrics</code>
                <p style="margin-top: 15px;">Server-Sent Events allow servers to push data to web clients over standard HTTP. It is simpler than WebSockets when only one-way downstream communication is needed.</p>
            </div>
        </div>

        <!-- Event Log Panel -->
        <div class="panel event-log-container">
            <div class="flex-header">
                <h2>Real-Time Event Stream Log</h2>
                <button onclick="clearLog()" class="clear-btn">Clear Log</button>
            </div>
            <div id="event-log" class="event-log">
                <div style="color: #64748b; text-align: center; margin-top: 50px;">Waiting for events...</div>
            </div>
        </div>
    </div>

    <script>
        let eventSource = null;

        function reconnectStream() {
            const interval = document.getElementById("interval-input").value;
            const eventName = document.getElementById("event-name-input").value;
            
            // Build query params
            const params = new URLSearchParams();
            if (interval) params.append("interval", interval);
            if (eventName) params.append("event", eventName);
            
            const endpoint = `/events?${params.toString()}`;
            document.getElementById("endpoint-url").textContent = window.location.origin + endpoint;

            // Close existing connection
            if (eventSource) {
                eventSource.close();
            }

            const statusDot = document.getElementById("status-dot");
            const statusText = document.getElementById("status-text");
            const eventLog = document.getElementById("event-log");

            statusDot.className = "status-dot connecting";
            statusText.textContent = "Connecting...";

            // Create EventSource
            eventSource = new EventSource(endpoint);

            eventSource.onopen = function() {
                statusDot.className = "status-dot connected";
                statusText.textContent = "Connected";
                appendSystemMessage("Connection established with stream.");
            };

            eventSource.onerror = function() {
                statusDot.className = "status-dot";
                statusText.textContent = "Disconnected (Error/Reconnecting)";
                appendSystemMessage("Connection error. EventSource will auto-reconnect.");
            };

            // If a specific event name is configured, EventSource requires adding a listener
            if (eventName) {
                eventSource.addEventListener(eventName, function(e) {
                    handleEvent(e, eventName);
                });
            } else {
                // Default 'message' handler
                eventSource.onmessage = function(e) {
                    handleEvent(e, "message");
                };
            }
        }

        function handleEvent(e, eventName) {
            const logDiv = document.getElementById("event-log");
            // Remove waiting placeholder
            if (logDiv.children.length === 1 && logDiv.children[0].className === "") {
                logDiv.innerHTML = "";
            }

            const item = document.createElement("div");
            item.className = `event-item ${eventName !== "message" ? "custom-event" : ""}`;
            
            // Format JSON data if possible
            let formattedData = e.data;
            try {
                const parsed = JSON.parse(e.data);
                formattedData = JSON.stringify(parsed, null, 2);
            } catch(err) {}

            const timestamp = new Date().toLocaleTimeString();

            item.innerHTML = `
                <div class="event-meta">
                    [${timestamp}] Event: <strong>${eventName}</strong> | ID: ${e.lastEventId || "N/A"}
                </div>
                <pre class="event-data">${escapeHtml(formattedData)}</pre>
            `;
            logDiv.insertBefore(item, logDiv.firstChild);
        }

        function appendSystemMessage(msg) {
            const logDiv = document.getElementById("event-log");
            const item = document.createElement("div");
            item.style.color = "#eab308";
            item.style.fontSize = "12px";
            item.style.margin = "5px 0";
            item.style.fontFamily = "monospace";
            item.textContent = `[SYSTEM] ${msg}`;
            logDiv.insertBefore(item, logDiv.firstChild);
        }

        function clearLog() {
            document.getElementById("event-log").innerHTML = '<div style="color: #64748b; text-align: center; margin-top: 50px;">Waiting for events...</div>';
        }

        function escapeHtml(text) {
            return text
                .replace(/&/g, "&amp;")
                .replace(/</g, "&lt;")
                .replace(/>/g, "&gt;")
                .replace(/"/g, "&quot;")
                .replace(/'/g, "&#039;");
        }

        // Auto initiate
        reconnectStream();
    </script>
</body>
</html>
"""

class SSEHTTPHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        # Suppress logging to keep stdout clear
        pass

    def do_GET(self):
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path
        query = urllib.parse.parse_qs(parsed_url.query)

        if path == "/":
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode('utf-8'))
        elif path == "/events":
            self.handle_event_stream(query)
        else:
            self.send_response(404)
            self.end_headers()

    def handle_event_stream(self, query):
        interval_val = query.get("interval", ["2"])[0]
        event_name = query.get("event", ["metrics"])[0]

        try:
            interval = float(interval_val)
        except ValueError:
            interval = 2.0

        # Set headers for SSE streaming
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "keep-alive")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()

        print(colorize(f"\n[Client Connected] Streaming event: '{event_name}' every {interval}s", 'green'))

        event_id = 1
        try:
            while True:
                # Generate mock telemetry payload
                data = {
                    "timestamp": int(time.time()),
                    "cpu_load_pct": round(random.uniform(5.0, 75.0), 1),
                    "memory_used_mb": random.randint(1024, 8192),
                    "active_users": random.randint(10, 500),
                    "system_status": random.choice(["OK", "OK", "OK", "DEGRADED", "WARNING"])
                }
                payload = json.dumps(data)

                # Format SSE chunk:
                # id: [id]\n
                # event: [event_name]\n (optional)
                # data: [payload]\n\n
                sse_chunk = f"id: {event_id}\n"
                if event_name:
                    sse_chunk += f"event: {event_name}\n"
                sse_chunk += f"data: {payload}\n\n"

                self.wfile.write(sse_chunk.encode('utf-8'))
                self.wfile.flush() # Force transfer down the socket

                # Print trace to terminal
                sys.stdout.write(colorize(".", 'cyan'))
                sys.stdout.flush()

                event_id += 1
                time.sleep(interval)
        except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
            print(colorize(f"\n[Client Disconnected] Stream terminated.", 'yellow'))
        except Exception as e:
            print(colorize(f"\n[Error in Stream] {e}", 'red'))

def get_free_port():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(('', 0))
    port = s.getsockname()[1]
    s.close()
    return port

def main():
    parser = argparse.ArgumentParser(description="Start a mock Server-Sent Events (SSE) server.")
    parser.add_argument("-p", "--port", type=int, default=8000, help="Port to run the mock server on (default: 8000)")
    args = parser.parse_args()

    port = args.port
    handler = SSEHTTPHandler

    try:
        server = socketserver.TCPServer(("", port), handler)
    except OSError:
        print(colorize(f"Port {port} is occupied. Searching for an available port...", 'yellow'))
        port = get_free_port()
        server = socketserver.TCPServer(("", port), handler)

    url = f"http://localhost:{port}"
    print(colorize("=== Server-Sent Events (SSE) Mock Server ===", 'bold'))
    print(f"Server is running at: {colorize(url, 'cyan')}")
    print("Open the link in your browser to view the real-time event log dashboard.")
    print("Press Ctrl+C to terminate.")
    print("=" * 44)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(colorize("\nShutting down SSE mock server...", 'yellow'))
        server.server_close()
        sys.exit(0)

if __name__ == "__main__":
    main()
