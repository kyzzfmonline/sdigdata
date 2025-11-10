# Async Migration Fix Guide

## Current Status

We've migrated from **psycopg (sync)** to **asyncpg (fully async, NO ORM)** but the automated conversion script broke some files.

### ✅ What's Working:
- Dependencies installed: `asyncpg>=0.30.0`, `alembic>=1.13.0`
- Core infrastructure: `app/core/database.py` (asyncpg connection pool)
- `app/api/deps.py` - Updated to async
- `app/main.py` - Async lifespan with `init_db_pool()` and `close_db_pool()`
- Service files already async: `users.py`, `organizations.py`, `notifications.py`

### ❌ What's Broken:
- `app/services/forms.py` - **IndentationError on line 25**
- `app/services/analytics.py` - May have syntax issues
- `app/services/responses.py` - May have syntax issues
- `app/services/ml_quality.py` - May have syntax issues
- All route files - Function signatures converted but may be missing `await` calls

---

## Fix Steps

### Step 1: Fix forms.py

The automated script broke the indentation. You need to manually review and fix `app/services/forms.py`.

**Problem:** Mixed up `conn.execute()` and `conn.fetchrow()` calls with wrong indentation.

**Pattern to follow:**

```python
# ❌ WRONG (what the script created)
async def create_form(...):
    result = await conn.execute(
            """INSERT INTO forms ...""",
            (params),
        )
        result = await conn.fetchrow(query, *params)  # Wrong indent!

# ✅ CORRECT
async def create_form(...):
    result = await conn.fetchrow(
        """
        INSERT INTO forms (title, organization_id, schema, status, version, created_by)
        VALUES ($1, $2, $3, $4, 1, $5)
        RETURNING id, title, organization_id, schema, status, version, created_by, created_at
        """,
        title, str(organization_id), json.dumps(schema), status, str(created_by)
    )
    return dict(result) if result else None
```

**Key conversion rules for forms.py:**

1. **INSERT/UPDATE with RETURNING** → Use `conn.fetchrow()`
   ```python
   result = await conn.fetchrow("INSERT ... RETURNING *", param1, param2)
   return dict(result) if result else None
   ```

2. **SELECT single row** → Use `conn.fetchrow()`
   ```python
   result = await conn.fetchrow("SELECT * FROM forms WHERE id = $1", form_id)
   return dict(result) if result else None
   ```

3. **SELECT multiple rows** → Use `conn.fetch()`
   ```python
   results = await conn.fetch("SELECT * FROM forms WHERE org_id = $1", org_id)
   return [dict(row) for row in results]
   ```

4. **UPDATE/DELETE without RETURNING** → Use `conn.execute()`
   ```python
   result = await conn.execute("DELETE FROM forms WHERE id = $1", form_id)
   return int(result.split()[-1]) > 0  # Extract row count
   ```

5. **Parameter placeholders:** `%s` → `$1, $2, $3, ...`
   ```python
   # ❌ OLD: WHERE id = %s AND org_id = %s
   # ✅ NEW: WHERE id = $1 AND org_id = $2
   ```

---

### Step 2: Fix analytics.py

Check for similar indentation issues and verify all SQL queries.

**Common patterns in analytics.py:**

```python
# Dashboard stats
async def get_dashboard_stats(conn: asyncpg.Connection, period: str = "7d") -> dict:
    # Get counts
    total_forms = await conn.fetchval(
        "SELECT COUNT(*) FROM forms WHERE created_at > $1",
        start_date
    )

    # Get multiple rows
    response_trend = await conn.fetch(
        """
        SELECT DATE(created_at) as date, COUNT(*) as count
        FROM responses
        WHERE created_at > $1
        GROUP BY DATE(created_at)
        ORDER BY date
        """,
        start_date
    )

    return {
        "total_forms": total_forms,
        "response_trend": [dict(row) for row in response_trend]
    }
```

---

### Step 3: Fix responses.py and ml_quality.py

Similar patterns - check for:
- Proper indentation
- `await` before all `conn.execute()`, `conn.fetch()`, `conn.fetchrow()`, `conn.fetchval()`
- Correct parameter placeholders ($1, $2, not %s)
- Proper dict conversion: `dict(result)` or `[dict(row) for row in results]`

---

### Step 4: Fix Route Files

All route files were converted to `async def` but may be missing `await` calls.

**Files to check:**
- `app/api/routes/auth.py`
- `app/api/routes/users.py`
- `app/api/routes/organizations.py`
- `app/api/routes/forms.py`
- `app/api/routes/responses.py`
- `app/api/routes/files.py`
- `app/api/routes/notifications.py`
- `app/api/routes/analytics.py`
- `app/api/routes/ml.py`

