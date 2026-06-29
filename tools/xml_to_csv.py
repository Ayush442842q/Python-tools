#!/usr/bin/env python3
"""
XML to CSV Converter
A command-line tool that parses XML documents, flattens nested elements, and
converts them into structured CSV or TSV files. Handles attributes, lists, and
deeply nested XML trees automatically.
"""

import sys
import os
import csv
import xml.etree.ElementTree as ET
import argparse

def extract_record_data(elem):
    """
    Recursively flattens an XML element into a key-value dictionary.
    Formats nested tags as 'parent.child' and attributes as 'element@attribute'.
    Handles repeating child tags as lists (e.g. 'element[0]', 'element[1]').
    """
    data = {}
    
    # Extract attributes of the record itself
    for attr, val in elem.attrib.items():
        data[f"@{attr}"] = val
        
    def recurse(node, path):
        # Count occurrences of child tags to handle arrays
        child_counts = {}
        for child in node:
            child_counts[child.tag] = child_counts.get(child.tag, 0) + 1
            
        child_indices = {}
        for child in node:
            tag = child.tag
            # Determine path segment
            if child_counts[tag] > 1:
                idx = child_indices.get(tag, 0)
                child_indices[tag] = idx + 1
                curr_path = f"{path}.{tag}[{idx}]" if path else f"{tag}[{idx}]"
            else:
                curr_path = f"{path}.{tag}" if path else tag
                
            # Extract child attributes
            for attr, val in child.attrib.items():
                data[f"{curr_path}@{attr}"] = val
                
            # Extract text if it's a leaf node
            text = (child.text or "").strip()
            # Element is a leaf if it has no children and has text
            if len(child) == 0:
                # Only record text if it's not empty, or if we want to store empty values
                data[curr_path] = text
            else:
                # If it's a mixed node (has child elements but also text of its own)
                if text:
                    data[f"{curr_path}#text"] = text
                    
            recurse(child, curr_path)
            
    recurse(elem, "")
    return data

def convert_xml_to_csv(xml_file, csv_file, record_tag=None, delimiter=","):
    """Parses XML and writes the extracted flattened records to CSV."""
    if not os.path.exists(xml_file):
        print(f"Error: XML file '{xml_file}' does not exist.")
        return False
        
    try:
        print(f"Parsing XML file: {xml_file}...")
        tree = ET.parse(xml_file)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"XML Parsing Error: {e}")
        return False
    except Exception as e:
        print(f"Error reading file: {e}")
        return False
        
    # Auto-detect or validate the record tag
    if not record_tag:
        # Find all tags present in children of root
        child_tags = [child.tag for child in root]
        if not child_tags:
            print("Error: The XML root element has no child elements to parse.")
            return False
            
        # Find the most common tag to use as the record tag
        from collections import Counter
        tag_counts = Counter(child_tags)
        record_tag = tag_counts.most_common(1)[0][0]
        print(f"Auto-detected record tag: <{record_tag}> (found {tag_counts[record_tag]} occurrences)")
        
    # Find all elements matching the record tag
    records = root.findall(f".//{record_tag}")
    if not records:
        # Try matching direct children if xpath search fails
        records = [child for child in root if child.tag == record_tag]
        
    if not records:
        print(f"Error: No elements matching record tag <{record_tag}> found in XML.")
        return False
        
    print(f"Found {len(records)} records matching <{record_tag}>. Extracting data...")
    
    # Extract data for all records and collect all unique column headers
    flat_records = []
    headers = set()
    
    for idx, elem in enumerate(records):
        record_data = extract_record_data(elem)
        flat_records.append(record_data)
        headers.update(record_data.keys())
        
    # Sort headers alphabetically for consistent column output, but keep '@' (attributes) first
    sorted_headers = sorted(list(headers), key=lambda x: (not x.startswith('@'), x))
    
    # Write to CSV
    try:
        with open(csv_file, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=sorted_headers, delimiter=delimiter)
            writer.writeheader()
            for record in flat_records:
                # Ensure all missing keys write empty strings
                writer.writerow(record)
                
        print(f"Successfully converted XML to CSV!")
        print(f"Output File: {csv_file}")
        print(f"Total Rows : {len(flat_records)}")
        print(f"Columns    : {len(sorted_headers)}")
        return True
    except Exception as e:
        print(f"Error writing CSV file: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="XML to CSV Converter (with nested element flattening)")
    parser.add_argument("-i", "--input", required=True, help="Path to input XML file")
    parser.add_argument("-o", "--output", required=True, help="Path to output CSV file")
    parser.add_argument("-r", "--record-tag", help="Repeating XML tag identifying each record (auto-detected if omitted)")
    parser.add_argument("-t", "--tsv", action="store_true", help="Output TSV (tab-separated values) instead of CSV")
    parser.add_argument("-d", "--delimiter", default=",", help="Custom CSV field delimiter (default: comma)")
    
    args = parser.parse_args()
    
    delimiter = "\t" if args.tsv else args.delimiter
    if args.tsv and args.delimiter != ",":
        print("Warning: Both --tsv and custom --delimiter specified. Using Tab delimiter.")
        
    success = convert_xml_to_csv(args.input, args.output, args.record_tag, delimiter)
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main()
