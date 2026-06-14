#!/usr/bin/env python3
"""
Subtitle Sync and Converter

A command-line tool to adjust subtitle timing (time shifting) and convert between
SRT (SubRip) and VTT (WebVTT) formats.

Usage:
    python tools/subtitle_sync_converter.py input.srt --shift 1.5 --out output.vtt
    python tools/subtitle_sync_converter.py movie.vtt --shift -500ms --convert srt
"""

import argparse
import sys
import re
import os

# Timestamp patterns
TIMESTAMP_re = re.compile(r'(\d{1,2}):(\d{2}):(\d{2})[.,](\d{3})')
VTT_SHORT_TIMESTAMP_re = re.compile(r'(\d{2}):(\d{2})[.,](\d{3})')

def time_str_to_ms(t_str):
    """Converts HH:MM:SS.mmm or MM:SS.mmm string to total milliseconds."""
    m = TIMESTAMP_re.match(t_str)
    if m:
        hours, mins, secs, ms = map(int, m.groups())
        return ms + (secs * 1000) + (mins * 60 * 1000) + (hours * 60 * 60 * 1000)
    
    m_short = VTT_SHORT_TIMESTAMP_re.match(t_str)
    if m_short:
        mins, secs, ms = map(int, m_short.groups())
        return ms + (secs * 1000) + (mins * 60 * 1000)
        
    raise ValueError(f"Invalid timestamp format: {t_str}")

