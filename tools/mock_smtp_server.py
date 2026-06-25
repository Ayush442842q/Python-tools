#!/usr/bin/env python3
"""
Mock SMTP Server - A lightweight local SMTP server for developer testing.
Listens for incoming SMTP connections, prints emails to stdout, and saves them as .eml files.
"""

import os
import sys
import socket
import threading
import datetime
import email
from email.policy import default
import argparse

def get_color(color_name):
    """Return ANSI escape code for terminal color if supported."""
    colors = {
        'red': '\033[91m',
        'green': '\033[92m',
        'yellow': '\033[93m',
        'blue': '\033[94m',
        'cyan': '\033[96m',
        'magenta': '\033[95m',
        'bold': '\033[1m',
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

class SMTPClientHandler(threading.Thread):
    def __init__(self, conn, addr, output_dir, verbose=False):
        super().__init__()
        self.conn = conn
        self.addr = addr
        self.output_dir = output_dir
        self.verbose = verbose
        self.daemon = True

    def run(self):
        c_red = get_color('red')
        c_green = get_color('green')
        c_yellow = get_color('yellow')
        c_blue = get_color('blue')
        c_cyan = get_color('cyan')
        c_magenta = get_color('magenta')
        c_bold = get_color('bold')
        c_reset = get_color('reset')

        if self.verbose:
            print(f"{c_blue}[+] Connection accepted from {self.addr[0]}:{self.addr[1]}{c_reset}")

        try:
            self.conn.sendall(b"220 localhost Mock SMTP Server Ready\r\n")
            
            mail_from = ""
            rcpt_to = []
            data_mode = False
            raw_data = bytearray()
            auth_in_progress = False

            while True:
                data = self.conn.recv(4096)
                if not data:
                    break

                if data_mode:
                    raw_data.extend(data)
                    # Check if email input is completed with <CRLF>.<CRLF>
                    if b"\r\n.\r\n" in raw_data or raw_data.endswith(b"\n.\r\n") or raw_data.endswith(b"\n.\n"):
                        # Extract exact data and end data mode
                        end_seqs = [b"\r\n.\r\n", b"\n.\r\n", b"\n.\n"]
                        msg_bytes = raw_data
                        for seq in end_seqs:
                            idx = raw_data.rfind(seq)
                            if idx != -1:
                                msg_bytes = raw_data[:idx]
                                break

                        self.process_email(bytes(msg_bytes), mail_from, rcpt_to)
                        self.conn.sendall(b"250 2.0.0 OK Message accepted for delivery\r\n")
                        
                        # Reset session variables
                        raw_data = bytearray()
                        mail_from = ""
                        rcpt_to = []
                        data_mode = False
                    continue

                # Normal command mode
                command_line = data.decode('utf-8', errors='ignore').strip()
                if not command_line:
                    continue

                if self.verbose:
                    print(f" -> {command_line}")

                upper_cmd = command_line.upper()

                # Handle multi-line AUTH or input state
                if auth_in_progress:
                    # Mock successful authentication for whatever credentials sent
                    self.conn.sendall(b"235 2.7.0 Authentication successful\r\n")
                    auth_in_progress = False
                    continue

                if upper_cmd.startswith("HELO") or upper_cmd.startswith("EHLO"):
                    self.conn.sendall(b"250-localhost Hello\r\n250-AUTH LOGIN PLAIN\r\n250-SIZE 35840000\r\n250 HELP\r\n")
                elif upper_cmd.startswith("MAIL FROM:"):
                    mail_from = command_line[10:].strip('<> ')
                    self.conn.sendall(b"250 2.1.0 Sender OK\r\n")
                elif upper_cmd.startswith("RCPT TO:"):
                    recipient = command_line[8:].strip('<> ')
                    rcpt_to.append(recipient)
                    self.conn.sendall(b"250 2.1.5 Recipient OK\r\n")
                elif upper_cmd.startswith("DATA"):
                    data_mode = True
                    raw_data = bytearray()
                    self.conn.sendall(b"354 Start mail input; end with <CRLF>.<CRLF>\r\n")
                elif upper_cmd.startswith("QUIT"):
                    self.conn.sendall(b"221 2.0.0 localhost closing connection\r\n")
                    break
                elif upper_cmd.startswith("RSET"):
                    mail_from = ""
                    rcpt_to = []
                    data_mode = False
                    raw_data = bytearray()
                    self.conn.sendall(b"250 2.0.0 OK Reset State\r\n")
                elif upper_cmd.startswith("NOOP"):
                    self.conn.sendall(b"250 2.0.0 OK\r\n")
                elif upper_cmd.startswith("AUTH "):
                    # Command has arguments
                    if "PLAIN" in upper_cmd or "LOGIN" in upper_cmd:
                        parts = command_line.split()
                        if len(parts) > 2:
                            # Direct inline credentials
                            self.conn.sendall(b"235 2.7.0 Authentication successful\r\n")
                        else:
                            self.conn.sendall(b"334 VXNlcm5hbWU6\r\n") # base64 Username:
                            auth_in_progress = True
                    else:
                        self.conn.sendall(b"504 Unrecognized authentication type\r\n")
                else:
                    self.conn.sendall(b"500 5.5.1 Command unrecognized\r\n")

        except Exception as e:
            if self.verbose:
                print(f"{c_red}[!] Exception handling SMTP client {self.addr[0]}:{self.addr[1]}: {str(e)}{c_reset}")
        finally:
            self.conn.close()
            if self.verbose:
                print(f"{c_blue}[-] Connection closed from {self.addr[0]}:{self.addr[1]}{c_reset}")

    def process_email(self, msg_bytes, mail_from, rcpt_to):
        c_green = get_color('green')
        c_yellow = get_color('yellow')
        c_blue = get_color('blue')
        c_cyan = get_color('cyan')
        c_magenta = get_color('magenta')
        c_bold = get_color('bold')
        c_reset = get_color('reset')

        timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S-%f")
        
        # Save EML file
        filename = f"email_{timestamp}.eml"
        filepath = os.path.join(self.output_dir, filename)
        try:
            with open(filepath, 'wb') as f:
                f.write(msg_bytes)
        except Exception as e:
            print(f"Error saving email to file: {e}")

        # Parse message structure
        msg = email.message_from_bytes(msg_bytes, policy=default)

        # Retrieve headers
        subject = msg.get('Subject', '(No Subject)')
        sender = msg.get('From', mail_from or '(Unknown)')
        recipients = msg.get('To', ", ".join(rcpt_to) or '(Unknown)')
        date_hdr = msg.get('Date', '(No Date Header)')

        # Find body and attachments
        body_text = ""
        body_html = ""
        attachments = []

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get_content_disposition())

                if "attachment" in content_disposition:
                    attachments.append(part.get_filename() or "(Unnamed Attachment)")
                elif content_type == "text/plain" and not body_text:
                    try:
                        body_text = part.get_content()
                    except Exception:
                        body_text = part.get_payload(decode=True).decode('utf-8', errors='ignore')
                elif content_type == "text/html" and not body_html:
                    try:
                        body_html = part.get_content()
                    except Exception:
                        body_html = part.get_payload(decode=True).decode('utf-8', errors='ignore')
        else:
            content_type = msg.get_content_type()
            if content_type == "text/html":
                body_html = msg.get_content()
            else:
                body_text = msg.get_content()

        # Display email notification in terminal
        print("\n" + "=" * 65)
        print(f"{c_bold}{c_green}✉ RECEIVED EMAIL - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{c_reset}")
        print(f"{c_bold}Saved To:   {c_reset}{filepath}")
        print(f"{c_bold}Subject:    {c_reset}{c_cyan}{subject}{c_reset}")
        print(f"{c_bold}From:       {c_reset}{sender}")
        print(f"{c_bold}To:         {c_reset}{recipients}")
        print(f"{c_bold}Date Header:{c_reset} {date_hdr}")
        
        if attachments:
            print(f"{c_bold}Attachments:{c_reset} {c_magenta}{', '.join(attachments)}{c_reset}")
        
        print("-" * 65)
        if body_text:
            print(f"{c_bold}Plain Text Body:{c_reset}")
            print(body_text.strip())
        elif body_html:
            print(f"{c_bold}HTML Body (Source Snippet):{c_reset}")
            print(body_html.strip()[:400] + ("\n... [HTML text truncated]" if len(body_html) > 400 else ""))
        else:
            print(f"{c_yellow}(Empty Body){c_reset}")
        print("=" * 65 + "\n")

