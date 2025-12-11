"""Add location_visits table for change tracking.

Revision ID: 012
Revises: 011_add_npc_goals
Create Date: 2025-12-10

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '012'
down_revision = '011_add_npc_goals'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create location_visits table."""
    op.create_table(
        'location_visits',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.Integer(), nullable=False),
        sa.Column('location_key', sa.String(100), nullable=False),
        sa.Column('last_visit_turn', sa.Integer(), nullable=False),
        sa.Column('last_visit_time', sa.String(5), nullable=True),
        sa.Column('last_visit_day', sa.Integer(), nullable=True),
        sa.Column('items_snapshot', sa.JSON(), nullable=True),
        sa.Column('npcs_snapshot', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ['session_id'],
            ['game_sessions.id'],
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'session_id', 'location_key',
            name='uq_location_visit_session_location'
        ),
    )
    op.create_index(
        op.f('ix_location_visits_id'),
        'location_visits',
        ['id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_location_visits_session_id'),
        'location_visits',
        ['session_id'],
        unique=False,
    )
    op.create_index(
        op.f('ix_location_visits_location_key'),
        'location_visits',
        ['location_key'],
        unique=False,
    )


def downgrade() -> None:
    """Drop location_visits table."""
    op.drop_index(op.f('ix_location_visits_location_key'), table_name='location_visits')
    op.drop_index(op.f('ix_location_visits_session_id'), table_name='location_visits')
    op.drop_index(op.f('ix_location_visits_id'), table_name='location_visits')
    op.drop_table('location_visits')
