# Environment Setup - Quick Reference

## Overview

This project uses environment-based configuration for easy switching between development, production, and local environments.

## Quick Start

### 1. Choose Your Environment

```bash
# Development (Docker)
./scripts/use-dev.sh

# Production (DigitalOcean)
./scripts/use-prod.sh

# Local (Host machine)
./scripts/use-local.sh
```

### 2. Run Migrations (if needed)

```bash
./scripts/db-migrate.sh
```

### 3. Verify Database

```bash
./scripts/verify-db.sh
```

## All Available Scripts

| Script | Purpose |
|--------|---------|
| `./scripts/use-dev.sh` | Switch to development environment (Docker) |
| `./scripts/use-prod.sh` | Switch to production environment (⚠️ Live DB!) |
| `./scripts/use-local.sh` | Switch to local environment (host machine) |
| `./scripts/show-env.sh` | Display current environment configuration |
| `./scripts/db-migrate.sh` | Run database migrations on active environment |
| `./scripts/db-status.sh` | Check migration status of active database |
| `./scripts/verify-db.sh` | Verify database schema has all required columns |

## Environment Files

| File | Purpose | Tracked in Git? |
|------|---------|-----------------|
| `.env` | Active configuration (copied from templates) | ❌ No |
| `.env.dev` | Development template | ✅ Yes |
| `.env.prod` | Production template | ✅ Yes |
| `.env.local` | Local development template | ✅ Yes |
| `.env.example` | Example/reference | ✅ Yes |

## Common Workflows

### Local Development

```bash
# 1. Switch to dev environment
./scripts/use-dev.sh

# 2. Start Docker services
docker-compose up -d

# 3. Run migrations
./scripts/db-migrate.sh

# 4. Verify setup
./scripts/verify-db.sh
```

### Production Deployment

```bash
# 1. Switch to production
./scripts/use-prod.sh

# 2. Verify current state
./scripts/db-status.sh

# 3. Apply migrations
./scripts/db-migrate.sh

# 4. Verify schema
./scripts/verify-db.sh

# 5. Switch back to dev
./scripts/use-dev.sh
```

### Running Outside Docker

```bash
# 1. Switch to local environment
./scripts/use-local.sh

# 2. Ensure PostgreSQL is running
# (depends on your OS)

# 3. Run the app
uvicorn app.main:app --reload
```

## Database Connection Strings

### Development (Docker)
```
postgresql://metroform:password@db:5432/sdigdata
```

### Production (DigitalOcean)
```
postgresql://sdig_access:ac6cdf37b0ce4ab3@138.68.143.213:3690/sdig_data
```

### Local (Host)
```
postgresql://metroform:password@localhost:5432/metroform
```

## Troubleshooting

### "DATABASE_URL is not set"
Run an environment script: `./scripts/use-dev.sh`

### Connection Refused
- **Docker**: Ensure containers are running: `docker-compose ps`
- **Local**: Ensure PostgreSQL is running: `pg_isready`

### Migration Conflicts
```bash
./scripts/db-status.sh  # Check current state
alembic history         # View history
alembic downgrade -1    # Downgrade if needed
./scripts/db-migrate.sh # Re-apply
```

## Security Notes

- ⚠️ Never commit `.env` file
- ⚠️ Template files (`.env.dev`, `.env.prod`) should not contain real production secrets
- ⚠️ Always update `.env.prod` with real credentials before using in production
- ⚠️ Use `./scripts/use-prod.sh` with caution - it connects to live data

## For More Details

See [docs/DATABASE_MANAGEMENT.md](docs/DATABASE_MANAGEMENT.md) for comprehensive documentation.
