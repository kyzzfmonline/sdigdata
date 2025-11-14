"""add_rbac_security_enhancements

Revision ID: 8c041eef0d9a
Revises: e84dc12cb616
Create Date: 2025-11-14 06:21:31.034239

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8c041eef0d9a'
down_revision: Union[str, Sequence[str], None] = 'e84dc12cb616'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add RBAC security enhancement tables."""
    op.execute("""
    -- ========================================================================
    -- AUDIT LOGS TABLE (Enhanced version - drop and recreate if exists)
    -- ========================================================================
    DROP TABLE IF EXISTS audit_logs CASCADE;

    CREATE TABLE audit_logs (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_id UUID REFERENCES users(id) ON DELETE SET NULL,
        action_type VARCHAR(100) NOT NULL,
        resource_type VARCHAR(100),
        resource_id UUID,
        severity VARCHAR(20) DEFAULT 'info',
        ip_address VARCHAR(45),
        user_agent TEXT,
        details JSONB,
        timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX idx_audit_logs_user_id ON audit_logs(user_id);
    CREATE INDEX idx_audit_logs_action_type ON audit_logs(action_type);
    CREATE INDEX idx_audit_logs_resource ON audit_logs(resource_type, resource_id);
    CREATE INDEX idx_audit_logs_timestamp ON audit_logs(timestamp DESC);
    CREATE INDEX idx_audit_logs_severity ON audit_logs(severity);

    COMMENT ON TABLE audit_logs IS 'Audit trail of all security-relevant actions';
    COMMENT ON COLUMN audit_logs.action_type IS 'Type of action (login, logout, permission_change, role_assignment, etc.)';
    COMMENT ON COLUMN audit_logs.severity IS 'Log severity: info, warning, critical';

    -- ========================================================================
    -- USER SESSIONS TABLE
    -- ========================================================================
    CREATE TABLE IF NOT EXISTS user_sessions (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        token_hash VARCHAR(255) NOT NULL UNIQUE,
        device_info JSONB,
        ip_address VARCHAR(45),
        location VARCHAR(255),
        user_agent TEXT,
        last_active_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        revoked_at TIMESTAMP WITH TIME ZONE
    );

    CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);
    CREATE INDEX IF NOT EXISTS idx_user_sessions_token_hash ON user_sessions(token_hash);
    CREATE INDEX IF NOT EXISTS idx_user_sessions_expires_at ON user_sessions(expires_at);
    CREATE INDEX IF NOT EXISTS idx_user_sessions_active ON user_sessions(user_id, revoked_at) WHERE revoked_at IS NULL;

    COMMENT ON TABLE user_sessions IS 'Active user login sessions for session management';
    COMMENT ON COLUMN user_sessions.token_hash IS 'Hashed JWT token for session tracking';
    COMMENT ON COLUMN user_sessions.revoked_at IS 'Timestamp when session was revoked (NULL = active)';

    -- ========================================================================
    -- API KEYS TABLE
    -- ========================================================================
    CREATE TABLE IF NOT EXISTS api_keys (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        name VARCHAR(255) NOT NULL,
        key_hash VARCHAR(255) NOT NULL UNIQUE,
        key_prefix VARCHAR(20) NOT NULL,
        scopes JSONB,
        last_used_at TIMESTAMP WITH TIME ZONE,
        expires_at TIMESTAMP WITH TIME ZONE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        revoked_at TIMESTAMP WITH TIME ZONE
    );

    CREATE INDEX IF NOT EXISTS idx_api_keys_user_id ON api_keys(user_id);
    CREATE INDEX IF NOT EXISTS idx_api_keys_key_hash ON api_keys(key_hash);
    CREATE INDEX IF NOT EXISTS idx_api_keys_active ON api_keys(user_id, revoked_at) WHERE revoked_at IS NULL;

    COMMENT ON TABLE api_keys IS 'API keys for programmatic access';
    COMMENT ON COLUMN api_keys.key_hash IS 'Bcrypt hash of the API key';
    COMMENT ON COLUMN api_keys.key_prefix IS 'First 10 chars of key for identification (e.g., sk_live_abc...)';
    COMMENT ON COLUMN api_keys.scopes IS 'JSON array of permission scopes for this key';

    -- ========================================================================
    -- PERMISSION GROUPS TABLE
    -- ========================================================================
    CREATE TABLE IF NOT EXISTS permission_groups (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        name VARCHAR(255) NOT NULL,
        description TEXT,
        is_system BOOLEAN DEFAULT FALSE,
        organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(name, organization_id)
    );

    CREATE TABLE IF NOT EXISTS permission_group_permissions (
        group_id UUID NOT NULL REFERENCES permission_groups(id) ON DELETE CASCADE,
        permission_id UUID NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
        PRIMARY KEY (group_id, permission_id)
    );

    CREATE INDEX IF NOT EXISTS idx_permission_groups_org ON permission_groups(organization_id);
    CREATE INDEX IF NOT EXISTS idx_permission_groups_name ON permission_groups(name);

    COMMENT ON TABLE permission_groups IS 'Reusable groups of permissions for easier role management';
    COMMENT ON COLUMN permission_groups.is_system IS 'System-defined groups cannot be deleted';

    -- ========================================================================
    -- PASSWORD POLICIES TABLE
    -- ========================================================================
    CREATE TABLE IF NOT EXISTS password_policies (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        organization_id UUID UNIQUE REFERENCES organizations(id) ON DELETE CASCADE,
        min_length INTEGER DEFAULT 8 CHECK (min_length >= 1 AND min_length <= 128),
        max_length INTEGER DEFAULT 128 CHECK (max_length >= 1 AND max_length <= 256),
        require_uppercase BOOLEAN DEFAULT TRUE,
        require_lowercase BOOLEAN DEFAULT TRUE,
        require_numbers BOOLEAN DEFAULT TRUE,
        require_special_chars BOOLEAN DEFAULT TRUE,
        special_chars_allowed VARCHAR(100) DEFAULT '@$!%*?&#^()_+-=[]{}|;:,.<>/',
        prevent_common_passwords BOOLEAN DEFAULT TRUE,
        password_expiry_days INTEGER CHECK (password_expiry_days IS NULL OR password_expiry_days > 0),
        password_history_count INTEGER DEFAULT 5 CHECK (password_history_count >= 0),
        max_login_attempts INTEGER DEFAULT 5 CHECK (max_login_attempts > 0),
        lockout_duration_minutes INTEGER DEFAULT 30 CHECK (lockout_duration_minutes > 0),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    COMMENT ON TABLE password_policies IS 'Password policy configuration per organization';
    COMMENT ON COLUMN password_policies.organization_id IS 'NULL = system-wide default policy';

    -- Insert default system-wide password policy
    INSERT INTO password_policies (organization_id, min_length, max_length, require_uppercase, require_lowercase, require_numbers, require_special_chars)
    VALUES (NULL, 8, 128, TRUE, TRUE, TRUE, TRUE)
    ON CONFLICT (organization_id) DO NOTHING;

    -- ========================================================================
    -- IP WHITELIST RULES TABLE
    -- ========================================================================
    CREATE TABLE IF NOT EXISTS ip_whitelist_rules (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
        ip_address VARCHAR(45) NOT NULL,
        ip_range VARCHAR(50),
        description TEXT,
        created_by UUID REFERENCES users(id) ON DELETE SET NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_ip_whitelist_org ON ip_whitelist_rules(organization_id);
    CREATE INDEX IF NOT EXISTS idx_ip_whitelist_ip ON ip_whitelist_rules(ip_address);

    COMMENT ON TABLE ip_whitelist_rules IS 'IP address whitelist for access control';
    COMMENT ON COLUMN ip_whitelist_rules.ip_range IS 'CIDR notation for IP ranges (e.g., 192.168.1.0/24)';

    -- ========================================================================
    -- 2FA (Two-Factor Authentication) TABLE
    -- ========================================================================
    CREATE TABLE IF NOT EXISTS user_2fa (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
        method VARCHAR(50) NOT NULL,
        secret VARCHAR(255) NOT NULL,
        backup_codes JSONB,
        enabled BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        verified_at TIMESTAMP WITH TIME ZONE
    );

    CREATE INDEX IF NOT EXISTS idx_user_2fa_user_id ON user_2fa(user_id);

    COMMENT ON TABLE user_2fa IS 'Two-factor authentication configuration per user';
    COMMENT ON COLUMN user_2fa.method IS 'Authentication method: totp, sms, email';
    COMMENT ON COLUMN user_2fa.secret IS 'Encrypted TOTP secret or phone/email for other methods';
    COMMENT ON COLUMN user_2fa.backup_codes IS 'Hashed backup recovery codes';

    -- ========================================================================
    -- SECURITY SETTINGS TABLE
    -- ========================================================================
    CREATE TABLE IF NOT EXISTS security_settings (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        organization_id UUID UNIQUE REFERENCES organizations(id) ON DELETE CASCADE,

        -- Session settings
        session_timeout_minutes INTEGER DEFAULT 60 CHECK (session_timeout_minutes > 0),
        absolute_timeout_hours INTEGER DEFAULT 12 CHECK (absolute_timeout_hours > 0),
        idle_timeout_minutes INTEGER DEFAULT 30 CHECK (idle_timeout_minutes > 0),
        max_concurrent_sessions INTEGER DEFAULT 5 CHECK (max_concurrent_sessions > 0),
        require_reauth_for_sensitive_actions BOOLEAN DEFAULT TRUE,
        force_logout_on_password_change BOOLEAN DEFAULT TRUE,
        remember_me_enabled BOOLEAN DEFAULT TRUE,
        remember_me_duration_days INTEGER DEFAULT 30 CHECK (remember_me_duration_days > 0),

        -- Organization security
        allow_public_forms BOOLEAN DEFAULT FALSE,
        require_email_verification BOOLEAN DEFAULT TRUE,
        allowed_email_domains TEXT[],
        enforce_2fa_for_all BOOLEAN DEFAULT FALSE,
        enforce_2fa_for_roles TEXT[],
        data_retention_days INTEGER DEFAULT 365 CHECK (data_retention_days > 0),
        auto_logout_inactive_users_days INTEGER DEFAULT 90 CHECK (auto_logout_inactive_users_days > 0),

        -- IP whitelist
        ip_whitelist_enabled BOOLEAN DEFAULT FALSE,

        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_security_settings_org ON security_settings(organization_id);

    COMMENT ON TABLE security_settings IS 'Security configuration per organization';
    COMMENT ON COLUMN security_settings.organization_id IS 'NULL = system-wide default settings';

    -- Insert default system-wide security settings
    INSERT INTO security_settings (organization_id)
    VALUES (NULL)
    ON CONFLICT (organization_id) DO NOTHING;

    -- ========================================================================
    -- RBAC SETTINGS TABLE
    -- ========================================================================
    CREATE TABLE IF NOT EXISTS rbac_settings (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        organization_id UUID UNIQUE REFERENCES organizations(id) ON DELETE CASCADE,

        allow_custom_roles BOOLEAN DEFAULT TRUE,
        allow_role_delegation BOOLEAN DEFAULT FALSE,
        require_approval_for_role_changes BOOLEAN DEFAULT TRUE,
        approval_required_for_roles TEXT[],
        max_roles_per_user INTEGER DEFAULT 5 CHECK (max_roles_per_user > 0),
        role_assignment_notifications_enabled BOOLEAN DEFAULT TRUE,

        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_rbac_settings_org ON rbac_settings(organization_id);

    COMMENT ON TABLE rbac_settings IS 'RBAC behavior configuration per organization';

    -- Insert default system-wide RBAC settings
    INSERT INTO rbac_settings (organization_id)
    VALUES (NULL)
    ON CONFLICT (organization_id) DO NOTHING;

    -- ========================================================================
    -- SYSTEM CONFIGURATION TABLE
    -- ========================================================================
    CREATE TABLE IF NOT EXISTS system_config (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        key VARCHAR(100) UNIQUE NOT NULL,
        value JSONB NOT NULL,
        description TEXT,
        updated_by UUID REFERENCES users(id) ON DELETE SET NULL,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    COMMENT ON TABLE system_config IS 'System-wide configuration key-value store';

    -- Insert default system configuration
    INSERT INTO system_config (key, value, description) VALUES
    ('rbac.enabled', 'true', 'Enable RBAC system'),
    ('rbac.default_role_for_new_users', '"viewer"', 'Default role assigned to new users'),
    ('rbac.permission_cache_ttl_seconds', '300', 'Permission cache TTL in seconds'),
    ('rbac.enable_permission_inheritance', 'true', 'Enable permission inheritance'),
    ('rbac.enable_role_hierarchy', 'true', 'Enable role hierarchy'),
    ('rbac.log_permission_checks', 'false', 'Log all permission checks'),
    ('rbac.strict_permission_mode', 'false', 'Strict permission checking mode'),
    ('features.2fa_enabled', 'true', 'Enable 2FA feature'),
    ('features.api_keys_enabled', 'true', 'Enable API key feature'),
    ('features.audit_logs_enabled', 'true', 'Enable audit logging'),
    ('features.ip_whitelisting_enabled', 'false', 'Enable IP whitelisting'),
    ('compliance.mode', '"GDPR"', 'Compliance mode: GDPR, HIPAA, SOC2'),
    ('compliance.audit_log_retention_days', '365', 'Audit log retention period'),
    ('compliance.inactive_user_data_retention_days', '730', 'Inactive user data retention'),
    ('compliance.deleted_data_retention_days', '90', 'Soft-deleted data retention'),
    ('compliance.session_log_retention_days', '30', 'Session log retention'),
    ('compliance.auto_cleanup_enabled', 'false', 'Enable automatic data cleanup')
    ON CONFLICT (key) DO NOTHING;

    -- ========================================================================
    -- ROLE ASSIGNMENTS ENHANCEMENTS
    -- ========================================================================
    -- Add reason column to user_roles if it doesn't exist
    DO $$
    BEGIN
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'user_roles' AND column_name = 'reason'
        ) THEN
            ALTER TABLE user_roles ADD COLUMN reason TEXT;
        END IF;
    END $$;

    COMMENT ON COLUMN user_roles.reason IS 'Reason for role assignment (especially for temporary access)';

    -- ========================================================================
    -- PERMISSION CHANGE HISTORY TABLE
    -- ========================================================================
    CREATE TABLE IF NOT EXISTS permission_change_history (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        change_type VARCHAR(50) NOT NULL,
        role_id UUID REFERENCES roles(id) ON DELETE SET NULL,
        role_name VARCHAR(100),
        permission_id UUID REFERENCES permissions(id) ON DELETE SET NULL,
        permission_name VARCHAR(100),
        changed_by UUID REFERENCES users(id) ON DELETE SET NULL,
        changed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP WITH TIME ZONE,
        reason TEXT
    );

    CREATE INDEX IF NOT EXISTS idx_permission_history_user ON permission_change_history(user_id, changed_at DESC);
    CREATE INDEX IF NOT EXISTS idx_permission_history_changed_by ON permission_change_history(changed_by);

    COMMENT ON TABLE permission_change_history IS 'Audit trail of permission and role changes';
    COMMENT ON COLUMN permission_change_history.change_type IS 'Type: role_assigned, role_revoked, permission_granted, permission_revoked';

    -- ========================================================================
    -- PASSWORD HISTORY TABLE (for preventing reuse)
    -- ========================================================================
    CREATE TABLE IF NOT EXISTS password_history (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        password_hash VARCHAR(255) NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    CREATE INDEX IF NOT EXISTS idx_password_history_user ON password_history(user_id, created_at DESC);

    COMMENT ON TABLE password_history IS 'Historical password hashes to prevent password reuse';
    """)



