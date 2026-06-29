#!/usr/bin/env python3
"""
Terminal Keyboard Tester
An interactive, cross-platform terminal-based keyboard input analyzer.
Captures keypresses, hex scan codes, and ANSI escape sequences in real-time.
"""

import os
import sys

# Configure stdout encoding to UTF-8 to prevent character encoding issues
if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# Platform detection
IS_WINDOWS = sys.platform == "win32"

if IS_WINDOWS:
    import msvcrt
else:
    import termios
    import tty
    import select


def get_key_windows():
    """Reads keyboard input on Windows using msvcrt."""
    # Wait for keypress
    ch = msvcrt.getch()
    # Check for special prefix bytes (0x00 or 0xE0) indicating a function/arrow key
    if ch in (b'\x00', b'\xe0'):
        ch2 = msvcrt.getch()
        return ch + ch2
    return ch


class RawTerminalUnix:
    """Context manager to safely put Unix terminal into raw mode and restore it."""
    def __init__(self):
        self.fd = sys.stdin.fileno()
        self.old_settings = None

    def __enter__(self):
        try:
            self.old_settings = termios.tcgetattr(self.fd)
            tty.setraw(self.fd)
        except Exception as e:
            sys.stderr.write(f"Error setting raw mode: {e}\n")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.old_settings is not None:
            termios.tcsetattr(self.fd, termios.TCSADRAIN, self.old_settings)


def get_key_unix():
    """Reads keyboard input on Unix using select and non-blocking read."""
    # Read first char (blocking)
    first_char = sys.stdin.read(1)
    if not first_char:
        return b''

    # Convert to bytes
    res = first_char.encode('utf-8', errors='surrogateescape')

    # If it's escape character, try to read the rest of the sequence (non-blocking)
    if first_char == '\x1b':
        # Wait a very short time to see if more characters follow
        r, _, _ = select.select([sys.stdin], [], [], 0.05)
        if r:
            # Read whatever else is available in stdin buffer up to 15 chars
            extra = ""
            # Set stdin to non-blocking temporarily or just read
            # Since raw mode is set, read will be immediate if select says it's ready
            try:
                # We read characters one by one until select says no more data is ready
                while True:
                    r_next, _, _ = select.select([sys.stdin], [], [], 0.01)
                    if r_next:
                        extra += sys.stdin.read(1)
                    else:
                        break
            except Exception:
                pass
            res += extra.encode('utf-8', errors='surrogateescape')
    return res


# Common key definitions mapping for friendly display
KEY_MAP = {
    # Common Windows scan codes (bytes)
    b'\xe0H': "Arrow Up",
    b'\xe0P': "Arrow Down",
    b'\xe0K': "Arrow Left",
    b'\xe0M': "Arrow Right",
    b'\xe0S': "Delete",
    b'\xe0R': "Insert",
    b'\xe0G': "Home",
    b'\xe0O': "End",
    b'\xe0I': "Page Up",
    b'\xe0Q': "Page Down",
    b'\x00;': "F1",
    b'\x00<': "F2",
    b'\x00=': "F3",
    b'\x00>': "F4",
    b'\x00?': "F5",
    b'\x00@': "F6",
    b'\x00A': "F7",
    b'\x00B': "F8",
    b'\x00C': "F9",
    b'\x00D': "F10",
    b'\xe0\x85': "F11",
    b'\xe0\x86': "F12",
    b'\r': "Enter",
    b'\n': "Line Feed",
    b'\t': "Tab",
    b'\x1b': "Escape",
    b'\x08': "Backspace",
    b' ': "Space",

    # Common Unix escape sequences (bytes)
    b'\x1b[A': "Arrow Up",
    b'\x1b[B': "Arrow Down",
    b'\x1b[D': "Arrow Left",
    b'\x1b[C': "Arrow Right",
    b'\x1b[3~': "Delete",
    b'\x1b[2~': "Insert",
    b'\x1b[H': "Home",
    b'\x1b[F': "End",
    b'\x1bOH': "Home (Alternative)",
    b'\x1bOF': "End (Alternative)",
    b'\x1b[5~': "Page Up",
    b'\x1b[6~': "Page Down",
    b'\x1bOP': "F1",
    b'\x1bOQ': "F2",
    b'\x1bOR': "F3",
    b'\x1bOS': "F4",
    b'\x1b[15~': "F5",
    b'\x1b[17~': "F6",
    b'\x1b[18~': "F7",
    b'\x1b[19~': "F8",
    b'\x1b[20~': "F9",
    b'\x1b[21~': "F10",
    b'\x1b[23~': "F11",
    b'\x1b[24~': "F12",
    b'\x7f': "Backspace",
}


