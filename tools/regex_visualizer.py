#!/usr/bin/env python3
"""
Regex Visualizer - Parse a regular expression and generate an AST tree with a step-by-step explanation.

Usage:
    python tools/regex_visualizer.py "<REGEX_PATTERN>"
"""

import sys
import argparse
import warnings
# Suppress DeprecationWarning for sre_parse in newer Python versions
warnings.filterwarnings("ignore", category=DeprecationWarning)
import sre_parse
import sre_constants

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

def get_op_name(op):
    """Convert operators to friendly strings"""
    if isinstance(op, str):
        return op
    return str(op).split('.')[-1]

def format_char(char_code):
    """Format character codes nicely"""
    if 32 <= char_code <= 126:
        return f"'{chr(char_code)}'"
    elif char_code == 9:
        return "'\\t' (tab)"
    elif char_code == 10:
        return "'\\n' (newline)"
    elif char_code == 13:
        return "'\\r' (carriage return)"
    else:
        return f"char code {char_code} (0x{char_code:02X})"

def explain_node(op, av):
    """Provide a friendly text explanation of a node"""
    op_name = get_op_name(op)
    
    if op_name == "LITERAL":
        return f"Match literal character {format_char(av)}"
    elif op_name == "NOT_LITERAL":
        return f"Match any character EXCEPT {format_char(av)}"
    elif op_name == "ANY":
        return "Match any single character (except newline)"
    elif op_name == "AT":
        at_loc = get_op_name(av)
        explanations = {
            "AT_BEGINNING": "Assert position at the beginning of the string",
            "AT_BEGINNING_STRING": "Assert position at the beginning of the string",
            "AT_END": "Assert position at the end of the string",
            "AT_END_STRING": "Assert position at the end of the string",
            "AT_BOUNDARY": "Assert position at a word boundary",
            "AT_NON_BOUNDARY": "Assert position not at a word boundary"
        }
        return explanations.get(at_loc, f"Assertion: {at_loc}")
    elif op_name == "MAXREPEAT" or op_name == "MINREPEAT":
        min_rep, max_rep, _ = av
        repeat_type = "greedy" if op_name == "MAXREPEAT" else "non-greedy"
        max_str = "infinity" if max_rep == sre_constants.MAXREPEAT else str(max_rep)
        
        if min_rep == 0 and max_rep == 1:
            return f"Optional ({repeat_type}, 0 or 1 time)"
        elif min_rep == 0 and max_rep == sre_constants.MAXREPEAT:
            return f"Repeat 0 or more times ({repeat_type}, '*')"
        elif min_rep == 1 and max_rep == sre_constants.MAXREPEAT:
            return f"Repeat 1 or more times ({repeat_type}, '+')"
        elif min_rep == max_rep:
            return f"Repeat exactly {min_rep} times"
        else:
            return f"Repeat between {min_rep} and {max_str} times ({repeat_type})"
    elif op_name == "SUBPATTERN":
        group_id = av[0]
        name = av[3] if len(av) > 3 else None
        if name:
            return f"Capture Group #{group_id} (named '{name}')"
        return f"Capture Group #{group_id}"
    elif op_name == "IN":
        return "Match one of the characters in the set"
    elif op_name == "RANGE":
        return f"Range from {format_char(av[0])} to {format_char(av[1])}"
    elif op_name == "CATEGORY":
        cat_type = get_op_name(av)
        categories = {
            "CATEGORY_DIGIT": "Any digit [0-9]",
            "CATEGORY_NOT_DIGIT": "Any non-digit [^0-9]",
            "CATEGORY_SPACE": "Any whitespace character [ \\t\\n\\r\\f\\v]",
            "CATEGORY_NOT_SPACE": "Any non-whitespace character",
            "CATEGORY_WORD": "Any word character [a-zA-Z0-9_]",
            "CATEGORY_NOT_WORD": "Any non-word character",
        }
        return categories.get(cat_type, f"Character category: {cat_type}")
    elif op_name == "BRANCH":
        return "Alternation (OR)"
    elif op_name == "NEGATE":
        return "Negate the character set (match none of these)"
    
    return f"{op_name}: {av}"

