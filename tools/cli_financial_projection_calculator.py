#!/usr/bin/env python3
"""
CLI Financial Projection Calculator
-----------------------------------
A financial forecasting tool to simulate long-term investment compound growth.
Supports starting balance, monthly contributions, annual rate of return, inflation,
tax rates, and scheduled one-time events (e.g. buying a car or receiving a inheritance).
Displays a detailed tabular summary, milestone timelines, and a beautiful
ASCII/Unicode growth chart directly in the terminal.

Author: Antigravity
License: MIT
"""

import sys
import argparse
from datetime import datetime

# ANSI Colors
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"

def render_ascii_chart(data, width=65, height=15):
    """Renders a beautiful ASCII/Unicode line chart of the projection data."""
    if not data:
        return
        
    n = len(data)
    sampled = []
    for i in range(width):
        idx = int(i * n / width)
        sampled.append(data[min(idx, n - 1)])
        
    val_min = min(sampled)
    val_max = max(sampled)
    val_range = val_max - val_min if val_max > val_min else 1.0
    
    grid = [[" " for _ in range(width)] for _ in range(height)]
    
    # Plot data points
    last_row = None
    for x in range(width):
        y_val = sampled[x]
        ratio = (y_val - val_min) / val_range
        y_scaled = int(ratio * (height - 1))
        row = (height - 1) - y_scaled
        
        # Draw line segment
        grid[row][x] = "█"
        if last_row is not None:
            # Fill intermediate gaps to make the line continuous
            step = 1 if row > last_row else -1
            for r in range(last_row + step, row, step):
                grid[r][x] = "░"
        last_row = row
        
    # Print the chart
    print("\n" + " " * 15 + f"{BOLD}{CYAN}INVESTMENT GROWTH TIMELINE{RESET}")
    print(" " * 15 + f"Balance ($) vs Timeline\n")
    
    for r in range(height):
        # Y-axis label
        y_val = val_max - (r / (height - 1)) * val_range
        label = f"${y_val:,.0f}"
        print(f" {label:>12} | " + "".join(grid[r]))
        
    # X-axis line
    print(" " * 14 + "+" + "-" * width)
    
    # X-axis labels (Years)
    total_months = len(data)
    total_years = total_months / 12.0
    half_years = total_years / 2.0
    
    labels = f"Year 0"
    mid_label = f"Year {half_years:.1f}"
    end_label = f"Year {total_years:.1f}"
    
    # Calculate spacing
    space_mid = int(width / 2) - len(labels)
    space_end = width - len(labels) - space_mid - len(mid_label)
    
    print(" " * 15 + labels + " " * space_mid + mid_label + " " * space_end + end_label + "\n")

def parse_events(events_list):
    """Parses events in the format 'month:amount' or 'month:amount:description'."""
    parsed_events = {}
    if not events_list:
        return parsed_events
        
    for event in events_list:
        parts = event.split(':', 2)
        if len(parts) >= 2:
            try:
                month = int(parts[0])
                amount = float(parts[1])
                desc = parts[2] if len(parts) > 2 else "Custom Event"
                parsed_events[month] = {"amount": amount, "desc": desc}
            except ValueError:
                print(f"{RED}Warning: Ignoring invalid event syntax '{event}' (Expected: month:amount[:desc]){RESET}")
    return parsed_events

def run_simulation(start_balance, monthly_contrib, annual_return, inflation, years, tax_rate, events):
    """Runs simulation month-by-month and returns logs, milestones, and chart data."""
    monthly_return_rate = (1 + annual_return / 100) ** (1 / 12) - 1
    monthly_inflation_rate = (1 + inflation / 100) ** (1 / 12) - 1
    
    nominal_balance = start_balance
    real_balance = start_balance  # Inflation adjusted
    total_contributed = start_balance
    
    nominal_history = [nominal_balance]
    real_history = [real_balance]
    
    logs = []
    milestones = []
    
    milestone_targets = [10000, 50000, 100000, 250000, 500000, 1000000, 2000000, 5000000, 10000000]
    next_milestone_idx = 0
    # Find initial milestones already met
    while next_milestone_idx < len(milestone_targets) and start_balance >= milestone_targets[next_milestone_idx]:
        next_milestone_idx += 1
        
    total_months = years * 12
    for m in range(1, total_months + 1):
        # 1. Apply investment growth
        interest = nominal_balance * monthly_return_rate
        nominal_balance += interest
        
        # 2. Add monthly contribution
        nominal_balance += monthly_contrib
        total_contributed += monthly_contrib
        
        # 3. Apply custom events
        event_applied = None
        if m in events:
            event_amount = events[m]["amount"]
            nominal_balance += event_amount
            if event_amount > 0:
                total_contributed += event_amount
            event_applied = events[m]
            
        # Ensure balance doesn't drop below zero
        if nominal_balance < 0:
            nominal_balance = 0
            
        # 4. Calculate real (inflation adjusted) value
        # We discount the nominal balance back to Year 0 dollars
        discount_factor = (1 + monthly_inflation_rate) ** m
        real_balance = nominal_balance / discount_factor
        
        nominal_history.append(nominal_balance)
        real_history.append(real_balance)
        
        # Log entry for reporting
        logs.append({
            "month": m,
            "year": m / 12.0,
            "nominal": nominal_balance,
            "real": real_balance,
            "contributed": total_contributed,
            "event": event_applied
        })
        
        # Check milestones
        while next_milestone_idx < len(milestone_targets):
            target = milestone_targets[next_milestone_idx]
            if nominal_balance >= target:
                milestones.append({
                    "target": target,
                    "month": m,
                    "year": m / 12.0,
                    "nominal": nominal_balance
                })
                next_milestone_idx += 1
            else:
                break
                
    return nominal_history, real_history, logs, milestones

