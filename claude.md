# SDIGdata Backend - Context for Claude AI

**Project:** SDIGdata Backend
**Purpose:** Data collection system for Metropolitan Assemblies
**Stack:** FastAPI + PostgreSQL + DigitalOcean Spaces
**Architecture:** Raw SQL (no ORM), JWT auth, Docker deployment

---

## 🧠 Project Context

### What This Is
A production-grade FastAPI backend that powers both a Next.js admin dashboard and mobile clients for field data collection. Used by Metropolitan Assemblies (like Kumasi Metropolitan Assembly) to collect survey data via agents in the field.

### Key Design Decisions

1. **Raw SQL (No ORM)**
   - Direct psycopg queries for performance and clarity
   - All queries in service layer (`app/services/`)
   - No SQLAlchemy or other ORM overhead

2. **JWT Authentication**
   - 24-hour token expiry (configurable)
   - Two roles: `admin` (full access) and `agent` (limited)
   - Bearer token in Authorization header

3. **File Storage**
   - Presigned URLs for direct S3 uploads
   - DigitalOcean Spaces (production) / MinIO (development)
   - No files pass through API

4. **Package Management**
   - Using `uv` (modern Python package manager)
   - Dependencies in `pyproject.toml`
   - Use `[dependency-groups]` not deprecated `[tool.uv.dev-dependencies]`

5. **Migrations**
   - Yoyo migrations (pure SQL files)
   - Located in `migrations/` directory
   - Command: `uv run yoyo apply --database $DATABASE_URL migrations`

---

## 🚨 Critical Information

### API Field Naming (IMPORTANT!)

**The form creation endpoint uses `form_schema` (NOT `schema`) in request bodies:**

```json
POST /forms
{
  "title": "My Form",
  "form_schema": { ... }  // ← Must use form_schema
}
```

**Why?** Pydantic v2 reserves `schema` for JSON schema generation. Using `form_schema` in the request model avoids UserWarning conflicts.

**Note:** Database column is still named `schema`, and response objects return `schema`. Only the **creation request** uses `form_schema`.

### Environment Variables

**Always Required:**
```bash
DATABASE_URL=postgresql://user:pass@host:5432/dbname
SECRET_KEY=<64-char-hex>  # Generate: openssl rand -hex 32
SPACES_ENDPOINT=https://nyc3.digitaloceanspaces.com
SPACES_REGION=nyc3
SPACES_BUCKET=bucket-name
SPACES_KEY=access-key
SPACES_SECRET=secret-key
CORS_ORIGINS=https://app.com,https://admin.app.com
```

### Default Admin Credentials

**Username:** `admin`
**Password:** `admin123` (hash: `$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5oo2lI1kd.JWi`)

**⚠️ MUST CHANGE IN PRODUCTION!**

---

## 📁 Project Structure

```
app/
├── main.py                    # FastAPI app, lifespan, CORS
├── core/
│   ├── config.py             # Pydantic settings
│   ├── db.py                 # psycopg connection management
│   └── security.py           # JWT + bcrypt
├── api/
│   ├── deps.py               # Auth dependencies (get_current_user, require_admin)
│   └── routes/
│       ├── auth.py           # POST /auth/login, /auth/register
│       ├── organizations.py  # Organization CRUD
│       ├── forms.py          # Form CRUD, assignment, CSV export
│       ├── responses.py      # Response submission and retrieval
│       └── files.py          # Presigned URL generation
├── services/                  # Raw SQL queries (NO ORM)
│   ├── users.py
│   ├── organizations.py
│   ├── forms.py
│   └── responses.py
└── utils/
    ├── spaces.py             # boto3 S3 client, presigned URLs
    └── csv_export.py         # Flatten JSON and export to CSV

migrations/
└── 0001_initial_schema.sql   # Complete DB schema with indexes
```

---

## 🗄️ Database Schema

### Tables

**organizations**
- `id` (UUID, PK)
- `name`, `logo_url`, `primary_color`
- `created_at`

**users**
- `id` (UUID, PK)
- `username` (unique), `password_hash`, `role` (admin/agent)
- `organization_id` (FK → organizations)
- `created_at`

