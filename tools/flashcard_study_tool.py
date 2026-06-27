#!/usr/bin/env python3
"""
Flashcard Study Tool

An interactive CLI-based flashcard study system that parses questions/answers from
Markdown or text files, tracks learning progress using the Leitner box spaced
repetition system, and exports decks to Anki-compatible CSV formats.

Usage:
    python tools/flashcard_study_tool.py <file> [options]
"""

import sys
import os
import re
import json
import argparse
import random
from pathlib import Path

# Terminal colors
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"

def print_banner():
    banner = f"""
{BLUE}{BOLD}=========================================================
      🗂️   FLASHCARD CLI STUDY SYSTEM (LEITNER BOX)  🗂️
========================================================={RESET}
"""
    print(banner)

def parse_flashcards(file_path):
    """Parses Q&A flashcards from a file. Supports Markdown & text patterns."""
    if not os.path.exists(file_path):
        print(f"{RED}Error: File '{file_path}' not found.{RESET}", file=sys.stderr)
        return []

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    cards = []
    
    # Method 1: Check for Markdown Headings
    # e.g. ### Q: What is Python?
    #      A: An interpreted, high-level language.
    markdown_qa = re.findall(
        r'(?:^|\n)#+\s*(?:Q|Question):\s*(.*?)\n(?:A|Answer):\s*(.*?)(?=\n#+|$)',
        content, re.IGNORECASE | re.DOTALL
    )
    for q, a in markdown_qa:
        cards.append({"question": q.strip(), "answer": a.strip()})

    # Method 2: Check for Markdown List items
    # e.g. - **Q**: Question text
    #      - **A**: Answer text
    if not cards:
        bullet_qa = re.findall(
            r'-\s*\*\*Q\*\*:\s*(.*?)\n\s*-\s*\*\*A\*\*:\s*(.*?)(?=\n\s*-\s*\*\*Q\*\*|\n\n|\Z)',
            content, re.IGNORECASE | re.DOTALL
        )
        for q, a in bullet_qa:
            cards.append({"question": q.strip(), "answer": a.strip()})

    # Method 3: Standard block parsing
    # e.g., Q: Question
    #       A: Answer
    if not cards:
        blocks = re.split(r'\n\s*\n', content)
        for block in blocks:
            q_match = re.search(r'^\s*(?:Q|Question):\s*(.*?)$', block, re.IGNORECASE | re.MULTILINE)
            a_match = re.search(r'^\s*(?:A|Answer):\s*(.*?)$', block, re.IGNORECASE | re.MULTILINE | re.DOTALL)
            if q_match and a_match:
                cards.append({
                    "question": q_match.group(1).strip(),
                    "answer": a_match.group(1).strip()
                })

    # Fallback: line-by-line CSV-like parsing if colon separated
    if not cards:
        for i, line in enumerate(content.splitlines(), 1):
            if '|' in line:
                parts = line.split('|', 1)
                cards.append({"question": parts[0].strip(), "answer": parts[1].strip()})

    return cards

def load_progress(state_file):
    """Loads Leitner box states from a JSON file."""
    if os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"{YELLOW}Warning: Could not parse state file: {e}. Starting fresh.{RESET}")
    return {}

def save_progress(state_file, progress):
    """Saves Leitner box states to a JSON file."""
    try:
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(progress, f, indent=4)
    except Exception as e:
        print(f"{RED}Error saving progress: {e}{RESET}", file=sys.stderr)

