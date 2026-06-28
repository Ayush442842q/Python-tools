#!/usr/bin/env python3
"""
Calendar Event Parser & ICS Generator
Parse event descriptions and generate ICS calendar files.
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
import hashlib
import uuid
from typing import List, Dict, Optional, Tuple


def parse_date_string(date_str: str) -> Optional[datetime]:
    """Parse various date string formats."""
    formats = [
        '%Y-%m-%d',           # 2024-01-15
        '%Y/%m/%d',           # 2024/01/15
        '%d-%m-%Y',           # 15-01-2024
        '%d/%m/%Y',           # 15/01/2024
        '%m-%d-%Y',           # 01-15-2024
        '%m/%d/%Y',           # 01/15/2024
        '%B %d, %Y',          # January 15, 2024
        '%b %d, %Y',          # Jan 15, 2024
        '%d %B %Y',           # 15 January 2024
        '%d %b %Y',           # 15 Jan 2024
        '%Y-%m-%d %H:%M',     # 2024-01-15 09:30
        '%Y-%m-%dT%H:%M',     # 2024-01-15T09:30
        '%Y-%m-%dT%H:%M:%S',  # 2024-01-15T09:30:00
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    return None


def parse_time_string(time_str: str) -> Optional[datetime]:
    """Parse time string."""
    formats = [
        '%H:%M',              # 09:30
        '%H:%M:%S',           # 09:30:00
        '%I:%M %p',           # 09:30 AM
        '%I:%M:%S %p',        # 09:30:00 AM
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(time_str, fmt)
        except ValueError:
            continue
    
    return None


def create_event_uid() -> str:
    """Generate unique event ID."""
    return str(uuid.uuid4())


def format_datetime(dt: datetime, all_day: bool = False) -> str:
    """Format datetime for ICS format."""
    if all_day:
        return dt.strftime('%Y%m%d')
    else:
        return dt.strftime('%Y%m%dT%H%M%S')


def escape_text(text: str) -> str:
    """Escape special characters for ICS format."""
    if not text:
        return ''
    text = text.replace('\\', '\\\\')
    text = text.replace(';', '\\;')
    text = text.replace(',', '\\,')
    text = text.replace('\n', '\\n')
    return text


class CalendarEvent:
    """Represents a calendar event."""
    
    def __init__(self):
        self.uid: str = create_event_uid()
        self.summary: str = ''
        self.description: str = ''
        self.location: str = ''
        self.start: Optional[datetime] = None
        self.end: Optional[datetime] = None
        self.all_day: bool = False
        self.organizer: str = ''
        self.attendees: List[str] = []
        self.categories: List[str] = []
        self.url: str = ''
        self.created: datetime = datetime.now()
        self.last_modified: datetime = datetime.now()
    
    def to_ics(self) -> str:
        """Convert event to ICS VEVENT format."""
        lines = []
        lines.append('BEGIN:VEVENT')
        lines.append(f'UID:{self.uid}')
        lines.append(f'DTSTAMP:{format_datetime(datetime.now())}')
        lines.append(f'DTSTART:{format_datetime(self.start, self.all_day)}')
        
        if self.end:
            lines.append(f'DTEND:{format_datetime(self.end, self.all_day)}')
        
        if self.summary:
            lines.append(f'SUMMARY:{escape_text(self.summary)}')
        
        if self.description:
            lines.append(f'DESCRIPTION:{escape_text(self.description)}')
        
        if self.location:
            lines.append(f'LOCATION:{escape_text(self.location)}')
        
        if self.organizer:
            lines.append(f'ORGANIZER;CN={escape_text(self.organizer)}:mailto:{self.organizer}')
        
        for attendee in self.attendees:
            lines.append(f'ATTENDEE;CN={escape_text(attendee)}:mailto:{attendee}')
        
        for category in self.categories:
            lines.append(f'CATEGORIES:{escape_text(category)}')
        
        if self.url:
            lines.append(f'URL:{escape_text(self.url)}')
        
        lines.append(f'CREATED:{format_datetime(self.created)}')
        lines.append(f'LAST-MODIFIED:{format_datetime(self.last_modified)}')
        lines.append('END:VEVENT')
        
        return '\r\n'.join(lines)


class ICSGenerator:
    """Generate ICS calendar files."""
    
    def __init__(self, name: str = 'My Calendar', description: str = ''):
        self.name = name
        self.description = description
        self.events: List[CalendarEvent] = []
    
    def add_event(self, event: CalendarEvent):
        """Add event to calendar."""
        self.events.append(event)
    
    def to_ics(self) -> str:
        """Generate complete ICS content."""
        lines = []
        lines.append('BEGIN:VCALENDAR')
        lines.append('VERSION:2.0')
        lines.append('PRODID:-//Python Tools Collection//Calendar Generator//EN')
        lines.append('CALSCALE:GREGORIAN')
        lines.append('METHOD:PUBLISH')
        
        if self.name:
            lines.append(f'X-WR-CALNAME:{escape_text(self.name)}')
        
        if self.description:
            lines.append(f'X-WR-CALDESC:{escape_text(self.description)}')
        
        for event in self.events:
            lines.append(event.to_ics())
        
        lines.append('END:VCALENDAR')
        
        return '\r\n'.join(lines)
    
    def save(self, filepath: str):
        """Save calendar to file."""
        content = self.to_ics()
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        return filepath


def parse_event_text(text: str) -> CalendarEvent:
    """Parse event details from text description."""
    event = CalendarEvent()
    
    lines = text.split('\n')
    current_field = None
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
        
        lower_line = line.lower()
        
        # Check for field markers
        if lower_line.startswith('title:') or lower_line.startswith('summary:'):
            event.summary = line.split(':', 1)[1].strip()
            current_field = 'summary'
        elif lower_line.startswith('description:'):
            event.description = line.split(':', 1)[1].strip()
            current_field = 'description'
        elif lower_line.startswith('location:'):
            event.location = line.split(':', 1)[1].strip()
            current_field = 'location'
        elif lower_line.startswith('start:') or lower_line.startswith('date:'):
            date_part = line.split(':', 1)[1].strip()
            event.start = parse_date_string(date_part)
            if event.start and not event.all_day:
                event.start = event.start.replace(hour=9, minute=0)
            current_field = 'start'
        elif lower_line.startswith('end:'):
            date_part = line.split(':', 1)[1].strip()
            event.end = parse_date_string(date_part)
            current_field = 'end'
        elif lower_line.startswith('time:'):
            time_part = line.split(':', 1)[1].strip()
            event.all_day = False
            parsed_time = parse_time_string(time_part)
            if parsed_time and event.start:
                event.start = event.start.replace(
                    hour=parsed_time.hour, 
                    minute=parsed_time.minute,
                    second=parsed_time.second
                )
        elif lower_line.startswith('duration:'):
            duration_str = line.split(':', 1)[1].strip().lower()
            if event.start:
                hours = 0
                minutes = 0
                if 'hour' in duration_str:
                    hours = int(duration_str.split('hour')[0].strip())
                if 'min' in duration_str:
                    minutes = int(duration_str.split('min')[0].strip())
                event.end = event.start + timedelta(hours=hours, minutes=minutes)
        elif lower_line.startswith('url:'):
            event.url = line.split(':', 1)[1].strip()
        elif lower_line.startswith('organizer:'):
            event.organizer = line.split(':', 1)[1].strip()
        elif line.startswith('-') or line.startswith('•'):
            # Attendee list item
            attendee = line.lstrip('-•').strip()
            if attendee and '@' in attendee:
                event.attendees.append(attendee)
        elif ',' in line and not current_field:
            # Might be categories
            event.categories.extend([c.strip() for c in line.split(',')])
        else:
            # Append to description if no specific field
            if current_field == 'description':
                event.description += '\n' + line
            elif event.description:
                event.description += '\n' + line
            else:
                event.summary += ' ' + line if event.summary else line
    
    return event


def create_recurring_events(event: CalendarEvent, recurrence: str, 
                           count: Optional[int] = None,
                           until: Optional[datetime] = None) -> List[CalendarEvent]:
    """Create recurring events from base event."""
    events = []
    
    if not event.start:
        return events
    
    rec_type = recurrence.upper()
    
    if rec_type == 'DAILY':
        delta = timedelta(days=1)
    elif rec_type == 'WEEKLY':
        delta = timedelta(weeks=1)
    elif rec_type == 'MONTHLY':
        delta = timedelta(days=30)  # Approximate
    elif rec_type == 'YEARLY':
        delta = timedelta(days=365)
    else:
        return [event]
    
    if count:
        for i in range(count):
            new_event = CalendarEvent()
            new_event.uid = create_event_uid()
            new_event.summary = event.summary
            new_event.description = event.description
            new_event.location = event.location
            new_event.start = event.start + (delta * i)
            if event.end:
                duration = event.end - event.start
                new_event.end = new_event.start + duration
            events.append(new_event)
    
    return events


def main():
    parser = argparse.ArgumentParser(
        description='Calendar Event Parser & ICS Generator - Create calendar events and ICS files'
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command')
    
    # Create event command
    create_parser = subparsers.add_parser('create', help='Create single event')
    create_parser.add_argument('-t', '--title', required=True, help='Event title/summary')
    create_parser.add_argument('-d', '--date', required=True, help='Event date (YYYY-MM-DD)')
    create_parser.add_argument('--start-time', help='Start time (HH:MM or HH:MM AM/PM)')
    create_parser.add_argument('--end-time', help='End time (HH:MM or HH:MM AM/PM)')
    create_parser.add_argument('--duration', help='Duration (e.g., "2 hours", "90 minutes")')
    create_parser.add_argument('-l', '--location', help='Event location')
    create_parser.add_argument('-D', '--description', help='Event description')
    create_parser.add_argument('-o', '--organizer', help='Organizer name/email')
    create_parser.add_argument('-c', '--category', action='append', help='Categories')
    create_parser.add_argument('--url', help='Event URL')
    create_parser.add_argument('-O', '--output', default='event.ics', help='Output file')
    
    # Parse text command
    parse_parser = subparsers.add_parser('parse', help='Parse event from text')
    parse_parser.add_argument('text', nargs='?', help='Event description text')
    parse_parser.add_argument('-f', '--file', help='Read text from file')
    parse_parser.add_argument('-O', '--output', default='event.ics', help='Output file')
    
    # Template command
    subparsers.add_parser('template', help='Show event template')
    
    # Demo command
    subparsers.add_parser('demo', help='Generate demo calendar with sample events')
    
    args = parser.parse_args()
    
    if args.command == 'template':
        template = """
