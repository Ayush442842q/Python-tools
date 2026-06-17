#!/usr/bin/env python3
"""
word_frequency_analyzer - Text frequency analysis and terminal tag cloud generator

Analyzes a text file or standard input for word frequencies, calculates text metrics
(readability, average lengths, sentence counts), filters stop words, and displays
colored terminal frequency charts and a word tag cloud.

Usage:
    python tools/word_frequency_analyzer.py [FILE] [-n TOP_N] [--exclude-stops] [--no-chart]

Options:
    FILE                File to analyze (reads from standard input if omitted)
    -n, --top           Number of top words to show (default: 15)
    --no-stops          Exclude common English stop words (default: True)
    --custom-stops      Path to a file containing custom stop words (one per line)
    --include-numbers   Include numbers as words in frequency analysis
    --min-len           Minimum word length to count (default: 2)
    --no-cloud          Disable word tag cloud rendering

Example:
    python tools/word_frequency_analyzer.py README.md -n 10
"""

import os
import re
import sys
import string
import argparse
from collections import Counter

# Terminal ANSI colors
COLOR_CYAN = "\033[96m"
COLOR_GREEN = "\033[92m"
COLOR_YELLOW = "\033[93m"
COLOR_MAGENTA = "\033[95m"
COLOR_BLUE = "\033[94m"
COLOR_RED = "\033[91m"
COLOR_BOLD = "\033[1m"
COLOR_UNDERLINE = "\033[4m"
COLOR_END = "\033[0m"

# Default English stop words
DEFAULT_STOP_WORDS = {
    'a', 'about', 'above', 'after', 'again', 'against', 'all', 'am', 'an', 'and', 'any', 'are', 'arent',
    'as', 'at', 'be', 'because', 'been', 'before', 'being', 'below', 'between', 'both', 'but', 'by',
    'cant', 'cannot', 'could', 'couldnt', 'did', 'didnt', 'do', 'does', 'doesnt', 'doing', 'dont',
    'down', 'during', 'each', 'few', 'for', 'from', 'further', 'had', 'hadnt', 'has', 'hasnt', 'have',
    'havent', 'having', 'he', 'hed', 'hell', 'hes', 'her', 'here', 'heres', 'hers', 'herself', 'him',
    'himself', 'his', 'how', 'hows', 'i', 'id', 'ill', 'im', 'ive', 'if', 'in', 'into', 'is', 'isnt',
    'it', 'its', 'itself', 'lets', 'me', 'more', 'most', 'mustnt', 'my', 'myself', 'no', 'nor', 'not',
    'of', 'off', 'on', 'once', 'only', 'or', 'other', 'ought', 'our', 'ours', 'ourselves', 'out', 'over',
    'own', 'same', 'shant', 'she', 'shed', 'shell', 'shes', 'should', 'shouldnt', 'so', 'some', 'such',
    'than', 'that', 'thats', 'the', 'their', 'theirs', 'them', 'themselves', 'then', 'there', 'theres',
    'these', 'they', 'theyd', 'theyll', 'theyre', 'theyve', 'this', 'those', 'through', 'to', 'too',
    'under', 'until', 'up', 'very', 'was', 'wasnt', 'we', 'wed', 'well', 'were', 'weve', 'werent',
    'what', 'whats', 'when', 'whens', 'where', 'wheres', 'which', 'while', 'who', 'whos', 'whom',
    'why', 'whys', 'with', 'wont', 'would', 'wouldnt', 'you', 'youd', 'youll', 'youre', 'youve',
    'your', 'yours', 'yourself', 'yourselves'
}

def clean_text(text):
    """Normalize text and remove punctuation/special characters."""
    # Convert smart quotes to regular quotes
    text = text.replace('‘', "'").replace('’', "'").replace('“', '"').replace('”', '"')
    return text

def calculate_metrics(text):
    """Calculate basic text readability and count statistics."""
    # Sentence count: look for sentence ending marks followed by space/newline
    sentences = re.split(r'[.!?]+(?:\s+|\n|$)', text)
    sentences = [s for s in sentences if s.strip()]
    sentence_count = max(len(sentences), 1)

    # Word splitting for metrics
    words = re.findall(r'\b\w+\b', text)
    word_count = len(words)
    
    # Syllables count approximation (vowel groups)
    syllable_count = 0
    for word in words:
        word = word.lower()
        # count vowel groups
        vowels = "aeiouy"
        count = 0
        if not word:
            continue
        if word[0] in vowels:
            count += 1
        for index in range(1, len(word)):
            if word[index] in vowels and word[index - 1] not in vowels:
                count += 1
        if word.endswith("e"):
            count -= 1
        if count == 0:
            count = 1
        syllable_count += count

    char_count_no_spaces = sum(len(w) for w in words)
    avg_word_len = char_count_no_spaces / max(word_count, 1)
    avg_sentence_len = word_count / sentence_count

    # Flesch Reading Ease Formula
    # 206.835 - 1.015 * (total words / total sentences) - 84.6 * (total syllables / total words)
    if word_count > 0:
        ease_score = 206.835 - (1.015 * avg_sentence_len) - (84.6 * (syllable_count / word_count))
        # Flesch-Kincaid Grade Level
        # 0.39 * (total words / total sentences) + 11.8 * (total syllables / total words) - 15.59
        grade_level = (0.39 * avg_sentence_len) + (11.8 * (syllable_count / word_count)) - 15.59
    else:
        ease_score = 0
        grade_level = 0

    return {
        "sentences": sentence_count,
        "words": word_count,
        "chars": char_count_no_spaces,
        "avg_word_len": avg_word_len,
        "avg_sentence_len": avg_sentence_len,
        "flesch_ease": ease_score,
        "flesch_grade": grade_level
    }

