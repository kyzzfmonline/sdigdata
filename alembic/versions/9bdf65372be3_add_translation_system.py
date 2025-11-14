"""add_translation_system

Revision ID: 9bdf65372be3
Revises: a384a4b92753
Create Date: 2025-11-10 18:27:45.575570

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '9bdf65372be3'
down_revision: Union[str, Sequence[str], None] = 'a384a4b92753'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add translation data collection system with reputation/ELO rating."""
    op.execute("""
    -- ===================================================================
    -- PHASE 1: Extend existing tables for translation features
    -- ===================================================================

    -- 1. Add form_type discriminator to forms table
    ALTER TABLE forms
    ADD COLUMN IF NOT EXISTS form_type VARCHAR(50) DEFAULT 'survey'
    CHECK (form_type IN ('survey', 'translation', 'translation_review'));

    -- Add translation-specific metadata
    ALTER TABLE forms
    ADD COLUMN IF NOT EXISTS translation_config JSONB;

    -- Add indexes
    CREATE INDEX IF NOT EXISTS idx_forms_form_type ON forms(form_type);
    CREATE INDEX IF NOT EXISTS idx_forms_translation_config ON forms USING GIN(translation_config);

    COMMENT ON COLUMN forms.form_type IS 'Type of form: survey, translation, translation_review';
    COMMENT ON COLUMN forms.translation_config IS 'Translation-specific config: languages, domain, review_threshold, etc.';

    -- 2. Extend responses table for review workflow
    ALTER TABLE responses
    DROP CONSTRAINT IF EXISTS responses_status_check;

    ALTER TABLE responses
    ADD CONSTRAINT responses_status_check
    CHECK (status IN ('draft', 'submitted', 'in_review', 'approved', 'rejected', 'needs_revision'));

    -- Add translation review tracking columns
    ALTER TABLE responses
    ADD COLUMN IF NOT EXISTS review_count INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS weighted_review_score DECIMAL(10,2) DEFAULT 0,
    ADD COLUMN IF NOT EXISTS approved_at TIMESTAMP WITH TIME ZONE,
    ADD COLUMN IF NOT EXISTS approved_by UUID REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS rejection_reason TEXT;

    -- Add indexes for review queries
    CREATE INDEX IF NOT EXISTS idx_responses_status ON responses(status);
    CREATE INDEX IF NOT EXISTS idx_responses_review_count ON responses(review_count);
    CREATE INDEX IF NOT EXISTS idx_responses_weighted_score ON responses(weighted_review_score);
    CREATE INDEX IF NOT EXISTS idx_responses_approved_by ON responses(approved_by);

    COMMENT ON COLUMN responses.review_count IS 'Number of reviews received';
    COMMENT ON COLUMN responses.weighted_review_score IS 'Weighted aggregate review score (ELO-based)';
    COMMENT ON COLUMN responses.approved_at IS 'Timestamp when translation was approved';

    -- ===================================================================
    -- PHASE 2: Create new translation-specific tables
    -- ===================================================================

    -- 3. User Reputation Table (ELO-based rating system)
    CREATE TABLE IF NOT EXISTS user_reputation (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        user_id UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,

        -- Translation metrics
        translations_submitted INTEGER DEFAULT 0,
        translations_accepted INTEGER DEFAULT 0,
        translations_rejected INTEGER DEFAULT 0,

        -- Review metrics
        reviews_submitted INTEGER DEFAULT 0,
        reviews_upvoted INTEGER DEFAULT 0,        -- Other reviewers agreed
        reviews_downvoted INTEGER DEFAULT 0,      -- Other reviewers disagreed

        -- Reputation scores (ELO-style)
        reputation_score DECIMAL(10,2) DEFAULT 100.0,  -- ELO-style score (starts at 100)
        review_weight DECIMAL(5,2) DEFAULT 1.0,        -- Current review voting weight (1.0 - 3.0)
        accuracy_rate DECIMAL(5,4) DEFAULT 0.0,        -- % of accepted translations

        -- Rank/level
        rank VARCHAR(50) DEFAULT 'novice',              -- novice, intermediate, expert, master, grandmaster
        rank_level INTEGER DEFAULT 1,

        -- Timestamps
        first_contribution_at TIMESTAMP WITH TIME ZONE,
        last_contribution_at TIMESTAMP WITH TIME ZONE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    -- Indexes for reputation queries
    CREATE INDEX IF NOT EXISTS idx_user_reputation_user_id ON user_reputation(user_id);
    CREATE INDEX IF NOT EXISTS idx_user_reputation_score ON user_reputation(reputation_score DESC);
    CREATE INDEX IF NOT EXISTS idx_user_reputation_rank ON user_reputation(rank_level DESC);
    CREATE INDEX IF NOT EXISTS idx_user_reputation_accuracy ON user_reputation(accuracy_rate DESC);

    COMMENT ON TABLE user_reputation IS 'User reputation and review weight for translation quality (ELO-based)';
    COMMENT ON COLUMN user_reputation.reputation_score IS 'ELO-style reputation score (starts at 100, logarithmic growth)';
    COMMENT ON COLUMN user_reputation.review_weight IS 'Current voting weight (1.0 = base, max ~3.0 to prevent gaming)';
    COMMENT ON COLUMN user_reputation.accuracy_rate IS 'Percentage of translations accepted (0.0 - 1.0)';

    -- 4. Translation Reviews Table
    CREATE TABLE IF NOT EXISTS translation_reviews (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        response_id UUID NOT NULL REFERENCES responses(id) ON DELETE CASCADE,
        reviewer_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,

        -- Review decision
        action VARCHAR(50) NOT NULL CHECK (action IN ('accept', 'reject', 'suggest_edit')),
        quality_rating INTEGER CHECK (quality_rating BETWEEN 1 AND 5),

        -- Feedback
        feedback TEXT,
        suggested_edit TEXT,                          -- Alternative translation
        improvement_notes JSONB,                      -- Structured feedback (grammar, accuracy, fluency, etc.)

        -- Review metadata (for weighted scoring)
        reviewer_reputation DECIMAL(10,2) NOT NULL,   -- Reputation at time of review
        review_weight DECIMAL(5,2) NOT NULL,          -- Weight at time of review
        weighted_score DECIMAL(10,2) NOT NULL,        -- This review's weighted contribution

        -- Agreement tracking (for reputation updates)
        agreement_votes INTEGER DEFAULT 0,            -- Reviews that agreed with this
        disagreement_votes INTEGER DEFAULT 0,         -- Reviews that disagreed

        -- Timestamps
        reviewed_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

        -- Prevent duplicate reviews
        UNIQUE(response_id, reviewer_id)
    );

    -- Indexes for review queries
    CREATE INDEX IF NOT EXISTS idx_translation_reviews_response ON translation_reviews(response_id);
    CREATE INDEX IF NOT EXISTS idx_translation_reviews_reviewer ON translation_reviews(reviewer_id);
    CREATE INDEX IF NOT EXISTS idx_translation_reviews_action ON translation_reviews(action);
    CREATE INDEX IF NOT EXISTS idx_translation_reviews_date ON translation_reviews(reviewed_at DESC);
    CREATE INDEX IF NOT EXISTS idx_translation_reviews_weight ON translation_reviews(review_weight DESC);

    COMMENT ON TABLE translation_reviews IS 'Reviews and feedback for translation submissions with weighted scoring';
    COMMENT ON COLUMN translation_reviews.weighted_score IS 'Contribution to response weighted score (rating * review_weight)';
    COMMENT ON COLUMN translation_reviews.improvement_notes IS 'Structured feedback: {"grammar": 4, "accuracy": 5, "fluency": 3, "cultural": 5}';

    -- 5. Translation Pairs Table (for ML export)
    CREATE TABLE IF NOT EXISTS translation_pairs (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

        -- Source and target
        source_text TEXT NOT NULL,
        target_text TEXT NOT NULL,
        source_language VARCHAR(10) NOT NULL,
        target_language VARCHAR(10) NOT NULL,

        -- Metadata
        domain VARCHAR(100),
        difficulty VARCHAR(50),
        context TEXT,                                  -- Additional context for the text

        -- Quality metrics
        final_quality_score DECIMAL(5,2),
        review_count INTEGER,

        -- References
        response_id UUID REFERENCES responses(id) ON DELETE SET NULL,
        form_id UUID REFERENCES forms(id) ON DELETE SET NULL,
        submitted_by UUID REFERENCES users(id) ON DELETE SET NULL,
        organization_id UUID REFERENCES organizations(id) ON DELETE CASCADE,

        -- Status
        is_validated BOOLEAN DEFAULT FALSE,
        suitable_for_training BOOLEAN DEFAULT FALSE,
        export_count INTEGER DEFAULT 0,                -- Track how many times exported

        -- Timestamps
        validated_at TIMESTAMP WITH TIME ZONE,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    -- Indexes for ML export queries
    CREATE INDEX IF NOT EXISTS idx_translation_pairs_languages ON translation_pairs(source_language, target_language);
    CREATE INDEX IF NOT EXISTS idx_translation_pairs_domain ON translation_pairs(domain);
    CREATE INDEX IF NOT EXISTS idx_translation_pairs_validated ON translation_pairs(is_validated);
    CREATE INDEX IF NOT EXISTS idx_translation_pairs_training ON translation_pairs(suitable_for_training);
    CREATE INDEX IF NOT EXISTS idx_translation_pairs_org ON translation_pairs(organization_id);
    CREATE INDEX IF NOT EXISTS idx_translation_pairs_quality ON translation_pairs(final_quality_score DESC);

    -- Full-text search indexes for finding translations
    CREATE INDEX IF NOT EXISTS idx_translation_pairs_source_text ON translation_pairs USING GIN(to_tsvector('english', source_text));
    CREATE INDEX IF NOT EXISTS idx_translation_pairs_target_text ON translation_pairs USING GIN(to_tsvector('english', target_text));

    COMMENT ON TABLE translation_pairs IS 'Validated translation pairs ready for ML training export';
    COMMENT ON COLUMN translation_pairs.suitable_for_training IS 'Meets quality threshold for ML training data';
    COMMENT ON COLUMN translation_pairs.export_count IS 'Number of times this pair has been exported';

    -- 6. Translation Batch Imports Table
    CREATE TABLE IF NOT EXISTS translation_batch_imports (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

        -- Import metadata
        form_id UUID NOT NULL REFERENCES forms(id) ON DELETE CASCADE,
        uploaded_by UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
        organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

        -- File info
        filename VARCHAR(500),
        file_size INTEGER,
        file_format VARCHAR(50),                      -- csv, json, tmx, etc.

        -- Import stats
        total_rows INTEGER DEFAULT 0,
        successful_imports INTEGER DEFAULT 0,
        failed_imports INTEGER DEFAULT 0,
        duplicate_imports INTEGER DEFAULT 0,

        -- Status
        status VARCHAR(50) DEFAULT 'processing' CHECK (status IN ('processing', 'completed', 'failed', 'partial')),
        error_log JSONB,                              -- Detailed error information

        -- Timestamps
        started_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        completed_at TIMESTAMP WITH TIME ZONE,

        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    -- Indexes for import tracking
    CREATE INDEX IF NOT EXISTS idx_batch_imports_form ON translation_batch_imports(form_id);
    CREATE INDEX IF NOT EXISTS idx_batch_imports_user ON translation_batch_imports(uploaded_by);
    CREATE INDEX IF NOT EXISTS idx_batch_imports_org ON translation_batch_imports(organization_id);
    CREATE INDEX IF NOT EXISTS idx_batch_imports_status ON translation_batch_imports(status);

    COMMENT ON TABLE translation_batch_imports IS 'Track bulk translation imports from CSV/files';

    -- ===================================================================
    -- PHASE 3: Performance optimization indexes
    -- ===================================================================

    -- Composite indexes for common queries
    CREATE INDEX IF NOT EXISTS idx_responses_form_status ON responses(form_id, status);
    CREATE INDEX IF NOT EXISTS idx_responses_user_status ON responses(submitted_by, status);
    CREATE INDEX IF NOT EXISTS idx_reviews_response_weight ON translation_reviews(response_id, review_weight DESC);

    -- Partial indexes for active data
    CREATE INDEX IF NOT EXISTS idx_responses_in_review ON responses(form_id, submitted_at DESC)
    WHERE status = 'in_review';

    CREATE INDEX IF NOT EXISTS idx_responses_approved ON responses(form_id, approved_at DESC)
    WHERE status = 'approved';

    -- ===================================================================
    -- PHASE 4: Add translation-specific permissions
    -- ===================================================================

    -- Insert new permissions for translation features
    INSERT INTO permissions (name, description, resource, action) VALUES
        ('translations.submit', 'Submit new translations', 'translations', 'submit'),
        ('translations.review', 'Review translations', 'translations', 'review'),
        ('translations.export', 'Export validated translations for ML training', 'translations', 'export'),
        ('translations.import', 'Bulk import translations', 'translations', 'import'),
        ('translations.moderate', 'Moderate translation reviews', 'translations', 'moderate'),
        ('reputation.view', 'View user reputation and leaderboards', 'reputation', 'view'),
        ('reputation.manage', 'Manage user reputation scores', 'reputation', 'manage')
    ON CONFLICT (resource, action) DO NOTHING;

    -- Assign translation permissions to existing roles
    -- Super admin gets all permissions
    INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, p.id
    FROM roles r
    CROSS JOIN permissions p
    WHERE r.name = 'super_admin'
    AND p.resource IN ('translations', 'reputation')
    ON CONFLICT (role_id, permission_id) DO NOTHING;

    -- Admin can submit, review, export, import, and moderate
    INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, p.id
    FROM roles r
    CROSS JOIN permissions p
    WHERE r.name = 'admin'
    AND p.resource IN ('translations', 'reputation')
    AND p.action NOT IN ('manage')
    ON CONFLICT (role_id, permission_id) DO NOTHING;

    -- Agents can submit and review
    INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, p.id
    FROM roles r
    CROSS JOIN permissions p
    WHERE r.name = 'agent'
    AND p.resource = 'translations'
    AND p.action IN ('submit', 'review')
    ON CONFLICT (role_id, permission_id) DO NOTHING;

    -- Agents can view reputation
    INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, p.id
    FROM roles r
    CROSS JOIN permissions p
    WHERE r.name = 'agent'
    AND p.resource = 'reputation'
    AND p.action = 'view'
    ON CONFLICT (role_id, permission_id) DO NOTHING;

    -- Viewers can view reputation
    INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, p.id
    FROM roles r
    CROSS JOIN permissions p
    WHERE r.name = 'viewer'
    AND p.resource = 'reputation'
    AND p.action = 'view'
    ON CONFLICT (role_id, permission_id) DO NOTHING;
    """)



