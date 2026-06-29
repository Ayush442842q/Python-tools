#!/usr/bin/env python3
"""
Terminal ASCII Clock, Stopwatch & Timer
An interactive terminal utility that renders a large digital clock, stopwatch,
or countdown timer using 5x5 ASCII block characters.
Supports keyboard controls (pause, lap, reset) and a visual/audio alarm.
"""

import argparse
import os
import sys
import time

# Attempt to import Windows-specific keyboard polling, otherwise define a dummy/Unix alternative
try:
    import msvcrt
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False
    import select

# 5x5 ASCII characters for digits 0-9, colon, period, and space
ASCII_DIGITS = {
    '0': [
        " ### ",
        "#   #",
        "#   #",
        "#   #",
        " ### "
    ],
    '1': [
        "  #  ",
        " ##  ",
        "  #  ",
        "  #  ",
        " ### "
    ],
    '2': [
        " ### ",
        "    #",
        " ### ",
        "#    ",
        " ### "
    ],
    '3': [
        " ### ",
        "    #",
        " ### ",
        "    #",
        " ### "
    ],
    '4': [
        " # # ",
        "#  # ",
        "#####",
        "   # ",
        "   # "
    ],
    '5': [
        "#####",
        "#    ",
        "#### ",
        "    #",
        "#### "
    ],
    '6': [
        " ### ",
        "#    ",
        "#### ",
        "#   #",
        " ### "
    ],
    '7': [
        "#####",
        "    #",
        "   # ",
        "  #  ",
        "  #  "
    ],
    '8': [
        " ### ",
        "#   #",
        " ### ",
        "#   #",
        " ### "
    ],
    '9': [
        " ### ",
        "#   #",
        " ####",
        "    #",
        " ### "
    ],
    ':': [
        "   ",
        " # ",
        "   ",
        " # ",
        "   "
    ],
    '.': [
        " ",
        " ",
        " ",
        " ",
        "#"
    ],
    ' ': [
        "     ",
        "     ",
        "     ",
        "     ",
        "     "
    ]
}

# ANSI colors
COLORS = {
    'red': '\033[91m',
    'green': '\033[92m',
    'yellow': '\033[93m',
    'blue': '\033[94m',
    'magenta': '\033[95m',
    'cyan': '\033[96m',
    'white': '\033[97m',
    'reset': '\033[0m',
    'bold': '\033[1m',
    'invert': '\033[7m'
}


def clear_screen():
    """Clears the terminal screen."""
    os.system('cls' if os.name == 'nt' else 'clear')


def get_ascii_string(s):
    """Converts a string of digits/symbols into a 5-line ASCII representation."""
    lines = ["", "", "", "", ""]
    for char in s:
        char_matrix = ASCII_DIGITS.get(char, ASCII_DIGITS[' '])
        for i in range(5):
            lines[i] += char_matrix[i] + "  "
    return "\n".join(lines)


def get_key_press():
    """Non-blocking keyboard input reader."""
    if HAS_MSVCRT:
        if msvcrt.kbhit():
            ch = msvcrt.getch()
            # Handle decode/special keys
            try:
                return ch.decode('utf-8').lower()
            except UnicodeDecodeError:
                return str(ch)
        return None
    else:
        # Unix/macOS select-based non-blocking read
        rlist, _, _ = select.select([sys.stdin], [], [], 0.0)
        if rlist:
            return sys.stdin.read(1).lower()
        return None