def downgrade() -> None:
    """Remove RBAC security enhancement tables."""
    op.execute("""
    -- Drop tables in reverse order (respecting foreign keys)
    DROP TABLE IF EXISTS password_history CASCADE;
    DROP TABLE IF EXISTS permission_change_history CASCADE;
    DROP TABLE IF EXISTS system_config CASCADE;
    DROP TABLE IF EXISTS rbac_settings CASCADE;
    DROP TABLE IF EXISTS security_settings CASCADE;
    DROP TABLE IF EXISTS user_2fa CASCADE;
    DROP TABLE IF EXISTS ip_whitelist_rules CASCADE;
    DROP TABLE IF EXISTS password_policies CASCADE;
    DROP TABLE IF EXISTS permission_group_permissions CASCADE;
    DROP TABLE IF EXISTS permission_groups CASCADE;
    DROP TABLE IF EXISTS api_keys CASCADE;
    DROP TABLE IF EXISTS user_sessions CASCADE;
    DROP TABLE IF EXISTS audit_logs CASCADE;

    -- Remove reason column from user_roles if it exists
    DO $$
    BEGIN
        IF EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'user_roles' AND column_name = 'reason'
        ) THEN
            ALTER TABLE user_roles DROP COLUMN reason;
        END IF;
    END $$;
    """)
