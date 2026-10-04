"""merge responder and agency resource heads

Revision ID: c16f3260d3de
Revises: 7cb4374e2986, c055d1b2bede
Create Date: 2026-09-11 09:17:07.510875

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'c16f3260d3de'
down_revision: Union[str, Sequence[str], None] = ('7cb4374e2986', 'c055d1b2bede')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
