"""add_missing_responses_columns

Revision ID: e7cb0933ef41
Revises: 2e9d8ffbcded
Create Date: 2025-11-10 12:32:52.156879

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e7cb0933ef41'
down_revision: Union[str, Sequence[str], None] = '2e9d8ffbcded'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add missing columns to responses table."""
    op.execute("""
    -- Add organization_id column to responses table
    -- This is derived from the form's organization
    ALTER TABLE responses
    ADD COLUMN IF NOT EXISTS organization_id UUID;

    -- Add public form submission tracking columns
    ALTER TABLE responses
    ADD COLUMN IF NOT EXISTS submitter_ip INET,
    ADD COLUMN IF NOT EXISTS user_agent TEXT,
    ADD COLUMN IF NOT EXISTS anonymous_metadata JSONB;

    -- Backfill organization_id from forms table for existing responses
    UPDATE responses r
    SET organization_id = f.organization_id
    FROM forms f
    WHERE r.form_id = f.id
    AND r.organization_id IS NULL;

    -- Add foreign key constraint
    ALTER TABLE responses
    ADD CONSTRAINT fk_responses_organization
    FOREIGN KEY (organization_id) REFERENCES organizations(id) ON DELETE CASCADE;

    -- Make organization_id NOT NULL after backfilling
    ALTER TABLE responses
    ALTER COLUMN organization_id SET NOT NULL;

    -- Create index for better query performance
    CREATE INDEX IF NOT EXISTS idx_responses_organization_id ON responses(organization_id);
    CREATE INDEX IF NOT EXISTS idx_responses_submitter_ip ON responses(submitter_ip);

    -- Add comments
    COMMENT ON COLUMN responses.organization_id IS 'Organization that owns this response (denormalized from form)';
    COMMENT ON COLUMN responses.submitter_ip IS 'IP address of the submitter (for public forms)';
    COMMENT ON COLUMN responses.user_agent IS 'Browser user agent of the submitter (for public forms)';
    COMMENT ON COLUMN responses.anonymous_metadata IS 'Additional metadata for anonymous submissions';
    """)


def downgrade() -> None:
    """Remove added columns from responses table."""
    op.execute("""
    DROP INDEX IF EXISTS idx_responses_submitter_ip;
    DROP INDEX IF EXISTS idx_responses_organization_id;

    ALTER TABLE responses
    DROP CONSTRAINT IF EXISTS fk_responses_organization;

    ALTER TABLE responses
    DROP COLUMN IF EXISTS anonymous_metadata,
    DROP COLUMN IF EXISTS user_agent,
    DROP COLUMN IF EXISTS submitter_ip,
    DROP COLUMN IF EXISTS organization_id;
    """)
