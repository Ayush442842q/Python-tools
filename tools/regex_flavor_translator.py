#!/usr/bin/env python3
"""
Regex Flavor & Dialect Translator
Author: Antigravity

Analyzes regex patterns and translates/portability-checks them across
various regular expression engines: Python (re), JavaScript (ECMAScript),
PCRE, Rust (regex), and Go (regexp).
"""

import argparse
import re
import sys
from typing import Dict, List, Tuple, Any

class RegexFeatureDetector:
    """Analyzes a regex pattern for specific engine features and syntax."""
    def __init__(self, pattern: str):
        self.pattern = pattern
        self.features = {
            "python_named_group": False,  # (?P<name>...)
            "standard_named_group": False, # (?<name>...)
            "lookahead_positive": False,  # (?=...)
            "lookahead_negative": False,  # (?!...)
            "lookbehind_positive": False, # (?<=...)
            "lookbehind_negative": False, # (?<!...)
            "backreferences": False,      # \1, \2, etc.
            "possessive_quantifier": False,# *+, ++, ?+, {m,n}+
            "conditional_pattern": False,  # (?(group)...)
            "unicode_property": False,     # \p{...}, \P{...}
            "non_capturing_group": False,  # (?:...)
            "atomic_group": False,         # (?>...)
        }
        self.analyze()

    def analyze(self):
        p = self.pattern
        
        # Detect Python named group (?P<name>...)
        if re.search(r'\(\?P<[a-zA-Z_][a-zA-Z0-9_]*>', p):
            self.features["python_named_group"] = True
            
        # Detect Standard named group (?<name>...)
        # Negative check to make sure it's not lookbehind (?<=...)
        if re.search(r'\(\?<[a-zA-Z_][a-zA-Z0-9_]*>', p):
            self.features["standard_named_group"] = True

        # Detect positive lookahead (?=...)
        if re.search(r'\(\?=', p):
            self.features["lookahead_positive"] = True
            
        # Detect negative lookahead (?!...)
        if re.search(r'\(\?!', p):
            self.features["lookahead_negative"] = True
            
        # Detect positive lookbehind (?<=...)
        if re.search(r'\(\?<=', p):
            self.features["lookbehind_positive"] = True
            
        # Detect negative lookbehind (?<!...)
        if re.search(r'\(\?<!', p):
            self.features["lookbehind_negative"] = True

        # Detect backreferences (like \1, \2, \g<1> but not inside character class or escaped digits)
        # Avoid matching \0 (octal) or simply escaped chars. Let's look for \1-\9
        if re.search(r'(?<!\\)\\[1-9]\b', p) or re.search(r'\\g<[a-zA-Z0-9_]+>', p):
            self.features["backreferences"] = True

        # Detect possessive quantifiers: *+, ++, ?+, {m,n}+
        if re.search(r'(?:[+*?]|}\s*)\+', p):
            self.features["possessive_quantifier"] = True

        # Detect conditional pattern: (?(group)yes|no)
        if re.search(r'\(\?\([a-zA-Z0-9_]+\)', p):
            self.features["conditional_pattern"] = True

        # Detect Unicode properties: \p{...} or \P{...}
        if re.search(r'\\[pP]\{[a-zA-Z0-9_=-]+\}', p):
            self.features["unicode_property"] = True

        # Detect non-capturing group: (?:...)
        # Make sure not lookahead/lookbehind
        if re.search(r'\(\?:(?!<=|<!|=|!)', p):
            self.features["non_capturing_group"] = True

        # Detect atomic group: (?>...)
        if re.search(r'\(\?>', p):
            self.features["atomic_group"] = True

def translate_pattern(pattern: str, target: str) -> Tuple[str, List[str]]:
    """Translates pattern syntax and returns translation + list of warning notes."""
    translated = pattern
    warnings = []
    
    detector = RegexFeatureDetector(pattern)

    if target == "javascript":
        # Convert Python named groups (?P<name>...) to JS (?<name>...)
        translated = re.sub(r'\(\?P<([a-zA-Z_][a-zA-Z0-9_]*)>', r'(?<\1>', translated)
        
        # Warn if backreferences use Python format \g<name>
        if "\\g<" in pattern:
            warnings.append("Python style backreference '\\g<name>' is not supported in JS. Use '\\k<name>' instead.")
            translated = re.sub(r'\\g<([a-zA-Z_][a-zA-Z0-9_]*)>', r'\\k<\1>', translated)
            
        if detector.features["possessive_quantifier"]:
            warnings.append("JS does not support possessive quantifiers (*+, ++, ?+). Replace with greedy quantifiers and lookaheads if absolute backtracking control is required.")
        if detector.features["conditional_pattern"]:
            warnings.append("JS does not support conditional patterns (?(group)...). Simplify your logic.")
        if detector.features["atomic_group"]:
            warnings.append("JS does not support atomic groups (?>...).")
            
    elif target == "python":
        # Convert JS named groups (?<name>...) to Python (?P<name>...)
        # We need to be careful not to match (?<=...) or (?<!...)
        # Let's replace (?<name>...) where name is word characters
        translated = re.sub(r'\(\?<([a-zA-Z_][a-zA-Z0-9_]*)>', r'(?P<\1>', translated)
        
        if detector.features["possessive_quantifier"]:
            warnings.append("Python 're' module does not support possessive quantifiers. Consider using the third-party 'regex' library or rewriting using lookaheads.")
        if detector.features["atomic_group"]:
            warnings.append("Python 're' module does not support atomic groups (?>...). Use the third-party 'regex' library.")
        if detector.features["unicode_property"]:
            warnings.append(r"Python 're' module lacks native \p{...} unicode properties. Use explicit character sets or the third-party 'regex' library.")
        if detector.features["conditional_pattern"]:
            # Python re actually supports (?(id/name)yes|no)
            pass

    elif target == "pcre":
        # PCRE is highly capable, supports both (?P<name>) and (?<name>)
        # PCRE supports atomic groups, possessive quantifiers, lookarounds, conditionals
        pass

    elif target in ("rust", "go"):
        # Rust and Go do not support: Lookarounds, Backreferences, Atomic groups, Conditionals
        # Convert JS named groups to standard (?P<name>...)
        translated = re.sub(r'\(\?<([a-zA-Z_][a-zA-Z0-9_]*)>', r'(?P<\1>', translated)
        
        if detector.features["lookahead_positive"] or detector.features["lookahead_negative"]:
            warnings.append(f"Lookahead assertions are UNSUPPORTED in {target.capitalize()} regex engine.")
        if detector.features["lookbehind_positive"] or detector.features["lookbehind_negative"]:
            warnings.append(f"Lookbehind assertions are UNSUPPORTED in {target.capitalize()} regex engine.")
        if detector.features["backreferences"]:
            warnings.append(f"Backreferences (like \\1 or \\k<name>) are UNSUPPORTED in {target.capitalize()} regex engine.")
        if detector.features["possessive_quantifier"]:
            warnings.append(f"Possessive quantifiers (*+, ++, ?+) are UNSUPPORTED in {target.capitalize()} regex engine.")
        if detector.features["conditional_pattern"]:
            warnings.append(f"Conditional patterns are UNSUPPORTED in {target.capitalize()} regex engine.")
        if detector.features["atomic_group"]:
            warnings.append(f"Atomic groups (?>...) are UNSUPPORTED in {target.capitalize()} regex engine.")
            
        if target == "go":
            # Go regexp doesn't support lookaround, atomic, backreferences.
            # Also doesn't support \p for some unicode scripts unless it matches Go conventions.
            pass

    return translated, warnings

