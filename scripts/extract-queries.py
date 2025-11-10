#!/usr/bin/env python3
"""
Extract SQL queries from the codebase for automated testing.

This script scans the codebase for SQL queries and extracts SELECT statements
to create a test suite that validates the database schema.
"""

import re
import os
from pathlib import Path
from typing import List, Tuple

def extract_select_queries(file_path: str) -> List[Tuple[str, int, str]]:
    """Extract SELECT queries from a Python file."""
    queries = []

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Pattern to match SQL queries in triple quotes or regular strings
    # This looks for SELECT statements
    patterns = [
        r'"""(.*?SELECT.*?)"""',
        r"'''(.*?SELECT.*?)'''",
        r'\"(SELECT[^\"]+)\"',
        r"'(SELECT[^']+)'",
    ]

    for pattern in patterns:
        matches = re.finditer(pattern, content, re.DOTALL | re.IGNORECASE)
        for match in matches:
            query = match.group(1).strip()
            # Find line number
            line_num = content[:match.start()].count('\n') + 1

            # Clean up the query
            query = ' '.join(query.split())  # Normalize whitespace

            # Only include SELECT queries (exclude INSERT, UPDATE, DELETE for testing)
            if query.upper().startswith('SELECT'):
                queries.append((file_path, line_num, query))

    return queries

def scan_codebase(root_dir: str = 'app') -> List[Tuple[str, int, str]]:
    """Scan the entire codebase for SELECT queries."""
    all_queries = []

    for root, dirs, files in os.walk(root_dir):
        # Skip test directories and migrations
        if 'test' in root or 'migration' in root or '__pycache__' in root:
            continue

        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                queries = extract_select_queries(file_path)
                all_queries.extend(queries)

    return all_queries

def simplify_query_for_testing(query: str) -> str:
    """
    Simplify a query for schema testing by:
    - Removing WHERE clauses (we just want to test column existence)
    - Removing ORDER BY, LIMIT, etc.
    - Adding LIMIT 0 to make it fast
    """
    # Remove everything after WHERE, ORDER BY, GROUP BY, LIMIT
    for keyword in ['WHERE', 'ORDER BY', 'GROUP BY', 'LIMIT', 'OFFSET']:
        pattern = re.compile(f'\\s+{keyword}\\s+', re.IGNORECASE)
        query = pattern.split(query)[0]

    # Add LIMIT 0 to avoid fetching data
    query = query.strip()
    if not query.upper().endswith('LIMIT 0'):
        query += ' LIMIT 0'

    return query

def generate_test_queries() -> List[Tuple[str, str, str]]:
    """Generate a list of unique test queries with metadata."""
    all_queries = scan_codebase()

    # Deduplicate and simplify
    unique_queries = {}
    for file_path, line_num, query in all_queries:
        simplified = simplify_query_for_testing(query)

        # Use simplified query as key to deduplicate
        if simplified not in unique_queries:
            # Extract table name
            table_match = re.search(r'FROM\s+(\w+)', simplified, re.IGNORECASE)
            table = table_match.group(1) if table_match else 'unknown'

            unique_queries[simplified] = {
                'query': simplified,
                'table': table,
                'source': f"{file_path}:{line_num}"
            }

    return [(v['source'], v['table'], v['query']) for v in unique_queries.values()]

if __name__ == '__main__':
    print("Extracting SELECT queries from codebase...")
    print()

    queries = generate_test_queries()

    print(f"Found {len(queries)} unique queries to test:\n")

    for source, table, query in sorted(queries, key=lambda x: x[1]):
        print(f"Table: {table}")
        print(f"Source: {source}")
        print(f"Query: {query[:100]}...")
        print()

    # Generate Python code for the test
    print("\n" + "="*70)
    print("GENERATED TEST CODE")
    print("="*70)
    print()
    print("# Add these tests to verify-db.sh:\n")

    for i, (source, table, query) in enumerate(queries[:10], 1):
        print(f'# Test {i}: {table} ({source})')
        print(f'all_good &= test_query(')
        print(f'    cur,')
        print(f'    "{table} query",')
        print(f'    "{query}"')
        print(f')')
        print()
