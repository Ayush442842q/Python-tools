#!/usr/bin/env python3
"""
Extractive Text Summarizer - Generate concise summaries and text analytics.

This tool scores and extracts key sentences from documents based on term frequency
analysis (TF-IDF approximation), automatically filtering stop words. It reports
compression ratios, reading statistics, and keyword extractions.
"""

import sys
import os
import re
import argparse
from collections import Counter

# ANSI Colors
COLORS = {
    'green': '\033[32m',
    'yellow': '\033[33m',
    'blue': '\033[34m',
    'cyan': '\033[36m',
    'bold': '\033[1m',
    'reset': '\033[0m'
}

# Simple list of English stop words
STOP_WORDS = set([
    'a', 'about', 'above', 'after', 'again', 'against', 'all', 'am', 'an', 'and', 'any', 'are', 'arent',
    'as', 'at', 'be', 'because', 'been', 'before', 'being', 'below', 'between', 'both', 'but', 'by',
    'cant', 'cannot', 'could', 'couldnt', 'did', 'didnt', 'do', 'does', 'doesnt', 'doing', 'dont', 'down',
    'during', 'each', 'few', 'for', 'from', 'further', 'had', 'hadnt', 'has', 'hasnt', 'have', 'havent',
    'having', 'he', 'hed', 'hell', 'hes', 'her', 'here', 'heres', 'hers', 'herself', 'him', 'himself',
    'his', 'how', 'hows', 'i', 'id', 'ive', 'im', 'if', 'in', 'into', 'is', 'isnt', 'it', 'its', 'itself',
    'lets', 'me', 'more', 'most', 'mustnt', 'my', 'myself', 'no', 'nor', 'not', 'of', 'off', 'on', 'once',
    'only', 'or', 'other', 'ought', 'our', 'ours', 'ourselves', 'out', 'over', 'own', 'same', 'shant',
    'she', 'shed', 'shell', 'shes', 'should', 'shouldnt', 'so', 'some', 'such', 'than', 'that', 'thats',
    'the', 'their', 'theirs', 'them', 'themselves', 'then', 'there', 'theres', 'these', 'they', 'theyd',
    'theyll', 'theyre', 'theyve', 'this', 'those', 'through', 'to', 'too', 'under', 'until', 'up', 'very',
    'was', 'wasnt', 'we', 'wed', 'well', 'were', 'weve', 'werent', 'what', 'whats', 'when', 'whens',
    'where', 'wheres', 'which', 'while', 'who', 'whos', 'whom', 'why', 'whys', 'with', 'wont', 'would',
    'wouldnt', 'you', 'youd', 'youll', 'youre', 'youve', 'your', 'yours', 'yourself', 'yourselves'
])

def colorize(text, color):
    """Colorize text with ANSI codes if supported"""
    if color in COLORS:
        return f"{COLORS[color]}{text}{COLORS['reset']}"
    return text

def clean_word(word):
    """Normalize word to lowercase and strip non-alphabetic chars"""
    return re.sub(r'[^a-z]', '', word.lower())

def split_into_sentences(text):
    """Split text into sentences using simple regex boundaries"""
    # Handles periods, question marks, and exclamation marks, avoiding decimals
    sentence_end = re.compile(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|\!)\s')
    sentences = sentence_end.split(text)
    return [s.strip() for s in sentences if s.strip()]

def get_word_frequencies(sentences):
    """Tokenize words and calculate frequency counts excluding stop words"""
    words = []
    for s in sentences:
        for word in s.split():
            cleaned = clean_word(word)
            if cleaned and cleaned not in STOP_WORDS:
                words.append(cleaned)
    return Counter(words)

def score_sentences(sentences, word_freqs):
    """Score each sentence based on sum of normalised word frequencies"""
    scores = {}
    max_freq = max(word_freqs.values()) if word_freqs else 1
    
    for i, sentence in enumerate(sentences):
        score = 0
        words = sentence.split()
        word_count = 0
        
        for word in words:
            cleaned = clean_word(word)
            if cleaned in word_freqs:
                # Normalise word frequency (similar to TF score)
                score += word_freqs[cleaned] / max_freq
                word_count += 1
                
        # Normalise by length to prevent bias towards excessively long sentences
        if word_count > 0:
            scores[i] = score / math_log_len(word_count)
        else:
            scores[i] = 0
            
    return scores