**forms**
- `id` (UUID, PK)
- `title`, `organization_id` (FK), `created_by` (FK → users)
- `schema` (JSONB - includes branding and fields)
- `status` (draft/published), `version`
- `created_at`

**form_assignments**
- `id` (UUID, PK)
- `form_id` (FK → forms), `agent_id` (FK → users)
- `assigned_at`
- Unique constraint: (form_id, agent_id)

**responses**
- `id` (UUID, PK)
- `form_id` (FK → forms), `submitted_by` (FK → users)
- `data` (JSONB), `attachments` (JSONB)
- `submitted_at`

### All PKs are UUID, all timestamps are `timestamptz`

---

## 🔐 Authentication Flow

1. **Login:** `POST /auth/login` with `{username, password}`
2. **Returns:** `{access_token, token_type, user}`
3. **Use:** Include in all requests: `Authorization: Bearer <token>`
4. **Expiry:** 24 hours (1440 minutes)

### Dependencies

```python
from app.api.deps import get_current_user, require_admin

# Any authenticated user
@router.get("/protected")
def protected(user = Depends(get_current_user)):
    pass

# Admin only
@router.post("/admin-only")
def admin_only(user = Depends(require_admin)):
    pass
```

---

## 📤 File Upload Pattern

**3-Step Process:**

1. **Get Presigned URL**
   ```python
   POST /files/presign
   {"filename": "photo.jpg", "content_type": "image/jpeg"}
   → {"upload_url": "...", "file_url": "..."}
   ```

2. **Upload to S3** (client-side, direct)
   ```javascript
   PUT <upload_url>
   Content-Type: image/jpeg
   Body: <file binary>
   ```

3. **Submit Response with URL**
   ```python
   POST /responses
   {
     "form_id": "...",
     "data": {...},
     "attachments": {"photo": "<file_url from step 1>"}
   }
   ```

**Key:** Files never pass through API, always direct to S3.

---

## 🛠️ Development Commands

```bash
# Install dependencies
uv sync

# Run migrations
uv run yoyo apply --database $DATABASE_URL migrations

# Start dev server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run with Docker Compose
docker-compose up -d

# View logs
docker-compose logs -f api

# Connect to database
docker-compose exec db psql -U metroform -d metroform

# Verify setup
./verify_setup.sh
```

---

## 🚀 Deployment

### CapRover (Production)

1. Create app in CapRover
2. Set environment variables (see above)
3. Deploy: `caprover deploy`
4. Run migrations manually first time
5. Create admin user in database

### Docker

```bash
# Build
docker build -t sdigdata-backend .

# Run
docker run -p 8000:8000 --env-file .env sdigdata-backend

# Note: Build installs dependencies without lock file (uv sync --no-dev)
# This is fine for Docker since environment is reproducible
```

---

## 🐛 Common Issues

### 1. "UserWarning: Field name 'schema' shadows..."
**Fix:** Already fixed - we use `form_schema` in request models.

### 2. "Unable to determine which files to ship"
**Fix:** Add to `pyproject.toml`:
```toml
[tool.hatch.build.targets.wheel]
packages = ["app"]
```

### 3. Database connection refused
**Fixes:**
- Check `DATABASE_URL` format
- For Docker: use `db` as host (not `localhost`)
- Verify database is running: `docker-compose ps db`

### 4. CORS errors
**Fix:** Add frontend URL to `CORS_ORIGINS` env var

### 5. MinIO bucket not found
**Fix:** API creates automatically on startup. Check logs: `docker-compose logs api`

---

## 📊 Code Patterns

### Service Layer (Raw SQL)

```python
def create_form(conn, title, organization_id, schema, created_by, status="draft"):
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """
            INSERT INTO forms (title, organization_id, schema, status, version, created_by)
            VALUES (%s, %s, %s, %s, 1, %s)
            RETURNING id, title, organization_id, schema, status, version, created_by, created_at
            """,
            (title, str(organization_id), json.dumps(schema), status, str(created_by))
        )
        result = cur.fetchone()
        result['schema'] = json.loads(result['schema'])  # Parse JSONB
        return result
```

### API Routes

