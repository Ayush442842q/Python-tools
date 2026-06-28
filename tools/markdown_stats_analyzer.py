#!/usr/bin/env python3
"""
Markdown Stats Analyzer
Analyzes Markdown files to calculate readability metrics (Flesch Reading Ease, Grade Level),
counts words, sentences, characters (excluding Markdown syntax, code blocks, and tags),
and audits markdown structure (headers, links, images, code blocks).
"""

import sys
import os
import re
import argparse

def count_syllables(word):
    """Simple heuristic to count syllables in an English word"""
    word = word.lower().strip(".:;?!,()\"'")
    if not word:
        return 0
        
    # Check for simple edge cases
    if len(word) <= 3:
        return 1
        
    # Count vowel groups
    vowels = "aeiouy"
    count = 0
    prev_is_vowel = False
    
    for char in word:
        is_vowel = char in vowels
        if is_vowel and not prev_is_vowel:
            count += 1
        prev_is_vowel = is_vowel
        
    # Adjustments
    if word.endswith("e"):
        count -= 1
    if word.endswith("le") and len(word) > 2 and word[-3] not in vowels:
        count += 1
    if count == 0:
        count = 1
    return count

def strip_markdown(content):
    """Strip markdown elements to extract clean plain text for word/sentence counting"""
    # 1. Remove fenced code blocks (``` ... ```)
    content = re.sub(r'```[\s\S]*?```', '', content)
    
    # 2. Remove inline code (`...`)
    content = re.sub(r'`[^`\n]+`', '', content)
    
    # 3. Remove HTML comments (<!-- ... -->)
    content = re.sub(r'<!--[\s\S]*?-->', '', content)
    
    # 4. Remove HTML tags (e.g. <div>)
    content = re.sub(r'<[^>]+>', '', content)
    
    # 5. Convert links [text](url) to just text
    content = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', content)
    
    # 6. Remove image links ![alt](url)
    content = re.sub(r'!\[([^\]]*)\]\([^\)]+\)', '', content)
    
    # 7. Strip headers styling (# Header -> Header)
    content = re.sub(r'^#+\s+', '', content, flags=re.MULTILINE)
    
    # 8. Strip formatting tags (*, **, _, __, ~~, etc.)
    content = re.sub(r'(\*\*|\*|__|_|~~)', '', content)
    
    # 9. Clean up multiple spaces and empty lines
    content = re.sub(r'\s+', ' ', content)
    
    return content.strip()

def analyze_markdown(filepath):
    """Analyze a markdown file and calculate readability and structural statistics"""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            raw_content = f.read()
    except Exception as e:
        print(f"Error: Could not read {filepath}: {e}", file=sys.stderr)
        return None
        
    # Analyze structural elements in raw content
    headers = re.findall(r'^#+\s+(.+)$', raw_content, re.MULTILINE)
    links = re.findall(r'\[([^\]]+)\]\([^\)]+\)', raw_content)
    images = re.findall(r'!\[([^\]]*)\]\([^\)]+\)', raw_content)
    code_blocks = re.findall(r'```', raw_content)
    code_block_count = len(code_blocks) // 2
    
    # Get header hierarchy counts
    header_counts = {1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0}
    for match in re.finditer(r'^(?P<level>#+)\s+', raw_content, re.MULTILINE):
        level = len(match.group('level'))
        if level in header_counts:
            header_counts[level] += 1

    # Extract plain text for linguistic analysis
    plain_text = strip_markdown(raw_content)
    
    # Count words (alphabetic or alphanumeric sequences)
    words = [w for w in re.split(r'\s+', plain_text) if re.search(r'\w', w)]
    word_count = len(words)
    char_count_no_spaces = sum(len(w) for w in words)
    
    # Count sentences (simple splitter by end punctuation followed by spaces or end of string)
    sentences = [s.strip() for s in re.split(r'[.!?]+(?=\s|$)', plain_text) if s.strip()]
    sentence_count = len(sentences)
    
    if word_count == 0 or sentence_count == 0:
        return {
            'word_count': word_count,
            'char_count': len(raw_content),
            'sentence_count': sentence_count,
            'avg_sentence_len': 0,
            'avg_word_len': 0,
            'syllables': 0,
            'flesch_reading_ease': 0.0,
            'flesch_kincaid_grade': 0.0,
            'read_time_m': 0,
            'speak_time_m': 0,
            'headers_total': len(headers),
            'header_hierarchy': header_counts,
            'links_count': len(links),
            'images_count': len(images),
            'code_blocks_count': code_block_count
        }

    # Calculations
    avg_sentence_len = word_count / sentence_count
    avg_word_len = char_count_no_spaces / word_count
    
    total_syllables = sum(count_syllables(w) for w in words)
    avg_syllables_per_word = total_syllables / word_count
    
    # Flesch Reading Ease Formula
    # 206.835 - (1.015 * ASL) - (84.6 * ASW)
    flesch_reading_ease = 206.835 - (1.015 * avg_sentence_len) - (84.6 * avg_syllables_per_word)
    # Clamp score
    flesch_reading_ease = max(0.0, min(100.0, flesch_reading_ease))
    
    # Flesch-Kincaid Grade Level Formula
    # (0.39 * ASL) + (11.8 * ASW) - 15.59
    flesch_kincaid_grade = (0.39 * avg_sentence_len) + (11.8 * avg_syllables_per_word) - 15.59
    flesch_kincaid_grade = max(0.0, flesch_kincaid_grade)
    
    # Reading time (200 words/min)
    read_time_seconds = int((word_count / 200) * 60)
    # Speaking time (130 words/min)
    speak_time_seconds = int((word_count / 130) * 60)
    
    return {
        'word_count': word_count,
        'char_count': len(raw_content),
        'char_count_clean': char_count_no_spaces,
        'sentence_count': sentence_count,
        'avg_sentence_len': avg_sentence_len,
        'avg_word_len': avg_word_len,
        'syllables': total_syllables,
        'flesch_reading_ease': flesch_reading_ease,
        'flesch_kincaid_grade': flesch_kincaid_grade,
        'read_time_s': read_time_seconds,
        'speak_time_s': speak_time_seconds,
        'headers_total': len(headers),
        'header_hierarchy': header_counts,
        'links_count': len(links),
        'images_count': len(images),
        'code_blocks_count': code_block_count
    }

