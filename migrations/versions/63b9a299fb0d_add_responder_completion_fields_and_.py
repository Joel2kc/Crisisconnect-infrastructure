"""add responder completion fields and evidence

Revision ID: 63b9a299fb0d
Revises: c40d14599278
Create Date: 2026-09-14 09:57:30.040173

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '63b9a299fb0d'
down_revision: Union[str, Sequence[str], None] = 'c40d14599278'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    responder_response_outcome = sa.Enum(
        'resolved',
        'stabilized_or_assistance_provided',
        'transferred_to_another_agency',
        'unable_to_resolve',
        'no_action_required',
        'other',
        name='responderresponseoutcome',
    )

    # Create the PostgreSQL enum type before adding the column
    responder_response_outcome.create(op.get_bind(), checkfirst=True)

    op.create_table(
        'respondercompletionevidence',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('assignment_id', sa.Integer(), nullable=False),
        sa.Column('uploaded_by', sa.Integer(), nullable=False),
        sa.Column('url', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('uploaded_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ['assignment_id'],
            ['responderassignment.id'],
        ),
        sa.ForeignKeyConstraint(
            ['uploaded_by'],
            ['user.id'],
        ),
        sa.PrimaryKeyConstraint('id'),
    )

    op.create_index(
        op.f('ix_respondercompletionevidence_assignment_id'),
        'respondercompletionevidence',
        ['assignment_id'],
        unique=False,
    )

    op.drop_index(
        op.f('ix_locationping_assignment_recorded'),
        table_name='locationping',
    )

    op.add_column(
        'responderassignment',
        sa.Column(
            'response_outcome',
            responder_response_outcome,
            nullable=True,
        ),
    )

    op.add_column(
        'responderassignment',
        sa.Column(
            'response_note',
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=True,
        ),
    )

    op.create_index(
        op.f('ix_responderassignment_incident_id'),
        'responderassignment',
        ['incident_id'],
        unique=False,
    )

    op.create_index(
        op.f('ix_responderassignment_responder_id'),
        'responderassignment',
        ['responder_id'],
        unique=False,
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_index(
        op.f('ix_responderassignment_responder_id'),
        table_name='responderassignment',
    )

    op.drop_index(
        op.f('ix_responderassignment_incident_id'),
        table_name='responderassignment',
    )

    op.drop_column(
        'responderassignment',
        'response_note',
    )

    op.drop_column(
        'responderassignment',
        'response_outcome',
    )

    op.create_index(
        op.f('ix_locationping_assignment_recorded'),
        'locationping',
        ['assignee_kind', 'assignment_id', 'recorded_at'],
        unique=False,
    )

    op.drop_index(
        op.f('ix_respondercompletionevidence_assignment_id'),
        table_name='respondercompletionevidence',
    )

    op.drop_table('respondercompletionevidence')

    # Drop the PostgreSQL enum after the column using it is gone
    responder_response_outcome = sa.Enum(
        'resolved',
        'stabilized_or_assistance_provided',
        'transferred_to_another_agency',
        'unable_to_resolve',
        'no_action_required',
        'other',
        name='responderresponseoutcome',
    )

    responder_response_outcome.drop(
        op.get_bind(),
        checkfirst=True,
    )
    # ### end Alembic commands ###
