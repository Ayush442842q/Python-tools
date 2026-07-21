#!/usr/bin/env python3
"""
file_sharing_server - Local web-based file sharing server

A standalone HTTP server that allows users on the same local network to upload
and download files through a beautiful, modern, responsive web interface.

Usage:
    python tools/file_sharing_server.py [-p PORT] [-d DIRECTORY] [--read-only]

Options:
    -p, --port      Port to bind the server to (default: 8000)
    -d, --dir       Directory to share (default: current directory)
    -b, --bind      IP address to bind to (default: 0.0.0.0)
    --read-only     Disable file uploads

Example:
    python tools/file_sharing_server.py -p 8080 -d ~/Downloads
"""

import os
import re
import sys
import html
import socket
import urllib.parse
import http.server
import argparse
from datetime import datetime

# Define standard colors for terminal output
COLOR_BLUE = "\033[94m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_BOLD = "\033[1m"
COLOR_END = "\033[0m"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Local File Share - {current_path}</title>
    <style>
        :root {{
            --bg-color: #0f172a;
            --container-bg: #1e293b;
            --text-color: #f1f5f9;
            --text-muted: #94a3b8;
            --primary-color: #3b82f6;
            --primary-hover: #2563eb;
            --success-color: #10b981;
            --border-color: #334155;
            --hover-bg: #334155;
        }}
        body {{
            font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-color);
            margin: 0;
            padding: 2rem 1rem;
            display: flex;
            justify-content: center;
        }}
        .container {{
            max-width: 900px;
            width: 100%;
            background: var(--container-bg);
            border-radius: 12px;
            box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3);
            padding: 2rem;
            border: 1px solid var(--border-color);
        }}
        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid var(--border-color);
            padding-bottom: 1.5rem;
            margin-bottom: 1.5rem;
        }}
        h1 {{
            font-size: 1.6rem;
            margin: 0;
            color: #ffffff;
            font-weight: 700;
        }}
        .path-breadcrumb {{
            font-size: 0.95rem;
            color: var(--text-muted);
            margin-top: 0.5rem;
            word-break: break-all;
        }}
        .path-link {{
            color: var(--primary-color);
            text-decoration: none;
        }}
        .path-link:hover {{
            text-decoration: underline;
        }}
        .toast {{
            padding: 1rem;
            border-radius: 8px;
            margin-bottom: 1.5rem;
            font-weight: 500;
        }}
        .toast-success {{
            background: rgba(16, 185, 129, 0.15);
            color: var(--success-color);
            border: 1px solid var(--success-color);
        }}
        .toast-error {{
            background: rgba(239, 68, 68, 0.15);
            color: #ef4444;
            border: 1px solid #ef4444;
        }}
        .upload-card {{
            background: rgba(59, 130, 246, 0.03);
            border: 2px dashed var(--primary-color);
            border-radius: 8px;
            padding: 2rem;
            text-align: center;
            margin-bottom: 2rem;
            transition: all 0.2s ease-in-out;
        }}
        .upload-card:hover {{
            background: rgba(59, 130, 246, 0.08);
            border-color: var(--primary-hover);
        }}
        .upload-form {{
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 1rem;
        }}
        .file-select {{
            background: #0f172a;
            border: 1px solid var(--border-color);
            color: var(--text-color);
            padding: 0.5rem;
            border-radius: 6px;
            cursor: pointer;
            width: 100%;
            max-width: 300px;
        }}
        .btn {{
            background: var(--primary-color);
            color: white;
            padding: 0.6rem 1.5rem;
            border-radius: 6px;
            border: none;
            cursor: pointer;
            font-weight: 600;
            transition: background 0.2s;
            font-size: 0.95rem;
        }}
        .btn:hover {{
            background: var(--primary-hover);
        }}
        .table-container {{
            overflow-x: auto;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
        }}
        th {{
            color: var(--text-muted);
            font-weight: 600;
            padding: 0.75rem 1rem;
            border-bottom: 2px solid var(--border-color);
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        td {{
            padding: 0.9rem 1rem;
            border-bottom: 1px solid var(--border-color);
            font-size: 0.95rem;
        }}
        tr:hover td {{
            background: rgba(255, 255, 255, 0.02);
        }}
        .item-name {{
            color: var(--text-color);
            text-decoration: none;
            font-weight: 500;
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .item-name:hover {{
            color: var(--primary-color);
        }}
        .icon {{
            font-size: 1.1rem;
        }}
        .meta-col {{
            color: var(--text-muted);
            white-space: nowrap;
        }}
        .empty-state {{
            text-align: center;
            padding: 3rem;
            color: var(--text-muted);
            font-style: italic;
        }}
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div>
                <h1>Local File Sharing Server</h1>
                <div class="path-breadcrumb">
                    Current Directory: {breadcrumb}
                </div>
            </div>
            <div>
                <a href=".." class="btn" style="background: transparent; border: 1px solid var(--border-color); text-decoration: none; color: var(--text-color);">Up a Directory</a>
            </div>
        </header>

        {toast_msg}

        {upload_section}

        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Name</th>
                        <th>Size</th>
                        <th>Last Modified</th>
                    </tr>
                </thead>
                <tbody>
                    {file_rows}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""

def format_size(size):
    """Format file size in human-readable notation."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}" if unit != 'B' else f"{size} B"
        size /= 1024.0
    return f"{size:.1f} PB"

def get_local_ip_addresses():
    """Find all active local IP addresses for this machine."""
    ips = []
    # Try getting primary LAN IP first
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        primary_ip = s.getsockname()[0]
        s.close()
        ips.append(primary_ip)
    except Exception:
        pass
    
    # Backup: get all hostname IPs
    try:
        hostname = socket.gethostname()
        for ip in socket.gethostbyname_ex(hostname)[2]:
            if ip not in ips and not ip.startswith("127."):
                ips.append(ip)
    except Exception:
        pass
        
    if not ips:
        ips.append("127.0.0.1")
    return ips

class FileSharingHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    server_dir = os.getcwd()
    read_only = False

    def translate_path(self, path):
        """Translate URL path to local directory structure, relative to server_dir."""
        # Standard translate_path resolves relative to os.getcwd()
        # We temporarily change to server_dir to let super translate it correctly
        old_cwd = os.getcwd()
        try:
            os.chdir(self.server_dir)
            resolved_path = super().translate_path(path)
            # Prevent path traversal outside server_dir
            real_server_dir = os.path.realpath(self.server_dir)
            real_resolved_path = os.path.realpath(resolved_path)
            if not real_resolved_path.startswith(real_server_dir):
                return real_server_dir
            return resolved_path
        finally:
            os.chdir(old_cwd)

    def do_GET(self):
        """Serve GET requests, providing custom directory index or standard files."""
        path = self.translate_path(self.path)
        if os.path.isdir(path):
            # If the path doesn't end with a slash, redirect to have one
            if not self.path.endswith('/'):
                self.send_response(301)
                self.send_header("Location", self.path + "/")
                self.end_headers()
                return
            
            # Serve custom directory listing page
            self.serve_directory_index(path)
        else:
            # Serve standard file
            super().do_GET()

    def do_POST(self):
        """Handle POST file upload requests."""
        if self.read_only:
            self.send_error(403, "File upload is disabled (Read-only mode)")
            return

        success, message = self.save_uploaded_file()
        
        # Determine redirect path (back to the current directory URL)
        # Avoid query parameters stacking up
        redirect_url = urllib.parse.urlparse(self.path).path
        status_param = "success" if success else "error"
        redirect_url += f"?status={status_param}&msg={urllib.parse.quote(message)}"

        self.send_response(303)
        self.send_header("Location", redirect_url)
        self.end_headers()

    def save_uploaded_file(self):
        """Parse multipart form-data and save the file to local path."""
        content_type = self.headers.get('content-type', '')
        if not content_type or 'multipart/form-data' not in content_type:
            return False, "Invalid Content-Type (must be multipart/form-data)"
            
        boundary_match = re.search(r'boundary=([^;]+)', content_type)
        if not boundary_match:
            return False, "Multipart boundary not found in Content-Type"
            
        boundary = boundary_match.group(1).encode()
        try:
            content_length = int(self.headers.get('content-length', 0))
        except ValueError:
            return False, "Invalid Content-Length header"

        if content_length <= 0:
            return False, "Empty request body"

        # Locate correct output directory based on request URL
        target_dir = self.translate_path(self.path)
        if not os.path.isdir(target_dir):
            return False, "Target directory does not exist"

        # Read multipart stream
        rfile = self.rfile
        
        # Read the first boundary line
        line = rfile.readline()
        if boundary not in line:
            return False, "Request does not start with boundary"

        # Read headers for the part
        part_headers = {}
        while True:
            line = rfile.readline()
            if not line or line == b'\r\n':
                break
            header_text = line.decode('utf-8', errors='ignore').strip()
            if ':' in header_text:
                k, v = header_text.split(':', 1)
                part_headers[k.strip().lower()] = v.strip()

        # Parse filename from Content-Disposition
        content_disp = part_headers.get('content-disposition', '')
        fn_match = re.search(r'filename="([^"]+)"', content_disp)
        if not fn_match:
            return False, "No file uploaded (missing filename in headers)"
            
        filename = fn_match.group(1)
        filename = os.path.basename(filename)  # Protection against path traversal
        if not filename:
            return False, "Uploaded file has no name"

        # Skip headers ending line
        out_filepath = os.path.join(target_dir, filename)
        
        # Write binary file chunk by chunk
        try:
            with open(out_filepath, 'wb') as f:
                # Read the body and strip the boundary at the end
                boundary_line = b'\r\n--' + boundary
                
                # Keep a small buffer to scan for boundary
                buffer_size = 65536
                buffer = rfile.read(buffer_size)
                
                while buffer:
                    boundary_idx = buffer.find(boundary_line)
                    if boundary_idx != -1:
                        # Found the boundary, write data before it and exit
                        f.write(buffer[:boundary_idx])
                        break
                    
                    # If boundary isn't fully in buffer, check if it could be partially cut off at the end
                    # Length of boundary_line is len(boundary_line)
                    overlap = len(boundary_line)
                    if len(buffer) > overlap:
                        # Write everything except the potential overlap at the end
                        f.write(buffer[:-overlap])
                        # Keep the overlap for the next read
                        buffer = buffer[-overlap:] + rfile.read(buffer_size)
                    else:
                        # Buffer is too small, just read more
                        buffer += rfile.read(buffer_size)
                        
                    if len(buffer) == 0:
                        break
            
            return True, f"File '{filename}' successfully uploaded."
        except Exception as e:
            return False, f"Error saving file: {str(e)}"

    def serve_directory_index(self, path):
        """Generate a custom, modern directory list webpage."""
        try:
            dir_list = os.listdir(path)
        except OSError:
            self.send_error(404, "Directory permission denied or not found")
            return

        # Sort: directories first, then files (alphabetically)
        items = []
        for name in dir_list:
            if name.startswith('.'):
                continue
            item_path = os.path.join(path, name)
            is_dir = os.path.isdir(item_path)
            try:
                stat = os.stat(item_path)
                size = format_size(stat.st_size) if not is_dir else "-"
                mtime = datetime.fromtimestamp(stat.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
            except Exception:
                size = "Error"
                mtime = "Error"
            items.append((is_dir, name, size, mtime))

        items.sort(key=lambda x: (not x[0], x[1].lower()))

        # Build breadcrumbs
        # Calculate path relative to server_dir
        rel_path = os.path.relpath(path, self.server_dir)
        if rel_path == '.' or rel_path == '':
            rel_parts = []
        else:
            rel_parts = rel_path.split(os.sep)

        breadcrumb_links = ['<a href="/" class="path-link">Home</a>']
        accumulated = ""
        for part in rel_parts:
            accumulated += f"/{part}"
            breadcrumb_links.append(f'<a href="{accumulated}" class="path-link">{html.escape(part)}</a>')
        
        breadcrumb = " / ".join(breadcrumb_links)

        # Build file list rows
        file_rows = ""
        # Add parent directory link if not in home
        if rel_parts:
            file_rows += f"""
            <tr>
                <td><a href=".." class="item-name"><span class="icon">📁</span> .. (Parent Directory)</a></td>
                <td class="meta-col">-</td>
                <td class="meta-col">-</td>
            </tr>
            """

        for is_dir, name, size, mtime in items:
            icon = "📁" if is_dir else "📄"
            # Standardize URL escaping for path items
            escaped_name = urllib.parse.quote(name)
            url = f"{escaped_name}/" if is_dir else escaped_name
            
            file_rows += f"""
            <tr>
                <td><a href="{url}" class="item-name"><span class="icon">{icon}</span> {html.escape(name)}</a></td>
                <td class="meta-col">{html.escape(size)}</td>
                <td class="meta-col">{html.escape(mtime)}</td>
            </tr>
            """

        if not items and not rel_parts:
            file_rows = '<tr><td colspan="3" class="empty-state">No files or folders in this directory.</td></tr>'

        # Build toast message from GET query parameters
        toast_msg = ""
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        
        if 'status' in params and 'msg' in params:
            status = params['status'][0]
            msg = params['msg'][0]
            toast_class = "toast-success" if status == "success" else "toast-error"
            toast_msg = f'<div class="toast {toast_class}">{html.escape(msg)}</div>'

        # Build upload section
        if self.read_only:
            upload_section = '<div style="color: var(--text-muted); font-style: italic; margin-bottom: 2rem; border: 1px solid var(--border-color); padding: 1rem; border-radius: 8px; text-align: center;">Uploads are disabled (Read-only mode).</div>'
        else:
            upload_section = f"""
            <div class="upload-card">
                <form action="" method="post" enctype="multipart/form-data" class="upload-form">
                    <h3 style="margin: 0; color: #fff;">Upload File to this Folder</h3>
                    <input type="file" name="file" class="file-select" required>
                    <button type="submit" class="btn">Upload File</button>
                </form>
            </div>
            """

        html_content = HTML_TEMPLATE.format(
            current_path=html.escape(rel_path if rel_parts else "Home"),
            breadcrumb=breadcrumb,
            toast_msg=toast_msg,
            upload_section=upload_section,
            file_rows=file_rows
        )

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html_content.encode('utf-8'))

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Local web-based file sharing server with upload and download capabilities.")
    parser.add_argument('-p', '--port', type=int, default=8000, help='Port to run the server on (default: 8000)')
    parser.add_argument('-d', '--dir', type=str, default=os.getcwd(), help='Directory to share (default: current directory)')
    parser.add_argument('-b', '--bind', type=str, default='0.0.0.0', help='IP address to bind to (default: 0.0.0.0)')
    parser.add_argument('--read-only', action='store_true', help='Disable file uploads')

    args = parser.parse_args()

    # Resolve shared directory path
    shared_dir = os.path.abspath(args.dir)
    if not os.path.isdir(shared_dir):
        print(f"{COLOR_RED}Error: Shared directory '{shared_dir}' does not exist.{COLOR_END}", file=sys.stderr)
        return 1

    # Configure our handler class
    FileSharingHTTPRequestHandler.server_dir = shared_dir
    FileSharingHTTPRequestHandler.read_only = args.read_only

    # Print server details
    print(f"\n{COLOR_GREEN}{COLOR_BOLD}=== Local File Sharing Server ==={COLOR_END}")
    print(f"Sharing Directory: {COLOR_BLUE}{shared_dir}{COLOR_END}")
    print(f"Mode: {'Read-Only' if args.read_only else 'Read-Write (Uploads Allowed)'}")
    print(f"Binding Address: {args.bind}\n")

    # Get local IPs to show user how to connect
    local_ips = get_local_ip_addresses()
    print(f"{COLOR_BOLD}Available URLs to access this server:{COLOR_END}")
    for ip in local_ips:
        url = f"http://{ip}:{args.port}"
        print(f"  - {COLOR_GREEN}{url}{COLOR_END}")
    print(f"  - {COLOR_GREEN}http://localhost:{args.port}{COLOR_END} (Local machine only)")
    print(f"\nPress Ctrl+C to stop the server.\n")

    # Start HTTP server
    try:
        server = http.server.HTTPServer((args.bind, args.port), FileSharingHTTPRequestHandler)
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\n{COLOR_YELLOW}Server stopped by user.{COLOR_END}")
    except Exception as e:
        print(f"{COLOR_RED}Error: {e}{COLOR_END}", file=sys.stderr)
        return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
