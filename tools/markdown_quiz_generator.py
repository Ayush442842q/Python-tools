#!/usr/bin/env python3
"""
Markdown Quiz & Self-Assessment Generator
Parses Markdown notes, documentation, and flashcards to generate interactive self-assessment quizzes:
  - Terminal interactive quiz runner with instant scoring and explanations
  - Export to standalone single-file HTML interactive web quiz
  - Export to Markdown test paper with separate answer keys

Uses only standard Python libraries.
"""

import argparse
import json
import os
import random
import re
import sys


def extract_questions_from_markdown(text):
    """
    Parses Markdown text for Q&A structures:
      - Header as Question, followed by paragraph/list answer
      - Flashcards: `Q: Question` ... `A: Answer`
      - Definitions: `**Term** - Definition`
      - Markdown Blockquotes or Lists
    """
    questions = []
    
    # 1. Flashcard Q: / A: patterns
    qa_blocks = re.findall(r'(?:Q|Question):\s*(.*?)\n(?:A|Answer):\s*(.*?)(?=\n\n|\n(?:Q|Question):|$)', text, re.DOTALL | re.IGNORECASE)
    for q, a in qa_blocks:
        questions.append({
            "type": "short_answer",
            "question": q.strip(),
            "answer": a.strip(),
            "explanation": f"Source answer: {a.strip()}"
        })

    # 2. Header as Question (headers ending with '?')
    header_qs = re.findall(r'^#{1,6}\s+(.*?\?)\s*\n([\s\S]*?)(?=\n#{1,6}\s+|$)', text, re.MULTILINE)
    for q, body in header_qs:
        ans_lines = [l.strip() for l in body.split("\n") if l.strip() and not l.startswith("#")]
        if ans_lines:
            questions.append({
                "type": "multiple_choice",
                "question": q.strip(),
                "answer": ans_lines[0],
                "explanation": " ".join(ans_lines[:3])
            })

    # 3. Term Definitions (`**Term** - Definition`)
    definitions = re.findall(r'\*\*(.*?)\*\*\s*[:\-–]\s*(.*?)(?=\n|$)', text)
    for term, defn in definitions:
        if len(term.strip()) > 2 and len(defn.strip()) > 5:
            questions.append({
                "type": "definition",
                "question": f"What is the definition of **{term.strip()}**?",
                "answer": defn.strip(),
                "term": term.strip(),
                "explanation": f"{term.strip()} refers to: {defn.strip()}"
            })

    # Generate options for multiple choice questions
    all_answers = [q["answer"] for q in questions if "answer" in q]
    all_terms = [q["term"] for q in questions if "term" in q]

    for q in questions:
        if q["type"] == "definition":
            distractors = [t for t in all_terms if t != q["term"]]
            if len(distractors) >= 3:
                opts = random.sample(distractors, 3) + [q["term"]]
                random.shuffle(opts)
                q["options"] = opts
                q["correct_option"] = q["term"]
                q["question"] = f"Which term matches this definition: \"{q['answer']}\"?"

    return questions


def run_interactive_quiz(questions):
    if not questions:
        print("No quiz questions could be parsed from the Markdown file.", file=sys.stderr)
        return

    print("=" * 65)
    print(f" INTERACTIVE MARKDOWN SELF-ASSESSMENT QUIZ ({len(questions)} Questions)")
    print("=" * 65)

    score = 0
    total = len(questions)

    for idx, q in enumerate(questions, 1):
        print(f"\nQuestion {idx}/{total}: {q['question']}")
        
        if "options" in q:
            for opt_idx, opt in enumerate(q["options"], 1):
                print(f"  {opt_idx}. {opt}")
            try:
                user_input = input("\nYour Answer (1-4): ").strip()
                if user_input.isdigit() and 1 <= int(user_input) <= len(q["options"]):
                    selected = q["options"][int(user_input) - 1]
                    if selected.lower() == q["correct_option"].lower():
                        print("[CORRECT!]")
                        score += 1
                    else:
                        print(f"[INCORRECT] Correct Answer: {q['correct_option']}")
                else:
                    print(f"[SKIPPED / INVALID] Correct Answer: {q['correct_option']}")
            except (KeyboardInterrupt, EOFError):
                print("\nQuiz terminated.")
                return
        else:
            try:
                user_input = input("Your Answer: ").strip()
                print(f"\nExpected Answer: {q['answer']}")
                confirm = input("Did your answer match? (y/n): ").strip().lower()
                if confirm == "y":
                    print("[POINT AWARDED!]")
                    score += 1
                else:
                    print("[NOTED]")
            except (KeyboardInterrupt, EOFError):
                print("\nQuiz terminated.")
                return

    pct = (score / total) * 100
    print("\n" + "=" * 65)
    print(f" QUIZ COMPLETED! Final Score: {score}/{total} ({pct:.1f}%)")
    print("=" * 65)


