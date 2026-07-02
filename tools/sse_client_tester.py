#!/usr/bin/env python3
"""
HTTP Server Sent Events (SSE) Tester & Client

A dual-mode terminal utility containing:
1. An SSE Client: Connects to a remote HTTP URL stream and prints events
   (event, data, id) in real-time, calculating statistics (latency, throughput).
2. An SSE Mock Server: A local server that serves simulated SSE streams
   (e.g., word-by-word quote generators, CPU statistics) to test SSE clients.

Usage:
    # Run as a local mock server on port 8080:
    python sse_client_tester.py --server --port 8080

    # Run as a client connecting to a stream:
    python sse_client_tester.py http://localhost:8080/stream
"""

import sys
import argparse
import urllib.request
import urllib.parse
import time
import http.server
import socketserver
import threading
import json
import random

# Global flag to stop server if needed
server_running = True

class SSEServerHandler(http.server.BaseHTTPRequestHandler):
    """A simple HTTP request handler that generates mock SSE event streams."""
    def log_message(self, format, *args):
        # Override to suppress standard http server logs on stdout
        pass

    def do_GET(self):
        parsed_path = urllib.parse.urlparse(self.path)
        
        # Simple health check endpoint
        if parsed_path.path == '/health':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
            return

        # SSE Stream endpoint
        if parsed_path.path in ('/stream', '/'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            print(f"Server: Client connected from {self.client_address}")
            
            # Select stream payload mode
            query = urllib.parse.parse_qs(parsed_path.query)
            mode = query.get('mode', ['quote'])[0]
            
            try:
                if mode == 'stats':
                    # Emit simulated CPU / RAM telemetry stats
                    for i in range(15):
                        cpu = random.uniform(5.0, 95.0)
                        ram = random.uniform(20.0, 85.0)
                        payload = json.dumps({"cpu_pct": round(cpu, 2), "ram_pct": round(ram, 2), "seq": i})
                        
                        self.wfile.write(b"event: telemetry\n")
                        self.wfile.write(f"data: {payload}\n".encode('utf-8'))
                        self.wfile.write(f"id: stat_{i}\n\n".encode('utf-8'))
                        self.wfile.flush()
                        time.sleep(1.0)
                else:
                    # Default: Stream words of a quote (simulating LLM token streaming)
                    quotes = [
                        "Knowledge is power. Information is liberating. Education is the premise of progress, in every society, in every family.",
                        "Code is like humor. When you have to explain it, it's bad.",
                        "Simple things should be simple, complex things should be possible."
                    ]
                    quote = random.choice(quotes)
                    words = quote.split()
                    
                    self.wfile.write(b"event: start\n")
                    self.wfile.write(b"data: Starting text generation stream...\n\n")
                    self.wfile.flush()
                    time.sleep(0.5)
                    
                    for idx, word in enumerate(words):
                        payload = json.dumps({"token": word + " ", "index": idx})
                        self.wfile.write(b"event: token\n")
                        self.wfile.write(f"data: {payload}\n".encode('utf-8'))
                        self.wfile.write(f"id: token_{idx}\n\n".encode('utf-8'))
                        self.wfile.flush()
                        time.sleep(0.15)  # Simulate token generation latency
                        
                    self.wfile.write(b"event: end\n")
                    self.wfile.write(b"data: [DONE]\n\n")
                    self.wfile.flush()
            except (ConnectionResetError, ConnectionAbortedError):
                print(f"Server: Client {self.client_address} disconnected abruptly.")
            except Exception as e:
                print(f"Server error: {e}", file=sys.stderr)
            finally:
                print(f"Server: Connection closed for {self.client_address}")
            return
            
        # Default 404
        self.send_response(404)
        self.end_headers()
        self.wfile.write(b"Not Found")

def run_server(port):
    """Starts the local mock SSE server."""
    class ThreadingHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
        daemon_threads = True

    server = ThreadingHTTPServer(('0.0.0.0', port), SSEServerHandler)
    print(f"Mock SSE Server running on http://localhost:{port}/")
    print(f"  Stream endpoints:")
    print(f"    - Token stream     : http://localhost:{port}/stream?mode=quote")
    print(f"    - Telemetry stream : http://localhost:{port}/stream?mode=stats")
    print("Press Ctrl+C to terminate the server.\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        print("Server shutdown completed.")

def run_client(url):
    """Connects to a remote SSE stream and prints events to the console."""
    print(f"Connecting to SSE stream: {url}")
    print("Listening for events (Press Ctrl+C to disconnect)...\n")
    
    req = urllib.request.Request(
        url,
        headers={
            'Accept': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'User-Agent': 'SseClientTester/1.0'
        }
    )
    
    start_time = time.time()
    events_count = 0
    bytes_received = 0
    
    current_event = {}
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            connect_latency = time.time() - start_time
            print(f"\033[90mConnected in {connect_latency:.3f}s. Server Response HTTP Code: {response.status}\033[0m")
            print("=" * 60)
            
            # Read line-by-line
            for line_bytes in response:
                bytes_received += len(line_bytes)
                line = line_bytes.decode('utf-8', errors='ignore').strip()
                
                # An empty line indicates the end of an event block
                if not line:
                    if current_event:
                        # Output the parsed event
                        events_count += 1
                        ev_name = current_event.get('event', 'message')
                        ev_data = current_event.get('data', '')
                        ev_id = current_event.get('id', 'N/A')
                        
                        # Try to pretty print JSON data
                        try:
                            # In LLM streams, token data is often JSON string
                            parsed_json = json.loads(ev_data)
                            if 'token' in parsed_json:
                                # Stream LLM tokens directly on stdout without headers
                                sys.stdout.write(parsed_json['token'])
                                sys.stdout.flush()
                            else:
                                print(f"\n\033[94mEvent: {ev_name}\033[0m (id: {ev_id})")
                                print(f"  Data: {json.dumps(parsed_json, indent=2)}")
                        except Exception:
                            # Otherwise print raw data
                            # If it's a finish marker, line break
                            if ev_data == '[DONE]':
                                print("\n\033[90m[Stream finished]\033[0m")
                            else:
                                print(f"\n\033[94mEvent: {ev_name}\033[0m (id: {ev_id})")
                                print(f"  Data: {ev_data}")
                                
                        current_event = {}
                    continue
                
                # Parse SSE fields: field_name: field_value
                if ':' in line:
                    field, val = line.split(':', 1)
                    field = field.strip()
                    val = val.strip()
                    
                    if field == 'event':
                        current_event['event'] = val
                    elif field == 'data':
                        # Handle consecutive data lines
                        if 'data' in current_event:
                            current_event['data'] += '\n' + val
                        else:
                            current_event['data'] = val
                    elif field == 'id':
                        current_event['id'] = val
                    elif field == 'retry':
                        print(f"\033[90mServer requested retry delay change: {val}ms\033[0m")
                        
    except KeyboardInterrupt:
        print("\n\033[93mClient disconnected by user.\033[0m")
    except Exception as e:
        print(f"\nError reading SSE stream: {e}", file=sys.stderr)
    finally:
        total_time = time.time() - start_time
        print("\n" + "=" * 60)
        print("STREAM STATISTICS")
        print("=" * 60)
        print(f"Total stream duration : {total_time:.2f} seconds")
        print(f"Total events received : {events_count}")
        print(f"Data received         : {bytes_received} bytes ({bytes_received / 1024:.2f} KB)")
        if total_time > 0:
            print(f"Average throughput    : {bytes_received / total_time:.2f} bytes/sec")
        print("=" * 60)

def main():
    parser = argparse.ArgumentParser(
        description="Dual SSE client tester and server simulator tool.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # Mode selection
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "url",
        nargs="?",
        help="Remote URL of the SSE stream to connect to (client mode)."
    )
    group.add_argument(
        "-s", "--server",
        action="store_true",
        help="Run as a local mock SSE server."
    )
    
    parser.add_argument(
        "-p", "--port",
        type=int,
        default=8080,
        help="Port number to host mock server (default: 8080)"
    )
    
    args = parser.parse_args()
    
    if args.server:
        run_server(args.port)
    elif args.url:
        # Standardize URL
        url = args.url
        if not url.startswith(('http://', 'https://')):
            url = 'http://' + url
        run_client(url)
        
    return 0

if __name__ == "__main__":
    sys.exit(main())