def draw_bar_chart(frequencies, max_width=45):
    """Draw a horizontal Unicode bar chart for word frequencies."""
    if not frequencies:
        return
    
    max_count = frequencies[0][1]
    # Check encoding support for Unicode blocks
    encoding = sys.stdout.encoding or 'ascii'
    try:
        "█░".encode(encoding)
        fill_char, empty_char = "█", "░"
    except Exception:
        fill_char, empty_char = "#", "-"

    max_word_len = max(len(word) for word, _ in frequencies)
    
    print(f"\n{COLOR_BOLD}{COLOR_UNDERLINE}Word Frequencies Chart{COLOR_END}")
    for word, count in frequencies:
        # Calculate proportional bar width
        bar_len = int((count / max_count) * max_width) if max_count > 0 else 0
        bar = fill_char * bar_len + empty_char * (max_width - bar_len)
        
        # Color bar based on size
        if bar_len > (max_width * 0.7):
            bar_color = COLOR_GREEN
        elif bar_len > (max_width * 0.4):
            bar_color = COLOR_CYAN
        else:
            bar_color = COLOR_BLUE
            
        padding = " " * (max_word_len - len(word))
        print(f"  {COLOR_BOLD}{word}{COLOR_END}{padding} | {bar_color}{bar}{COLOR_END} | {count}")

def draw_tag_cloud(frequencies):
    """Renders a colorful terminal word cloud."""
    if not frequencies:
        return
    
    # Shuffle words so they aren't strictly sorted by size in the cloud
    import random
    words_cloud = list(frequencies)
    random.seed(42)  # Consistent layout
    random.shuffle(words_cloud)
    
    # Determine frequency tiers
    counts = [c for _, c in frequencies]
    max_c = max(counts) if counts else 1
    min_c = min(counts) if counts else 1
    span = max(max_c - min_c, 1)

    print(f"\n{COLOR_BOLD}{COLOR_UNDERLINE}Terminal Word Tag Cloud{COLOR_END}\n")
    cloud_elements = []
    
    for word, count in words_cloud:
        # Determine weight tier (0-4)
        tier = int(((count - min_c) / span) * 4) if span > 0 else 0
        
        # Color and style based on weight
        if tier == 4:
            styled = f"{COLOR_BOLD}{COLOR_RED}{word}{COLOR_END}"
        elif tier == 3:
            styled = f"{COLOR_BOLD}{COLOR_YELLOW}{word}{COLOR_END}"
        elif tier == 2:
            styled = f"{COLOR_GREEN}{word}{COLOR_END}"
        elif tier == 1:
            styled = f"{COLOR_CYAN}{word}{COLOR_END}"
        else:
            styled = f"{COLOR_BLUE}{word}{COLOR_END}"
            
        cloud_elements.append(styled)

    # Print elements in a nice block wrapping at window width (approx 80 chars)
    line = "  "
    for item in cloud_elements:
        # Calculate raw length of item without ANSI codes
        raw_len = len(re.sub(r'\033\[[0-9;]*m', '', item))
        if len(line) + raw_len + 3 > 80:
            print(line)
            line = "  " + item + "   "
        else:
            line += item + "   "
    if line.strip():
        print(line)
    print()

