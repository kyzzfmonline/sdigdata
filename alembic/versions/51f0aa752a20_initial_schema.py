"""initial_schema

Revision ID: 51f0aa752a20
Revises: 
Create Date: 2025-11-05 20:11:01.399465

"""
from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '51f0aa752a20'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Read and execute the SQL from migrations/20251105_01_S7zXT-initial-schema.sql
    op.execute("""
-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Organizations table
CREATE TABLE IF NOT EXISTS organizations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    logo_url TEXT,
    primary_color VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role VARCHAR(50) NOT NULL CHECK (role IN ('admin', 'agent')),
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index for faster username lookups
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_organization ON users(organization_id);

-- Forms table
CREATE TABLE IF NOT EXISTS forms (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(500) NOT NULL,
    organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
    schema JSONB NOT NULL,
    status VARCHAR(50) NOT NULL CHECK (status IN ('draft', 'published')) DEFAULT 'draft',
    version INTEGER NOT NULL DEFAULT 1,
    created_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for forms
CREATE INDEX IF NOT EXISTS idx_forms_organization ON forms(organization_id);
CREATE INDEX IF NOT EXISTS idx_forms_status ON forms(status);
CREATE INDEX IF NOT EXISTS idx_forms_created_by ON forms(created_by);

-- Form assignments table (many-to-many: forms <-> agents)
CREATE TABLE IF NOT EXISTS form_assignments (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    form_id UUID NOT NULL REFERENCES forms(id) ON DELETE CASCADE,
    agent_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(form_id, agent_id)
);

-- Indexes for form assignments
CREATE INDEX IF NOT EXISTS idx_form_assignments_form ON form_assignments(form_id);
CREATE INDEX IF NOT EXISTS idx_form_assignments_agent ON form_assignments(agent_id);

-- Responses table
CREATE TABLE IF NOT EXISTS responses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    form_id UUID NOT NULL REFERENCES forms(id) ON DELETE CASCADE,
    submitted_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    data JSONB NOT NULL,
    attachments JSONB,
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for responses
CREATE INDEX IF NOT EXISTS idx_responses_form ON responses(form_id);
CREATE INDEX IF NOT EXISTS idx_responses_submitted_by ON responses(submitted_by);
CREATE INDEX IF NOT EXISTS idx_responses_submitted_at ON responses(submitted_at);

-- Comments explaining the schema
COMMENT ON TABLE organizations IS 'Metropolitan assemblies and organizations';
COMMENT ON TABLE users IS 'System users (admins and agents)';
COMMENT ON TABLE forms IS 'Data collection forms with JSON schema including branding';
COMMENT ON TABLE form_assignments IS 'Assignment of forms to agents';
COMMENT ON TABLE responses IS 'Form responses submitted by agents';
COMMENT ON COLUMN forms.schema IS 'JSON schema containing fields and branding (logo, colors, header/footer)';
COMMENT ON COLUMN responses.data IS 'Collected form data (text, GPS, etc.)';
COMMENT ON COLUMN responses.attachments IS 'Uploaded file URLs (photos, signatures, etc.)';
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("""
    DROP TABLE IF EXISTS responses CASCADE;
    DROP TABLE IF NOT EXISTS form_assignments CASCADE;
    DROP TABLE IF EXISTS forms CASCADE;
    DROP TABLE IF EXISTS users CASCADE;
    DROP TABLE IF EXISTS organizations CASCADE;
    DROP EXTENSION IF EXISTS "uuid-ossp";
    """)
