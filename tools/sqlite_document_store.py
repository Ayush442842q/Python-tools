#!/usr/bin/env python3
"""
SQLite JSON Document Store Wrapper

A command-line utility implementing a MongoDB-like document-store interface
(collections, insert, find, update, delete, indexing) on top of a standard SQLite database.
Utilizes SQLite's native JSON support (available in standard Python sqlite3).
"""

import sys
import os
import sqlite3
import json
import uuid
import argparse
import re
from typing import Any, Dict, List, Optional, Union

# ANSI Color Escape Codes
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
BOLD = "\033[1m"
RESET = "\033[0m"

def colored(text: str, color_code: str) -> str:
    if sys.platform == "win32":
        import os
        os.system("")
    return f"{color_code}{text}{RESET}"

class DocumentStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row
        
    def close(self):
        self.conn.close()

    def _get_table_name(self, collection: str) -> str:
        """Sanitize collection name to table name."""
        if not re.match(r"^[a-zA-Z_][a-zA-Z0-9_]*$", collection):
            raise ValueError(f"Invalid collection name: {collection}. Only alphanumeric characters and underscores are allowed.")
        return f"col_{collection}"

    def create_collection(self, collection: str):
        table = self._get_table_name(collection)
        cursor = self.conn.cursor()
        cursor.execute(f"""
            CREATE TABLE IF NOT EXISTS {table} (
                id TEXT PRIMARY KEY,
                doc TEXT
            )
        """)
        self.conn.commit()

    def list_collections(self) -> List[Dict[str, Any]]:
        cursor = self.conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'col_%'")
        tables = cursor.fetchall()
        
        collections = []
        for row in tables:
            table_name = row['name']
            col_name = table_name[4:] # Strip 'col_'
            cursor.execute(f"SELECT COUNT(*) as cnt FROM {table_name}")
            cnt = cursor.fetchone()['cnt']
            collections.append({"name": col_name, "count": cnt})
        return collections

    def insert(self, collection: str, doc: Dict[str, Any]) -> str:
        self.create_collection(collection)
        table = self._get_table_name(collection)
        
        if "_id" not in doc:
            doc["_id"] = str(uuid.uuid4())
        
        doc_id = str(doc["_id"])
        doc_str = json.dumps(doc)
        
        cursor = self.conn.cursor()
        cursor.execute(
            f"INSERT OR REPLACE INTO {table} (id, doc) VALUES (?, ?)",
            (doc_id, doc_str)
        )
        self.conn.commit()
        return doc_id

    def _resolve_key(self, doc: Dict[str, Any], path: str) -> Any:
        """Resolve nested dotted paths in document (e.g. 'address.city')."""
        parts = path.split('.')
        curr = doc
        for part in parts:
            if isinstance(curr, dict) and part in curr:
                curr = curr[part]
            else:
                return None
        return curr

    def _match_operator(self, doc_val: Any, op: str, filter_val: Any) -> bool:
        if op == "$eq":
            return doc_val == filter_val
        elif op == "$ne":
            return doc_val != filter_val
        elif op == "$gt":
            try: return doc_val > filter_val
            except: return False
        elif op == "$gte":
            try: return doc_val >= filter_val
            except: return False
        elif op == "$lt":
            try: return doc_val < filter_val
            except: return False
        elif op == "$lte":
            try: return doc_val <= filter_val
            except: return False
        elif op == "$in":
            return isinstance(filter_val, list) and doc_val in filter_val
        elif op == "$nin":
            return isinstance(filter_val, list) and doc_val not in filter_val
        elif op == "$exists":
            exists = doc_val is not None
            return exists == bool(filter_val)
        elif op == "$regex":
            try:
                pattern = re.compile(str(filter_val), re.IGNORECASE)
                return bool(pattern.search(str(doc_val)))
            except:
                return False
        return False

    def _matches_filter(self, doc: Dict[str, Any], query: Dict[str, Any]) -> bool:
        """Check if document matches MongoDB-like query filter."""
        if not query:
            return True
            
        for key, val in query.items():
            if key == "$and":
                if not isinstance(val, list): return False
                if not all(self._matches_filter(doc, q) for q in val): return False
            elif key == "$or":
                if not isinstance(val, list): return False
                if not any(self._matches_filter(doc, q) for q in val): return False
            elif key == "$not":
                if not isinstance(val, dict): return False
                if self._matches_filter(doc, val): return False
            else:
                # Dotted path lookup
                doc_val = self._resolve_key(doc, key)
                if isinstance(val, dict):
                    # Operator dict like {"$gt": 10}
                    for op, op_val in val.items():
                        if op.startswith('$'):
                            if not self._match_operator(doc_val, op, op_val):
                                return False
                        else:
                            # Subdocument match
                            if doc_val != val:
                                return False
                else:
                    # Direct match
                    if doc_val != val:
                        return False
        return True

    def find(self, collection: str, query: Dict[str, Any] = {}) -> List[Dict[str, Any]]:
        table = self._get_table_name(collection)
        cursor = self.conn.cursor()
        
        # Check if table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,))
        if not cursor.fetchone():
            return []
            
        cursor.execute(f"SELECT doc FROM {table}")
        rows = cursor.fetchall()
        
        results = []
        for row in rows:
            doc = json.loads(row['doc'])
            if self._matches_filter(doc, query):
                results.append(doc)
        return results

    def update(self, collection: str, query: Dict[str, Any], update_ops: Dict[str, Any]) -> int:
        table = self._get_table_name(collection)
        docs = self.find(collection, query)
        if not docs:
            return 0
            
        cursor = self.conn.cursor()
        updated_count = 0
        
        for doc in docs:
            doc_id = doc["_id"]
            
            # Apply MongoDB-like update operators
            modified = False
            
            # $set operator
            if "$set" in update_ops:
                for k, v in update_ops["$set"].items():
                    # Support nested dictionary setting
                    parts = k.split('.')
                    curr = doc
                    for part in parts[:-1]:
                        if part not in curr or not isinstance(curr[part], dict):
                            curr[part] = {}
                        curr = curr[part]
                    curr[parts[-1]] = v
                    modified = True
                    
            # $unset operator
            if "$unset" in update_ops:
                for k in update_ops["$unset"].keys():
                    parts = k.split('.')
                    curr = doc
                    for part in parts[:-1]:
                        if isinstance(curr, dict) and part in curr:
                            curr = curr[part]
                    if isinstance(curr, dict) and parts[-1] in curr:
                        del curr[parts[-1]]
                        modified = True
                        
            if modified:
                cursor.execute(
                    f"UPDATE {table} SET doc = ? WHERE id = ?",
                    (json.dumps(doc), doc_id)
                )
                updated_count += 1
                
        self.conn.commit()
        return updated_count

    def delete(self, collection: str, query: Dict[str, Any]) -> int:
        table = self._get_table_name(collection)
        docs = self.find(collection, query)
        if not docs:
            return 0
            
        cursor = self.conn.cursor()
        deleted_count = 0
        for doc in docs:
            doc_id = doc["_id"]
            cursor.execute(f"DELETE FROM {table} WHERE id = ?", (doc_id,))
            deleted_count += 1
            
        self.conn.commit()
        return deleted_count

    def create_index(self, collection: str, field_path: str):
        """Creates an expression-based index on a JSON field for faster sorting/lookup in SQLite."""
        self.create_collection(collection)
        table = self._get_table_name(collection)
        index_name = f"idx_{collection}_{field_path.replace('.', '_')}"
        
        # SQLite json_extract extracts values. Let's use it to build index
        # SQLite path syntax uses $.field
        sqlite_path = f"$.{field_path}"
        query = f"CREATE INDEX IF NOT EXISTS {index_name} ON {table}(json_extract(doc, '{sqlite_path}'))"
        
        cursor = self.conn.cursor()
        cursor.execute(query)
        self.conn.commit()

