"""add_rbac_tables

Revision ID: 2e9d8ffbcded
Revises: 68df989a6c19
Create Date: 2025-11-10 11:44:45.794429

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2e9d8ffbcded'
down_revision: Union[str, Sequence[str], None] = '68df989a6c19'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add RBAC tables (roles, permissions, user_roles, role_permissions)."""
    op.execute("""
    -- Roles table
    CREATE TABLE IF NOT EXISTS roles (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        name VARCHAR(100) UNIQUE NOT NULL,
        description TEXT,
        level INTEGER NOT NULL DEFAULT 0,
        is_system BOOLEAN NOT NULL DEFAULT FALSE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    -- Permissions table
    CREATE TABLE IF NOT EXISTS permissions (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        name VARCHAR(100) UNIQUE NOT NULL,
        description TEXT,
        resource VARCHAR(100) NOT NULL,
        action VARCHAR(50) NOT NULL,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(resource, action)
    );

    -- User roles table (many-to-many: users <-> roles)
    CREATE TABLE IF NOT EXISTS user_roles (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
        assigned_by UUID REFERENCES users(id) ON DELETE SET NULL,
        assigned_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        expires_at TIMESTAMP WITH TIME ZONE,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        UNIQUE(user_id, role_id)
    );

    -- Role permissions table (many-to-many: roles <-> permissions)
    CREATE TABLE IF NOT EXISTS role_permissions (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        role_id UUID NOT NULL REFERENCES roles(id) ON DELETE CASCADE,
        permission_id UUID NOT NULL REFERENCES permissions(id) ON DELETE CASCADE,
        granted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(role_id, permission_id)
    );

    -- Create indexes for better query performance
    CREATE INDEX IF NOT EXISTS idx_roles_name ON roles(name);
    CREATE INDEX IF NOT EXISTS idx_roles_level ON roles(level DESC);
    CREATE INDEX IF NOT EXISTS idx_permissions_resource ON permissions(resource);
    CREATE INDEX IF NOT EXISTS idx_permissions_action ON permissions(action);
    CREATE INDEX IF NOT EXISTS idx_user_roles_user_id ON user_roles(user_id);
    CREATE INDEX IF NOT EXISTS idx_user_roles_role_id ON user_roles(role_id);
    CREATE INDEX IF NOT EXISTS idx_user_roles_active ON user_roles(is_active);
    CREATE INDEX IF NOT EXISTS idx_role_permissions_role_id ON role_permissions(role_id);
    CREATE INDEX IF NOT EXISTS idx_role_permissions_permission_id ON role_permissions(permission_id);

    -- Add comments
    COMMENT ON TABLE roles IS 'User roles for RBAC (Role-Based Access Control)';
    COMMENT ON TABLE permissions IS 'System permissions for fine-grained access control';
    COMMENT ON TABLE user_roles IS 'Assignment of roles to users';
    COMMENT ON TABLE role_permissions IS 'Assignment of permissions to roles';
    COMMENT ON COLUMN roles.level IS 'Role hierarchy level (higher = more privileged)';
    COMMENT ON COLUMN roles.is_system IS 'Whether this is a system-managed role (cannot be deleted)';
    COMMENT ON COLUMN permissions.resource IS 'Resource type (e.g., users, forms, responses)';
    COMMENT ON COLUMN permissions.action IS 'Action type (e.g., create, read, update, delete)';
    COMMENT ON COLUMN user_roles.expires_at IS 'Optional expiration timestamp for temporary role assignments';

    -- Insert default roles
    INSERT INTO roles (name, description, level, is_system) VALUES
        ('super_admin', 'Super Administrator with full system access', 100, TRUE),
        ('admin', 'Organization Administrator', 50, TRUE),
        ('agent', 'Data Collection Agent', 10, TRUE),
        ('viewer', 'Read-only Viewer', 5, TRUE)
    ON CONFLICT (name) DO NOTHING;

    -- Insert default permissions
    INSERT INTO permissions (name, description, resource, action) VALUES
        -- User permissions
        ('users.create', 'Create new users', 'users', 'create'),
        ('users.read', 'View user information', 'users', 'read'),
        ('users.update', 'Update user information', 'users', 'update'),
        ('users.delete', 'Delete users', 'users', 'delete'),
        ('users.manage_roles', 'Assign roles to users', 'users', 'manage_roles'),

        -- Organization permissions
        ('organizations.create', 'Create new organizations', 'organizations', 'create'),
        ('organizations.read', 'View organization information', 'organizations', 'read'),
        ('organizations.update', 'Update organization information', 'organizations', 'update'),
        ('organizations.delete', 'Delete organizations', 'organizations', 'delete'),

        -- Form permissions
        ('forms.create', 'Create new forms', 'forms', 'create'),
        ('forms.read', 'View forms', 'forms', 'read'),
        ('forms.update', 'Update forms', 'forms', 'update'),
        ('forms.delete', 'Delete forms', 'forms', 'delete'),
        ('forms.publish', 'Publish forms', 'forms', 'publish'),
        ('forms.assign', 'Assign forms to agents', 'forms', 'assign'),

        -- Response permissions
        ('responses.create', 'Submit new responses', 'responses', 'create'),
        ('responses.read', 'View responses', 'responses', 'read'),
        ('responses.update', 'Update responses', 'responses', 'update'),
        ('responses.delete', 'Delete responses', 'responses', 'delete'),
        ('responses.export', 'Export responses to CSV/JSON', 'responses', 'export'),

        -- Analytics permissions
        ('analytics.view', 'View analytics dashboards', 'analytics', 'view'),
        ('analytics.export', 'Export analytics data', 'analytics', 'export'),

        -- System permissions
        ('system.admin', 'Full system administration', 'system', 'admin'),
        ('system.audit', 'View audit logs', 'system', 'audit')
    ON CONFLICT (resource, action) DO NOTHING;

    -- Assign all permissions to super_admin role
    INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, p.id
    FROM roles r
    CROSS JOIN permissions p
    WHERE r.name = 'super_admin'
    ON CONFLICT (role_id, permission_id) DO NOTHING;

    -- Assign permissions to admin role
    INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, p.id
    FROM roles r
    CROSS JOIN permissions p
    WHERE r.name = 'admin'
    AND p.resource IN ('users', 'forms', 'responses', 'analytics')
    AND p.action NOT IN ('system.admin', 'organizations.delete')
    ON CONFLICT (role_id, permission_id) DO NOTHING;

    -- Assign permissions to agent role
    INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, p.id
    FROM roles r
    CROSS JOIN permissions p
    WHERE r.name = 'agent'
    AND (
        (p.resource = 'forms' AND p.action = 'read')
        OR (p.resource = 'responses' AND p.action IN ('create', 'read', 'update'))
    )
    ON CONFLICT (role_id, permission_id) DO NOTHING;

    -- Assign permissions to viewer role
    INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, p.id
    FROM roles r
    CROSS JOIN permissions p
    WHERE r.name = 'viewer'
    AND p.action = 'read'
    ON CONFLICT (role_id, permission_id) DO NOTHING;
    """)


def downgrade() -> None:
    """Remove RBAC tables."""
    op.execute("""
    DROP INDEX IF EXISTS idx_role_permissions_permission_id;
    DROP INDEX IF EXISTS idx_role_permissions_role_id;
    DROP INDEX IF EXISTS idx_user_roles_active;
    DROP INDEX IF EXISTS idx_user_roles_role_id;
    DROP INDEX IF EXISTS idx_user_roles_user_id;
    DROP INDEX IF EXISTS idx_permissions_action;
    DROP INDEX IF EXISTS idx_permissions_resource;
    DROP INDEX IF EXISTS idx_roles_level;
    DROP INDEX IF EXISTS idx_roles_name;

    DROP TABLE IF EXISTS role_permissions CASCADE;
    DROP TABLE IF EXISTS user_roles CASCADE;
    DROP TABLE IF EXISTS permissions CASCADE;
    DROP TABLE IF EXISTS roles CASCADE;
    """)