def run_study_session(cards, state_file=None):
    """Runs interactive Leitner box study session."""
    if not cards:
        print(f"{RED}No valid flashcards found to study.{RESET}")
        return

    progress = load_progress(state_file) if state_file else {}
    
    # Initialize cards into boxes (1 to 5)
    # Leitner boxes structure: card_question -> box_number (1-5)
    box_mapping = {}
    for card in cards:
        q = card["question"]
        box_mapping[q] = progress.get(q, 1)

    print(f"Loaded {BOLD}{len(cards)}{RESET} flashcards.")
    print(f"Boxes status: " + ", ".join([
        f"Box {i}: {list(box_mapping.values()).count(i)}" for i in range(1, 6)
    ]))
    
    session_cards = cards.copy()
    random.shuffle(session_cards)

    correct_count = 0
    total_count = 0

    print(f"\n{CYAN}Starting study session. Press Ctrl+C to exit at any time.{RESET}")
    print(f"For each card, view the question, guess the answer in your head, then press Enter to reveal the true answer.\n")

    try:
        for idx, card in enumerate(session_cards, 1):
            q = card["question"]
            a = card["answer"]
            current_box = box_mapping[q]

            print(f"{BOLD}--- Card {idx}/{len(session_cards)} (Box {current_box}) ---{RESET}")
            print(f"{YELLOW}Question:{RESET} {q}")
            input("Press Enter to reveal the answer...")
            
            print(f"{GREEN}Answer:{RESET} {a}")
            
            while True:
                response = input("Did you get it right? (y/n): ").strip().lower()
                if response in ('y', 'yes', 'n', 'no'):
                    break
                print("Please enter 'y' or 'n'.")

            total_count += 1
            if response in ('y', 'yes'):
                correct_count += 1
                # Move up box if not already in Box 5
                new_box = min(5, current_box + 1)
                box_mapping[q] = new_box
                print(f"{GREEN}Correct! Card promoted to Box {new_box}. 🎉{RESET}\n")
            else:
                # Demote back to Box 1 (Leitner standard rule)
                box_mapping[q] = 1
                print(f"{RED}Incorrect. Card demoted back to Box 1. 📚{RESET}\n")

            if state_file:
                # Update progress dict and save
                progress[q] = box_mapping[q]
                save_progress(state_file, progress)

    except KeyboardInterrupt:
        print(f"\n\n{YELLOW}Session ended early by user.{RESET}")

    # Session stats
    if total_count > 0:
        accuracy = (correct_count / total_count) * 100
        print(f"--- Session Summary ---")
        print(f"Cards Studied : {total_count}")
        print(f"Correct Answers: {correct_count} ({accuracy:.1f}%)")
        print(f"Progress saved to state file.")
    else:
        print("No cards were studied.")

def export_to_anki(cards, output_path):
    """Exports cards to a CSV format that Anki can import directly."""
    import csv
    try:
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            # Anki standard import structure: Front, Back
            for card in cards:
                writer.writerow([card["question"], card["answer"]])
        print(f"{GREEN}Exported {len(cards)} flashcards to Anki CSV: '{output_path}'{RESET}")
    except Exception as e:
        print(f"{RED}Failed to export to Anki CSV: {e}{RESET}", file=sys.stderr)

def create_cards_interactively(file_path):
    """Interactively creates new Q&A cards and appends them to file."""
    print(f"{CYAN}Entering Interactive Card Creator Mode.{RESET}")
    print(f"Saving to: {file_path}")
    print(f"Type 'exit' or Ctrl+C to stop.\n")
    
    card_count = 0
    try:
        while True:
            print(f"{BOLD}Card #{card_count + 1}{RESET}")
            q = input("Enter Question: ").strip()
            if not q or q.lower() == 'exit':
                break
            
            a = input("Enter Answer: ").strip()
            if not a or a.lower() == 'exit':
                break

            # Append to file in standard block format
            with open(file_path, "a", encoding="utf-8") as f:
                f.write(f"\nQ: {q}\nA: {a}\n")
            
            card_count += 1
            print(f"{GREEN}Card added!{RESET}\n")

    except KeyboardInterrupt:
        pass
    
    print(f"\n{GREEN}Added {card_count} new flashcards to '{file_path}'.{RESET}")

def main():
    parser = argparse.ArgumentParser(
        description="Flashcard CLI Study Tool - Study flashcards using Leitner spaced repetition system.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("file", help="Path to flashcards file (Markdown or Text)")
    parser.add_argument("--state", "-s", help="Path to JSON state file to persist progress")
    parser.add_argument("--anki", "-a", help="Export deck to Anki-compatible CSV at this path")
    parser.add_argument("--create", "-c", action="store_true", help="Interactively create cards and append to file")
    
    args = parser.parse_args()
    
    print_banner()

    if args.create:
        create_cards_interactively(args.file)
        return 0

    cards = parse_flashcards(args.file)
    if not cards:
        print(f"{RED}No flashcards found in file. Ensure the file has Q: / A: lines.{RESET}")
        return 1

    if args.anki:
        export_to_anki(cards, args.anki)
        return 0

    # Start study session
    run_study_session(cards, state_file=args.state)
    return 0

if __name__ == "__main__":
    sys.exit(main())
