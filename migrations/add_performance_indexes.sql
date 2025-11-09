-- Performance optimization indexes for production deployment
-- Generated: 2025-11-09
-- Purpose: Add critical indexes to improve query performance

-- Responses table indexes
-- These queries are run frequently in the application
CREATE INDEX IF NOT EXISTS idx_responses_form_id
    ON responses(form_id)
    WHERE deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_responses_submitted_by
    ON responses(submitted_by)
    WHERE deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_responses_submitted_at
    ON responses(submitted_at DESC);

CREATE INDEX IF NOT EXISTS idx_responses_submission_type
    ON responses(submission_type)
    WHERE deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_responses_deleted
    ON responses(deleted);

-- Composite index for common query pattern: form + date
CREATE INDEX IF NOT EXISTS idx_responses_form_date
    ON responses(form_id, submitted_at DESC)
    WHERE deleted = FALSE;

-- Form assignments indexes
CREATE INDEX IF NOT EXISTS idx_form_assignments_agent_id
    ON form_assignments(agent_id);

CREATE INDEX IF NOT EXISTS idx_form_assignments_form_id
    ON form_assignments(form_id);

CREATE INDEX IF NOT EXISTS idx_form_assignments_status
    ON form_assignments(status);

-- Composite index for checking agent permissions
CREATE INDEX IF NOT EXISTS idx_form_assignments_agent_form
    ON form_assignments(agent_id, form_id);

-- Forms table indexes
CREATE INDEX IF NOT EXISTS idx_forms_organization_id
    ON forms(organization_id)
    WHERE deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_forms_status
    ON forms(status)
    WHERE deleted = FALSE;

CREATE INDEX IF NOT EXISTS idx_forms_created_by
    ON forms(created_by);

CREATE INDEX IF NOT EXISTS idx_forms_deleted
    ON forms(deleted);

-- Users table indexes
CREATE INDEX IF NOT EXISTS idx_users_role
    ON users(role);

CREATE INDEX IF NOT EXISTS idx_users_organization_id
    ON users(organization_id);

CREATE INDEX IF NOT EXISTS idx_users_status
    ON users(status);

-- Quality scores table indexes (if exists)
CREATE INDEX IF NOT EXISTS idx_quality_scores_response_id
    ON quality_scores(response_id);

CREATE INDEX IF NOT EXISTS idx_quality_scores_quality_score
    ON quality_scores(quality_score);

-- Audit logs indexes (if exists)
CREATE INDEX IF NOT EXISTS idx_audit_logs_user_id
    ON audit_logs(user_id);

CREATE INDEX IF NOT EXISTS idx_audit_logs_action
    ON audit_logs(action);

CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at
    ON audit_logs(created_at DESC);

-- Notifications indexes (if exists)
CREATE INDEX IF NOT EXISTS idx_notifications_user_id
    ON notifications(user_id);

CREATE INDEX IF NOT EXISTS idx_notifications_read
    ON notifications(read);

CREATE INDEX IF NOT EXISTS idx_notifications_created_at
    ON notifications(created_at DESC);

-- Add comments for documentation
COMMENT ON INDEX idx_responses_form_id IS 'Performance: Speeds up queries filtering responses by form';
COMMENT ON INDEX idx_responses_submitted_at IS 'Performance: Speeds up chronological sorting of responses';
COMMENT ON INDEX idx_form_assignments_agent_form IS 'Performance: Speeds up permission checks for agent access to forms';
COMMENT ON INDEX idx_forms_organization_id IS 'Performance: Speeds up queries filtering forms by organization';

-- Analyze tables to update query planner statistics
ANALYZE responses;
ANALYZE forms;
ANALYZE form_assignments;
ANALYZE users;
ANALYZE organizations;