def describe_key(key_bytes):
    """Returns a friendly description of key_bytes."""
    if not key_bytes:
        return "None"

    # Check mapping
    if key_bytes in KEY_MAP:
        return KEY_MAP[key_bytes]

    # Check for Control characters (Ctrl + A to Ctrl + Z are 1 to 26)
    if len(key_bytes) == 1:
        val = key_bytes[0]
        if 1 <= val <= 26:
            # Exclude Enter/Tab/Backspace which are mapped above
            if val not in (9, 10, 13):
                return f"Ctrl + {chr(val + 64)}"
        if 32 <= val <= 126:
            return chr(val)
        # Printable unicode checks for single byte
        try:
            char = key_bytes.decode('utf-8')
            if char.isprintable():
                return char
        except UnicodeDecodeError:
            pass
        return f"Control Char ({val})"

    # Multi-byte UTF-8 character
    try:
        char = key_bytes.decode('utf-8')
        if char.isprintable():
            return char
    except UnicodeDecodeError:
        pass

    return "Unknown Key Sequence"


def main():
    print("======================================================================")
    print("                 Terminal Keyboard Event Tester                      ")
    print("======================================================================")
    print("Press keys/combinations to analyze their raw codes and ANSI sequences.")
    print("Press 'q' or Ctrl+C to exit.")
    print("----------------------------------------------------------------------")
    print(f"{'Key Name / Char':<25} | {'Hex Sequence':<20} | {'Raw Representation'}")
    print("-" * 70)

    try:
        if IS_WINDOWS:
            # Windows console loop
            while True:
                key = get_key_windows()
                if not key:
                    continue
                
                # Check for exit (q or Ctrl+C which is b'\x03')
                if key == b'q':
                    print(f"{'q (Exit command)':<25} | {key.hex():<20} | {repr(key)}")
                    break
                elif key == b'\x03':
                    print(f"{'Ctrl+C (Exit command)':<25} | {key.hex():<20} | {repr(key)}")
                    break

                desc = describe_key(key)
                hex_str = " ".join(f"{b:02X}" for b in key)
                print(f"{desc:<25} | {hex_str:<20} | {repr(key)}")
        else:
            # Unix console loop
            with RawTerminalUnix():
                while True:
                    key = get_key_unix()
                    if not key:
                        continue

                    # Check for exit (q or Ctrl+C which is b'\x03')
                    if key == b'q':
                        # Can't easily print in raw mode nicely without carriage returns
                        sys.stdout.write(f"\rq (Exit command)           | {key.hex():<20} | {repr(key)}\r\n")
                        break
                    elif key == b'\x03':
                        sys.stdout.write(f"\rCtrl+C (Exit command)      | {key.hex():<20} | {repr(key)}\r\n")
                        break

                    desc = describe_key(key)
                    hex_str = " ".join(f"{b:02X}" for b in key)
                    sys.stdout.write(f"\r{desc:<25} | {hex_str:<20} | {repr(key)}\r\n")

    except KeyboardInterrupt:
        print("\nExiting due to KeyboardInterrupt.")
    except Exception as e:
        print(f"\nAn error occurred: {e}")
    finally:
        print("\nKeyboard Tester finished.")


if __name__ == "__main__":
    main()
