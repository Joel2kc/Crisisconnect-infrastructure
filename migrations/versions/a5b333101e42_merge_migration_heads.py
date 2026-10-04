"""merge migration heads

Revision ID: a5b333101e42
Revises: 0c8e5f5c93f4, b1a53abec381
Create Date: 2026-08-28 16:55:06.277758

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = 'a5b333101e42'
down_revision: Union[str, Sequence[str], None] = ('0c8e5f5c93f4', 'b1a53abec381')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