```python
@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
def create_form_route(
    request: FormCreate,
    conn: Annotated[psycopg.Connection, Depends(get_db)],
    current_user: Annotated[dict, Depends(get_current_user)]
):
    form = create_form(
        conn,
        title=request.title,
        organization_id=UUID(request.organization_id),
        schema=request.form_schema,  # Note: form_schema in request
        created_by=UUID(current_user['id']),
        status=request.status
    )
    return form
```

---

## 🧪 Testing

### Manual Testing
- Swagger UI: `http://localhost:8000/docs`
- Click "Authorize" and enter: `Bearer <your_token>`

### Health Checks
- Root: `GET /` → Version info
- Health: `GET /health` → `{"status": "healthy"}`

---

## 📝 Form Schema Format

Forms include branding in their JSON schema:

```json
{
  "branding": {
    "logo_url": "https://example.com/logo.png",
    "primary_color": "#0066CC",
    "header_text": "Kumasi Metropolitan Assembly",
    "footer_text": "Thank you for participating"
  },
  "fields": [
    {
      "id": "respondent_name",
      "type": "text",
      "label": "Full Name",
      "required": true
    },
    {
      "id": "location",
      "type": "gps",
      "label": "Location",
      "required": true
    },
    {
      "id": "photo",
      "type": "file",
      "label": "Photo",
      "required": false,
      "accept": "image/*"
    }
  ]
}
```

---

## 🔄 Making Changes

### Adding a New Endpoint

1. Create route in `app/api/routes/`
2. Add service function in `app/services/`
3. Register router in `app/main.py`
4. Test via `/docs`

### Database Changes

1. Create new migration: `uv run yoyo new migrations -m "description"`
2. Write SQL in new file
3. Apply: `uv run yoyo apply migrations`
4. Update service functions

### Adding Dependencies

```bash
uv add package-name          # Add to dependencies
uv add --dev package-name    # Add to dev dependencies
uv sync                      # Install all
```

---

## 📚 Related Files

- **[IMPORTANT.md](IMPORTANT.md)** - Critical info (THIS FILE in detail)
- **[README.md](README.md)** - Full documentation
- **[QUICKSTART.md](QUICKSTART.md)** - 5-minute setup
- **[PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)** - Architecture deep-dive
- **[API_NOTES.md](API_NOTES.md)** - API-specific notes

---

## 🎯 When Helping Users

### Always Check

1. Which environment? (dev/staging/prod)
2. Docker or standalone?
3. Have migrations run?
4. Is admin user created?
5. What do logs show?

### Common Requests

- **"Add new field"** → Update migration + service layer
- **"Change auth"** → Modify `app/api/deps.py` and `app/core/security.py`
- **"Fix CORS"** → Update `CORS_ORIGINS` env var
- **"Deploy help"** → Check [IMPORTANT.md](IMPORTANT.md) deployment section

### Security Reminders

- Always validate `SECRET_KEY` is changed in production
- Verify `CORS_ORIGINS` is restricted
- Check database SSL is enabled
- Confirm default passwords changed

---

## 🔧 Current Status

**Version:** 1.0.0
**Last Updated:** 2025-11-03
**Build Status:** ✅ All checks passing (29/29)
**Dependencies:** ✅ Clean build with uv
**Warnings:** ✅ None (form_schema field renamed)

---

## 💡 Pro Tips

1. **Always use raw SQL** - No ORM means no abstractions to debug
2. **JSONB is your friend** - Store flexible data in `schema`, `data`, `attachments`
3. **UUIDs everywhere** - No auto-increment integers
4. **Presigned URLs** - Never stream files through the API
5. **dict_row factory** - Makes psycopg return dicts instead of tuples
6. **Type hints** - Use them for better IDE support
7. **Docstrings** - All endpoints have request/response examples

---

**Remember:** This is a production-grade system. When making changes:
- Run migrations before code changes
- Test with real JWT tokens
- Check CORS settings
- Verify file uploads work
- Test both admin and agent roles
- Check CSV export functionality

**Documentation hierarchy:**
1. `claude.md` (this file) - Quick context
2. `IMPORTANT.md` - Critical details
3. `README.md` - Complete guide
4. API docs at `/docs` - Interactive testing
