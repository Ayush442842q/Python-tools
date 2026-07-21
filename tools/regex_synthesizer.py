#!/usr/bin/env python3
"""
Regex Synthesizer

A CLI tool that infers and generates regular expressions based on positive and negative string examples.
It analyzes patterns, common prefixes/suffixes, character classes, and repeat counts to suggest regexes.

Usage:
    python regex_synthesizer.py --pos "abc-123" "def-456" --neg "123-abc"
"""

import sys
import argparse
import re
from typing import List, Dict, Tuple, Set

def analyze_character(char: str) -> str:
    """Classify character into regex class."""
    if char.isdigit():
        return r"\d"
    elif char.isalpha():
        if char.isupper():
            return "[A-Z]"
        else:
            return "[a-z]"
    elif char.isspace():
        return r"\s"
    elif char in r".^$*+?{}[]\|()":
        return "\\" + char
    else:
        return re.escape(char)

def get_character_class_name(char_cls: str) -> str:
    """Helper to convert regex token class back to friendly text."""
    if char_cls == r"\d": return "digit"
    if char_cls == "[A-Z]": return "uppercase letter"
    if char_cls == "[a-z]": return "lowercase letter"
    if char_cls == r"\s": return "whitespace"
    return "literal"

def get_shared_prefix(strings: List[str]) -> str:
    """Find the longest shared prefix among all positive examples."""
    if not strings:
        return ""
    prefix = strings[0]
    for string in strings[1:]:
        while not string.startswith(prefix):
            prefix = prefix[:-1]
            if not prefix:
                break
    return prefix

def get_shared_suffix(strings: List[str]) -> str:
    """Find the longest shared suffix among all positive examples."""
    if not strings:
        return ""
    suffix = strings[0]
    for string in strings[1:]:
        while not string.endswith(suffix):
            suffix = suffix[1:]
            if not suffix:
                break
    return suffix

def generalize_classes(strings: List[str]) -> List[Tuple[str, int, int]]:
    """Convert a list of strings to a generalized list of (token_class, min_count, max_count) triples.
    Assumes strings are somewhat structural-aligned.
    """
    if not strings:
        return []
    
    # Tokenize each string into sequences of classes
    token_sequences = []
    for s in strings:
        seq = []
        for char in s:
            seq.append(analyze_character(char))
        
        # Merge consecutive identical classes into (class, count)
        merged = []
        if seq:
            curr_cls = seq[0]
            curr_count = 1
            for cls in seq[1:]:
                if cls == curr_cls:
                    curr_count += 1
                else:
                    merged.append((curr_cls, curr_count))
                    curr_cls = cls
                    curr_count = 1
            merged.append((curr_cls, curr_count))
        token_sequences.append(merged)
    
    # If all strings tokenized to the same sequence length, we can align them directly
    first_seq = token_sequences[0]
    is_aligned = all(len(seq) == len(first_seq) for seq in token_sequences)
    
    final_pattern = []
    if is_aligned:
        for col_idx in range(len(first_seq)):
            col_tokens = [seq[col_idx] for seq in token_sequences]
            classes = {t[0] for t in col_tokens}
            min_count = min(t[1] for t in col_tokens)
            max_count = max(t[1] for t in col_tokens)
            
            # Generalize class
            if len(classes) == 1:
                # Same class (e.g. all digits)
                cls = list(classes)[0]
            else:
                # Mixed classes (e.g. uppercase and lowercase)
                if all(c in ("[a-z]", "[A-Z]", r"\w") for c in classes):
                    cls = "[a-zA-Z]"
                elif all(c in ("[a-z]", "[A-Z]", r"\d", r"\w") for c in classes):
                    cls = r"\w"
                else:
                    cls = "."
            
            final_pattern.append((cls, min_count, max_count))
    else:
        # Fallback: simple character-by-character alignment
        # Or just find common delimiters and generalize what's between them
        pass
        
    return final_pattern

