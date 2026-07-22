#!/usr/bin/env python3
"""
HTTP Status Code Lookup & Offline Developer Reference
A CLI reference utility to look up HTTP status codes, definitions, RFC references, and debugging tips.

Features:
- Look up specific status codes directly (e.g. `200`, `418`).
- Search for status codes using text keywords (e.g. `teapot`, `auth`, `redirect`).
- List all status codes within a specific class (e.g. 4xx Client Errors, 5xx Server Errors).
- Provides comprehensive descriptions, RFC specifications, and actionable debugging advice.
"""

import sys
import json
import argparse
from typing import Dict, Any, List

# Configure stdout/stderr encoding to UTF-8
for stream in (sys.stdout, sys.stderr):
    if hasattr(stream, 'reconfigure'):
        try:
            stream.reconfigure(encoding='utf-8')
        except Exception:
            pass


# Local database of HTTP Status Codes
HTTP_STATUS_DATABASE: Dict[int, Dict[str, Any]] = {
    # 1xx Informational
    100: {
        "name": "Continue",
        "rfc": "RFC 9110, Section 15.2.1",
        "description": "The server has received the request headers and the client should proceed to send the request body.",
        "tips": "Commonly used with the 'Expect: 100-continue' header. If headers are rejected, the client avoids sending a large body."
    },
    101: {
        "name": "Switching Protocols",
        "rfc": "RFC 9110, Section 15.2.2",
        "description": "The requester has asked the server to switch protocols and the server has agreed to do so.",
        "tips": "Typically sent when upgrading to WebSockets (Upgrade: websocket)."
    },
    102: {
        "name": "Processing",
        "rfc": "RFC 2518 (WebDAV)",
        "description": "The server has received and is processing the request, but no response is available yet.",
        "tips": "Used in WebDAV or long-running requests to prevent client timeouts."
    },
    # 2xx Success
    200: {
        "name": "OK",
        "rfc": "RFC 9110, Section 15.3.1",
        "description": "Standard response for successful HTTP requests.",
        "tips": "The actual response depends on the request method (GET: body returned; POST: status of action; PUT/DELETE: execution state)."
    },
    201: {
        "name": "Created",
        "rfc": "RFC 9110, Section 15.3.2",
        "description": "The request has been fulfilled, resulting in the creation of a new resource.",
        "tips": "Should include a 'Location' header pointing to the URI of the newly created resource."
    },
    202: {
        "name": "Accepted",
        "rfc": "RFC 9110, Section 15.3.3",
        "description": "The request has been accepted for processing, but the processing has not been completed.",
        "tips": "Useful for asynchronous operations or batch processing. Response should specify where to poll for status."
    },
    204: {
        "name": "No Content",
        "rfc": "RFC 9110, Section 15.3.5",
        "description": "The server successfully processed the request, and is not returning any content.",
        "tips": "Commonly returned for successful DELETE or PUT actions where returning the resource representation is not necessary."
    },
    206: {
        "name": "Partial Content",
        "rfc": "RFC 9110, Section 15.3.7",
        "description": "The server is delivering only part of the resource due to a range header sent by the client.",
        "tips": "Used by download managers and streaming services to resume downloads or stream media in segments."
    },
    # 3xx Redirection
    301: {
        "name": "Moved Permanently",
        "rfc": "RFC 9110, Section 15.4.2",
        "description": "This and all future requests should be directed to the given URI.",
        "tips": "Modern browsers cache 301 redirects aggressively. If redirecting temporarily, use 302 or 307 instead."
    },
    302: {
        "name": "Found (Moved Temporarily)",
        "rfc": "RFC 9110, Section 15.4.3",
        "description": "The resource resides temporarily under a different URI.",
        "tips": "Used for temporary redirection. Many browsers change the method from POST to GET upon redirection."
    },
    304: {
        "name": "Not Modified",
        "rfc": "RFC 9110, Section 15.4.5",
        "description": "Indicates that the resource has not been modified since the version specified by the conditional headers (If-Modified-Since or If-None-Match).",
        "tips": "Extremely important for web performance. No response body is returned; the client loads the resource from local cache."
    },
    307: {
        "name": "Temporary Redirect",
        "rfc": "RFC 9110, Section 15.4.8",
        "description": "The request should be repeated with another URI; however, future requests should still use the original URI.",
        "tips": "Differs from 302 because the request method (e.g. POST) is guaranteed to NOT change on redirect."
    },
    308: {
        "name": "Permanent Redirect",
        "rfc": "RFC 9110, Section 15.4.9",
        "description": "The request and all future requests should be repeated using another URI.",
        "tips": "Differs from 301 because the request method (e.g. POST) is guaranteed to NOT change on redirect."
    },
    # 4xx Client Error
    400: {
        "name": "Bad Request",
        "rfc": "RFC 9110, Section 15.5.1",
        "description": "The server cannot or will not process the request due to an apparent client error.",
        "tips": "Check payload validation, missing query parameters, malformed JSON, or oversized headers."
    },
    401: {
        "name": "Unauthorized",
        "rfc": "RFC 9110, Section 15.5.2",
        "description": "Similar to 403 Forbidden, but specifically for use when authentication is required and has failed or has not yet been provided.",
        "tips": "Must include a 'WWW-Authenticate' header containing challenges applicable to the requested resource."
    },
    403: {
        "name": "Forbidden",
        "rfc": "RFC 9110, Section 15.5.4",
        "description": "The request was valid, but the server is refusing action. The user might not have the necessary permissions.",
        "tips": "Typically indicates credential validation succeeded but authorization failed (e.g. lack of RBAC roles)."
    },
    404: {
        "name": "Not Found",
        "rfc": "RFC 9110, Section 15.5.5",
        "description": "The requested resource could not be found but may be available in the future.",
        "tips": "Verify the endpoint path, spelling, URL parameters, or database IDs. Often used to hide existences of resources from unauthorized users."
    },
    405: {
        "name": "Method Not Allowed",
        "rfc": "RFC 9110, Section 15.5.6",
        "description": "A request method is not supported for the requested resource.",
        "tips": "Ensure you are sending GET/POST/PUT/DELETE appropriately. The response must generate an 'Allow' header indicating supported methods."
    },
    408: {
        "name": "Request Timeout",
        "rfc": "RFC 9110, Section 15.5.9",
        "description": "The server timed out waiting for the request.",
        "tips": "Common when network connections are slow or dropped during body transmission."
    },
    409: {
        "name": "Conflict",
        "rfc": "RFC 9110, Section 15.5.10",
        "description": "Indicates that the request could not be processed because of conflict in the current state of the resource.",
        "tips": "Commonly occurs during concurrent edits (optimistic locking conflicts) or unique constraint violations in databases."
    },
    413: {
        "name": "Payload Too Large",
        "rfc": "RFC 9110, Section 15.5.14",
        "description": "The request is larger than the server is willing or able to process.",
        "tips": "Check file upload limits in web server config (e.g., client_max_body_size in Nginx)."
    },
    415: {
        "name": "Unsupported Media Type",
        "rfc": "RFC 9110, Section 15.5.16",
        "description": "The request entity has a media type which the server or resource does not support.",
        "tips": "Verify the 'Content-Type' header of the request (e.g., application/json vs application/x-www-form-urlencoded)."
    },
    418: {
        "name": "I'm a teapot",
        "rfc": "RFC 2324 (HTCPCP/1.0)",
        "description": "Any attempt to brew coffee with a teapot should result in the error code 'I'm a teapot'.",
        "tips": "An April Fools' joke RFC. Used as an easter egg or for custom API testing."
    },
    429: {
        "name": "Too Many Requests",
        "rfc": "RFC 6585",
        "description": "The user has sent too many requests in a given amount of time.",
        "tips": "Indicates rate limiting is active. Response should include a 'Retry-After' header indicating how long to wait before retrying."
    },
    # 5xx Server Error
    500: {
        "name": "Internal Server Error",
        "rfc": "RFC 9110, Section 15.6.1",
        "description": "A generic error message, given when an unexpected condition was encountered and no more specific message is suitable.",
        "tips": "Check server backend logs, stack traces, unhandled exceptions, database connection state, or environment variables."
    },
    502: {
        "name": "Bad Gateway",
        "rfc": "RFC 9110, Section 15.6.3",
        "description": "The server, while acting as a gateway or proxy, received an invalid response from the upstream server.",
        "tips": "Occurs when backend application services (Node.js, Gunicorn, PHP-FPM) are offline or crashed."
    },
    503: {
        "name": "Service Unavailable",
        "rfc": "RFC 9110, Section 15.6.4",
        "description": "The server cannot handle the request (because it is overloaded or down for maintenance).",
        "tips": "Often temporary. A 'Retry-After' header should be sent. Check CPU/Memory utilization or active deployments."
    },
    504: {
        "name": "Gateway Timeout",
        "rfc": "RFC 9110, Section 15.6.5",
        "description": "The server, while acting as a gateway or proxy, did not receive a timely response from the upstream server.",
        "tips": " backend execution time exceeded HTTP server proxy timeout limits. Check database query performance or slow API calls."
    }
}