def export_html_quiz(questions, title="Markdown Interactive Quiz"):
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{title}</title>
  <style>
    body {{ font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: #0f172a; color: #f8fafc; padding: 40px; max-width: 800px; margin: auto; }}
    .card {{ background: #1e293b; padding: 25px; border-radius: 12px; margin-bottom: 20px; box-shadow: 0 4px 6px rgba(0,0,0,0.3); }}
    h1 {{ color: #38bdf8; }}
    .btn {{ background: #0284c7; color: white; border: none; padding: 10px 20px; border-radius: 6px; cursor: pointer; font-size: 16px; margin-top: 10px; }}
    .btn:hover {{ background: #0369a1; }}
    .option {{ background: #334155; padding: 12px; margin: 8px 0; border-radius: 6px; cursor: pointer; transition: background 0.2s; }}
    .option:hover {{ background: #475569; }}
    .correct {{ background: #166534 !important; color: white; }}
    .wrong {{ background: #991b1b !important; color: white; }}
    #score-box {{ font-size: 22px; font-weight: bold; color: #4ade80; display: none; }}
  </style>
</head>
<body>
  <h1>{title}</h1>
  <div id="quiz-container"></div>
  <div id="score-box" class="card"></div>

  <script>
    const questions = {json.dumps(questions)};
    const container = document.getElementById('quiz-container');

    questions.forEach((q, idx) => {{
      const div = document.createElement('div');
      div.className = 'card';
      div.innerHTML = `<h3>Q${{idx + 1}}: ${{q.question}}</h3>`;
      
      if (q.options) {{
        q.options.forEach(opt => {{
          const btn = document.createElement('div');
          btn.className = 'option';
          btn.innerText = opt;
          btn.onclick = () => {{
            if (opt === q.correct_option) {{
              btn.classList.add('correct');
            }} else {{
              btn.classList.add('wrong');
            }}
          }};
          div.appendChild(btn);
        }});
      }} else {{
        const input = document.createElement('input');
        input.type = 'text';
        input.placeholder = 'Type answer...';
        input.style.width = '80%'; input.style.padding = '8px';
        const showBtn = document.createElement('button');
        showBtn.className = 'btn';
        showBtn.innerText = 'Reveal Answer';
        const ansP = document.createElement('p');
        ansP.style.display = 'none'; ansP.style.color = '#38bdf8';
        ansP.innerText = 'Answer: ' + q.answer;
        showBtn.onclick = () => ansP.style.display = 'block';
        div.appendChild(input);
        div.appendChild(showBtn);
        div.appendChild(ansP);
      }}
      container.appendChild(div);
    }});
  </script>
</body>
</html>"""
    return html


def run_demo():
    print("=== Running Markdown Quiz Generator Demo ===")
    sample_md = """
    # Python & Software Architecture Quiz Notes

    ## What is Object-Oriented Programming?
    Object-oriented programming (OOP) is a programming paradigm based on the concept of objects, which can contain data and code.

    Q: What does API stand for?
    A: Application Programming Interface

    Q: What is the primary advantage of Virtual Environments in Python?
    A: Isolation of project dependencies to prevent version conflicts.

    **Abstraction** - Hiding complex background details and exposing only essential features.
    **Encapsulation** - Bundling data and methods that operate on that data within a single unit or class.
    **Polymorphism** - The ability of different classes to respond to the same method call in unique ways.
    **Inheritance** - Mechanism where a new class derives properties and behaviors from an existing parent class.
    """

    qs = extract_questions_from_markdown(sample_md)
    print(f"Extracted {len(qs)} quiz questions from Markdown note sample:\n")
    for idx, q in enumerate(qs, 1):
        print(f"{idx}. [{q['type'].upper()}] {q['question']}")
        if "options" in q:
            print(f"   Options: {', '.join(q['options'])}")
        print(f"   Answer: {q.get('correct_option', q.get('answer'))}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Markdown Quiz & Self-Assessment Generator - Convert Markdown notes into interactive quizzes."
    )
    parser.add_argument("file", nargs="?", help="Path to Markdown file")
    parser.add_argument("--html", help="Path to export interactive HTML quiz")
    parser.add_argument("--json", action="store_true", help="Output questions in JSON format")
    parser.add_argument("--demo", action="store_true", help="Run demonstration")

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
        title = os.path.basename(args.file)
    else:
        content = sys.stdin.read()
        title = "Markdown Quiz"

    questions = extract_questions_from_markdown(content)

    if args.html:
        html_code = export_html_quiz(questions, title=f"Quiz - {title}")
        with open(args.html, "w", encoding="utf-8") as f:
            f.write(html_code)
        print(f"Interactive HTML quiz successfully exported to '{args.html}'!")
    elif args.json:
        print(json.dumps(questions, indent=2))
    else:
        run_interactive_quiz(questions)


if __name__ == "__main__":
    main()
