#!/usr/bin/env python3
"""
CLI Eisenhower Matrix Task Planner
Organizes, prioritizes, and tracks tasks using the Eisenhower Matrix decision framework:
  Q1: Urgent & Important (Do First)
  Q2: Not Urgent & Important (Schedule)
  Q3: Urgent & Not Important (Delegate)
  Q4: Not Urgent & Not Important (Eliminate)

Uses only standard Python libraries.
"""

import argparse
import json
import os
import sys
from datetime import datetime

DEFAULT_DB_FILE = os.path.expanduser("~/.todo_matrix.json")


class TaskManager:
    def __init__(self, db_path=DEFAULT_DB_FILE):
        self.db_path = db_path
        self.tasks = self.load_tasks()

    def load_tasks(self):
        if not os.path.exists(self.db_path):
            return []
        try:
            with open(self.db_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading tasks from {self.db_path}: {e}", file=sys.stderr)
            return []

    def save_tasks(self):
        try:
            db_dir = os.path.dirname(self.db_path)
            if db_dir and not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
            with open(self.db_path, "w", encoding="utf-8") as f:
                json.dump(self.tasks, f, indent=2)
        except Exception as e:
            print(f"Error saving tasks to {self.db_path}: {e}", file=sys.stderr)

    def add_task(self, title, urgent=False, important=False, category="General", due_date=None):
        next_id = max([t.get("id", 0) for t in self.tasks], default=0) + 1
        quadrant = self.get_quadrant(urgent, important)
        task = {
            "id": next_id,
            "title": title,
            "urgent": bool(urgent),
            "important": bool(important),
            "quadrant": quadrant,
            "category": category,
            "due_date": due_date,
            "completed": False,
            "created_at": datetime.now().isoformat()
        }
        self.tasks.append(task)
        self.save_tasks()
        return task

    @staticmethod
    def get_quadrant(urgent, important):
        if urgent and important:
            return "Q1 (Do First)"
        elif not urgent and important:
            return "Q2 (Schedule)"
        elif urgent and not important:
            return "Q3 (Delegate)"
        else:
            return "Q4 (Eliminate)"

    def complete_task(self, task_id):
        for task in self.tasks:
            if task["id"] == task_id:
                task["completed"] = True
                task["completed_at"] = datetime.now().isoformat()
                self.save_tasks()
                return task
        return None

    def delete_task(self, task_id):
        initial_len = len(self.tasks)
        self.tasks = [t for t in self.tasks if t["id"] != task_id]
        if len(self.tasks) < initial_len:
            self.save_tasks()
            return True
        return False

    def list_tasks(self, include_completed=False, category=None):
        filtered = self.tasks
        if not include_completed:
            filtered = [t for t in filtered if not t.get("completed", False)]
        if category:
            filtered = [t for t in filtered if t.get("category", "").lower() == category.lower()]
        return filtered

    def render_matrix(self):
        active_tasks = [t for t in self.tasks if not t.get("completed", False)]
        q1 = [t for t in active_tasks if t["urgent"] and t["important"]]
        q2 = [t for t in active_tasks if not t["urgent"] and t["important"]]
        q3 = [t for t in active_tasks if t["urgent"] and not t["important"]]
        q4 = [t for t in active_tasks if not t["urgent"] and not t["important"]]

        def fmt_q(title, task_list, width=38):
            lines = [f" --- {title} ({len(task_list)}) ---"]
            for t in task_list[:5]:
                due = f" [{t['due_date']}]" if t.get("due_date") else ""
                cat = f" ({t.get('category')})" if t.get("category") != "General" else ""
                item = f" #{t['id']} {t['title']}{cat}{due}"
                if len(item) > width - 2:
                    item = item[:width - 5] + "..."
                lines.append(item)
            if len(task_list) > 5:
                lines.append(f" ... +{len(task_list) - 5} more")
            return lines

        q1_lines = fmt_q("Q1: DO FIRST (Urgent & Important)", q1)
        q2_lines = fmt_q("Q2: SCHEDULE (Not Urgent & Important)", q2)
        q3_lines = fmt_q("Q3: DELEGATE (Urgent & Not Important)", q3)
        q4_lines = fmt_q("Q4: ELIMINATE (Not Urgent/Important)", q4)

        max_top = max(len(q1_lines), len(q2_lines))
        max_bot = max(len(q3_lines), len(q4_lines))

        q1_lines += [""] * (max_top - len(q1_lines))
        q2_lines += [""] * (max_top - len(q2_lines))
        q3_lines += [""] * (max_bot - len(q3_lines))
        q4_lines += [""] * (max_bot - len(q4_lines))

        box_w = 40
        sep = "+" + "-" * box_w + "+" + "-" * box_w + "+"

        out = []
        out.append(sep)
        out.append(f"| {'EISENHOWER MATRIX TASK PLANNER':^{box_w*2 + 1}} |")
        out.append(sep)

        for l1, l2 in zip(q1_lines, q2_lines):
            out.append(f"| {l1:<{box_w-1}} | {l2:<{box_w-1}} |")

        out.append(sep)

        for l3, l4 in zip(q3_lines, q4_lines):
            out.append(f"| {l3:<{box_w-1}} | {l4:<{box_w-1}} |")

        out.append(sep)
        return "\n".join(out)


def run_demo():
    print("=== Running Eisenhower Matrix Task Planner Demo ===")
    demo_db = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_demo_todo_matrix.json")
    if os.path.exists(demo_db):
        os.remove(demo_db)

    mgr = TaskManager(db_path=demo_db)
    mgr.add_task("Fix production server crash", urgent=True, important=True, category="DevOps", due_date="Today")
    mgr.add_task("Design Q3 product roadmap", urgent=False, important=True, category="Strategy", due_date="2026-07-15")
    mgr.add_task("Respond to non-critical vendor emails", urgent=True, important=False, category="Admin")
    mgr.add_task("Browse social media feed", urgent=False, important=False, category="Distraction")
    mgr.add_task("Refactor authentication module", urgent=False, important=True, category="Code")
    mgr.add_task("Submit quarterly tax returns", urgent=True, important=True, category="Finance", due_date="Tomorrow")

    print("\nGenerated Matrix Visual View:\n")
    print(mgr.render_matrix())

    print("\nMarking Task #1 as Completed...")
    mgr.complete_task(1)

    print("\nUpdated Matrix View:\n")
    print(mgr.render_matrix())

    if os.path.exists(demo_db):
        os.remove(demo_db)


def main():
    parser = argparse.ArgumentParser(
        description="CLI Eisenhower Matrix Task Planner - Organize tasks by urgency and importance."
    )
    parser.add_argument("--db", default=DEFAULT_DB_FILE, help="Path to JSON task database")
    parser.add_argument("--demo", action="store_true", help="Run interactive demonstration")

    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # Add task
    add_parser = subparsers.add_parser("add", help="Add a new task")
    add_parser.add_argument("title", help="Task title/description")
    add_parser.add_argument("-u", "--urgent", action="store_true", help="Mark task as urgent")
    add_parser.add_argument("-i", "--important", action="store_true", help="Mark task as important")
    add_parser.add_argument("-c", "--category", default="General", help="Category tag")
    add_parser.add_argument("-d", "--due", help="Due date (e.g. YYYY-MM-DD)")

    # Matrix view
    subparsers.add_parser("matrix", help="Display tasks in 2x2 Eisenhower Matrix box view")

    # List tasks
    list_parser = subparsers.add_parser("list", help="List tasks in tabular form")
    list_parser.add_argument("-a", "--all", action="store_true", help="Include completed tasks")
    list_parser.add_argument("-c", "--category", help="Filter by category")

    # Complete task
    comp_parser = subparsers.add_parser("complete", help="Mark task as completed")
    comp_parser.add_argument("id", type=int, help="Task ID")

    # Delete task
    del_parser = subparsers.add_parser("delete", help="Delete task by ID")
    del_parser.add_argument("id", type=int, help="Task ID")

    args = parser.parse_args()

    if args.demo or (len(sys.argv) == 1 and not os.path.exists(DEFAULT_DB_FILE)):
        run_demo()
        return

    mgr = TaskManager(db_path=args.db)

    if args.command == "add":
        t = mgr.add_task(args.title, urgent=args.urgent, important=args.important, category=args.category, due_date=args.due)
        print(f"Added Task #{t['id']} -> Quadrant: {t['quadrant']}")
    elif args.command == "matrix" or (len(sys.argv) == 1):
        print(mgr.render_matrix())
    elif args.command == "list":
        tasks = mgr.list_tasks(include_completed=args.all, category=args.category)
        if not tasks:
            print("No tasks found.")
            return
        print(f"{'ID':<4} {'Status':<10} {'Quadrant':<22} {'Category':<12} {'Title'}")
        print("-" * 75)
        for t in tasks:
            status = "Completed" if t.get("completed") else "Pending"
            print(f"#{t['id']:<3} {status:<10} {t['quadrant']:<22} {t.get('category','General'):<12} {t['title']}")
    elif args.command == "complete":
        t = mgr.complete_task(args.id)
        if t:
            print(f"Task #{args.id} marked as completed!")
        else:
            print(f"Task #{args.id} not found.", file=sys.stderr)
    elif args.command == "delete":
        if mgr.delete_task(args.id):
            print(f"Task #{args.id} deleted successfully.")
        else:
            print(f"Task #{args.id} not found.", file=sys.stderr)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
