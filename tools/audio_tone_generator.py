#!/usr/bin/env python3
"""
Audio Tone Generator & Melody Compiler - Zero-dependency WAV synthesizer
Generate clean waveforms, frequency sweeps, custom ADSR envelopes, stereo panning,
and compile text-based sheet music melodies into high-quality WAV files.
"""

import argparse
import math
import random
import struct
import sys
import wave
from typing import Dict, List, Tuple

# Mapping of notes to frequencies (in Octave 4)
NOTE_FREQS = {
    'C': 261.63, 'C#': 277.18, 'Db': 277.18, 'D': 293.66, 'D#': 311.13, 'Eb': 311.13,
    'E': 329.63, 'F': 349.23, 'F#': 369.99, 'Gb': 369.99, 'G': 392.00, 'G#': 415.30,
    'Ab': 415.30, 'A': 440.00, 'A#': 466.16, 'Bb': 466.16, 'B': 493.88
}

# Standard sample rate
SAMPLE_RATE = 44100

def get_note_freq(note_name: str) -> float:
    """Calculate frequency of a note from its name (e.g. C4, A#5, Gb3). Returns 0.0 for rests (R)."""
    if note_name.upper() == 'R':
        return 0.0
    
    # Parse note and octave
    if len(note_name) > 1 and note_name[-1].isdigit():
        note = note_name[:-1]
        octave = int(note_name[-1])
    else:
        note = note_name
        octave = 4  # Default octave
        
    if note not in NOTE_FREQS:
        raise ValueError(f"Invalid note name: {note}")
        
    base_freq = NOTE_FREQS[note]
    # Shift frequency by octave relative to octave 4
    return base_freq * (2.0 ** (octave - 4))

def apply_adsr(sample_idx: int, total_samples: int, sample_rate: int,
               attack: float, decay: float, sustain: float, release: float) -> float:
    """Calculate the ADSR envelope multiplier (0.0 to 1.0) for a given sample index."""
    t = sample_idx / sample_rate
    duration = total_samples / sample_rate
    
    # Calculate durations in seconds
    a_len = attack
    d_len = decay
    r_len = release
    s_len = max(0.0, duration - (a_len + d_len + r_len))
    
    # Adjust envelope if total duration is shorter than ADSR times
    total_env = a_len + d_len + r_len
    if total_env > duration:
        factor = duration / total_env
        a_len *= factor
        d_len *= factor
        r_len *= factor
        s_len = 0.0

    # Boundaries
    t_decay = a_len
    t_sustain = a_len + d_len
    t_release = a_len + d_len + s_len
    
    if t < a_len:
        # Attack phase: linear ramp from 0 to 1
        return t / a_len if a_len > 0 else 1.0
    elif t < t_sustain:
        # Decay phase: linear decay from 1 to sustain level
        dt = t - t_decay
        return 1.0 - (1.0 - sustain) * (dt / d_len) if d_len > 0 else sustain
    elif t < t_release:
        # Sustain phase: constant level
        return sustain
    elif t < duration:
        # Release phase: linear decay from sustain level to 0
        rt = t - t_release
        return sustain * (1.0 - rt / r_len) if r_len > 0 else 0.0
    else:
        return 0.0

def generate_sample(t: float, freq: float, wave_type: str, phase: float = 0.0) -> float:
    """Generate a raw waveform sample (-1.0 to 1.0) for a given time, frequency, and wave type."""
    if freq <= 0.0:
        return 0.0  # Silence for rests/invalid freqs
        
    cycle_t = (t * freq + phase) % 1.0
    
    if wave_type == 'sine':
        return math.sin(2.0 * math.pi * freq * t + phase)
    elif wave_type == 'square':
        return 1.0 if cycle_t < 0.5 else -1.0
    elif wave_type == 'triangle':
        if cycle_t < 0.25:
            return cycle_t * 4.0
        elif cycle_t < 0.75:
            return 2.0 - cycle_t * 4.0
        else:
            return cycle_t * 4.0 - 4.0
    elif wave_type == 'sawtooth':
        return 2.0 * cycle_t - 1.0
    elif wave_type == 'noise':
        return random.uniform(-1.0, 1.0)
    else:
        return math.sin(2.0 * math.pi * freq * t)