def print_code_details(code: int, info: Dict[str, Any]) -> None:
    """Pretty prints details of a single status code."""
    # Color output
    color = "\033[94m"  # Blue for info/success
    if code >= 300:
        color = "\033[93m"  # Yellow for redirects
    if code >= 400:
        color = "\033[91m"  # Red for client errors
    if code >= 500:
        color = "\033[95m"  # Magenta for server errors

    reset = "\033[0m"

    print(f"\n{color}[HTTP {code}] {info['name']}{reset}")
    print(f"  - Specification: {info['rfc']}")
    print(f"  - Description: {info['description']}")
    print(f"  - Debugging Tips: {info['tips']}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline HTTP Status Code Reference and Lookup utility.")
    parser.add_argument("query", nargs="?", type=str,
                        help="HTTP status code (e.g. 200) or text keyword query (e.g. 'unauthorized').")
    parser.add_argument("-c", "--class", type=int, choices=[1, 2, 3, 4, 5], dest="status_class",
                        help="List all status codes in a specific class (1 for 1xx, etc.).")
    parser.add_argument("--json", action="store_true", help="Output result as raw JSON.")

    args = parser.parse_args()

    results: Dict[int, Dict[str, Any]] = {}

    if args.status_class:
        # Filter by class
        for code, info in HTTP_STATUS_DATABASE.items():
            if code // 100 == args.status_class:
                results[code] = info
    elif args.query:
        # Check if query is integer
        try:
            code_int = int(args.query)
            if code_int in HTTP_STATUS_DATABASE:
                results[code_int] = HTTP_STATUS_DATABASE[code_int]
        except ValueError:
            # Text search
            query_lower = args.query.lower()
            for code, info in HTTP_STATUS_DATABASE.items():
                if (query_lower in info["name"].lower() or 
                    query_lower in info["description"].lower() or 
                    query_lower in info["tips"].lower()):
                    results[code] = info
    else:
        # Default: list all
        results = HTTP_STATUS_DATABASE

    if not results:
        print(f"No HTTP status codes matched query '{args.query}'.", file=sys.stderr)
        sys.exit(1)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        for code, info in sorted(results.items()):
            print_code_details(code, info)
        print()


if __name__ == "__main__":
    main()
