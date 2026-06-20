#!/usr/bin/env python3
"""
Local Markdown Wiki & Backlink Analyzer
Scans a folder of Markdown notes (e.g. Obsidian vault or personal wiki), detects wiki-style 
and standard links, extracts tags, computes backlinks/orphans/dead-ends, and generates Mermaid network graphs.
"""

import argparse
import os
import re
import sys
from typing import Dict, List, Set, Tuple

class WikiNode:
    def __init__(self, filepath: str, rel_path: str):
        self.filepath = filepath
        self.rel_path = rel_path
        self.title = os.path.splitext(os.path.basename(filepath))[0]
        self.outgoing_links: Set[str] = set()  # Set of target relative paths
        self.incoming_links: Set[str] = set()  # Set of source relative paths
        self.tags: Set[str] = set()
        self.word_count = 0

def clean_wiki_link(link: str) -> str:
    """Normalize wikilink target (e.g. [[Note Name|Display Label]] -> 'Note Name.md')."""
    # Remove display label if present
    target = link.split("|")[0]
    # Remove anchor/heading if present
    target = target.split("#")[0]
    target = target.strip()
    
    # If it doesn't end with .md, assume it's a markdown note
    if not target.lower().endswith(".md"):
        target = f"{target}.md"
    return target

def parse_note_content(filepath: str, all_titles_map: Dict[str, str]) -> Tuple[Set[str], Set[str], int]:
    """Parse links, tags, and word count from markdown file content."""
    outgoing = set()
    tags = set()
    word_count = 0
    
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        print(f"Warning: Failed to read {filepath} - {e}", file=sys.stderr)
        return outgoing, tags, 0

    # Strip code blocks to avoid false positives for links or tags
    content_clean = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
    content_clean = re.sub(r"`.*?`", "", content_clean)
    
    # Word count
    word_count = len(content_clean.split())

    # 1. Parse standard Markdown links: [anchor](target.md)
    # Match relative markdown links, ignoring external HTTP URLs
    std_links = re.findall(r"\[[^\]]*\]\(([^)]+\.md)\)", content_clean)
    for link in std_links:
        # Ignore external links or absolute system paths starting with protocols
        if not re.match(r"^[a-zA-Z]+://", link):
            # Normalize path delimiters
            norm = os.path.normpath(link).replace("\\", "/")
            outgoing.add(norm)

    # 2. Parse Wikilinks: [[Note Name]] or [[Note Name|Display]]
    wiki_links = re.findall(r"\[\[(.*?)\]\]", content_clean)
    for link in wiki_links:
        cleaned = clean_wiki_link(link)
        # Find matching relative path if possible, or keep as cleaned name
        matched_rel = all_titles_map.get(cleaned.lower())
        if matched_rel:
            outgoing.add(matched_rel)
        else:
            # Fallback to key
            outgoing.add(cleaned)

    # 3. Parse tags: #tag-name
    # Must start with # and be followed by alphanumeric/dashes, not starting with digits
    # Ensure it's not a hex color or heading structure
    tag_matches = re.finditer(r"\s#([a-zA-Z_][a-zA-Z0-9_\-/]*)", " " + content_clean)
    for match in tag_matches:
        tag = match.group(1).lower()
        # Avoid matching markdown headers (which don't have trailing alphanumeric directly or have spaces)
        tags.add(tag)

    return outgoing, tags, word_count

