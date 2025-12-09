"""Add companion tracking fields to NPCExtension.

Revision ID: 010_add_companion_tracking
Revises: 009_add_character_memory
Create Date: 2025-01-01
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "010_add_companion_tracking"
down_revision = "009_add_character_memory"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add companion tracking columns to npc_extensions."""
    op.add_column(
        "npc_extensions",
        sa.Column(
            "is_companion",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
            comment="Whether NPC is currently traveling with player (needs decay tracked)",
        ),
    )
    op.add_column(
        "npc_extensions",
        sa.Column(
            "companion_since_turn",
            sa.Integer(),
            nullable=True,
            comment="Turn when NPC joined as companion",
        ),
    )


def downgrade() -> None:
    """Remove companion tracking columns."""
    op.drop_column("npc_extensions", "companion_since_turn")
    op.drop_column("npc_extensions", "is_companion")
