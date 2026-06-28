#!/usr/bin/env python3
"""
Video Metadata Extractor
Extract and display metadata from video files (duration, codec, resolution, bitrate, etc.)
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Optional, Dict, Any

try:
    import subprocess
    HAS_FFMPEG = True
except ImportError:
    HAS_FFMPEG = False


def check_ffmpeg() -> bool:
    """Check if ffmpeg/ffprobe is installed."""
    try:
        result = subprocess.run(
            ['ffprobe', '-version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def get_video_metadata(filepath: str) -> Optional[Dict[str, Any]]:
    """Extract metadata from video file using ffprobe."""
    if not check_ffmpeg():
        print("Error: ffprobe not found")
        print("Install FFmpeg: https://ffmpeg.org/download.html")
        print("Or use: winget install ffmpeg (Windows)")
        print("Or: sudo apt install ffmpeg (Ubuntu)")
        print("Or: brew install ffmpeg (macOS)")
        return None
    
    try:
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-print_format', 'json',
            '-show_format',
            '-show_streams',
            filepath
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode != 0:
            print(f"Error: {result.stderr}")
            return None
        
        data = json.loads(result.stdout)
        
        metadata = {
            'filepath': filepath,
            'format': {},
            'video_streams': [],
            'audio_streams': [],
            'other_streams': []
        }
        
        # Format info
        if 'format' in data:
            fmt = data['format']
            metadata['format'] = {
                'format_name': fmt.get('format_name', 'unknown'),
                'format_long_name': fmt.get('format_long_name', 'unknown'),
                'duration': round(float(fmt.get('duration', 0)), 2),
                'size_bytes': int(fmt.get('size', 0)),
                'bitrate': int(fmt.get('bit_rate', 0)),
                'tags': {}
            }
            
            # Extract tags
            if 'tags' in fmt:
                tags = fmt['tags']
                tag_map = {
                    'title': 'title',
                    'artist': 'artist',
                    'album': 'album',
                    'date': 'year',
                    'genre': 'genre',
                    'track': 'track',
                    'comment': 'comment',
                    'creation_time': 'creation_time'
                }
                for k, v in tag_map.items():
                    if k in tags:
                        metadata['format']['tags'][v] = tags[k]
        
        # Stream info
        if 'streams' in data:
            for stream in data['streams']:
                stream_info = {
                    'index': stream.get('index'),
                    'codec_type': stream.get('codec_type'),
                    'codec_name': stream.get('codec_name'),
                    'codec_long_name': stream.get('codec_long_name'),
                }
                
                if stream.get('codec_type') == 'video':
                    stream_info.update({
                        'width': stream.get('width'),
                        'height': stream.get('height'),
                        'aspect_ratio': stream.get('display_aspect_ratio', ''),
                        'frame_rate': stream.get('r_frame_rate', ''),
                        'avg_frame_rate': stream.get('avg_frame_rate', ''),
                        'bit_rate': int(stream.get('bit_rate', 0)),
                        'pix_fmt': stream.get('pix_fmt'),
                        'color_space': stream.get('color_space'),
                        'color_range': stream.get('color_range'),
                        'bits_per_sample': stream.get('bits_per_sample'),
                    })
                    
                    # Calculate resolution string
                    if stream_info.get('width') and stream_info.get('height'):
                        w, h = stream_info['width'], stream_info['height']
                        if w >= 3840 and h >= 2160:
                            stream_info['resolution_name'] = '4K UHD'
                        elif w >= 2560 and h >= 1440:
                            stream_info['resolution_name'] = '1440p (2K)'
                        elif w >= 1920 and h >= 1080:
                            stream_info['resolution_name'] = '1080p (Full HD)'
                        elif w >= 1280 and h >= 720:
                            stream_info['resolution_name'] = '720p (HD)'
                        elif w >= 854 and h >= 480:
                            stream_info['resolution_name'] = '480p (SD)'
                        else:
                            stream_info['resolution_name'] = f'{w}x{h}'
                    
                    metadata['video_streams'].append(stream_info)
                
                elif stream.get('codec_type') == 'audio':
                    stream_info.update({
                        'sample_rate': stream.get('sample_rate'),
                        'channels': stream.get('channels'),
                        'channel_layout': stream.get('channel_layout'),
                        'bit_rate': int(stream.get('bit_rate', 0)),
                        'bits_per_sample': stream.get('bits_per_sample'),
                    })
                    metadata['audio_streams'].append(stream_info)
                
                else:
                    metadata['other_streams'].append(stream_info)
        
        return metadata
    
    except subprocess.TimeoutExpired:
        print("Error: ffprobe timed out")
        return None
    except json.JSONDecodeError as e:
        print(f"Error parsing ffprobe output: {e}")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


def format_duration(seconds: float) -> str:
    """Format duration in HH:MM:SS.mmm format."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


def format_size(bytes_val: int) -> str:
    """Format file size in human-readable format."""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_val < 1024:
            return f"{bytes_val:.2f} {unit}"
        bytes_val /= 1024
    return f"{bytes_val:.2f} PB"


def format_bitrate(bps: int) -> str:
    """Format bitrate in human-readable format."""
    if bps >= 1000000:
        return f"{bps / 1000000:.2f} Mbps"
    elif bps >= 1000:
        return f"{bps / 1000:.2f} Kbps"
    else:
        return f"{bps} bps"


