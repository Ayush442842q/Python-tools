#!/usr/bin/env python3
"""
Text Similarity Detector & Plagiarism Finder
Compares text files or code files to compute similarity scores (Cosine Similarity via TF-IDF and Jaccard similarity).
Uses only standard Python libraries.
"""
import argparse
import collections
import math
import os
import re
import sys

# Standard set of English stop words to filter out (optional)
STOP_WORDS = {
    'a', 'about', 'above', 'after', 'again', 'against', 'all', 'am', 'an', 'and', 'any', 'are', 'arent', 'as', 'at',
    'be', 'because', 'been', 'before', 'being', 'below', 'between', 'both', 'but', 'by', 'cant', 'cannot', 'could',
    'couldnt', 'did', 'didnt', 'do', 'does', 'doesnt', 'doing', 'dont', 'down', 'during', 'each', 'few', 'for', 'from',
    'further', 'had', 'hadnt', 'has', 'hasnt', 'have', 'havent', 'having', 'he', 'hed', 'hell', 'hes', 'her', 'here',
    'heres', 'hers', 'herself', 'him', 'himself', 'his', 'how', 'hows', 'i', 'id', 'ill', 'im', 'ive', 'if', 'in',
    'into', 'is', 'isnt', 'it', 'its', 'itself', 'lets', 'me', 'more', 'most', 'mustnt', 'my', 'myself', 'no', 'nor',
    'not', 'of', 'off', 'on', 'once', 'only', 'or', 'other', 'ought', 'our', 'ours', 'ourselves', 'out', 'over', 'own',
    'same', 'shant', 'shes', 'should', 'shouldnt', 'so', 'some', 'such', 'than', 'that', 'thats', 'the', 'their',
    'theirs', 'them', 'themselves', 'then', 'there', 'theres', 'these', 'they', 'theyd', 'theyll', 'theyre', 'theyve',
    'this', 'those', 'through', 'to', 'too', 'under', 'until', 'up', 'very', 'was', 'wasnt', 'we', 'wed', 'well',
    'were', 'weve', 'werent', 'what', 'whats', 'when', 'whens', 'where', 'wheres', 'which', 'while', 'who', 'whos',
    'whom', 'why', 'whys', 'with', 'wont', 'would', 'wouldnt', 'you', 'youd', 'youll', 'youre', 'youve', 'your',
    'yours', 'yourself', 'yourselves'
}

def tokenize(text, remove_stopwords=False):
    """Tokenize text into lowercase alphanumeric words."""
    words = re.findall(r'[a-zA-Z0-9]+', text.lower())
    if remove_stopwords:
        words = [w for w in words if w not in STOP_WORDS]
    return words

def get_word_frequencies(words):
    """Compute frequency count of words."""
    return collections.Counter(words)

def compute_jaccard_similarity(words1, words2):
    """
    Compute Jaccard Similarity: Intersection / Union.
    Excellent for set-based comparisons.
    """
    set1, set2 = set(words1), set(words2)
    if not set1 and not set2:
        return 1.0
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return intersection / union

def compute_cosine_similarity(freq1, freq2):
    """
    Compute Cosine Similarity between two term frequency dictionaries.
    Cosine Similarity = (A . B) / (||A|| * ||B||)
    """
    # Dot product
    dot_product = sum(freq1[word] * freq2[word] for word in freq1 if word in freq2)
    
    # Vector lengths
    length1 = math.sqrt(sum(val ** 2 for val in freq1.values()))
    length2 = math.sqrt(sum(val ** 2 for val in freq2.values()))
    
    if length1 == 0 or length2 == 0:
        return 0.0
        
    return dot_product / (length1 * length2)

def compute_tfidf_cosine_similarity(doc1_words, doc2_words, corpus_words_list):
    """
    Compute TF-IDF Cosine Similarity.
    Takes into account document frequencies across a larger corpus (if available).
    """
    # Create a small temporary corpus out of the two documents if no larger one is provided
    corpus = corpus_words_list if corpus_words_list else [doc1_words, doc2_words]
    num_docs = len(corpus)
    
    # Calculate Document Frequency (DF) for each word
    df = collections.defaultdict(int)
    for doc in corpus:
        unique_words = set(doc)
        for word in unique_words:
            df[word] += 1
            
    # Calculate IDF: log(N / DF)
    idf = {}
    for word, count in df.items():
        idf[word] = math.log(num_docs / count) + 1.0  # smoothing

    # Calculate TF-IDF vectors
    def get_tfidf_vector(doc_words):
        tf = collections.Counter(doc_words)
        total_words = len(doc_words)
        tfidf = {}
        for word, count in tf.items():
            # Term Frequency (TF) normalized
            tf_norm = count / total_words
            tfidf[word] = tf_norm * idf.get(word, 1.0)
        return tfidf

    vector1 = get_tfidf_vector(doc1_words)
    vector2 = get_tfidf_vector(doc2_words)
    
    # Compute Cosine Similarity of TF-IDF vectors
    dot_product = sum(vector1[word] * vector2[word] for word in vector1 if word in vector2)
    length1 = math.sqrt(sum(val ** 2 for val in vector1.values()))
    length2 = math.sqrt(sum(val ** 2 for val in vector2.values()))
    
    if length1 == 0 or length2 == 0:
        return 0.0
        
    return dot_product / (length1 * length2)

