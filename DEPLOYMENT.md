# Deployment Guide for CapRover

This guide explains how to deploy the SDIGdata backend to CapRover.

## Prerequisites

- CapRover instance running
- CapRover CLI installed (`npm install -g caprover`)

## Database Setup

The application requires PostgreSQL 16 with the following extensions:
- PostGIS (for geospatial features)
- pg_trgm (for text matching)

### Recommended: Using Custom Dockerfile (Best for CapRover)

The repository includes a `Dockerfile.db` that creates a PostgreSQL 16 container with PostGIS pre-installed. This is the recommended approach for CapRover deployments.

**To deploy in CapRover:**

1. Create a new CapRover app for the database (e.g., "metroform-db")
2. In the app settings, go to the "Deployment" tab
3. Upload or paste the contents of `Dockerfile.db`:

```dockerfile
FROM postgres:16

# Install PostGIS and required extensions
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       postgresql-16-postgis-3 \
       postgresql-16-postgis-3-scripts \
    && rm -rf /var/lib/apt/lists/*
```

4. Set environment variables in CapRover:
   - `POSTGRES_DB=metroform`
   - `POSTGRES_USER=metroform`
   - `POSTGRES_PASSWORD=<strong-password>`

5. Deploy the app

6. Once running, connect and verify extensions:

```bash
# In CapRover terminal for the database app
psql -U metroform -d metroform -c "CREATE EXTENSION IF NOT EXISTS postgis; CREATE EXTENSION IF NOT EXISTS pg_trgm; SELECT extname, extversion FROM pg_extension;"
```

### Alternative: Using CapRover One-Click PostgreSQL

If you prefer using the one-click PostgreSQL app:

1. Deploy PostgreSQL 16 from CapRover One-Click Apps
2. Access the database container terminal in CapRover
3. Run:

```bash
apt-get update && apt-get install -y postgresql-16-postgis-3
```

4. Connect to the database and enable extensions:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
```

**Note:** You can also use the provided `init_db_extensions.sql` script to enable all required extensions at once.

### Option 3: Use Managed PostgreSQL with PostGIS

If you're using a managed PostgreSQL service (AWS RDS, DigitalOcean, etc.):
1. Ensure PostGIS is available (most managed services include it)
2. Enable the extension via your database management console or SQL:

```sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
```

## Application Deployment

### 1. Set Environment Variables in CapRover

In your CapRover app settings, add these environment variables:

```bash
# Database
DATABASE_URL=postgresql://metroform:password@srv-captain--db:5432/metroform
DATABASE_URL_YOYO=postgresql+psycopg://metroform:password@srv-captain--db:5432/metroform
DATABASE_URL_APP=postgresql://metroform:password@srv-captain--db:5432/metroform

# Security
SECRET_KEY=<generate-a-strong-secret-key>

# DigitalOcean Spaces (or S3-compatible storage)
SPACES_ENDPOINT=https://nyc3.digitaloceanspaces.com
SPACES_REGION=nyc3
SPACES_BUCKET=your-bucket-name
SPACES_KEY=your-spaces-key
SPACES_SECRET=your-spaces-secret

# Optional
CORS_ORIGINS=https://your-frontend-domain.com
ENVIRONMENT=production
```

### 2. Deploy the Application

```bash
# Login to CapRover
caprover login

# Deploy the app
caprover deploy
```

### 3. Run Database Migrations

After the first deployment, run migrations:

```bash
# Access your app container terminal in CapRover dashboard
# Or use captain-definition to run migrations on deploy

yoyo-migrate apply --batch --database "$DATABASE_URL_YOYO"
```

### 4. Post-Deployment Steps

1. Create your first admin user (see API documentation)
2. Configure your forms
3. Set up monitoring and backups

## Automatic Migration on Deploy

To run migrations automatically on each deployment, add this to your `captain-definition`:

```json
{
  "schemaVersion": 2,
  "dockerfileLines": [
    "FROM python:3.12-slim",
    "WORKDIR /app",
    "COPY . .",
    "RUN pip install uv && uv sync",
    "RUN yoyo-migrate apply --batch --database \"$DATABASE_URL_YOYO\"",
    "CMD [\"uv\", \"run\", \"uvicorn\", \"app.main:app\", \"--host\", \"0.0.0.0\", \"--port\", \"8000\"]"
  ]
}
```

## Storage Configuration

The application uses S3-compatible storage (DigitalOcean Spaces, AWS S3, MinIO, etc.) for file uploads.

### Using DigitalOcean Spaces:
1. Create a Space in your DigitalOcean account
2. Generate API keys (Spaces access key and secret)
3. Set the environment variables as shown above

### Using AWS S3:
```bash
SPACES_ENDPOINT=https://s3.amazonaws.com
SPACES_REGION=us-east-1
SPACES_BUCKET=your-bucket-name
SPACES_KEY=your-aws-access-key
SPACES_SECRET=your-aws-secret-key
```

## Monitoring

- Health check endpoint: `/health`
- API documentation: `/docs`
- Logs are available in CapRover dashboard

## Backup Strategy

### Database Backups
```bash
# Create backup
pg_dump -h your-db-host -U metroform metroform > backup.sql

# Restore backup
psql -h your-db-host -U metroform metroform < backup.sql
```

### Storage Backups
Configure backup policies in your DigitalOcean Spaces or S3 bucket settings.

## Troubleshooting

### PostGIS Extension Not Found
If you get an error about PostGIS not being available:
1. Verify PostGIS is installed in the PostgreSQL container
2. Check that the extension is enabled: `SELECT * FROM pg_extension WHERE extname = 'postgis';`
3. Ensure you're using PostgreSQL 16 or later

### Connection Issues
- Verify `DATABASE_URL` matches your database service name in CapRover
- For CapRover services, use `srv-captain--<service-name>` as the hostname
- Check that the database port is correct (default: 5432)

### Migration Failures
- Ensure PostGIS is installed before running migrations
- Check database permissions
- Review migration logs for specific errors

## Security Checklist

- [ ] Change default database password
- [ ] Generate strong `SECRET_KEY`
- [ ] Configure CORS_ORIGINS for production
- [ ] Enable HTTPS in CapRover
- [ ] Set up database backups
- [ ] Configure storage bucket permissions
- [ ] Set up monitoring and alerts
- [ ] Review and restrict API access