def downgrade() -> None:
    """Remove translation system."""
    op.execute("""
    -- Remove translation permissions
    DELETE FROM role_permissions
    WHERE permission_id IN (
        SELECT id FROM permissions
        WHERE resource IN ('translations', 'reputation')
    );

    DELETE FROM permissions
    WHERE resource IN ('translations', 'reputation');

    -- Drop performance indexes
    DROP INDEX IF EXISTS idx_responses_approved;
    DROP INDEX IF EXISTS idx_responses_in_review;
    DROP INDEX IF EXISTS idx_reviews_response_weight;
    DROP INDEX IF EXISTS idx_responses_user_status;
    DROP INDEX IF EXISTS idx_responses_form_status;

    -- Drop new tables
    DROP TABLE IF EXISTS translation_batch_imports CASCADE;
    DROP TABLE IF EXISTS translation_pairs CASCADE;
    DROP TABLE IF EXISTS translation_reviews CASCADE;
    DROP TABLE IF EXISTS user_reputation CASCADE;

    -- Remove indexes from responses table
    DROP INDEX IF EXISTS idx_responses_approved_by;
    DROP INDEX IF EXISTS idx_responses_weighted_score;
    DROP INDEX IF EXISTS idx_responses_review_count;

    -- Remove columns from responses table
    ALTER TABLE responses
    DROP COLUMN IF EXISTS rejection_reason,
    DROP COLUMN IF EXISTS approved_by,
    DROP COLUMN IF EXISTS approved_at,
    DROP COLUMN IF EXISTS weighted_review_score,
    DROP COLUMN IF EXISTS review_count;

    -- Revert responses status constraint
    ALTER TABLE responses
    DROP CONSTRAINT IF EXISTS responses_status_check;

    ALTER TABLE responses
    ADD CONSTRAINT responses_status_check
    CHECK (status IN ('complete', 'incomplete', 'draft'));

    -- Remove indexes from forms table
    DROP INDEX IF EXISTS idx_forms_translation_config;
    DROP INDEX IF EXISTS idx_forms_form_type;

    -- Remove columns from forms table
    ALTER TABLE forms
    DROP COLUMN IF EXISTS translation_config,
    DROP COLUMN IF EXISTS form_type;
    """)