def main():
    parser = argparse.ArgumentParser(description="Analyze word frequencies, text statistics, and draw colorful terminal tag clouds.")
    parser.add_argument('file', nargs='?', help='Path to the text file (reads from stdin if omitted)')
    parser.add_argument('-n', '--top', type=int, default=15, help='Number of top words to report')
    parser.add_argument('--no-stops', action='store_true', help='Do NOT filter common English stop words')
    parser.add_argument('--custom-stops', type=str, help='Path to file containing custom stop words (one per line)')
    parser.add_argument('--include-numbers', action='store_true', help='Include numbers/digits as words')
    parser.add_argument('--min-len', type=int, default=2, help='Minimum character length of a word to be processed')
    parser.add_argument('--no-cloud', action='store_true', help='Do not display the word cloud')
    
    args = parser.parse_args()

    # Read input text
    if args.file:
        if not os.path.exists(args.file):
            print(f"{COLOR_RED}Error: File '{args.file}' not found.{COLOR_END}", file=sys.stderr)
            return 1
        try:
            with open(args.file, 'r', encoding='utf-8', errors='ignore') as f:
                raw_text = f.read()
        except Exception as e:
            print(f"{COLOR_RED}Error reading file: {e}{COLOR_END}", file=sys.stderr)
            return 1
    else:
        # Read from stdin
        if sys.stdin.isatty():
            print(f"{COLOR_YELLOW}Reading from standard input (Ctrl+D to finish)...{COLOR_END}")
        raw_text = sys.stdin.read()

    if not raw_text.strip():
        print(f"{COLOR_YELLOW}Warning: Input is empty.{COLOR_END}")
        return 0

    clean_raw = clean_text(raw_text)
    metrics = calculate_metrics(clean_raw)

    # Process stop words
    stops = set()
    if not args.no_stops:
        stops = set(DEFAULT_STOP_WORDS)

    if args.custom_stops:
        if os.path.exists(args.custom_stops):
            try:
                with open(args.custom_stops, 'r', encoding='utf-8') as f:
                    custom = [line.strip().lower() for line in f if line.strip()]
                    stops.update(custom)
            except Exception as e:
                print(f"{COLOR_YELLOW}Warning: Could not read custom stop words file: {e}{COLOR_END}", file=sys.stderr)
        else:
            print(f"{COLOR_YELLOW}Warning: Custom stop words file not found at: {args.custom_stops}{COLOR_END}", file=sys.stderr)

    # Extract words for frequency list
    # Match words depending on if we include numbers
    word_pattern = r'\b[a-zA-Z0-9_\-\']+\b' if args.include_numbers else r'\b[a-zA-Z\']+\b'
    all_words = re.findall(word_pattern, clean_raw)

    filtered_words = []
    for word in all_words:
        # Normalize: strip quotes, make lowercase
        word_clean = word.strip("'").lower()
        if len(word_clean) < args.min_len:
            continue
        if word_clean in stops:
            continue
        if not args.include_numbers and word_clean.isdigit():
            continue
        filtered_words.append(word_clean)

    # Calculate frequencies
    counter = Counter(filtered_words)
    top_frequencies = counter.most_common(args.top)

    # Display results
    print(f"\n{COLOR_GREEN}{COLOR_BOLD}=== Text Analysis Summary ==={COLOR_END}")
    print(f"  Total Characters (excl. space): {COLOR_CYAN}{metrics['chars']}{COLOR_END}")
    print(f"  Total Words:                    {COLOR_CYAN}{metrics['words']}{COLOR_END}")
    print(f"  Unique Words (filtered):        {COLOR_CYAN}{len(counter)}{COLOR_END}")
    print(f"  Total Sentences:                {COLOR_CYAN}{metrics['sentences']}{COLOR_END}")
    print(f"  Average Sentence Length:        {COLOR_CYAN}{metrics['avg_sentence_len']:.1f} words{COLOR_END}")
    print(f"  Average Word Length:            {COLOR_CYAN}{metrics['avg_word_len']:.1f} characters{COLOR_END}")
    
    # Format Flesch Reading Ease
    ease = metrics['flesch_ease']
    if ease >= 90:
        ease_desc = "Very Easy (5th grade level)"
    elif ease >= 80:
        ease_desc = "Easy (6th grade level)"
    elif ease >= 70:
        ease_desc = "Fairly Easy (7th grade level)"
    elif ease >= 60:
        ease_desc = "Standard (8th-9th grade level)"
    elif ease >= 50:
        ease_desc = "Fairly Difficult (High School)"
    elif ease >= 30:
        ease_desc = "Difficult (College level)"
    else:
        ease_desc = "Very Difficult (College Graduate)"
        
    print(f"  Flesch Reading Ease:            {COLOR_CYAN}{ease:.1f} ({ease_desc}){COLOR_END}")
    print(f"  Flesch-Kincaid Grade Level:     {COLOR_CYAN}{max(metrics['flesch_grade'], 0.0):.1f}{COLOR_END}")

    if not top_frequencies:
        print(f"\n{COLOR_YELLOW}No words found matching the filter criteria.{COLOR_END}")
        return 0

    # Draw frequency chart
    draw_bar_chart(top_frequencies)

    # Draw word cloud
    if not args.no_cloud:
        draw_tag_cloud(top_frequencies)

    return 0

if __name__ == "__main__":
    sys.exit(main())
