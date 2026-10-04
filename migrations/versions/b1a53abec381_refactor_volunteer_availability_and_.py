"""refactor volunteer availability and skills

Revision ID: b1a53abec381
Revises: cadf4e13b08b
Create Date: 2026-08-28 15:13:06.487909

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b1a53abec381"
down_revision: Union[str, Sequence[str], None] = "cadf4e13b08b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Remove proficiency level because it is not part of the design.
    op.drop_column(
        "volunteerskill",
        "proficiency_level",
    )

    # Change availability_status from a single enum
    # to an array of enums so multiple availability
    # options can be selected.
    op.alter_column(
        "volunteerprofile",
        "availability_status",
        existing_type=postgresql.ENUM(
            "weekdays",
            "weekends",
            "emergencies_only",
            name="availabilitystatus",
        ),
        type_=postgresql.ARRAY(
            postgresql.ENUM(
                "weekdays",
                "weekends",
                "emergencies_only",
                name="availabilitystatus",
                create_type=False,
            )
        ),
        postgresql_using=(
            "ARRAY[availability_status::text::availabilitystatus]"
        ),
        existing_nullable=False,
    )


def downgrade() -> None:
    """Downgrade schema."""

    # Convert the first availability value back to a single enum.
    op.alter_column(
        "volunteerprofile",
        "availability_status",
        existing_type=postgresql.ARRAY(
            postgresql.ENUM(
                "weekdays",
                "weekends",
                "emergencies_only",
                name="availabilitystatus",
                create_type=False,
            )
        ),
        type_=postgresql.ENUM(
            "weekdays",
            "weekends",
            "emergencies_only",
            name="availabilitystatus",
        ),
        postgresql_using=(
            "(availability_status[1])::text::availabilitystatus"
        ),
        existing_nullable=False,
    )

    # Restore proficiency level.
    op.add_column(
        "volunteerskill",
        sa.Column(
            "proficiency_level",
            postgresql.ENUM(
                "beginner",
                "intermediate",
                "advanced",
                name="proficiencylevel",
            ),
            nullable=False,
            server_default="beginner",
        ),
    )

    op.alter_column(
        "volunteerskill",
        "proficiency_level",
        server_default=None,
    )