def main():
    parser = argparse.ArgumentParser(
        description="CLI Financial Projection Calculator - Simulate compound interest and compound growth.",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--start", type=float, default=10000.0, help="Starting balance/investment ($) (default: 10000)")
    parser.add_argument("--contrib", type=float, default=500.0, help="Monthly contribution ($) (default: 500)")
    parser.add_argument("--return-rate", type=float, default=8.0, help="Expected annual rate of return (%%) (default: 8.0)")
    parser.add_argument("--inflation", type=float, default=2.5, help="Expected annual inflation rate (%%) (default: 2.5)")
    parser.add_argument("--years", type=int, default=25, help="Simulation duration in years (default: 25)")
    parser.add_argument("--tax-rate", type=float, default=0.0, help="Tax rate on capital gains (%%) applied at end of projection (default: 0.0)")
    parser.add_argument("--event", action="append", help="Scheduled custom events. Format: 'month:amount:description' (e.g. '36:-5000:Travel' or '120:20000:Bonus')")
    parser.add_argument("--details", action="store_true", help="Print detailed year-by-year summary table.")
    
    args = parser.parse_args()
    
    events = parse_events(args.event)
    
    nominal_history, real_history, logs, milestones = run_simulation(
        args.start, args.contrib, args.return_rate, args.inflation, args.years, args.tax_rate, events
    )
    
    final_nominal = nominal_history[-1]
    final_real = real_history[-1]
    total_contributed = logs[-1]["contributed"] if logs else args.start
    total_interest = final_nominal - total_contributed
    
    # Calculate taxes if any
    tax_paid = 0.0
    post_tax_nominal = final_nominal
    if args.tax_rate > 0:
        gains = final_nominal - total_contributed
        if gains > 0:
            tax_paid = gains * (args.tax_rate / 100.0)
            post_tax_nominal = final_nominal - tax_paid
            
    print("\n" + "=" * 65)
    print(f"{BOLD}{GREEN}FINANCIAL PROJECTION SUMMARY ({args.years} YEARS){RESET}")
    print("=" * 65)
    print(f"Initial Principal:         ${args.start:,.2f}")
    print(f"Total Contributions:       ${total_contributed - args.start:,.2f}")
    print(f"Total Amount Deposited:    ${total_contributed:,.2f}")
    print(f"Total Interest Earned:     {GREEN}${total_interest:,.2f}{RESET}")
    print("-" * 65)
    print(f"{BOLD}Final Nominal Value:       ${final_nominal:,.2f}{RESET}")
    if args.tax_rate > 0:
        print(f"Tax Paid ({args.tax_rate}% on gains):  ${tax_paid:,.2f}")
        print(f"{BOLD}Post-Tax Nominal Value:    ${post_tax_nominal:,.2f}{RESET}")
    print(f"{BOLD}Final Real Value (CPI):    {YELLOW}${final_real:,.2f}{RESET} (Inflation adjusted to Year 0)")
    print("=" * 65)
    
    # Render line chart
    render_ascii_chart(nominal_history)
    
    # Print year-by-year details if requested
    if args.details:
        print("\n" + "=" * 70)
        print(f"{BOLD}{'YEAR-BY-YEAR REPORT':^70}{RESET}")
        print("=" * 70)
        print(f"| {'Year':<6} | {'Nominal Balance':<18} | {'Real Balance (CPI)':<20} | {'Deposited':<14} |")
        print("-" * 70)
        for log in logs:
            if log["month"] % 12 == 0:
                print(f"| {int(log['year']):<6} | ${log['nominal']:16,.2f} | ${log['real']:18,.2f} | ${log['contributed']:12,.2f} |")
        print("=" * 70)
        
    # Print milestones
    if milestones:
        print(f"{BOLD}Milestone Achieved Timeline:{RESET}")
        print("-" * 45)
        for ms in milestones:
            print(f"  • {GREEN}${ms['target']:>10,}{RESET} reached in {BOLD}Year {ms['year']:.1f}{RESET} (Month {ms['month']})")
        print("-" * 45 + "\n")
        
    if final_nominal < total_contributed:
        print(f"{RED}[!] Warning: Inflation, custom events, or negative returns caused the final value to be less than the total deposits.{RESET}")

if __name__ == "__main__":
    main()
