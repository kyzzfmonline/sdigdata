"""add_soft_delete_columns

Revision ID: b843f7a58fb4
Revises: 1b4e9bf7b275
Create Date: 2025-11-10 11:20:07.457819

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b843f7a58fb4'
down_revision: str | Sequence[str] | None = '1b4e9bf7b275'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add soft delete columns to tables."""
    op.execute("""
    -- Add deleted and deleted_at columns to users table
    ALTER TABLE users
    ADD COLUMN IF NOT EXISTS deleted BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE;

    -- Add deleted and deleted_at columns to forms table
    ALTER TABLE forms
    ADD COLUMN IF NOT EXISTS deleted BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE;

    -- Add deleted and deleted_at columns to responses table
    ALTER TABLE responses
    ADD COLUMN IF NOT EXISTS deleted BOOLEAN NOT NULL DEFAULT FALSE,
    ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE;

    -- Add status column to users table if it doesn't exist
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='users' AND column_name='status'
        ) THEN
            ALTER TABLE users ADD COLUMN status VARCHAR(50) NOT NULL DEFAULT 'active'
            CHECK (status IN ('active', 'inactive', 'suspended'));
        END IF;
    END $$;

    -- Add status and submission_type columns to responses table if they don't exist
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='responses' AND column_name='status'
        ) THEN
            ALTER TABLE responses ADD COLUMN status VARCHAR(50) NOT NULL DEFAULT 'complete'
            CHECK (status IN ('complete', 'incomplete', 'draft'));
        END IF;

        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='responses' AND column_name='submission_type'
        ) THEN
            ALTER TABLE responses ADD COLUMN submission_type VARCHAR(50) NOT NULL DEFAULT 'online';
        END IF;
    END $$;

    -- Add status column to form_assignments table if it doesn't exist
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='form_assignments' AND column_name='status'
        ) THEN
            ALTER TABLE form_assignments ADD COLUMN status VARCHAR(50) NOT NULL DEFAULT 'active'
            CHECK (status IN ('active', 'inactive'));
        END IF;
    END $$;

    -- Add audit_logs table if it doesn't exist (for analytics)
    CREATE TABLE IF NOT EXISTS audit_logs (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_id UUID REFERENCES users(id) ON DELETE SET NULL,
        action VARCHAR(100) NOT NULL,
        entity_type VARCHAR(100),
        entity_id UUID,
        details JSONB,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    -- Add quality_scores table if it doesn't exist (for analytics)
    CREATE TABLE IF NOT EXISTS quality_scores (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        response_id UUID NOT NULL REFERENCES responses(id) ON DELETE CASCADE,
        quality_score DECIMAL(3,2) CHECK (quality_score >= 0 AND quality_score <= 1),
        reviewed_by UUID REFERENCES users(id) ON DELETE SET NULL,
        reviewed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        comments TEXT
    );

    -- Create indexes for soft delete columns
    CREATE INDEX IF NOT EXISTS idx_users_deleted ON users(deleted);
    CREATE INDEX IF NOT EXISTS idx_forms_deleted ON forms(deleted);
    CREATE INDEX IF NOT EXISTS idx_responses_deleted ON responses(deleted);

    -- Create indexes for audit and quality tables
    CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id ON audit_logs(user_id);
    CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);
    CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at ON audit_logs(created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_quality_scores_response_id ON quality_scores(response_id);
    CREATE INDEX IF NOT EXISTS idx_quality_scores_quality_score ON quality_scores(quality_score);
    """)


def downgrade() -> None:
    """Remove soft delete columns from tables."""
    op.execute("""
    DROP INDEX IF EXISTS idx_quality_scores_quality_score;
    DROP INDEX IF EXISTS idx_quality_scores_response_id;
    DROP INDEX IF EXISTS idx_audit_logs_created_at;
    DROP INDEX IF EXISTS idx_audit_logs_action;
    DROP INDEX IF EXISTS idx_audit_logs_user_id;
    DROP INDEX IF EXISTS idx_responses_deleted;
    DROP INDEX IF EXISTS idx_forms_deleted;
    DROP INDEX IF EXISTS idx_users_deleted;

    DROP TABLE IF EXISTS quality_scores CASCADE;
    DROP TABLE IF EXISTS audit_logs CASCADE;

    ALTER TABLE form_assignments DROP COLUMN IF EXISTS status;
    ALTER TABLE responses DROP COLUMN IF EXISTS submission_type;
    ALTER TABLE responses DROP COLUMN IF EXISTS status;
    ALTER TABLE users DROP COLUMN IF EXISTS status;
    ALTER TABLE responses DROP COLUMN IF EXISTS deleted_at;
    ALTER TABLE responses DROP COLUMN IF EXISTS deleted;
    ALTER TABLE forms DROP COLUMN IF EXISTS deleted_at;
    ALTER TABLE forms DROP COLUMN IF EXISTS deleted;
    ALTER TABLE users DROP COLUMN IF EXISTS deleted_at;
    ALTER TABLE users DROP COLUMN IF EXISTS deleted;
    """)
