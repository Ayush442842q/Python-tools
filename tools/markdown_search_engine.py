#!/usr/bin/env python3
"""
Local Markdown Search Engine & TF-IDF Indexer

Recursively indexes a directory of Markdown files, computes TF-IDF scores
for all terms, and provides an interactive search interface with ranked
results and highlighted context snippets in the terminal.
"""

import os
import sys
import math
import re
import argparse
import json
from typing import Dict, List, Set, Tuple

# ANSI Color Escape Codes
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
UNDERLINE = "\033[4m"
RESET = "\033[0m"

# Common English Stop Words to filter out
STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are", "arent", "as", "at",
    "be", "because", "been", "before", "being", "below", "between", "both", "but", "by", "cant", "cannot", "could",
    "couldnt", "did", "didnt", "do", "does", "doesnt", "doing", "dont", "down", "during", "each", "few", "for", "from",
    "further", "had", "hadnt", "has", "hasnt", "have", "havent", "having", "he", "hed", "hell", "hes", "her", "here",
    "heres", "hers", "herself", "him", "himself", "his", "how", "hows", "i", "id", "ill", "im", "ive", "if", "in",
    "into", "is", "isnt", "it", "its", "itself", "lets", "me", "more", "most", "mustnt", "my", "myself", "no", "nor",
    "not", "of", "off", "on", "once", "only", "or", "other", "ought", "our", "ours", "ourselves", "out", "over", "own",
    "same", "shant", "she", "shed", "shell", "shes", "should", "shouldnt", "so", "some", "such", "than", "that",
    "thats", "the", "their", "theirs", "them", "themselves", "then", "there", "theres", "these", "they", "theyd",
    "theyll", "theyre", "theyve", "this", "those", "through", "to", "too", "under", "until", "up", "very", "was",
    "wasnt", "we", "wed", "well", "were", "weve", "werent", "what", "whats", "when", "whens", "where", "wheres",
    "which", "while", "who", "whos", "whom", "why", "whys", "with", "wont", "would", "wouldnt", "you", "youd",
    "youll", "youre", "youve", "your", "yours", "yourself", "yourselves"
}

def colored(text: str, color_code: str) -> str:
    if sys.platform == "win32":
        import os
        os.system("")
    return f"{color_code}{text}{RESET}"

def tokenize(text: str) -> List[str]:
    """Lowercase text and split into alphabetic words, filtering out short/empty tokens."""
    words = re.findall(r'[a-zA-Z0-9]+', text.lower())
    return [w for w in words if len(w) > 1 and w not in STOP_WORDS]

