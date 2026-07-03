#!/usr/bin/env python3
"""
Mock AWS SQS Server - A lightweight pure-Python local mock server for AWS SQS testing.
"""

import sys
import argparse
from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import urllib.parse
import uuid
import hashlib
import re

# ANSI colors
def get_color(color_name):
    colors = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'bold': '\033[1m',
        'cyan': '\033[96m',
        'reset': '\033[0m'
    }
    if sys.platform == 'win32':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        except Exception:
            return ''
    return colors.get(color_name, '')

# Global In-Memory Queue Store
# Format: { queue_name: [ { "id": str, "body": str, "receipt": str, "md5": str } ] }
QUEUES = {}

class SqsRequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        # Prevent default stdout logs to keep display clean, custom logging used
        pass

    def do_GET(self):
        # SQS GET requests can be used to list queues or query queue urls
        self.handle_request("GET")

    def do_POST(self):
        self.handle_request("POST")

    def get_post_params(self) -> dict:
        """Parse POST parameters from form-urlencoded or JSON body."""
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        content_type = self.headers.get('Content-Type', '')
        
        if 'application/x-amz-json' in content_type or 'application/json' in content_type:
            try:
                return json.loads(post_data.decode('utf-8'))
            except Exception:
                return {}
        else:
            # Query / urlencoded format
            params = urllib.parse.parse_qs(post_data.decode('utf-8'))
            # Simplify list values to single values
            return {k: v[0] for k, v in params.items()}

    def extract_queue_name(self, queue_url: str) -> str:
        """Extract queue name from SQS Queue URL."""
        if not queue_url:
            return ""
        parts = queue_url.rstrip('/').split('/')
        return parts[-1] if parts else ""

    def handle_request(self, method: str):
        colors = self.server.colors
        
        # Parse query params from URL (for GET or POST query fallbacks)
        parsed_url = urllib.parse.urlparse(self.path)
        url_params = urllib.parse.parse_qs(parsed_url.query)
        params = {k: v[0] for k, v in url_params.items()}
        
        # Merge POST params
        if method == "POST":
            params.update(self.get_post_params())
            
        # Determine Action
        # SQS uses either Action query parameter, Action POST parameter, or X-Amz-Target header
        action = params.get("Action")
        target_header = self.headers.get('X-Amz-Target', '')
        
        if not action and target_header:
            # Target header format: AmazonSQS.CreateQueue
            action = target_header.split('.')[-1]
            
        if not action:
            # SQS Query protocol fallback: Action might be in path or body
            action = "ListQueues" if parsed_url.path == "/" else "ReceiveMessage"
            
        # Standardize return format (XML or JSON)
        accept_header = self.headers.get('Accept', '')
        content_type = self.headers.get('Content-Type', '')
        is_json = 'json' in accept_header or 'json' in content_type or 'X-Amz-Target' in self.headers
        
        # Log HTTP Action
        print(f"[{colors['yellow']}REQUEST{colors['reset']}] Action: {colors['bold']}{action}{colors['reset']} (Format: {'JSON' if is_json else 'XML'})")
        
        # Execute Action
        status_code = 200
        response_data = ""
        
        # --- SQS ACTIONS IMPLEMENTATION ---
        
        if action == "CreateQueue":
            queue_name = params.get("QueueName")
            if not queue_name:
                # Boto3 JSON format
                queue_name = params.get("queueName")
                
            if not queue_name:
                status_code = 400
                response_data = self.make_error(is_json, "MissingParameter", "The request must contain the parameter QueueName.")
            else:
                queue_url = f"http://{self.headers.get('Host', 'localhost')}/queue/{queue_name}"
                QUEUES.setdefault(queue_name, [])
                print(f"  {colors['green']}✔ Queue Created:{colors['reset']} {queue_name}")
                
                if is_json:
                    response_data = json.dumps({"QueueUrl": queue_url})
                else:
                    response_data = (
                        f'<CreateQueueResponse>'
                        f'<CreateQueueResult><QueueUrl>{queue_url}</QueueUrl></CreateQueueResult>'
                        f'<ResponseMetadata><RequestId>{uuid.uuid4()}</RequestId></ResponseMetadata>'
                        f'</CreateQueueResponse>'
                    )

        elif action == "GetQueueUrl":
            queue_name = params.get("QueueName")
            if not queue_name:
                queue_name = params.get("queueName")
                
            if not queue_name or queue_name not in QUEUES:
                status_code = 404
                response_data = self.make_error(is_json, "QueueDoesNotExist", f"The specified queue {queue_name} does not exist.")
            else:
                queue_url = f"http://{self.headers.get('Host', 'localhost')}/queue/{queue_name}"
                if is_json:
                    response_data = json.dumps({"QueueUrl": queue_url})
                else:
                    response_data = (
                        f'<GetQueueUrlResponse>'
                        f'<GetQueueUrlResult><QueueUrl>{queue_url}</QueueUrl></GetQueueUrlResult>'
                        f'<ResponseMetadata><RequestId>{uuid.uuid4()}</RequestId></ResponseMetadata>'
                        f'</GetQueueUrlResponse>'
                    )

        elif action == "SendMessage":
            queue_url = params.get("QueueUrl") or params.get("queueUrl")
            queue_name = self.extract_queue_name(queue_url) or self.extract_queue_name(parsed_url.path)
            
            message_body = params.get("MessageBody") or params.get("messageBody")
            
            if not queue_name or queue_name not in QUEUES:
                status_code = 404
                response_data = self.make_error(is_json, "QueueDoesNotExist", "The specified queue does not exist.")
            elif not message_body:
                status_code = 400
                response_data = self.make_error(is_json, "MissingParameter", "The request must contain the parameter MessageBody.")
            else:
                msg_id = str(uuid.uuid4())
                md5_hash = hashlib.md5(message_body.encode('utf-8')).hexdigest()
                
                msg_obj = {
                    "id": msg_id,
                    "body": message_body,
                    "receipt": str(uuid.uuid4()),
                    "md5": md5_hash
                }
                QUEUES[queue_name].append(msg_obj)
                
                print(f"  {colors['green']}✔ Message Sent to {queue_name}:{colors['reset']} ID={msg_id} ({len(message_body)} bytes)")
                
                if is_json:
                    response_data = json.dumps({"MD5OfMessageBody": md5_hash, "MessageId": msg_id})
                else:
                    response_data = (
                        f'<SendMessageResponse>'
                        f'<SendMessageResult>'
                        f'<MD5OfMessageBody>{md5_hash}</MD5OfMessageBody>'
                        f'<MessageId>{msg_id}</MessageId>'
                        f'</SendMessageResult>'
                        f'<ResponseMetadata><RequestId>{uuid.uuid4()}</RequestId></ResponseMetadata>'
                        f'</SendMessageResponse>'
                    )

        elif action == "ReceiveMessage":
            queue_url = params.get("QueueUrl") or params.get("queueUrl")
            queue_name = self.extract_queue_name(queue_url) or self.extract_queue_name(parsed_url.path)
            
            max_msgs = int(params.get("MaxNumberOfMessages") or params.get("maxNumberOfMessages") or 1)
            
            if not queue_name or queue_name not in QUEUES:
                status_code = 404
                response_data = self.make_error(is_json, "QueueDoesNotExist", "The specified queue does not exist.")
            else:
                # Pop up to max_msgs messages
                # Simple implementation: messages are returned and kept in queue until deleted,
                # but for simple mock testing we will just yield them (they remain visible or invisible)
                # To simulate visibility timeout, we won't delete them yet, but we will return them.
                # In a basic mock, we can just yield messages and let the client delete them.
                # For simplicity, we just return them. (If visibility timeout is wanted, we could hide them,
                # but simple mocks can just list them).
                msgs = QUEUES[queue_name][:max_msgs]
                print(f"  {colors['green']}✔ ReceiveMessage from {queue_name}:{colors['reset']} returned {len(msgs)} messages")
                
                if is_json:
                    json_msgs = []
                    for m in msgs:
                        json_msgs.append({
                            "MessageId": m["id"],
                            "ReceiptHandle": m["receipt"],
                            "MD5OfBody": m["md5"],
                            "Body": m["body"]
                        })
                    response_data = json.dumps({"Messages": json_msgs})
                else:
                    msg_xml = ""
                    for m in msgs:
                        msg_xml += (
                            f'<Message>'
                            f'<MessageId>{m["id"]}</MessageId>'
                            f'<ReceiptHandle>{m["receipt"]}</ReceiptHandle>'
                            f'<MD5OfBody>{m["md5"]}</MD5OfBody>'
                            f'<Body>{m["body"]}</Body>'
                            f'</Message>'
                        )
                    response_data = (
                        f'<ReceiveMessageResponse>'
                        f'<ReceiveMessageResult>{msg_xml}</ReceiveMessageResult>'
                        f'<ResponseMetadata><RequestId>{uuid.uuid4()}</RequestId></ResponseMetadata>'
                        f'</ReceiveMessageResponse>'
                    )

        elif action == "DeleteMessage":
            queue_url = params.get("QueueUrl") or params.get("queueUrl")
            queue_name = self.extract_queue_name(queue_url) or self.extract_queue_name(parsed_url.path)
            receipt_handle = params.get("ReceiptHandle") or params.get("receiptHandle")
            
            if not queue_name or queue_name not in QUEUES:
                status_code = 404
                response_data = self.make_error(is_json, "QueueDoesNotExist", "The specified queue does not exist.")
            elif not receipt_handle:
                status_code = 400
                response_data = self.make_error(is_json, "MissingParameter", "The request must contain the parameter ReceiptHandle.")
            else:
                # Remove message matching receipt_handle
                queue = QUEUES[queue_name]
                original_len = len(queue)
                QUEUES[queue_name] = [m for m in queue if m["receipt"] != receipt_handle]
                
                deleted = original_len - len(QUEUES[queue_name])
                if deleted > 0:
                    print(f"  {colors['green']}✔ Message Deleted from {queue_name}{colors['reset']} (Receipt: {receipt_handle[:8]}...)")
                else:
                    print(f"  {colors['yellow']}⚠ Message delete attempted, but receipt handle not found in {queue_name}{colors['reset']}")
                    
                if is_json:
                    response_data = json.dumps({})
                else:
                    response_data = (
                        f'<DeleteMessageResponse>'
                        f'<ResponseMetadata><RequestId>{uuid.uuid4()}</RequestId></ResponseMetadata>'
                        f'</DeleteMessageResponse>'
                    )

        elif action == "ListQueues":
            urls = [f"http://{self.headers.get('Host', 'localhost')}/queue/{name}" for name in QUEUES.keys()]
            if is_json:
                response_data = json.dumps({"QueueUrls": urls})
            else:
                urls_xml = "".join(f"<QueueUrl>{url}</QueueUrl>" for url in urls)
                response_data = (
                    f'<ListQueuesResponse>'
                    f'<ListQueuesResult>{urls_xml}</ListQueuesResult>'
                    f'<ResponseMetadata><RequestId>{uuid.uuid4()}</RequestId></ResponseMetadata>'
                    f'</ListQueuesResponse>'
                )

        elif action == "PurgeQueue":
            queue_url = params.get("QueueUrl") or params.get("queueUrl")
            queue_name = self.extract_queue_name(queue_url) or self.extract_queue_name(parsed_url.path)
            
            if not queue_name or queue_name not in QUEUES:
                status_code = 404
                response_data = self.make_error(is_json, "QueueDoesNotExist", "The specified queue does not exist.")
            else:
                QUEUES[queue_name] = []
                print(f"  {colors['green']}✔ Queue Purged:{colors['reset']} {queue_name}")
                if is_json:
                    response_data = json.dumps({})
                else:
                    response_data = (
                        f'<PurgeQueueResponse>'
                        f'<ResponseMetadata><RequestId>{uuid.uuid4()}</RequestId></ResponseMetadata>'
                        f'</PurgeQueueResponse>'
                    )

        else:
            # Action not supported or unknown
            status_code = 404
            response_data = self.make_error(is_json, "InvalidAction", f"Action {action} is not supported by this mock server.")

        # Send response
        self.send_response(status_code)
        if is_json:
            self.send_header('Content-Type', 'application/json')
        else:
            self.send_header('Content-Type', 'text/xml')
        self.send_header('Content-Length', str(len(response_data)))
        self.end_headers()
        self.wfile.write(response_data.encode('utf-8'))

    def make_error(self, is_json: bool, code: str, message: str) -> str:
        """Helper to generate XML or JSON error messages."""
        if is_json:
            return json.dumps({
                "__type": code,
                "message": message
            })
        else:
            return (
                f'<ErrorResponse>'
                f'<Error>'
                f'<Type>Sender</Type>'
                f'<Code>{code}</Code>'
                f'<Message>{message}</Message>'
                f'<Detail/>'
                f'</Error>'
                f'<RequestId>{uuid.uuid4()}</RequestId>'
                f'</ErrorResponse>'
            )

