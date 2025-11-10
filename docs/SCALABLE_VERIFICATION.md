# Scalable Database Schema Verification

## Problem

Manually maintaining a list of required database columns in verification scripts is:
- ❌ Not scalable
- ❌ Error-prone
- ❌ Quickly becomes outdated
- ❌ Requires duplicate maintenance (code + verification)

## Solution

We use multiple scalable approaches that don't require manual column maintenance:

### 1. Query-Based Testing (Current Approach)

**Location**: `scripts/verify-db.sh`

**How it works**:
- Tests actual SELECT queries copied from the codebase
- If a column is missing, the query will fail
- No need to list every column manually
- Tests what actually matters: queries that the app runs

**Benefits**:
✅ Tests real usage patterns
✅ Catches issues before they hit production
✅ Self-documenting (shows which queries are critical)
✅ Easy to maintain (just add/update queries as code changes)

**Example**:
```python
# Instead of listing: users needs id, username, email, etc...
# We test the actual query:
test_query(
    cur,
    "User list query",
    "SELECT id, username, email, role FROM users LIMIT 0"
)
```

### 2. Automated Testing (Recommended)

**Location**: `tests/test_database_schema.py`

**How it works**:
- Pytest-based test suite
- Tests extracted from real codebase queries
- Parametrized tests for efficiency
- Can be run in CI/CD pipeline

**Usage**:
```bash
# Run all schema tests
pytest tests/test_database_schema.py -v

# Run specific test
pytest tests/test_database_schema.py::TestDatabaseSchema::test_query_columns_exist -v

# Run with specific database
DATABASE_URL="postgresql://..." pytest tests/test_database_schema.py
```

**Benefits**:
✅ Integrates with CI/CD
✅ Detailed error reporting
✅ Easy to extend with new tests
✅ Industry standard approach

### 3. Query Extraction Tool (Optional)

**Location**: `scripts/extract-queries.py`

**How it works**:
- Scans codebase for SQL queries
- Extracts SELECT statements
- Generates test code automatically

**Usage**:
```bash
# Extract queries and generate test code
python3 scripts/extract-queries.py

# Use output to update verification scripts
```

**Benefits**:
✅ Fully automated
✅ Catches all queries in codebase
✅ Can be run periodically to find new queries

### 4. Migration-Based Verification

**How it works**:
- Verify migrations are applied (check `alembic_version`)
- Trust that migrations define the correct schema
- Test critical paths only

**Benefits**:
✅ Single source of truth (migrations)
✅ Minimal maintenance
✅ Fast execution

## Best Practices

### 1. Keep Verification Scripts Lean

❌ **Don't do this**:
```python
required_columns = {
    'users': ['id', 'username', 'email', 'role', 'status', ...],  # 50 columns
    'forms': ['id', 'title', 'organization_id', ...],  # Manual list
    # ... maintain this forever
}
```

✅ **Do this instead**:
```python
# Test the actual queries used in the app
test_query(cur, "User list", "SELECT id, username FROM users LIMIT 0")
```

### 2. Test Real Usage Patterns

Focus on queries that are actually used in the application, not theoretical completeness.

```python
# Copy queries from your service files
# app/services/users.py:72
test_query(
    cur,
    "User list query from users.py:72",
    "SELECT id, username, email, role FROM users LIMIT 0"
)
```

### 3. Use Pytest for CI/CD

```yaml
# .github/workflows/test.yml
- name: Test Database Schema
  run: |
    export DATABASE_URL="${{ secrets.TEST_DB_URL }}"
    pytest tests/test_database_schema.py -v
```

### 4. Update Tests When Code Changes

When you add a new query to the codebase:
1. Add the query to your service file
2. Add a test case to `test_database_schema.py`
3. Run the test to verify it works

## Maintenance Workflow

### When Adding New Features

1. **Write the code** with new queries:
   ```python
   # app/services/users.py
   result = await conn.fetchrow("""
       SELECT id, username, new_column FROM users
   """)
   ```

2. **Create migration**:
   ```bash
   alembic revision -m "add_new_column"
   ```

3. **Add test** (copy query from code):
   ```python
   # tests/test_database_schema.py
   @pytest.mark.parametrize("query,description", [
       # ... existing tests ...
       (
           "SELECT id, username, new_column FROM users LIMIT 0",
           "User query with new column"
       ),
   ])
   ```

4. **Apply and verify**:
   ```bash
   ./scripts/db-migrate.sh
   pytest tests/test_database_schema.py -v
   ```

### When Queries Change

1. Update the code
2. Update the corresponding test query
3. Run tests to verify

No need to maintain separate column lists!

## Comparison: Before vs After

### Before (Not Scalable)
```python
# Manually maintain complete column lists for all tables
required_columns = {
    'users': [
        'id', 'username', 'email', 'password_hash',
        'role', 'status', 'created_at', 'updated_at',
        'deleted', 'deleted_at', 'last_login',
        'email_notifications', 'theme', 'compact_mode',
        'form_assignments', 'responses', 'system_updates',
        # ... any new column must be added here manually
    ],
    'forms': [...],  # 50+ lines
    'responses': [...],  # More manual lists
    # ... maintain this forever
}

# Check each column exists
for table, columns in required_columns.items():
    for column in columns:
        check_column_exists(table, column)  # 62+ checks
```

**Problems**:
- 62+ columns to maintain manually
- Easy to forget to update
- Duplicates information from migrations
- No clear connection to actual usage

### After (Scalable)
```python
# Test actual queries from the codebase
test_queries = [
    ("SELECT id, username, email FROM users LIMIT 0", "User list"),
    ("SELECT id, title FROM forms LIMIT 0", "Form list"),
    # ... 5-10 critical queries
]

for query, description in test_queries:
    try:
        cursor.execute(query)  # Will fail if columns missing
    except Exception as e:
        report_error(description, e)
```

**Benefits**:
- ~10 queries to maintain (vs 62+ columns)
- Tests real usage patterns
- Self-documenting
- Easy to understand
- Fails fast when issues occur

## Tools Summary

| Tool | Purpose | When to Use |
|------|---------|-------------|
| `scripts/verify-db.sh` | Quick schema validation | Before deployment, after migrations |
| `tests/test_database_schema.py` | Comprehensive testing | CI/CD, development |
| `scripts/extract-queries.py` | Query discovery | Periodic audit, refactoring |
| `scripts/db-migrate.sh` | Apply migrations | Schema changes |

## Recommended Approach

1. **Use pytest tests** as primary verification (best for CI/CD)
2. **Use verify-db.sh** for quick manual checks
3. **Run extract-queries.py** periodically to discover new queries
4. **Trust your migrations** as the source of truth

This approach scales from small projects to large codebases without requiring manual column list maintenance.
