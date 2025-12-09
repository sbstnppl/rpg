"""Add thirst need and craving modifiers to character_needs.

Revision ID: 008_add_thirst_and_cravings
Revises: 007_remove_intimacy_profiles
Create Date: 2024-12-09

This migration adds:
1. thirst - New vital need (decays faster than hunger)
2. Craving modifiers - Temporary psychological urgency boosts for:
   - hunger_craving, thirst_craving, energy_craving, social_craving, intimacy_craving
3. last_drink_turn - Tracking field for thirst satisfaction deduplication
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "008_add_thirst_and_cravings"
down_revision = "007_remove_intimacy_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add thirst need (vital, decays faster than hunger)
    op.add_column(
        "character_needs",
        sa.Column(
            "thirst",
            sa.Integer(),
            nullable=False,
            server_default="80",
            comment="0=dehydrated, 50=satisfied, 100=well-hydrated. Optimal: 40-80",
        ),
    )

    # Add craving modifiers (temporary psychological urgency from stimuli)
    op.add_column(
        "character_needs",
        sa.Column(
            "hunger_craving",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Temporary hunger urgency boost from stimuli (0-100)",
        ),
    )
    op.add_column(
        "character_needs",
        sa.Column(
            "thirst_craving",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Temporary thirst urgency boost from stimuli (0-100)",
        ),
    )
    op.add_column(
        "character_needs",
        sa.Column(
            "energy_craving",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Temporary fatigue urgency boost from stimuli (0-100)",
        ),
    )
    op.add_column(
        "character_needs",
        sa.Column(
            "social_craving",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Temporary social urgency boost from stimuli (0-100)",
        ),
    )
    op.add_column(
        "character_needs",
        sa.Column(
            "intimacy_craving",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Temporary intimacy urgency boost from stimuli (0-100)",
        ),
    )

    # Add last_drink_turn for thirst satisfaction tracking
    op.add_column(
        "character_needs",
        sa.Column("last_drink_turn", sa.Integer(), nullable=True),
    )

    # Remove server defaults after data is migrated (cleaner schema)
    op.alter_column("character_needs", "thirst", server_default=None)
    op.alter_column("character_needs", "hunger_craving", server_default=None)
    op.alter_column("character_needs", "thirst_craving", server_default=None)
    op.alter_column("character_needs", "energy_craving", server_default=None)
    op.alter_column("character_needs", "social_craving", server_default=None)
    op.alter_column("character_needs", "intimacy_craving", server_default=None)


def downgrade() -> None:
    op.drop_column("character_needs", "last_drink_turn")
    op.drop_column("character_needs", "intimacy_craving")
    op.drop_column("character_needs", "social_craving")
    op.drop_column("character_needs", "energy_craving")
    op.drop_column("character_needs", "thirst_craving")
    op.drop_column("character_needs", "hunger_craving")
    op.drop_column("character_needs", "thirst")
