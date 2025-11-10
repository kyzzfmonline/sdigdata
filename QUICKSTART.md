# 🚀 SDIGdata Backend - Quick Start Guide

Get your SDIGdata backend running in **5 minutes**!

## Option 1: Docker (Recommended)

### Step 1: Start Everything
```bash
./setup_dev.sh
```

Or manually:
```bash
cp .env.example .env
docker-compose up -d
```

### Step 2: Create Admin User

```bash
# Connect to database
docker-compose exec db psql -U metroform -d metroform
```

Then run these SQL commands:

```sql
-- Create organization
INSERT INTO organizations (name, logo_url, primary_color)
VALUES ('Kumasi Metropolitan Assembly', 'https://example.com/logo.png', '#0066CC')
RETURNING id;

-- Copy the returned ID and replace YOUR_ORG_ID below
INSERT INTO users (username, password_hash, role, organization_id)
VALUES (
    'admin',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5oo2lI1kd.JWi',
    'admin',
    'YOUR_ORG_ID'  -- Replace with actual ID
);

-- Exit psql
\q
```

### Step 3: Test the API

```bash
# Login
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin123"}'
```

You'll get back:
```json
{
  "access_token": "eyJ...",
  "token_type": "bearer",
  "user": { ... }
}
```

### Step 4: Try the Interactive Docs

Visit: **http://localhost:8000/docs**

Click "Authorize" and enter: `Bearer YOUR_ACCESS_TOKEN`

Now you can test all endpoints interactively!

---

## Option 2: Local Development (Without Docker)

### Step 1: Install Dependencies

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install project dependencies
uv sync
```

### Step 2: Set Up Database

You need PostgreSQL running locally:

```bash
# Create database
createdb metroform

# Copy and configure .env
cp .env.example .env
# Edit DATABASE_URL to point to your local PostgreSQL
```

### Step 3: Run Migrations

```bash
uv run yoyo apply --database $DATABASE_URL migrations
```

### Step 4: Start Server

```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 🎯 Common Tasks

### View Logs
```bash
docker-compose logs -f api
```

### Stop Services
```bash
docker-compose down
```

### Reset Database
```bash
docker-compose down -v  # Remove volumes
docker-compose up -d
# Then recreate admin user
```

### Check MinIO Files
Visit: http://localhost:9001
- Username: `minio`
- Password: `miniopass`

---

## 📱 Example: Create a Form

1. Login and get your token
2. Create a form:

```bash
curl -X POST http://localhost:8000/forms \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Household Survey 2025",
    "organization_id": "YOUR_ORG_ID",
    "status": "draft",
    "schema": {
      "branding": {
        "logo_url": "https://example.com/logo.png",
        "primary_color": "#0066CC",
        "header_text": "KMA Survey",
        "footer_text": "Thank you!"
      },
      "fields": [
        {
          "id": "name",
          "type": "text",
          "label": "Full Name",
          "required": true
        },
        {
          "id": "age",
          "type": "number",
          "label": "Age",
          "required": true
        },
        {
          "id": "location",
          "type": "gps",
          "label": "Location",
          "required": true
        }
      ]
    }
  }'
```

3. Publish the form:
```bash
curl -X POST http://localhost:8000/forms/FORM_ID/publish \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## 🔧 Troubleshooting

### "Connection refused" error
- Make sure Docker is running
- Check services: `docker-compose ps`
- Restart: `docker-compose restart`

### "Database does not exist"
- The migration runs automatically on startup
- Check logs: `docker-compose logs db`

### MinIO bucket not found
- The bucket is created automatically on first startup
- Check API logs: `docker-compose logs api`

### Port already in use
Edit `docker-compose.yml` to change ports:
```yaml
ports:
  - "8001:8000"  # Change 8000 to 8001
```

---

## 📚 Next Steps

- Read the full [README.md](README.md)
- Explore [API Documentation](http://localhost:8000/docs)
- Check out the [Database Schema](README.md#database-schema)
- Learn about [File Uploads](README.md#file-upload-flow)

---

**Need Help?** Check the logs first:
```bash
docker-compose logs -f
```
