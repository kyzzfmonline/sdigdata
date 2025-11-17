"""fix_critical_schema_issues

Revision ID: dc375e053374
Revises: 3a22df3f24b5
Create Date: 2025-11-17 17:22:46.550051

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'dc375e053374'
down_revision: Union[str, Sequence[str], None] = '3a22df3f24b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Fix critical schema issues:
    1. Update form status constraint to include all valid states
    2. Add missing columns to forms, responses, and users tables
    3. Add indexes for performance
    """
    # Fix form status constraint
    op.execute("""
        ALTER TABLE forms DROP CONSTRAINT IF EXISTS forms_status_check;
        ALTER TABLE forms ADD CONSTRAINT forms_status_check
            CHECK (status IN ('draft', 'active', 'archived', 'decommissioned'));
    """)

    # Add missing columns to forms table
    op.execute("""
        ALTER TABLE forms
            ADD COLUMN IF NOT EXISTS description TEXT,
            ADD COLUMN IF NOT EXISTS published_at TIMESTAMP WITH TIME ZONE,
            ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP WITH TIME ZONE,
            ADD COLUMN IF NOT EXISTS decommissioned_at TIMESTAMP WITH TIME ZONE,
            ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE,
            ADD COLUMN IF NOT EXISTS deleted BOOLEAN DEFAULT FALSE;
    """)

    # Add missing columns to responses table
    op.execute("""
        ALTER TABLE responses
            ADD COLUMN IF NOT EXISTS organization_id UUID REFERENCES organizations(id),
            ADD COLUMN IF NOT EXISTS submission_type VARCHAR(50) DEFAULT 'authenticated',
            ADD COLUMN IF NOT EXISTS submitter_ip INET,
            ADD COLUMN IF NOT EXISTS user_agent TEXT,
            ADD COLUMN IF NOT EXISTS anonymous_metadata JSONB,
            ADD COLUMN IF NOT EXISTS deleted BOOLEAN DEFAULT FALSE;
    """)

    # Add missing columns to users table
    op.execute("""
        ALTER TABLE users
            ADD COLUMN IF NOT EXISTS email VARCHAR(255),
            ADD COLUMN IF NOT EXISTS status VARCHAR(50) DEFAULT 'active',
            ADD COLUMN IF NOT EXISTS last_login TIMESTAMP WITH TIME ZONE,
            ADD COLUMN IF NOT EXISTS deleted BOOLEAN DEFAULT FALSE;
    """)

    # Add unique constraint on email if it doesn't exist
    op.execute("""
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'users_email_key'
            ) THEN
                ALTER TABLE users ADD CONSTRAINT users_email_key UNIQUE (email);
            END IF;
        END $$;
    """)

    # Update existing forms to have 'active' status instead of 'published'
    op.execute("""
        UPDATE forms SET status = 'active' WHERE status = 'published';
    """)

    # Backfill organization_id in responses from forms
    op.execute("""
        UPDATE responses r
        SET organization_id = f.organization_id
        FROM forms f
        WHERE r.form_id = f.id AND r.organization_id IS NULL;
    """)

    # Add indexes for better performance
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_forms_status_deleted ON forms(status) WHERE deleted = FALSE;
        CREATE INDEX IF NOT EXISTS idx_forms_organization_status ON forms(organization_id, status) WHERE deleted = FALSE;
        CREATE INDEX IF NOT EXISTS idx_responses_form_deleted ON responses(form_id) WHERE deleted = FALSE;
        CREATE INDEX IF NOT EXISTS idx_responses_organization ON responses(organization_id) WHERE deleted = FALSE;
        CREATE INDEX IF NOT EXISTS idx_responses_submission_type ON responses(submission_type);
        CREATE INDEX IF NOT EXISTS idx_users_email ON users(email) WHERE email IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_users_status ON users(status) WHERE deleted = FALSE;
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Remove indexes
    op.execute("""
        DROP INDEX IF EXISTS idx_forms_status_deleted;
        DROP INDEX IF EXISTS idx_forms_organization_status;
        DROP INDEX IF EXISTS idx_responses_form_deleted;
        DROP INDEX IF EXISTS idx_responses_organization;
        DROP INDEX IF EXISTS idx_responses_submission_type;
        DROP INDEX IF EXISTS idx_users_email;
        DROP INDEX IF EXISTS idx_users_status;
    """)

    # Revert status values
    op.execute("""
        UPDATE forms SET status = 'published' WHERE status = 'active';
    """)

    # Restore old constraint
    op.execute("""
        ALTER TABLE forms DROP CONSTRAINT IF EXISTS forms_status_check;
        ALTER TABLE forms ADD CONSTRAINT forms_status_check
            CHECK (status IN ('draft', 'published'));
    """)

    # Note: We don't drop columns in downgrade to prevent data loss
    # If needed, manually drop columns: description, published_at, archived_at,
    # decommissioned_at, updated_at, deleted, organization_id, submission_type,
    # submitter_ip, user_agent, anonymous_metadata, email, status, last_login
