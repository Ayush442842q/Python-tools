#!/usr/bin/env python3
"""
CLI Personal Finance Tracker - Command-line personal budget & expense manager
Logs transactions (income, expenses, transfers), manages monthly category budgets,
displays progress bars, renders ASCII category expense charts, and persists data to JSON.
"""

import argparse
import csv
import datetime
import json
import os
import sys
from typing import Dict, List, Any

DEFAULT_DB = "finance_db.json"

def load_data(db_path: str) -> Dict[str, Any]:
    """Load financial data from the JSON file."""
    if not os.path.exists(db_path):
        return {
            "transactions": [],
            "budgets": {},
            "categories": ["Food", "Rent", "Utilities", "Salary", "Entertainment", "Transport", "Shopping", "Other"]
        }
    try:
        with open(db_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading database: {e}. Starting fresh.", file=sys.stderr)
        return {
            "transactions": [],
            "budgets": {},
            "categories": ["Food", "Rent", "Utilities", "Salary", "Entertainment", "Transport", "Shopping", "Other"]
        }

def save_data(db_path: str, data: Dict[str, Any]) -> None:
    """Save financial data to the JSON file."""
    try:
        with open(db_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        print(f"Error saving data: {e}", file=sys.stderr)

def format_currency(amount: float) -> str:
    """Format currency values cleanly."""
    return f"${amount:,.2f}"

def render_progress_bar(percentage: float, width: int = 20) -> str:
    """Generate an ASCII progress bar."""
    filled_len = int(round(width * min(100.0, percentage) / 100.0))
    bar = "█" * filled_len + "-" * (width - filled_len)
    return f"[{bar}] {percentage:.1f}%"

def add_transaction(db_path: str, date_str: str, amount: float, t_type: str, category: str, desc: str) -> None:
    """Add a new transaction to the database."""
    data = load_data(db_path)
    
    # Validate date
    try:
        date_obj = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
    except ValueError:
        print("Error: Invalid date format. Use YYYY-MM-DD.", file=sys.stderr)
        return
        
    if t_type.lower() not in ["income", "expense", "transfer"]:
        print("Error: Transaction type must be income, expense, or transfer.", file=sys.stderr)
        return
        
    # Ensure category exists
    if category not in data["categories"]:
        data["categories"].append(category)
        
    new_t = {
        "id": len(data["transactions"]) + 1,
        "date": date_str,
        "amount": amount,
        "type": t_type.lower(),
        "category": category,
        "description": desc
    }
    
    data["transactions"].append(new_t)
    save_data(db_path, data)
    print(f"Success: Added {t_type} of {format_currency(amount)} under '{category}'.")

def set_budget(db_path: str, category: str, limit: float) -> None:
    """Set or update a budget for a category."""
    data = load_data(db_path)
    data["budgets"][category] = limit
    save_data(db_path, data)
    print(f"Success: Set monthly budget for '{category}' to {format_currency(limit)}.")

def show_summary(db_path: str, month: str = None) -> None:
    """Display a summary of income, expenses, and budget usage."""
    data = load_data(db_path)
    transactions = data["transactions"]
    
    # Filter by month if specified (format: YYYY-MM)
    if not month:
        month = datetime.datetime.now().strftime("%Y-%m")
        
    print(f"\nFinancial Summary for {month}")
    print("=" * 60)
    
    total_income = 0.0
    total_expense = 0.0
    category_totals: Dict[str, float] = {}
    
    for t in transactions:
        if t["date"].startswith(month):
            amount = t["amount"]
            if t["type"] == "income":
                total_income += amount
            elif t["type"] == "expense":
                total_expense += amount
                cat = t["category"]
                category_totals[cat] = category_totals.get(cat, 0.0) + amount
                
    net_savings = total_income - total_expense
    savings_rate = (net_savings / total_income * 100) if total_income > 0 else 0.0
    
    print(f"Total Income:   {format_currency(total_income)}")
    print(f"Total Expenses: {format_currency(total_expense)}")
    print(f"Net Savings:    {format_currency(net_savings)} (Savings Rate: {savings_rate:.1f}%)")
    print("-" * 60)
    
    # Budget vs Actual Breakdown
    print(f"{'Category':<15} | {'Spent':<10} | {'Budget':<10} | {'Status/Progress':<20}")
    print("-" * 60)
    
    all_categories = set(list(data["budgets"].keys()) + list(category_totals.keys()))
    for cat in sorted(all_categories):
        spent = category_totals.get(cat, 0.0)
        budget = data["budgets"].get(cat, 0.0)
        
        if budget > 0:
            percentage = (spent / budget) * 100
            bar = render_progress_bar(percentage, width=15)
            budget_str = format_currency(budget)
        else:
            bar = "No Budget Limit"
            budget_str = "N/A"
            
        print(f"{cat:<15} | {format_currency(spent):<10} | {budget_str:<10} | {bar}")
        
    # Render ASCII Bar Chart of Expenses
    if category_totals:
        print("\nExpense Distribution Chart")
        print("=" * 60)
        max_spent = max(category_totals.values())
        chart_width = 30
        for cat, spent in sorted(category_totals.items(), key=lambda x: x[1], reverse=True):
            bar_len = int((spent / max_spent) * chart_width)
            bar = "█" * bar_len
            print(f"{cat:<15} | {bar:<30} | {format_currency(spent)}")

def list_transactions(db_path: str, limit: int = 50) -> None:
    """List recent transactions in a neat table format."""
    data = load_data(db_path)
    transactions = sorted(data["transactions"], key=lambda x: x["date"], reverse=True)[:limit]
    
    if not transactions:
        print("No transactions found.")
        return
        
    print(f"\nRecent Transactions (Showing last {len(transactions)}):")
    print("-" * 75)
    print(f"{'ID':<4} | {'Date':<10} | {'Type':<8} | {'Category':<12} | {'Amount':<10} | {'Description'}")
    print("-" * 75)
    
    for t in transactions:
        amount_str = format_currency(t["amount"])
        type_str = t["type"].upper()
        # Add color indicators if running in ANSI-enabled terminal
        if type_str == "INCOME":
            type_fmt = f"\033[92m{type_str:<8}\033[0m"
        elif type_str == "EXPENSE":
            type_fmt = f"\033[91m{type_str:<8}\033[0m"
        else:
            type_fmt = f"{type_str:<8}"
            
        print(f"{t['id']:<4} | {t['date']:<10} | {type_fmt} | {t['category']:<12} | {amount_str:<10} | {t['description']}")
    print("-" * 75)

def export_csv(db_path: str, output_path: str) -> None:
    """Export all transactions to a CSV file."""
    data = load_data(db_path)
    transactions = data["transactions"]
    
    if not transactions:
        print("No transactions to export.", file=sys.stderr)
        return
        
    try:
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["ID", "Date", "Type", "Category", "Amount", "Description"])
            for t in transactions:
                writer.writerow([t["id"], t["date"], t["type"], t["category"], t["amount"], t["description"]])
        print(f"Success: Exported {len(transactions)} transactions to {output_path}.")
    except Exception as e:
        print(f"Error exporting CSV: {e}", file=sys.stderr)

def interactive_menu(db_path: str) -> None:
    """Run an interactive wizard menu for the finance tracker."""
    print("Welcome to CLI Personal Finance Tracker!")
    while True:
        print("\nMain Menu:")
        print("1. Add Transaction")
        print("2. Set Monthly Budget")
        print("3. View Monthly Summary & Charts")
        print("4. List Recent Transactions")
        print("5. Export Transactions to CSV")
        print("6. Exit")
        
        choice = input("\nSelect option (1-6): ").strip()
        
        if choice == "1":
            print("\n--- Add Transaction ---")
            t_type = input("Type (income/expense/transfer): ").strip()
            amount_str = input("Amount ($): ").strip()
            category = input("Category (e.g. Food, Rent, Salary): ").strip()
            desc = input("Description: ").strip()
            
            # Default to today
            today = datetime.date.today().strftime("%Y-%m-%d")
            date_str = input(f"Date (YYYY-MM-DD, default '{today}'): ").strip() or today
            
            try:
                amount = float(amount_str)
                add_transaction(db_path, date_str, amount, t_type, category, desc)
            except ValueError:
                print("Error: Invalid amount value.", file=sys.stderr)
                
        elif choice == "2":
            print("\n--- Set Monthly Budget ---")
            category = input("Category: ").strip()
            limit_str = input("Monthly Limit ($): ").strip()
            try:
                limit = float(limit_str)
                set_budget(db_path, category, limit)
            except ValueError:
                print("Error: Invalid limit value.", file=sys.stderr)
                
        elif choice == "3":
            today_month = datetime.date.today().strftime("%Y-%m")
            month = input(f"Enter month (YYYY-MM, default '{today_month}'): ").strip() or today_month
            show_summary(db_path, month)
            
        elif choice == "4":
            list_transactions(db_path)
            
        elif choice == "5":
            out_file = input("Enter output CSV path (default 'expenses.csv'): ").strip() or "expenses.csv"
            export_csv(db_path, out_file)
            
        elif choice == "6":
            print("Goodbye!")
            break
        else:
            print("Invalid selection. Try again.")

def main():
    parser = argparse.ArgumentParser(
        description="CLI Personal Finance Tracker - Command-line budget & expense manager",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--db", default=DEFAULT_DB, help=f"Path to JSON database file (default: {DEFAULT_DB})")
    
    subparsers = parser.add_subparsers(dest="command", help="Financial actions")
    
    # Subcommand: interactive
    subparsers.add_parser("interactive", help="Run interactive TUI menu wizard")
    
    # Subcommand: add
    add_parser = subparsers.add_parser("add", help="Add a new transaction")
    add_parser.add_argument("-t", "--type", required=True, choices=["income", "expense", "transfer"], help="Type of transaction")
    add_parser.add_argument("-a", "--amount", required=True, type=float, help="Transaction amount")
    add_parser.add_argument("-c", "--category", required=True, help="Category name")
    add_parser.add_argument("-d", "--description", default="", help="Description")
    add_parser.add_argument("--date", default=datetime.date.today().strftime("%Y-%m-%d"), help="Transaction date (YYYY-MM-DD, default today)")
    
    # Subcommand: budget
    budget_parser = subparsers.add_parser("budget", help="Set monthly category budget")
    budget_parser.add_argument("-c", "--category", required=True, help="Category name")
    budget_parser.add_argument("-l", "--limit", required=True, type=float, help="Monthly budget limit ($)")
    
    # Subcommand: summary
    sum_parser = subparsers.add_parser("summary", help="Show budget progress and monthly financial breakdown")
    sum_parser.add_argument("-m", "--month", default=datetime.datetime.now().strftime("%Y-%m"), help="Month to summarize (YYYY-MM, default current)")
    
    # Subcommand: list
    list_parser = subparsers.add_parser("list", help="List recent transactions")
    list_parser.add_argument("-n", "--limit", type=int, default=30, help="Number of records to show (default: 30)")
    
    # Subcommand: export
    exp_parser = subparsers.add_parser("export", help="Export transactions to a CSV file")
    exp_parser.add_argument("-o", "--output", default="transactions.csv", help="Output file path (default: transactions.csv)")
    
    args = parser.parse_args()
    
    # Default to interactive if no arguments
    if not args.command:
        interactive_menu(args.db)
        sys.exit(0)
        
    if args.command == "interactive":
        interactive_menu(args.db)
    elif args.command == "add":
        add_transaction(args.db, args.date, args.amount, args.type, args.category, args.description)
    elif args.command == "budget":
        set_budget(args.db, args.category, args.limit)
    elif args.command == "summary":
        show_summary(args.db, args.month)
    elif args.command == "list":
        list_transactions(args.db, args.limit)
    elif args.command == "export":
        export_csv(args.db, args.output)

if __name__ == "__main__":
    main()
