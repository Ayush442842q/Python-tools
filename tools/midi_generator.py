#!/usr/bin/env python3
"""
MIDI Generator - A tool to convert simple text-based musical notation into standard MIDI files.
"""

import argparse
import sys
import struct

# Note name mapping to semitone offset
NOTE_OFFSETS = {
    'C': 0, 'C#': 1, 'DB': 1, 'D': 2, 'D#': 3, 'EB': 3,
    'E': 4, 'F': 5, 'F#': 6, 'GB': 6, 'G': 7, 'G#': 8,
    'AB': 8, 'A': 9, 'A#': 10, 'BB': 10, 'B': 11
}

# Duration mapping relative to quarter note (1.0 = quarter note)
# e.g., '4' = quarter, '8' = eighth, '2' = half, '1' = whole, '16' = sixteenth
DURATION_MAP = {
    '1': 4.0,     # Whole note
    '2': 2.0,     # Half note
    '4': 1.0,     # Quarter note
    '8': 0.5,     # Eighth note
    '16': 0.25,   # Sixteenth note
    '32': 0.125,  # Thirty-second note
}

def parse_note(note_str):
    """
    Parse a single note string like 'C4' or 'F#5' or 'Bb3'.
    Returns the MIDI note number (0-127), or None if it's a rest.
    """
    note_str = note_str.strip().upper()
    if note_str in ('R', 'REST', 'P', 'PAUSE', '_'):
        return None

    # Separate note name and octave
    if len(note_str) < 2:
        raise ValueError(f"Invalid note format: '{note_str}'")

    # Find the boundary between letters (with # or b) and digits (octave)
    octave_idx = -1
    for i, char in enumerate(note_str):
        if char.isdigit() or char == '-':
            octave_idx = i
            break

    if octave_idx == -1:
        # Default octave to 4 if not specified
        name = note_str
        octave = 4
    else:
        name = note_str[:octave_idx]
        try:
            octave = int(note_str[octave_idx:])
        except ValueError:
            raise ValueError(f"Invalid octave in note: '{note_str}'")

    if name not in NOTE_OFFSETS:
        raise ValueError(f"Invalid note name: '{name}'")

    offset = NOTE_OFFSETS[name]
    note_num = 12 * (octave + 1) + offset

    if not (0 <= note_num <= 127):
        raise ValueError(f"MIDI note number out of bounds (0-127): {note_num} for '{note_str}'")

    return note_num

def parse_chord_or_note(token):
    """
    Parse a token which might be a note ('C4'), a chord ('C4-E4-G4'),
    optionally followed by a duration suffix (e.g. 'C4:4', 'C4-E4-G4:8').
    Returns a tuple: (list_of_midi_notes, duration_ratio)
    """
    token = token.strip()
    if not token:
        return [], 0.0

    # Split duration suffix if present
    parts = token.split(':')
    note_part = parts[0]
    
    # Default duration is quarter note (1.0)
    dur_ratio = 1.0
    if len(parts) > 1:
        dur_str = parts[1]
        if dur_str in DURATION_MAP:
            dur_ratio = DURATION_MAP[dur_str]
        else:
            try:
                # Support fractional durations directly, e.g. '0.5' for eighth note
                dur_ratio = float(dur_str)
            except ValueError:
                # Custom duration parser (e.g. support quarter notes as 4, eighth as 8)
                # If they passed '4' and it wasn't mapped (though '4' is mapped to 1.0 above),
                # we just try to parse it. Let's print a warning or fallback.
                raise ValueError(f"Unknown duration format: '{dur_str}'")

    # Parse notes (split by '-' for chords)
    note_tokens = note_part.split('-')
    midi_notes = []
    for nt in note_tokens:
        if nt:
            parsed = parse_note(nt)
            if parsed is not None:
                midi_notes.append(parsed)

    return midi_notes, dur_ratio

def encode_vlq(value):
    """Encode a value into MIDI variable-length quantity bytes."""
    if value == 0:
        return b'\x00'
    bytes_list = []
    while value > 0:
        byte = value & 0x7F
        value >>= 7
        if bytes_list:
            byte |= 0x80
        bytes_list.append(byte)
    return bytes(reversed(bytes_list))

