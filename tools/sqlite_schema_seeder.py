#!/usr/bin/env python3
"""
SQLite Database Schema Seeder & Faker
Inspects a SQLite database, resolves table foreign key dependencies (topological sort),
and seeds them with referentially-valid mock data.
"""

import sys
import sqlite3
import random
import datetime
import argparse
from collections import defaultdict, deque

# Seed data pools
FIRST_NAMES = ["Alice", "Bob", "Charlie", "David", "Eve", "Frank", "Grace", "Hank", "Ivy", "Jack", "Karl", "Lily", "Mona", "Nate", "Oscar", "Paul", "Quinn", "Rose", "Sam", "Tina"]
LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia", "Miller", "Davis", "Rodriguez", "Martinez", "Hernandez", "Lopez", "Gonzalez", "Wilson", "Anderson", "Thomas", "Taylor", "Moore", "Jackson", "Martin"]
DOMAINS = ["example.com", "testmail.org", "company.net", "service.io", "webmail.com"]
WORDS = ["innovative", "scalable", "secure", "optimized", "cloud", "platform", "database", "analytics", "dashboard", "microservice", "container", "automation", "pipeline", "performance", "monitoring"]
SENTENCES = [
    "This is a sample description of the seeded item.",
    "Highly recommended for daily developer usage.",
    "A clean and automated utility for developers.",
    "Designed to run seamlessly across local environments.",
    "Maintained and optimized by the community contributors."
]

def get_tables(cursor):
    """Retrieves all user tables in the SQLite database."""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
    return [row[0] for row in cursor.fetchall()]

def get_columns(cursor, table_name):
    """Retrieves columns info (name, type, notnull, dflt_value, pk) for a table."""
    cursor.execute(f"PRAGMA table_info({table_name});")
    return cursor.fetchall()

def get_foreign_keys(cursor, table_name):
    """Retrieves foreign keys for a table. Returns list of (table, from_col, to_col)."""
    cursor.execute(f"PRAGMA foreign_key_list({table_name});")
    # Columns in result: id, seq, table, from, to, on_update, on_delete, match
    return [(row[2], row[3], row[4]) for row in cursor.fetchall()]

def topological_sort(tables, deps):
    """
    Sorts tables topologically based on dependencies.
    deps is a dict: table -> set of tables it depends on.
    """
    in_degree = {t: 0 for t in tables}
    adj = defaultdict(list)
    
    for t in tables:
        for dep in deps[t]:
            # dep is the parent table (must be inserted first)
            # t depends on dep, so dep -> t
            if dep in tables: # Only check dependencies within our tables list
                adj[dep].append(t)
                in_degree[t] += 1
                
    queue = deque([t for t in tables if in_degree[t] == 0])
    order = []
    
    while queue:
        u = queue.popleft()
        order.append(u)
        for v in adj[u]:
            in_degree[v] -= 1
            if in_degree[v] == 0:
                queue.append(v)
                
    # If circular dependencies exist, we just append remaining tables
    if len(order) < len(tables):
        remaining = [t for t in tables if t not in order]
        order.extend(remaining)
        
    return order

def generate_mock_value(col_name, col_type, generated_ids):
    """Generates mock data based on column name hints, types, and parent table primary keys."""
    col_name_lower = col_name.lower()
    
    # Check if this is a foreign key column reference we have generated IDs for
    # col_name format is often 'table_id' or 'parent_id'
    for ref_table, ids in generated_ids.items():
        # Match if col_name contains the table name or ends with it
        # E.g., 'user_id' -> match 'user', 'users'
        singular_ref = ref_table.rstrip('s')
        if ids and (col_name_lower == f"{singular_ref}_id" or col_name_lower == f"{ref_table}_id" or col_name_lower.endswith(f"_{singular_ref}id")):
            return random.choice(ids)
            
    # Generate generic data based on column name hints
    if "email" in col_name_lower or "mail" in col_name_lower:
        first = random.choice(FIRST_NAMES).lower()
        last = random.choice(LAST_NAMES).lower()
        domain = random.choice(DOMAINS)
        return f"{first}.{last}@{domain}"
        
    if "phone" in col_name_lower or "tel" in col_name_lower:
        return f"+1-555-{random.randint(100, 999):03d}-{random.randint(1000, 9999):04d}"
        
    if "firstname" in col_name_lower or "first_name" in col_name_lower:
        return random.choice(FIRST_NAMES)
        
    if "lastname" in col_name_lower or "last_name" in col_name_lower:
        return random.choice(LAST_NAMES)
        
    if "name" in col_name_lower or "author" in col_name_lower:
        return f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        
    if "date" in col_name_lower or "time" in col_name_lower or "created" in col_name_lower or "updated" in col_name_lower:
        # Generate random date in past year
        days_ago = random.randint(0, 365)
        dt = datetime.datetime.now() - datetime.timedelta(days=days_ago)
        if "date" in col_type.lower() and "time" not in col_type.lower():
            return dt.date().isoformat()
        return dt.isoformat()
        
    if "desc" in col_name_lower or "content" in col_name_lower or "comment" in col_name_lower:
        return random.choice(SENTENCES)
        
    if "title" in col_name_lower or "subject" in col_name_lower:
        return " ".join(random.sample(WORDS, 2)).title()
        
    if "price" in col_name_lower or "amount" in col_name_lower or "cost" in col_name_lower:
        return round(random.uniform(5.0, 150.0), 2)
        
    if "status" in col_name_lower:
        return random.choice(["active", "pending", "completed", "cancelled"])
        
    # Generate based strictly on SQLite data types
    col_type_upper = col_type.upper()
    if "INT" in col_type_upper:
        return random.randint(1, 1000)
    elif "CHAR" in col_type_upper or "TEXT" in col_type_upper or "CLOB" in col_type_upper:
        return random.choice(WORDS)
    elif "REAL" in col_type_upper or "FLO" in col_type_upper or "DOUB" in col_type_upper:
        return round(random.uniform(1.0, 100.0), 4)
    elif "BLOB" in col_type_upper:
        return b"\x00\x01\x02\x03\x04\x05"
    else:
        # Default fallback
        return "seeded_data"