def check_compatibility(detector: RegexFeatureDetector) -> Dict[str, Dict[str, Any]]:
    """Calculates compatibility stats for each engine."""
    engines = ["python", "javascript", "pcre", "rust", "go"]
    status = {}
    
    for eng in engines:
        unsupported = []
        f = detector.features
        
        if eng == "python":
            if f["possessive_quantifier"]:
                unsupported.append("Possessive Quantifiers (*+, ++, etc.)")
            if f["atomic_group"]:
                unsupported.append("Atomic Groups (?>...)")
            if f["unicode_property"]:
                unsupported.append("Unicode Properties (\\p{...})")
                
        elif eng == "javascript":
            if f["possessive_quantifier"]:
                unsupported.append("Possessive Quantifiers (*+, ++, etc.)")
            if f["atomic_group"]:
                unsupported.append("Atomic Groups (?>...)")
            if f["conditional_pattern"]:
                unsupported.append("Conditional Patterns (?(group)...)")
            # Standard JS supports lookarounds since ES2018
            
        elif eng == "pcre":
            # PCRE supports everything listed
            pass
            
        elif eng in ("rust", "go"):
            if f["lookahead_positive"] or f["lookahead_negative"]:
                unsupported.append("Lookahead Assertions ((?=...), (?!...))")
            if f["lookbehind_positive"] or f["lookbehind_negative"]:
                unsupported.append("Lookbehind Assertions ((?<=...), (?<!...))")
            if f["backreferences"]:
                unsupported.append("Backreferences (\\1, \\k<...>)")
            if f["possessive_quantifier"]:
                unsupported.append("Possessive Quantifiers (*+, ++, etc.)")
            if f["atomic_group"]:
                unsupported.append("Atomic Groups (?>...)")
            if f["conditional_pattern"]:
                unsupported.append("Conditional Patterns (?(group)...)")

        score = 100 - (len(unsupported) * 15)
        score = max(score, 0)
        if not unsupported:
            score = 100
            
        status[eng] = {
            "score": score,
            "compatible": len(unsupported) == 0,
            "unsupported": unsupported
        }
    return status

def main():
    parser = argparse.ArgumentParser(
        description="Regex Flavor & Dialect Translator - Audit regex features and translate patterns between engines."
    )
    parser.add_argument("pattern", help="The regular expression pattern to analyze")
    args = parser.parse_args()

    pattern = args.pattern
    print(f"Analyzing Pattern: {pattern}\n")
    
    detector = RegexFeatureDetector(pattern)
    
    print("Detected Regex Syntaxes/Features:")
    has_features = False
    for feat, found in detector.features.items():
        if found:
            print(f"  - {feat.replace('_', ' ').title()}: Yes")
            has_features = True
    if not has_features:
        print("  - Standard features only (highly compatible)")

    compat = check_compatibility(detector)
    
    print("\n" + "=" * 80)
    print(" ENGINE COMPATIBILITY SCORES ".center(80, "="))
    print("=" * 80)
    
    for eng, info in compat.items():
        symbol = "✓" if info["compatible"] else "✗"
        print(f"  {eng.capitalize():15} | Compatibility: {info['score']:3d}% | {symbol}")
        if info["unsupported"]:
            print(f"    Unsupported features in native {eng.capitalize()}:")
            for u in info["unsupported"]:
                print(f"      * {u}")
        print("  " + "-" * 74)

    print("\n" + "=" * 80)
    print(" DIALECT TRANSLATIONS ".center(80, "="))
    print("=" * 80)
    
    for eng in ["python", "javascript", "pcre", "rust", "go"]:
        trans, warnings = translate_pattern(pattern, eng)
        print(f"\nTarget: {eng.capitalize()}")
        print(f"  Pattern: {trans}")
        if warnings:
            print("  Warnings / Migration notes:")
            for w in warnings:
                print(f"    - {w}")

if __name__ == "__main__":
    main()
