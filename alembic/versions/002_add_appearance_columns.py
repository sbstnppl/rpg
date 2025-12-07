"""Add appearance columns to entities.

Revision ID: 002_appearance
Revises: 001_realism
Create Date: 2024-12-07

This migration adds dedicated appearance columns to the entities table
for better queryability and media generation support. The columns are
synced to the existing JSON appearance field for flexibility.
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "002_appearance"
down_revision = "001_realism"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Demographics
    op.add_column("entities", sa.Column("age", sa.Integer(), nullable=True, comment="Numeric age in years"))
    op.add_column("entities", sa.Column("age_apparent", sa.String(50), nullable=True, comment="Apparent age description (e.g., 'early 20s', 'elderly')"))
    op.add_column("entities", sa.Column("gender", sa.String(50), nullable=True, comment="Gender identity (free-text for inclusivity)"))

    # Physical (Essential for image generation)
    op.add_column("entities", sa.Column("height", sa.String(50), nullable=True, comment="Height (e.g., '5\\'10\"', 'tall', 'short')"))
    op.add_column("entities", sa.Column("build", sa.String(50), nullable=True, comment="Body build (e.g., 'athletic', 'slim', 'stocky')"))
    op.add_column("entities", sa.Column("hair_color", sa.String(50), nullable=True, comment="Hair color (e.g., 'blonde', 'dark brown')"))
    op.add_column("entities", sa.Column("hair_style", sa.String(100), nullable=True, comment="Hair style (e.g., 'long wavy', 'buzz cut', 'ponytail')"))
    op.add_column("entities", sa.Column("eye_color", sa.String(50), nullable=True, comment="Eye color (e.g., 'blue', 'brown', 'heterochromatic')"))
    op.add_column("entities", sa.Column("skin_tone", sa.String(50), nullable=True, comment="Skin tone (e.g., 'fair', 'tan', 'dark', 'olive')"))

    # Species (for fantasy/sci-fi settings)
    op.add_column("entities", sa.Column("species", sa.String(50), nullable=True, comment="Species/race (e.g., 'human', 'half-elf', 'android')"))

    # Detailed features
    op.add_column("entities", sa.Column("distinguishing_features", sa.Text(), nullable=True, comment="Notable features (scars, tattoos, birthmarks, etc.)"))
    op.add_column("entities", sa.Column("voice_description", sa.Text(), nullable=True, comment="Voice characteristics (e.g., 'deep and gravelly', 'melodic')"))


def downgrade() -> None:
    op.drop_column("entities", "voice_description")
    op.drop_column("entities", "distinguishing_features")
    op.drop_column("entities", "species")
    op.drop_column("entities", "skin_tone")
    op.drop_column("entities", "eye_color")
    op.drop_column("entities", "hair_style")
    op.drop_column("entities", "hair_color")
    op.drop_column("entities", "build")
    op.drop_column("entities", "height")
    op.drop_column("entities", "gender")
    op.drop_column("entities", "age_apparent")
    op.drop_column("entities", "age")