def math_log_len(count):
    """Soft damping function to normalise sentence length"""
    # Simple logarithm approximation for sentence length damping
    import math
    return math.log(1 + count)

def summarize(text, num_sentences=3):
    """Extract top N highest scoring sentences in original chronological order"""
    raw_sentences = split_into_sentences(text)
    if not raw_sentences:
        return [], []
        
    word_freqs = get_word_frequencies(raw_sentences)
    scores = score_sentences(raw_sentences, word_freqs)
    
    # Sort by score descending to get top sentences
    top_indices = sorted(scores, key=scores.get, reverse=True)[:num_sentences]
    
    # Re-sort chronologically so the summary reads in order of original text
    summary_indices = sorted(top_indices)
    
    summary = [raw_sentences[i] for i in summary_indices]
    
    # Extract keywords (top 8 most frequent words)
    keywords = [word for word, freq in word_freqs.most_common(8)]
    
    return summary, keywords, len(raw_sentences)

def main():
    parser = argparse.ArgumentParser(
        description="Extractive Text Summarizer - Generate clean summaries from text files or standard input."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "-f", "--file",
        help="Path to the text file to summarize"
    )
    group.add_argument(
        "-t", "--text",
        help="Raw text string to summarize"
    )
    group.add_argument(
        "--stdin",
        action="store_true",
        help="Read text from standard input"
    )
    
    parser.add_argument(
        "-n", "--sentences",
        type=int,
        default=3,
        help="Number of sentences in the generated summary (default: 3)"
    )
    parser.add_argument(
        "-s", "--stats",
        action="store_true",
        help="Show detailed text statistics"
    )
    
    args = parser.parse_args()
    
    text = ""
    if args.file:
        if not os.path.exists(args.file):
            print(colorize(f"Error: File '{args.file}' does not exist.", 'red'), file=sys.stderr)
            sys.exit(1)
        try:
            with open(args.file, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
        except Exception as e:
            print(colorize(f"Error reading file: {e}", 'red'), file=sys.stderr)
            sys.exit(1)
    elif args.text:
        text = args.text
    elif args.stdin:
        if sys.stdin.isatty():
            print("Enter text (Ctrl+D / Ctrl+Z to finish):")
        text = sys.stdin.read()
        
    text = text.strip()
    if not text:
        print(colorize("Error: Empty text input.", 'red'), file=sys.stderr)
        sys.exit(1)
        
    # Enable terminal VT processing on Windows
    if os.name == 'nt':
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
        
    summary_sentences, keywords, total_sentences = summarize(text, args.sentences)
    
    if not summary_sentences:
        print("Could not generate a summary. Make sure the text contains complete sentences.")
        return
        
    # Stats calculations
    original_words = len(text.split())
    summary_text = " ".join(summary_sentences)
    summary_words = len(summary_text.split())
    compression = (1 - (summary_words / original_words)) * 100 if original_words > 0 else 0
    reading_time_mins = max(1, original_words // 200) # average 200 WPM
    
    # Output summary
    print("\n" + colorize("Summary:", 'bold'))
    for s in summary_sentences:
        print(f"• {s}")
    print()
    
    # Output keywords
    if keywords:
        print(colorize("Keywords: ", 'bold') + ", ".join(keywords))
        print()
        
    if args.stats:
        print("=" * 50)
        print(colorize("Text Analytics & Statistics", 'bold'))
        print("=" * 50)
        print(f"Original Sentences:   {total_sentences}")
        print(f"Summary Sentences:    {len(summary_sentences)}")
        print(f"Original Word Count:  {original_words}")
        print(f"Summary Word Count:   {summary_words}")
        print(f"Compression Ratio:    {compression:.1f}% reduced")
        print(f"Est. Reading Time:    {reading_time_mins} minute(s)")
        print("=" * 50)

if __name__ == '__main__':
    main()
