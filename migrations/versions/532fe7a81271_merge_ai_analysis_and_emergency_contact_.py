"""merge ai analysis and emergency contact heads

Revision ID: 532fe7a81271
Revises: c84ead96ade8, 0df3a419faf8
Create Date: 2026-09-11 07:48:59.497913

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '532fe7a81271'
down_revision: Union[str, Sequence[str], None] = ('c84ead96ade8', '0df3a419faf8')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
