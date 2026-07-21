# Password Strength Analyzer

A Python tool to analyze and evaluate the strength of passwords, providing detailed feedback and suggestions for improvement.

## Features

- Analyze password length and character variety
- Detect common weak password patterns
- Calculate strength scores out of 100
- Provide actionable feedback for improvement
- Batch analysis from file input
- Interactive mode for single password analysis

## Usage

```bash
# Analyze a password interactively
python password_analyzer.py

# Analyze a specific password
python password_analyzer.py "MyPassword123!"

# Analyze a password using the --password flag
python password_analyzer.py --password "MyPassword123!"

# Analyze passwords from a file
python password_analyzer.py -f passwords.txt
```

## Example Output

```
Password Analysis for: MyPassword123!
========================================
Length: 15 characters
Character types used: Lowercase letters, Uppercase letters, Numbers, Special characters
Strength Score: 95/100
Feedback: Very Strong Password
```

## Security Notes

This tool analyzes password strength locally and does not transmit any data over the internet. Passwords entered are processed only on your local machine.

## Requirements

- Python 3.x

## How It Works

The tool calculates password strength based on:
1. Password length (up to 50 points)
2. Character variety (up to 50 points)
3. Bonus points for long passwords with good variety

Strength scores:
- 80-100: Very Strong
- 60-79: Strong
- 40-59: Medium
- 20-39: Weak
- 0-19: Very Weak