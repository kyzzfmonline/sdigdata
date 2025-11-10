# 🚨 IMPORTANT - Critical Information for SDIGdata Backend

**READ THIS FIRST** - Essential information for developers, DevOps, and integrators.

---

## 📋 Table of Contents

1. [API Field Naming Changes](#api-field-naming-changes)
2. [Environment Variables](#environment-variables)
3. [Database Configuration](#database-configuration)
4. [Authentication & Security](#authentication--security)
5. [File Upload Flow](#file-upload-flow)
6. [Deployment Requirements](#deployment-requirements)
7. [Common Gotchas](#common-gotchas)
8. [Integration Notes](#integration-notes)

---

## 🔴 API Field Naming Changes

### **CRITICAL: Form Creation Field Name**

The form creation endpoint uses `form_schema` (NOT `schema`) in request bodies:

**✅ CORRECT:**
```json
POST /forms
{
  "title": "Household Survey 2025",
  "organization_id": "550e8400-e29b-41d4-a716-446655440000",
  "form_schema": {
    "branding": { ... },
    "fields": [ ... ]
  }
}
```

**❌ WRONG:**
```json
{
  "schema": { ... }  // This will fail
}
```

**Why?** Pydantic v2 reserves `schema` for JSON schema generation. Using `form_schema` avoids conflicts.

**Note:** Response objects and database still use `schema` - only the creation request uses `form_schema`.

---

## 🔐 Environment Variables

### **Required in Production**

```bash
# Database - REQUIRED
DATABASE_URL=postgresql://user:password@host:5432/dbname

# JWT Security - REQUIRED (Generate with: openssl rand -hex 32)
SECRET_KEY=your_64_character_secret_key_here_generate_new_for_prod

# DigitalOcean Spaces - REQUIRED
SPACES_ENDPOINT=https://nyc3.digitaloceanspaces.com
SPACES_REGION=nyc3
SPACES_BUCKET=your-bucket-name
SPACES_KEY=your-spaces-access-key
SPACES_SECRET=your-spaces-secret-key

# CORS - REQUIRED (comma-separated)
CORS_ORIGINS=https://yourdomain.com,https://admin.yourdomain.com
```

### **Optional (with defaults)**

```bash
JWT_ALGORITHM=HS256                    # Default: HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440       # Default: 24 hours
ENVIRONMENT=production                 # Default: development
```

### **Development (MinIO)**

```bash
SPACES_ENDPOINT=http://minio:9000
SPACES_REGION=us-east-1
SPACES_BUCKET=metroform-dev
SPACES_KEY=minio
SPACES_SECRET=miniopass
```

---

## 🗄️ Database Configuration

### **PostgreSQL Requirements**

- **Version:** PostgreSQL 16+ (tested)
- **Extensions:** `uuid-ossp` (auto-created in migration)
- **Encoding:** UTF-8
- **Min Resources:** 1GB RAM, 10GB disk

### **Connection String Format**

```bash
# Standard format
postgresql://username:password@host:port/database

# With SSL (production)
postgresql://username:password@host:port/database?sslmode=require

# Local development
postgresql://metroform:password@localhost:5432/metroform
```

### **Initial Setup**

**CRITICAL:** Before first use, create an admin user:

```sql
-- 1. Create organization
INSERT INTO organizations (name, logo_url, primary_color)
VALUES ('Your Organization', 'https://...', '#0066CC')
RETURNING id;

-- 2. Create admin user (replace ORG_ID with ID from step 1)
INSERT INTO users (username, password_hash, role, organization_id)
VALUES (
    'admin',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5oo2lI1kd.JWi',  -- password: admin123
    'admin',
    'ORG_ID'  -- Replace with actual UUID
);
```

**⚠️ CHANGE DEFAULT PASSWORD IN PRODUCTION!**

Generate new hash:
```python
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
print(pwd_context.hash("your_secure_password"))
```

---

## 🔒 Authentication & Security

### **JWT Token Flow**

1. **Login:** `POST /auth/login` → Returns `access_token`
2. **Use:** Include in all requests: `Authorization: Bearer <token>`
3. **Expiry:** 24 hours (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`)

### **Roles**

| Role    | Permissions                                              |
|---------|----------------------------------------------------------|
| `admin` | Full access: create forms, assign agents, export data   |
| `agent` | Limited: view assigned forms, submit responses           |

### **Security Checklist for Production**

- [ ] Change `SECRET_KEY` (generate new: `openssl rand -hex 32`)
- [ ] Change default admin password
- [ ] Enable HTTPS only
- [ ] Set `CORS_ORIGINS` to your actual domains
- [ ] Use DigitalOcean Spaces (not MinIO)
- [ ] Enable database SSL (`sslmode=require`)
- [ ] Restrict database access (firewall/VPN)
- [ ] Set up SSL certificates
- [ ] Enable rate limiting (via reverse proxy)
- [ ] Regular backups (daily recommended)

---

## 📤 File Upload Flow

### **Complete Flow (3 Steps)**

**Step 1: Get Presigned URL**
```bash
POST /files/presign
Authorization: Bearer <token>

{
  "filename": "photo.jpg",
  "content_type": "image/jpeg"
}

Response:
{
  "upload_url": "https://...",  // Use this to upload
  "file_url": "https://..."     // Save this in response
}
```

**Step 2: Upload File (Direct to S3)**
```bash
PUT <upload_url>
Content-Type: image/jpeg

<binary file data>
```

**Step 3: Submit Response with File URL**
```bash
POST /responses
Authorization: Bearer <token>

{
  "form_id": "...",
  "data": { ... },
  "attachments": {
    "photo": "<file_url from step 1>"
  }
}
```

**IMPORTANT:**
- Upload happens DIRECTLY to S3 (not through API)
- Presigned URLs expire in 1 hour (default)
- Save `file_url` (not `upload_url`) in your response

---

## 🚀 Deployment Requirements

### **CapRover (Recommended)**

**Requirements:**
- Docker installed on server
- CapRover installed and configured
- PostgreSQL database (managed or external)
- DigitalOcean Spaces account

**Deployment Steps:**

1. Create app in CapRover
2. Set environment variables (see above)
3. Deploy: `caprover deploy`
4. Run migrations manually first time:
   ```bash
   caprover run --appName sdigdata -- uv run yoyo apply migrations
   ```

### **Docker Compose (Development)**

```bash
# Start everything
docker-compose up -d

# Check logs
docker-compose logs -f api

# Stop
docker-compose down
```

### **Standalone Docker**

```bash
# Build
docker build -t sdigdata-backend .

# Run (with external DB)
docker run -p 8000:8000 \
  -e DATABASE_URL=postgresql://... \
  -e SECRET_KEY=... \
  -e SPACES_ENDPOINT=... \
  sdigdata-backend
```

---

## ⚠️ Common Gotchas

### **1. Database Connection Issues**

**Problem:** `connection refused` or `could not connect to server`

**Solutions:**
- Check `DATABASE_URL` format
- Verify database is running
- Check firewall rules
- For Docker: use `db` as hostname (not `localhost`)
- For SSL: add `?sslmode=require` to connection string

### **2. CORS Errors**

**Problem:** Frontend gets CORS errors

**Solutions:**
- Add frontend URL to `CORS_ORIGINS` environment variable
- Use comma-separated list: `https://app.com,https://admin.app.com`
- Include protocol (`https://` or `http://`)
- No trailing slashes

### **3. MinIO Bucket Not Created**

**Problem:** "NoSuchBucket" error in development

**Solutions:**
- API creates bucket automatically on startup
- Check API logs: `docker-compose logs api`
- Manually create: `docker-compose exec minio mc mb local/metroform-dev`
- Verify MinIO is running: `docker-compose ps minio`

### **4. JWT Token Invalid**

**Problem:** "Invalid authentication credentials"

**Solutions:**
- Token may have expired (24h default)
- Login again to get new token
- Check `SECRET_KEY` hasn't changed
- Verify token format: `Bearer <token>`

### **5. Migration Fails**

**Problem:** Yoyo migration errors

**Solutions:**
- Check database exists
- Verify database user has CREATE permissions
- Run manually: `uv run yoyo apply --database $DATABASE_URL migrations`
- Check migration history: `uv run yoyo list --database $DATABASE_URL migrations`

### **6. File Upload Returns 500**

**Problem:** Presigned URL generation fails

**Solutions:**
- Verify Spaces credentials are correct
- Check bucket exists
- Verify endpoint URL is correct
- For MinIO: ensure it's running and accessible

### **7. Docker Build Fails**

**Problem:** `Failed to build sdigdata` or hatchling errors

**Solutions:**
- Ensure `pyproject.toml` includes:
  ```toml
  [tool.hatch.build.targets.wheel]
  packages = ["app"]
  ```
- Build copies all files first (needs full project structure)
- No lock file needed in Docker (uses `uv sync --no-dev`)
- Check Docker logs: `docker build -t sdigdata . 2>&1 | tail -50`

---

## 🔗 Integration Notes

### **For Frontend Developers**

**Base URL (Development):** `http://localhost:8000`

**Required Headers:**
```javascript
headers: {
  'Content-Type': 'application/json',
  'Authorization': `Bearer ${token}`
}
```

**API Documentation:** `http://localhost:8000/docs` (Swagger UI)

**Key Endpoints:**
- Login: `POST /auth/login`
- List forms: `GET /forms`
- Submit response: `POST /responses`
- File upload: `POST /files/presign`

### **For Mobile Developers**

**Authentication:**
- Store JWT token securely (KeyChain/KeyStore)
- Refresh on 401 errors
- Include in all requests

**File Uploads:**
1. Request presigned URL from API
2. Upload file directly to S3 (PUT request)
3. Submit response with file URL

**Offline Support:**
- Queue responses locally
- Sync when online
- Handle 409 conflicts

### **For DevOps**

**Monitoring Endpoints:**
- Health: `GET /health` → `{"status": "healthy"}`
- Root: `GET /` → Version info

**Logs:**
- Application: stdout/stderr
- Access logs: via uvicorn
- Database: PostgreSQL logs

**Backups:**
- Database: `pg_dump` daily
- Files: S3 versioning enabled
- Retention: 30 days minimum

**Scaling:**
- Stateless API (can run multiple instances)
- Database connection pooling included
- Consider Redis for caching (future)

---

## 📊 Database Schema Summary

```
organizations
  ├─ users (FK: organization_id)
  └─ forms (FK: organization_id, created_by)
      ├─ form_assignments (FK: form_id, agent_id)
      └─ responses (FK: form_id, submitted_by)
```

**All tables use UUID primary keys**

---

## 🆘 Troubleshooting Checklist

Before asking for help, verify:

1. [ ] Environment variables are set correctly
2. [ ] Database is accessible and migrations have run
3. [ ] Default admin user has been created
4. [ ] CORS origins include your frontend URL
5. [ ] JWT token is valid and not expired
6. [ ] Spaces/MinIO credentials are correct
7. [ ] Logs have been checked: `docker-compose logs -f`
8. [ ] Health endpoint returns 200: `curl http://localhost:8000/health`

---

## 📚 Additional Resources

- **Full Documentation:** [README.md](README.md)
- **Quick Start:** [QUICKSTART.md](QUICKSTART.md)
- **Architecture:** [PROJECT_SUMMARY.md](PROJECT_SUMMARY.md)
- **API Notes:** [API_NOTES.md](API_NOTES.md)
- **API Docs:** http://localhost:8000/docs (when running)

---

## 🔄 Version Information

- **Project Version:** 1.0.0
- **Python:** 3.12+
- **PostgreSQL:** 16+
- **FastAPI:** 0.115+
- **Pydantic:** 2.9+

---

## 📞 Support

**For Issues:**
1. Check this file first
2. Review logs: `docker-compose logs -f api`
3. Test health endpoint: `curl http://localhost:8000/health`
4. Check database connectivity
5. Review [README.md](README.md) for detailed setup

**Common Commands:**
```bash
# View logs
docker-compose logs -f api

# Restart API
docker-compose restart api

# Connect to database
docker-compose exec db psql -U metroform -d metroform

# Run migrations
uv run yoyo apply --database $DATABASE_URL migrations

# Test API
curl http://localhost:8000/health
```

---

**Last Updated:** 2025-11-03
**Maintained By:** SDIGdata Development Team
