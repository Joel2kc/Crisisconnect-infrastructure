"""add incident, incident_media, incident_agency, incident_update, agency_coverage tables

Revision ID: a02df9c612d1
Revises: 21ac059eabce
Create Date: 2026-09-02 15:26:35.247644

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a02df9c612d1'
down_revision: Union[str, Sequence[str], None] = '21ac059eabce'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


emergency_type_enum = postgresql.ENUM(
    'fire',
    'medical',
    'accident',
    'crime',
    'flood',
    'others',
    name='emergencytype',
    create_type=False,
)

incident_severity_enum = postgresql.ENUM(
    'low',
    'medium',
    'high_critical',
    name='incidentseverity',
    create_type=False,
)

incident_status_enum = postgresql.ENUM(
    'reported',
    'verified',
    'dispatched',
    'in_progress',
    'resolved',
    'rejected',
    name='incidentstatus',
    create_type=False,
)

incident_agency_role_enum = postgresql.ENUM(
    'primary',
    'supporting',
    name='incidentagencyrole',
    create_type=False,
)

incident_agency_status_enum = postgresql.ENUM(
    'notified',
    'verified',
    'dispatched',
    'responding',
    'resolved',
    'declined',
    name='incidentagencystatus',
    create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""

    bind = op.get_bind()

    # Create the enum types only if they don't already exist.
    emergency_type_enum.create(bind, checkfirst=True)
    incident_severity_enum.create(bind, checkfirst=True)
    incident_status_enum.create(bind, checkfirst=True)
    incident_agency_role_enum.create(bind, checkfirst=True)
    incident_agency_status_enum.create(bind, checkfirst=True)

    op.create_table(
        'agencycoverage',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('agency_id', sa.Integer(), nullable=False),
        sa.Column(
            'emergency_type',
            emergency_type_enum,
            nullable=False
        ),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['agency_id'], ['agency.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'incident',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('reference_code', sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column('reporter_id', sa.Integer(), nullable=True),
        sa.Column(
            'emergency_type',
            emergency_type_enum,
            nullable=False
        ),
        sa.Column(
            'emergency_type_other',
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=True
        ),
        sa.Column(
            'description',
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False
        ),
        sa.Column(
            'location',
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False
        ),
        sa.Column(
            'severity',
            incident_severity_enum,
            nullable=False
        ),
        sa.Column(
            'status',
            incident_status_enum,
            nullable=False
        ),
        sa.Column('occurred_at', sa.DateTime(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['reporter_id'], ['user.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_index(
        op.f('ix_incident_reference_code'),
        'incident',
        ['reference_code'],
        unique=True
    )

    op.create_table(
        'incidentagency',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('incident_id', sa.Integer(), nullable=False),
        sa.Column('agency_id', sa.Integer(), nullable=False),
        sa.Column(
            'role',
            incident_agency_role_enum,
            nullable=False
        ),
        sa.Column(
            'status',
            incident_agency_status_enum,
            nullable=False
        ),
        sa.Column('assigned_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['agency_id'], ['agency.id']),
        sa.ForeignKeyConstraint(['incident_id'], ['incident.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'incidentmedia',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('incident_id', sa.Integer(), nullable=False),
        sa.Column('uploaded_by', sa.Integer(), nullable=True),
        sa.Column(
            'url',
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=False
        ),
        sa.Column('uploaded_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['incident_id'], ['incident.id']),
        sa.ForeignKeyConstraint(['uploaded_by'], ['user.id']),
        sa.PrimaryKeyConstraint('id')
    )

    op.create_table(
        'incidentupdate',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('incident_id', sa.Integer(), nullable=False),
        sa.Column('actor_id', sa.Integer(), nullable=True),
        sa.Column(
            'note',
            sqlmodel.sql.sqltypes.AutoString(),
            nullable=True
        ),
        sa.Column(
            'old_status',
            incident_status_enum,
            nullable=True
        ),
        sa.Column(
            'new_status',
            incident_status_enum,
            nullable=False
        ),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['actor_id'], ['user.id']),
        sa.ForeignKeyConstraint(['incident_id'], ['incident.id']),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""

    op.drop_table('incidentupdate')
    op.drop_table('incidentmedia')
    op.drop_table('incidentagency')
    op.drop_index(
        op.f('ix_incident_reference_code'),
        table_name='incident'
    )
    op.drop_table('incident')
    op.drop_table('agencycoverage')
