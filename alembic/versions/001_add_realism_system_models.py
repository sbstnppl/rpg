"""Add realism system models.

Revision ID: 001_realism
Revises:
Create Date: 2024-12-06

This migration adds:
- New tables: character_needs, intimacy_profiles, body_injuries,
  activity_restrictions, entity_vital_states, mental_conditions, grief_conditions
- New columns to relationships: familiarity, fear, social_debt
- New column to npc_extensions: personality_traits
- New columns to locations: canonical_description, first_visited_turn, state_history, spatial_layout
- New columns to facts: is_foreshadowing, foreshadow_target, times_mentioned
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "001_realism"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # === NEW TABLES ===

    # Character Needs
    op.create_table(
        "character_needs",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("entity_id", sa.Integer(), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, unique=True, index=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("game_sessions.id", ondelete="CASCADE"), nullable=False, index=True),
        # Tier 1: Survival
        sa.Column("hunger", sa.Integer(), nullable=False, default=50, comment="0=starving, 50=satisfied, 100=stuffed"),
        sa.Column("fatigue", sa.Integer(), nullable=False, default=20, comment="0=rested, 100=exhausted"),
        # Tier 2: Comfort
        sa.Column("hygiene", sa.Integer(), nullable=False, default=80),
        sa.Column("comfort", sa.Integer(), nullable=False, default=70),
        sa.Column("pain", sa.Integer(), nullable=False, default=0),
        # Tier 3: Psychological
        sa.Column("social_connection", sa.Integer(), nullable=False, default=60),
        sa.Column("morale", sa.Integer(), nullable=False, default=70),
        sa.Column("sense_of_purpose", sa.Integer(), nullable=False, default=50),
        sa.Column("intimacy", sa.Integer(), nullable=False, default=30),
        # Timestamps
        sa.Column("last_updated", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("last_meal_turn", sa.Integer(), nullable=True),
        sa.Column("last_sleep_turn", sa.Integer(), nullable=True),
        sa.Column("last_bath_turn", sa.Integer(), nullable=True),
        sa.Column("last_social_turn", sa.Integer(), nullable=True),
        sa.Column("last_intimate_turn", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Intimacy Profiles
    op.create_table(
        "intimacy_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("entity_id", sa.Integer(), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, unique=True, index=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("game_sessions.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("drive_level", sa.String(20), nullable=False, default="moderate"),
        sa.Column("drive_threshold", sa.Integer(), nullable=False, default=50),
        sa.Column("intimacy_style", sa.String(20), nullable=False, default="emotional"),
        sa.Column("attraction_preferences", postgresql.JSON(), nullable=True),
        sa.Column("has_regular_partner", sa.Boolean(), nullable=False, default=False),
        sa.Column("is_actively_seeking", sa.Boolean(), nullable=False, default=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Body Injuries
    op.create_table(
        "body_injuries",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("entity_id", sa.Integer(), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("game_sessions.id", ondelete="CASCADE"), nullable=False, index=True),
        # Injury details
        sa.Column("body_part", sa.String(30), nullable=False),
        sa.Column("injury_type", sa.String(30), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("caused_by", sa.Text(), nullable=False),
        sa.Column("occurred_turn", sa.Integer(), nullable=False, index=True),
        sa.Column("occurred_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        # Medical care
        sa.Column("received_medical_care", sa.Boolean(), nullable=False, default=False),
        sa.Column("medical_care_quality", sa.Integer(), nullable=True),
        sa.Column("medical_care_turn", sa.Integer(), nullable=True),
        # Recovery
        sa.Column("base_recovery_days", sa.Integer(), nullable=False),
        sa.Column("adjusted_recovery_days", sa.Float(), nullable=False),
        sa.Column("recovery_progress_days", sa.Float(), nullable=False, default=0.0),
        sa.Column("is_healed", sa.Boolean(), nullable=False, default=False),
        sa.Column("healed_at", sa.DateTime(), nullable=True),
        sa.Column("healed_turn", sa.Integer(), nullable=True),
        # Complications
        sa.Column("is_infected", sa.Boolean(), nullable=False, default=False),
        sa.Column("is_reinjured", sa.Boolean(), nullable=False, default=False),
        sa.Column("has_permanent_damage", sa.Boolean(), nullable=False, default=False),
        sa.Column("permanent_damage_description", sa.Text(), nullable=True),
        sa.Column("current_pain_level", sa.Integer(), nullable=False, default=0),
        sa.Column("activity_restrictions", postgresql.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Activity Restrictions (lookup table)
    op.create_table(
        "activity_restrictions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("body_part", sa.String(30), nullable=False),
        sa.Column("injury_type", sa.String(30), nullable=False),
        sa.Column("severity", sa.String(20), nullable=False),
        sa.Column("activity_name", sa.String(100), nullable=False, index=True),
        sa.Column("impact_type", sa.String(20), nullable=False),
        sa.Column("impact_value", sa.Integer(), nullable=True),
        sa.Column("requirement", sa.String(100), nullable=True),
    )

    # Entity Vital States
    op.create_table(
        "entity_vital_states",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("entity_id", sa.Integer(), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, unique=True, index=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("game_sessions.id", ondelete="CASCADE"), nullable=False, index=True),
        # Vital status
        sa.Column("vital_status", sa.String(20), nullable=False, default="healthy"),
        sa.Column("death_saves_remaining", sa.Integer(), nullable=False, default=3),
        sa.Column("death_saves_failed", sa.Integer(), nullable=False, default=0),
        sa.Column("stabilized_at", sa.DateTime(), nullable=True),
        sa.Column("stabilized_turn", sa.Integer(), nullable=True),
        # Death record
        sa.Column("is_dead", sa.Boolean(), nullable=False, default=False),
        sa.Column("death_timestamp", sa.DateTime(), nullable=True),
        sa.Column("death_turn", sa.Integer(), nullable=True),
        sa.Column("death_cause", sa.String(200), nullable=True),
        sa.Column("death_description", sa.Text(), nullable=True),
        sa.Column("death_location", sa.String(100), nullable=True),
        # Revival
        sa.Column("has_been_revived", sa.Boolean(), nullable=False, default=False),
        sa.Column("revival_count", sa.Integer(), nullable=False, default=0),
        sa.Column("last_revival_turn", sa.Integer(), nullable=True),
        sa.Column("revival_method", sa.String(100), nullable=True),
        sa.Column("revival_cost", sa.Text(), nullable=True),
        # Sci-fi backup
        sa.Column("has_consciousness_backup", sa.Boolean(), nullable=False, default=False),
        sa.Column("last_backup_turn", sa.Integer(), nullable=True),
        sa.Column("backup_location", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Mental Conditions
    op.create_table(
        "mental_conditions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("entity_id", sa.Integer(), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("game_sessions.id", ondelete="CASCADE"), nullable=False, index=True),
        # Condition
        sa.Column("condition_type", sa.String(50), nullable=False),
        sa.Column("severity", sa.Integer(), nullable=False, default=50),
        sa.Column("is_permanent", sa.Boolean(), nullable=False, default=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, default=True),
        # Triggers
        sa.Column("trigger_description", sa.Text(), nullable=True),
        sa.Column("triggers", postgresql.JSON(), nullable=True),
        # Effects
        sa.Column("stat_penalties", postgresql.JSON(), nullable=True),
        sa.Column("behavioral_effects", postgresql.JSON(), nullable=True),
        # Lifecycle
        sa.Column("acquired_turn", sa.Integer(), nullable=False, index=True),
        sa.Column("acquired_reason", sa.Text(), nullable=False),
        sa.Column("acquired_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        # Treatment
        sa.Column("can_be_treated", sa.Boolean(), nullable=False, default=True),
        sa.Column("treatment_progress", sa.Integer(), nullable=False, default=0),
        sa.Column("treatment_notes", sa.Text(), nullable=True),
        # Resolution
        sa.Column("resolved_turn", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Grief Conditions
    op.create_table(
        "grief_conditions",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("entity_id", sa.Integer(), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("deceased_entity_id", sa.Integer(), sa.ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("session_id", sa.Integer(), sa.ForeignKey("game_sessions.id", ondelete="CASCADE"), nullable=False, index=True),
        # Grief stage
        sa.Column("grief_stage", sa.String(20), nullable=False, default="shock"),
        sa.Column("intensity", sa.Integer(), nullable=False, default=50),
        # Timeline
        sa.Column("started_turn", sa.Integer(), nullable=False, index=True),
        sa.Column("started_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("current_stage_started_turn", sa.Integer(), nullable=False),
        sa.Column("expected_duration_days", sa.Integer(), nullable=False),
        # Effects
        sa.Column("morale_modifier", sa.Integer(), nullable=False, default=-20),
        sa.Column("behavioral_changes", postgresql.JSON(), nullable=True),
        # Blame
        sa.Column("blames_someone", sa.Boolean(), nullable=False, default=False),
        sa.Column("blamed_entity_key", sa.String(100), nullable=True),
        # Resolution
        sa.Column("is_resolved", sa.Boolean(), nullable=False, default=False),
        sa.Column("resolved_turn", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # === MODIFY EXISTING TABLES ===

    # Add columns to relationships
    op.add_column("relationships", sa.Column("familiarity", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("relationships", sa.Column("fear", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("relationships", sa.Column("social_debt", sa.Integer(), nullable=False, server_default="0"))

    # Add column to npc_extensions
    op.add_column("npc_extensions", sa.Column("personality_traits", postgresql.JSON(), nullable=True))

    # Add columns to locations
    op.add_column("locations", sa.Column("canonical_description", sa.Text(), nullable=True))
    op.add_column("locations", sa.Column("first_visited_turn", sa.Integer(), nullable=True))
    op.add_column("locations", sa.Column("state_history", postgresql.JSON(), nullable=True))
    op.add_column("locations", sa.Column("spatial_layout", postgresql.JSON(), nullable=True))

    # Add columns to facts
    op.add_column("facts", sa.Column("is_foreshadowing", sa.Boolean(), nullable=False, server_default="false"))
    op.add_column("facts", sa.Column("foreshadow_target", sa.String(200), nullable=True))
    op.add_column("facts", sa.Column("times_mentioned", sa.Integer(), nullable=False, server_default="1"))


def downgrade() -> None:
    # Remove columns from facts
    op.drop_column("facts", "times_mentioned")
    op.drop_column("facts", "foreshadow_target")
    op.drop_column("facts", "is_foreshadowing")

    # Remove columns from locations
    op.drop_column("locations", "spatial_layout")
    op.drop_column("locations", "state_history")
    op.drop_column("locations", "first_visited_turn")
    op.drop_column("locations", "canonical_description")

    # Remove column from npc_extensions
    op.drop_column("npc_extensions", "personality_traits")

    # Remove columns from relationships
    op.drop_column("relationships", "social_debt")
    op.drop_column("relationships", "fear")
    op.drop_column("relationships", "familiarity")

    # Drop new tables
    op.drop_table("grief_conditions")
    op.drop_table("mental_conditions")
    op.drop_table("entity_vital_states")
    op.drop_table("activity_restrictions")
    op.drop_table("body_injuries")
    op.drop_table("intimacy_profiles")
    op.drop_table("character_needs")
