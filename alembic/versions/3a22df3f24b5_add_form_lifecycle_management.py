"""add_form_lifecycle_management

Revision ID: 3a22df3f24b5
Revises: 3a7bdda9c3ea
Create Date: 2025-11-15 13:46:12.506136

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3a22df3f24b5'
down_revision: Union[str, Sequence[str], None] = '3a7bdda9c3ea'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add new columns for form lifecycle management
    op.execute("""
        -- Add lifecycle tracking columns
        ALTER TABLE forms ADD COLUMN IF NOT EXISTS archived_at TIMESTAMP WITH TIME ZONE;
        ALTER TABLE forms ADD COLUMN IF NOT EXISTS decommissioned_at TIMESTAMP WITH TIME ZONE;
        ALTER TABLE forms ADD COLUMN IF NOT EXISTS decommissioned_by UUID REFERENCES users(id) ON DELETE SET NULL;
        ALTER TABLE forms ADD COLUMN IF NOT EXISTS decommission_reason TEXT;
        ALTER TABLE forms ADD COLUMN IF NOT EXISTS is_public BOOLEAN DEFAULT TRUE;

        -- Add comments
        COMMENT ON COLUMN forms.archived_at IS 'When the form was archived (stopped accepting responses)';
        COMMENT ON COLUMN forms.decommissioned_at IS 'When the form was permanently decommissioned';
        COMMENT ON COLUMN forms.decommissioned_by IS 'Admin user who decommissioned the form';
        COMMENT ON COLUMN forms.decommission_reason IS 'Reason for decommissioning';
        COMMENT ON COLUMN forms.is_public IS 'Whether form is accessible to public (unauthenticated users)';

        -- Update existing 'published' status to 'active'
        UPDATE forms SET status = 'active' WHERE status = 'published';

        -- Drop old status constraint if exists
        ALTER TABLE forms DROP CONSTRAINT IF EXISTS forms_status_check;

        -- Add new status constraint with all valid statuses
        ALTER TABLE forms ADD CONSTRAINT forms_status_check
            CHECK (status IN ('draft', 'active', 'archived', 'decommissioned'));

        -- Create indexes for performance
        CREATE INDEX IF NOT EXISTS idx_forms_status_public ON forms(status, is_public) WHERE deleted = FALSE;
        CREATE INDEX IF NOT EXISTS idx_forms_archived_at ON forms(archived_at) WHERE archived_at IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_forms_decommissioned_at ON forms(decommissioned_at) WHERE decommissioned_at IS NOT NULL;
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("""
        -- Drop indexes
        DROP INDEX IF EXISTS idx_forms_decommissioned_at;
        DROP INDEX IF EXISTS idx_forms_archived_at;
        DROP INDEX IF EXISTS idx_forms_status_public;

        -- Revert 'active' status back to 'published'
        UPDATE forms SET status = 'published' WHERE status = 'active';

        -- Drop new status constraint
        ALTER TABLE forms DROP CONSTRAINT IF EXISTS forms_status_check;

        -- Re-add old status constraint
        ALTER TABLE forms ADD CONSTRAINT forms_status_check
            CHECK (status IN ('draft', 'published'));

        -- Drop new columns
        ALTER TABLE forms DROP COLUMN IF EXISTS decommission_reason;
        ALTER TABLE forms DROP COLUMN IF EXISTS decommissioned_by;
        ALTER TABLE forms DROP COLUMN IF EXISTS decommissioned_at;
        ALTER TABLE forms DROP COLUMN IF EXISTS archived_at;
        ALTER TABLE forms DROP COLUMN IF EXISTS is_public;
    """)
