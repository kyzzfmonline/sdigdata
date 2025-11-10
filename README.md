# SDIGdata Backend

**SDIGdata Backend** - A production-grade FastAPI backend for data collection in Metropolitan Assemblies. Powers both web dashboards and mobile clients for field data collection with form management, branding, agent assignment, and file uploads.

> **🚨 IMPORTANT:** First time here? Read [IMPORTANT.md](IMPORTANT.md) for critical information about API changes, security, deployment, and common issues.
>
> **📚 Documentation:** See [DOCS_INDEX.md](DOCS_INDEX.md) for a complete guide to all documentation files.

## 🎯 Features

- ✅ **Form Management** - Create, publish, and version forms with custom branding
- ✅ **Organization Management** - Multi-tenant support with logos and colors
- ✅ **User Management** - Admin and agent roles with JWT authentication
- ✅ **Agent Assignment** - Assign specific forms to field agents
- ✅ **Response Collection** - Submit text, GPS coordinates, and media
- ✅ **Geospatial Support** - PostGIS integration for location tracking and spatial analysis
- ✅ **ML/AI Ready** - Data quality tracking, feature store, and dataset versioning
- ✅ **File Uploads** - DigitalOcean Spaces / MinIO integration with presigned URLs
- ✅ **CSV Export** - Export form responses for analysis
- ✅ **Raw SQL** - Direct PostgreSQL queries with psycopg (no ORM)
- ✅ **Migrations** - Alembic migrations for database versioning
- ✅ **Docker Ready** - Docker Compose for local dev, CapRover for production

## 🏗️ Tech Stack

| Component | Technology |
|-----------|------------|
| Framework | FastAPI 0.115+ |
| Database | PostgreSQL 16 + PostGIS |
| DB Driver | psycopg 3 |
| Migrations | Alembic |
| Auth | JWT (python-jose) + bcrypt |
| Storage | DigitalOcean Spaces / MinIO (S3-compatible) |
| Package Manager | uv |
| Deployment | Docker + CapRover |

## 📁 Project Structure

```
sdigdata/
├── app/
│   ├── main.py                 # FastAPI application
│   ├── core/
│   │   ├── config.py          # Settings & environment
│   │   ├── db.py              # Database connections
│   │   └── security.py        # JWT & password hashing
│   ├── api/
│   │   ├── deps.py            # Auth dependencies
│   │   └── routes/
│   │       ├── auth.py        # Login & registration
│   │       ├── organizations.py
│   │       ├── forms.py       # Form CRUD & assignments
│   │       ├── responses.py   # Response submission
│   │       └── files.py       # Presigned URLs
│   ├── services/              # Database operations (raw SQL)
│   │   ├── users.py
│   │   ├── organizations.py
│   │   ├── forms.py
│   │   └── responses.py
│   └── utils/
│       ├── spaces.py          # S3-compatible storage
│       └── csv_export.py      # CSV generation
├── alembic/
│   ├── versions/              # Migration files
│   ├── env.py                 # Migration environment
│   └── script.py.mako         # Migration template
├── docker-compose.yml         # Local dev environment
├── Dockerfile                 # Production image
├── pyproject.toml             # Dependencies (uv)
├── alembic.ini                # Migration config
└── .env.example               # Environment template
```

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.12+ (for local development)
- uv package manager

### 1. Clone and Setup

```bash
git clone <repository>
cd sdigdata

# Copy environment file
cp .env.example .env

# Edit .env with your settings (optional for dev)
# The defaults work with docker-compose
```

### 2. Start with Docker Compose

```bash
# Start all services (PostgreSQL, MinIO, API)
docker-compose up -d

# Check logs
docker-compose logs -f api

# API available at: http://localhost:8000
# MinIO console: http://localhost:9001 (user: minio, pass: miniopass)
# API docs: http://localhost:8000/docs
```

### 3. Create First Admin User

**Option A: Using the Bootstrap API Endpoint (Recommended)**

```bash
curl -X POST http://localhost:8000/auth/bootstrap-admin \
  -H "Content-Type: application/json" \
  -d '{
    "username": "admin",
    "password": "SecurePass123!"
  }'
```

This endpoint:
- Only works when NO admin users exist (security feature)
- Automatically creates a default organization if needed
- Validates password strength and username format
- Returns the created admin user details

**Option B: Using SQL (Manual Method)**

```bash
# Connect to database
docker-compose exec db psql -U metroform -d metroform

-- Create an organization
INSERT INTO organizations (name, logo_url, primary_color)
VALUES ('Kumasi Metropolitan Assembly', 'https://example.com/logo.png', '#0066CC')
RETURNING id;

-- Note the organization ID, then create admin user
-- Replace 'YOUR_ORG_ID' with the ID from above
INSERT INTO users (username, password_hash, role, organization_id)
VALUES (
    'admin',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5oo2lI1kd.JWi', -- password: admin123
    'admin',
    'YOUR_ORG_ID'
);
```

**Note:** The password hash above is for `admin123`. For production, generate a new hash:

```python
from passlib.context import CryptContext
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
print(pwd_context.hash("your_secure_password"))
```

### 4. Test the API

```bash
# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'

# You'll get a response with access_token
# Use this token in subsequent requests:
# Authorization: Bearer <token>
```

