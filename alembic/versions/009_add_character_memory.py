"""Add character_memories table for emotional reactions.

Revision ID: 009_add_character_memory
Revises: 008_add_thirst_and_cravings
Create Date: 2024-12-09

This migration adds the character_memories table for storing significant
memories that can trigger emotional reactions to scene elements:
- Extracted from backstory during character creation
- Created during gameplay when significant events occur
- Used by SceneInterpreter to detect memory triggers
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "009_add_character_memory"
down_revision = "008_add_thirst_and_cravings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create MemoryType enum
    memory_type_enum = postgresql.ENUM(
        "person",
        "item",
        "place",
        "event",
        "creature",
        "concept",
        name="memorytype",
        create_type=False,
    )
    memory_type_enum.create(op.get_bind(), checkfirst=True)

    # Create EmotionalValence enum
    emotional_valence_enum = postgresql.ENUM(
        "positive",
        "negative",
        "mixed",
        "neutral",
        name="emotionalvalence",
        create_type=False,
    )
    emotional_valence_enum.create(op.get_bind(), checkfirst=True)

    # Create character_memories table
    op.create_table(
        "character_memories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        # What is remembered
        sa.Column(
            "subject",
            sa.String(200),
            nullable=False,
            comment="What is remembered: 'mother's hat', 'red chicken', 'house fire'",
        ),
        sa.Column(
            "subject_type",
            sa.Enum(
                "person",
                "item",
                "place",
                "event",
                "creature",
                "concept",
                name="memorytype",
            ),
            nullable=False,
            comment="Type of memory subject",
        ),
        sa.Column(
            "keywords",
            postgresql.JSON(),
            nullable=False,
            server_default="[]",
            comment="Keywords for matching: ['hat', 'wide-brimmed', 'straw']",
        ),
        # Emotional context
        sa.Column(
            "valence",
            sa.Enum(
                "positive",
                "negative",
                "mixed",
                "neutral",
                name="emotionalvalence",
            ),
            nullable=False,
            comment="Emotional direction: positive, negative, mixed, neutral",
        ),
        sa.Column(
            "emotion",
            sa.String(50),
            nullable=False,
            comment="Primary emotion: 'grief', 'joy', 'fear', 'curiosity', 'nostalgia'",
        ),
        sa.Column(
            "context",
            sa.Text(),
            nullable=False,
            comment="Why this is meaningful",
        ),
        # Source and strength
        sa.Column(
            "source",
            sa.String(50),
            nullable=False,
            server_default="backstory",
            comment="Where memory came from: 'backstory', 'gameplay', 'relationship'",
        ),
        sa.Column(
            "intensity",
            sa.Integer(),
            nullable=False,
            server_default="5",
            comment="How strongly this affects character (1-10)",
        ),
        # Tracking
        sa.Column(
            "created_turn",
            sa.Integer(),
            nullable=True,
            comment="Turn number when memory was created (null for backstory)",
        ),
        sa.Column(
            "last_triggered_turn",
            sa.Integer(),
            nullable=True,
            comment="Turn number when memory was last activated",
        ),
        sa.Column(
            "trigger_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="How many times this memory has been triggered",
        ),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # Constraints
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["entities.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["game_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )

    # Create indexes
    op.create_index(
        "ix_character_memories_id",
        "character_memories",
        ["id"],
        unique=False,
    )
    op.create_index(
        "ix_character_memories_entity_id",
        "character_memories",
        ["entity_id"],
        unique=False,
    )
    op.create_index(
        "ix_character_memories_session_id",
        "character_memories",
        ["session_id"],
        unique=False,
    )

    # Remove server defaults after table creation (cleaner schema)
    op.alter_column("character_memories", "keywords", server_default=None)
    op.alter_column("character_memories", "source", server_default=None)
    op.alter_column("character_memories", "intensity", server_default=None)
    op.alter_column("character_memories", "trigger_count", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_character_memories_session_id", table_name="character_memories")
    op.drop_index("ix_character_memories_entity_id", table_name="character_memories")
    op.drop_index("ix_character_memories_id", table_name="character_memories")
    op.drop_table("character_memories")

    # Drop enums
    op.execute("DROP TYPE IF EXISTS emotionalvalence")
    op.execute("DROP TYPE IF EXISTS memorytype")
