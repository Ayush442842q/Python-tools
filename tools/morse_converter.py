#!/usr/bin/env python3
"""
Morse Code Converter & Audio Player

Translates alphanumeric text into Morse code and decodes Morse code back to text.
Supports live terminal blinking and audio beep playback (using winsound on Windows).

Usage:
    python tools/morse_converter.py "Hello World" --play
    python tools/morse_converter.py ".... . .-.. .-.. ---" --decode
"""

import argparse
import os
import sys
import time

# ANSI Escape Sequences
CLR_CYAN = "\033[96m"
CLR_GREEN = "\033[92m"
CLR_YELLOW = "\033[93m"
CLR_RED = "\033[91m"
CLR_BOLD = "\033[1m"
CLR_RESET = "\033[0m"

# Morse Code Dictionary
MORSE_DICT = {
    'A': '.-',     'B': '-...',   'C': '-.-.',   'D': '-..',    'E': '.',
    'F': '..-.',   'G': '--.',    'H': '....',   'I': '..',     'J': '.---',
    'K': '-.-',    'L': '.-..',   'M': '--',     'N': '-.',     'O': '---',
    'P': '.--.',   'Q': '--.-',   'R': '.-.',    'S': '...',    'T': '-',
    'U': '..-',    'V': '...-',   'W': '.--',    'X': '-..-',   'Y': '-.--',
    'Z': '--..',
    '0': '-----',  '1': '.----',  '2': '..---',  '3': '...--',  '4': '....-',
    '5': '.....',  '6': '-....',  '7': '--...',  '8': '---..',  '9': '----.',
    '.': '.-.-.-', ',': '--..--', '?': '..--..', "'": '.----.', '!': '-.-.--',
    '/': '-..-.',  '(': '-.--.',  ')': '-.--.-', '&': '.-...',  ':': '---...',
    ';': '-.-.-.', '=': '-...-',  '+': '.-.-.',  '-': '-....-', '_': '..--.-',
    '"': '.-..-.', '$': '...-..-', '@': '.--.-.', ' ': '/'
}

REVERSE_MORSE_DICT = {v: k for k, v in MORSE_DICT.items()}

def encode_morse(text):
    """Converts plain text to Morse code."""
    text = text.upper()
    morse_list = []
    for char in text:
        if char in MORSE_DICT:
            morse_list.append(MORSE_DICT[char])
        else:
            # Skip unsupported characters
            pass
    return " ".join(morse_list)

def decode_morse(morse_code):
    """Converts Morse code back to plain text."""
    words = morse_code.strip().split(" / ")
    decoded_message = []
    
    for word in words:
        decoded_word = []
        chars = word.split(" ")
        for char in chars:
            if not char:
                continue
            if char in REVERSE_MORSE_DICT:
                decoded_word.append(REVERSE_MORSE_DICT[char])
            else:
                decoded_word.append("?")
        decoded_message.append("".join(decoded_word))
        
    return " ".join(decoded_message)

def play_morse(morse_code, wpm=15, frequency=750):
    """Plays the Morse code audio (using winsound on Windows) with visual highlight."""
    # Standard Morse Timing rules based on Paris WPM:
    # 1 WPM = 1.2 seconds (1200 ms) per unit
    dot_duration_sec = 1.2 / wpm
    dash_duration_sec = dot_duration_sec * 3
    symbol_gap_sec = dot_duration_sec
    letter_gap_sec = dot_duration_sec * 3
    word_gap_sec = dot_duration_sec * 7

    # Platform audio configuration
    can_beep = False
    if sys.platform == 'win32':
        try:
            import winsound
            can_beep = True
        except ImportError:
            pass

    if not can_beep:
        print(f"{CLR_YELLOW}Warning: Audio playback is only native on Windows (winsound). Running in Visual Playback mode.{CLR_RESET}\n")

    print(f"Playing Morse Code ({wpm} WPM, {frequency} Hz):")
    sys.stdout.write("Progress: ")
    sys.stdout.flush()

    words = morse_code.split(" / ")
    for word_idx, word in enumerate(words):
        chars = word.split(" ")
        for char_idx, char in enumerate(chars):
            # Print and highlight current symbol
            sys.stdout.write(f"{CLR_CYAN}{CLR_BOLD}{char}{CLR_RESET} ")
            sys.stdout.flush()

            for symbol in char:
                duration = dot_duration_sec if symbol == '.' else dash_duration_sec
                
                if can_beep:
                    winsound.Beep(frequency, int(duration * 1000))
                    time.sleep(symbol_gap_sec)
                else:
                    # Visual representation flash
                    sys.stdout.write("\a") # terminal bell fallback
                    sys.stdout.flush()
                    time.sleep(duration + symbol_gap_sec)
            
            # Gap between letters (minus the symbol gap already elapsed)
            time.sleep(letter_gap_sec - symbol_gap_sec)

        # Gap between words (minus the letter gap already elapsed)
        if word_idx < len(words) - 1:
            sys.stdout.write(f"{CLR_YELLOW}/ {CLR_RESET}")
            sys.stdout.flush()
            time.sleep(word_gap_sec - letter_gap_sec)

    print(f"\n\n{CLR_GREEN}{CLR_BOLD}Playback completed.{CLR_RESET}")

def main():
    if sys.platform == 'win32':
        os.system('')  # Enable ANSI color escape sequences on Windows

    parser = argparse.ArgumentParser(
        description="Morse Code Converter & Player - Encode, decode, and play Morse code"
    )
    parser.add_argument("input", nargs="?", help="Text to translate or play")
    parser.add_argument("-d", "--decode", action="store_true", help="Decode Morse code input into plain text")
    parser.add_argument("-p", "--play", action="store_true", help="Play the Morse code using system audio and visuals")
    parser.add_argument("-w", "--wpm", type=int, default=15, help="Speed of audio playback in Words Per Minute (default: 15)")
    parser.add_argument("-f", "--freq", type=int, default=750, help="Tone frequency in Hz (default: 750)")
    args = parser.parse_args()

    message = args.input
    if not message:
        # Check standard input redirection
        if not sys.stdin.isatty():
            message = sys.stdin.read().strip()
        else:
            parser.print_help()
            print(f"\n{CLR_RED}Error: Please provide a text input as an argument or via standard input.{CLR_RESET}")
            return 1

    print("=" * 60)
    print(f"{CLR_GREEN}{CLR_BOLD}MORSE CODE CONVERTER & PLAYER{CLR_RESET}")
    print("=" * 60)

    if args.decode:
        # User wants to decode Morse Code
        print(f"Input Morse Code: {CLR_YELLOW}{message}{CLR_RESET}")
        decoded = decode_morse(message)
        print(f"Decoded Message : {CLR_BOLD}{CLR_GREEN}{decoded}{CLR_RESET}")
        print("=" * 60)
    else:
        # User wants to encode Plain Text
        print(f"Input Plain Text: {CLR_YELLOW}{message}{CLR_RESET}")
        encoded = encode_morse(message)
        print(f"Encoded Morse   : {CLR_BOLD}{CLR_GREEN}{encoded}{CLR_RESET}")
        print("=" * 60)
        
        if args.play:
            print()
            play_morse(encoded, wpm=args.wpm, frequency=args.freq)
            print("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
