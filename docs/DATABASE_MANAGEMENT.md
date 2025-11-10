# Database Management Guide

This guide explains how to manage database connections and migrations across different environments (development, production, and local).

## Overview

The project uses environment-specific configuration files to manage different database connections:

- `.env.dev` - Development environment (Docker-based)
- `.env.prod` - Production environment (DigitalOcean)
- `.env.local` - Local development (running directly on host)
- `.env` - Active configuration (copied from one of the above)

## Quick Start

### Switch to Development Environment

```bash
./scripts/use-dev.sh
```

This configures the app to use:
- Local Docker PostgreSQL database
- Local MinIO for file storage
- Development settings

### Switch to Production Environment

```bash
./scripts/use-prod.sh
```

⚠️ **Warning**: This connects to the live production database. Use with caution!

This configures the app to use:
- Production PostgreSQL database (DigitalOcean)
- Production DigitalOcean Spaces
- Production settings

### Switch to Local Environment

```bash
./scripts/use-local.sh
```

This configures the app to use:
- PostgreSQL running on localhost
- MinIO running on localhost
- For running the app outside Docker

## Environment Management Scripts

### Show Current Environment

```bash
./scripts/show-env.sh
```

Displays current environment configuration with sensitive values redacted.

### Check Migration Status

```bash
./scripts/db-status.sh
```

Shows the current migration version and history for the active database.

### Run Migrations

```bash
./scripts/db-migrate.sh
```

Applies pending migrations to the active database.

## Manual Migration Management

### Using Alembic Directly

You can also use Alembic commands directly with the `DATABASE_URL` environment variable:

```bash
# Check current migration status
alembic current

# Show migration history
alembic history

# Upgrade to latest version
alembic upgrade head

# Downgrade one version
alembic downgrade -1

# Create a new migration
alembic revision -m "description of changes"
```

### Connect to Production Database

To run migrations on production:

```bash
# Switch to production environment
./scripts/use-prod.sh

# Check status
./scripts/db-status.sh

# Apply migrations
./scripts/db-migrate.sh
```

Or use the DATABASE_URL directly:

```bash
DATABASE_URL="postgresql://user:pass@host:port/database" alembic upgrade head
```

## Environment File Structure

### .env.dev (Development - Docker)

```bash
DATABASE_URL=postgresql://metroform:password@db:5432/sdigdata
SPACES_ENDPOINT=http://minio:9000
ENVIRONMENT=development
```

### .env.prod (Production - DigitalOcean)

```bash
DATABASE_URL=postgresql://sdig_access:password@138.68.143.213:3690/sdig_data
SPACES_ENDPOINT=https://nyc3.digitaloceanspaces.com
ENVIRONMENT=production
```

### .env.local (Local Development - Host)

```bash
DATABASE_URL=postgresql://metroform:password@localhost:5432/metroform
SPACES_ENDPOINT=http://localhost:9000
ENVIRONMENT=development
```

## Best Practices

### Development Workflow

1. **Default to Development**: Always use `.env.dev` for regular development
2. **Test Locally First**: Use `.env.local` when debugging without Docker
3. **Production Access**: Only use `.env.prod` when absolutely necessary

### Migration Workflow

1. **Create Migration**: Develop schema changes locally
   ```bash
   ./scripts/use-dev.sh
   alembic revision -m "add new column"
   # Edit the generated migration file
   ```

2. **Test Migration**: Test on local development database
   ```bash
   ./scripts/db-migrate.sh
   # Test the application
   ```

3. **Apply to Production**: Only after thorough testing
   ```bash
   ./scripts/use-prod.sh
   ./scripts/db-migrate.sh
   ```

### Security Considerations

1. **Never commit `.env`**: The active `.env` file is in `.gitignore`
2. **Template files only**: `.env.dev`, `.env.prod`, `.env.example` are templates
3. **Update `.env.prod`**: Replace placeholder values with actual production credentials
4. **Rotate secrets**: Change `SECRET_KEY` and other sensitive values in production

## Troubleshooting

### "DATABASE_URL is not set" Error

Run one of the environment scripts:
```bash
./scripts/use-dev.sh
```

### Connection Refused

**For Docker (use-dev.sh)**:
- Ensure Docker containers are running: `docker-compose up -d`
- Database host should be `db` (container name)

**For Local (use-local.sh)**:
- Ensure PostgreSQL is running on host: `systemctl status postgresql`
- Database host should be `localhost`

### Migration Conflicts

If you get migration conflicts:

```bash
# Check current state
./scripts/db-status.sh

# View migration history
alembic history

# If needed, downgrade and re-apply
alembic downgrade <revision>
alembic upgrade head
```

### Testing Database Connection

Use Python to test the connection:

```python
import psycopg2
import os

# Load .env
from dotenv import load_dotenv
load_dotenv()

conn = psycopg2.connect(os.getenv("DATABASE_URL"))
print("✅ Connected successfully!")
conn.close()
```

## Architecture Notes

### Why Environment Files?

1. **Developer Experience**: Easy switching between environments
2. **Safety**: Clear separation prevents accidental production changes
3. **Team Collaboration**: Shared configuration templates
4. **CI/CD Ready**: Environment variables can override file-based config

### Alembic Integration

The `alembic/env.py` file is configured to:
1. Check for `DATABASE_URL` environment variable
2. Fall back to `alembic.ini` if not set
3. Support both approaches for flexibility

### Application Integration

The `app/core/config.py` uses Pydantic settings:
- Automatically loads from `.env` file
- Environment variables override file values
- Type-safe configuration

## Additional Resources

- [Alembic Documentation](https://alembic.sqlalchemy.org/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)
- [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/)
