#!/usr/bin/env python3
"""
Mock S3 Server - A standalone, local mock Amazon S3 HTTP server

This tool launches a lightweight mock Amazon S3 server using only standard libraries.
It parses and answers S3-compatible HTTP API calls, persisting buckets and objects
in a local folder. This is useful for testing S3 client code (boto3, aws-cli, etc.)
locally without touching actual AWS infrastructure.

Supported Operations:
    - List Buckets: GET /
    - Create Bucket: PUT /{bucket}
    - Delete Bucket: DELETE /{bucket}
    - List Objects: GET /{bucket}
    - Get Object: GET /{bucket}/{key}
    - Put Object: PUT /{bucket}/{key}
    - Delete Object: DELETE /{bucket}/{key}
    - Head Object: HEAD /{bucket}/{key}

Usage:
    python tools/mock_s3_server.py [--port 8000] [--data-dir ./s3_mock_data]
"""

import argparse
import datetime
import hashlib
import mimetypes
import os
import shutil
import sys
import urllib.parse
from http.server import HTTPServer, BaseHTTPRequestHandler
from xml.sax.saxutils import escape

# Constants
XML_DECLARATION = '<?xml version="1.0" encoding="UTF-8"?>\n'
S3_NAMESPACE = ' xmlns="http://s3.amazonaws.com/doc/2006-03-01/"'


def get_md5(file_path: str) -> str:
    """Calculates MD5 hash of a file to return as ETag."""
    hasher = hashlib.md5()
    try:
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hasher.update(chunk)
        return hasher.hexdigest()
    except IOError:
        return ""


def get_formatted_time(timestamp: float) -> str:
    """Formats timestamp into S3-compatible ISO 8601 string."""
    dt = datetime.datetime.fromtimestamp(timestamp, datetime.timezone.utc)
    return dt.strftime('%Y-%m-%dT%H:%M:%S.000Z')


