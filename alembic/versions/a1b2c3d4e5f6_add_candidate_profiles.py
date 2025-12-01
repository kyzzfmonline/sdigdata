"""add_candidate_profiles

Revision ID: a1b2c3d4e5f6
Revises: f1e2c3d4a5b6
Create Date: 2025-12-01 00:00:00.000000

This migration adds reusable candidate profiles so candidates can be
tracked across multiple election seasons with historical stats.
"""

from collections.abc import Sequence

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "f1e2c3d4a5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add candidate profiles for reusable candidates across elections."""
    op.execute("""
    -- ============================================
    -- POLITICAL_PARTIES TABLE - Manage political parties/groups
    -- ============================================
    CREATE TABLE IF NOT EXISTS political_parties (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

        -- Basic Information
        name VARCHAR(255) NOT NULL,
        abbreviation VARCHAR(20),
        slogan VARCHAR(500),
        description TEXT,

        -- Branding
        logo_url TEXT,
        color_primary VARCHAR(7),   -- Hex color like #FF0000
        color_secondary VARCHAR(7),

        -- Contact Information
        headquarters_address TEXT,
        website VARCHAR(500),
        email VARCHAR(255),
        phone VARCHAR(50),
        social_links JSONB DEFAULT '{}',

        -- Leadership & Structure
        leader_name VARCHAR(255),
        founded_date DATE,
        registration_number VARCHAR(100),

        -- Stats (computed)
        total_candidates INTEGER DEFAULT 0,
        total_elections_participated INTEGER DEFAULT 0,
        total_wins INTEGER DEFAULT 0,

        -- Status
        status VARCHAR(50) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'suspended', 'dissolved')),

        -- Audit
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        deleted BOOLEAN DEFAULT FALSE,
        deleted_at TIMESTAMP WITH TIME ZONE,

        -- Unique name within organization
        CONSTRAINT unique_party_name_org UNIQUE (organization_id, name)
    );

    -- Indexes for political_parties
    CREATE INDEX IF NOT EXISTS idx_political_parties_org ON political_parties(organization_id);
    CREATE INDEX IF NOT EXISTS idx_political_parties_status ON political_parties(status);
    CREATE INDEX IF NOT EXISTS idx_political_parties_name ON political_parties(name);
    CREATE INDEX IF NOT EXISTS idx_political_parties_deleted ON political_parties(deleted) WHERE deleted = FALSE;

    COMMENT ON TABLE political_parties IS 'Political parties or groups that candidates can belong to';
    COMMENT ON COLUMN political_parties.abbreviation IS 'Short form like NPP, NDC, etc.';
    COMMENT ON COLUMN political_parties.color_primary IS 'Party primary color in hex format';

    -- ============================================
    -- CANDIDATE_PROFILES TABLE - Master candidate records
    -- ============================================
    CREATE TABLE IF NOT EXISTS candidate_profiles (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        organization_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,

        -- Personal Information
        name VARCHAR(255) NOT NULL,
        photo_url TEXT,
        email VARCHAR(255),
        phone VARCHAR(50),
        date_of_birth DATE,

        -- Political Information
        party_id UUID REFERENCES political_parties(id) ON DELETE SET NULL,
        party VARCHAR(255),  -- Kept for backward compatibility / independent candidates
        bio TEXT,
        manifesto TEXT,

        -- Extended Information (JSONB for flexibility)
        policies JSONB DEFAULT '{}',
        experience JSONB DEFAULT '{}',
        endorsements JSONB DEFAULT '[]',
        education JSONB DEFAULT '[]',
        social_links JSONB DEFAULT '{}',

        -- Status
        status VARCHAR(50) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'suspended', 'deceased')),

        -- Computed Stats (updated after each election)
        total_elections INTEGER DEFAULT 0,
        total_wins INTEGER DEFAULT 0,
        total_votes_received BIGINT DEFAULT 0,
        highest_vote_percentage DECIMAL(5,2) DEFAULT 0.00,
        last_election_date TIMESTAMP WITH TIME ZONE,

        -- Audit
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        deleted BOOLEAN DEFAULT FALSE,
        deleted_at TIMESTAMP WITH TIME ZONE,

        -- Uniqueness within organization
        CONSTRAINT unique_candidate_name_org UNIQUE (organization_id, name, party)
    );

    -- Indexes for candidate_profiles
    CREATE INDEX IF NOT EXISTS idx_candidate_profiles_org ON candidate_profiles(organization_id);
    CREATE INDEX IF NOT EXISTS idx_candidate_profiles_party ON candidate_profiles(party);
    CREATE INDEX IF NOT EXISTS idx_candidate_profiles_party_id ON candidate_profiles(party_id);
    CREATE INDEX IF NOT EXISTS idx_candidate_profiles_status ON candidate_profiles(status);
    CREATE INDEX IF NOT EXISTS idx_candidate_profiles_name ON candidate_profiles(name);
    CREATE INDEX IF NOT EXISTS idx_candidate_profiles_deleted ON candidate_profiles(deleted) WHERE deleted = FALSE;

    COMMENT ON TABLE candidate_profiles IS 'Master candidate records that persist across elections';
    COMMENT ON COLUMN candidate_profiles.total_elections IS 'Number of elections participated in';
    COMMENT ON COLUMN candidate_profiles.total_wins IS 'Number of elections won';
    COMMENT ON COLUMN candidate_profiles.total_votes_received IS 'Total votes received across all elections';
    COMMENT ON COLUMN candidate_profiles.highest_vote_percentage IS 'Best performance percentage';

    -- ============================================
    -- ELECTION_CANDIDATES TABLE - Links candidates to positions
    -- This replaces the direct position_id in candidates table
    -- ============================================
    CREATE TABLE IF NOT EXISTS election_candidates (
        id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
        candidate_profile_id UUID NOT NULL REFERENCES candidate_profiles(id) ON DELETE CASCADE,
        position_id UUID NOT NULL REFERENCES election_positions(id) ON DELETE CASCADE,
        election_id UUID NOT NULL REFERENCES elections(id) ON DELETE CASCADE,

        -- Election-specific overrides (can differ from profile)
        display_name VARCHAR(255),  -- If different from profile name
        campaign_photo_url TEXT,    -- Election-specific photo
        campaign_slogan VARCHAR(500),
        campaign_manifesto TEXT,    -- Election-specific manifesto

        -- Election-specific data
        ballot_number INTEGER,      -- Position on ballot
        display_order INTEGER DEFAULT 0,

        -- Status in this election
        status VARCHAR(50) NOT NULL DEFAULT 'nominated' CHECK (status IN ('nominated', 'confirmed', 'withdrawn', 'disqualified')),

        -- Results (populated after election)
        votes_received INTEGER DEFAULT 0,
        vote_percentage DECIMAL(5,2) DEFAULT 0.00,
        ranking INTEGER,            -- Final position (1st, 2nd, etc.)
        is_winner BOOLEAN DEFAULT FALSE,

        -- Audit
        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,

        -- A candidate can only be in one position per election
        CONSTRAINT unique_candidate_position UNIQUE (candidate_profile_id, position_id),
        CONSTRAINT unique_candidate_election UNIQUE (candidate_profile_id, election_id)
    );

    -- Indexes for election_candidates
    CREATE INDEX IF NOT EXISTS idx_election_candidates_profile ON election_candidates(candidate_profile_id);
    CREATE INDEX IF NOT EXISTS idx_election_candidates_position ON election_candidates(position_id);
    CREATE INDEX IF NOT EXISTS idx_election_candidates_election ON election_candidates(election_id);
    CREATE INDEX IF NOT EXISTS idx_election_candidates_status ON election_candidates(status);
    CREATE INDEX IF NOT EXISTS idx_election_candidates_winner ON election_candidates(is_winner) WHERE is_winner = TRUE;

    COMMENT ON TABLE election_candidates IS 'Links candidate profiles to specific election positions';
    COMMENT ON COLUMN election_candidates.display_name IS 'Optional override of profile name for this election';
    COMMENT ON COLUMN election_candidates.ballot_number IS 'Position on the ballot paper';
    COMMENT ON COLUMN election_candidates.votes_received IS 'Total votes in this election';
    COMMENT ON COLUMN election_candidates.vote_percentage IS 'Percentage of total valid votes';
    COMMENT ON COLUMN election_candidates.ranking IS 'Final position (1=winner, 2=runner-up, etc.)';

    -- ============================================
    -- CANDIDATE_ELECTION_HISTORY VIEW
    -- Provides easy access to candidate history
    -- ============================================
    CREATE OR REPLACE VIEW candidate_election_history AS
    SELECT
        cp.id as candidate_id,
        cp.name as candidate_name,
        COALESCE(pp.name, cp.party) as party_name,
        pp.id as party_id,
        pp.abbreviation as party_abbreviation,
        pp.logo_url as party_logo,
        pp.color_primary as party_color,
        cp.photo_url,
        e.id as election_id,
        e.title as election_title,
        e.election_type,
        e.start_date as election_date,
        e.status as election_status,
        ep.title as position_title,
        ec.votes_received,
        ec.vote_percentage,
        ec.ranking,
        ec.is_winner,
        ec.status as candidacy_status
    FROM candidate_profiles cp
    LEFT JOIN political_parties pp ON cp.party_id = pp.id
    JOIN election_candidates ec ON cp.id = ec.candidate_profile_id
    JOIN elections e ON ec.election_id = e.id
    JOIN election_positions ep ON ec.position_id = ep.id
    WHERE cp.deleted = FALSE
    ORDER BY e.start_date DESC;

    COMMENT ON VIEW candidate_election_history IS 'Complete election history for all candidates';

    -- ============================================
    -- PARTY_ELECTION_STATS VIEW
    -- Aggregate stats per party per election
    -- ============================================
    CREATE OR REPLACE VIEW party_election_stats AS
    SELECT
        pp.id as party_id,
        pp.name as party_name,
        pp.abbreviation,
        pp.logo_url,
        pp.color_primary,
        e.id as election_id,
        e.title as election_title,
        e.election_type,
        e.start_date as election_date,
        COUNT(DISTINCT ec.candidate_profile_id) as candidates_fielded,
        COUNT(*) FILTER (WHERE ec.is_winner = TRUE) as seats_won,
        COALESCE(SUM(ec.votes_received), 0) as total_votes,
        ROUND(AVG(ec.vote_percentage), 2) as avg_vote_percentage
    FROM political_parties pp
    JOIN candidate_profiles cp ON pp.id = cp.party_id
    JOIN election_candidates ec ON cp.id = ec.candidate_profile_id
    JOIN elections e ON ec.election_id = e.id
    WHERE pp.deleted = FALSE
    GROUP BY pp.id, pp.name, pp.abbreviation, pp.logo_url, pp.color_primary,
             e.id, e.title, e.election_type, e.start_date
    ORDER BY e.start_date DESC;

    COMMENT ON VIEW party_election_stats IS 'Party performance statistics per election';

    -- ============================================
    -- MIGRATE EXISTING DATA from candidates table
    -- Create profiles from existing candidates
    -- ============================================

    -- First, create profiles from existing candidates
    INSERT INTO candidate_profiles (
        id,
        organization_id,
        name,
        photo_url,
        party,
        bio,
        manifesto,
        policies,
        experience,
        endorsements,
        created_at,
        updated_at
    )
    SELECT
        c.id,
        e.organization_id,
        c.name,
        c.photo_url,
        c.party,
        c.bio,
        c.manifesto,
        c.policies,
        c.experience,
        c.endorsements,
        c.created_at,
        c.updated_at
    FROM candidates c
    JOIN election_positions ep ON c.position_id = ep.id
    JOIN elections e ON ep.election_id = e.id
    ON CONFLICT DO NOTHING;

    -- Then create election_candidates records for existing candidates
    INSERT INTO election_candidates (
        candidate_profile_id,
        position_id,
        election_id,
        display_order,
        created_at,
        updated_at
    )
    SELECT
        c.id,
        c.position_id,
        ep.election_id,
        c.display_order,
        c.created_at,
        c.updated_at
    FROM candidates c
    JOIN election_positions ep ON c.position_id = ep.id
    ON CONFLICT DO NOTHING;

    -- ============================================
    -- UPDATE VOTES TABLE to reference election_candidates
    -- Add column for the new relationship
    -- ============================================
    ALTER TABLE votes
    ADD COLUMN IF NOT EXISTS election_candidate_id UUID REFERENCES election_candidates(id) ON DELETE SET NULL;

    -- Migrate existing vote candidate_id to election_candidate_id
    UPDATE votes v
    SET election_candidate_id = ec.id
    FROM election_candidates ec
    WHERE v.candidate_id = ec.candidate_profile_id
      AND v.election_id = ec.election_id
      AND v.election_candidate_id IS NULL;

    CREATE INDEX IF NOT EXISTS idx_votes_election_candidate ON votes(election_candidate_id);

    -- ============================================
    -- FUNCTION: Update candidate stats after election
    -- ============================================
    CREATE OR REPLACE FUNCTION update_candidate_stats(p_election_id UUID)
    RETURNS void AS $$
    DECLARE
        v_total_votes INTEGER;
    BEGIN
        -- Get total valid votes for the election
        SELECT COUNT(*) INTO v_total_votes
        FROM votes
        WHERE election_id = p_election_id;

        -- Update vote counts and percentages for candidates in this election
        UPDATE election_candidates ec
        SET
            votes_received = vote_count,
            vote_percentage = CASE
                WHEN v_total_votes > 0 THEN ROUND((vote_count::DECIMAL / v_total_votes) * 100, 2)
                ELSE 0
            END,
            updated_at = CURRENT_TIMESTAMP
        FROM (
            SELECT
                v.election_candidate_id,
                COUNT(*) as vote_count
            FROM votes v
            WHERE v.election_id = p_election_id
              AND v.election_candidate_id IS NOT NULL
            GROUP BY v.election_candidate_id
        ) vote_counts
        WHERE ec.id = vote_counts.election_candidate_id
          AND ec.election_id = p_election_id;

        -- Calculate rankings per position
        WITH ranked AS (
            SELECT
                id,
                position_id,
                ROW_NUMBER() OVER (PARTITION BY position_id ORDER BY votes_received DESC) as rank
            FROM election_candidates
            WHERE election_id = p_election_id
        )
        UPDATE election_candidates ec
        SET ranking = ranked.rank,
            is_winner = (ranked.rank = 1)
        FROM ranked
        WHERE ec.id = ranked.id;

        -- Update candidate profile aggregate stats
        UPDATE candidate_profiles cp
        SET
            total_elections = stats.election_count,
            total_wins = stats.win_count,
            total_votes_received = stats.total_votes,
            highest_vote_percentage = stats.best_percentage,
            last_election_date = stats.last_date,
            updated_at = CURRENT_TIMESTAMP
        FROM (
            SELECT
                ec.candidate_profile_id,
                COUNT(DISTINCT ec.election_id) as election_count,
                COUNT(*) FILTER (WHERE ec.is_winner = TRUE) as win_count,
                COALESCE(SUM(ec.votes_received), 0) as total_votes,
                COALESCE(MAX(ec.vote_percentage), 0) as best_percentage,
                MAX(e.start_date) as last_date
            FROM election_candidates ec
            JOIN elections e ON ec.election_id = e.id
            GROUP BY ec.candidate_profile_id
        ) stats
        WHERE cp.id = stats.candidate_profile_id;
    END;
    $$ LANGUAGE plpgsql;

    COMMENT ON FUNCTION update_candidate_stats IS 'Updates vote counts and rankings for candidates after an election';

    -- ============================================
    -- FUNCTION: Update party stats
    -- ============================================
    CREATE OR REPLACE FUNCTION update_party_stats()
    RETURNS void AS $$
    BEGIN
        UPDATE political_parties pp
        SET
            total_candidates = stats.candidate_count,
            total_elections_participated = stats.election_count,
            total_wins = stats.win_count,
            updated_at = CURRENT_TIMESTAMP
        FROM (
            SELECT
                cp.party_id,
                COUNT(DISTINCT cp.id) as candidate_count,
                COUNT(DISTINCT ec.election_id) as election_count,
                COUNT(*) FILTER (WHERE ec.is_winner = TRUE) as win_count
            FROM candidate_profiles cp
            LEFT JOIN election_candidates ec ON cp.id = ec.candidate_profile_id
            WHERE cp.party_id IS NOT NULL AND cp.deleted = FALSE
            GROUP BY cp.party_id
        ) stats
        WHERE pp.id = stats.party_id;
    END;
    $$ LANGUAGE plpgsql;

    COMMENT ON FUNCTION update_party_stats IS 'Updates aggregate statistics for all political parties';
    """)


def downgrade() -> None:
    """Remove candidate profiles system."""
    op.execute("""
    -- Drop functions
    DROP FUNCTION IF EXISTS update_candidate_stats(UUID);
    DROP FUNCTION IF EXISTS update_party_stats();

    -- Drop views
    DROP VIEW IF EXISTS candidate_election_history;
    DROP VIEW IF EXISTS party_election_stats;

    -- Remove column from votes
    ALTER TABLE votes DROP COLUMN IF EXISTS election_candidate_id;

    -- Drop tables (order matters due to foreign keys)
    DROP TABLE IF EXISTS election_candidates CASCADE;
    DROP TABLE IF EXISTS candidate_profiles CASCADE;
    DROP TABLE IF EXISTS political_parties CASCADE;
    """)
