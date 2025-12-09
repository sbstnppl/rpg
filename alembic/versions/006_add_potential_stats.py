"""Add potential stats and occupation to entities.

Revision ID: 006_potential_stats
Revises: 005_navigation
Create Date: 2024-12-09

This migration adds hidden potential stat columns to the entities table
for the two-tier attribute system. Potential stats are rolled randomly
during character creation and used to calculate current stats along with
age and occupation modifiers.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "006_potential_stats"
down_revision = "005_navigation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Hidden potential stats (rolled randomly, never shown to player)
    op.add_column(
        "entities",
        sa.Column(
            "potential_strength",
            sa.Integer(),
            nullable=True,
            comment="Innate strength potential (hidden from player)",
        ),
    )
    op.add_column(
        "entities",
        sa.Column(
            "potential_dexterity",
            sa.Integer(),
            nullable=True,
            comment="Innate dexterity potential (hidden from player)",
        ),
    )
    op.add_column(
        "entities",
        sa.Column(
            "potential_constitution",
            sa.Integer(),
            nullable=True,
            comment="Innate constitution potential (hidden from player)",
        ),
    )
    op.add_column(
        "entities",
        sa.Column(
            "potential_intelligence",
            sa.Integer(),
            nullable=True,
            comment="Innate intelligence potential (hidden from player)",
        ),
    )
    op.add_column(
        "entities",
        sa.Column(
            "potential_wisdom",
            sa.Integer(),
            nullable=True,
            comment="Innate wisdom potential (hidden from player)",
        ),
    )
    op.add_column(
        "entities",
        sa.Column(
            "potential_charisma",
            sa.Integer(),
            nullable=True,
            comment="Innate charisma potential (hidden from player)",
        ),
    )

    # Occupation data for attribute calculation
    op.add_column(
        "entities",
        sa.Column(
            "occupation",
            sa.String(100),
            nullable=True,
            comment="Primary occupation/profession (e.g., 'blacksmith', 'farmer', 'scholar')",
        ),
    )
    op.add_column(
        "entities",
        sa.Column(
            "occupation_years",
            sa.Integer(),
            nullable=True,
            comment="Years spent in the occupation (affects attribute modifiers)",
        ),
    )


def downgrade() -> None:
    op.drop_column("entities", "occupation_years")
    op.drop_column("entities", "occupation")
    op.drop_column("entities", "potential_charisma")
    op.drop_column("entities", "potential_wisdom")
    op.drop_column("entities", "potential_intelligence")
    op.drop_column("entities", "potential_constitution")
    op.drop_column("entities", "potential_dexterity")
    op.drop_column("entities", "potential_strength")
