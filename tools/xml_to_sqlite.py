#!/usr/bin/env python3
"""
XML to SQLite Relational Converter
A zero-dependency Python utility to parse XML files, dynamically infer a relational database schema,
create corresponding SQLite tables, and import the hierarchical data while preserving node relationships.
"""

import argparse
import os
import sqlite3
import sys
import xml.etree.ElementTree as ET
from typing import Dict, List, Set, Tuple


class XMLSqliteConverter:
    """Infers relational schemas from XML trees and imports elements to SQLite databases."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        
        # Schema tracking: table_name -> set of column names
        self.schema: Dict[str, Set[str]] = {}
        # Parent relations: child_table -> parent_table name
        self.parents: Dict[str, str] = {}

    def sanitize_name(self, name: str) -> str:
        """Sanitizes tag or attribute names for SQL safety."""
        # Remove namespaces or special chars, convert to lowercase
        clean = name.split("}")[-1].lower()  # Remove XML namespace prefix
        clean = "".join(c for c in clean if c.isalnum() or c == "_")
        
        # Avoid reserved words
        reserved = {"group", "order", "select", "table", "index", "column", "key", "id", "check"}
        if clean in reserved:
            return f"xml_{clean}"
        return clean

    def infer_schema(self, node: ET.Element, parent_table: str = None):
        """Recursively walks the XML tree to gather tables, columns, and parent relations."""
        table_name = self.sanitize_name(node.tag)
        
        if table_name not in self.schema:
            self.schema[table_name] = set()

        if parent_table:
            # Map child to parent key
            self.parents[table_name] = parent_table
            self.schema[table_name].add(f"parent_{parent_table}_id")

        # Gather attribute columns
        for attr_name in node.attrib:
            col_name = self.sanitize_name(attr_name)
            # Avoid name collision with autoincrement id
            if col_name == "id":
                col_name = "attr_id"
            self.schema[table_name].add(col_name)

        # Check sub-elements to classify as values (columns) or relational child tables
        for child in node:
            child_name = self.sanitize_name(child.tag)
            
            # If child has child elements or attributes, it's a separate entity/table
            has_children = len(child) > 0
            has_attributes = len(child.attrib) > 0
            
            if has_children or has_attributes:
                self.infer_schema(child, parent_table=table_name)
            else:
                # Leaf element with text value: treat as a column in current table
                self.schema[table_name].add(child_name)

    def create_database_tables(self):
        """Creates the inferred SQLite tables with appropriate schema and foreign keys."""
        cursor = self.conn.cursor()
        
        for table, columns in self.schema.items():
            col_definitions = ["id INTEGER PRIMARY KEY AUTOINCREMENT"]
            foreign_keys = []
            
            for col in sorted(columns):
                # Avoid redefining id
                if col == "id":
                    continue
                
                # Check if it is a parent foreign key
                if col.startswith("parent_") and col.endswith("_id"):
                    parent_table = col[7:-3]
                    col_definitions.append(f"{col} INTEGER")
                    foreign_keys.append(f"FOREIGN KEY({col}) REFERENCES {parent_table}(id) ON DELETE CASCADE")
                else:
                    col_definitions.append(f"{col} TEXT")
            
            # Combine columns and constraints
            all_defs = col_definitions + foreign_keys
            create_query = f"CREATE TABLE IF NOT EXISTS {table} ({', '.join(all_defs)});"
            cursor.execute(create_query)
            
        self.conn.commit()

    def insert_elements(self, node: ET.Element, parent_id: int = None, parent_table: str = None) -> int:
        """Recursively inserts XML elements and child nodes into database tables."""
        cursor = self.conn.cursor()
        table_name = self.sanitize_name(node.tag)
        
        row_data: Dict[str, str] = {}
        
        # Populate parent foreign key
        if parent_table and parent_id is not None:
            row_data[f"parent_{parent_table}_id"] = str(parent_id)

        # Populate attributes
        for attr_name, attr_val in node.attrib.items():
            col_name = self.sanitize_name(attr_name)
            if col_name == "id":
                col_name = "attr_id"
            row_data[col_name] = attr_val

        # Populate text values (leaf child elements) and recurse sub-elements (child tables)
        sub_elements_to_recurse: List[ET.Element] = []
        
        for child in node:
            child_name = self.sanitize_name(child.tag)
            
            has_children = len(child) > 0
            has_attributes = len(child.attrib) > 0
            
            if has_children or has_attributes:
                sub_elements_to_recurse.append(child)
            else:
                # Text node value
                row_data[child_name] = child.text.strip() if child.text else ""

        # Insert record into table
        if row_data:
            columns = list(row_data.keys())
            placeholders = ", ".join(["?"] * len(columns))
            insert_query = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"
            cursor.execute(insert_query, list(row_data.values()))
            inserted_id = cursor.lastrowid
        else:
            # Empty element placeholder insert
            cursor.execute(f"INSERT INTO {table_name} DEFAULT VALUES")
            inserted_id = cursor.lastrowid

        # Recurse for nested child tables
        for child in sub_elements_to_recurse:
            self.insert_elements(child, parent_id=inserted_id, parent_table=table_name)
            
        return inserted_id

    def close(self):
        self.conn.commit()
        self.conn.close()


def main():
    parser = argparse.ArgumentParser(
        description="XML to SQLite Relational Converter. "
                    "Parses XML files, infers a schema, and imports data to SQLite tables."
    )
    parser.add_argument("xml_file", help="Path to input XML file")
    parser.add_argument("-d", "--database", help="Path to output SQLite database file (default: input_file.db)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Print schema information during execution")
    
    args = parser.parse_args()
    
    if not os.path.exists(args.xml_file):
        print(f"[-] Error: File not found: {args.xml_file}", file=sys.stderr)
        sys.exit(1)
        
    db_path = args.database if args.database else f"{os.path.splitext(args.xml_file)[0]}.db"
    
    # Remove existing db to ensure clean import
    if os.path.exists(db_path):
        try:
            os.remove(db_path)
        except OSError as e:
            print(f"[-] Error removing existing database: {e}", file=sys.stderr)
            sys.exit(1)

    print(f"[*] Parsing XML structure from {args.xml_file}...")
    try:
        tree = ET.parse(args.xml_file)
        root = tree.getroot()
    except ET.ParseError as e:
        print(f"[-] XML parsing error: {e}", file=sys.stderr)
        sys.exit(1)

    converter = XMLSqliteConverter(db_path)
    
    print("[*] Inferring database schema...")
    converter.infer_schema(root)
    
    if args.verbose:
        print("[+] Inferred Tables and Columns:")
        for t, cols in converter.schema.items():
            print(f"    Table: {t}")
            for c in sorted(cols):
                print(f"      - {c}")
                
    print(f"[*] Creating SQLite database tables in {db_path}...")
    converter.create_database_tables()
    
    print("[*] Inserting elements into relational database...")
    converter.conn.execute("PRAGMA foreign_keys = ON;")
    converter.insert_elements(root)
    
    converter.close()
    print(f"[+] Success: Relational database created at {db_path}")


if __name__ == "__main__":
    main()