def format_duration(seconds):
    """Formats seconds into HH:MM:SS."""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def run_clock(color_name, use_12h):
    """Runs the live ASCII digital clock."""
    color = COLORS.get(color_name, COLORS['green'])
    print("Press Ctrl+C to exit the clock.")
    time.sleep(1)

    while True:
        try:
            now = time.localtime()
            if use_12h:
                hour = now.tm_hour % 12
                if hour == 0:
                    hour = 12
                suffix = " PM" if now.tm_hour >= 12 else " AM"
                time_str = f"{hour:02d}:{now.tm_min:02d}:{now.tm_sec:02d}"
            else:
                suffix = ""
                time_str = f"{now.tm_hour:02d}:{now.tm_min:02d}:{now.tm_sec:02d}"

            clear_screen()
            ascii_art = get_ascii_string(time_str)

            print(COLORS['bold'] + f"--- DIGITAL CLOCK ({'12h' if use_12h else '24h'}) ---" + COLORS['reset'])
            print(color + ascii_art + COLORS['reset'])
            if suffix:
                print(color + " " * 15 + suffix + COLORS['reset'])
            print(COLORS['bold'] + "\nPress Ctrl+C to stop." + COLORS['reset'])

            time.sleep(0.2)
        except KeyboardInterrupt:
            print("\nClock stopped.")
            break