Event Template
==============

Copy and customize this template:

```
Title: Team Meeting
Date: 2024-06-15
Time: 09:00 AM
Duration: 1 hour
Location: Conference Room A
Description: Weekly team sync
Organizer: john@example.com
Categories: Work, Meeting
URL: https://meet.example.com/123
Attendees:
- alice@example.com
- bob@example.com
```

Supported date formats:
- YYYY-MM-DD
- YYYY/MM/DD
- DD-MM-YYYY
- DD/MM/YYYY
- MM-DD-YYYY
- Month DD, YYYY
- DD Month YYYY

Supported time formats:
- HH:MM (24-hour)
- HH:MM:SS
- HH:MM AM/PM
- HH:MM:SS AM/PM
"""
        print(template)
        sys.exit(0)
    
    if args.command == 'demo':
        calendar = ICSGenerator(name='Demo Calendar', description='Sample events')
        
        # Sample event 1
        event1 = CalendarEvent()
        event1.summary = 'Team Standup'
        event1.description = 'Daily team sync meeting'
        event1.location = 'Conference Room A'
        event1.start = datetime(2024, 6, 15, 9, 0)
        event1.end = datetime(2024, 6, 15, 9, 30)
        event1.organizer = 'team@example.com'
        event1.categories = ['Work', 'Meeting']
        calendar.add_event(event1)
        
        # Sample event 2
        event2 = CalendarEvent()
        event2.summary = 'Project Review'
        event2.description = 'Quarterly project review with stakeholders'
        event2.location = 'Main Office'
        event2.start = datetime(2024, 6, 20, 14, 0)
        event2.end = datetime(2024, 6, 20, 16, 0)
        event2.organizer = 'pm@example.com'
        event2.categories = ['Work', 'Review']
        calendar.add_event(event2)
        
        # Sample event 3
        event3 = CalendarEvent()
        event3.summary = 'Lunch with Client'
        event3.description = 'Business lunch discussion'
        event3.location = 'Restaurant XYZ, 123 Main St'
        event3.start = datetime(2024, 6, 25, 12, 0)
        event3.end = datetime(2024, 6, 25, 13, 30)
        event3.organizer = 'sales@example.com'
        event3.categories = ['Business', 'Lunch']
        calendar.add_event(event3)
        
        # Sample all-day event
        event4 = CalendarEvent()
        event4.summary = 'Company Holiday'
        event4.description = 'Office closed for holiday'
        event4.all_day = True
        event4.start = datetime(2024, 7, 4)
        event4.end = datetime(2024, 7, 5)
        event4.categories = ['Holiday']
        calendar.add_event(event4)
        
        output_file = calendar.save('demo_calendar.ics')
        print(f"Demo calendar created: {output_file}")
        print(f"Contains {len(calendar.events)} sample events")
        sys.exit(0)
    
    if args.command == 'create':
        event = CalendarEvent()
        event.summary = args.title
        
        event.start = parse_date_string(args.date)
        if not event.start:
            print(f"Error: Could not parse date '{args.date}'")
            sys.exit(1)
        
        # Set default start time if not all day
        if not args.start_time:
            event.start = event.start.replace(hour=9, minute=0)
        
        if args.start_time:
            parsed_time = parse_time_string(args.start_time)
            if parsed_time:
                event.start = event.start.replace(
                    hour=parsed_time.hour,
                    minute=parsed_time.minute
                )
        
        if args.end_time:
            parsed_end = parse_time_string(args.end_time)
            if parsed_end:
                event.end = event.start.replace(
                    hour=parsed_end.hour,
                    minute=parsed_end.minute
                )
        
        if args.duration and not event.end:
            duration_str = args.duration.lower()
            hours = 0
            minutes = 0
            if 'hour' in duration_str:
                hours = int(duration_str.split('hour')[0].strip())
            if 'min' in duration_str:
                minutes = int(duration_str.split('min')[0].strip())
            event.end = event.start + timedelta(hours=hours, minutes=minutes)
        
        if event.end and event.end < event.start:
            event.end = event.end.replace(day=event.start.day + 1)
        
        if args.location:
            event.location = args.location
        if args.description:
            event.description = args.description
        if args.organizer:
            event.organizer = args.organizer
        if args.category:
            event.categories = args.category
        if args.url:
            event.url = args.url
        
        calendar = ICSGenerator()
        calendar.add_event(event)
        
        output_file = calendar.save(args.output)
        print(f"Event created: {args.output}")
        print(f"\nEvent Details:")
        print(f"  Title: {event.summary}")
        print(f"  Date: {event.start.strftime('%Y-%m-%d')}")
        print(f"  Time: {event.start.strftime('%H:%M')}")
        if event.end:
            print(f"  End: {event.end.strftime('%H:%M')}")
        if event.location:
            print(f"  Location: {event.location}")
        
        sys.exit(0)
    
    if args.command == 'parse':
        if args.file:
            if not Path(args.file).exists():
                print(f"Error: File '{args.file}' not found")
                sys.exit(1)
            with open(args.file, 'r') as f:
                text = f.read()
        elif args.text:
            text = args.text
        else:
            print("Error: Provide text or file with -f option")
            sys.exit(1)
        
        event = parse_event_text(text)
        
        calendar = ICSGenerator()
        calendar.add_event(event)
        
        output_file = calendar.save(args.output)
        print(f"Event parsed and saved: {args.output}")
        if event.summary:
            print(f"  Title: {event.summary}")
        if event.start:
            print(f"  Date: {event.start.strftime('%Y-%m-%d %H:%M')}")
        
        sys.exit(0)
    
    parser.print_help()
    sys.exit(1)


if __name__ == '__main__':
    main()