def print_pretty_json(doc: Any):
    """Print JSON with basic terminal coloring."""
    json_str = json.dumps(doc, indent=2)
    # Simple syntax coloring for keys and values
    colored_lines = []
    for line in json_str.split('\n'):
        # Match keys
        line = re.sub(r'(".*?")\s*:', lambda m: f"{colored(m.group(1), BOLD + CYAN)}:", line)
        # Match string values
        line = re.sub(r':\s*(".*?")', lambda m: f": {colored(m.group(1), GREEN)}", line)
        # Match numbers/booleans/null
        line = re.sub(r':\s*(true|false|null|\d+(?:\.\d+)?)', lambda m: f": {colored(m.group(1), MAGENTA)}", line)
        colored_lines.append(line)
    print('\n'.join(colored_lines))

def main():
    parser = argparse.ArgumentParser(description="SQLite JSON Document Store CLI Wrapper")
    parser.add_argument("--db", default="docstore.db", help="Path to SQLite database file (default: docstore.db)")
    
    subparsers = parser.add_argument_split = parser.add_subparsers(dest="command", help="Command to run")
    
    # List Collections
    subparsers.add_parser("list", help="List all collections")
    
    # Insert
    p_insert = subparsers.add_parser("insert", help="Insert a document into a collection")
    p_insert.add_argument("collection", help="Collection name")
    p_insert.add_argument("doc", help="JSON document string or path to JSON file")
    
    # Find
    p_find = subparsers.add_parser("find", help="Find documents in a collection")
    p_find.add_argument("collection", help="Collection name")
    p_find.add_argument("query", nargs="?", default="{}", help="Query filter JSON string (default: {})")
    
    # Update
    p_update = subparsers.add_parser("update", help="Update documents in a collection")
    p_update.add_argument("collection", help="Collection name")
    p_update.add_argument("query", help="Query filter JSON string")
    p_update.add_argument("update", help="Update operators JSON string (e.g. '{\"$set\": {\"a\": 1}}')")
    
    # Delete
    p_delete = subparsers.add_parser("delete", help="Delete documents from a collection")
    p_delete.add_argument("collection", help="Collection name")
    p_delete.add_argument("query", help="Query filter JSON string")
    
    # Index
    p_index = subparsers.add_parser("create-index", help="Create index on a document field")
    p_index.add_argument("collection", help="Collection name")
    p_index.add_argument("field", help="Dotted field path (e.g. 'profile.age')")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return

    store = DocumentStore(args.db)
    
    try:
        if args.command == "list":
            cols = store.list_collections()
            print(colored(f"\nCollections in database: {args.db}", BOLD + YELLOW))
            print(colored("-" * 40, BOLD))
            print(f"{'Collection Name':<25} | {'Document Count':<12}")
            print(colored("-" * 40, BOLD))
            for c in cols:
                print(f"{c['name']:<25} | {c['count']:<12}")
            print()
            
        elif args.command == "insert":
            # Load JSON
            try:
                if os.path.exists(args.doc):
                    with open(args.doc, 'r') as f:
                        doc_data = json.load(f)
                else:
                    doc_data = json.loads(args.doc)
            except Exception as e:
                print(colored(f"[!] Error parsing JSON document: {e}", RED))
                return
                
            if not isinstance(doc_data, dict):
                print(colored("[!] Error: Document must be a JSON object (dictionary)", RED))
                return
                
            doc_id = store.insert(args.collection, doc_data)
            print(colored(f"✓ Inserted document successfully. _id: {doc_id}", GREEN))
            
        elif args.command == "find":
            try:
                query_data = json.loads(args.query)
            except Exception as e:
                print(colored(f"[!] Error parsing query JSON: {e}", RED))
                return
                
            results = store.find(args.collection, query_data)
            print(colored(f"\nFound {len(results)} matching documents in '{args.collection}':", BOLD + YELLOW))
            for doc in results:
                print_pretty_json(doc)
                print(colored("-" * 40, BOLD))
            print()
            
        elif args.command == "update":
            try:
                query_data = json.loads(args.query)
                update_data = json.loads(args.update)
            except Exception as e:
                print(colored(f"[!] Error parsing JSON parameters: {e}", RED))
                return
                
            cnt = store.update(args.collection, query_data, update_data)
            print(colored(f"✓ Updated {cnt} documents in '{args.collection}'.", GREEN))
            
        elif args.command == "delete":
            try:
                query_data = json.loads(args.query)
            except Exception as e:
                print(colored(f"[!] Error parsing query JSON: {e}", RED))
                return
                
            cnt = store.delete(args.collection, query_data)
            print(colored(f"✓ Deleted {cnt} documents from '{args.collection}'.", GREEN))
            
        elif args.command == "create-index":
            store.create_index(args.collection, args.field)
            print(colored(f"✓ Created index on field '{args.field}' in collection '{args.collection}'.", GREEN))
            
    except Exception as e:
        print(colored(f"[!] Database error: {e}", RED))
    finally:
        store.close()

if __name__ == "__main__":
    main()
