#!/usr/bin/env python3
"""
File Watcher - Monitor directory changes and trigger actions.

This script watches a directory for file changes (create, modify, delete)
and can execute commands or scripts when changes occur.
"""

import os
import sys
import time
import argparse
import subprocess
from pathlib import Path
from typing import List, Callable, Optional

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    WATCHDOG_AVAILABLE = True
except ImportError:
    WATCHDOG_AVAILABLE = False


class ChangeHandler(FileSystemEventHandler):
    """Handle file system events."""
    
    def __init__(self, command: str = None, callback: Callable = None):
        self.command = command
        self.callback = callback
        super().__init__()
    
    def on_any_event(self, event):
        if self.callback:
            self.callback(event)
        elif self.command:
            try:
                subprocess.run(self.command, shell=True, check=False)
            except Exception:
                pass


def watch_directory(
    directory: Path,
    command: str = None,
    callback: Callable = None,
    recursive: bool = False,
) -> None:
    """
    Watch a directory for changes.
    
    Args:
        directory: Directory to watch
        command: Command to run on changes
        callback: Callback function to execute on changes
        recursive: Whether to watch subdirectories
    """
    if not WATCHDOG_AVAILABLE:
        print("Error: watchdog package not installed. Install with: pip install watchdog", file=sys.stderr)
        sys.exit(1)
    
    if not directory.exists():
        print(f"Error: Directory '{directory}' does not exist.", file=sys.stderr)
        sys.exit(1)
    
    event_handler = ChangeHandler(command, callback)
    observer = Observer()
    observer.schedule(event_handler, str(directory), recursive=recursive)
    
    print(f"Watching {'recursively ' if recursive else ''}directory: {directory}")
    if command:
        print(f"Triggering command: {command}")
    print("Press Ctrl+C to stop...")
    
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        print("\nStopped watching.")
    
    observer.join()


def main():
    """Main entry point for the file watcher."""
    parser = argparse.ArgumentParser(
        description="Monitor directory changes and trigger actions",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s /path/to/watch --command "echo 'File changed'"
  %(prog)s ~/Documents -r --command "rsync -avz . backup/"
  %(prog)s /var/log --command "systemctl restart rsyslog"
        """
    )
    
    parser.add_argument(
        'directory',
        type=str,
        help='Directory to watch'
    )
    
    parser.add_argument(
        '-r', '--recursive',
        action='store_true',
        help='Watch subdirectories recursively'
    )
    
    parser.add_argument(
        '-c', '--command',
        type=str,
        help='Command to execute when changes are detected'
    )
    
    parser.add_argument(
        '--callback',
        type=str,
        help='Python callback function (not implemented in CLI version)'
    )
    
    args = parser.parse_args()
    
    if not args.command and not args.callback:
        print("Error: Either --command or --callback must be specified", file=sys.stderr)
        sys.exit(1)
    
    directory = Path(args.directory).expanduser().resolve()
    
    watch_directory(
        directory=directory,
        command=args.command,
        recursive=args.recursive,
    )


if __name__ == '__main__':
    main()