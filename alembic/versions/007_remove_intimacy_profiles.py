"""Remove deprecated intimacy_profiles table.

Revision ID: 007_remove_intimacy_profiles
Revises: 006_potential_stats
Create Date: 2024-12-09

The IntimacyProfile table has been superseded by CharacterPreferences,
which consolidates all character preferences (intimacy, food, drink,
social, stamina) into a single table. This migration drops the now-
unused intimacy_profiles table.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "007_remove_intimacy_profiles"
down_revision = "006_potential_stats"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("intimacy_profiles")


def downgrade() -> None:
    # Recreate the intimacy_profiles table for rollback
    op.create_table(
        "intimacy_profiles",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column(
            "drive_level",
            sa.Enum(
                "asexual", "very_low", "low", "moderate", "high", "very_high",
                name="drivelevel"
            ),
            nullable=False,
        ),
        sa.Column("drive_threshold", sa.Integer(), nullable=False),
        sa.Column(
            "intimacy_style",
            sa.Enum(
                "casual", "emotional", "monogamous", "polyamorous",
                name="intimacystyle"
            ),
            nullable=False,
        ),
        sa.Column("attraction_preferences", postgresql.JSON(), nullable=True),
        sa.Column("has_regular_partner", sa.Boolean(), nullable=False),
        sa.Column("is_actively_seeking", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["entity_id"], ["entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["session_id"], ["game_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_intimacy_profiles_entity_id", "intimacy_profiles", ["entity_id"], unique=True
    )
    op.create_index(
        "ix_intimacy_profiles_session_id", "intimacy_profiles", ["session_id"], unique=False
    )
    op.create_index(
        "ix_intimacy_profiles_id", "intimacy_profiles", ["id"], unique=False
    )