def main():
    parser = argparse.ArgumentParser(
        description="Mock AWS SQS Server - Run a lightweight SQS server locally for testing purposes."
    )
    parser.add_argument("--listen-ip", default="127.0.0.1", help="IP address to listen on (default: 127.0.0.1)")
    parser.add_argument("--listen-port", type=int, default=9324, help="Port to listen on (default: 9324)")
    parser.add_argument("--create-queues", nargs="+", help="Pre-create these queue names on startup")

    args = parser.parse_args()

    colors = {
        'red': get_color('red'),
        'green': get_color('green'),
        'yellow': get_color('yellow'),
        'blue': get_color('blue'),
        'cyan': get_color('cyan'),
        'bold': get_color('bold'),
        'reset': get_color('reset')
    }

    # Pre-create queues if specified
    if args.create_queues:
        for q in args.create_queues:
            QUEUES[q] = []

    server = HTTPServer((args.listen_ip, args.listen_port), SqsRequestHandler)
    server.colors = colors

    print("=" * 65)
    print(f"{colors['bold']}{colors['green']}Mock AWS SQS Server Listening on:{colors['reset']} http://{args.listen_ip}:{args.listen_port}")
    if QUEUES:
        print(f"Pre-created queues:")
        for q in QUEUES.keys():
            print(f"  - {q}")
    print("=" * 65)
    print("Press Ctrl+C to stop the SQS server.\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print(f"\n{colors['yellow']}[*] Stopping SQS Server...{colors['reset']}")
    finally:
        server.server_close()

if __name__ == '__main__':
    main()
