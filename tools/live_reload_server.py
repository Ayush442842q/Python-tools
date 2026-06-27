#!/usr/bin/env python3
"""
Live Reload Development Server
A lightweight, zero-dependency HTTP server that automatically monitors static files
(HTML, CSS, JS) for modifications and refreshes connected browsers instantly via Server-Sent Events (SSE).
"""

import os
import sys
import time
import argparse
import threading
from http.server import SimpleHTTPRequestHandler
from socketserver import ThreadingTCPServer

# Live reload client script to inject
LIVE_RELOAD_SCRIPT = """
<!-- Live Reload Script -->
<script type="text/javascript">
(function() {
    console.log("Live Reload client initialized.");
    let retryCount = 0;
    function connect() {
        const source = new EventSource('/__livereload__');
        source.onmessage = function(event) {
            if (event.data === 'reload') {
                console.log('Live Reload: Change detected, reloading page...');
                window.location.reload();
            }
        };
        source.onerror = function() {
            source.close();
            retryCount++;
            let delay = Math.min(1000 * retryCount, 5000);
            console.log('Live Reload: Connection lost. Reconnecting in ' + delay + 'ms...');
            setTimeout(connect, delay);
        };
        source.onopen = function() {
            retryCount = 0;
            console.log('Live Reload: Connected.');
        };
    }
    connect();
})();
</script>
"""

class LiveReloadHandler(SimpleHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def do_GET(self):
        # Serve the SSE live reload endpoint
        if self.path == '/__livereload__':
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Connection', 'keep-alive')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            # Keep client in active list
            client_queue = self.server.register_client()
            try:
                # Wait for file change events
                while self.server.running:
                    try:
                        event = client_queue.get(timeout=1.0)
                        if event == 'reload':
                            self.wfile.write(b"data: reload\n\n")
                            self.wfile.flush()
                    except Exception:
                        # Timeout, send a keep-alive ping
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                pass  # Client disconnected
            finally:
                self.server.unregister_client(client_queue)
            return

        # Regular file serving - intercept HTML to inject the live reload script
        # Check if the file requested is HTML
        normalized_path = self.translate_path(self.path)
        if os.path.isdir(normalized_path):
            # Look for index.html
            index_path = os.path.join(normalized_path, "index.html")
            if os.path.exists(index_path):
                normalized_path = index_path

        if normalized_path.endswith('.html') and os.path.exists(normalized_path) and os.path.isfile(normalized_path):
            try:
                with open(normalized_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()

                # Inject script before </body> or </html>, or at the end
                if "</body>" in content:
                    content = content.replace("</body>", f"{LIVE_RELOAD_SCRIPT}\n</body>")
                elif "</html>" in content:
                    content = content.replace("</html>", f"{LIVE_RELOAD_SCRIPT}\n</html>")
                else:
                    content += LIVE_RELOAD_SCRIPT

                encoded_content = content.encode('utf-8')
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.send_header('Content-Length', str(len(encoded_content)))
                self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
                self.end_headers()
                self.wfile.write(encoded_content)
                return
            except Exception as e:
                # Fallback to default serving if reading fails
                print(f"Error injecting script into {normalized_path}: {e}")

        # Disable browser caching for local development
        super().do_GET()

    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate, max-age=0')
        super().end_headers()

    def log_message(self, format, *args):
        # Ignore logging live reload pings to keep stdout clean
        if "/__livereload__" in args[0] if len(args) > 0 else "":
            return
        super().log_message(format, *args)


class ThreadingLiveReloadServer(ThreadingTCPServer):
    allow_reuse_address = True

    def __init__(self, server_address, RequestHandlerClass, watch_dir, extensions):
        super().__init__(server_address, RequestHandlerClass)
        self.watch_dir = watch_dir
        self.extensions = extensions
        self.clients = []
        self.clients_lock = threading.Lock()
        self.running = True
        self.file_states = self._scan_directory()

        # Start directory watching thread
        self.watcher_thread = threading.Thread(target=self._watch_loop, daemon=True)
        self.watcher_thread.start()

    def register_client(self):
        import queue
        q = queue.Queue()
        with self.clients_lock:
            self.clients.append(q)
        return q

    def unregister_client(self, q):
        with self.clients_lock:
            if q in self.clients:
                self.clients.remove(q)

    def trigger_reload(self):
        with self.clients_lock:
            for q in self.clients:
                q.put('reload')

    def _scan_directory(self):
        """Scans the watch directory and returns a dict mapping file path to modification time."""
        states = {}
        for root, _, files in os.walk(self.watch_dir):
            for file in files:
                # Skip hidden files
                if file.startswith('.'):
                    continue
                ext = os.path.splitext(file)[1].lower()
                if not self.extensions or ext in self.extensions:
                    filepath = os.path.join(root, file)
                    try:
                        states[filepath] = os.path.getmtime(filepath)
                    except OSError:
                        pass
        return states

    def _watch_loop(self):
        """Monitors directory for changes and triggers reload."""
        print(f"Watching directory '{self.watch_dir}' for changes...")
        while self.running:
            time.sleep(0.5)
            current_states = self._scan_directory()
            changed = False

            # Check for modified or new files
            for filepath, mtime in current_states.items():
                if filepath not in self.file_states or current_states[filepath] > self.file_states[filepath]:
                    print(f"\n[Live Reload] File changed: {os.path.relpath(filepath, self.watch_dir)}")
                    changed = True
                    break

            # Check for deleted files
            if not changed:
                for filepath in self.file_states:
                    if filepath not in current_states:
                        print(f"\n[Live Reload] File deleted: {os.path.relpath(filepath, self.watch_dir)}")
                        changed = True
                        break

            if changed:
                self.file_states = current_states
                self.trigger_reload()


def main():
    parser = argparse.ArgumentParser(description="Live Reload HTTP Development Server")
    parser.add_argument('--port', type=int, default=8000, help='Port to run the server on (default: 8000)')
    parser.add_argument('--bind', default='127.0.0.1', help='IP address to bind the server to (default: 127.0.0.1)')
    parser.add_argument('--dir', default='.', help='Directory to serve and watch (default: current directory)')
    parser.add_argument('--ext', default='.html,.css,.js', help='Comma-separated file extensions to watch (default: .html,.css,.js)')

    args = parser.parse_args()

    watch_dir = os.path.abspath(args.dir)
    if not os.path.exists(watch_dir):
        print(f"Error: Directory '{watch_dir}' does not exist.")
        sys.exit(1)

    extensions = [ext.strip().lower() for ext in args.ext.split(',')] if args.ext else []
    # Ensure extensions start with a dot
    extensions = [ext if ext.startswith('.') else f".{ext}" for ext in extensions]

    print("==================================================")
    print(f"Starting Live Reload Server at http://{args.bind}:{args.port}")
    print(f"Serving directory: {watch_dir}")
    print(f"Watching extensions: {', '.join(extensions)}")
    print("Press Ctrl+C to stop the server")
    print("==================================================")

    # Change working directory so SimpleHTTPRequestHandler serves from correct folder
    os.chdir(watch_dir)

    server = None
    try:
        server = ThreadingLiveReloadServer((args.bind, args.port), LiveReloadHandler, watch_dir, extensions)
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping Live Reload Server...")
    finally:
        if server:
            server.running = False
            server.server_close()
        print("Server stopped.")

if __name__ == '__main__':
    main()