class MockS3Handler(BaseHTTPRequestHandler):
    data_dir = "./s3_mock_data"

    def log_message(self, format, *args):
        # Override default server logs to use stdout with customized prefix
        sys.stdout.write(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] S3 Mock API: {format % args}\n")

    def _get_path_info(self) -> tuple:
        """Parses path to extract bucket name and object key."""
        parsed = urllib.parse.urlparse(self.path)
        path = urllib.parse.unquote(parsed.path).lstrip('/')
        
        parts = path.split('/', 1)
        bucket = parts[0] if parts[0] else None
        key = parts[1] if len(parts) > 1 and parts[1] else None
        
        query = urllib.parse.parse_qs(parsed.query)
        return bucket, key, query

    def _send_xml_response(self, status: int, xml_content: str):
        """Sends an XML response with proper headers."""
        response_body = (XML_DECLARATION + xml_content).encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'application/xml')
        self.send_header('Content-Length', str(len(response_body)))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(response_body)

    def _send_error(self, code: str, message: str, status: int = 400, resource: str = ""):
        """Sends an S3-compatible XML error response."""
        xml = f"""<Error>
  <Code>{code}</Code>
  <Message>{escape(message)}</Message>
  <Resource>{escape(resource)}</Resource>
  <RequestId>MOCKS3REQUESTID</RequestId>
</Error>"""
        self._send_xml_response(status, xml)

    def do_GET(self):
        bucket, key, query = self._get_path_info()

        # 1. List Buckets
        if not bucket:
            self._list_buckets()
            return

        bucket_path = os.path.join(self.data_dir, bucket)
        if not os.path.exists(bucket_path) or not os.path.isdir(bucket_path):
            self._send_error("NoSuchBucket", "The specified bucket does not exist", 404, bucket)
            return

        # 2. List Objects (No key provided)
        if not key:
            self._list_objects(bucket, bucket_path, query)
            return

        # 3. Get Object
        self._get_object(bucket, key, bucket_path)

    def do_HEAD(self):
        bucket, key, _ = self._get_path_info()
        if not bucket or not key:
            self.send_response(400)
            self.end_headers()
            return

        bucket_path = os.path.join(self.data_dir, bucket)
        if not os.path.exists(bucket_path):
            self.send_response(404)
            self.end_headers()
            return

        obj_path = os.path.join(bucket_path, key)
        # Prevent Directory Traversal
        if not os.path.abspath(obj_path).startswith(os.path.abspath(bucket_path)):
            self.send_response(403)
            self.end_headers()
            return

        if not os.path.exists(obj_path) or os.path.isdir(obj_path):
            self.send_response(404)
            self.end_headers()
            return

        # Get object info
        stat = os.stat(obj_path)
        etag = get_md5(obj_path)
        mime_type, _ = mimetypes.guess_type(obj_path)
        if not mime_type:
            mime_type = 'application/octet-stream'

        self.send_response(200)
        self.send_header('Content-Type', mime_type)
        self.send_header('Content-Length', str(stat.st_size))
        self.send_header('ETag', f'"{etag}"')
        self.send_header('Last-Modified', get_formatted_time(stat.st_mtime))
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

    def do_PUT(self):
        bucket, key, _ = self._get_path_info()
        if not bucket:
            self._send_error("MethodNotAllowed", "Bucket name must be specified", 405)
            return

        bucket_path = os.path.join(self.data_dir, bucket)

        # 1. Create Bucket
        if not key:
            try:
                os.makedirs(bucket_path, exist_ok=True)
                self.send_response(200)
                self.send_header('Content-Length', '0')
                self.send_header('Location', f'/{bucket}')
                self.end_headers()
            except Exception as e:
                self._send_error("InternalError", f"Failed to create bucket: {e}", 500, bucket)
            return

        # 2. Put Object
        if not os.path.exists(bucket_path):
            self._send_error("NoSuchBucket", "The specified bucket does not exist to upload to", 404, bucket)
            return

        obj_path = os.path.join(bucket_path, key)
        # Prevent Directory Traversal
        if not os.path.abspath(obj_path).startswith(os.path.abspath(bucket_path)):
            self._send_error("AccessDenied", "Directory traversal forbidden", 403)
            return

        try:
            # Create subdirectories if key contains slashes
            os.makedirs(os.path.dirname(obj_path), exist_ok=True)
            
            content_length = int(self.headers.get('Content-Length', 0))
            
            with open(obj_path, 'wb') as f:
                remaining = content_length
                while remaining > 0:
                    chunk_size = min(remaining, 65536)
                    chunk = self.rfile.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    remaining -= len(chunk)
            
            etag = get_md5(obj_path)
            self.send_response(200)
            self.send_header('ETag', f'"{etag}"')
            self.send_header('Content-Length', '0')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
        except Exception as e:
            self._send_error("InternalError", f"Failed to upload object: {e}", 500, f"{bucket}/{key}")

    def do_DELETE(self):
        bucket, key, _ = self._get_path_info()
        if not bucket:
            self._send_error("MethodNotAllowed", "Bucket name must be specified", 405)
            return

        bucket_path = os.path.join(self.data_dir, bucket)
        if not os.path.exists(bucket_path):
            self._send_error("NoSuchBucket", "The specified bucket does not exist", 404, bucket)
            return

        # 1. Delete Bucket
        if not key:
            try:
                # Check if bucket is empty (can configure to force delete or standard S3 empty delete block)
                if os.listdir(bucket_path):
                    self._send_error("BucketNotEmpty", "The bucket you tried to delete is not empty", 409, bucket)
                    return
                os.rmdir(bucket_path)
                self.send_response(204)  # No content
                self.end_headers()
            except Exception as e:
                self._send_error("InternalError", f"Failed to delete bucket: {e}", 500, bucket)
            return

        # 2. Delete Object
        obj_path = os.path.join(bucket_path, key)
        # Prevent Directory Traversal
        if not os.path.abspath(obj_path).startswith(os.path.abspath(bucket_path)):
            self._send_error("AccessDenied", "Directory traversal forbidden", 403)
            return

        if not os.path.exists(obj_path) or os.path.isdir(obj_path):
            self._send_error("NoSuchKey", "The specified key does not exist", 404, f"{bucket}/{key}")
            return

        try:
            os.remove(obj_path)
            # Remove empty parent folders recursively up to bucket root
            parent = os.path.dirname(obj_path)
            while parent != bucket_path:
                if not os.listdir(parent):
                    os.rmdir(parent)
                    parent = os.path.dirname(parent)
                else:
                    break
                    
            self.send_response(204)
            self.end_headers()
        except Exception as e:
            self._send_error("InternalError", f"Failed to delete object: {e}", 500, f"{bucket}/{key}")

    def _list_buckets(self):
        """Builds XML list of existing buckets (directories)."""
        buckets_xml = []
        if os.path.exists(self.data_dir):
            for entry in os.listdir(self.data_dir):
                entry_path = os.path.join(self.data_dir, entry)
                if os.path.isdir(entry_path):
                    stat = os.stat(entry_path)
                    created = get_formatted_time(stat.st_ctime)
                    buckets_xml.append(f"""    <Bucket>
      <Name>{escape(entry)}</Name>
      <CreationDate>{created}</CreationDate>
    </Bucket>""")
                    
        xml = f"""<ListAllMyBucketsResult{S3_NAMESPACE}>
  <Buckets>
{"\n".join(buckets_xml)}
  </Buckets>
  <Owner>
    <ID>mock-s3-owner-id</ID>
    <DisplayName>mock-s3-owner</DisplayName>
  </Owner>
</ListAllMyBucketsResult>"""
        self._send_xml_response(200, xml)

    def _list_objects(self, bucket: str, bucket_path: str, query: dict):
        """Lists objects (files) inside a bucket directory."""
        prefix = query.get('prefix', [''])[0]
        delimiter = query.get('delimiter', [''])[0]
        marker = query.get('marker', [''])[0]
        max_keys = int(query.get('max-keys', ['1000'])[0])

        contents_xml = []
        common_prefixes = set()

        # Recursively walk directories to gather files
        all_keys = []
        for root, dirs, files in os.walk(bucket_path):
            for file in files:
                full_path = os.path.join(root, file)
                # Compute key (relative path from bucket root)
                key = os.path.relpath(full_path, bucket_path).replace('\\', '/')
                
                # Filter prefix
                if not key.startswith(prefix):
                    continue
                # Filter marker
                if marker and key <= marker:
                    continue
                all_keys.append((key, full_path))

        # Sort alphabetically as S3 does
        all_keys.sort()

        truncated = False
        count = 0

        for key, full_path in all_keys:
            if count >= max_keys:
                truncated = True
                break

            # Handle delimiters for virtual folders
            if delimiter:
                relative_to_prefix = key[len(prefix):]
                delim_pos = relative_to_prefix.find(delimiter)
                if delim_pos != -1:
                    virt_folder = prefix + relative_to_prefix[:delim_pos + 1]
                    common_prefixes.add(virt_folder)
                    continue

            # Standard S3 object metadata
            stat = os.stat(full_path)
            last_modified = get_formatted_time(stat.st_mtime)
            etag = get_md5(full_path)
            size = stat.st_size
            
            contents_xml.append(f"""  <Contents>
    <Key>{escape(key)}</Key>
    <LastModified>{last_modified}</LastModified>
    <ETag>"{etag}"</ETag>
    <Size>{size}</Size>
    <StorageClass>STANDARD</StorageClass>
    <Owner>
      <ID>mock-s3-owner-id</ID>
      <DisplayName>mock-s3-owner</DisplayName>
    </Owner>
  </Contents>""")
            count += 1

        common_prefixes_xml = []
        for cp in sorted(common_prefixes):
            common_prefixes_xml.append(f"  <CommonPrefixes>\n    <Prefix>{escape(cp)}</Prefix>\n  </CommonPrefixes>")

        xml = f"""<ListBucketResult{S3_NAMESPACE}>
  <Name>{escape(bucket)}</Name>
  <Prefix>{escape(prefix)}</Prefix>
  <Marker>{escape(marker)}</Marker>
  <MaxKeys>{max_keys}</MaxKeys>
  <Delimiter>{escape(delimiter)}</Delimiter>
  <IsTruncated>{'true' if truncated else 'false'}</IsTruncated>
{"\n".join(contents_xml)}
{"\n".join(common_prefixes_xml)}
</ListBucketResult>"""
        self._send_xml_response(200, xml)

    def _get_object(self, bucket: str, key: str, bucket_path: str):
        """Fetches and sends object file data."""
        obj_path = os.path.join(bucket_path, key)
        # Prevent Directory Traversal
        if not os.path.abspath(obj_path).startswith(os.path.abspath(bucket_path)):
            self._send_error("AccessDenied", "Directory traversal forbidden", 403)
            return

        if not os.path.exists(obj_path) or os.path.isdir(obj_path):
            self._send_error("NoSuchKey", "The specified key does not exist", 404, f"{bucket}/{key}")
            return

        try:
            stat = os.stat(obj_path)
            etag = get_md5(obj_path)
            mime_type, _ = mimetypes.guess_type(obj_path)
            if not mime_type:
                mime_type = 'application/octet-stream'

            self.send_response(200)
            self.send_header('Content-Type', mime_type)
            self.send_header('Content-Length', str(stat.st_size))
            self.send_header('ETag', f'"{etag}"')
            self.send_header('Last-Modified', get_formatted_time(stat.st_mtime))
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()

            # Stream file content to response
            with open(obj_path, 'rb') as f:
                shutil.copyfileobj(f, self.wfile)
        except Exception as e:
            self._send_error("InternalError", f"Failed to read object: {e}", 500, f"{bucket}/{key}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Launch a lightweight local S3 mock server."
    )
    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Host address to bind the server to (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to run the S3 mock server on (default: 8000)"
    )
    parser.add_argument(
        "--data-dir",
        default="./s3_mock_data",
        help="Directory to store mock S3 buckets and files (default: ./s3_mock_data)"
    )

    args = parser.parse_args()

    # Configure handler class storage path
    MockS3Handler.data_dir = os.path.abspath(args.data_dir)
    os.makedirs(MockS3Handler.data_dir, exist_ok=True)

    server = HTTPServer((args.host, args.port), MockS3Handler)
    
    print("=" * 60)
    print("Mock Amazon S3 Local HTTP Server")
    print("=" * 60)
    print(f"Server Endpoint: http://{args.host}:{args.port}")
    print(f"Data Directory:  {MockS3Handler.data_dir}")
    print("-" * 60)
    print("Press Ctrl+C to terminate...")
    print("-" * 60)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Mock S3 server...")
        server.server_close()
        sys.exit(0)


if __name__ == '__main__':
    main()