def run_stopwatch(color_name):
    """Runs the interactive ASCII stopwatch with splits/laps."""
    color = COLORS.get(color_name, COLORS['cyan'])
    clear_screen()
    print("=" * 40)
    print("        ASCII STOPWATCH")
    print("=" * 40)
    print("Controls:")
    print("  [Space] - Pause / Resume")
    print("  [L]     - Record Lap / Split time")
    print("  [R]     - Reset stopwatch")
    print("  [Q]     - Quit stopwatch")
    print("\nPress any key to start...")
    
    if HAS_MSVCRT:
        msvcrt.getch()
    else:
        sys.stdin.read(1)

    start_time = time.time()
    elapsed_offset = 0.0
    running = True
    laps = []

    last_update = 0.0

    while True:
        current_time = time.time()
        
        # Read keyboard input
        key = get_key_press()
        if key == 'q':
            break
        elif key == ' ':
            if running:
                # Pause
                elapsed_offset += current_time - start_time
                running = False
            else:
                # Resume
                start_time = time.time()
                running = True
        elif key == 'r':
            start_time = time.time()
            elapsed_offset = 0.0
            laps = []
        elif key == 'l':
            # Record lap
            tot_elapsed = elapsed_offset + (current_time - start_time if running else 0)
            lap_num = len(laps) + 1
            laps.append((lap_num, tot_elapsed))

        # Throttle redraws to ~30 FPS
        if current_time - last_update > 0.03:
            last_update = current_time
            
            total_elapsed = elapsed_offset
            if running:
                total_elapsed += current_time - start_time

            # Format: MM:SS.d (tenths of second)
            minutes = int(total_elapsed // 60)
            seconds = int(total_elapsed % 60)
            tenths = int((total_elapsed * 10) % 10)
            time_str = f"{minutes:02d}:{seconds:02d}.{tenths}"

            clear_screen()
            ascii_art = get_ascii_string(time_str)

            print(COLORS['bold'] + "--- STOPWATCH ---" + COLORS['reset'])
            print(color + ascii_art + COLORS['reset'])
            
            # Status indicator
            status = "RUNNING" if running else "PAUSED"
            status_color = COLORS['green'] if running else COLORS['yellow']
            print(f"Status: {status_color}{status}{COLORS['reset']} | [Space] Pause/Resume | [L] Lap | [R] Reset | [Q] Quit\n")

            # Show laps (last 5)
            if laps:
                print("Laps:")
                for num, lap_time in laps[-5:]:
                    # Compute lap duration relative to previous lap
                    if num == 1:
                        lap_dur = lap_time
                    else:
                        lap_dur = lap_time - laps[num-2][1]
                    
                    lm = int(lap_dur // 60)
                    ls = int(lap_dur % 60)
                    lt = int((lap_dur * 10) % 10)
                    
                    tm = int(lap_time // 60)
                    ts = int(lap_time % 60)
                    tt = int((lap_time * 10) % 10)
                    
                    print(f"  Lap {num:02d}: +{lm:02d}:{ls:02d}.{lt}  (Total: {tm:02d}:{ts:02d}.{tt})")

        time.sleep(0.01)


def run_timer(duration_seconds, color_name):
    """Runs the ASCII countdown timer with a progress bar and alarm."""
    color = COLORS.get(color_name, COLORS['yellow'])
    start_time = time.time()
    target_time = start_time + duration_seconds
    total_duration = duration_seconds

    running = True
    elapsed_offset = 0.0

    while True:
        current_time = time.time()
        
        # Read keyboard input
        key = get_key_press()
        if key == 'q':
            break
        elif key == ' ':
            if running:
                # Pause
                elapsed_offset += current_time - start_time
                running = False
            else:
                # Resume
                start_time = time.time()
                running = True
        elif key == 'r':
            # Reset
            start_time = time.time()
            elapsed_offset = 0.0
            running = True

        remaining = total_duration - (elapsed_offset + (current_time - start_time if running else 0))

        if remaining <= 0:
            remaining = 0
            
        # Format time string
        rem_min = int(remaining // 60)
        rem_sec = int(remaining % 60)
        time_str = f"{rem_min:02d}:{rem_sec:02d}"

        clear_screen()
        ascii_art = get_ascii_string(time_str)

        print(COLORS['bold'] + "--- COUNTDOWN TIMER ---" + COLORS['reset'])
        print(color + ascii_art + COLORS['reset'])

        # Progress bar
        bar_width = 30
        pct = max(0.0, min(1.0, remaining / total_duration))
        filled = int(bar_width * pct)
        bar = "█" * filled + "-" * (bar_width - filled)
        print(f"Progress: [{bar}] {int(pct*100)}%")
        
        # Pause status
        status = "RUNNING" if running else "PAUSED"
        status_color = COLORS['green'] if running else COLORS['yellow']
        print(f"Status: {status_color}{status}{COLORS['reset']} | [Space] Pause/Resume | [R] Reset | [Q] Quit\n")

        if remaining <= 0:
            # Alarm mode: flash screen and beep
            for _ in range(5):
                clear_screen()
                print(COLORS['invert'] + COLORS['red'] + "\n" * 2 + " " * 10 + "TIME'S UP!" + "\n" * 2 + COLORS['reset'])
                # Terminal beep
                sys.stdout.write('\a')
                sys.stdout.flush()
                time.sleep(0.5)
                clear_screen()
                print("\n" * 2 + " " * 10 + "TIME'S UP!" + "\n" * 2)
                time.sleep(0.5)
            break

        time.sleep(0.1)


def parse_duration(s):
    """Parses a duration string like '5m', '90s', '1h' into total seconds."""
    s = s.strip().lower()
    if s.endswith('s'):
        return int(s[:-1])
    elif s.endswith('m'):
        return int(s[:-1]) * 60
    elif s.endswith('h'):
        return int(s[:-1]) * 3600
    else:
        # Default to seconds if just digits
        return int(s)


def main():
    parser = argparse.ArgumentParser(description="Terminal ASCII Digital Clock, Stopwatch & Countdown Timer")
    parser.add_argument("--mode", choices=["clock", "stopwatch", "timer"], default="clock",
                        help="Choose utility mode: clock, stopwatch, or timer")
    parser.add_argument("--color", choices=["red", "green", "yellow", "blue", "magenta", "cyan", "white"],
                        default="green", help="ANSI text color for the ASCII display")
    parser.add_argument("--12h", action="store_true", dest="use_12h", help="Use 12-hour format with AM/PM (Clock mode)")
    parser.add_argument("--time", type=str, default="5m",
                        help="Countdown duration for timer mode (e.g. 5m, 120s, 1h)")

    args = parser.parse_args()

    # Clear terminal before start
    clear_screen()

    if args.mode == "clock":
        run_clock(args.color, args.use_12h)
    elif args.mode == "stopwatch":
        run_stopwatch(args.color)
    elif args.mode == "timer":
        try:
            secs = parse_duration(args.time)
        except ValueError:
            print(f"Error: Invalid duration format '{args.time}'. Use e.g. 5m, 90s, 1h.")
            sys.exit(1)
        run_timer(secs, args.color)


if __name__ == "__main__":
    main()
