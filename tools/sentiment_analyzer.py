#!/usr/bin/env python3
"""
Sentiment Analyzer
A lightweight, offline, lexicon-based text sentiment analyzer.

Usage:
    python tools/sentiment_analyzer.py [text_or_file] [options]

Arguments:
    text_or_file           A text string to analyze, a file path, or "-" for stdin (default: "-")

Options:
    -s, --sentences        Show sentence-by-sentence sentiment breakdown
    -f, --format FORMAT    Output format: text, json (default: text)
    -c, --no-color         Disable colored terminal output
    -h, --help             Show this help message and exit

Example:
    python tools/sentiment_analyzer.py "This product is absolutely amazing and I love it!"
    python tools/sentiment_analyzer.py review.txt --sentences
    echo "This is not good, very disappointing." | python tools/sentiment_analyzer.py
"""

import argparse
import json
import os
import re
import sys

# Built-in sentiment lexicon (word -> score from -4 to +4)
LEXICON = {
    # Positive words
    'love': 4, 'loved': 4, 'loves': 4, 'loving': 4, 'like': 2, 'liked': 2, 'likes': 2, 'liking': 2,
    'good': 2, 'great': 3, 'excellent': 4, 'best': 4, 'wonderful': 4, 'amazing': 4, 'fantastic': 4,
    'awesome': 4, 'beautiful': 3, 'pretty': 2, 'happy': 3, 'glad': 2, 'pleased': 2, 'enjoy': 2,
    'enjoyed': 2, 'enjoys': 2, 'perfect': 4, 'perfectly': 4, 'nice': 2, 'nicely': 2, 'cool': 1,
    'satisfy': 2, 'satisfied': 2, 'satisfying': 2, 'recommend': 2, 'superb': 4, 'outstanding': 4,
    'brilliant': 4, 'fine': 1, 'smart': 2, 'clever': 2, 'friendly': 2, 'helpful': 2, 'useful': 2,
    'valuable': 3, 'worth': 2, 'worthy': 2, 'easier': 2, 'easy': 2, 'fast': 1, 'secure': 2,
    'safe': 2, 'clean': 2, 'clear': 1, 'clearly': 1, 'simple': 1, 'simply': 1, 'stable': 2,
    'support': 2, 'supported': 2, 'trust': 3, 'trusted': 3, 'win': 3, 'winner': 3, 'won': 3,
    'ideal': 3, 'genius': 4, 'hero': 3, 'success': 3, 'successful': 3, 'happily': 3, 'kind': 2,

    # Negative words
    'hate': -4, 'hated': -4, 'hating': -4, 'hates': -4, 'dislike': -2, 'disliked': -2, 'bad': -2,
    'worse': -3, 'worst': -4, 'terrible': -4, 'horrible': -4, 'awful': -3, 'hateable': -3,
    'poor': -2, 'poorly': -2, 'broken': -2, 'bug': -1, 'bugs': -1, 'buggy': -2, 'fail': -2,
    'failed': -2, 'fails': -2, 'failure': -3, 'error': -1, 'errors': -1, 'defect': -2,
    'faulty': -2, 'wrong': -2, 'incorrect': -2, 'crash': -2, 'crashed': -2, 'crashes': -2,
    'slow': -2, 'slowly': -2, 'lag': -2, 'lagging': -2, 'pain': -2, 'painful': -2, 'sad': -2,
    'suffer': -3, 'suffered': -3, 'angry': -3, 'mad': -3, 'annoy': -2, 'annoyed': -2,
    'annoying': -3, 'disappoint': -2, 'disappointed': -2, 'disappointing': -3, 'disappointment': -3,
    'useless': -3, 'worthless': -4, 'waste': -2, 'wasted': -2, 'hatefully': -4, 'scam': -4,
    'fraud': -4, 'risky': -2, 'risk': -2, 'danger': -2, 'dangerous': -3, 'unstable': -3,
    'confusing': -2, 'confused': -2, 'hard': -1, 'difficult': -2, 'complex': -1, 'mess': -2,
    'messy': -2, 'dirty': -2, 'ugly': -3, 'hate': -3, 'unhappy': -3, 'boring': -2, 'bored': -2,
    'stupid': -3, 'dumb': -3, 'silly': -1, 'lame': -2, 'lose': -2, 'loser': -3, 'lost': -2,
}

# Negation words that reverse the sentiment of the following word
NEGATIONS = {'not', 'no', 'never', 'neither', 'nor', 'dont', 'doesnt', 'didnt', 'wasnt', 'werent', 'isnt', 'arent', 'cannot', 'cant', 'wont', 'shant', 'wouldnt', 'shouldnt', 'couldnt', 'havent', 'hasnt', 'hadnt'}


def clean_and_tokenize(text):
    """Clean text and split into words, keeping trace of original casing."""
    text = text.lower()
    # Replace common contractions
    text = re.sub(r"n't", " not", text)
    text = re.sub(r"'s", " is", text)
    text = re.sub(r"'re", " are", text)
    text = re.sub(r"'d", " would", text)
    text = re.sub(r"'ll", " will", text)
    text = re.sub(r"'t", " not", text)
    
    # Remove punctuation except spaces
    words = re.findall(r'\b\w+\b', text)
    return words


