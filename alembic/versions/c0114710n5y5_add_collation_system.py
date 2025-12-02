"""add_collation_system

Revision ID: c0114710n5y5
Revises: a1b2c3d4e5f6
Create Date: 2024-12-02

Adds comprehensive election collation infrastructure:
- Geographic hierarchy (regions, constituencies, wards, polling stations)
- Collation centers and officers
- Result sheets with multi-level approval workflow
- Incident and discrepancy tracking
- Aggregated results at each level
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "c0114710n5y5"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ============================================
    # GEOGRAPHIC HIERARCHY
    # ============================================

    # Regions (Level 1 - e.g., Greater Accra, Ashanti)
    op.create_table(
        "regions",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(50), nullable=True),  # e.g., "GAR", "ASH"
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("population", sa.Integer, nullable=True),
        sa.Column("registered_voters", sa.Integer, nullable=True),
        sa.Column("gps_lat", sa.Numeric(10, 8), nullable=True),
        sa.Column("gps_lng", sa.Numeric(11, 8), nullable=True),
        sa.Column("boundary_geojson", postgresql.JSONB, nullable=True),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("deleted", sa.Boolean, server_default="false"),
    )
    op.create_index("idx_regions_organization", "regions", ["organization_id"])
    op.create_index("idx_regions_code", "regions", ["code"])

    # Constituencies (Level 2 - e.g., Ayawaso West, Kumasi Central)
    op.create_table(
        "constituencies",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("region_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("regions.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(50), nullable=True),  # e.g., "AYW", "KMC"
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("constituency_type", sa.String(50), server_default="parliamentary"),  # parliamentary, local, etc.
        sa.Column("population", sa.Integer, nullable=True),
        sa.Column("registered_voters", sa.Integer, nullable=True),
        sa.Column("gps_lat", sa.Numeric(10, 8), nullable=True),
        sa.Column("gps_lng", sa.Numeric(11, 8), nullable=True),
        sa.Column("boundary_geojson", postgresql.JSONB, nullable=True),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("deleted", sa.Boolean, server_default="false"),
    )
    op.create_index("idx_constituencies_organization", "constituencies", ["organization_id"])
    op.create_index("idx_constituencies_region", "constituencies", ["region_id"])
    op.create_index("idx_constituencies_code", "constituencies", ["code"])

    # Electoral Areas / Wards (Level 3)
    op.create_table(
        "electoral_areas",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("constituency_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("constituencies.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(50), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("population", sa.Integer, nullable=True),
        sa.Column("registered_voters", sa.Integer, nullable=True),
        sa.Column("gps_lat", sa.Numeric(10, 8), nullable=True),
        sa.Column("gps_lng", sa.Numeric(11, 8), nullable=True),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("deleted", sa.Boolean, server_default="false"),
    )
    op.create_index("idx_electoral_areas_organization", "electoral_areas", ["organization_id"])
    op.create_index("idx_electoral_areas_constituency", "electoral_areas", ["constituency_id"])

    # Polling Stations (Level 4 - the actual voting locations)
    op.create_table(
        "polling_stations",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("electoral_area_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("electoral_areas.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("code", sa.String(100), nullable=True),  # Official station code
        sa.Column("station_number", sa.String(50), nullable=True),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column("facility_type", sa.String(100), nullable=True),  # school, community center, etc.
        sa.Column("registered_voters", sa.Integer, server_default="0"),
        sa.Column("gps_lat", sa.Numeric(10, 8), nullable=True),
        sa.Column("gps_lng", sa.Numeric(11, 8), nullable=True),
        sa.Column("accessibility_features", postgresql.JSONB, server_default="[]"),  # wheelchair, etc.
        sa.Column("contact_phone", sa.String(50), nullable=True),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("deleted", sa.Boolean, server_default="false"),
    )
    op.create_index("idx_polling_stations_organization", "polling_stations", ["organization_id"])
    op.create_index("idx_polling_stations_electoral_area", "polling_stations", ["electoral_area_id"])
    op.create_index("idx_polling_stations_code", "polling_stations", ["code"])

    # ============================================
    # COLLATION CENTERS
    # ============================================

    # Collation centers at each level
    op.create_table(
        "collation_centers",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("level", sa.String(50), nullable=False),  # polling_station, electoral_area, constituency, regional, national
        sa.Column("region_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("regions.id"), nullable=True),
        sa.Column("constituency_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("constituencies.id"), nullable=True),
        sa.Column("electoral_area_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("electoral_areas.id"), nullable=True),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column("gps_lat", sa.Numeric(10, 8), nullable=True),
        sa.Column("gps_lng", sa.Numeric(11, 8), nullable=True),
        sa.Column("contact_phone", sa.String(50), nullable=True),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_collation_centers_organization", "collation_centers", ["organization_id"])
    op.create_index("idx_collation_centers_level", "collation_centers", ["level"])

    # ============================================
    # COLLATION OFFICERS
    # ============================================

    op.create_table(
        "collation_officers",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("organization_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("officer_type", sa.String(50), nullable=False),  # presiding, returning, deputy_returning, collation, supervisor
        sa.Column("level", sa.String(50), nullable=False),  # polling_station, electoral_area, constituency, regional, national
        sa.Column("id_number", sa.String(100), nullable=True),  # Official ID/badge number
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("emergency_contact", sa.String(100), nullable=True),
        sa.Column("training_completed", sa.Boolean, server_default="false"),
        sa.Column("training_date", sa.Date, nullable=True),
        sa.Column("oath_taken", sa.Boolean, server_default="false"),
        sa.Column("oath_date", sa.Date, nullable=True),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("status", sa.String(20), server_default="active"),  # active, suspended, removed
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_collation_officers_organization", "collation_officers", ["organization_id"])
    op.create_index("idx_collation_officers_user", "collation_officers", ["user_id"])
    op.create_index("idx_collation_officers_type", "collation_officers", ["officer_type"])

    # Officer assignments to elections
    op.create_table(
        "officer_assignments",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("officer_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("collation_officers.id"), nullable=False),
        sa.Column("election_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("elections.id"), nullable=False),
        sa.Column("polling_station_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("polling_stations.id"), nullable=True),
        sa.Column("electoral_area_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("electoral_areas.id"), nullable=True),
        sa.Column("constituency_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("constituencies.id"), nullable=True),
        sa.Column("region_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("regions.id"), nullable=True),
        sa.Column("collation_center_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("collation_centers.id"), nullable=True),
        sa.Column("role", sa.String(100), nullable=False),  # presiding_officer, returning_officer, agent, observer
        sa.Column("assignment_date", sa.Date, nullable=True),
        sa.Column("confirmed", sa.Boolean, server_default="false"),
        sa.Column("confirmed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("checked_in", sa.Boolean, server_default="false"),
        sa.Column("checked_in_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("checked_in_gps_lat", sa.Numeric(10, 8), nullable=True),
        sa.Column("checked_in_gps_lng", sa.Numeric(11, 8), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), server_default="pending"),  # pending, active, completed, removed
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_officer_assignments_officer", "officer_assignments", ["officer_id"])
    op.create_index("idx_officer_assignments_election", "officer_assignments", ["election_id"])
    op.create_index("idx_officer_assignments_station", "officer_assignments", ["polling_station_id"])

    # ============================================
    # RESULT SHEETS (Paper-based results capture)
    # ============================================

    op.create_table(
        "result_sheets",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("election_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("elections.id"), nullable=False),
        sa.Column("position_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("election_positions.id"), nullable=False),
        sa.Column("polling_station_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("polling_stations.id"), nullable=False),
        sa.Column("sheet_number", sa.String(100), nullable=True),  # Official form number
        sa.Column("sheet_type", sa.String(50), server_default="primary"),  # primary, duplicate, replacement

        # Voter statistics
        sa.Column("registered_voters", sa.Integer, server_default="0"),
        sa.Column("ballots_issued", sa.Integer, server_default="0"),
        sa.Column("ballots_cast", sa.Integer, server_default="0"),
        sa.Column("valid_votes", sa.Integer, server_default="0"),
        sa.Column("rejected_ballots", sa.Integer, server_default="0"),
        sa.Column("spoilt_ballots", sa.Integer, server_default="0"),
        sa.Column("unused_ballots", sa.Integer, server_default="0"),

        # Workflow status
        sa.Column("status", sa.String(50), server_default="draft"),  # draft, submitted, verified, approved, disputed, rejected

        # Entry tracking
        sa.Column("entered_by", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("entered_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("entry_method", sa.String(50), nullable=True),  # manual, ocr, direct_upload

        # Submission
        sa.Column("submitted_by", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("submitted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("submission_gps_lat", sa.Numeric(10, 8), nullable=True),
        sa.Column("submission_gps_lng", sa.Numeric(11, 8), nullable=True),

        # Verification (by electoral area level)
        sa.Column("verified_by", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("verified_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("verification_notes", sa.Text, nullable=True),

        # Approval (by constituency level)
        sa.Column("approved_by", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("approval_signature", sa.Text, nullable=True),  # Digital signature hash

        # Rejection
        sa.Column("rejected_by", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("rejected_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text, nullable=True),

        # Data quality
        sa.Column("data_quality_score", sa.Numeric(5, 2), nullable=True),  # 0-100
        sa.Column("data_quality_flags", postgresql.JSONB, server_default="[]"),

        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_result_sheets_election", "result_sheets", ["election_id"])
    op.create_index("idx_result_sheets_position", "result_sheets", ["position_id"])
    op.create_index("idx_result_sheets_station", "result_sheets", ["polling_station_id"])
    op.create_index("idx_result_sheets_status", "result_sheets", ["status"])
    op.create_unique_constraint("uq_result_sheet_election_position_station", "result_sheets", ["election_id", "position_id", "polling_station_id", "sheet_type"])

    # Individual candidate results on each sheet
    op.create_table(
        "result_sheet_entries",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("result_sheet_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("result_sheets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("candidates.id"), nullable=True),
        sa.Column("election_candidate_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("election_candidates.id"), nullable=True),
        sa.Column("candidate_name", sa.String(255), nullable=False),  # Denormalized for records
        sa.Column("party", sa.String(100), nullable=True),
        sa.Column("votes_in_words", sa.String(255), nullable=True),  # "One Hundred Twenty Three"
        sa.Column("votes_in_figures", sa.Integer, nullable=False),
        sa.Column("ballot_order", sa.Integer, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_result_sheet_entries_sheet", "result_sheet_entries", ["result_sheet_id"])
    op.create_index("idx_result_sheet_entries_candidate", "result_sheet_entries", ["candidate_id"])

    # Attachments (photos of physical result sheets)
    op.create_table(
        "result_sheet_attachments",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("result_sheet_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("result_sheets.id", ondelete="CASCADE"), nullable=False),
        sa.Column("file_url", sa.Text, nullable=False),
        sa.Column("file_type", sa.String(50), nullable=False),  # image, pdf, document
        sa.Column("file_name", sa.String(255), nullable=True),
        sa.Column("file_size", sa.Integer, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("ocr_text", sa.Text, nullable=True),  # OCR extracted text if applicable
        sa.Column("ocr_confidence", sa.Numeric(5, 2), nullable=True),
        sa.Column("uploaded_by", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("uploaded_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("gps_lat", sa.Numeric(10, 8), nullable=True),
        sa.Column("gps_lng", sa.Numeric(11, 8), nullable=True),
    )
    op.create_index("idx_result_sheet_attachments_sheet", "result_sheet_attachments", ["result_sheet_id"])

    # ============================================
    # COLLATION WORKFLOW
    # ============================================

    # Aggregated results at each level
    op.create_table(
        "collation_results",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("election_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("elections.id"), nullable=False),
        sa.Column("position_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("election_positions.id"), nullable=False),
        sa.Column("level", sa.String(50), nullable=False),  # polling_station, electoral_area, constituency, regional, national

        # Location (one of these based on level)
        sa.Column("polling_station_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("polling_stations.id"), nullable=True),
        sa.Column("electoral_area_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("electoral_areas.id"), nullable=True),
        sa.Column("constituency_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("constituencies.id"), nullable=True),
        sa.Column("region_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("regions.id"), nullable=True),

        # Coverage stats
        sa.Column("total_units", sa.Integer, server_default="0"),  # Total child units
        sa.Column("reported_units", sa.Integer, server_default="0"),  # Units that have reported
        sa.Column("approved_units", sa.Integer, server_default="0"),  # Units approved at this level

        # Vote statistics
        sa.Column("registered_voters", sa.Integer, server_default="0"),
        sa.Column("total_votes_cast", sa.Integer, server_default="0"),
        sa.Column("valid_votes", sa.Integer, server_default="0"),
        sa.Column("rejected_ballots", sa.Integer, server_default="0"),
        sa.Column("turnout_percentage", sa.Numeric(5, 2), nullable=True),

        # Results data (JSONB for flexibility)
        sa.Column("results", postgresql.JSONB, server_default="[]"),  # [{candidate_id, name, party, votes, percentage}]

        # Workflow status
        sa.Column("status", sa.String(50), server_default="incomplete"),  # incomplete, submitted, verified, approved, certified, disputed

        # Timestamps
        sa.Column("submitted_by", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("submitted_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("verified_by", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("verified_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("approved_by", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("approved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("certified_by", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("certified_at", sa.TIMESTAMP(timezone=True), nullable=True),

        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_collation_results_election", "collation_results", ["election_id"])
    op.create_index("idx_collation_results_position", "collation_results", ["position_id"])
    op.create_index("idx_collation_results_level", "collation_results", ["level"])
    op.create_index("idx_collation_results_status", "collation_results", ["status"])

    # Workflow state transitions
    op.create_table(
        "collation_workflow_log",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("collation_result_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("collation_results.id"), nullable=True),
        sa.Column("result_sheet_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("result_sheets.id"), nullable=True),
        sa.Column("election_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("elections.id"), nullable=False),
        sa.Column("action", sa.String(100), nullable=False),  # submitted, verified, approved, rejected, disputed, resolved
        sa.Column("from_status", sa.String(50), nullable=True),
        sa.Column("to_status", sa.String(50), nullable=False),
        sa.Column("level", sa.String(50), nullable=True),
        sa.Column("performed_by", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("ip_address", sa.String(50), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("gps_lat", sa.Numeric(10, 8), nullable=True),
        sa.Column("gps_lng", sa.Numeric(11, 8), nullable=True),
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_collation_workflow_log_election", "collation_workflow_log", ["election_id"])
    op.create_index("idx_collation_workflow_log_result", "collation_workflow_log", ["collation_result_id"])
    op.create_index("idx_collation_workflow_log_sheet", "collation_workflow_log", ["result_sheet_id"])

    # ============================================
    # INCIDENTS & DISCREPANCIES
    # ============================================

    op.create_table(
        "collation_incidents",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("election_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("elections.id"), nullable=False),
        sa.Column("polling_station_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("polling_stations.id"), nullable=True),
        sa.Column("electoral_area_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("electoral_areas.id"), nullable=True),
        sa.Column("constituency_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("constituencies.id"), nullable=True),
        sa.Column("region_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("regions.id"), nullable=True),
        sa.Column("result_sheet_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("result_sheets.id"), nullable=True),

        sa.Column("incident_type", sa.String(100), nullable=False),  # missing_sheet, damaged_sheet, violence, equipment_failure, irregularity, discrepancy, delay, etc.
        sa.Column("category", sa.String(100), nullable=False),  # process, security, equipment, documentation, other
        sa.Column("severity", sa.String(20), nullable=False),  # low, medium, high, critical
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=False),

        sa.Column("reported_by", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("reported_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("report_gps_lat", sa.Numeric(10, 8), nullable=True),
        sa.Column("report_gps_lng", sa.Numeric(11, 8), nullable=True),

        sa.Column("status", sa.String(50), server_default="open"),  # open, investigating, resolved, closed, escalated

        sa.Column("assigned_to", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("assigned_at", sa.TIMESTAMP(timezone=True), nullable=True),

        sa.Column("resolved_by", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("resolution", sa.Text, nullable=True),
        sa.Column("resolution_type", sa.String(100), nullable=True),  # fixed, ignored, escalated, documented

        sa.Column("attachments", postgresql.JSONB, server_default="[]"),  # [{url, type, description}]
        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_collation_incidents_election", "collation_incidents", ["election_id"])
    op.create_index("idx_collation_incidents_station", "collation_incidents", ["polling_station_id"])
    op.create_index("idx_collation_incidents_type", "collation_incidents", ["incident_type"])
    op.create_index("idx_collation_incidents_severity", "collation_incidents", ["severity"])
    op.create_index("idx_collation_incidents_status", "collation_incidents", ["status"])

    # Discrepancies (specific to vote count mismatches)
    op.create_table(
        "collation_discrepancies",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("election_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("elections.id"), nullable=False),
        sa.Column("result_sheet_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("result_sheets.id"), nullable=True),
        sa.Column("collation_result_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("collation_results.id"), nullable=True),
        sa.Column("position_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("election_positions.id"), nullable=True),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=False), nullable=True),

        sa.Column("discrepancy_type", sa.String(100), nullable=False),  # vote_mismatch, ballot_count, total_mismatch, regional_mismatch
        sa.Column("level", sa.String(50), nullable=False),  # Where the discrepancy was detected

        sa.Column("expected_value", sa.Integer, nullable=True),
        sa.Column("reported_value", sa.Integer, nullable=True),
        sa.Column("difference", sa.Integer, nullable=True),
        sa.Column("percentage_difference", sa.Numeric(5, 2), nullable=True),

        sa.Column("description", sa.Text, nullable=True),

        sa.Column("detected_by", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("detected_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("detection_method", sa.String(100), nullable=True),  # automatic, manual_review

        sa.Column("status", sa.String(50), server_default="unresolved"),  # unresolved, investigating, resolved, ignored

        sa.Column("resolved_by", postgresql.UUID(as_uuid=False), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("resolution", sa.Text, nullable=True),
        sa.Column("corrected_value", sa.Integer, nullable=True),

        sa.Column("metadata", postgresql.JSONB, server_default="{}"),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_collation_discrepancies_election", "collation_discrepancies", ["election_id"])
    op.create_index("idx_collation_discrepancies_sheet", "collation_discrepancies", ["result_sheet_id"])
    op.create_index("idx_collation_discrepancies_type", "collation_discrepancies", ["discrepancy_type"])
    op.create_index("idx_collation_discrepancies_status", "collation_discrepancies", ["status"])

    # ============================================
    # ELECTION-GEOGRAPHIC MAPPING
    # ============================================

    # Map which polling stations are active for each election
    op.create_table(
        "election_polling_stations",
        sa.Column("id", postgresql.UUID(as_uuid=False), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("election_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("elections.id"), nullable=False),
        sa.Column("polling_station_id", postgresql.UUID(as_uuid=False), sa.ForeignKey("polling_stations.id"), nullable=False),
        sa.Column("registered_voters", sa.Integer, nullable=True),  # Override for this election
        sa.Column("status", sa.String(20), server_default="active"),  # active, inactive, suspended
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("idx_election_polling_stations_election", "election_polling_stations", ["election_id"])
    op.create_index("idx_election_polling_stations_station", "election_polling_stations", ["polling_station_id"])
    op.create_unique_constraint("uq_election_polling_station", "election_polling_stations", ["election_id", "polling_station_id"])

    # ============================================
    # HELPER FUNCTIONS
    # ============================================

    # Function to calculate collation progress
    op.execute("""
        CREATE OR REPLACE FUNCTION calculate_collation_progress(p_election_id UUID, p_level VARCHAR)
        RETURNS TABLE (
            total_units INTEGER,
            reported_units INTEGER,
            approved_units INTEGER,
            progress_percentage NUMERIC(5,2)
        ) AS $$
        BEGIN
            RETURN QUERY
            SELECT
                COUNT(DISTINCT ps.id)::INTEGER as total_units,
                COUNT(DISTINCT CASE WHEN rs.status IN ('submitted', 'verified', 'approved') THEN ps.id END)::INTEGER as reported_units,
                COUNT(DISTINCT CASE WHEN rs.status = 'approved' THEN ps.id END)::INTEGER as approved_units,
                ROUND(
                    COUNT(DISTINCT CASE WHEN rs.status IN ('submitted', 'verified', 'approved') THEN ps.id END)::NUMERIC /
                    NULLIF(COUNT(DISTINCT ps.id), 0) * 100, 2
                ) as progress_percentage
            FROM election_polling_stations eps
            JOIN polling_stations ps ON eps.polling_station_id = ps.id
            LEFT JOIN result_sheets rs ON rs.election_id = eps.election_id AND rs.polling_station_id = ps.id
            WHERE eps.election_id = p_election_id
            AND eps.status = 'active';
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Function to aggregate votes from polling stations to higher levels
    op.execute("""
        CREATE OR REPLACE FUNCTION aggregate_collation_results(
            p_election_id UUID,
            p_position_id UUID,
            p_level VARCHAR
        ) RETURNS VOID AS $$
        DECLARE
            v_area RECORD;
        BEGIN
            IF p_level = 'electoral_area' THEN
                -- Aggregate polling stations to electoral area
                FOR v_area IN
                    SELECT DISTINCT ea.id as area_id
                    FROM electoral_areas ea
                    JOIN polling_stations ps ON ps.electoral_area_id = ea.id
                    JOIN election_polling_stations eps ON eps.polling_station_id = ps.id
                    WHERE eps.election_id = p_election_id
                LOOP
                    INSERT INTO collation_results (
                        election_id, position_id, level, electoral_area_id,
                        total_units, reported_units, approved_units,
                        registered_voters, total_votes_cast, valid_votes, rejected_ballots,
                        results, status
                    )
                    SELECT
                        p_election_id,
                        p_position_id,
                        'electoral_area',
                        v_area.area_id,
                        COUNT(DISTINCT rs.polling_station_id)::INTEGER,
                        COUNT(DISTINCT CASE WHEN rs.status IN ('submitted', 'verified', 'approved') THEN rs.polling_station_id END)::INTEGER,
                        COUNT(DISTINCT CASE WHEN rs.status = 'approved' THEN rs.polling_station_id END)::INTEGER,
                        SUM(COALESCE(rs.registered_voters, 0))::INTEGER,
                        SUM(COALESCE(rs.ballots_cast, 0))::INTEGER,
                        SUM(COALESCE(rs.valid_votes, 0))::INTEGER,
                        SUM(COALESCE(rs.rejected_ballots, 0))::INTEGER,
                        '[]'::JSONB,
                        'incomplete'
                    FROM polling_stations ps
                    JOIN election_polling_stations eps ON eps.polling_station_id = ps.id
                    LEFT JOIN result_sheets rs ON rs.election_id = eps.election_id
                        AND rs.polling_station_id = ps.id
                        AND rs.position_id = p_position_id
                    WHERE ps.electoral_area_id = v_area.area_id
                    AND eps.election_id = p_election_id
                    ON CONFLICT (election_id, position_id, electoral_area_id)
                    DO UPDATE SET
                        total_units = EXCLUDED.total_units,
                        reported_units = EXCLUDED.reported_units,
                        approved_units = EXCLUDED.approved_units,
                        registered_voters = EXCLUDED.registered_voters,
                        total_votes_cast = EXCLUDED.total_votes_cast,
                        valid_votes = EXCLUDED.valid_votes,
                        rejected_ballots = EXCLUDED.rejected_ballots,
                        updated_at = CURRENT_TIMESTAMP;
                END LOOP;
            END IF;
            -- Similar logic for constituency and regional levels can be added
        END;
        $$ LANGUAGE plpgsql;
    """)

    # Trigger to auto-detect discrepancies
    op.execute("""
        CREATE OR REPLACE FUNCTION check_result_sheet_discrepancies()
        RETURNS TRIGGER AS $$
        DECLARE
            v_total_candidate_votes INTEGER;
        BEGIN
            -- Check if total candidate votes matches valid_votes
            SELECT SUM(votes_in_figures) INTO v_total_candidate_votes
            FROM result_sheet_entries
            WHERE result_sheet_id = NEW.id;

            IF v_total_candidate_votes IS NOT NULL AND NEW.valid_votes != v_total_candidate_votes THEN
                INSERT INTO collation_discrepancies (
                    election_id, result_sheet_id, position_id,
                    discrepancy_type, level,
                    expected_value, reported_value, difference,
                    description, detection_method
                ) VALUES (
                    NEW.election_id, NEW.id, NEW.position_id,
                    'vote_mismatch', 'polling_station',
                    NEW.valid_votes, v_total_candidate_votes,
                    ABS(NEW.valid_votes - v_total_candidate_votes),
                    'Sum of candidate votes does not match total valid votes',
                    'automatic'
                );
            END IF;

            -- Check if ballots cast makes sense
            IF NEW.ballots_cast > NEW.registered_voters * 1.1 THEN
                INSERT INTO collation_discrepancies (
                    election_id, result_sheet_id, position_id,
                    discrepancy_type, level,
                    expected_value, reported_value, difference,
                    description, detection_method
                ) VALUES (
                    NEW.election_id, NEW.id, NEW.position_id,
                    'ballot_count', 'polling_station',
                    NEW.registered_voters, NEW.ballots_cast,
                    NEW.ballots_cast - NEW.registered_voters,
                    'Ballots cast exceeds registered voters by more than 10%',
                    'automatic'
                );
            END IF;

            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;

        CREATE TRIGGER trigger_check_result_sheet_discrepancies
        AFTER INSERT OR UPDATE OF valid_votes, ballots_cast, registered_voters ON result_sheets
        FOR EACH ROW
        WHEN (NEW.status IN ('submitted', 'verified'))
        EXECUTE FUNCTION check_result_sheet_discrepancies();
    """)


def downgrade() -> None:
    # Drop triggers and functions
    op.execute("DROP TRIGGER IF EXISTS trigger_check_result_sheet_discrepancies ON result_sheets")
    op.execute("DROP FUNCTION IF EXISTS check_result_sheet_discrepancies()")
    op.execute("DROP FUNCTION IF EXISTS aggregate_collation_results(UUID, UUID, VARCHAR)")
    op.execute("DROP FUNCTION IF EXISTS calculate_collation_progress(UUID, VARCHAR)")

    # Drop tables in reverse order
    op.drop_table("election_polling_stations")
    op.drop_table("collation_discrepancies")
    op.drop_table("collation_incidents")
    op.drop_table("collation_workflow_log")
    op.drop_table("collation_results")
    op.drop_table("result_sheet_attachments")
    op.drop_table("result_sheet_entries")
    op.drop_table("result_sheets")
    op.drop_table("officer_assignments")
    op.drop_table("collation_officers")
    op.drop_table("collation_centers")
    op.drop_table("polling_stations")
    op.drop_table("electoral_areas")
    op.drop_table("constituencies")
    op.drop_table("regions")
