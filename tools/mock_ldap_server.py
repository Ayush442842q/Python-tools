#!/usr/bin/env python3
"""
Mock LDAP Directory Server - A pure-Python lightweight server for testing LDAP Bind and Search.
"""

import sys
import socket
import argparse
import threading
import json

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

# --- ASN.1 BER helper functions ---

def encode_len(length: int) -> bytes:
    """Encode length according to ASN.1 BER rules."""
    if length < 128:
        return bytes([length])
    # Long form
    temp = bytearray()
    while length > 0:
        temp.append(length & 0xff)
        length >>= 8
    temp.reverse()
    return bytes([0x80 | len(temp)]) + bytes(temp)

def decode_len(data: bytes, offset: int) -> tuple:
    """Decode ASN.1 BER length. Returns (length, bytes_consumed)."""
    if offset >= len(data):
        return 0, 0
    first = data[offset]
    if first < 128:
        return first, 1
    # Long form
    num_bytes = first & 0x7f
    if offset + 1 + num_bytes > len(data):
        return 0, 0
    val = 0
    for i in range(num_bytes):
        val = (val << 8) | data[offset + 1 + i]
    return val, 1 + num_bytes

def encode_integer(val: int) -> bytes:
    """Encode an integer as ASN.1 BER INTEGER."""
    if val == 0:
        return b'\x02\x01\x00'
    
    # Calculate bytes (signed)
    temp = bytearray()
    # Handle negative integers if any (though usually not needed here)
    if val < 0:
        val = (1 << (val.bit_length() + 8)) + val
    
    while val > 0:
        temp.append(val & 0xff)
        val >>= 8
        
    # Ensure proper sign bit padding if necessary
    if temp and temp[-1] >= 128:
        temp.append(0x00)
        
    temp.reverse()
    return b'\x02' + encode_len(len(temp)) + bytes(temp)

def encode_octet_string(s: bytes) -> bytes:
    """Encode bytes as ASN.1 BER OCTET STRING."""
    return b'\x04' + encode_len(len(s)) + s

def encode_enumerated(val: int) -> bytes:
    """Encode an integer as ASN.1 BER ENUMERATED (tag 0x0A)."""
    return b'\x0a\x01' + bytes([val & 0xff])

def encode_sequence(content: bytes, tag: int = 0x30) -> bytes:
    """Encode content into an ASN.1 BER SEQUENCE container."""
    return bytes([tag]) + encode_len(len(content)) + content

def parse_ber_node(data: bytes, offset: int) -> tuple:
    """Parse a single BER node. Returns (tag, content, next_offset)."""
    if offset >= len(data):
        return None, None, offset
    tag = data[offset]
    length, consumed = decode_len(data, offset + 1)
    content_start = offset + 1 + consumed
    content = data[content_start : content_start + length]
    return tag, content, content_start + length

# --- LDAP Specific Protocol Handlers ---

def build_ldap_message(message_id: int, protocol_op: bytes) -> bytes:
    """Wrap a protocol operation in an LDAP Message Sequence."""
    msg_bytes = encode_integer(message_id) + protocol_op
    return encode_sequence(msg_bytes)

def build_bind_response(result_code: int, matched_dn: str, diagnostic_msg: str) -> bytes:
    """Construct an LDAP BindResponse (Tag 0x61)."""
    content = (
        encode_enumerated(result_code) +
        encode_octet_string(matched_dn.encode('utf-8')) +
        encode_octet_string(diagnostic_msg.encode('utf-8'))
    )
    return encode_sequence(content, tag=0x61)

def build_search_result_entry(dn: str, attributes: dict) -> bytes:
    """Construct an LDAP SearchResultEntry (Tag 0x64)."""
    # Attributes is a dict of name -> list of values
    attr_list_bytes = bytearray()
    for name, values in attributes.items():
        val_set = bytearray()
        for v in values:
            if isinstance(v, str):
                v = v.encode('utf-8')
            val_set += encode_octet_string(v)
            
        attr_entry = encode_octet_string(name.encode('utf-8')) + encode_sequence(bytes(val_set), tag=0x31) # SET OF
        attr_list_bytes += encode_sequence(attr_entry)
        
    content = (
        encode_octet_string(dn.encode('utf-8')) +
        encode_sequence(bytes(attr_list_bytes))
    )
    return encode_sequence(content, tag=0x64)

