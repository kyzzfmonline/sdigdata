"""add_missing_columns

Revision ID: 239b7d1516aa
Revises: b843f7a58fb4
Create Date: 2025-11-10 11:28:39.972325

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '239b7d1516aa'
down_revision: str | Sequence[str] | None = 'b843f7a58fb4'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add missing columns referenced in code."""
    op.execute("""
    -- Add missing columns to users table
    ALTER TABLE users
    ADD COLUMN IF NOT EXISTS email VARCHAR(255) UNIQUE,
    ADD COLUMN IF NOT EXISTS last_login TIMESTAMP WITH TIME ZONE,
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ADD COLUMN IF NOT EXISTS email_notifications BOOLEAN DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS theme VARCHAR(50) DEFAULT 'light',
    ADD COLUMN IF NOT EXISTS compact_mode BOOLEAN DEFAULT FALSE;

    -- Create index on email
    CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

    -- Add missing columns to forms table
    ALTER TABLE forms
    ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    ADD COLUMN IF NOT EXISTS published_at TIMESTAMP WITH TIME ZONE;

    -- Add missing columns to form_assignments table
    ALTER TABLE form_assignments
    ADD COLUMN IF NOT EXISTS assigned_by UUID REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS due_date TIMESTAMP WITH TIME ZONE,
    ADD COLUMN IF NOT EXISTS target_responses INTEGER;

    -- Add indexes for new columns
    CREATE INDEX IF NOT EXISTS idx_form_assignments_assigned_by ON form_assignments(assigned_by);
    CREATE INDEX IF NOT EXISTS idx_form_assignments_due_date ON form_assignments(due_date);

    -- Add comments
    COMMENT ON COLUMN users.email IS 'User email address for notifications';
    COMMENT ON COLUMN users.last_login IS 'Timestamp of last successful login';
    COMMENT ON COLUMN users.updated_at IS 'Timestamp of last profile update';
    COMMENT ON COLUMN users.email_notifications IS 'Whether to send email notifications';
    COMMENT ON COLUMN users.theme IS 'User interface theme preference (light/dark)';
    COMMENT ON COLUMN users.compact_mode IS 'Whether to use compact UI mode';
    COMMENT ON COLUMN forms.updated_at IS 'Timestamp of last form update';
    COMMENT ON COLUMN forms.published_at IS 'Timestamp when form was published';
    COMMENT ON COLUMN form_assignments.assigned_by IS 'User who created this assignment';
    COMMENT ON COLUMN form_assignments.due_date IS 'Deadline for completing responses';
    COMMENT ON COLUMN form_assignments.target_responses IS 'Target number of responses to collect';
    """)


def downgrade() -> None:
    """Remove added columns."""
    op.execute("""
    DROP INDEX IF EXISTS idx_form_assignments_due_date;
    DROP INDEX IF EXISTS idx_form_assignments_assigned_by;
    DROP INDEX IF EXISTS idx_users_email;

    ALTER TABLE form_assignments
    DROP COLUMN IF EXISTS target_responses,
    DROP COLUMN IF EXISTS due_date,
    DROP COLUMN IF EXISTS assigned_by;

    ALTER TABLE forms
    DROP COLUMN IF EXISTS published_at,
    DROP COLUMN IF EXISTS updated_at;

    ALTER TABLE users
    DROP COLUMN IF EXISTS compact_mode,
    DROP COLUMN IF EXISTS theme,
    DROP COLUMN IF EXISTS email_notifications,
    DROP COLUMN IF EXISTS updated_at,
    DROP COLUMN IF EXISTS last_login,
    DROP COLUMN IF EXISTS email;
    """)
