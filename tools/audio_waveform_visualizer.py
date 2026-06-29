#!/usr/bin/env python3
"""
audio_waveform_visualizer.py - WAV Audio Waveform Visualizer

Natively reads WAV audio files using standard libraries and generates a
symmetrical Unicode waveform in the terminal, as well as a beautiful
vector SVG waveform with custom gradient themes.

Requirements:
    - Python 3.6+ (No external dependencies)
    - Input file must be a standard PCM WAV format (.wav)
"""

import os
import sys
import wave
import struct
import argparse

# ANSI color escape sequences
COLOR_CYAN = "\033[96m"
COLOR_MAGENTA = "\033[95m"
COLOR_RESET = "\033[0m"

# Unicode blocks for vertical bar building
BLOCKS = [" ", " ", "▂", "▃", "▄", "▅", "▆", "▇", "█"]

SVG_THEMES = {
    "fire": ("#f59e0b", "#ef4444"),  # Yellow to Red
    "ocean": ("#06b6d4", "#3b82f6"), # Cyan to Blue
    "neon": ("#10b981", "#8b5cf6"),  # Green to Purple
    "sunset": ("#ec4899", "#f43f5e") # Pink to Rose
}

def read_wav_samples(wav_path):
    """
    Reads PCM WAV file and returns normalized floating-point samples (-1.0 to 1.0)
    along with audio metadata.
    """
    try:
        with wave.open(wav_path, 'rb') as w:
            num_channels = w.getnchannels()
            sample_width = w.getsampwidth()
            frame_rate = w.getframerate()
            num_frames = w.getnframes()
            
            raw_data = w.readframes(num_frames)
    except wave.Error as e:
        print(f"Error: Invalid or unsupported WAV format: {e}", file=sys.stderr)
        sys.exit(1)
    except FileNotFoundError:
        print(f"Error: File '{wav_path}' not found.", file=sys.stderr)
        sys.exit(1)

    # Determine unpack format based on sample width (bytes per sample)
    # 8-bit: unsigned char (B)
    # 16-bit: signed short (h)
    # 32-bit: signed int (i)
    if sample_width == 1:
        fmt = f"{num_frames * num_channels}B"
        normalize_factor = 128.0
        unsigned = True
    elif sample_width == 2:
        fmt = f"<{num_frames * num_channels}h"
        normalize_factor = 32768.0
        unsigned = False
    elif sample_width == 4:
        fmt = f"<{num_frames * num_channels}i"
        normalize_factor = 2147483648.0
        unsigned = False
    else:
        print(f"Error: Unsupported sample width ({sample_width} bytes). Only 8, 16, or 32-bit PCM supported.", file=sys.stderr)
        sys.exit(1)

    try:
        raw_samples = struct.unpack(fmt, raw_data)
    except struct.error:
        print("Error: Audio data size does not match header declaration.", file=sys.stderr)
        sys.exit(1)

    # Normalize samples to [-1.0, 1.0] and average channels to mono
    normalized = []
    
    for i in range(0, len(raw_samples), num_channels):
        channel_sum = 0
        for ch in range(num_channels):
            val = raw_samples[i + ch]
            if unsigned:
                val -= 128
            channel_sum += val / normalize_factor
        normalized.append(channel_sum / num_channels)

    return normalized, {
        "channels": num_channels,
        "sample_width": sample_width,
        "sample_rate": frame_rate,
        "duration": num_frames / frame_rate
    }