def generate_midi(notes_sequence, bpm=120, instrument=0, ticks_per_quarter=480):
    """
    Compile a sequence of notes/chords into standard MIDI format 0 bytes.
    """
    # Header Chunk: MThd, length=6, format=0, tracks=1, division=ticks_per_quarter
    header = b'MThd' + struct.pack('>LHHH', 6, 0, 1, ticks_per_quarter)

    # Compile track events
    track_events = bytearray()
    
    # Meta Event: Set Tempo (FF 51 03 tttttt)
    # tempo in microseconds per quarter note = 60,000,000 / BPM
    us_per_quarter = int(60000000 / bpm)
    tempo_bytes = struct.pack('>L', us_per_quarter)[1:]  # 3 bytes
    
    # Delta time 0 for tempo setup
    track_events.extend(encode_vlq(0))
    track_events.extend(b'\xFF\x51\x03' + tempo_bytes)

    # Program Change (Change instrument on Channel 0): C0 <instrument>
    track_events.extend(encode_vlq(0))
    track_events.extend(struct.pack('BB', 0xC0, instrument))

    # Process notes
    pending_delta = 0
    
    for token in notes_sequence.split():
        if not token:
            continue
        try:
            midi_notes, dur_ratio = parse_chord_or_note(token)
        except ValueError as e:
            print(f"Error parsing token '{token}': {e}", file=sys.stderr)
            sys.exit(1)

        step_ticks = int(dur_ratio * ticks_per_quarter)

        if not midi_notes:
            # It's a rest, accumulate the ticks to pending delta
            pending_delta += step_ticks
            continue

        # Note On for all notes in the chord/note
        # First note gets the pending delta time, others get 0
        first = True
        for note in midi_notes:
            dt = pending_delta if first else 0
            # 0x90 = Note On, channel 0. Velocity 96 (0x60)
            track_events.extend(encode_vlq(dt))
            track_events.extend(struct.pack('BBB', 0x90, note, 0x60))
            first = False
        
        pending_delta = 0

        # Note Off (or Note On with velocity 0) for all notes in the chord/note
        # The first Note Off gets the step_ticks delta (meaning the notes play for step_ticks)
        # Subsequent Note Offs get 0
        first = True
        for note in midi_notes:
            dt = step_ticks if first else 0
            # 0x80 = Note Off, channel 0. Velocity 0 (0x00)
            track_events.extend(encode_vlq(dt))
            track_events.extend(struct.pack('BBB', 0x80, note, 0x00))
            first = False

    # Meta Event: End of Track (FF 2F 00)
    track_events.extend(encode_vlq(pending_delta))
    track_events.extend(b'\xFF\x2F\x00')

    # Track Chunk: MTrk, length, track_events
    track_header = b'MTrk' + struct.pack('>L', len(track_events))
    
    return header + track_header + track_events

def main():
    parser = argparse.ArgumentParser(
        description="MIDI Generator - Convert text musical notation to standard MIDI files."
    )
    parser.add_argument(
        "notes",
        nargs="?",
        help="Space-separated musical notes/chords sequence (e.g. 'C4:4 D4:4 E4:4 C4:4')"
    )
    parser.add_argument(
        "-f", "--file",
        help="Input text file containing notes sequence"
    )
    parser.add_argument(
        "-o", "--output",
        default="output.mid",
        help="Output MIDI file name (default: output.mid)"
    )
    parser.add_argument(
        "-t", "--tempo",
        type=int,
        default=120,
        help="Tempo in BPM (default: 120)"
    )
    parser.add_argument(
        "-i", "--instrument",
        type=int,
        default=0,
        help="MIDI Instrument program number 0-127 (default: 0 = Acoustic Piano)"
    )

    args = parser.parse_args()

    notes_seq = ""
    if args.file:
        try:
            with open(args.file, "r") as f:
                notes_seq = f.read()
        except FileNotFoundError:
            print(f"Error: Input file '{args.file}' not found.", file=sys.stderr)
            sys.exit(1)
    elif args.notes:
        notes_seq = args.notes
    else:
        # Default demo song (Frere Jacques / Brother John)
        print("No notes provided. Generating a demo melody (Frere Jacques)...")
        notes_seq = (
            "C4:4 D4:4 E4:4 C4:4  C4:4 D4:4 E4:4 C4:4 "
            "E4:4 F4:4 G4:2  E4:4 F4:4 G4:2 "
            "G4:8 A4:8 G4:8 F4:8 E4:4 C4:4  G4:8 A4:8 G4:8 F4:8 E4:4 C4:4 "
            "C4:4 G3:4 C4:2  C4:4 G3:4 C4:2"
        )

    # Clean up whitespace and newlines
    notes_seq = " ".join(notes_seq.replace("\n", " ").split())
    
    midi_data = generate_midi(
        notes_seq, 
        bpm=args.tempo, 
        instrument=args.instrument
    )

    try:
        with open(args.output, "wb") as f:
            f.write(midi_data)
        print(f"✓ Successfully generated MIDI file: {args.output}")
        print(f"  Tempo: {args.tempo} BPM")
        print(f"  Instrument: {args.instrument}")
        print(f"  Notes processed: {len(notes_seq.split())}")
    except Exception as e:
        print(f"Error writing output file: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
