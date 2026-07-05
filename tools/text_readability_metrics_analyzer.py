#!/usr/bin/env python3
"""
Text Readability Metrics & Prose Analyzer
Calculates multi-formula readability scores for plain text files, markdown documents, or code comments:
  - Flesch Reading Ease
  - Flesch-Kincaid Grade Level
  - Gunning Fog Index
  - Coleman-Liau Index
  - SMOG Index
  - Automated Readability Index (ARI)
  - LIX Readability Index

Uses only standard Python libraries.
"""

import argparse
import json
import math
import os
import re
import sys


def count_syllables_word(word):
    """
    Estimate syllable count for an English word using heuristic rules.
    """
    word = word.lower().strip()
    if not word:
        return 0
    if len(word) <= 3:
        return 1
    
    word = re.sub(r'(?:[^laeiouy]|ed|es|e)$', '', word)
    word = re.sub(r'^y', '', word)
    syllables = len(re.findall(r'[aeiouy]{1,2}', word))
    return max(1, syllables)


def analyze_text(text):
    """
    Parses input text and computes linguistic counts and readability formulas.
    """
    # Clean text
    clean_text = re.sub(r'```[\s\S]*?```', '', text)  # remove code blocks
    clean_text = re.sub(r'#+\s*', '', clean_text)      # remove headers
    
    # Extract sentences
    sentences = re.split(r'[.!?]+', clean_text)
    sentences = [s.strip() for s in sentences if s.strip()]
    num_sentences = max(1, len(sentences))
    
    # Extract words
    words = re.findall(r'\b[a-zA-Z]+\b', clean_text)
    num_words = max(1, len(words))
    
    # Letters & Syllables
    num_letters = sum(len(w) for w in words)
    syllable_counts = [count_syllables_word(w) for w in words]
    num_syllables = sum(syllable_counts)
    
    complex_words = sum(1 for s in syllable_counts if s >= 3)
    long_words = sum(1 for w in words if len(w) > 6)
    
    # Average ratios
    words_per_sentence = num_words / num_sentences
    syllables_per_word = num_syllables / num_words
    letters_per_100_words = (num_letters / num_words) * 100
    sentences_per_100_words = (num_sentences / num_words) * 100
    percent_complex = (complex_words / num_words) * 100
    percent_long = (long_words / num_words) * 100

    # Formulas
    # 1. Flesch Reading Ease
    flesch_reading_ease = 206.835 - (1.015 * words_per_sentence) - (84.6 * syllables_per_word)
    flesch_reading_ease = max(0.0, min(100.0, flesch_reading_ease))
    
    # 2. Flesch-Kincaid Grade Level
    flesch_kincaid = (0.39 * words_per_sentence) + (11.8 * syllables_per_word) - 15.59
    
    # 3. Gunning Fog Index
    gunning_fog = 0.4 * (words_per_sentence + percent_complex)
    
    # 4. Coleman-Liau Index
    coleman_liau = (0.0588 * letters_per_100_words) - (0.296 * sentences_per_100_words) - 15.8
    
    # 5. SMOG Index
    if num_sentences >= 3:
        smog = 1.0430 * math.sqrt(complex_words * (30 / num_sentences)) + 3.1291
    else:
        smog = 0.0
        
    # 6. Automated Readability Index (ARI)
    ari = (4.71 * (num_letters / num_words)) + (0.5 * words_per_sentence) - 21.43
    
    # 7. LIX
    lix = words_per_sentence + percent_long

    # Consensus Grade Level calculation
    valid_grades = [g for g in [flesch_kincaid, gunning_fog, coleman_liau, smog, ari] if g > 0]
    consensus_grade = sum(valid_grades) / len(valid_grades) if valid_grades else 0.0

    return {
        "statistics": {
            "num_words": num_words,
            "num_sentences": num_sentences,
            "num_letters": num_letters,
            "num_syllables": num_syllables,
            "complex_words_3plus_syllables": complex_words,
            "long_words_gt6_chars": long_words,
            "avg_words_per_sentence": round(words_per_sentence, 2),
            "avg_syllables_per_word": round(syllables_per_word, 2)
        },
        "metrics": {
            "flesch_reading_ease": round(flesch_reading_ease, 2),
            "flesch_kincaid_grade": round(max(0.0, flesch_kincaid), 2),
            "gunning_fog_index": round(max(0.0, gunning_fog), 2),
            "coleman_liau_index": round(max(0.0, coleman_liau), 2),
            "smog_index": round(max(0.0, smog), 2),
            "automated_readability_index": round(max(0.0, ari), 2),
            "lix_index": round(max(0.0, lix), 2),
            "consensus_grade_level": round(max(0.0, consensus_grade), 2)
        }
    }


