#!/usr/bin/env python3
"""
TUI HTTP Client
An interactive, menu-driven terminal REST API client.
Allows developers to build, configure, and send HTTP requests (GET, POST, etc.)
interactively, inspect styled responses, view history, and save/load templates.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from typing import Dict, List, Any, Optional, Tuple

# ANSI Colors
COLOR_RESET = "\033[0m"
COLOR_BOLD = "\033[1m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_RED = "\033[91m"
COLOR_CYAN = "\033[96m"
COLOR_BLUE = "\033[94m"

def supports_color() -> bool:
    """Checks if the terminal supports color output."""
    platform_supports = sys.platform != "win32" or "ANSICON" in os.environ or "WT_SESSION" in os.environ
    is_a_tty = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()
    return platform_supports and is_a_tty

if not supports_color():
    COLOR_RESET = ""
    COLOR_BOLD = ""
    COLOR_GREEN = ""
    COLOR_YELLOW = ""
    COLOR_RED = ""
    COLOR_CYAN = ""
    COLOR_BLUE = ""

class TUIHTTPClient:
    def __init__(self):
        self.url: str = ""
        self.method: str = "GET"
        self.headers: Dict[str, str] = {
            "User-Agent": "TUI-HTTP-Client/1.0",
            "Accept": "*/*"
        }
        self.body: str = ""
        self.history: List[Dict[str, Any]] = []

    def clear_screen(self):
        os.system('cls' if os.name == 'nt' else 'clear')

    def display_status_bar(self):
        print(f"{COLOR_BOLD}{COLOR_BLUE}=" * 60)
        print(f"  TUI HTTP CLIENT - REST API Console")
        print(f"=" * 60 + COLOR_RESET)
        url_display = self.url if self.url else f"{COLOR_YELLOW}[Not Set]{COLOR_RESET}"
        print(f"  {COLOR_BOLD}Method:{COLOR_RESET} {COLOR_GREEN}{self.method}{COLOR_RESET}")
        print(f"  {COLOR_BOLD}URL:{COLOR_RESET}    {url_display}")
        print(f"  {COLOR_BOLD}Headers:{COLOR_RESET} {len(self.headers)} configured")
        body_status = f"{len(self.body)} bytes" if self.body else "empty"
        print(f"  {COLOR_BOLD}Body:{COLOR_RESET}    {body_status}")
        print(f"{COLOR_BOLD}{COLOR_BLUE}-" * 60 + COLOR_RESET)

    def select_method(self):
        print(f"\n{COLOR_BOLD}Select HTTP Method:{COLOR_RESET}")
        methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"]
        for idx, m in enumerate(methods, 1):
            print(f"  [{COLOR_GREEN}{idx}{COLOR_RESET}] {m}")
        try:
            choice = int(input("Choice (1-7): ").strip())
            if 1 <= choice <= len(methods):
                self.method = methods[choice - 1]
                # Default content-type helper
                if self.method in ["POST", "PUT", "PATCH"] and "Content-Type" not in self.headers:
                    self.headers["Content-Type"] = "application/json"
                print(f"Method set to {COLOR_GREEN}{self.method}{COLOR_RESET}")
            else:
                print(f"{COLOR_RED}Invalid choice.{COLOR_RESET}")
        except ValueError:
            print(f"{COLOR_RED}Please enter a number.{COLOR_RESET}")
        time.sleep(1)

    def set_url(self):
        url_input = input(f"\nEnter Request URL (current: {self.url}): ").strip()
        if url_input:
            if not url_input.startswith(("http://", "https://")):
                url_input = "http://" + url_input
            self.url = url_input
            print(f"{COLOR_GREEN}URL updated successfully!{COLOR_RESET}")
        else:
            print("URL unchanged.")
        time.sleep(1)

    def configure_headers(self):
        while True:
            self.clear_screen()
            print(f"{COLOR_BOLD}{COLOR_CYAN}=== Request Headers ==={COLOR_RESET}")
            for key, val in self.headers.items():
                print(f"  {COLOR_GREEN}{key}{COLOR_RESET}: {val}")
            print(f"\nOptions:")
            print(f"  [{COLOR_GREEN}1{COLOR_RESET}] Add/Update Header")
            print(f"  [{COLOR_GREEN}2{COLOR_RESET}] Delete Header")
            print(f"  [{COLOR_GREEN}3{COLOR_RESET}] Clear All Custom Headers")
            print(f"  [{COLOR_GREEN}4{COLOR_RESET}] Back to Main Menu")
            
            choice = input("Select option (1-4): ").strip()
            if choice == "1":
                key = input("Enter Header Name: ").strip()
                val = input("Enter Header Value: ").strip()
                if key and val:
                    self.headers[key] = val
            elif choice == "2":
                key = input("Enter Header Name to delete: ").strip()
                if key in self.headers:
                    del self.headers[key]
                    print(f"Header '{key}' deleted.")
                else:
                    print(f"{COLOR_RED}Header not found.{COLOR_RESET}")
                time.sleep(1)
            elif choice == "3":
                self.headers = {"User-Agent": "TUI-HTTP-Client/1.0", "Accept": "*/*"}
                print("Headers reset to defaults.")
                time.sleep(1)
            elif choice == "4":
                break

    def edit_body(self):
        print(f"\nCurrent Body size: {len(self.body)} characters.")
        print("Enter/Paste your request body (leave blank to clear, double Enter to finish):")
        lines = []
        while True:
            try:
                line = input()
                if line == "" and (not lines or lines[-1] == ""):
                    break
                lines.append(line)
            except KeyboardInterrupt:
                break
        
        # Merge lines, trimming the trailing empty line representing double Enter
        if lines and lines[-1] == "":
            lines.pop()
        
        raw_body = "\n".join(lines).strip()
        self.body = raw_body
        
        # Ask to prettify if it looks like JSON
        if self.body.startswith("{") or self.body.startswith("["):
            try:
                parsed = json.loads(self.body)
                self.body = json.dumps(parsed, indent=2)
                print(f"{COLOR_GREEN}Body detected as valid JSON and formatted.{COLOR_RESET}")
            except json.JSONDecodeError:
                pass
                
        print(f"Body updated. Total size: {len(self.body)} bytes.")
        time.sleep(1)

    def send_request(self):
        if not self.url:
            print(f"{COLOR_RED}Error: URL is not set. Cannot send request.{COLOR_RESET}")
            time.sleep(1.5)
            return

        print(f"\n{COLOR_YELLOW}Sending {self.method} request to {self.url}...{COLOR_RESET}")
        
        data_bytes = None
        if self.method in ["POST", "PUT", "PATCH", "DELETE"] and self.body:
            data_bytes = self.body.encode('utf-8')
            
        req = urllib.request.Request(
            url=self.url,
            data=data_bytes,
            headers=self.headers,
            method=self.method
        )
        
        start_time = time.perf_counter()
        
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                status_code = response.status
                status_msg = response.msg
                resp_headers = response.getheaders()
                resp_body_bytes = response.read()
        except urllib.error.HTTPError as e:
            status_code = e.code
            status_msg = e.reason
            resp_headers = e.headers.items()
            resp_body_bytes = e.read()
        except Exception as e:
            print(f"{COLOR_RED}Connection error: {e}{COLOR_RESET}")
            input("\nPress Enter to continue...")
            return
            
        duration = time.perf_counter() - start_time
        
        # Save to history
        self.history.append({
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "method": self.method,
            "url": self.url,
            "status_code": status_code,
            "duration": duration
        })
        
        self.clear_screen()
        print(f"{COLOR_BOLD}{COLOR_CYAN}=== Response Statistics ==={COLOR_RESET}")
        status_color = COLOR_GREEN if status_code < 300 else (COLOR_YELLOW if status_code < 400 else COLOR_RED)
        print(f"  {COLOR_BOLD}Status:{COLOR_RESET} {status_color}{status_code} {status_msg}{COLOR_RESET}")
        print(f"  {COLOR_BOLD}Latency:{COLOR_RESET} {duration:.3f}s")
        print(f"  {COLOR_BOLD}Response Size:{COLOR_RESET} {len(resp_body_bytes)} bytes")
        
        print(f"\n{COLOR_BOLD}{COLOR_CYAN}=== Response Headers ==={COLOR_RESET}")
        for k, v in resp_headers:
            print(f"  {COLOR_GREEN}{k}{COLOR_RESET}: {v}")
            
        print(f"\n{COLOR_BOLD}{COLOR_CYAN}=== Response Body ==={COLOR_RESET}")
        try:
            decoded_body = resp_body_bytes.decode('utf-8')
            # Try parsing as JSON
            try:
                parsed_json = json.loads(decoded_body)
                print(COLOR_GREEN + json.dumps(parsed_json, indent=2) + COLOR_RESET)
            except json.JSONDecodeError:
                # Text output
                if len(decoded_body) > 2000:
                    print(decoded_body[:2000] + f"\n... [Body truncated from {len(decoded_body)} bytes] ...")
                else:
                    print(decoded_body)
        except UnicodeDecodeError:
            print(f"{COLOR_YELLOW}[Binary Content / Decouple Failed]{COLOR_RESET}")
            
        input(f"\n{COLOR_BOLD}Press Enter to return to main menu...{COLOR_RESET}")

    def view_history(self):
        self.clear_screen()
        print(f"{COLOR_BOLD}{COLOR_CYAN}=== Request History ==={COLOR_RESET}")
        if not self.history:
            print("  No requests sent in this session.")
        else:
            for idx, h in enumerate(reversed(self.history), 1):
                status_color = COLOR_GREEN if h["status_code"] < 300 else (COLOR_YELLOW if h["status_code"] < 400 else COLOR_RED)
                print(f"  [{idx}] {h['timestamp']} - {COLOR_BOLD}{h['method']}{COLOR_RESET} {h['url']}")
                print(f"      Response: {status_color}{h['status_code']}{COLOR_RESET} | Duration: {h['duration']:.3f}s")
                print("-" * 50)
                
        input("\nPress Enter to return to main menu...")

    def save_template(self):
        filepath = input("\nEnter path/filename to save template (e.g. tools/req.json): ").strip()
        if not filepath:
            return
        try:
            template = {
                "url": self.url,
                "method": self.method,
                "headers": self.headers,
                "body": self.body
            }
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(template, f, indent=4)
            print(f"{COLOR_GREEN}Template saved successfully to {filepath}{COLOR_RESET}")
        except Exception as e:
            print(f"{COLOR_RED}Error saving template: {e}{COLOR_RESET}")
        time.sleep(1.5)

    def load_template(self):
        filepath = input("\nEnter template filename to load: ").strip()
        if not filepath or not os.path.exists(filepath):
            print(f"{COLOR_RED}File does not exist.{COLOR_RESET}")
            time.sleep(1)
            return
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                template = json.load(f)
            self.url = template.get("url", "")
            self.method = template.get("method", "GET")
            self.headers = template.get("headers", {})
            self.body = template.get("body", "")
            print(f"{COLOR_GREEN}Template loaded successfully!{COLOR_RESET}")
        except Exception as e:
            print(f"{COLOR_RED}Error loading template: {e}{COLOR_RESET}")
        time.sleep(1.5)

    def start(self):
        while True:
            self.clear_screen()
            self.display_status_bar()
            print("  1. Set URL")
            print("  2. Select Method")
            print("  3. Configure Headers")
            print("  4. Edit Body")
            print("  5. Send Request")
            print("  6. View History")
            print("  7. Save Template")
            print("  8. Load Template")
            print("  9. Exit")
            print(f"{COLOR_BOLD}{COLOR_BLUE}-" * 60 + COLOR_RESET)
            
            choice = input("Enter choice (1-9): ").strip()
            if choice == "1":
                self.set_url()
            elif choice == "2":
                self.select_method()
            elif choice == "3":
                self.configure_headers()
            elif choice == "4":
                self.edit_body()
            elif choice == "5":
                self.send_request()
            elif choice == "6":
                self.view_history()
            elif choice == "7":
                self.save_template()
            elif choice == "8":
                self.load_template()
            elif choice == "9":
                print(f"\n{COLOR_GREEN}Thank you for using TUI HTTP Client!{COLOR_RESET}\n")
                break
            else:
                print(f"{COLOR_RED}Invalid option. Enter 1 to 9.{COLOR_RESET}")
                time.sleep(1)

def main():
    client = TUIHTTPClient()
    try:
        client.start()
    except KeyboardInterrupt:
        print(f"\n\n{COLOR_RED}Exiting TUI HTTP Client...{COLOR_RESET}\n")

if __name__ == "__main__":
    main()
