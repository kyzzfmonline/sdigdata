"""admin requirements

Revision ID: b7ab79e8e908
Revises: 51f0aa752a20
Create Date: 2025-11-09 11:15:02.910044

"""
from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = 'b7ab79e8e908'
down_revision: str | Sequence[str] | None = '51f0aa752a20'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
