"""add description to forms

Revision ID: 510c81575b4a
Revises: b7ab79e8e908
Create Date: 2025-11-09 16:45:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "510c81575b4a"
down_revision: Union[str, Sequence[str], None] = "b7ab79e8e908"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add description column to forms table."""
    op.add_column("forms", sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    """Remove description column from forms table."""
    op.drop_column("forms", "description")
