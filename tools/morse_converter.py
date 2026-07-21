#!/usr/bin/env python3
"""
Morse Code Converter - A utility to encode text to Morse code and decode Morse code back.
Includes Windows-native audio playback for Morse code signals.
"""

import argparse
import sys
import time

# Morse code dictionary
MORSE_CODE_DICT = {
    'A': '.-', 'B': '-...', 'C': '-.-.', 'D': '-..', 'E': '.', 'F': '..-.',
    'G': '--.', 'H': '....', 'I': '..', 'J': '.---', 'K': '-.-', 'L': '.-..',
    'M': '--', 'N': '-.', 'O': '---', 'P': '.--.', 'Q': '--.-', 'R': '.-.',
    'S': '...', 'T': '-', 'U': '..-', 'V': '...-', 'W': '.--', 'X': '-..-',
    'Y': '-.--', 'Z': '--..',
    '1': '.----', '2': '..---', '3': '...--', '4': '....-', '5': '.....',
    '6': '-....', '7': '--...', '8': '---..', '9': '----.', '0': '-----',
    ',': '--..--', '.': '.-.-.-', '?': '..--..', '/': '-..-.', '-': '-....-',
    '(': '-.--.', ')': '-.--.-', '&': '.-...', ':': '---...', ';': '-.-.-.',
    '=': '-...-', '+': '.-.-.', '_': '..--.-', '"': '.-..-.', '$': '...-..-',
    '@': '.--.-.', '!': '-.-.--'
}

# Reverse dictionary for decoding
REVERSE_DICT = {value: key for key, value in MORSE_CODE_DICT.items()}

def encode(text):
    """Encode normal text into Morse code."""
    encoded_words = []
    words = text.upper().split(' ')
    for word in words:
        encoded_chars = []
        for char in word:
            if char in MORSE_CODE_DICT:
                encoded_chars.append(MORSE_CODE_DICT[char])
            elif char != '':
                # Ignore characters not in dictionary
                pass
        encoded_words.append(' '.join(encoded_chars))
    return ' / '.join(encoded_words)

def decode(morse_code):
    """Decode Morse code back into plain text."""
    decoded_words = []
    # Morse code words are separated by '/' or ' / '
    words = [w.strip() for w in morse_code.split('/')]
    for word in words:
        decoded_chars = []
        chars = word.split(' ')
        for char in chars:
            if char in REVERSE_DICT:
                decoded_chars.append(REVERSE_DICT[char])
            elif char == '':
                pass
        decoded_words.append(''.join(decoded_chars))
    return ' '.join(decoded_words)

def play_audio(morse_code):
    """Play Morse code sounds using Windows winsound library."""
    try:
        import winsound
    except ImportError:
        print("Audio playback is only supported on Windows.", file=sys.stderr)
        return

    # Standard Morse code timing relative to dot duration
    dot_duration = 100  # milliseconds
    dash_duration = dot_duration * 3
    frequency = 800  # Hz

    print("Playing Morse audio...")
    for char in morse_code:
        if char == '.':
            winsound.Beep(frequency, dot_duration)
            time.sleep(dot_duration / 1000.0)
        elif char == '-':
            winsound.Beep(frequency, dash_duration)
            time.sleep(dot_duration / 1000.0)
        elif char == ' ':
            time.sleep((dot_duration * 2) / 1000.0)  # Total 3 dots space between chars
        elif char == '/':
            time.sleep((dot_duration * 6) / 1000.0)  # Total 7 dots space between words

def main():
    parser = argparse.ArgumentParser(
        description="Morse Code Converter - Encode and decode Morse code with audio feedback."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("-e", "--encode", help="Text to encode into Morse code")
    group.add_argument("-d", "--decode", help="Morse code to decode (separate characters by space, words by '/')")
    
    parser.add_argument("-p", "--play", action="store_true", help="Play the audio sound of the Morse code (Windows only)")
    parser.add_argument("-f", "--file", help="Input file to process instead of direct string")
    parser.add_argument("-o", "--output", help="Output file to write results to")

    args = parser.parse_args()

    content = ""
    is_encoding = True

    if args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            is_encoding = bool(args.encode)
        except Exception as e:
            print(f"Error reading file: {e}", file=sys.stderr)
            return 1
    else:
        if args.encode:
            content = args.encode
            is_encoding = True
        else:
            content = args.decode
            is_encoding = False

    if is_encoding:
        result = encode(content)
        print("Encoded Morse Code:")
        print(result)
        if args.play:
            play_audio(result)
    else:
        result = decode(content)
        print("Decoded Text:")
        print(result)
        if args.play:
            # Play the audio of the encoded version of the decoded text
            play_audio(encode(result))

    if args.output:
        try:
            with open(args.output, 'w', encoding='utf-8') as f:
                f.write(result + '\n')
            print(f"\n[+] Results saved to: {args.output}")
        except Exception as e:
            print(f"Error writing to output file: {e}", file=sys.stderr)
            return 1

    return 0

if __name__ == "__main__":
    sys.exit(main())