def synthesize_tone(freq: float, duration: float, wave_type: str = 'sine',
                    volume: float = 0.5, pan: float = 0.5,
                    attack: float = 0.01, decay: float = 0.05,
                    sustain: float = 0.8, release: float = 0.1,
                    sweep_to_freq: float = 0.0) -> List[Tuple[float, float]]:
    """Synthesize stereo samples for a single tone with panning, ADSR envelope, and frequency sweeps."""
    total_samples = int(duration * SAMPLE_RATE)
    samples = []
    
    # Calculate constant panning scaling
    # pan=0.0 (all left), pan=0.5 (center), pan=1.0 (all right)
    left_gain = math.sqrt(1.0 - pan)
    right_gain = math.sqrt(pan)
    
    # Initialize dynamic frequency tracking for sweeps
    is_sweep = sweep_to_freq > 0.0 and sweep_to_freq != freq
    current_phase = 0.0
    
    for i in range(total_samples):
        t = i / SAMPLE_RATE
        
        # Calculate frequency at this sample if doing a sweep (linear interpolation)
        current_freq = freq
        if is_sweep:
            progress = i / total_samples
            current_freq = freq + (sweep_to_freq - freq) * progress
            
        # Accumulate phase to avoid crackles/discontinuity during sweeps
        current_phase += (2.0 * math.pi * current_freq) / SAMPLE_RATE
        
        # Base waveform value
        val = generate_sample(t, current_freq, wave_type, phase=current_phase - (2.0 * math.pi * current_freq * t))
        
        # Apply ADSR Envelope
        env = apply_adsr(i, total_samples, SAMPLE_RATE, attack, decay, sustain, release)
        val *= env * volume
        
        # Clamp value
        val = max(-1.0, min(1.0, val))
        
        # Stereo panning
        samples.append((val * left_gain, val * right_gain))
        
    return samples

def parse_melody(melody_str: str) -> List[Tuple[str, float]]:
    """
    Parse a melody string formatted as "Note:Duration Note:Duration ..."
    Example: "C4:0.5 E4:0.5 G4:1.0 R:0.25 C5:1.0"
    """
    tokens = melody_str.strip().split()
    notes = []
    for token in tokens:
        if ':' in token:
            note_name, duration_str = token.split(':')
            duration = float(duration_str)
        else:
            note_name = token
            duration = 0.25  # Default duration (quarter note)
        notes.append((note_name, duration))
    return notes

def save_wav(filename: str, stereo_samples: List[Tuple[float, float]]) -> None:
    """Save synthesized stereo samples to a 16-bit PCM WAV file."""
    with wave.open(filename, 'wb') as wav:
        wav.setnchannels(2)
        wav.setsampwidth(2)  # 16-bit PCM
        wav.setframerate(SAMPLE_RATE)
        
        packed_frames = []
        for left, right in stereo_samples:
            # Convert float samples (-1.0 to 1.0) to 16-bit integers
            l_val = int(left * 32767)
            r_val = int(right * 32767)
            
            # Pack as short integers (h) for left and right channels
            packed_frames.append(struct.pack('<hh', l_val, r_val))
            
        wav.writeframes(b''.join(packed_frames))

