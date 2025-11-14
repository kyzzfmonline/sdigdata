"""add_form_builder_enhancements

Revision ID: e84dc12cb616
Revises: 9bdf65372be3
Create Date: 2025-11-14 02:48:45.476131

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e84dc12cb616'
down_revision: Union[str, Sequence[str], None] = '9bdf65372be3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("""
    -- =====================================================
    -- 1. CONDITIONAL LOGIC ENGINE
    -- =====================================================
    CREATE TABLE IF NOT EXISTS conditional_rules (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        form_id UUID NOT NULL REFERENCES forms(id) ON DELETE CASCADE,
        rule_name VARCHAR(255) NOT NULL,
        rule_type VARCHAR(50) NOT NULL CHECK (rule_type IN ('show_hide', 'calculate', 'validate', 'set_value')),
        conditions JSONB NOT NULL,
        actions JSONB NOT NULL,
        priority INTEGER DEFAULT 0,
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        created_by UUID REFERENCES users(id) ON DELETE SET NULL
    );

    CREATE INDEX IF NOT EXISTS idx_conditional_rules_form_id ON conditional_rules(form_id);
    CREATE INDEX IF NOT EXISTS idx_conditional_rules_type ON conditional_rules(rule_type);
    CREATE INDEX IF NOT EXISTS idx_conditional_rules_active ON conditional_rules(is_active);

    COMMENT ON TABLE conditional_rules IS 'Conditional logic rules for dynamic form behavior';
    COMMENT ON COLUMN conditional_rules.conditions IS 'Array of condition objects for rule evaluation';
    COMMENT ON COLUMN conditional_rules.actions IS 'Array of action objects to execute when conditions met';

    -- =====================================================
    -- 2. FORM TEMPLATES
    -- =====================================================
    CREATE TABLE IF NOT EXISTS form_templates (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        name VARCHAR(255) NOT NULL,
        description TEXT,
        category VARCHAR(100) NOT NULL,
        form_schema JSONB NOT NULL,
        thumbnail_url TEXT,
        is_public BOOLEAN DEFAULT FALSE,
        organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
        created_by UUID REFERENCES users(id) ON DELETE SET NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        usage_count INTEGER DEFAULT 0,
        tags TEXT[] DEFAULT ARRAY[]::TEXT[]
    );

    CREATE INDEX IF NOT EXISTS idx_form_templates_category ON form_templates(category);
    CREATE INDEX IF NOT EXISTS idx_form_templates_public ON form_templates(is_public);
    CREATE INDEX IF NOT EXISTS idx_form_templates_org ON form_templates(organization_id);
    CREATE INDEX IF NOT EXISTS idx_form_templates_tags ON form_templates USING GIN(tags);
    CREATE INDEX IF NOT EXISTS idx_form_templates_usage ON form_templates(usage_count DESC);

    COMMENT ON TABLE form_templates IS 'Pre-built form templates for common use cases';
    COMMENT ON COLUMN form_templates.category IS 'Template category: survey, registration, feedback, inspection, etc.';

    -- =====================================================
    -- 3. FORM VERSIONING & HISTORY
    -- =====================================================
    CREATE TABLE IF NOT EXISTS form_versions (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        form_id UUID NOT NULL REFERENCES forms(id) ON DELETE CASCADE,
        version_number INTEGER NOT NULL,
        form_schema JSONB NOT NULL,
        title VARCHAR(500) NOT NULL,
        description TEXT,
        change_summary TEXT,
        status VARCHAR(50) NOT NULL DEFAULT 'draft',
        created_by UUID REFERENCES users(id) ON DELETE SET NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        published_at TIMESTAMP WITH TIME ZONE,
        UNIQUE(form_id, version_number)
    );

    CREATE INDEX IF NOT EXISTS idx_form_versions_form_id ON form_versions(form_id);
    CREATE INDEX IF NOT EXISTS idx_form_versions_version ON form_versions(form_id, version_number DESC);
    CREATE INDEX IF NOT EXISTS idx_form_versions_status ON form_versions(status);

    COMMENT ON TABLE form_versions IS 'Version history for forms';
    COMMENT ON COLUMN form_versions.change_summary IS 'Human-readable description of changes in this version';

    -- Form change log for detailed audit trail
    CREATE TABLE IF NOT EXISTS form_change_log (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        form_id UUID NOT NULL REFERENCES forms(id) ON DELETE CASCADE,
        version_number INTEGER NOT NULL,
        change_type VARCHAR(50) NOT NULL,
        change_details JSONB NOT NULL,
        changed_by UUID REFERENCES users(id) ON DELETE SET NULL,
        changed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_form_change_log_form_id ON form_change_log(form_id);
    CREATE INDEX IF NOT EXISTS idx_form_change_log_version ON form_change_log(form_id, version_number);
    CREATE INDEX IF NOT EXISTS idx_form_change_log_type ON form_change_log(change_type);

    COMMENT ON TABLE form_change_log IS 'Detailed change log for form modifications';

    -- =====================================================
    -- 4. VALIDATION RULES
    -- =====================================================
    CREATE TABLE IF NOT EXISTS validation_rules (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        form_id UUID NOT NULL REFERENCES forms(id) ON DELETE CASCADE,
        field_id VARCHAR(255) NOT NULL,
        rule_type VARCHAR(50) NOT NULL CHECK (rule_type IN ('regex', 'custom', 'cross_field', 'async', 'range', 'length')),
        rule_config JSONB NOT NULL,
        error_message TEXT NOT NULL,
        severity VARCHAR(20) DEFAULT 'error' CHECK (severity IN ('error', 'warning', 'info')),
        is_active BOOLEAN DEFAULT TRUE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_validation_rules_form_field ON validation_rules(form_id, field_id);
    CREATE INDEX IF NOT EXISTS idx_validation_rules_type ON validation_rules(rule_type);
    CREATE INDEX IF NOT EXISTS idx_validation_rules_active ON validation_rules(is_active);

    COMMENT ON TABLE validation_rules IS 'Custom validation rules for form fields';
    COMMENT ON COLUMN validation_rules.rule_config IS 'Rule-specific configuration (pattern, compare_field, etc.)';

    -- =====================================================
    -- 5. FORM ANALYTICS
    -- =====================================================
    CREATE TABLE IF NOT EXISTS form_analytics (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        form_id UUID NOT NULL REFERENCES forms(id) ON DELETE CASCADE,
        date DATE NOT NULL,
        views INTEGER DEFAULT 0,
        starts INTEGER DEFAULT 0,
        completions INTEGER DEFAULT 0,
        avg_completion_time_seconds INTEGER,
        drop_off_rate DECIMAL(5,2),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(form_id, date)
    );

    CREATE INDEX IF NOT EXISTS idx_form_analytics_form_date ON form_analytics(form_id, date DESC);
    CREATE INDEX IF NOT EXISTS idx_form_analytics_date ON form_analytics(date DESC);

    COMMENT ON TABLE form_analytics IS 'Daily aggregated analytics for forms';

    CREATE TABLE IF NOT EXISTS field_analytics (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        form_id UUID NOT NULL REFERENCES forms(id) ON DELETE CASCADE,
        field_id VARCHAR(255) NOT NULL,
        date DATE NOT NULL,
        error_count INTEGER DEFAULT 0,
        skip_count INTEGER DEFAULT 0,
        avg_time_spent_seconds INTEGER,
        most_common_errors JSONB,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(form_id, field_id, date)
    );

    CREATE INDEX IF NOT EXISTS idx_field_analytics_form_field_date ON field_analytics(form_id, field_id, date DESC);

    COMMENT ON TABLE field_analytics IS 'Daily aggregated analytics for individual form fields';

    -- =====================================================
    -- 6. SECURITY ENHANCEMENTS
    -- =====================================================
    CREATE TABLE IF NOT EXISTS security_audit_log (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_id UUID REFERENCES users(id) ON DELETE SET NULL,
        action VARCHAR(100) NOT NULL,
        resource_type VARCHAR(50) NOT NULL,
        resource_id UUID,
        ip_address INET,
        user_agent TEXT,
        metadata JSONB,
        severity VARCHAR(20) DEFAULT 'info' CHECK (severity IN ('info', 'warning', 'critical')),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_security_audit_user ON security_audit_log(user_id, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_security_audit_resource ON security_audit_log(resource_type, resource_id);
    CREATE INDEX IF NOT EXISTS idx_security_audit_severity ON security_audit_log(severity, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_security_audit_action ON security_audit_log(action);

    COMMENT ON TABLE security_audit_log IS 'Security audit trail for all sensitive operations';

    CREATE TABLE IF NOT EXISTS rate_limit_violations (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        ip_address INET NOT NULL,
        endpoint VARCHAR(255) NOT NULL,
        violation_count INTEGER DEFAULT 1,
        first_violation_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        last_violation_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        is_blocked BOOLEAN DEFAULT FALSE,
        blocked_until TIMESTAMP WITH TIME ZONE
    );

    CREATE INDEX IF NOT EXISTS idx_rate_limit_ip ON rate_limit_violations(ip_address);
    CREATE INDEX IF NOT EXISTS idx_rate_limit_endpoint ON rate_limit_violations(endpoint);
    CREATE INDEX IF NOT EXISTS idx_rate_limit_blocked ON rate_limit_violations(is_blocked, blocked_until);

    COMMENT ON TABLE rate_limit_violations IS 'Track and manage rate limit violations';

    -- =====================================================
    -- 7. FORM LOCKING (Conflict Resolution)
    -- =====================================================
    ALTER TABLE forms
    ADD COLUMN IF NOT EXISTS lock_version INTEGER DEFAULT 1,
    ADD COLUMN IF NOT EXISTS locked_by UUID REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS locked_at TIMESTAMP WITH TIME ZONE;

    CREATE INDEX IF NOT EXISTS idx_forms_locked_by ON forms(locked_by) WHERE locked_by IS NOT NULL;

    COMMENT ON COLUMN forms.lock_version IS 'Optimistic locking version number';
    COMMENT ON COLUMN forms.locked_by IS 'User currently holding exclusive edit lock';
    COMMENT ON COLUMN forms.locked_at IS 'When the lock was acquired';

    -- =====================================================
    -- 8. ADDITIONAL FORM ASSIGNMENT COLUMNS
    -- =====================================================
    ALTER TABLE form_assignments
    ADD COLUMN IF NOT EXISTS completed_responses INTEGER DEFAULT 0;

    COMMENT ON COLUMN form_assignments.completed_responses IS 'Number of responses completed by this agent';

    -- =====================================================
    -- 9. RESPONSE TRACKING FOR MULTI-PAGE FORMS
    -- =====================================================
    ALTER TABLE responses
    ADD COLUMN IF NOT EXISTS current_page VARCHAR(255),
    ADD COLUMN IF NOT EXISTS completed_pages TEXT[] DEFAULT ARRAY[]::TEXT[],
    ADD COLUMN IF NOT EXISTS progress_percentage INTEGER DEFAULT 0;

    CREATE INDEX IF NOT EXISTS idx_responses_progress ON responses(progress_percentage) WHERE progress_percentage < 100;

    COMMENT ON COLUMN responses.current_page IS 'Current page ID for multi-page forms';
    COMMENT ON COLUMN responses.completed_pages IS 'Array of completed page IDs';
    COMMENT ON COLUMN responses.progress_percentage IS 'Completion progress (0-100)';

    -- =====================================================
    -- 10. PERFORMANCE INDEXES
    -- =====================================================
    CREATE INDEX IF NOT EXISTS idx_forms_org_status ON forms(organization_id, status) WHERE deleted = FALSE;
    CREATE INDEX IF NOT EXISTS idx_forms_created_at ON forms(created_at DESC) WHERE deleted = FALSE;
    CREATE INDEX IF NOT EXISTS idx_responses_form_submitted ON responses(form_id, submitted_at DESC) WHERE deleted = FALSE;
    """)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute("""
    -- Drop indexes
    DROP INDEX IF EXISTS idx_responses_form_submitted;
    DROP INDEX IF EXISTS idx_forms_created_at;
    DROP INDEX IF EXISTS idx_forms_org_status;
    DROP INDEX IF EXISTS idx_responses_progress;
    DROP INDEX IF EXISTS idx_forms_locked_by;
    DROP INDEX IF EXISTS idx_rate_limit_blocked;
    DROP INDEX IF EXISTS idx_rate_limit_endpoint;
    DROP INDEX IF EXISTS idx_rate_limit_ip;
    DROP INDEX IF EXISTS idx_security_audit_action;
    DROP INDEX IF EXISTS idx_security_audit_severity;
    DROP INDEX IF EXISTS idx_security_audit_resource;
    DROP INDEX IF EXISTS idx_security_audit_user;
    DROP INDEX IF EXISTS idx_field_analytics_form_field_date;
    DROP INDEX IF EXISTS idx_form_analytics_date;
    DROP INDEX IF EXISTS idx_form_analytics_form_date;
    DROP INDEX IF EXISTS idx_validation_rules_active;
    DROP INDEX IF EXISTS idx_validation_rules_type;
    DROP INDEX IF EXISTS idx_validation_rules_form_field;
    DROP INDEX IF EXISTS idx_form_change_log_type;
    DROP INDEX IF EXISTS idx_form_change_log_version;
    DROP INDEX IF EXISTS idx_form_change_log_form_id;
    DROP INDEX IF EXISTS idx_form_versions_status;
    DROP INDEX IF EXISTS idx_form_versions_version;
    DROP INDEX IF EXISTS idx_form_versions_form_id;
    DROP INDEX IF EXISTS idx_form_templates_usage;
    DROP INDEX IF EXISTS idx_form_templates_tags;
    DROP INDEX IF EXISTS idx_form_templates_org;
    DROP INDEX IF EXISTS idx_form_templates_public;
    DROP INDEX IF EXISTS idx_form_templates_category;
    DROP INDEX IF EXISTS idx_conditional_rules_active;
    DROP INDEX IF EXISTS idx_conditional_rules_type;
    DROP INDEX IF EXISTS idx_conditional_rules_form_id;

    -- Remove columns from existing tables
    ALTER TABLE responses
    DROP COLUMN IF EXISTS progress_percentage,
    DROP COLUMN IF EXISTS completed_pages,
    DROP COLUMN IF EXISTS current_page;

    ALTER TABLE form_assignments
    DROP COLUMN IF EXISTS completed_responses;

    ALTER TABLE forms
    DROP COLUMN IF EXISTS locked_at,
    DROP COLUMN IF EXISTS locked_by,
    DROP COLUMN IF EXISTS lock_version;

    -- Drop new tables
    DROP TABLE IF EXISTS rate_limit_violations CASCADE;
    DROP TABLE IF EXISTS security_audit_log CASCADE;
    DROP TABLE IF EXISTS field_analytics CASCADE;
    DROP TABLE IF EXISTS form_analytics CASCADE;
    DROP TABLE IF EXISTS validation_rules CASCADE;
    DROP TABLE IF EXISTS form_change_log CASCADE;
    DROP TABLE IF EXISTS form_versions CASCADE;
    DROP TABLE IF EXISTS form_templates CASCADE;
    DROP TABLE IF EXISTS conditional_rules CASCADE;
    """)
