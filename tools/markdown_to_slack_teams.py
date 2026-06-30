#!/usr/bin/env python3
"""
Markdown to Slack & Teams Payload Converter
Parses basic markdown (headers, bold, italics, code blocks, lists, links, dividers)
and outputs JSON structures for Slack Block Kit or MS Teams Adaptive Cards.
"""

import os
import sys
import json
import re
import argparse

# Simple inline formatting replacements
def convert_inline_markdown(text, target_format):
    if target_format == 'slack':
        # Bold: **bold** -> *bold*
        text = re.sub(r'\*\*(.*?)\*\*|__(.*?)__', r'*\1\2*', text)
        # Italics: *italic* -> _italic_
        text = re.sub(r'\*(.*?)\*|_(.*?)_', r'_\1\2_', text)
        # Inline code: `code` -> `code`
        # Links: [text](url) -> <url|text>
        text = re.sub(r'\[(.*?)\]\((.*?)\)', r'<\2|\1>', text)
    else:  # teams / adaptive cards (uses standard markdown, but handles details)
        # Teams supports standard markdown: **bold**, *italic*, [text](url), `code`
        pass
    return text

def parse_markdown_to_payloads(md_content):
    lines = md_content.splitlines()
    slack_blocks = []
    teams_body = []
    
    in_code_block = False
    code_block_content = []
    
    current_list_slack = []
    current_list_teams = []
    
    def flush_list():
        nonlocal current_list_slack, current_list_teams
        if current_list_slack:
            slack_blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "".join(current_list_slack)
                }
            })
            current_list_slack = []
        if current_list_teams:
            teams_body.append({
                "type": "TextBlock",
                "text": "".join(current_list_teams),
                "wrap": True
            })
            current_list_teams = []

    for line in lines:
        # Code block toggle
        if line.strip().startswith("```"):
            if in_code_block:
                in_code_block = False
                code_text = "\n".join(code_block_content)
                # Slack
                slack_blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"```\n{code_text}\n```"
                    }
                })
                # Teams
                teams_body.append({
                    "type": "TextBlock",
                    "text": f"```\n{code_text}\n```",
                    "wrap": True,
                    "fontType": "Monospace"
                })
                code_block_content = []
            else:
                flush_list()
                in_code_block = True
            continue
            
        if in_code_block:
            code_block_content.append(line)
            continue

        # Header check: # Header
        header_match = re.match(r'^(#{1,6})\s+(.*)$', line)
        if header_match:
            flush_list()
            h_level = len(header_match.group(1))
            h_text = header_match.group(2)
            
            # Slack: headers must be plain text
            slack_blocks.append({
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": h_text,
                    "emoji": True
                }
            })
            
            # Teams
            sizes = {1: "ExtraLarge", 2: "Large", 3: "Medium"}
            size = sizes.get(h_level, "Default")
            teams_body.append({
                "type": "TextBlock",
                "text": h_text,
                "weight": "Bolder",
                "size": size,
                "wrap": True
            })
            continue

        # Divider check: ---
        if re.match(r'^\s*[-*_]{3,}\s*$', line):
            flush_list()
            slack_blocks.append({"type": "divider"})
            teams_body.append({
                "type": "TextBlock",
                "text": " ",
                "separator": True
            })
            continue

        # List item check: * item or - item or 1. item
        list_match = re.match(r'^\s*[\*\-\+]\s+(.*)$', line)
        if list_match:
            item_text = list_match.group(1)
            slack_txt = convert_inline_markdown(item_text, 'slack')
            teams_txt = convert_inline_markdown(item_text, 'teams')
            
            current_list_slack.append(f"• {slack_txt}\n")
            current_list_teams.append(f"- {teams_txt}\n")
            continue
            
        # Empty line
        if not line.strip():
            flush_list()
            continue

        # Regular paragraph
        flush_list()
        slack_blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": convert_inline_markdown(line, 'slack')
            }
        })
        teams_body.append({
            "type": "TextBlock",
            "text": convert_inline_markdown(line, 'teams'),
            "wrap": True
        })

    flush_list()

    slack_payload = {
        "blocks": slack_blocks
    }
    
    teams_payload = {
        "type": "AdaptiveCard",
        "body": teams_body,
        "$schema": "http://adaptivecards.io/schemas/adaptive-card.json",
        "version": "1.3"
    }
    
    return slack_payload, teams_payload

def main():
    parser = argparse.ArgumentParser(description="Markdown to Slack & Teams Payload Converter")
    parser.add_argument("markdown_file", nargs="?", help="Path to markdown file (reads stdin if omitted)")
    parser.add_argument("-f", "--format", choices=["slack", "teams", "both"], default="both", help="Target payload format")
    parser.add_argument("-o", "--output", help="Prefix for output JSON files (e.g. 'result' -> 'result_slack.json')")
    
    args = parser.parse_args()

    # Read content
    if args.markdown_file:
        if not os.path.exists(args.markdown_file):
            print(f"Error: File '{args.markdown_file}' does not exist.")
            sys.exit(1)
        with open(args.markdown_file, 'r', encoding='utf-8') as f:
            md_content = f.read()
    else:
        # Read from stdin
        if sys.stdin.isatty():
            print("Usage: Pass a file path or pipe markdown via stdin.")
            parser.print_help()
            sys.exit(1)
        md_content = sys.stdin.read()

    slack_pay, teams_pay = parse_markdown_to_payloads(md_content)

    if args.output:
        if args.format in ["slack", "both"]:
            s_file = f"{args.output}_slack.json"
            with open(s_file, 'w', encoding='utf-8') as f:
                json.dump(slack_pay, f, indent=2)
            print(f"Saved Slack Block Kit payload to {s_file}")
            
        if args.format in ["teams", "both"]:
            t_file = f"{args.output}_teams.json"
            with open(t_file, 'w', encoding='utf-8') as f:
                json.dump(teams_pay, f, indent=2)
            print(f"Saved MS Teams Adaptive Card payload to {t_file}")
    else:
        if args.format == "slack":
            print(json.dumps(slack_pay, indent=2))
        elif args.format == "teams":
            print(json.dumps(teams_pay, indent=2))
        else:
            combined = {
                "slack": slack_pay,
                "teams": teams_pay
            }
            print(json.dumps(combined, indent=2))

if __name__ == "__main__":
    main()