def generate_patterns(pos: List[str]) -> List[Dict[str, str]]:
    """Generate various regex suggestions based on positive examples."""
    patterns = []
    
    # 1. Exact list match (naive)
    naive = "^(" + "|".join(re.escape(p) for p in pos) + ")$"
    patterns.append({
        "name": "Exact Matches Only",
        "pattern": naive,
        "description": "Matches only the provided positive examples exactly."
    })
    
    # 2. General structural inference
    structural_tokens = generalize_classes(pos)
    if structural_tokens:
        parts_precise = []
        parts_loose = []
        
        for cls, min_c, max_c in structural_tokens:
            # Precise count
            if min_c == max_c:
                count_str = f"{{{min_c}}}" if min_c > 1 else ""
            else:
                count_str = f"{{{min_c},{max_c}}}"
            
            # Loose count
            loose_count_str = "+" if min_c > 0 else "*"
            
            # Simplify alpha ranges
            if cls == "[a-z]" or cls == "[A-Z]":
                cls = "[a-zA-Z]"
                
            parts_precise.append(f"{cls}{count_str}")
            parts_loose.append(f"{cls}{loose_count_str}")
            
        pattern_precise = "^" + "".join(parts_precise) + "$"
        pattern_loose = "^" + "".join(parts_loose) + "$"
        
        patterns.append({
            "name": "Precise Structured Pattern",
            "pattern": pattern_precise,
            "description": "Infers length constraints and character classes from input format."
        })
        
        patterns.append({
            "name": "Flexible Structured Pattern",
            "pattern": pattern_loose,
            "description": "Uses wildcards like '+' and '*' for flexible lengths."
        })

    # 3. Simple character frequency pattern
    all_chars = set("".join(pos))
    char_cls = ""
    if all(c.isdigit() for c in all_chars):
        char_cls = r"\d+"
    elif all(c.isalpha() for c in all_chars):
        char_cls = r"[a-zA-Z]+"
    elif all(c.isalnum() or c in "_-" for c in all_chars):
        char_cls = r"[\w\-]+"
    else:
        char_cls = r".+"
        
    patterns.append({
        "name": "General Alphanumeric / Character Class",
        "pattern": f"^{char_cls}$",
        "description": "A broad pattern matching the type of characters found in positive examples."
    })
    
    return patterns

def main():
    parser = argparse.ArgumentParser(
        description="Regex Synthesizer: Infer and generate regular expressions from string examples.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--pos", "-p",
        nargs="+",
        required=True,
        help="One or more positive examples that the regex SHOULD match."
    )
    parser.add_argument(
        "--neg", "-n",
        nargs="+",
        default=[],
        help="One or more negative examples that the regex SHOULD NOT match."
    )
    parser.add_argument(
        "--test", "-t",
        nargs="+",
        default=[],
        help="Additional strings to test against the generated regexes."
    )
    
    args = parser.parse_args()
    
    print("\033[94m[+] Analyzing positive examples:\033[0m")
    for s in args.pos:
        print(f"  - {s}")
        
    if args.neg:
        print("\033[93m[+] Analyzing negative examples (to exclude):\033[0m")
        for s in args.neg:
            print(f"  - {s}")
            
    print("\n\033[92m[+] Synthesizing Candidate Patterns:\033[0m\n")
    
    candidates = generate_patterns(args.pos)
    
    for idx, cand in enumerate(candidates, 1):
        pat_str = cand["pattern"]
        name = cand["name"]
        desc = cand["description"]
        
        # Test candidate regex against positives
        try:
            compiled = re.compile(pat_str)
        except re.error as e:
            print(f"Error compiling pattern: {pat_str} ({e})")
            continue
            
        pos_match = all(compiled.match(p) is not None for p in args.pos)
        
        # Test against negatives
        neg_fail = []
        if args.neg:
            for n in args.neg:
                if compiled.match(n) is not None:
                    neg_fail.append(n)
        
        # Format output
        status_color = "\033[92m[PASSED]\033[0m"
        if not pos_match:
            status_color = "\033[91m[FAILED POSITIVE MATCH]\033[0m"
        elif neg_fail:
            status_color = f"\033[91m[FAILED - Matches negatives: {', '.join(neg_fail)}]\033[0m"
            
        print(f"{idx}. \033[1m{name}\033[0m  {status_color}")
        print(f"   Pattern:     \033[96m{pat_str}\033[0m")
        print(f"   Description: {desc}")
        
        # Test additional test arguments
        if args.test:
            print("   Tests:")
            for t in args.test:
                m = "MATCH" if compiled.match(t) else "NO MATCH"
                col = "\033[92m" if m == "MATCH" else "\033[90m"
                print(f"     - '{t}': {col}{m}\033[0m")
        print()

if __name__ == "__main__":
    main()