def build_search_result_done(result_code: int, matched_dn: str, diagnostic_msg: str) -> bytes:
    """Construct an LDAP SearchResultDone (Tag 0x65)."""
    content = (
        encode_enumerated(result_code) +
        encode_octet_string(matched_dn.encode('utf-8')) +
        encode_octet_string(diagnostic_msg.encode('utf-8'))
    )
    return encode_sequence(content, tag=0x65)

# --- Mock Data & Client Thread Handling ---

DEFAULT_USERS = {
    "cn=admin,dc=example,dc=org": {
        "password": "adminpassword",
        "attributes": {
            "objectClass": ["top", "person", "organizationalPerson", "inetOrgPerson"],
            "cn": ["admin"],
            "sn": ["Administrator"],
            "mail": ["admin@example.org"]
        }
    },
    "uid=jdoe,ou=users,dc=example,dc=org": {
        "password": "password123",
        "attributes": {
            "objectClass": ["top", "person", "organizationalPerson", "inetOrgPerson"],
            "uid": ["jdoe"],
            "cn": ["John Doe"],
            "sn": ["Doe"],
            "givenName": ["John"],
            "mail": ["jdoe@example.org"]
        }
    }
}

def handle_client(conn: socket.socket, addr: tuple, users_db: dict, colors: dict):
    """Handle LDAP connection dialog."""
    try:
        while True:
            # LDAP messages are usually small, but let's read iteratively
            data = conn.recv(65535)
            if not data:
                break
                
            offset = 0
            while offset < len(data):
                # Parse LDAP Message envelope (SEQUENCE)
                tag, content, next_offset = parse_ber_node(data, offset)
                if tag != 0x30 or content is None:
                    break
                    
                offset = next_offset
                
                # Parse Message ID (INTEGER)
                id_tag, id_content, msg_offset = parse_ber_node(content, 0)
                if id_tag != 0x02 or not id_content:
                    break
                    
                msg_id = int.from_bytes(id_content, byteorder='big')
                
                # Parse ProtocolOp
                op_tag, op_content, _ = parse_ber_node(content, msg_offset)
                
                # 1. BindRequest (0x60)
                if op_tag == 0x60:
                    # Parse version, name (DN), authentication
                    v_tag, v_content, bind_offset = parse_ber_node(op_content, 0)
                    dn_tag, dn_content, auth_offset = parse_ber_node(op_content, bind_offset)
                    
                    dn = dn_content.decode('utf-8') if dn_content else ""
                    
                    # Parse Auth (simple auth is tag 0x80)
                    auth_tag, auth_content, _ = parse_ber_node(op_content, auth_offset)
                    
                    password = ""
                    if auth_tag == 0x80:
                        password = auth_content.decode('utf-8') if auth_content else ""
                        
                    print(f"[{colors['yellow']}BIND{colors['reset']}] DN: {colors['bold']}{dn}{colors['reset']}, Password: {password}")
                    
                    # Authenticate
                    result_code = 0  # Success
                    diagnostic = "Success"
                    
                    if dn:
                        user = users_db.get(dn.lower().strip())
                        if not user or user["password"] != password:
                            result_code = 49  # invalidCredentials
                            diagnostic = "Invalid Credentials"
                            print(f"  {colors['red']}✗ Authentication failed.{colors['reset']}")
                        else:
                            print(f"  {colors['green']}✔ Authentication successful.{colors['reset']}")
                    else:
                        # Anonymous bind
                        print(f"  {colors['green']}✔ Anonymous bind successful.{colors['reset']}")
                        
                    response = build_ldap_message(
                        msg_id, 
                        build_bind_response(result_code, dn, diagnostic)
                    )
                    conn.sendall(response)
                    
                # 2. SearchRequest (0x63)
                elif op_tag == 0x63:
                    # Parse search parameters: baseObject, scope, deref, sizeLimit, timeLimit, typesOnly, filter
                    base_tag, base_content, search_offset = parse_ber_node(op_content, 0)
                    scope_tag, scope_content, search_offset = parse_ber_node(op_content, search_offset)
                    deref_tag, _ , search_offset = parse_ber_node(op_content, search_offset)
                    sizelimit_tag, _ , search_offset = parse_ber_node(op_content, search_offset)
                    timelimit_tag, _ , search_offset = parse_ber_node(op_content, search_offset)
                    typesonly_tag, _ , search_offset = parse_ber_node(op_content, search_offset)
                    
                    base_dn = base_content.decode('utf-8') if base_content else ""
                    print(f"[{colors['cyan']}SEARCH{colors['reset']}] Base DN: {colors['bold']}{base_dn}{colors['reset']}")
                    
                    # Return all users matching the base DN or all if empty
                    matches = 0
                    for dn, details in users_db.items():
                        # Simple substring match for base DN
                        if not base_dn or base_dn.lower().strip() in dn.lower():
                            result_entry = build_search_result_entry(dn, details["attributes"])
                            conn.sendall(build_ldap_message(msg_id, result_entry))
                            print(f"  {colors['green']}-> Sent entry:{colors['reset']} {dn}")
                            matches += 1
                            
                    # Done
                    done_op = build_search_result_done(0, "", f"Search completed. Found {matches} entry/entries.")
                    conn.sendall(build_ldap_message(msg_id, done_op))
                    print(f"  {colors['green']}✔ Search finished (sent {matches} results).{colors['reset']}")
                    
                # 3. UnbindRequest (0x62)
                elif op_tag == 0x62:
                    print(f"[{colors['yellow']}UNBIND{colors['reset']}] Client disconnected gracefully.")
                    break
                else:
                    # Unsupported protocol op
                    print(f"[{colors['red']}UNSUPPORTED{colors['reset']}] Op Tag: {hex(op_tag)}")
                    break
                    
    except Exception as e:
        print(f"Error handling client {addr}: {e}", file=sys.stderr)
    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser(
        description="Mock LDAP Directory Server - A lightweight pure-Python directory mock for authentication tests."
    )
    parser.add_argument("--listen-ip", default="127.0.0.1", help="IP address to listen on (default: 127.0.0.1)")
    parser.add_argument("--listen-port", type=int, default=1389, help="Port to listen on (default: 1389)")
    parser.add_argument("--users-file", help="Path to JSON file containing custom users DB")
    
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
    
    # Load users DB
    users_db = {}
    if args.users_file:
        try:
            with open(args.users_file, "r") as f:
                raw_db = json.load(f)
                # Lowercase keys for case-insensitive matching
                for dn, data in raw_db.items():
                    users_db[dn.lower().strip()] = data
            print(f"Loaded {len(users_db)} users from custom database file: {args.users_file}")
        except Exception as e:
            print(f"{colors['red']}[ERROR] Failed loading user file: {e}{colors['reset']}", file=sys.stderr)
            sys.exit(1)
    else:
        # Load defaults
        for dn, data in DEFAULT_USERS.items():
            users_db[dn.lower().strip()] = data
            
    # Start Socket Server
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    
    try:
        server.bind((args.listen_ip, args.listen_port))
        server.listen(50)
    except Exception as e:
        print(f"{colors['red']}[ERROR] Failed binding to {args.listen_ip}:{args.listen_port} - {e}{colors['reset']}", file=sys.stderr)
        sys.exit(1)
        
    print("=" * 65)
    print(f"{colors['bold']}{colors['green']}Mock LDAP Server Listening on:{colors['reset']} {args.listen_ip}:{args.listen_port}")
    print(f"Preconfigured Users:")
    for dn in users_db.keys():
        print(f"  - {dn}")
    print("=" * 65)
    print("Press Ctrl+C to stop the LDAP server.\n")
    
    try:
        while True:
            conn, addr = server.accept()
            print(f"[{colors['green']}+ {colors['reset']}] Client connected from {addr[0]}:{addr[1]}")
            t = threading.Thread(
                target=handle_client,
                args=(conn, addr, users_db, colors),
                daemon=True
            )
            t.start()
    except KeyboardInterrupt:
        print(f"\n{colors['yellow']}[*] Stopping LDAP Server...{colors['reset']}")
    finally:
        server.close()

if __name__ == '__main__':
    main()