def get_flesch_description(score):
    if score >= 90:
        return "5th Grade (Very Easy)"
    elif score >= 80:
        return "6th Grade (Easy)"
    elif score >= 70:
        return "7th Grade (Fairly Easy)"
    elif score >= 60:
        return "8th-9th Grade (Standard Plain English)"
    elif score >= 50:
        return "10th-12th Grade (Fairly Difficult)"
    elif score >= 30:
        return "College Level (Difficult)"
    else:
        return "College Graduate / Technical (Very Difficult)"


def print_report(results, filename="Input Text"):
    stats = results["statistics"]
    m = results["metrics"]
    
    print("=" * 65)
    print(f" TEXT READABILITY & PROSE ANALYSIS: {filename}")
    print("=" * 65)
    
    print("\n[STATISTICS]")
    print(f"  Total Words:                  {stats['num_words']}")
    print(f"  Total Sentences:              {stats['num_sentences']}")
    print(f"  Total Letters:                {stats['num_letters']}")
    print(f"  Total Syllables:              {stats['num_syllables']}")
    print(f"  Complex Words (>=3 Syllables): {stats['complex_words_3plus_syllables']}")
    print(f"  Avg Words per Sentence:       {stats['avg_words_per_sentence']}")
    print(f"  Avg Syllables per Word:       {stats['avg_syllables_per_word']}")
    
    print("\n[READABILITY FORMULAS]")
    print(f"  Flesch Reading Ease:           {m['flesch_reading_ease']} / 100 ({get_flesch_description(m['flesch_reading_ease'])})")
    print(f"  Flesch-Kincaid Grade Level:    {m['flesch_kincaid_grade']}")
    print(f"  Gunning Fog Index:            {m['gunning_fog_index']}")
    print(f"  Coleman-Liau Index:           {m['coleman_liau_index']}")
    print(f"  SMOG Index:                   {m['smog_index']}")
    print(f"  Automated Readability (ARI):  {m['automated_readability_index']}")
    print(f"  LIX Index:                    {m['lix_index']}")
    
    print("-" * 65)
    print(f" OVERALL CONSENSUS GRADE LEVEL:  Grade {m['consensus_grade_level']}")
    print("=" * 65)


def run_demo():
    print("=== Running Text Readability Metrics Analyzer Demo ===")
    sample_text = """
    Python is an interpreted high-level general-purpose programming language. Its design philosophy
    emphasizes code readability with its use of significant indentation. Its language constructs as
    well as its object-oriented approach aim to help programmers write clear, logical code for small
    and large-scale projects.
    
    Readability is essential for maintenance. Complex code structures increase cognitive overhead,
    making bug identification difficult and slowing down collaborative software development workflows.
    """
    res = analyze_text(sample_text)
    print_report(res, filename="Python Definition Sample")


def main():
    parser = argparse.ArgumentParser(
        description="Text Readability Metrics & Prose Analyzer - Calculate multi-formula readability scores."
    )
    parser.add_argument("file", nargs="?", help="Path to text or markdown file to analyze")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")
    parser.add_argument("--demo", action="store_true", help="Run demonstration with sample text")

    args = parser.parse_args()

    if args.demo or (not args.file and sys.stdin.isatty()):
        run_demo()
        return

    if args.file:
        if not os.path.exists(args.file):
            print(f"Error: File '{args.file}' not found.", file=sys.stderr)
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
        filename = os.path.basename(args.file)
    else:
        content = sys.stdin.read()
        filename = "Standard Input"

    results = analyze_text(content)

    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print_report(results, filename=filename)


if __name__ == "__main__":
    main()