def main():
    parser = argparse.ArgumentParser(
        description="Audio Tone Generator & Melody Compiler - Zero-dependency WAV synthesizer",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Synthesizer commands')
    
    # Subcommand: tone
    tone_parser = subparsers.add_parser('tone', help='Generate a single tone')
    tone_parser.add_argument('-f', '--frequency', type=float, default=440.0, help='Frequency in Hz (default: 440.0)')
    tone_parser.add_argument('-d', '--duration', type=float, default=2.0, help='Duration in seconds (default: 2.0)')
    tone_parser.add_argument('-w', '--waveform', choices=['sine', 'square', 'triangle', 'sawtooth', 'noise'], default='sine', help='Waveform type (default: sine)')
    tone_parser.add_argument('-v', '--volume', type=float, default=0.5, help='Volume 0.0 to 1.0 (default: 0.5)')
    tone_parser.add_argument('-p', '--pan', type=float, default=0.5, help='Stereo Panning 0.0=Left, 0.5=Center, 1.0=Right (default: 0.5)')
    tone_parser.add_argument('--sweep-to', type=float, default=0.0, help='Sweep frequency linearly to this target (Hz)')
    tone_parser.add_argument('--attack', type=float, default=0.05, help='ADSR Attack time in seconds (default: 0.05)')
    tone_parser.add_argument('--decay', type=float, default=0.1, help='ADSR Decay time in seconds (default: 0.1)')
    tone_parser.add_argument('--sustain', type=float, default=0.8, help='ADSR Sustain level 0.0 to 1.0 (default: 0.8)')
    tone_parser.add_argument('--release', type=float, default=0.15, help='ADSR Release time in seconds (default: 0.15)')
    tone_parser.add_argument('-o', '--output', default='tone.wav', help='Output file name (default: tone.wav)')
    
    # Subcommand: melody
    melody_parser = subparsers.add_parser('melody', help='Compile sheet music text into a melody')
    melody_group = melody_parser.add_mutually_exclusive_group(required=True)
    melody_group.add_argument('-m', '--melody', help='Melody string (e.g. "C4:0.5 E4:0.5 G4:1.0")')
    melody_group.add_argument('-f', '--file', help='Path to file containing a melody string')
    melody_group.add_argument('--demo', action='store_true', help='Generate a built-in classical melody demo')
    melody_parser.add_argument('-w', '--waveform', choices=['sine', 'square', 'triangle', 'sawtooth'], default='sine', help='Waveform type (default: sine)')
    melody_parser.add_argument('-v', '--volume', type=float, default=0.4, help='Volume 0.0 to 1.0 (default: 0.4)')
    melody_parser.add_argument('-o', '--output', default='melody.wav', help='Output file name (default: melody.wav)')
    melody_parser.add_argument('--attack', type=float, default=0.02, help='ADSR Attack (default: 0.02)')
    melody_parser.add_argument('--decay', type=float, default=0.04, help='ADSR Decay (default: 0.04)')
    melody_parser.add_argument('--sustain', type=float, default=0.7, help='ADSR Sustain (default: 0.7)')
    melody_parser.add_argument('--release', type=float, default=0.1, help='ADSR Release (default: 0.1)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(0)
        
    if args.command == 'tone':
        print(f"Synthesizing {args.waveform} tone...")
        print(f"  Frequency: {args.frequency} Hz" + (f" -> Sweeping to {args.sweep_to} Hz" if args.sweep_to > 0 else ""))
        print(f"  Duration: {args.duration}s, Volume: {args.volume}, Pan: {args.pan}")
        print(f"  ADSR Envelope: A={args.attack}s, D={args.decay}s, S={args.sustain}, R={args.release}s")
        
        samples = synthesize_tone(
            freq=args.frequency, duration=args.duration, wave_type=args.waveform,
            volume=args.volume, pan=args.pan, attack=args.attack, decay=args.decay,
            sustain=args.sustain, release=args.release, sweep_to_freq=args.sweep_to
        )
        
        save_wav(args.output, samples)
        print(f"Success! Saved tone to [tone.wav](file:///{args.output.replace('\\', '/')})")
        
    elif args.command == 'melody':
        melody_str = ""
        if args.demo:
            # Twinkle Twinkle Little Star demo
            melody_str = (
                "C4:0.5 C4:0.5 G4:0.5 G4:0.5 A4:0.5 A4:0.5 G4:1.0 "
                "F4:0.5 F4:0.5 E4:0.5 E4:0.5 D4:0.5 D4:0.5 C4:1.0 "
                "G4:0.5 G4:0.5 F4:0.5 F4:0.5 E4:0.5 E4:0.5 D4:1.0 "
                "G4:0.5 G4:0.5 F4:0.5 F4:0.5 E4:0.5 E4:0.5 D4:1.0 "
                "C4:0.5 C4:0.5 G4:0.5 G4:0.5 A4:0.5 A4:0.5 G4:1.0 "
                "F4:0.5 F4:0.5 E4:0.5 E4:0.5 D4:0.5 D4:0.5 C4:1.0"
            )
            print("Compiling 'Twinkle Twinkle Little Star' demo...")
        elif args.file:
            try:
                with open(args.file, 'r') as f:
                    melody_str = f.read()
                print(f"Reading melody from {args.file}...")
            except Exception as e:
                print(f"Error reading file: {e}", file=sys.stderr)
                sys.exit(1)
        else:
            melody_str = args.melody
            print("Compiling user-supplied melody string...")
            
        try:
            notes = parse_melody(melody_str)
        except Exception as e:
            print(f"Error parsing melody: {e}", file=sys.stderr)
            sys.exit(1)
            
        print(f"Synthesizing {len(notes)} notes using {args.waveform} waveform...")
        all_samples = []
        for i, (note_name, duration) in enumerate(notes):
            try:
                freq = get_note_freq(note_name)
            except ValueError as e:
                print(f"Warning: Skipping note at index {i} due to error: {e}", file=sys.stderr)
                continue
                
            # Synthesize note
            note_samples = synthesize_tone(
                freq=freq, duration=duration, wave_type=args.waveform,
                volume=args.volume, pan=0.5, attack=args.attack, decay=args.decay,
                sustain=args.sustain, release=args.release
            )
            all_samples.extend(note_samples)
            
        save_wav(args.output, all_samples)
        print(f"Success! Compiled melody saved to [melody.wav](file:///{args.output.replace('\\', '/')})")

if __name__ == '__main__':
    main()
