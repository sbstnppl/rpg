"""Add NPC goals table for autonomous behavior.

Revision ID: 011_add_npc_goals
Revises: 010_add_companion_tracking
Create Date: 2024-12-10

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "011_add_npc_goals"
down_revision: Union[str, None] = "010_add_companion_tracking"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create npc_goals table."""
    # Create enums first using raw SQL for better control
    conn = op.get_bind()

    # Create goal type enum
    conn.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE goaltype AS ENUM (
                'acquire', 'meet_person', 'go_to', 'learn_info', 'avoid',
                'protect', 'earn_money', 'romance', 'social', 'revenge',
                'survive', 'duty', 'craft', 'heal'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """))

    # Create goal priority enum
    conn.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE goalpriority AS ENUM (
                'background', 'low', 'medium', 'high', 'urgent'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """))

    # Create goal status enum
    conn.execute(sa.text("""
        DO $$ BEGIN
            CREATE TYPE goalstatus AS ENUM (
                'active', 'completed', 'failed', 'abandoned', 'blocked'
            );
        EXCEPTION
            WHEN duplicate_object THEN null;
        END $$;
    """))

    # Create npc_goals table using raw column types
    op.create_table(
        "npc_goals",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=False),
        sa.Column(
            "goal_key",
            sa.String(100),
            nullable=False,
            comment="Unique goal identifier within session",
        ),
        sa.Column(
            "goal_type",
            postgresql.ENUM("acquire", "meet_person", "go_to", "learn_info", "avoid",
                          "protect", "earn_money", "romance", "social", "revenge",
                          "survive", "duty", "craft", "heal",
                          name="goaltype", create_type=False),
            nullable=False,
            comment="Category of goal",
        ),
        sa.Column(
            "target",
            sa.String(200),
            nullable=False,
            comment="Target: entity_key, location_key, item_key, or description",
        ),
        sa.Column(
            "description",
            sa.Text(),
            nullable=False,
            comment="Human-readable goal description",
        ),
        sa.Column(
            "motivation",
            sa.JSON(),
            nullable=False,
            comment="Reasons driving this goal",
        ),
        sa.Column(
            "triggered_by",
            sa.String(200),
            nullable=True,
            comment="Event or turn that created this goal",
        ),
        sa.Column(
            "priority",
            postgresql.ENUM("background", "low", "medium", "high", "urgent",
                          name="goalpriority", create_type=False),
            nullable=False,
            comment="Goal priority level",
        ),
        sa.Column(
            "deadline",
            sa.DateTime(),
            nullable=True,
            comment="Game time deadline for this goal",
        ),
        sa.Column(
            "deadline_description",
            sa.String(100),
            nullable=True,
            comment="Human-readable deadline description",
        ),
        sa.Column(
            "strategies",
            sa.JSON(),
            nullable=False,
            comment="Ordered steps to achieve the goal",
        ),
        sa.Column(
            "current_step",
            sa.Integer(),
            nullable=False,
            server_default="0",
            comment="Index of current strategy step",
        ),
        sa.Column(
            "blocked_reason",
            sa.Text(),
            nullable=True,
            comment="Why the NPC cannot proceed (if blocked)",
        ),
        sa.Column(
            "success_condition",
            sa.Text(),
            nullable=False,
            comment="What must happen for goal completion",
        ),
        sa.Column(
            "failure_condition",
            sa.Text(),
            nullable=True,
            comment="What would cause goal failure",
        ),
        sa.Column(
            "status",
            postgresql.ENUM("active", "completed", "failed", "abandoned", "blocked",
                          name="goalstatus", create_type=False),
            nullable=False,
            comment="Current goal status",
        ),
        sa.Column(
            "outcome",
            sa.Text(),
            nullable=True,
            comment="Description of outcome when completed/failed",
        ),
        sa.Column(
            "created_at_turn",
            sa.Integer(),
            nullable=False,
            comment="Turn number when goal was created",
        ),
        sa.Column(
            "completed_at_turn",
            sa.Integer(),
            nullable=True,
            comment="Turn number when goal was completed",
        ),
        sa.Column(
            "last_processed_turn",
            sa.Integer(),
            nullable=True,
            comment="Last turn this goal was processed by World Simulator",
        ),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["game_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["entity_id"],
            ["entities.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("session_id", "goal_key", name="uq_goal_session_key"),
    )

    # Create indexes
    op.create_index("ix_npc_goals_id", "npc_goals", ["id"])
    op.create_index("ix_npc_goals_session_id", "npc_goals", ["session_id"])
    op.create_index("ix_npc_goals_entity_id", "npc_goals", ["entity_id"])
    op.create_index("ix_npc_goals_goal_key", "npc_goals", ["goal_key"])
    op.create_index("ix_npc_goals_goal_type", "npc_goals", ["goal_type"])
    op.create_index("ix_npc_goals_priority", "npc_goals", ["priority"])
    op.create_index("ix_npc_goals_status", "npc_goals", ["status"])


def downgrade() -> None:
    """Drop npc_goals table and enums."""
    # Drop indexes
    op.drop_index("ix_npc_goals_status", table_name="npc_goals")
    op.drop_index("ix_npc_goals_priority", table_name="npc_goals")
    op.drop_index("ix_npc_goals_goal_type", table_name="npc_goals")
    op.drop_index("ix_npc_goals_goal_key", table_name="npc_goals")
    op.drop_index("ix_npc_goals_entity_id", table_name="npc_goals")
    op.drop_index("ix_npc_goals_session_id", table_name="npc_goals")
    op.drop_index("ix_npc_goals_id", table_name="npc_goals")

    # Drop table
    op.drop_table("npc_goals")

    # Drop enums
    conn = op.get_bind()
    conn.execute(sa.text("DROP TYPE IF EXISTS goalstatus"))
    conn.execute(sa.text("DROP TYPE IF EXISTS goalpriority"))
    conn.execute(sa.text("DROP TYPE IF EXISTS goaltype"))
