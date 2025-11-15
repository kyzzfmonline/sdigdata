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
    # Create response_quality table for ML-generated quality scores
    op.create_table(
        'response_quality',
        sa.Column('response_id', sa.UUID(), nullable=False),
        sa.Column('quality_score', sa.Double(), nullable=True),
        sa.Column('completeness_score', sa.Double(), nullable=True),
        sa.Column('gps_accuracy_score', sa.Double(), nullable=True),
        sa.Column('photo_quality_score', sa.Double(), nullable=True),
        sa.Column('response_time_score', sa.Double(), nullable=True),
        sa.Column('consistency_score', sa.Double(), nullable=True),
        sa.Column('overall_score', sa.Double(), nullable=True),
        sa.Column('is_anomaly', sa.Boolean(), server_default='false', nullable=True),
        sa.Column('anomaly_reason', sa.Text(), nullable=True),
        sa.Column('suitable_for_training', sa.Boolean(), server_default='true', nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('updated_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.Column('calculated_at', sa.TIMESTAMP(), server_default=sa.text('CURRENT_TIMESTAMP'), nullable=True),
        sa.ForeignKeyConstraint(['response_id'], ['responses.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('response_id')
    )

    # Create indexes for performance
    op.create_index('idx_response_quality_overall_score', 'response_quality', ['overall_score'])
    op.create_index('idx_response_quality_suitable_for_training', 'response_quality', ['suitable_for_training'])
    op.create_index('idx_response_quality_is_anomaly', 'response_quality', ['is_anomaly'])


def downgrade() -> None:
    """Downgrade schema."""
    # Drop indexes
    op.drop_index('idx_response_quality_is_anomaly', table_name='response_quality')
    op.drop_index('idx_response_quality_suitable_for_training', table_name='response_quality')
    op.drop_index('idx_response_quality_overall_score', table_name='response_quality')

    # Drop table
    op.drop_table('response_quality')
