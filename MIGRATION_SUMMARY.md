# Database Migration Summary - 2025-11-10

## Issue
The production database was missing several columns that were referenced in the application code, causing runtime errors like:
- `asyncpg.exceptions.UndefinedColumnError: column "last_login" of relation "users" does not exist`
- `asyncpg.exceptions.UndefinedColumnError: column "deleted" does not exist`

## Solution
Created comprehensive database migrations to add all missing columns referenced in the codebase.

## Migrations Applied

### 1. Migration `b843f7a58fb4` - Add Soft Delete Columns
**Date**: 2025-11-10 11:20

Added soft delete and status tracking columns:
- **users**: `deleted`, `deleted_at`, `status`
- **forms**: `deleted`, `deleted_at`
- **responses**: `deleted`, `deleted_at`, `status`, `submission_type`
- **form_assignments**: `status`
- **audit_logs** table (new)
- **quality_scores** table (new)

### 2. Performance Indexes Migration
**Date**: 2025-11-10 11:25

Applied 32 performance indexes from `migrations/add_performance_indexes.sql`:
- Response filtering indexes (form_id, submitted_by, submitted_at, submission_type, deleted)
- Form filtering indexes (organization_id, status, created_by, deleted)
- User indexes (role, organization_id, status, deleted)
- Composite indexes for common query patterns

### 3. Migration `239b7d1516aa` - Add Missing Columns
**Date**: 2025-11-10 11:28

Added user profile and tracking columns:
- **users**: `email`, `last_login`, `updated_at`, `email_notifications`, `theme`, `compact_mode`
- **forms**: `updated_at`, `published_at`
- **form_assignments**: `assigned_by`, `due_date`, `target_responses`

### 4. Migration `68df989a6c19` - Add Notification Preference Columns
**Date**: 2025-11-10 11:29

Added user notification preference columns:
- **users**: `form_assignments`, `responses`, `system_updates`

These columns control whether users receive notifications for different event types.

## Final Schema Coverage

### ✅ Complete Column Coverage: 62/62 (100%)

#### Users Table (18 columns)
- Core: id, username, password_hash, role, organization_id, created_at
- Soft delete: deleted, deleted_at
- Profile: email, status, last_login, updated_at
- Preferences: email_notifications, theme, compact_mode
- Notifications: form_assignments, responses, system_updates

#### Forms Table (13 columns)
- Core: id, title, organization_id, schema, status, version, created_by, created_at, description
- Soft delete: deleted, deleted_at
- Tracking: updated_at, published_at

#### Responses Table (10 columns)
- Core: id, form_id, submitted_by, data, attachments, submitted_at
- Soft delete: deleted, deleted_at
- Status: status, submission_type

#### Form Assignments Table (8 columns)
- Core: id, form_id, agent_id, assigned_at, status
- Extended: assigned_by, due_date, target_responses

#### Organizations Table (5 columns)
- id, name, logo_url, primary_color, created_at

#### Notifications Table (8 columns)
- id, user_id, type, title, message, data, read, created_at

## Verification

All migrations have been verified using the comprehensive verification script:

```bash
./scripts/use-prod.sh
./scripts/verify-db.sh
```

**Result**: ✅ All 62 required columns present in production database

## Database Management Improvements

Created a complete environment management system:

### Environment Files
- `.env.dev` - Development (Docker)
- `.env.prod` - Production (DigitalOcean)
- `.env.local` - Local development
- `.env.example` - Template with documentation

### Helper Scripts
- `use-dev.sh` / `use-prod.sh` / `use-local.sh` - Environment switching
- `db-migrate.sh` - Run migrations on active environment
- `db-status.sh` - Check migration status
- `verify-db.sh` - Verify schema completeness
- `show-env.sh` - Display current configuration

### Documentation
- `ENVIRONMENT_SETUP.md` - Quick reference guide
- `docs/DATABASE_MANAGEMENT.md` - Comprehensive guide

## Testing

To ensure all columns are present:

1. **Switch to production**:
   ```bash
   ./scripts/use-prod.sh
   ```

2. **Verify schema**:
   ```bash
   ./scripts/verify-db.sh
   ```

3. **Check migration status**:
   ```bash
   ./scripts/db-status.sh
   ```

## Impact

✅ **No more column-related errors**: All columns referenced in the code now exist in the database

✅ **Improved DX**: Easy environment switching and migration management

✅ **Performance**: 32 indexes optimize query performance

✅ **Future-proof**: Comprehensive verification script catches missing columns

## Maintenance

### Adding New Columns

1. Update the code to reference the new column
2. Create a migration:
   ```bash
   alembic revision -m "add_new_column"
   ```
3. Edit the migration file to add the column
4. Apply to production:
   ```bash
   ./scripts/use-prod.sh
   ./scripts/db-migrate.sh
   ./scripts/verify-db.sh
   ```
5. Update `scripts/verify-db.sh` to include the new column in verification

### Troubleshooting

If you encounter column errors:

1. Check which columns are referenced:
   ```bash
   grep -r "column_name" app/ --include="*.py"
   ```

2. Compare with database schema:
   ```bash
   ./scripts/verify-db.sh
   ```

3. Create and apply migration if needed

## Related Files

- `alembic/versions/b843f7a58fb4_add_soft_delete_columns.py`
- `alembic/versions/239b7d1516aa_add_missing_columns.py`
- `alembic/versions/68df989a6c19_add_notification_preference_columns.py`
- `migrations/add_performance_indexes.sql`
- `scripts/verify-db.sh`
- `scripts/db-migrate.sh`

## Notes

- All migrations use `IF NOT EXISTS` clauses for idempotency
- Foreign keys are properly set with `ON DELETE` clauses
- Indexes are created for commonly queried columns
- Comments document the purpose of each column
- Migration revision: `68df989a6c19` (latest)