def format_time(seconds):
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    secs = seconds % 60
    return f"{minutes}m {secs}s"

def get_readability_description(score):
    if score >= 90:
        return "Very Easy (5th grade level, easily understood by an average 11-year-old)"
    elif score >= 80:
        return "Easy (6th grade level, conversational English)"
    elif score >= 70:
        return "Fairly Easy (7th grade level)"
    elif score >= 60:
        return "Standard (8th & 9th grade level, easily understood by 13- to 15-year-olds)"
    elif score >= 50:
        return "Fairly Difficult (10th to 12th grade level)"
    elif score >= 30:
        return "Difficult (College student level)"
    else:
        return "Very Confusing (College graduate level, best understood by professionals)"

def main():
    parser = argparse.ArgumentParser(description="Analyze Markdown file readability and structure statistics.")
    parser.add_argument("file", help="Path to the Markdown file to analyze")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.file):
        print(f"Error: File '{args.file}' does not exist.", file=sys.stderr)
        sys.exit(1)
        
    stats = analyze_markdown(args.file)
    if not stats:
        sys.exit(1)
        
    print(f"\nMarkdown Stats Report for: {os.path.basename(args.file)}")
    print("=" * 60)
    
    print("\n[Linguistic & Readability Statistics]")
    print(f"  • Total Words (Clean):      {stats['word_count']}")
    print(f"  • Total Sentences:          {stats['sentence_count']}")
    print(f"  • Character Count (Raw):    {stats['char_count']}")
    print(f"  • Character Count (Clean):  {stats['char_count_clean']}")
    print(f"  • Avg. Sentence Length:     {stats['avg_sentence_len']:.1f} words")
    print(f"  • Avg. Word Length:         {stats['avg_word_len']:.1f} characters")
    print(f"  • Estimated Read Time:      {format_time(stats['read_time_s'])}")
    print(f"  • Estimated Speak Time:     {format_time(stats['speak_time_s'])}")
    print(f"  • Flesch Reading Ease:      {stats['flesch_reading_ease']:.1f} / 100")
    print(f"    └─ Description:           {get_readability_description(stats['flesch_reading_ease'])}")
    print(f"  • Flesch-Kincaid Grade:     {stats['flesch_kincaid_grade']:.1f} (Grade Level)")
    
    print("\n[Structural Elements]")
    print(f"  • Total Headers:            {stats['headers_total']}")
    for level, count in stats['header_hierarchy'].items():
        if count > 0:
            print(f"    ├─ H{level}:                  {count}")
    print(f"  • Fenced Code Blocks:       {stats['code_blocks_count']}")
    print(f"  • Links/Hyperlinks:         {stats['links_count']}")
    print(f"  • Images:                   {stats['images_count']}")
    print("=" * 60)

if __name__ == "__main__":
    main()