**Pattern to fix:**

```python
# ❌ WRONG (missing await)
@router.post("/forms")
async def create_form(
    request: FormCreate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    form = forms.create_form(conn, ...)  # Missing await!
    return form

# ✅ CORRECT
@router.post("/forms")
async def create_form(
    request: FormCreate,
    conn: Annotated[asyncpg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)],
):
    form = await forms.create_form(conn, ...)  # Has await
    return form
```

**Quick check command:**
```bash
# Find service calls missing await in routes
grep -n "= [a-z_]*\.[a-z_]*(conn" app/api/routes/*.py | grep -v "await"
```

---

### Step 5: Test Syntax

Before rebuilding Docker, test Python syntax:

```bash
# Check all service files
python3 -m py_compile app/services/*.py

# Check all route files
python3 -m py_compile app/api/routes/*.py

# If any fail, you'll see the exact line number of the error
```

---

### Step 6: Rebuild and Test

```bash
# Rebuild Docker
docker-compose down
docker-compose build --no-cache api

# Start services
docker-compose up -d

# Check logs
docker-compose logs api | tail -50

# If successful, you should see:
# "✅ Database pool initialized: 10 / 50 connections"
# "INFO:     Application startup complete."
```

---

### Step 7: Test Login

```bash
# Test login with Argon2
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'

# Should return JWT token and user info
```

---

## Quick Reference: psycopg → asyncpg Conversion

| Operation | psycopg (OLD) | asyncpg (NEW) |
|-----------|---------------|---------------|
| Import | `import psycopg` | `import asyncpg` |
| Function | `def func(conn: psycopg.Connection)` | `async def func(conn: asyncpg.Connection)` |
| Single row | `cur.fetchone()` | `await conn.fetchrow(query, param1, param2)` |
| Multiple rows | `cur.fetchall()` | `await conn.fetch(query, param1, param2)` |
| Single value | `cur.fetchone()["col"]` | `await conn.fetchval(query, param1, param2)` |
| Execute | `cur.execute(query, (p1, p2))` | `await conn.execute(query, p1, p2)` |
| Parameters | `%s, %s` | `$1, $2` |
| Row count | `cur.rowcount` | `int(result.split()[-1])` |
| Dict conversion | `dict(row)` (already dict) | `dict(record)` (asyncpg.Record) |
| Commit | `conn.commit()` | Not needed (auto-commit) |
| Cursor | `with conn.cursor() as cur:` | Direct connection calls |

---

## Common Errors and Fixes

### Error: `NameError: name 'psycopg' is not defined`
**Fix:** Change `import psycopg` → `import asyncpg` in the file

### Error: `IndentationError: unexpected indent`
**Fix:** Review the file for mixed indentation from the conversion script

### Error: `object asyncpg.Record can't be used in 'await' expression`
**Fix:** You're awaiting something that's already awaited. Remove double await.

### Error: `coroutine 'Connection.fetch' was never awaited`
**Fix:** Add `await` before the database call

### Error: `'dict' object has no attribute 'split'`
**Fix:** You're trying to get rowcount from wrong type. Use:
```python
result = await conn.execute(...)  # Returns string like "DELETE 5"
count = int(result.split()[-1])
```

---

## Verification Checklist

- [ ] All service files compile without syntax errors
- [ ] All route files compile without syntax errors
- [ ] `app/services/forms.py` fixed and working
- [ ] `app/services/analytics.py` fixed and working
- [ ] `app/services/responses.py` fixed and working
- [ ] `app/services/ml_quality.py` fixed and working
- [ ] All routes have `await` before service calls
- [ ] Docker builds successfully
- [ ] Application starts without errors
- [ ] Database pool initializes (see in logs)
- [ ] Login endpoint works
- [ ] Tests pass

---

## Need Help?

If you get stuck, the pattern is always:

1. **Service layer** (app/services/*.py):
   - All functions are `async def`
   - All take `conn: asyncpg.Connection`
   - Use `await conn.fetch()` / `await conn.fetchrow()` / `await conn.execute()`
   - Parameters are `$1, $2, $3` not `%s`
   - Return `dict(result)` or `[dict(row) for row in results]`

2. **Route layer** (app/api/routes/*.py):
   - All endpoints are `async def`
   - All service calls have `await` before them
   - Use `conn: Annotated[asyncpg.Connection, Depends(get_db)]`

Good luck! The infrastructure is solid - just needs syntax cleanup.