def get_peaks(samples, num_bins):
    """Reduces samples list to a fixed number of bins, taking the peak absolute value in each bin."""
    bin_size = max(1, len(samples) // num_bins)
    peaks = []
    
    for i in range(num_bins):
        start = i * bin_size
        end = min(len(samples), start + bin_size)
        if start >= len(samples):
            peaks.append(0.0)
            continue
        chunk = samples[start:end]
        peak = max(abs(s) for s in chunk) if chunk else 0.0
        peaks.append(peak)
        
    return peaks

def render_terminal_waveform(peaks, height=15):
    """Renders a symmetrical waveform in the terminal using Unicode blocks."""
    # Symmetrical waveform grid: top half, center, bottom half
    grid = []
    for _ in range(height):
        grid.append([" "] * len(peaks))
        
    center_row = height // 2
    
    for col, peak in enumerate(peaks):
        # Calculate amplitude height in grid rows (max value = 1.0)
        # Symmetrical height = peak * (height / 2)
        amp_height = peak * center_row
        
        # Draw top half (going up from center)
        # Draw bottom half (going down from center)
        for row in range(height):
            dist_from_center = abs(row - center_row)
            if dist_from_center <= amp_height:
                grid[row][col] = "█"
            elif dist_from_center - amp_height < 1.0:
                # Fractional block rendering for precision
                fraction = dist_from_center - amp_height
                block_index = int((1.0 - fraction) * len(BLOCKS))
                block_index = max(0, min(len(BLOCKS) - 1, block_index))
                grid[row][col] = BLOCKS[block_index]

    # Print rows from top (row 0) to bottom (row height - 1)
    output = []
    for r in range(height):
        # Colorize the output waveform
        row_str = "".join(grid[r])
        if r == center_row:
            # Color the center baseline
            output.append(f"{COLOR_CYAN}{row_str}{COLOR_RESET}")
        else:
            output.append(f"{COLOR_MAGENTA}{row_str}{COLOR_RESET}")
            
    return "\n".join(output)

def generate_svg_waveform(peaks, theme_name, info, output_path):
    """Generates a highly-stylized, responsive SVG audio waveform."""
    width = 1200
    height = 300
    mid_y = height / 2
    
    theme = SVG_THEMES.get(theme_name, SVG_THEMES["ocean"])
    color1, color2 = theme
    
    # Calculate spacing and bar widths
    bar_gap = 3
    num_bars = len(peaks)
    bar_width = (width - (num_bars - 1) * bar_gap) / num_bars
    
    bars_svg = []
    for i, peak in enumerate(peaks):
        # Minimum visible height for silent parts
        h = max(3, peak * (height - 20))
        x = i * (bar_width + bar_gap)
        y = mid_y - (h / 2)
        
        bars_svg.append(
            f'<rect x="{x:.2f}" y="{y:.2f}" width="{bar_width:.2f}" height="{h:.2f}" rx="2" fill="url(#waveGrad)" />'
        )

    svg_template = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" style="background-color: #0b0f19; width: 100%; height: auto; border-radius: 12px; box-shadow: 0 4px 30px rgba(0, 0, 0, 0.3);">
    <defs>
        <linearGradient id="waveGrad" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" stop-color="{color1}" />
            <stop offset="50%" stop-color="{color2}" />
            <stop offset="100%" stop-color="{color1}" />
        </linearGradient>
        <linearGradient id="textGrad" x1="0%" y1="0%" x2="100%" y2="0%">
            <stop offset="0%" stop-color="#cbd5e1" />
            <stop offset="100%" stop-color="#94a3b8" />
        </linearGradient>
    </defs>
    
    <!-- Audio Waveform Bars -->
    <g transform="translate(0, 0)">
        {"".join(bars_svg)}
    </g>
    
    <!-- Meta Info overlay -->
    <rect x="15" y="15" width="220" height="70" rx="8" fill="rgba(15, 23, 42, 0.6)" stroke="rgba(255,255,255,0.08)" stroke-width="1" style="backdrop-filter: blur(8px);"/>
    <text x="30" y="38" font-family="-apple-system, sans-serif" font-size="12" font-weight="bold" fill="url(#textGrad)">Duration: {info['duration']:.2f}s</text>
    <text x="30" y="54" font-family="-apple-system, sans-serif" font-size="10" fill="#64748b">Rate: {info['sample_rate']} Hz | Mono averaged</text>
    <text x="30" y="70" font-family="-apple-system, sans-serif" font-size="10" fill="#64748b">Format: {info['sample_width']*8}-bit PCM WAV</text>
</svg>
"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(svg_template)

def main():
    parser = argparse.ArgumentParser(description="Visualize WAV audio files in the terminal and as vector SVGs.")
    parser.add_argument("wav_file", help="Path to the target PCM .wav file")
    parser.add_argument("-w", "--width", type=int, default=100, help="Terminal waveform width in characters (default: 100)")
    parser.add_argument("--height", type=int, default=19, help="Terminal waveform height in lines (default: 19, must be odd)")
    parser.add_argument("-s", "--svg", help="Output path for the vector SVG visualization")
    parser.add_argument("-t", "--theme", choices=["ocean", "fire", "neon", "sunset"], default="ocean", help="SVG gradient color theme")
    
    args = parser.parse_args()
    
    # Ensure height is odd for a clean center line
    height = args.height
    if height % 2 == 0:
        height += 1

    print(f"Reading WAV file: {args.wav_file}...")
    samples, info = read_wav_samples(args.wav_file)
    
    print(f"Loaded {len(samples)} samples. Duration: {info['duration']:.2f}s. Sample rate: {info['sample_rate']}Hz.")
    
    # Draw terminal representation
    peaks = get_peaks(samples, args.width)
    print("\n--- Audio Waveform Representation ---")
    print(render_terminal_waveform(peaks, height))
    print("--------------------------------------\n")
    
    if args.svg:
        svg_peaks = get_peaks(samples, 180) # Use more bins for high resolution SVG
        output_svg = os.path.abspath(args.svg)
        print(f"Generating SVG waveform: {output_svg}")
        generate_svg_waveform(svg_peaks, args.theme, info, output_svg)
        print("Done!")

if __name__ == "__main__":
    main()
