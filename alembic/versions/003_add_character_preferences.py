"""Add character preferences and need modifiers system.

Revision ID: 003_preferences
Revises: 002_appearance
Create Date: 2024-12-07

This migration creates:
- character_preferences: Consolidated preferences table (food, drink, intimacy, social)
- need_modifiers: Per-entity modifiers for need decay rates
- need_adaptations: History of need baseline changes from experience

The IntimacyProfile table is kept for now; data migration will be handled
separately when the new system is fully tested.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "003_preferences"
down_revision = "002_appearance"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # === CHARACTER PREFERENCES TABLE ===
    op.create_table(
        "character_preferences",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "entity_id",
            sa.Integer(),
            sa.ForeignKey("entities.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
            index=True,
        ),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("game_sessions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        # Food preferences
        sa.Column("favorite_foods", sa.JSON(), nullable=True),
        sa.Column("disliked_foods", sa.JSON(), nullable=True),
        sa.Column("is_vegetarian", sa.Boolean(), nullable=False, default=False),
        sa.Column("is_vegan", sa.Boolean(), nullable=False, default=False),
        sa.Column("food_allergies", sa.JSON(), nullable=True),
        sa.Column("is_greedy_eater", sa.Boolean(), nullable=False, default=False),
        sa.Column("is_picky_eater", sa.Boolean(), nullable=False, default=False),
        # Drink preferences
        sa.Column("favorite_drinks", sa.JSON(), nullable=True),
        sa.Column("disliked_drinks", sa.JSON(), nullable=True),
        sa.Column(
            "alcohol_tolerance",
            sa.String(20),
            nullable=False,
            default="moderate",
        ),
        sa.Column("is_alcoholic", sa.Boolean(), nullable=False, default=False),
        sa.Column("is_teetotaler", sa.Boolean(), nullable=False, default=False),
        # Intimacy preferences (migrated from IntimacyProfile)
        sa.Column("drive_level", sa.String(20), nullable=False, default="moderate"),
        sa.Column("drive_threshold", sa.Integer(), nullable=False, default=50),
        sa.Column("intimacy_style", sa.String(20), nullable=False, default="emotional"),
        sa.Column("attraction_preferences", sa.JSON(), nullable=True),
        sa.Column("has_regular_partner", sa.Boolean(), nullable=False, default=False),
        sa.Column("is_actively_seeking", sa.Boolean(), nullable=False, default=False),
        # Social preferences
        sa.Column("social_tendency", sa.String(20), nullable=False, default="ambivert"),
        sa.Column("preferred_group_size", sa.Integer(), nullable=False, default=3),
        sa.Column("is_social_butterfly", sa.Boolean(), nullable=False, default=False),
        sa.Column("is_loner", sa.Boolean(), nullable=False, default=False),
        # Stamina traits
        sa.Column("has_high_stamina", sa.Boolean(), nullable=False, default=False),
        sa.Column("has_low_stamina", sa.Boolean(), nullable=False, default=False),
        sa.Column("is_insomniac", sa.Boolean(), nullable=False, default=False),
        sa.Column("is_heavy_sleeper", sa.Boolean(), nullable=False, default=False),
        # Extra preferences
        sa.Column("extra_preferences", sa.JSON(), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )

    # === NEED MODIFIERS TABLE ===
    op.create_table(
        "need_modifiers",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "entity_id",
            sa.Integer(),
            sa.ForeignKey("entities.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("game_sessions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("need_name", sa.String(50), nullable=False, index=True),
        sa.Column("modifier_source", sa.String(20), nullable=False),
        sa.Column("source_detail", sa.String(100), nullable=True),
        sa.Column("decay_rate_multiplier", sa.Float(), nullable=False, default=1.0),
        sa.Column("satisfaction_multiplier", sa.Float(), nullable=False, default=1.0),
        sa.Column("max_intensity_cap", sa.Integer(), nullable=True),
        sa.Column("threshold_adjustment", sa.Integer(), nullable=False, default=0),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        sa.Column("expires_at_turn", sa.Integer(), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        # Unique constraint
        sa.UniqueConstraint(
            "entity_id", "need_name", "modifier_source", "source_detail",
            name="uq_need_modifier"
        ),
    )

    # === NEED ADAPTATIONS TABLE ===
    op.create_table(
        "need_adaptations",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column(
            "entity_id",
            sa.Integer(),
            sa.ForeignKey("entities.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "session_id",
            sa.Integer(),
            sa.ForeignKey("game_sessions.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("need_name", sa.String(50), nullable=False, index=True),
        sa.Column("adaptation_delta", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("trigger_event", sa.String(200), nullable=True),
        sa.Column("started_turn", sa.Integer(), nullable=False, index=True),
        sa.Column("completed_turn", sa.Integer(), nullable=True),
        sa.Column("is_gradual", sa.Boolean(), nullable=False, default=True),
        sa.Column("duration_days", sa.Integer(), nullable=True),
        sa.Column("is_reversible", sa.Boolean(), nullable=False, default=True),
        sa.Column("reversal_trigger", sa.Text(), nullable=True),
        # Timestamps
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("need_adaptations")
    op.drop_table("need_modifiers")
    op.drop_table("character_preferences")