def traverse_ast(subpattern, prefix="", is_last=True, explanation_list=None):
    """
    Recursively prints the AST tree and builds a linear step-by-step list of explanations.
    """
    if explanation_list is None:
        explanation_list = []

    # If it's a SubPattern wrapper, unpack it
    if hasattr(subpattern, "data"):
        items = subpattern.data
    elif isinstance(subpattern, list):
        items = subpattern
    else:
        items = [subpattern]

    for i, item in enumerate(items):
        op, av = item
        op_name = get_op_name(op)
        item_is_last = (i == len(items) - 1)
        
        connector = "└─ " if item_is_last else "├─ "
        node_text = f"{BOLD}{CYAN}{op_name}{RESET}"
        
        # Format display text
        display_val = ""
        if op_name == "LITERAL":
            display_val = f" {format_char(av)}"
        elif op_name == "NOT_LITERAL":
            display_val = f" NOT {format_char(av)}"
        elif op_name == "AT":
            display_val = f" {get_op_name(av)}"
        elif op_name == "SUBPATTERN":
            group_id = av[0]
            display_val = f" (Group {group_id})"
        elif op_name == "MAXREPEAT" or op_name == "MINREPEAT":
            min_rep, max_rep, _ = av
            max_str = "inf" if max_rep == sre_constants.MAXREPEAT else str(max_rep)
            display_val = f" ({min_rep} to {max_str})"
            
        print(f"{prefix}{connector}{node_text}{display_val}")
        
        # Add explanation to linear description
        explanation_list.append((prefix + connector, explain_node(op, av)))
        
        new_prefix = prefix + ("   " if item_is_last else "│  ")
        
        # Descend into children
        if op_name in ("MAXREPEAT", "MINREPEAT"):
            traverse_ast(av[2], new_prefix, True, explanation_list)
        elif op_name == "SUBPATTERN":
            # av is (group_id, add_flags, del_flags, subpattern)
            traverse_ast(av[3], new_prefix, True, explanation_list)
        elif op_name == "IN":
            # av is list of character sets
            traverse_ast(av, new_prefix, True, explanation_list)
        elif op_name == "BRANCH":
            # av is (None, list of subpatterns)
            branches = av[1]
            for idx, branch in enumerate(branches):
                branch_is_last = (idx == len(branches) - 1)
                branch_connector = "└─ Option: " if branch_is_last else "├─ Option: "
                print(f"{new_prefix}{branch_connector}")
                traverse_ast(branch, new_prefix + ("   " if branch_is_last else "│  "), True, explanation_list)

    return explanation_list

def main():
    parser = argparse.ArgumentParser(
        description="Regex Visualizer - Visualize regular expressions as a hierarchical AST tree with structural explanations."
    )
    parser.add_argument("pattern", help="The regular expression pattern to visualize.")
    args = parser.parse_args()

    # Enable Windows ANSI escape codes support
    if sys.platform == "win32":
        import os
        os.system("color")

    pattern = args.pattern
    print(f"\n{BOLD}{YELLOW}Regex Pattern:{RESET} {BOLD}{pattern}{RESET}\n")

    try:
        parsed = sre_parse.parse(pattern)
    except sre_parse.error as e:
        print(f"{RED}{BOLD}Regex Parsing Error:{RESET} {e}")
        # Print pointer to where the error occurred if possible
        if hasattr(e, "pos") and e.pos is not None:
            print(f"  {pattern}")
            print("  " + " " * e.pos + "^")
        return 1

    print(f"{BOLD}{BLUE}Hierarchy AST Tree:{RESET}")
    explanations = []
    traverse_ast(parsed, "", True, explanations)
    
    print(f"\n{BOLD}{BLUE}Plain English Explanation:{RESET}")
    for idx, (conn, desc) in enumerate(explanations):
        # We strip the AST connectors to show a clean bullet list
        clean_conn = conn.replace("├─ ", "• ").replace("└─ ", "• ").replace("│  ", "  ").replace("   ", "  ")
        # Bold the bullet point
        print(f"  {clean_conn}{desc}")

    print()
    return 0

if __name__ == "__main__":
    sys.exit(main())