## 📖 API Documentation

Once running, visit:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **Postman Collection**: Import `postman_collection.json` - see [POSTMAN_GUIDE.md](POSTMAN_GUIDE.md)

### Core Endpoints

#### Authentication
- `POST /auth/bootstrap-admin` - Create first admin user (only works when no admins exist)
- `POST /auth/register` - Register new user (admin only)
- `POST /auth/login` - Login and get JWT token

#### Organizations
- `GET /organizations` - List all organizations
- `POST /organizations` - Create organization (admin only)
- `GET /organizations/{id}` - Get organization details
- `PATCH /organizations/{id}` - Update organization (admin only)

#### Forms
- `GET /forms` - List forms
- `POST /forms` - Create form
- `GET /forms/{id}` - Get form details
- `POST /forms/{id}/publish` - Publish form (admin only)
- `POST /forms/{id}/assign` - Assign form to agent (admin only)
- `GET /forms/{id}/export` - Export responses as CSV (admin only)
- `GET /forms/assigned` - Get forms assigned to current user

#### Responses
- `POST /responses` - Submit form response
- `GET /responses` - List responses
- `GET /responses/{id}` - Get response details

#### Files
- `POST /files/presign` - Get presigned URL for file upload

## 🗄️ Database Schema

### Core Entities

**Organizations** - Metropolitan assemblies
- id, name, logo_url, primary_color, created_at

**Users** - Admin and agent accounts
- id, username, password_hash, role (admin/agent), organization_id, created_at

**Forms** - Data collection forms
- id, title, organization_id, schema (JSONB), status (draft/published), version, created_by, created_at

**Form Assignments** - Agent assignments
- id, form_id, agent_id, assigned_at

**Responses** - Submitted data
- id, form_id, submitted_by, data (JSONB), attachments (JSONB), submitted_at

## 📝 Form Schema Example

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
      "label": "Current Location",
      "required": true
    },
    {
      "id": "household_size",
      "type": "number",
      "label": "Number of people in household",
      "required": true
    },
    {
      "id": "photo",
      "type": "file",
      "label": "Photo of property",
      "required": false,
      "accept": "image/*"
    }
  ]
}
```

## 📤 File Upload Flow

1. **Request presigned URL**:
   ```bash
   POST /files/presign
   {
     "filename": "house_photo.jpg",
     "content_type": "image/jpeg"
   }
   ```

2. **Response**:
   ```json
   {
     "upload_url": "https://...",
     "file_url": "https://..."
   }
   ```

3. **Upload file** (from client):
   ```bash
   curl -X PUT "<upload_url>" \
     -H "Content-Type: image/jpeg" \
     --data-binary @house_photo.jpg
   ```

4. **Submit response with file URL**:
   ```bash
   POST /responses
   {
     "form_id": "...",
     "data": { ... },
     "attachments": {
       "photo": "https://..." // Use file_url from step 2
     }
   }
   ```

## 🐳 Docker Deployment

### Local Development

```bash
docker-compose up -d
```

### Production (CapRover)

1. **Create app in CapRover**
2. **Set environment variables** in CapRover dashboard
3. **Deploy**:
   ```bash
   caprover deploy
   ```

Or use the Dockerfile directly:

```bash
docker build -t sdigdata-backend .
docker run -p 8000:8000 --env-file .env sdigdata-backend
```

## 🔧 Development

### Without Docker

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync

# Set up .env
cp .env.example .env

# Run migrations
uv run yoyo apply --database "postgresql://..." migrations

# Start dev server
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Run Migrations

```bash
# Apply migrations
uv run alembic upgrade head

# Create new migration
uv run alembic revision -m "Description"
```

### Run Tests

```bash
uv run pytest
```

## 🔐 Security Notes

- Change `SECRET_KEY` in production
- Use strong passwords for all accounts
- Enable HTTPS in production
- Restrict CORS origins to your domains
- Use DigitalOcean Spaces (not MinIO) in production
- Regularly rotate JWT secrets
- Implement rate limiting (consider using FastAPI rate limiters)

## 📊 CSV Export

Admins can export form responses:

```bash
GET /forms/{form_id}/export
```

Returns a CSV file with:
- Response ID
- Submitter username
- Submission timestamp
- All form fields (flattened from JSON)
- File URLs

## 🌍 Environment Variables

See `.env.example` for all configuration options:

- `DATABASE_URL` - PostgreSQL connection string
- `SECRET_KEY` - JWT signing key
- `SPACES_*` - Storage configuration
- `CORS_ORIGINS` - Allowed origins for CORS

## 📦 Dependencies

Core dependencies (see `pyproject.toml`):

- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `psycopg[binary]` - PostgreSQL driver
- `python-jose[cryptography]` - JWT tokens
- `passlib[bcrypt]` - Password hashing
- `boto3` - S3-compatible storage
- `alembic` - Database migrations
- `pydantic-settings` - Configuration management

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## 📄 License

[Your License Here]

## 🆘 Support

For issues and questions:
- Check the `/docs` endpoint for API documentation
- Review logs: `docker-compose logs -f api`
- Inspect database: `docker-compose exec db psql -U metroform`

## 🎉 Credits

Built for Metropolitan Assemblies data collection needs.
Powered by FastAPI, PostgreSQL, and modern Python tools.
