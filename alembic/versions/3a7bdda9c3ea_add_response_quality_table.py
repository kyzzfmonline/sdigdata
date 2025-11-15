"""add_response_quality_table

Revision ID: 3a7bdda9c3ea
Revises: 8c041eef0d9a
Create Date: 2025-11-15 11:27:23.469906

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3a7bdda9c3ea'
down_revision: Union[str, Sequence[str], None] = '8c041eef0d9a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create response_quality table for ML-generated quality scores (if not exists)
    op.execute("""
        CREATE TABLE IF NOT EXISTS response_quality (
            response_id UUID NOT NULL PRIMARY KEY,
            quality_score DOUBLE PRECISION,
            completeness_score DOUBLE PRECISION,
            gps_accuracy_score DOUBLE PRECISION,
            photo_quality_score DOUBLE PRECISION,
            response_time_score DOUBLE PRECISION,
            consistency_score DOUBLE PRECISION,
            overall_score DOUBLE PRECISION,
            is_anomaly BOOLEAN DEFAULT false,
            anomaly_reason TEXT,
            suitable_for_training BOOLEAN DEFAULT true,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            calculated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (response_id) REFERENCES responses(id) ON DELETE CASCADE
        );

        -- Create indexes for performance
        CREATE INDEX IF NOT EXISTS idx_response_quality_overall_score ON response_quality(overall_score);
        CREATE INDEX IF NOT EXISTS idx_response_quality_suitable_for_training ON response_quality(suitable_for_training);
        CREATE INDEX IF NOT EXISTS idx_response_quality_is_anomaly ON response_quality(is_anomaly);
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index('idx_response_quality_is_anomaly', table_name='response_quality')
    op.drop_index('idx_response_quality_suitable_for_training', table_name='response_quality')
    op.drop_index('idx_response_quality_overall_score', table_name='response_quality')

    # Drop table
    op.drop_table('response_quality')
