"""add_elections_system

Revision ID: f1e2c3d4a5b6
Revises: dc375e053374
Create Date: 2025-11-30 12:00:00.000000

"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1e2c3d4a5b6"
down_revision: str | Sequence[str] | None = "dc375e053374"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add elections and polling system tables."""
    op.execute("""
    -- ============================================
    -- ELECTIONS TABLE - Core election/poll entity
    -- ============================================
    CREATE TABLE IF NOT EXISTS elections (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
        title VARCHAR(255) NOT NULL,
        description TEXT,

        -- Election type and voting method
        election_type VARCHAR(50) NOT NULL CHECK (election_type IN ('election', 'poll', 'survey', 'referendum')),
        voting_method VARCHAR(50) NOT NULL CHECK (voting_method IN ('single_choice', 'multi_choice', 'ranked_choice')),

        -- Verification settings
        verification_level VARCHAR(50) NOT NULL DEFAULT 'anonymous' CHECK (verification_level IN ('anonymous', 'registered', 'verified')),
        require_national_id BOOLEAN DEFAULT FALSE,
        require_phone_otp BOOLEAN DEFAULT FALSE,

        -- Visibility settings
        results_visibility VARCHAR(50) NOT NULL DEFAULT 'after_close' CHECK (results_visibility IN ('real_time', 'after_close')),
        show_voter_count BOOLEAN DEFAULT TRUE,

        -- Timing
        start_date TIMESTAMP WITH TIME ZONE NOT NULL,
        end_date TIMESTAMP WITH TIME ZONE NOT NULL,

        -- Status
        status VARCHAR(50) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'scheduled', 'active', 'paused', 'closed', 'cancelled')),

        -- Optional form link for questionnaires
        linked_form_id UUID REFERENCES forms(id) ON DELETE SET NULL,

        -- Settings (JSONB for extensibility)
        settings JSONB DEFAULT '{}',

        -- Branding
        branding JSONB DEFAULT '{}',

        -- Audit
        created_by UUID NOT NULL REFERENCES users(id),
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        deleted BOOLEAN DEFAULT FALSE,
        deleted_at TIMESTAMP WITH TIME ZONE,

        -- Constraints
        CONSTRAINT valid_election_dates CHECK (end_date > start_date)
    );

    -- Indexes for elections
    CREATE INDEX IF NOT EXISTS idx_elections_organization ON elections(organization_id);
    CREATE INDEX IF NOT EXISTS idx_elections_status ON elections(status);
    CREATE INDEX IF NOT EXISTS idx_elections_type ON elections(election_type);
    CREATE INDEX IF NOT EXISTS idx_elections_dates ON elections(start_date, end_date);
    CREATE INDEX IF NOT EXISTS idx_elections_created_by ON elections(created_by);
    CREATE INDEX IF NOT EXISTS idx_elections_deleted ON elections(deleted) WHERE deleted = FALSE;

    -- Comments
    COMMENT ON TABLE elections IS 'Elections, polls, surveys, and referendums';
    COMMENT ON COLUMN elections.election_type IS 'Type: election, poll, survey, referendum';
    COMMENT ON COLUMN elections.voting_method IS 'Voting method: single_choice, multi_choice, ranked_choice';
    COMMENT ON COLUMN elections.verification_level IS 'Voter verification: anonymous, registered, verified';
    COMMENT ON COLUMN elections.results_visibility IS 'When results are visible: real_time, after_close';

    -- ============================================
    -- ELECTION_POSITIONS TABLE - Positions/offices
    -- ============================================
    CREATE TABLE IF NOT EXISTS election_positions (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        election_id UUID NOT NULL REFERENCES elections(id) ON DELETE CASCADE,
        title VARCHAR(255) NOT NULL,
        description TEXT,
        max_selections INTEGER DEFAULT 1 CHECK (max_selections >= 1),
        display_order INTEGER DEFAULT 0,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    -- Indexes for positions
    CREATE INDEX IF NOT EXISTS idx_election_positions_election ON election_positions(election_id);
    CREATE INDEX IF NOT EXISTS idx_election_positions_order ON election_positions(election_id, display_order);

    COMMENT ON TABLE election_positions IS 'Positions/offices being contested in an election';
    COMMENT ON COLUMN election_positions.max_selections IS 'Maximum number of candidates a voter can select (for multi-choice)';

    -- ============================================
    -- CANDIDATES TABLE - Contenders for positions
    -- ============================================
    CREATE TABLE IF NOT EXISTS candidates (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        position_id UUID NOT NULL REFERENCES election_positions(id) ON DELETE CASCADE,
        name VARCHAR(255) NOT NULL,
        photo_url TEXT,
        party VARCHAR(255),
        bio TEXT,
        manifesto TEXT,

        -- Comparison data
        policies JSONB DEFAULT '{}',
        experience JSONB DEFAULT '{}',
        endorsements JSONB DEFAULT '[]',

        display_order INTEGER DEFAULT 0,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    -- Indexes for candidates
    CREATE INDEX IF NOT EXISTS idx_candidates_position ON candidates(position_id);
    CREATE INDEX IF NOT EXISTS idx_candidates_order ON candidates(position_id, display_order);
    CREATE INDEX IF NOT EXISTS idx_candidates_party ON candidates(party);

    COMMENT ON TABLE candidates IS 'Candidates/contenders for election positions';
    COMMENT ON COLUMN candidates.policies IS 'Key policy positions as JSONB';
    COMMENT ON COLUMN candidates.experience IS 'Qualifications and history as JSONB';
    COMMENT ON COLUMN candidates.endorsements IS 'List of endorsements as JSONB array';

    -- ============================================
    -- POLL_OPTIONS TABLE - For polls/surveys
    -- ============================================
    CREATE TABLE IF NOT EXISTS poll_options (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        election_id UUID NOT NULL REFERENCES elections(id) ON DELETE CASCADE,
        option_text VARCHAR(500) NOT NULL,
        description TEXT,
        display_order INTEGER DEFAULT 0,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    -- Indexes for poll options
    CREATE INDEX IF NOT EXISTS idx_poll_options_election ON poll_options(election_id);
    CREATE INDEX IF NOT EXISTS idx_poll_options_order ON poll_options(election_id, display_order);

    COMMENT ON TABLE poll_options IS 'Options for polls/surveys (non-candidate based)';

    -- ============================================
    -- VOTERS TABLE - Voter registry
    -- ============================================
    CREATE TABLE IF NOT EXISTS voters (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        election_id UUID NOT NULL REFERENCES elections(id) ON DELETE CASCADE,

        -- Identification (hashed for privacy)
        national_id_hash VARCHAR(64),
        phone_hash VARCHAR(64),
        user_id UUID REFERENCES users(id) ON DELETE SET NULL,

        -- Verification status
        verified_at TIMESTAMP WITH TIME ZONE,
        verification_method VARCHAR(50) CHECK (verification_method IN ('national_id', 'phone_otp', 'both', 'user_account')),

        -- Demographics (optional, anonymized)
        region VARCHAR(100),
        age_group VARCHAR(20),

        -- Voting record
        has_voted BOOLEAN DEFAULT FALSE,
        voted_at TIMESTAMP WITH TIME ZONE,

        -- Metadata
        ip_address INET,
        user_agent TEXT,

        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

        -- Unique constraints to prevent duplicate registrations
        CONSTRAINT unique_voter_national_id UNIQUE (election_id, national_id_hash),
        CONSTRAINT unique_voter_phone UNIQUE (election_id, phone_hash),
        CONSTRAINT unique_voter_user UNIQUE (election_id, user_id)
    );

    -- Indexes for voters
    CREATE INDEX IF NOT EXISTS idx_voters_election ON voters(election_id);
    CREATE INDEX IF NOT EXISTS idx_voters_national_id ON voters(national_id_hash) WHERE national_id_hash IS NOT NULL;
    CREATE INDEX IF NOT EXISTS idx_voters_phone ON voters(phone_hash) WHERE phone_hash IS NOT NULL;
    CREATE INDEX IF NOT EXISTS idx_voters_user ON voters(user_id) WHERE user_id IS NOT NULL;
    CREATE INDEX IF NOT EXISTS idx_voters_has_voted ON voters(election_id, has_voted);
    CREATE INDEX IF NOT EXISTS idx_voters_region ON voters(election_id, region) WHERE region IS NOT NULL;

    COMMENT ON TABLE voters IS 'Voter registry for elections with verification tracking';
    COMMENT ON COLUMN voters.national_id_hash IS 'SHA-256 hash of national ID for privacy';
    COMMENT ON COLUMN voters.phone_hash IS 'SHA-256 hash of phone number for privacy';

    -- ============================================
    -- VOTES TABLE - Individual votes (anonymized)
    -- ============================================
    CREATE TABLE IF NOT EXISTS votes (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        election_id UUID NOT NULL REFERENCES elections(id) ON DELETE CASCADE,
        position_id UUID REFERENCES election_positions(id) ON DELETE CASCADE,

        -- Vote data
        candidate_id UUID REFERENCES candidates(id) ON DELETE CASCADE,
        poll_option_id UUID REFERENCES poll_options(id) ON DELETE CASCADE,
        rank INTEGER CHECK (rank >= 1),

        -- Anonymized voter reference
        voter_hash VARCHAR(64) NOT NULL,

        -- Metadata (for analytics, no PII)
        region VARCHAR(100),
        age_group VARCHAR(20),

        voted_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

        -- Constraint: vote must have either candidate or poll option
        CONSTRAINT vote_target CHECK (
            (candidate_id IS NOT NULL AND poll_option_id IS NULL) OR
            (candidate_id IS NULL AND poll_option_id IS NOT NULL)
        ),
        -- Prevent duplicate votes per position (for single/multi choice)
        CONSTRAINT unique_vote_per_position UNIQUE (election_id, position_id, voter_hash, candidate_id),
        -- Prevent duplicate poll votes
        CONSTRAINT unique_poll_vote UNIQUE (election_id, voter_hash, poll_option_id)
    );

    -- Indexes for votes
    CREATE INDEX IF NOT EXISTS idx_votes_election ON votes(election_id);
    CREATE INDEX IF NOT EXISTS idx_votes_position ON votes(position_id);
    CREATE INDEX IF NOT EXISTS idx_votes_candidate ON votes(candidate_id) WHERE candidate_id IS NOT NULL;
    CREATE INDEX IF NOT EXISTS idx_votes_poll_option ON votes(poll_option_id) WHERE poll_option_id IS NOT NULL;
    CREATE INDEX IF NOT EXISTS idx_votes_voter ON votes(voter_hash);
    CREATE INDEX IF NOT EXISTS idx_votes_time ON votes(election_id, voted_at);
    CREATE INDEX IF NOT EXISTS idx_votes_region ON votes(election_id, region) WHERE region IS NOT NULL;
    CREATE INDEX IF NOT EXISTS idx_votes_age ON votes(election_id, age_group) WHERE age_group IS NOT NULL;

    COMMENT ON TABLE votes IS 'Individual votes with anonymized voter references';
    COMMENT ON COLUMN votes.voter_hash IS 'Hash of voter identifier for anonymity while preventing duplicates';
    COMMENT ON COLUMN votes.rank IS 'Ranking for ranked-choice voting (1 = first choice)';

    -- ============================================
    -- ELECTION_RESULTS TABLE - Cached/finalized
    -- ============================================
    CREATE TABLE IF NOT EXISTS election_results (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        election_id UUID NOT NULL REFERENCES elections(id) ON DELETE CASCADE,
        position_id UUID REFERENCES election_positions(id) ON DELETE CASCADE,

        -- Results data
        candidate_id UUID REFERENCES candidates(id) ON DELETE CASCADE,
        poll_option_id UUID REFERENCES poll_options(id) ON DELETE CASCADE,

        vote_count INTEGER NOT NULL DEFAULT 0,
        percentage DECIMAL(5,2),
        rank_points INTEGER,

        -- Breakdown by demographics
        regional_breakdown JSONB DEFAULT '{}',
        demographic_breakdown JSONB DEFAULT '{}',

        -- Finalization
        is_final BOOLEAN DEFAULT FALSE,
        finalized_at TIMESTAMP WITH TIME ZONE,
        finalized_by UUID REFERENCES users(id),

        calculated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

        -- Unique constraint for result entries
        CONSTRAINT unique_candidate_result UNIQUE (election_id, position_id, candidate_id),
        CONSTRAINT unique_poll_result UNIQUE (election_id, poll_option_id)
    );

    -- Indexes for results
    CREATE INDEX IF NOT EXISTS idx_election_results_election ON election_results(election_id);
    CREATE INDEX IF NOT EXISTS idx_election_results_position ON election_results(position_id);
    CREATE INDEX IF NOT EXISTS idx_election_results_final ON election_results(election_id, is_final);
    CREATE INDEX IF NOT EXISTS idx_election_results_votes ON election_results(vote_count DESC);

    COMMENT ON TABLE election_results IS 'Cached and finalized election results';
    COMMENT ON COLUMN election_results.rank_points IS 'Points for ranked-choice voting calculation';

    -- ============================================
    -- ELECTION_AUDIT_LOG TABLE - Audit trail
    -- ============================================
    CREATE TABLE IF NOT EXISTS election_audit_log (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        election_id UUID NOT NULL REFERENCES elections(id) ON DELETE CASCADE,
        action VARCHAR(100) NOT NULL,
        actor_id UUID REFERENCES users(id) ON DELETE SET NULL,
        details JSONB,
        ip_address INET,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    -- Indexes for audit log
    CREATE INDEX IF NOT EXISTS idx_election_audit_election ON election_audit_log(election_id);
    CREATE INDEX IF NOT EXISTS idx_election_audit_action ON election_audit_log(action);
    CREATE INDEX IF NOT EXISTS idx_election_audit_actor ON election_audit_log(actor_id);
    CREATE INDEX IF NOT EXISTS idx_election_audit_time ON election_audit_log(created_at DESC);

    COMMENT ON TABLE election_audit_log IS 'Audit trail for all election-related actions';

    -- ============================================
    -- OTP_TOKENS TABLE - For phone verification
    -- ============================================
    CREATE TABLE IF NOT EXISTS election_otp_tokens (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        election_id UUID NOT NULL REFERENCES elections(id) ON DELETE CASCADE,
        phone_hash VARCHAR(64) NOT NULL,
        token_hash VARCHAR(64) NOT NULL,
        expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
        used BOOLEAN DEFAULT FALSE,
        used_at TIMESTAMP WITH TIME ZONE,
        attempts INTEGER DEFAULT 0,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
    );

    -- Indexes for OTP tokens
    CREATE INDEX IF NOT EXISTS idx_otp_election ON election_otp_tokens(election_id);
    CREATE INDEX IF NOT EXISTS idx_otp_phone ON election_otp_tokens(phone_hash);
    CREATE INDEX IF NOT EXISTS idx_otp_expires ON election_otp_tokens(expires_at);
    CREATE INDEX IF NOT EXISTS idx_otp_valid ON election_otp_tokens(election_id, phone_hash, used) WHERE used = FALSE;

    COMMENT ON TABLE election_otp_tokens IS 'OTP tokens for phone verification in elections';

    -- ============================================
    -- ADD ELECTION PERMISSIONS
    -- ============================================
    INSERT INTO permissions (name, description, resource, action) VALUES
        -- Election management permissions
        ('elections.create', 'Create new elections', 'elections', 'create'),
        ('elections.read', 'View elections', 'elections', 'read'),
        ('elections.update', 'Update elections', 'elections', 'update'),
        ('elections.delete', 'Delete elections', 'elections', 'delete'),
        ('elections.publish', 'Publish/schedule elections', 'elections', 'publish'),
        ('elections.manage', 'Full election management', 'elections', 'manage'),

        -- Voting permissions
        ('voting.vote', 'Cast votes in elections', 'voting', 'vote'),
        ('voting.verify', 'Verify voter eligibility', 'voting', 'verify'),

        -- Election analytics permissions
        ('election_analytics.view', 'View election results and analytics', 'election_analytics', 'view'),
        ('election_analytics.export', 'Export election data', 'election_analytics', 'export'),
        ('election_analytics.finalize', 'Finalize election results', 'election_analytics', 'finalize')
    ON CONFLICT (resource, action) DO NOTHING;

    -- ============================================
    -- ADD ELECTION OFFICER ROLE
    -- ============================================
    INSERT INTO roles (name, description, level, is_system) VALUES
        ('election_officer', 'Election management and oversight', 40, TRUE)
    ON CONFLICT (name) DO NOTHING;

    -- Assign election permissions to super_admin
    INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, p.id
    FROM roles r
    CROSS JOIN permissions p
    WHERE r.name = 'super_admin'
    AND p.resource IN ('elections', 'voting', 'election_analytics')
    ON CONFLICT (role_id, permission_id) DO NOTHING;

    -- Assign election permissions to admin
    INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, p.id
    FROM roles r
    CROSS JOIN permissions p
    WHERE r.name = 'admin'
    AND p.resource IN ('elections', 'voting', 'election_analytics')
    AND p.action NOT IN ('finalize')
    ON CONFLICT (role_id, permission_id) DO NOTHING;

    -- Assign permissions to election_officer role
    INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, p.id
    FROM roles r
    CROSS JOIN permissions p
    WHERE r.name = 'election_officer'
    AND p.resource IN ('elections', 'voting', 'election_analytics')
    ON CONFLICT (role_id, permission_id) DO NOTHING;

    -- Assign basic voting permission to agent role
    INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, p.id
    FROM roles r
    CROSS JOIN permissions p
    WHERE r.name = 'agent'
    AND p.name IN ('elections.read', 'voting.vote', 'election_analytics.view')
    ON CONFLICT (role_id, permission_id) DO NOTHING;

    -- Assign read-only permissions to viewer role
    INSERT INTO role_permissions (role_id, permission_id)
    SELECT r.id, p.id
    FROM roles r
    CROSS JOIN permissions p
    WHERE r.name = 'viewer'
    AND p.name IN ('elections.read', 'election_analytics.view')
    ON CONFLICT (role_id, permission_id) DO NOTHING;
    """)


def downgrade() -> None:
    """Remove elections system tables and permissions."""
    op.execute("""
    -- Remove role permissions for election-related permissions
    DELETE FROM role_permissions
    WHERE permission_id IN (
        SELECT id FROM permissions WHERE resource IN ('elections', 'voting', 'election_analytics')
    );

    -- Remove election_officer role
    DELETE FROM roles WHERE name = 'election_officer';

    -- Remove election permissions
    DELETE FROM permissions WHERE resource IN ('elections', 'voting', 'election_analytics');

    -- Drop tables in reverse order of dependencies
    DROP TABLE IF EXISTS election_otp_tokens CASCADE;
    DROP TABLE IF EXISTS election_audit_log CASCADE;
    DROP TABLE IF EXISTS election_results CASCADE;
    DROP TABLE IF EXISTS votes CASCADE;
    DROP TABLE IF EXISTS voters CASCADE;
    DROP TABLE IF EXISTS poll_options CASCADE;
    DROP TABLE IF EXISTS candidates CASCADE;
    DROP TABLE IF EXISTS election_positions CASCADE;
    DROP TABLE IF EXISTS elections CASCADE;
    """)