class MarkdownSearchEngine:
    def __init__(self, root_dir: str, index_file: str = ".search_index.json"):
        self.root_dir = os.path.abspath(root_dir)
        self.index_file = os.path.join(self.root_dir, index_file)
        # Document index map: file_path -> doc_id
        self.doc_map: List[str] = []
        # Word frequencies per document: term -> {doc_id: count}
        self.term_freqs: Dict[str, Dict[str, int]] = {}
        # Document lengths (total tokens) for normalization: doc_id -> length
        self.doc_lengths: Dict[str, int] = {}
        # Cache of document titles/headers for nice displays
        self.doc_titles: Dict[str, str] = {}

    def save_index(self):
        data = {
            "doc_map": self.doc_map,
            "term_freqs": self.term_freqs,
            "doc_lengths": self.doc_lengths,
            "doc_titles": self.doc_titles
        }
        try:
            with open(self.index_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(colored(f"[!] Warning: Could not save search index: {e}", RED))

    def load_index(self) -> bool:
        if not os.path.exists(self.index_file):
            return False
        try:
            with open(self.index_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.doc_map = data.get("doc_map", [])
            self.term_freqs = data.get("term_freqs", {})
            # JSON keys are always strings; convert doc_lengths keys if needed
            self.doc_lengths = data.get("doc_lengths", {})
            self.doc_titles = data.get("doc_titles", {})
            return True
        except Exception:
            return False

    def build_index(self):
        """Recursively scan root_dir for markdown files and compute term counts."""
        self.doc_map = []
        self.term_freqs = {}
        self.doc_lengths = {}
        self.doc_titles = {}
        
        print(colored(f"[*] Scanning and indexing Markdown files in {self.root_dir}...", CYAN))
        count = 0
        
        for root, _, files in os.walk(self.root_dir):
            for file in files:
                if file.endswith(('.md', '.markdown')):
                    full_path = os.path.join(root, file)
                    rel_path = os.path.relpath(full_path, self.root_dir)
                    
                    # Skip the index file itself if stored as .md
                    if file == self.index_file:
                        continue
                        
                    try:
                        with open(full_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                    except Exception as e:
                        print(colored(f"[!] Skip {rel_path}: {e}", RED))
                        continue
                        
                    # Add to document map
                    doc_id = str(len(self.doc_map))
                    self.doc_map.append(rel_path)
                    
                    # Extract first header as title
                    first_header = rel_path
                    header_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
                    if header_match:
                        first_header = header_match.group(1).strip()
                    self.doc_titles[doc_id] = first_header
                    
                    # Tokenize and count frequencies
                    tokens = tokenize(content)
                    self.doc_lengths[doc_id] = len(tokens)
                    
                    for token in tokens:
                        if token not in self.term_freqs:
                            self.term_freqs[token] = {}
                        self.term_freqs[token][doc_id] = self.term_freqs[token].get(doc_id, 0) + 1
                        
                    count += 1
                    
        print(colored(f"✓ Indexed {count} documents.", GREEN))
        self.save_index()

    def search(self, query: str, limit: int = 5) -> List[Tuple[str, float, List[Tuple[int, str]]]]:
        """
        Search indexed documents using TF-IDF ranking.
        Returns a list of tuples: (rel_path, score, highlighted_snippets)
        """
        query_tokens = tokenize(query)
        if not query_tokens:
            return []
            
        num_docs = len(self.doc_map)
        scores: Dict[str, float] = {}
        
        # Calculate TF-IDF score for each document
        for token in query_tokens:
            if token not in self.term_freqs:
                continue
                
            # Document frequency (number of docs containing the term)
            doc_freq = len(self.term_freqs[token])
            if doc_freq == 0:
                continue
                
            # Compute Inverse Document Frequency (IDF)
            idf = math.log(1.0 + (num_docs / doc_freq))
            
            # Add scores for each document containing this term
            for doc_id, tf in self.term_freqs[token].items():
                # Term Frequency (normalized by doc length)
                doc_len = self.doc_lengths.get(doc_id, 1)
                normalized_tf = tf / doc_len if doc_len > 0 else 0
                
                scores[doc_id] = scores.get(doc_id, 0.0) + (normalized_tf * idf)
                
        # Sort documents by score descending
        sorted_docs = sorted(scores.items(), key=lambda item: item[1], reverse=True)[:limit]
        
        results = []
        for doc_id, score in sorted_docs:
            rel_path = self.doc_map[int(doc_id)]
            snippets = self._get_snippets(rel_path, query_tokens)
            results.append((rel_path, score, snippets))
            
        return results

    def _get_snippets(self, rel_path: str, query_tokens: List[str], max_snippets: int = 3) -> List[Tuple[int, str]]:
        """Read document, find lines containing query tokens, and highlight them."""
        full_path = os.path.join(self.root_dir, rel_path)
        if not os.path.exists(full_path):
            return []
            
        snippets = []
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except Exception:
            return []
            
        # Build query regex for fast matching and highlighting
        patterns = [r'\b' + re.escape(t) + r'\b' for t in query_tokens]
        combined_pattern = re.compile('|'.join(patterns), re.IGNORECASE)
        
        for idx, line in enumerate(lines):
            clean_line = line.strip()
            if not clean_line:
                continue
                
            match = combined_pattern.search(clean_line)
            if match:
                # Highlight all occurrences
                highlighted = combined_pattern.sub(lambda m: colored(m.group(0), BOLD + YELLOW), clean_line)
                snippets.append((idx + 1, highlighted))
                if len(snippets) >= max_snippets:
                    break
                    
        return snippets

def interactive_search_loop(engine: MarkdownSearchEngine):
    print(colored("\n=== Interactive Markdown Search Console ===", BOLD + CYAN))
    print("Type your search query and press Enter. Type 'exit' or 'q' to quit.")
    print("-" * 50)
    
    while True:
        try:
            query = input(colored("Search > ", BOLD + GREEN)).strip()
            if not query:
                continue
            if query.lower() in ('exit', 'quit', 'q'):
                break
                
            results = engine.search(query)
            if not results:
                print(colored("No matching documents found.", RED))
                print()
                continue
                
            print(colored(f"\nFound {len(results)} matching document(s):", BOLD + YELLOW))
            print(colored("=" * 60, BOLD))
            
            for idx, (path, score, snippets) in enumerate(results, 1):
                title = engine.doc_titles.get(str(engine.doc_map.index(path)), path)
                print(f"{idx}. {colored(title, BOLD + CYAN)} ({path}) [Score: {score:.5f}]")
                if snippets:
                    for line_num, snippet in snippets:
                        print(f"   Line {line_num:<4} : {snippet}")
                else:
                    print("   (No preview snippets available)")
                print(colored("-" * 60, CYAN))
            print()
            
        except KeyboardInterrupt:
            print("\nExiting search console.")
            break

def main():
    parser = argparse.ArgumentParser(description="Local Markdown Search Engine & TF-IDF Indexer")
    parser.add_argument("-d", "--dir", default=".", help="Directory to search (default: current directory)")
    parser.add_argument("-s", "--search", help="One-off search query")
    parser.add_argument("--reindex", action="store_true", help="Force building the search index")
    
    args = parser.parse_args()
    
    engine = MarkdownSearchEngine(args.dir)
    
    # Load index or build if not exists or forced reindex
    if args.reindex or not engine.load_index():
        engine.build_index()
    else:
        print(colored(f"[*] Loaded search index for {engine.root_dir}.", CYAN))
        
    if args.search:
        results = engine.search(args.search)
        if not results:
            print(colored("No matches found.", RED))
            return
            
        for path, score, snippets in results:
            print(colored(f"\nDocument: {path} [Score: {score:.5f}]", BOLD + CYAN))
            for line_num, snippet in snippets:
                print(f"  L{line_num}: {snippet}")
        print()
    else:
        interactive_search_loop(engine)

if __name__ == "__main__":
    main()