def build_wiki_graph(dirpath: str) -> Dict[str, WikiNode]:
    """Scan and compile wiki nodes and connect incoming/outgoing links."""
    dirpath = os.path.abspath(dirpath)
    nodes: Dict[str, WikiNode] = {}
    
    # Pre-map all filenames (e.g. 'my_note.md') and base titles to their actual relative paths 
    # to facilitate resolving wikilinks without full paths.
    all_titles_map = {}
    
    for root, _, files in os.walk(dirpath):
        if any(ignored in root for ignored in [".git", "__pycache__", "venv", ".venv"]):
            continue
        for file in files:
            if file.endswith(".md"):
                full_path = os.path.join(root, file)
                rel_path = os.path.relpath(full_path, dirpath).replace("\\", "/")
                
                # Register mapping
                all_titles_map[file.lower()] = rel_path
                all_titles_map[os.path.splitext(file)[0].lower() + ".md"] = rel_path
                
                nodes[rel_path] = WikiNode(full_path, rel_path)

    # Parse notes content
    for rel_path, node in nodes.items():
        outgoing, tags, w_count = parse_note_content(node.filepath, all_titles_map)
        node.outgoing_links = outgoing
        node.tags = tags
        node.word_count = w_count

    # Resolve links back (compute incoming connections)
    for rel_path, node in list(nodes.items()):
        resolved_outgoing = set()
        for target in node.outgoing_links:
            # Resolve target path relative to the node's dir location
            node_dir = os.path.dirname(rel_path)
            target_rel = os.path.normpath(os.path.join(node_dir, target)).replace("\\", "/")
            
            if target_rel in nodes:
                nodes[target_rel].incoming_links.add(rel_path)
                resolved_outgoing.add(target_rel)
            elif target in nodes:
                # If target was already resolved to a vault-relative path
                nodes[target].incoming_links.add(rel_path)
                resolved_outgoing.add(target)
                
        # Keep only successfully resolved internal connections
        node.outgoing_links = resolved_outgoing

    return nodes

def generate_mermaid(nodes: Dict[str, WikiNode]) -> str:
    """Generate Mermaid TD flowchart mapping note dependencies."""
    lines = ["graph TD"]
    
    # Avoid duplicate lines or self-loops
    rendered_edges = set()
    
    for rel_path, node in nodes.items():
        # Short clean ID
        node_id = re.sub(r"[^a-zA-Z0-9]", "_", node.title)
        lines.append(f'    {node_id}["{node.title}"]')
        
    for rel_path, node in nodes.items():
        src_id = re.sub(r"[^a-zA-Z0-9]", "_", node.title)
        for target_rel in node.outgoing_links:
            target_node = nodes[target_rel]
            target_id = re.sub(r"[^a-zA-Z0-9]", "_", target_node.title)
            
            edge = (src_id, target_id)
            if edge not in rendered_edges:
                lines.append(f"    {src_id} --> {target_id}")
                rendered_edges.add(edge)
                
    return "\n".join(lines)