def display_metadata(metadata: Dict[str, Any], json_output: bool = False,
                    brief: bool = False):
    """Display metadata in formatted output."""
    if json_output:
        print(json.dumps(metadata, indent=2))
        return
    
    if brief:
        # Brief output mode
        fmt = metadata.get('format', {})
        duration = fmt.get('duration', 0)
        size = fmt.get('size_bytes', 0)
        
        video_str = ""
        if metadata.get('video_streams'):
            v = metadata['video_streams'][0]
            video_str = f"{v.get('width', '?')}x{v.get('height', '?')} {v.get('codec_name', '?')}"
        
        print(f"{Path(metadata['filepath']).name}")
        print(f"  Duration: {format_duration(duration)}")
        print(f"  Size: {format_size(size)}")
        if video_str:
            print(f"  Video: {video_str}")
        return
    
    # Full output
    print(f"\n{'='*60}")
    print(f"File: {metadata['filepath']}")
    print(f"{'='*60}")
    
    # Format info
    fmt = metadata.get('format', {})
    print(f"\nFormat:")
    print(f"  Name: {fmt.get('format_name', 'N/A')}")
    print(f"  Full Name: {fmt.get('format_long_name', 'N/A')}")
    if fmt.get('duration'):
        print(f"  Duration: {format_duration(fmt['duration'])}")
    if fmt.get('size_bytes'):
        print(f"  Size: {format_size(fmt['size_bytes'])}")
    if fmt.get('bitrate'):
        print(f"  Bitrate: {format_bitrate(fmt['bitrate'])}")
    
    # Tags
    tags = fmt.get('tags', {})
    if tags:
        print(f"\nTags:")
        for key, value in tags.items():
            print(f"  {key}: {value}")
    
    # Video streams
    if metadata.get('video_streams'):
        print(f"\nVideo Stream(s):")
        for i, stream in enumerate(metadata['video_streams'], 1):
            print(f"  #{i}:")
            print(f"    Codec: {stream.get('codec_name')} ({stream.get('codec_long_name', '')})")
            if stream.get('width') and stream.get('height'):
                print(f"    Resolution: {stream['width']}x{stream['height']} {stream.get('resolution_name', '')}")
            if stream.get('aspect_ratio'):
                print(f"    Aspect Ratio: {stream['aspect_ratio']}")
            if stream.get('frame_rate'):
                print(f"    Frame Rate: {stream['frame_rate']}")
            if stream.get('pix_fmt'):
                print(f"    Pixel Format: {stream['pix_fmt']}")
            if stream.get('bit_rate'):
                print(f"    Bitrate: {format_bitrate(stream['bit_rate'])}")
    
    # Audio streams
    if metadata.get('audio_streams'):
        print(f"\nAudio Stream(s):")
        for i, stream in enumerate(metadata['audio_streams'], 1):
            print(f"  #{i}:")
            print(f"    Codec: {stream.get('codec_name')} ({stream.get('codec_long_name', '')})")
            if stream.get('sample_rate'):
                print(f"    Sample Rate: {stream['sample_rate']} Hz")
            if stream.get('channels'):
                print(f"    Channels: {stream['channels']}")
            if stream.get('channel_layout'):
                print(f"    Channel Layout: {stream['channel_layout']}")
            if stream.get('bit_rate'):
                print(f"    Bitrate: {format_bitrate(stream['bit_rate'])}")


def main():
    parser = argparse.ArgumentParser(
        description='Video Metadata Extractor - Extract and display video file metadata'
    )
    
    parser.add_argument('file', nargs='?', help='Video file path')
    parser.add_argument('-j', '--json', action='store_true',
                       help='Output as JSON')
    parser.add_argument('-b', '--brief', action='store_true',
                       help='Brief output summary only')
    parser.add_argument('-r', '--recursive', action='store_true',
                       help='Process directory recursively')
    parser.add_argument('--supported-formats', action='store_true',
                       help='List supported video formats')
    
    args = parser.parse_args()
    
    if args.supported_formats:
        formats = [
            'MP4 (.mp4)', 'AVI (.avi)', 'MKV (.mkv)', 'MOV (.mov)',
            'WMV (.wmv)', 'FLV (.flv)', 'WebM (.webm)', 'M4V (.m4v)',
            'MPEG (.mpg, .mpeg)', '3GP (.3gp)', 'OGV (.ogv)',
            'GIF (.gif)', 'TS (.ts)'
        ]
        print("Supported Video Formats:")
        print("-" * 40)
        for fmt in formats:
            print(f"  - {fmt}")
        sys.exit(0)
    
    if not args.file:
        parser.print_help()
        sys.exit(1)
    
    filepath = Path(args.file)
    
    if not filepath.exists():
        print(f"Error: File '{args.file}' not found")
        sys.exit(1)
    
    if filepath.is_dir():
        if args.recursive:
            video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', 
                              '.flv', '.webm', '.m4v', '.mpg', '.mpeg', 
                              '.3gp', '.ogv', '.gif', '.ts'}
            video_files = []
            for ext in video_extensions:
                video_files.extend(filepath.rglob(f'*{ext}'))
                video_files.extend(filepath.rglob(f'*{ext.upper()}'))
            
            if not video_files:
                print(f"No video files found in '{filepath}'")
                sys.exit(0)
            
            print(f"Found {len(video_files)} video file(s)")
            for vf in sorted(video_files):
                metadata = get_video_metadata(str(vf))
                if metadata:
                    display_metadata(metadata, args.json, brief=True)
                    if not args.json:
                        print()
        else:
            print("Use --recursive flag to process directories")
            sys.exit(1)
    else:
        metadata = get_video_metadata(str(filepath))
        if metadata:
            display_metadata(metadata, args.json, args.brief)
            sys.exit(0)
        else:
            sys.exit(1)


if __name__ == '__main__':
    main()