def analyze_sentiment(text):
    """Analyze sentiment of a text string and return detailed score mapping."""
    words = clean_and_tokenize(text)
    
    score = 0
    pos_words = []
    neg_words = []
    neutral_words = []
    
    negate = False
    
    for i, word in enumerate(words):
        # Check if the word is a negation
        if word in NEGATIONS:
            negate = True
            continue
            
        if word in LEXICON:
            word_score = LEXICON[word]
            if negate:
                word_score = -word_score
                negate = False
                
            score += word_score
            if word_score > 0:
                pos_words.append(word)
            elif word_score < 0:
                neg_words.append(word)
        else:
            neutral_words.append(word)
            # Reset negation after a non-lexicon word to avoid propagating too far
            negate = False
            
    # Calculate compound score normalized between -1.0 and +1.0
    # Uses simple hyperbolic tangent-like normalization: score / sqrt(score^2 + alpha)
    # where alpha controls the scaling
    if score == 0:
        compound = 0.0
    else:
        # standard normalization
        compound = score / (abs(score) + 5.0)
        
    # Classification
    if compound > 0.05:
        sentiment = "positive"
    elif compound < -0.05:
        sentiment = "negative"
    else:
        sentiment = "neutral"
        
    return {
        'score': score,
        'compound': round(compound, 3),
        'sentiment': sentiment,
        'positive_words': pos_words,
        'negative_words': neg_words,
        'word_count': len(words)
    }


def split_sentences(text):
    """Simple rule-based sentence splitter."""
    # Split by periods, exclamation marks, or question marks followed by spaces or newlines
    sentences = re.split(r'(?<=[.!?])\s+', text)
    return [s.strip() for s in sentences if s.strip()]


def get_colored_sentiment(sentiment, compound_score, no_color):
    """Format sentiment name with ANSI colors for terminal."""
    if no_color:
        return f"{sentiment.upper()} ({compound_score})"
        
    green = "\033[1;32m"
    red = "\033[1;31m"
    yellow = "\033[1;33m"
    reset = "\033[0m"
    
    if sentiment == "positive":
        return f"{green}POSITIVE{reset} ({compound_score})"
    elif sentiment == "negative":
        return f"{red}NEGATIVE{reset} ({compound_score})"
    else:
        return f"{yellow}NEUTRAL{reset} ({compound_score})"


def main():
    parser = argparse.ArgumentParser(description="Standalone Lexicon-based Sentiment Analyzer.")
    parser.add_argument('text_or_file', nargs='?', default='-',
                        help='A raw text string, a path to a text file, or "-" to read from stdin')
    parser.add_argument('-s', '--sentences', action='store_true',
                        help='Show sentence-by-sentence breakdown')
    parser.add_argument('-f', '--format', choices=['text', 'json'], default='text',
                        help='Output format (default: text)')
    parser.add_argument('-c', '--no-color', action='store_true',
                        help='Disable colored terminal outputs')
    
    args = parser.parse_args()

    # Read input text
    input_text = ""
    if args.text_or_file == '-':
        if sys.stdin.isatty():
            # Stdin is interactive, but empty
            print("Error: No text provided. Provide a string, file path, or pipe text to stdin.", file=sys.stderr)
            return 1
        input_text = sys.stdin.read()
    elif os.path.isfile(args.text_or_file):
        try:
            with open(args.text_or_file, 'r', encoding='utf-8', errors='ignore') as f:
                input_text = f.read()
        except Exception as e:
            print(f"Error reading file '{args.text_or_file}': {e}", file=sys.stderr)
            return 1
    else:
        input_text = args.text_or_file

    input_text = input_text.strip()
    if not input_text:
        print("Error: Empty input text.", file=sys.stderr)
        return 1

    # Analyze overall sentiment
    overall_result = analyze_sentiment(input_text)

    # Analyze sentences if requested
    sentence_results = []
    if args.sentences:
        sentences = split_sentences(input_text)
        for s in sentences:
            s_res = analyze_sentiment(s)
            sentence_results.append({
                'sentence': s,
                'analysis': s_res
            })

    # Output results
    if args.format == 'json':
        output_data = {
            'overall': overall_result,
        }
        if args.sentences:
            output_data['sentences'] = sentence_results
        print(json.dumps(output_data, indent=2))
        
    else:  # text
        print("=" * 60)
        print(" SENTIMENT ANALYSIS REPORT")
        print("=" * 60)
        
        # Display overall sentiment
        label = get_colored_sentiment(overall_result['sentiment'], overall_result['compound'], args.no_color)
        print(f"Overall Sentiment: {label}")
        print(f"Total Words parsed: {overall_result['word_count']}")
        print(f"Sentiment Score:   {overall_result['score']}")
        
        if overall_result['positive_words']:
            print(f"Positive Keywords: {', '.join(set(overall_result['positive_words']))}")
        if overall_result['negative_words']:
            print(f"Negative Keywords: {', '.join(set(overall_result['negative_words']))}")
            
        if args.sentences and sentence_results:
            print("\n" + "-" * 40)
            print(" Sentence Breakdown:")
            print("-" * 40)
            for item in sentence_results:
                s = item['sentence']
                res = item['analysis']
                s_label = get_colored_sentiment(res['sentiment'], res['compound'], args.no_color)
                # Trim sentence if too long for display
                disp_s = s[:80] + '...' if len(s) > 83 else s
                print(f"  [{s_label}] {disp_s}")
                
        print("=" * 60)

    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nAborted.", file=sys.stderr)
        sys.exit(1)