def load_file(file_path):
    """Load and read file safely."""
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            return f.read()
    except Exception as e:
        print(f"Error reading file '{file_path}': {e}", file=sys.stderr)
        return None

def main():
    parser = argparse.ArgumentParser(description="Find text similarity and plagiarism across files.")
    parser.add_argument("paths", nargs="+", help="Paths to files or directories to compare")
    parser.add_argument("-e", "--extensions", default=".txt,.py,.md,.js,.c,.cpp,.h",
                        help="Comma-separated file extensions to scan in directories")
    parser.add_argument("-t", "--threshold", type=float, default=0.3,
                        help="Similarity threshold (0.0 to 1.0) to report matches (default: 0.3)")
    parser.add_argument("--stop-words", action="store_true", help="Remove English stop words before comparing")
    parser.add_argument("--method", choices=["cosine", "jaccard", "tfidf"], default="tfidf",
                        help="Similarity calculation method (default: tfidf)")
    
    args = parser.parse_args()
    
    # Gather files
    files_to_read = []
    extensions = [ext.strip().lower() for ext in args.extensions.split(',')]
    
    for path in args.paths:
        if os.path.isfile(path):
            files_to_read.append(path)
        elif os.path.isdir(path):
            for root, _, files in os.walk(path):
                for file in files:
                    if any(file.lower().endswith(ext) for ext in extensions):
                        files_to_read.append(os.path.join(root, file))
                        
    # Remove duplicates
    files_to_read = list(set(files_to_read))
    
    if len(files_to_read) < 2:
        print("Error: Need at least 2 files to compare.", file=sys.stderr)
        sys.exit(1)
        
    print(f"Scanning and tokenizing {len(files_to_read)} files...")
    
    # Read files and tokenize
    doc_contents = {}
    doc_words = {}
    doc_freqs = {}
    
    for file_path in files_to_read:
        content = load_file(file_path)
        if content is not None:
            words = tokenize(content, remove_stopwords=args.stop_words)
            if words:
                doc_contents[file_path] = content
                doc_words[file_path] = words
                doc_freqs[file_path] = get_word_frequencies(words)
                
    # Filter files that had readable words
    valid_files = list(doc_words.keys())
    if len(valid_files) < 2:
        print("Error: Not enough valid files with content to compare.", file=sys.stderr)
        sys.exit(1)
        
    print(f"Comparing pairs from {len(valid_files)} files using method: {args.method}...\n")
    
    results = []
    
    # Pairwise comparison
    for i in range(len(valid_files)):
        for j in range(i + 1, len(valid_files)):
            file1 = valid_files[i]
            file2 = valid_files[j]
            
            words1 = doc_words[file1]
            words2 = doc_words[file2]
            
            if args.method == "jaccard":
                score = compute_jaccard_similarity(words1, words2)
            elif args.method == "cosine":
                score = compute_cosine_similarity(doc_freqs[file1], doc_freqs[file2])
            else:  # tfidf
                # Generate corpus words list dynamically from all files
                corpus = list(doc_words.values())
                score = compute_tfidf_cosine_similarity(words1, words2, corpus)
                
            if score >= args.threshold:
                results.append((score, file1, file2))
                
    # Sort results by score (descending)
    results.sort(key=lambda x: x[0], reverse=True)
    
    if not results:
        print("No files exceeded the similarity threshold of {:.2f}.".format(args.threshold))
        sys.exit(0)
        
    # Output formatting
    print(f"{'Similarity':<12} | {'File 1':<35} | {'File 2'}")
    print("-" * 80)
    for score, file1, file2 in results:
        # Get relative path or basename for display if paths are too long
        display1 = os.path.relpath(file1) if len(file1) > 35 else file1
        display2 = os.path.relpath(file2) if len(file2) > 35 else file2
        print(f"{score*100:6.2f}%      | {display1:<35} | {display2}")
        
    print()

if __name__ == "__main__":
    main()
