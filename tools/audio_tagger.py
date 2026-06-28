#!/usr/bin/env python3
"""
Audio File Metadata Editor & Tagger
Edit ID3 tags, metadata, and cover art for audio files (MP3, FLAC, OGG, M4A).
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

try:
    import mutagen
    from mutagen.id3 import ID3, TIT2, TALB, TPE1, TDRC, TCON, APIC, Travis
    from mutagen.mp3 import MP3
    from mutagen.flac import FLAC
    from mutagen.oggvorbis import OggVorbis
    from mutagen.mp4 import MP4
    HAS_MUTAGEN = True
except ImportError:
    HAS_MUTAGEN = False


def get_audio_metadata(filepath: str) -> dict:
    """Extract metadata from audio file."""
    try:
        import mutagen
        from mutagen.mp3 import MP3
        from mutagen.flac import FLAC
        from mutagen.oggvorbis import OggVorbis
        from mutagen.mp4 import MP4
    except ImportError:
        print("Error: mutagen not installed")
        print("Install with: pip install mutagen")
        sys.exit(1)
    
    try:
        audio = mutagen.File(filepath)
    except Exception as e:
        print(f"Error reading file: {e}")
        return {}
    
    if audio is None:
        print(f"Unsupported audio format: {filepath}")
        return {}
    
    metadata = {
        'filepath': filepath,
        'format': type(audio).__name__,
        'duration': round(audio.info.length, 2) if audio.info else None,
        'bitrate': None,
        'sample_rate': None,
        'channels': None,
        'tags': {}
    }
    
    if hasattr(audio.info, 'bitrate'):
        metadata['bitrate'] = audio.info.bitrate
    if hasattr(audio.info, 'sample_rate'):
        metadata['sample_rate'] = audio.info.sample_rate
    if hasattr(audio.info, 'channels'):
        metadata['channels'] = audio.info.channels
    
    # Extract tags based on format
    if isinstance(audio, MP3) and audio.tags:
        tags = audio.tags
        if tags.get('TIT2'):
            metadata['tags']['title'] = str(tags['TIT2'])
        if tags.get('TALB'):
            metadata['tags']['album'] = str(tags['TALB'])
        if tags.get('TPE1'):
            metadata['tags']['artist'] = str(tags['TPE1'])
        if tags.get('TDRC'):
            metadata['tags']['year'] = str(tags['TDRC'])
        if tags.get('TCON'):
            metadata['tags']['genre'] = str(tags['TCON'])
        if tags.get('TRCK'):
            metadata['tags']['track'] = str(tags['TRCK'])
        if tags.get('TPE2'):
            metadata['tags']['album_artist'] = str(tags['TPE2'])
        if tags.get('COMM'):
            metadata['tags']['comment'] = str(tags['COMM'])
        if tags.get('APIC'):
            metadata['tags']['has_cover'] = True
    
    elif isinstance(audio, (FLAC, OggVorbis)) and audio.tags:
        tags = audio.tags
        for key in ['title', 'album', 'artist', 'date', 'genre', 'tracknumber', 
                    'albumartist', 'comment', 'composer', 'performer']:
            if key in tags:
                metadata['tags'][key] = tags[key][0] if tags[key] else None
        if tags.get('metadata_block_picture'):
            metadata['tags']['has_cover'] = True
    
    elif isinstance(audio, MP4):
        tags = audio.tags or {}
        tag_map = {
            '©nam': 'title', '©alb': 'album', '©ART': 'artist',
            'aART': 'album_artist', '©day': 'year', '©gen': 'genre',
            'trkn': 'track', '©wrt': 'composer', '©cmt': 'comment'
        }
        for mp4_key, meta_key in tag_map.items():
            if mp4_key in tags:
                value = tags[mp4_key]
                if isinstance(value, list) and len(value) > 0:
                    metadata['tags'][meta_key] = value[0]
                else:
                    metadata['tags'][meta_key] = value
        if 'covr' in tags:
            metadata['tags']['has_cover'] = True
    
    return metadata


def set_audio_metadata(filepath: str, tags: dict, cover_path: Optional[str] = None):
    """Set metadata tags on audio file."""
    try:
        import mutagen
        from mutagen.id3 import ID3, TIT2, TALB, TPE1, TDRC, TCON, APIC
        from mutagen.mp3 import MP3
        from mutagen.flac import FLAC
        from mutagen.oggvorbis import OggVorbis
        from mutagen.mp4 import MP4
    except ImportError:
        print("Error: mutagen not installed")
        sys.exit(1)
    
    audio = mutagen.File(filepath)
    if audio is None:
        print(f"Unsupported audio format: {filepath}")
        return False
    
    try:
        if isinstance(audio, MP3):
            if audio.tags is None:
                audio.add_tags()
            
            tags_obj = audio.tags
            if tags.get('title'):
                tags_obj['TIT2'] = TIT2(encoding=3, text=tags['title'])
            if tags.get('album'):
                tags_obj['TALB'] = TALB(encoding=3, text=tags['album'])
            if tags.get('artist'):
                tags_obj['TPE1'] = TPE1(encoding=3, text=tags['artist'])
            if tags.get('year'):
                tags_obj['TDRC'] = TDRC(encoding=3, text=tags['year'])
            if tags.get('genre'):
                tags_obj['TCON'] = TCON(encoding=3, text=tags['genre'])
            if tags.get('track'):
                tags_obj['TRCK'] = Travis(encoding=3, text=tags['track'])
            if tags.get('comment'):
                tags_obj['COMM'] = mutagen.id3.COMM(encoding=3, text=tags['comment'])
            
            if cover_path:
                with open(cover_path, 'rb') as f:
                    cover_data = f.read()
                tags_obj['APIC'] = APIC(
                    encoding=3, mime='image/jpeg', type=3, desc='Cover', data=cover_data
                )
            
            audio.save()
        
        elif isinstance(audio, (FLAC, OggVorbis)):
            if audio.tags is None:
                audio.add_tags()
            
            tags_obj = audio.tags
            if tags.get('title'):
                tags_obj['title'] = tags['title']
            if tags.get('album'):
                tags_obj['album'] = tags['album']
            if tags.get('artist'):
                tags_obj['artist'] = tags['artist']
            if tags.get('year'):
                tags_obj['date'] = tags['year']
            if tags.get('genre'):
                tags_obj['genre'] = tags['genre']
            if tags.get('track'):
                tags_obj['tracknumber'] = tags['track']
            if tags.get('comment'):
                tags_obj['comment'] = tags['comment']
            
            audio.save()
        
        elif isinstance(audio, MP4):
            if tags.get('title'):
                audio['©nam'] = [tags['title']]
            if tags.get('album'):
                audio['©alb'] = [tags['album']]
            if tags.get('artist'):
                audio['©ART'] = [tags['artist']]
            if tags.get('year'):
                audio['©day'] = [tags['year']]
            if tags.get('genre'):
                audio['©gen'] = [tags['genre']]
            if tags.get('track'):
                audio['trkn'] = [(int(tags['track']), 0)]
            if tags.get('comment'):
                audio['©cmt'] = [tags['comment']]
            
            if cover_path:
                with open(cover_path, 'rb') as f:
                    cover_data = f.read()
                audio['covr'] = [cover_data]
            
            audio.save()
        
        else:
            print(f"Editing not supported for format: {type(audio).__name__}")
            return False
        
        return True
    
    except Exception as e:
        print(f"Error setting metadata: {e}")
        return False


def display_metadata(filepath: str, json_output: bool = False):
    """Display metadata in formatted output."""
    metadata = get_audio_metadata(filepath)
    
    if not metadata:
        return
    
    if json_output:
        import json
        print(json.dumps(metadata, indent=2))
        return
    
    print(f"\nFile: {metadata['filepath']}")
    print(f"Format: {metadata['format']}")
    if metadata['duration']:
        mins = int(metadata['duration'] // 60)
        secs = int(metadata['duration'] % 60)
        print(f"Duration: {mins}:{secs:02d}")
    if metadata['bitrate']:
        print(f"Bitrate: {metadata['bitrate']} kbps")
    if metadata['sample_rate']:
        print(f"Sample Rate: {metadata['sample_rate']} Hz")
    if metadata['channels']:
        print(f"Channels: {metadata['channels']}")
    
    if metadata['tags']:
        print("\nTags:")
        for key, value in metadata['tags'].items():
            if key != 'has_cover':
                print(f"  {key}: {value}")
        if metadata['tags'].get('has_cover'):
            print("  Cover Art: Yes")


def main():
    parser = argparse.ArgumentParser(
        description='Audio File Metadata Editor & Tagger - Edit ID3 tags and metadata'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command')
    
    # Show command
    show_parser = subparsers.add_parser('show', help='Display audio file metadata')
    show_parser.add_argument('file', help='Audio file path')
    show_parser.add_argument('-j', '--json', action='store_true',
                            help='Output as JSON')
    
    # Set command
    set_parser = subparsers.add_parser('set', help='Set metadata tags')
    set_parser.add_argument('file', help='Audio file path')
    set_parser.add_argument('-t', '--title', help='Track title')
    set_parser.add_argument('-a', '--artist', help='Artist name')
    set_parser.add_argument('-A', '--album', help='Album name')
    set_parser.add_argument('-y', '--year', help='Release year')
    set_parser.add_argument('-g', '--genre', help='Genre')
    set_parser.add_argument('-T', '--track', help='Track number')
    set_parser.add_argument('-c', '--comment', help='Comment')
    set_parser.add_argument('-C', '--cover', help='Cover art image path')
    
    # Remove command
    remove_parser = subparsers.add_parser('remove', help='Remove all metadata')
    remove_parser.add_argument('file', help='Audio file path')
    remove_parser.add_argument('--confirm', action='store_true',
                              help='Confirm deletion without prompt')
    
    args = parser.parse_args()
    
    if not HAS_MUTAGEN:
        print("Error: mutagen not installed")
        print("Install with: pip install mutagen")
        sys.exit(1)
    
    if args.command == 'show':
        if not Path(args.file).exists():
            print(f"Error: File '{args.file}' not found")
            sys.exit(1)
        display_metadata(args.file, args.json)
        sys.exit(0)
    
    if args.command == 'set':
        if not Path(args.file).exists():
            print(f"Error: File '{args.file}' not found")
            sys.exit(1)
        
        tags = {}
        if args.title:
            tags['title'] = args.title
        if args.artist:
            tags['artist'] = args.artist
        if args.album:
            tags['album'] = args.album
        if args.year:
            tags['year'] = args.year
        if args.genre:
            tags['genre'] = args.genre
        if args.track:
            tags['track'] = args.track
        if args.comment:
            tags['comment'] = args.comment
        
        if not tags and not args.cover:
            print("Error: No tags or cover art specified")
            sys.exit(1)
        
        cover_path = args.cover if args.cover else None
        if cover_path and not Path(cover_path).exists():
            print(f"Error: Cover art file '{cover_path}' not found")
            sys.exit(1)
        
        if set_audio_metadata(args.file, tags, cover_path):
            print(f"Metadata updated for: {args.file}")
            display_metadata(args.file)
            sys.exit(0)
        else:
            sys.exit(1)
    
    if args.command == 'remove':
        print("Error: Remove command not yet implemented")
        sys.exit(1)
    
    parser.print_help()
    sys.exit(1)


if __name__ == '__main__':
    main()