"""Normalize need semantics: fatigue→energy, pain→wellness, invert values.

Revision ID: 004_normalize_needs
Revises: 003_preferences
Create Date: 2024-12-07

This migration:
- Renames 'fatigue' column to 'energy' and inverts values (100 - old)
- Renames 'pain' column to 'wellness' and inverts values (100 - old)
- Inverts 'intimacy' values (100 - old)

After this migration, ALL needs follow consistent semantics:
- 0 = action required (bad state, red)
- 100 = no action needed (good state, green)
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "004_normalize_needs"
down_revision = "543ae419033d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: Add new columns with correct names
    op.add_column(
        "character_needs",
        sa.Column("energy", sa.Integer(), nullable=True),
    )
    op.add_column(
        "character_needs",
        sa.Column("wellness", sa.Integer(), nullable=True),
    )

    # Step 2: Migrate data with value inversion (100 - old_value)
    op.execute(
        """
        UPDATE character_needs
        SET energy = 100 - fatigue,
            wellness = 100 - pain,
            intimacy = 100 - intimacy
        """
    )

    # Step 3: Set NOT NULL constraints and defaults
    op.alter_column(
        "character_needs",
        "energy",
        existing_type=sa.Integer(),
        nullable=False,
        server_default="80",
    )
    op.alter_column(
        "character_needs",
        "wellness",
        existing_type=sa.Integer(),
        nullable=False,
        server_default="100",
    )

    # Step 4: Drop old columns
    op.drop_column("character_needs", "fatigue")
    op.drop_column("character_needs", "pain")


def downgrade() -> None:
    # Step 1: Add back old columns
    op.add_column(
        "character_needs",
        sa.Column("fatigue", sa.Integer(), nullable=True),
    )
    op.add_column(
        "character_needs",
        sa.Column("pain", sa.Integer(), nullable=True),
    )

    # Step 2: Migrate data back with value inversion
    op.execute(
        """
        UPDATE character_needs
        SET fatigue = 100 - energy,
            pain = 100 - wellness,
            intimacy = 100 - intimacy
        """
    )

    # Step 3: Set NOT NULL constraints and defaults
    op.alter_column(
        "character_needs",
        "fatigue",
        existing_type=sa.Integer(),
        nullable=False,
        server_default="20",
    )
    op.alter_column(
        "character_needs",
        "pain",
        existing_type=sa.Integer(),
        nullable=False,
        server_default="0",
    )

    # Step 4: Drop new columns
    op.drop_column("character_needs", "energy")
    op.drop_column("character_needs", "wellness")