def seed_database(db_path, num_rows):
    """Main seeding process."""
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        tables = get_tables(cursor)
        if not tables:
            print("❌ No tables found in database. Create your tables/schemas first!")
            return
            
        print(f"Found {len(tables)} tables: {', '.join(tables)}")
        
        # Build dependency graph
        deps = defaultdict(set)
        fk_references = {} # child_table -> list of parent_tables
        
        for table in tables:
            fks = get_foreign_keys(cursor, table)
            fk_references[table] = fks
            for parent_table, _, _ in fks:
                deps[table].add(parent_table)
                
        # Resolve order
        order = topological_sort(tables, deps)
        print("\nResolved seeding order (dependencies first):")
        for idx, table in enumerate(order, 1):
            print(f"  {idx}. {table}")
            
        generated_ids = {} # table -> list of generated primary keys (typically integers)
        
        print("\nSeeding rows...")
        print("-" * 50)
        
        for table in order:
            cols = get_columns(cursor, table)
            # Columns: cid, name, type, notnull, dflt_value, pk
            
            # Find primary key column
            pk_col = None
            pk_type = "INTEGER"
            insert_cols = []
            
            for col in cols:
                # col structure: (cid, name, type, notnull, dflt_value, pk)
                c_name, c_type, pk = col[1], col[2], col[5]
                if pk == 1:
                    pk_col = c_name
                    pk_type = c_type
                # We skip autoincrement / integer primary keys during insertions
                if pk == 1 and "INT" in c_type.upper():
                    continue
                insert_cols.append((c_name, c_type))
                
            # Perform insertions
            table_ids = []
            success_count = 0
            
            # Disable foreign keys temporarily if needed, but we try to respect them
            cursor.execute("PRAGMA foreign_keys = ON;")
            
            for _ in range(num_rows):
                row_data = {}
                col_names = []
                col_vals = []
                
                # Check for table foreign key dependencies
                # We overwrite the generated values with actual matching parent IDs
                for c_name, c_type in insert_cols:
                    val = generate_mock_value(c_name, c_type, generated_ids)
                    row_data[c_name] = val
                    
                # Explicitly override with parent foreign key matches
                fks = fk_references.get(table, [])
                for parent_table, from_col, to_col in fks:
                    if parent_table in generated_ids and generated_ids[parent_table]:
                        row_data[from_col] = random.choice(generated_ids[parent_table])
                        
                for k, v in row_data.items():
                    col_names.append(k)
                    col_vals.append(v)
                    
                placeholders = ", ".join(["?"] * len(col_names))
                cols_str = ", ".join(col_names)
                query = f"INSERT INTO {table} ({cols_str}) VALUES ({placeholders});"
                
                try:
                    cursor.execute(query, col_vals)
                    success_count += 1
                    
                    # Capture generated ID if it was auto-incremented
                    if pk_col and "INT" in pk_type.upper():
                        table_ids.append(cursor.lastrowid)
                    else:
                        # Otherwise capture what we inserted
                        if pk_col in row_data:
                            table_ids.append(row_data[pk_col])
                except sqlite3.Error as e:
                    # Log warning but continue
                    pass
                    
            generated_ids[table] = table_ids
            print(f"  Table '{table}': Successfully seeded {success_count}/{num_rows} rows.")
            
        conn.commit()
        print("-" * 50)
        print("✅ Database seeding complete.")
        conn.close()
        
    except sqlite3.Error as e:
        print(f"❌ SQLite Error: {e}")
    except Exception as e:
        print(f"❌ Unexpected Error: {e}")

def main():
    parser = argparse.ArgumentParser(description="SQLite Database Schema Seeder & Faker")
    parser.add_argument("db_path", help="Path to the SQLite database file")
    parser.add_argument("-r", "--rows", type=int, default=10, help="Number of rows to seed per table (default: 10)")
    args = parser.parse_args()
    
    seed_database(args.db_path, args.rows)

if __name__ == "__main__":
    main()
