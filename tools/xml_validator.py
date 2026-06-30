#!/usr/bin/env python3
"""
XML Schema & Syntax Validator
A utility to parse and validate XML files for well-formedness and schema compliance.
"""

import os
import sys
import argparse
import xml.etree.ElementTree as ET

def check_well_formedness(xml_path):
    """Parses XML and returns (is_valid, error_msg, line, column)."""
    try:
        parser = ET.XMLParser()
        ET.parse(xml_path, parser=parser)
        return True, "File is well-formed XML.", None, None
    except ET.ParseError as e:
        line, col = e.position if e.position else (None, None)
        return False, str(e), line, col
    except Exception as e:
        return False, f"Unexpected error: {str(e)}", None, None

def validate_xsd(xml_path, xsd_path):
    """Validates XML against XSD using lxml if available."""
    try:
        from lxml import etree
    except ImportError:
        return False, "lxml library is required for XSD schema validation. Install it with: pip install lxml"

    try:
        with open(xsd_path, 'rb') as f:
            schema_root = etree.XML(f.read())
        schema = etree.XMLSchema(schema_root)
        
        with open(xml_path, 'rb') as f:
            doc = etree.XML(f.read())
            
        schema.assertValid(doc)
        return True, "XML is valid against the provided XSD schema."
    except etree.DocumentInvalid as e:
        return False, f"Schema validation failed:\n{str(e)}"
    except Exception as e:
        return False, f"Error performing schema validation: {str(e)}"

def main():
    parser = argparse.ArgumentParser(description="XML Schema & Syntax Validator")
    parser.add_argument("xml_file", help="Path to the XML file to validate")
    parser.add_argument("-s", "--schema", help="Path to XSD schema file for validation (requires lxml)")
    parser.add_argument("-w", "--well-formed", action="store_true", help="Only check well-formedness, ignore schema")
    
    args = parser.parse_args()

    if not os.path.exists(args.xml_file):
        print(f"Error: XML file '{args.xml_file}' does not exist.")
        sys.exit(1)

    print(f"Analyzing: {args.xml_file}")
    is_ok, msg, line, col = check_well_formedness(args.xml_file)
    
    if not is_ok:
        print("\n[RESULT] Invalid XML (Syntax Error)")
        print(f"Details: {msg}")
        if line is not None:
            print(f"Position: Line {line}, Column {col}")
            # Try to show snippet
            try:
                with open(args.xml_file, 'r', encoding='utf-8', errors='replace') as f:
                    lines = f.readlines()
                    if 0 < line <= len(lines):
                        target_line = lines[line-1].rstrip('\n')
                        print("\nSnippet:")
                        print(f"  {line}: {target_line}")
                        print("     " + " " * col + "^")
            except Exception:
                pass
        sys.exit(1)

    print("[SUCCESS] XML syntax is well-formed.")

    if args.schema and not args.well_formed:
        print(f"Validating against XSD: {args.schema}")
        if not os.path.exists(args.schema):
            print(f"Error: Schema file '{args.schema}' does not exist.")
            sys.exit(1)
            
        valid, schema_msg = validate_xsd(args.xml_file, args.schema)
        if valid:
            print(f"[SUCCESS] {schema_msg}")
        else:
            print(f"\n[RESULT] Validation Failed")
            print(schema_msg)
            sys.exit(1)

if __name__ == "__main__":
    main()
