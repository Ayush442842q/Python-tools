#!/usr/bin/env python3
"""
Lorem Ipsum Generator
Generates customizable placeholder text (Lorem Ipsum) for developers and designers.
Supports words, sentences, paragraphs, lists, and HTML wrapping.
"""

import argparse
import random
import sys

# Standard Lorem Ipsum vocabulary
LOREM_WORDS = [
    "lorem", "ipsum", "dolor", "sit", "amet", "consectetur", "adipiscing", "elit", 
    "sed", "do", "eiusmod", "tempor", "incididunt", "ut", "labore", "et", "dolore", 
    "magna", "aliqua", "ut", "enim", "ad", "minim", "veniam", "quis", "nostrud", 
    "exercitation", "ullamco", "laboris", "nisi", "ut", "aliquip", "ex", "ea", 
    "commodo", "consequat", "duis", "aute", "irure", "dolor", "in", "reprehenderit", 
    "in", "voluptate", "velit", "esse", "cillum", "dolore", "eu", "fugiat", "nulla", 
    "pariatur", "excepteur", "sint", "occaecat", "cupidatat", "non", "proident", 
    "sunt", "in", "culpa", "qui", "officia", "deserunt", "mollit", "anim", "id", "est", "laborum"
]

def generate_sentence(words_pool, min_words=5, max_words=15, start_with_lorem=False):
    """Generates a single sentence with capitalized first letter and ending period."""
    num_words = random.randint(min_words, max_words)
    sentence_words = []
    
    if start_with_lorem:
        sentence_words = ["lorem", "ipsum", "dolor", "sit", "amet"]
        # Top up if required
        if num_words > 5:
            sentence_words.extend(random.choices(words_pool, k=num_words - 5))
        else:
            sentence_words = sentence_words[:num_words]
    else:
        sentence_words = random.choices(words_pool, k=num_words)
    
    # Capitalize first word
    sentence = " ".join(sentence_words).capitalize()
    
    # Add commas randomly in longer sentences
    if num_words > 8:
        words_list = sentence.split()
        comma_idx = random.randint(3, num_words - 4)
        words_list[comma_idx] += ","
        sentence = " ".join(words_list)
        
    return sentence + "."

def generate_paragraph(words_pool, num_sentences=5, min_words=6, max_words=16, start_with_lorem=False):
    """Generates a paragraph consisting of multiple sentences."""
    sentences = []
    for i in range(num_sentences):
        # Only start the very first sentence of the very first paragraph with lorem if requested
        is_first = (i == 0 and start_with_lorem)
        sentences.append(generate_sentence(words_pool, min_words, max_words, is_first))
    return " ".join(sentences)

def main():
    parser = argparse.ArgumentParser(
        description="Generate customizable placeholder Lorem Ipsum text."
    )
    
    parser.add_argument('-m', '--mode', choices=['words', 'sentences', 'paragraphs', 'lists'], default='paragraphs',
                        help="Type of content to generate (default: paragraphs)")
    parser.add_argument('-n', '--count', type=int, default=3,
                        help="Number of elements to generate (default: 3)")
    
    # Customization parameters
    parser.add_argument('--min-words', type=int, default=5,
                        help="Minimum words per sentence (default: 5)")
    parser.add_argument('--max-words', type=int, default=15,
                        help="Maximum words per sentence (default: 15)")
    parser.add_argument('--sentences-per-paragraph', type=int, default=5,
                        help="Sentences per paragraph (default: 5)")
    
    # Options
    parser.add_argument('--no-lorem', action='store_true',
                        help="Do not start the output with standard 'Lorem ipsum dolor sit amet'")
    parser.add_argument('--html', action='store_true',
                        help="Wrap output in appropriate HTML tags (<p>, <ul>/<li>)")
    parser.add_argument('--custom-vocab', help="File containing custom words to use instead of Latin")

    args = parser.parse_args()

    # Load custom vocabulary if provided
    words_pool = LOREM_WORDS
    if args.custom_vocab:
        try:
            with open(args.custom_vocab, 'r', encoding='utf-8') as f:
                content = f.read()
                # Extract words using regex
                custom_words = re.findall(r'\b\w+\b', content.lower())
                if custom_words:
                    words_pool = list(set(custom_words))
                else:
                    print(f"Warning: No words found in custom vocab file. Using defaults.", file=sys.stderr)
        except Exception as e:
            print(f"Error reading custom vocabulary file: {e}. Using defaults.", file=sys.stderr)

    start_with_lorem = not args.no_lorem
    output_parts = []

    if args.mode == 'words':
        word_count = args.count
        if start_with_lorem:
            lorem_start = ["lorem", "ipsum", "dolor", "sit", "amet"]
            if word_count > 5:
                generated_words = lorem_start + random.choices(words_pool, k=word_count - 5)
            else:
                generated_words = lorem_start[:word_count]
        else:
            generated_words = random.choices(words_pool, k=word_count)
            
        words_text = " ".join(generated_words)
        if args.html:
            output_parts.append(f"<span>{words_text}</span>")
        else:
            output_parts.append(words_text)

    elif args.mode == 'sentences':
        for i in range(args.count):
            is_first = (i == 0 and start_with_lorem)
            sentence = generate_sentence(words_pool, args.min_words, args.max_words, is_first)
            if args.html:
                output_parts.append(f"<li>{sentence}</li>" if args.html and args.count > 1 else f"<span>{sentence}</span>")
            else:
                output_parts.append(sentence)
        
        if args.html and args.count > 1:
            output_parts.insert(0, "<ul>")
            output_parts.append("</ul>")

    elif args.mode == 'paragraphs':
        for i in range(args.count):
            is_first = (i == 0 and start_with_lorem)
            paragraph = generate_paragraph(
                words_pool, 
                num_sentences=args.sentences_per_paragraph,
                min_words=args.min_words,
                max_words=args.max_words,
                start_with_lorem=is_first
            )
            if args.html:
                output_parts.append(f"<p>{paragraph}</p>")
            else:
                output_parts.append(paragraph)

    elif args.mode == 'lists':
        if args.html:
            output_parts.append("<ul>")
        for i in range(args.count):
            item_text = generate_sentence(words_pool, 3, 8, False)
            if args.html:
                output_parts.append(f"  <li>{item_text}</li>")
            else:
                output_parts.append(f"- {item_text}")
        if args.html:
            output_parts.append("</ul>")

    # Join output
    separator = "\n" if args.mode == 'lists' or args.html else "\n\n"
    print(separator.join(output_parts))

    return 0

if __name__ == '__main__':
    sys.exit(main())