def ms_to_time_str(total_ms, format_type='srt'):
    """Converts total milliseconds to HH:MM:SS,mmm (SRT) or HH:MM:SS.mmm (VTT) format."""
    if total_ms < 0:
        total_ms = 0  # Do not allow negative timestamps
        
    ms = int(total_ms % 1000)
    total_secs = int(total_ms // 1000)
    secs = int(total_secs % 60)
    total_mins = int(total_secs // 60)
    mins = int(total_mins % 60)
    hours = int(total_mins // 60)
    
    separator = ',' if format_type == 'srt' else '.'
    return f"{hours:02d}:{mins:02d}:{secs:02d}{separator}{ms:03d}"

def parse_shift_val(shift_str):
    """Parses shift value like '1.5', '-1.5', '500ms', '-300ms' to float seconds."""
    if not shift_str:
        return 0.0
    
    shift_str = shift_str.strip().lower()
    
    # Check if milliseconds specified
    if shift_str.endswith('ms'):
        try:
            return float(shift_str[:-2]) / 1000.0
        except ValueError:
            pass
            
    # Check if seconds specified with 's' suffix
    if shift_str.endswith('s'):
        try:
            return float(shift_str[:-1])
        except ValueError:
            pass
            
    # Default is float seconds
    try:
        return float(shift_str)
    except ValueError:
        raise ValueError(f"Could not parse shift value: {shift_str}. Use e.g. '1.5', '-500ms'")

def parse_subtitles(content):
    """Parses subtitles from a string, extracting cues."""
    # Normalize line endings
    content = content.replace('\r\n', '\n').strip()
    
    # Detect VTT header
    is_vtt = content.startswith("WEBVTT")
    if is_vtt:
        # Strip WEBVTT header and any leading metadata/styles
        header_end = content.find('\n\n')
        if header_end != -1:
            body = content[header_end + 2:]
        else:
            body = content[6:]
    else:
        body = content

    # Split into blocks by double newline (cues)
    blocks = re.split(r'\n\n+', body)
    cues = []
    
    # Regex to extract timestamps: HH:MM:SS.mmm --> HH:MM:SS.mmm
    time_line_re = re.compile(r'(\d{1,2}:\d{2}:\d{2}[.,]\d{3}|\d{2}:\d{2}[.,]\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[.,]\d{3}|\d{2}:\d{2}[.,]\d{3})')
    
    warning_count = 0
    
    for block_idx, block in enumerate(blocks):
        lines = block.strip().split('\n')
        if not lines or (len(lines) == 1 and lines[0] == ''):
            continue
            
        cue_id = ""
        time_line_idx = -1
        
        # Find time line in block (could be first or second line)
        for i, line in enumerate(lines[:3]):
            if '-->' in line:
                time_line_idx = i
                break
                
        if time_line_idx == -1:
            # Not a valid cue block, skip or treat as warning
            warning_count += 1
            continue
            
        if time_line_idx > 0:
            cue_id = lines[0].strip()
            
        time_line = lines[time_line_idx]
        match = time_line_re.search(time_line)
        if not match:
            warning_count += 1
            continue
            
        start_str, end_str = match.groups()
        
        try:
            start_ms = time_str_to_ms(start_str)
            end_ms = time_str_to_ms(end_str)
        except ValueError:
            warning_count += 1
            continue
            
        text = "\n".join(lines[time_line_idx + 1:])
        
        cues.append({
            "id": cue_id,
            "start": start_ms,
            "end": end_ms,
            "text": text
        })
        
    return cues, is_vtt, warning_count

def generate_subtitle_content(cues, target_format='srt'):
    """Generates the subtitle file contents in the specified format."""
    output = []
    if target_format == 'vtt':
        output.append("WEBVTT\n\n")
        
    for idx, cue in enumerate(cues, 1):
        cue_id = cue['id'] if cue['id'] else str(idx)
        start_str = ms_to_time_str(cue['start'], format_type=target_format)
        end_str = ms_to_time_str(cue['end'], format_type=target_format)
        
        if target_format == 'srt':
            output.append(f"{cue_id}\n")
        else:
            # In VTT, ID is optional but good practice
            output.append(f"{cue_id}\n")
            
        output.append(f"{start_str} --> {end_str}\n")
        output.append(f"{cue['text']}\n\n")
        
    return "".join(output).strip() + "\n"

def main():
    parser = argparse.ArgumentParser(description="Synchronize (time shift) and convert SRT/VTT subtitle files.")
    parser.add_argument("input_file", help="Path to the input subtitle file (.srt or .vtt)")
    parser.add_argument("--shift", help="Time shift to apply, e.g. '1.5' (seconds) or '-500ms'. Use negative values to make subtitles appear earlier.")
    parser.add_argument("--convert", choices=['srt', 'vtt'], help="Convert to target format ('srt' or 'vtt')")
    parser.add_argument("--out", help="Path to write the output file (defaults to stdout if not specified)")
    
    args = parser.parse_args()

    if not os.path.exists(args.input_file):
        print(f"Error: Input file '{args.input_file}' not found.", file=sys.stderr)
        return 1

    try:
        with open(args.input_file, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
    except Exception as e:
        print(f"Error reading input file: {e}", file=sys.stderr)
        return 1

    try:
        cues, detected_vtt, warnings = parse_subtitles(content)
    except Exception as e:
        print(f"Error parsing subtitles: {e}", file=sys.stderr)
        return 1

    orig_format = 'vtt' if detected_vtt else 'srt'
    target_format = args.convert if args.convert else orig_format
    
    if args.out:
        # Infer target format from output file extension if convert is not specified
        _, ext = os.path.splitext(args.out)
        if ext.lower() in ['.srt', '.vtt'] and not args.convert:
            target_format = ext[1:].lower()

    # Apply shift
    shift_s = 0.0
    if args.shift:
        try:
            shift_s = parse_shift_val(args.shift)
        except ValueError as e:
            print(f"Error: {e}", file=sys.stderr)
            return 1
            
        shift_ms = int(shift_s * 1000)
        for cue in cues:
            cue['start'] = max(0, cue['start'] + shift_ms)
            cue['end'] = max(0, cue['end'] + shift_ms)

    # Format output
    out_content = generate_subtitle_content(cues, target_format)
    
    # Print status
    total_duration_sec = (cues[-1]['end'] - cues[0]['start']) / 1000.0 if cues else 0
    
    status_info = [
        f"Input Format: {orig_format.upper()}",
        f"Output Format: {target_format.upper()}",
        f"Total Cues: {len(cues)}",
        f"Duration: {total_duration_sec:.2f} seconds",
        f"Warnings/Skipped blocks: {warnings}"
    ]
    if shift_s != 0.0:
        status_info.append(f"Applied Time Shift: {shift_s:+.3f}s")
        
    print(" | ".join(status_info), file=sys.stderr)

    if args.out:
        try:
            with open(args.out, 'w', encoding='utf-8') as f:
                f.write(out_content)
            print(f"Saved synchronized subtitles to: {args.out}", file=sys.stderr)
        except Exception as e:
            print(f"Error writing output file: {e}", file=sys.stderr)
            return 1
    else:
        sys.stdout.write(out_content)

    return 0

if __name__ == "__main__":
    sys.exit(main())