def start_smtp_server(host, port, output_dir, verbose=False):
    c_bold = get_color('bold')
    c_reset = get_color('reset')
    c_green = get_color('green')
    c_red = get_color('red')

    # Ensure output directory exists
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # Allow port reuse
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_socket.bind((host, port))
        server_socket.listen(5)
        print(f"{c_bold}{c_green}Mock SMTP Server running on {host}:{port}{c_reset}")
        print(f"Emails will be saved to: {os.path.abspath(output_dir)}")
        print("Press Ctrl+C to terminate the server.\n")
    except Exception as e:
        print(f"{c_red}Failed to bind to {host}:{port}: {str(e)}{c_reset}")
        sys.exit(1)

    try:
        while True:
            conn, addr = server_socket.accept()
            handler = SMTPClientHandler(conn, addr, output_dir, verbose)
            handler.start()
    except KeyboardInterrupt:
        print(f"\nShutting down Mock SMTP Server.")
    finally:
        server_socket.close()

def main():
    parser = argparse.ArgumentParser(description="Mock SMTP Server - Runs a local SMTP server for developer testing and captures mails.")
    parser.add_argument("-b", "--bind", default="127.0.0.1", help="Host address to bind SMTP server (default: 127.0.0.1)")
    parser.add_argument("-p", "--port", type=int, default=1025, help="Port to listen for SMTP mail (default: 1025)")
    parser.add_argument("-o", "--output-dir", default="./mock_emails", help="Directory where captured emails will be saved as .eml (default: ./mock_emails)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print debug/protocol output for incoming connections")

    args = parser.parse_args()

    start_smtp_server(args.bind, args.port, args.output_dir, args.verbose)

if __name__ == "__main__":
    main()