def main():
    parser = argparse.ArgumentParser(
        description="Local Markdown Wiki & Backlink Analyzer"
    )
    parser.add_argument(
        "--dir", default=".", help="Root directory of markdown wiki notes (default: current directory)"
    )
    parser.add_argument(
        "--search", help="Find files containing a search string in their text or title"
    )
    parser.add_argument(
        "--tag", help="Filter and list notes that are tagged with the specified tag"
    )
    parser.add_argument(
        "--backlinks", help="Target note filename/relative path to list all incoming backlinks for"
    )
    parser.add_argument(
        "--mermaid", action="store_true", help="Generate a Mermaid.js diagram definition of the wiki graph"
    )
    args = parser.parse_args()

    target_dir = os.path.abspath(args.dir)
    if not os.path.isdir(target_dir):
        print(f"Error: Directory '{target_dir}' does not exist.", file=sys.stderr)
        sys.exit(1)

    print(f"Scanning wiki vault at: {target_dir}...")
    nodes = build_wiki_graph(target_dir)

    if not nodes:
        print("No markdown (.md) files found in the vault.")
        sys.exit(0)

    # 1. Output Mermaid diagram if requested
    if args.mermaid:
        print("\n--- Mermaid Node Network Definition ---")
        print(generate_mermaid(nodes))
        print("----------------------------------------")
        sys.exit(0)

    # 2. Backlinks lookup
    if args.backlinks:
        # Match target
        target_norm = args.backlinks.replace("\\", "/")
        match = None
        for rel_path, node in nodes.items():
            if target_norm.lower() in [rel_path.lower(), node.title.lower(), os.path.basename(rel_path).lower()]:
                match = node
                break
                
        if not match:
            print(f"Error: Could not find note matching '{args.backlinks}' in the vault.")
            sys.exit(1)
            
        print(f"\n=== Backlinks for: {match.title} ({match.rel_path}) ===")
        if not match.incoming_links:
            print("No incoming backlinks found.")
        else:
            for src_rel in sorted(match.incoming_links):
                src_node = nodes[src_rel]
                print(f"- {src_node.title} ({src_rel})")
        sys.exit(0)

    # 3. Filter by Tag
    if args.tag:
        tag_query = args.tag.lower().lstrip("#")
        print(f"\n=== Notes tagged with: #{tag_query} ===")
        found = False
        for rel_path, node in sorted(nodes.items()):
            if tag_query in node.tags:
                print(f"- {node.title:<30} ({rel_path})")
                found = True
        if not found:
            print("No notes found with that tag.")
        sys.exit(0)

    # 4. Search query
    if args.search:
        query = args.search.lower()
        print(f"\n=== Search Results for query: '{args.search}' ===")
        found = False
        for rel_path, node in sorted(nodes.items()):
            match_title = query in node.title.lower()
            match_body = False
            try:
                with open(node.filepath, "r", encoding="utf-8") as f:
                    if query in f.read().lower():
                        match_body = True
            except Exception:
                pass
                
            if match_title or match_body:
                match_loc = "Title & Content" if (match_title and match_body) else ("Title" if match_title else "Content")
                print(f"- {node.title:<30} ({rel_path}) [Match: {match_loc}]")
                found = True
        if not found:
            print("No matches found in note titles or contents.")
        sys.exit(0)

    # 5. Default General statistics overview
    total_notes = len(nodes)
    total_words = sum(n.word_count for n in nodes.values())
    avg_words = total_words / total_notes if total_notes else 0
    
    # Connectives
    orphans = []
    dead_ends = []
    
    # Collect tags frequency
    tag_counts = {}
    for node in nodes.values():
        if not node.incoming_links and node.outgoing_links:
            orphans.append(node)
        if not node.outgoing_links and node.incoming_links:
            dead_ends.append(node)
        if not node.incoming_links and not node.outgoing_links:
            # Completely disconnected notes
            orphans.append(node)
            
        for tag in node.tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

    # Sort nodes by connection density
    most_connected_outgoing = sorted(nodes.values(), key=lambda n: len(n.outgoing_links), reverse=True)[:5]
    most_connected_incoming = sorted(nodes.values(), key=lambda n: len(n.incoming_links), reverse=True)[:5]

    print("\n================ Wiki Vault Statistics ==================")
    print(f"Total Notes:                {total_notes}")
    print(f"Total Word Count:           {total_words}")
    print(f"Average Words / Note:       {avg_words:.1f}")
    print(f"Unique Tags Found:          {len(tag_counts)}")
    print(f"Disconnected / Orphans:     {len(orphans)}")
    print(f"Dead-ends (no out links):   {len(dead_ends)}")
    
    print("\n--- Top Tag Frequencies ---")
    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:5]
    for tag, cnt in sorted_tags:
        print(f"  #{tag:<25} ({cnt} notes)")
        
    print("\n--- Most Connected Notes (Outgoing) ---")
    for node in most_connected_outgoing:
        if len(node.outgoing_links) > 0:
            print(f"  - {node.title:<30} {len(node.outgoing_links)} links out")
            
    print("\n--- Most Referenced Notes (Backlinks) ---")
    for node in most_connected_incoming:
        if len(node.incoming_links) > 0:
            print(f"  - {node.title:<30} {len(node.incoming_links)} references in")
            
    print("\n--- Disconnected/Orphan Notes ---")
    if not orphans:
        print("  None - All notes are connected!")
    else:
        for node in orphans[:10]:
            print(f"  - {node.title:<30} ({node.rel_path})")
        if len(orphans) > 10:
            print(f"  ... and {len(orphans)-10} more.")
    print("=========================================================")

if __name__ == "__main__":
    main()
