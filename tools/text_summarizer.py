#!/usr/bin/env python3
"""
Text Summarizer & Keyword Extractor - Summarize text files and extract key terms.

This tool implements extractive summarization based on word frequency scoring and
keyword extraction using stopword filtering, with no external dependencies.

Usage:
    python tools/text_summarizer.py [file_path] [options]
"""

import sys
import re
import argparse
from collections import Counter
from typing import List, Set, Tuple

# Built-in list of common English stopwords to avoid external dependencies
STOPWORDS: Set[str] = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "aren't",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but", "by",
    "can", "can't", "cannot", "could", "couldn't", "did", "didn't", "do", "does", "doesn't", "doing",
    "don't", "down", "during", "each", "few", "for", "from", "further", "had", "hadn't", "has", "hasn't",
    "have", "haven't", "having", "he", "he'd", "he'll", "he's", "her", "here", "here's", "hers",
    "herself", "him", "himself", "his", "how", "how's", "i", "i'd", "i'll", "i'm", "i've", "if", "in",
    "into", "is", "isn't", "it", "it's", "its", "itself", "let's", "me", "more", "most", "mustn't", "my",
    "myself", "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our",
    "ours", "ourselves", "out", "over", "own", "same", "shan't", "she", "she'd", "she'll", "she's",
    "should", "shouldn't", "so", "some", "such", "than", "that", "that's", "the", "their", "theirs",
    "them", "themselves", "then", "there", "there's", "these", "they", "they'd", "they'll", "they're",
    "they've", "this", "those", "through", "to", "too", "under", "until", "up", "very", "was", "wasn't",
    "we", "we'd", "we'll", "we're", "we've", "were", "weren't", "what", "what's", "when", "when's",
    "where", "where's", "which", "while", "who", "who's", "whom", "why", "why's", "with", "won't",
    "would", "wouldn't", "you", "you'd", "you'll", "you're", "you've", "your", "yours", "yourself",
    "yourselves"
}


def parse_args():
    parser = argparse.ArgumentParser(
        description="Text Summarizer & Keyword Extractor - Extracts summary sentences and keywords from text."
    )
    parser.add_argument(
        "file", nargs="?", help="Path to text file (reads from stdin if omitted)"
    )
    parser.add_argument(
        "-s", "--sentences", type=int, default=3, help="Number of summary sentences (default: 3)"
    )
    parser.add_argument(
        "-k", "--keywords", type=int, default=5, help="Number of keywords to extract (default: 5)"
    )
    parser.add_argument(
        "--stats", action="store_true", help="Print document statistics (words, sentences, etc.)"
    )
    return parser.parse_args()


def tokenize_sentences(text: str) -> List[str]:
    # Basic sentence splitter that handles abbreviations roughly
    # Split by period, exclamation, or question mark, followed by whitespace and a capital letter
    sentence_end = re.compile(r'(?<!\b\w\.\w.)(?<!\b[A-Z][a-z]\.)(?<=\.|\?|\!)\s(?=[A-Z0-9])')
    sentences = sentence_end.split(text.replace('\n', ' '))
    return [s.strip() for s in sentences if s.strip()]


def tokenize_words(text: str) -> List[str]:
    # Find all word characters and convert to lowercase
    return re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())


def extract_keywords(words: List[str], count: int) -> List[Tuple[str, int]]:
    filtered_words = [w for w in words if w not in STOPWORDS]
    counter = Counter(filtered_words)
    return counter.most_common(count)


def generate_summary(sentences: List[str], words: List[str], num_sentences: int) -> List[str]:
    if not sentences:
        return []
    
    # Calculate word frequency
    filtered_words = [w for w in words if w not in STOPWORDS]
    word_freq = Counter(filtered_words)
    if not word_freq:
        return sentences[:num_sentences]
        
    max_freq = max(word_freq.values())
    
    # Normalize frequency scores
    word_scores = {word: freq / max_freq for word, freq in word_freq.items()}
    
    # Score sentences based on sum of word scores
    sentence_scores = []
    for i, sentence in enumerate(sentences):
        sentence_words = tokenize_words(sentence)
        score = sum(word_scores.get(w, 0) for w in sentence_words)
        # Normalize score by length slightly to avoid favoring excessively long sentences
        length = len(sentence_words)
        if length > 0:
            score = score / (length ** 0.5) # Soft penalty for long sentences
        sentence_scores.append((score, i, sentence))
        
    # Sort sentences by score descending, pick top N
    top_sentences = sorted(sentence_scores, key=lambda x: x[0], reverse=True)[:num_sentences]
    
    # Re-sort top sentences by their original index to preserve reading order
    ordered_sentences = sorted(top_sentences, key=lambda x: x[1])
    
    return [s[2] for s in ordered_sentences]


def main():
    args = parse_args()
    
    if args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                text = f.read()
        except FileNotFoundError:
            print(f"Error: File '{args.file}' not found.", file=sys.stderr)
            return 1
        except Exception as e:
            print(f"Error reading file: {e}", file=sys.stderr)
            return 1
    else:
        # Read from stdin
        if sys.stdin.isatty():
            print("Provide file path or pipe/stdin input. Run with --help for options.")
            return 1
        text = sys.stdin.read()
        
    if not text.strip():
        print("Error: Input text is empty.", file=sys.stderr)
        return 1
        
    sentences = tokenize_sentences(text)
    words = tokenize_words(text)
    
    if args.stats:
        print("=== Document Statistics ===")
        print(f"Total Sentences: {len(sentences)}")
        print(f"Total Words:     {len(words)}")
        print(f"Estimated Read Time: {max(1, len(words) // 200)} min")
        print("===========================\n")
        
    # Extract Keywords
    keywords = extract_keywords(words, args.keywords)
    print(f"--- Top {len(keywords)} Keywords ---")
    for word, freq in keywords:
        print(f"  • {word} ({freq} times)")
    print()
    
    # Generate Summary
    summary = generate_summary(sentences, words, args.sentences)
    print(f"--- Summary ({len(summary)} sentences) ---")
    for sentence in summary:
        print(f"  {sentence}")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
