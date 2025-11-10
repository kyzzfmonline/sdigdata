"""add_notification_preference_columns

Revision ID: 68df989a6c19
Revises: 239b7d1516aa
Create Date: 2025-11-10 11:29:51.360567

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '68df989a6c19'
down_revision: Union[str, Sequence[str], None] = '239b7d1516aa'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add notification preference columns to users table."""
    op.execute("""
    -- Add notification preference columns with exact names as referenced in code
    -- Note: 'form_assignments' and 'responses' as column names don't conflict with table names in this context
    DO $$
    BEGIN
        -- Add form_assignments notification preference if it doesn't exist
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='users' AND column_name='form_assignments'
        ) THEN
            ALTER TABLE users ADD COLUMN form_assignments BOOLEAN DEFAULT TRUE;
        END IF;

        -- Add responses notification preference if it doesn't exist
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='users' AND column_name='responses'
        ) THEN
            ALTER TABLE users ADD COLUMN responses BOOLEAN DEFAULT TRUE;
        END IF;

        -- Add system_updates notification preference if it doesn't exist
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name='users' AND column_name='system_updates'
        ) THEN
            ALTER TABLE users ADD COLUMN system_updates BOOLEAN DEFAULT TRUE;
        END IF;
    END $$;

    -- Add comments for clarity
    COMMENT ON COLUMN users.form_assignments IS 'Receive notifications for form assignments';
    COMMENT ON COLUMN users.responses IS 'Receive notifications for form responses';
    COMMENT ON COLUMN users.system_updates IS 'Receive notifications for system updates';
    """)


def downgrade() -> None:
    """Remove notification preference columns."""
    op.execute("""
    ALTER TABLE users
    DROP COLUMN IF EXISTS system_updates,
    DROP COLUMN IF EXISTS responses,
    DROP COLUMN IF EXISTS form_assignments;
    """)
