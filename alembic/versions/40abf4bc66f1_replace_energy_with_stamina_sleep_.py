"""replace_energy_with_stamina_sleep_pressure

Revision ID: 40abf4bc66f1
Revises: 8c46f05ac0b1
Create Date: 2025-12-20 08:26:57.215482

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '40abf4bc66f1'
down_revision: Union[str, None] = '8c46f05ac0b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new stamina and sleep_pressure columns
    op.add_column(
        'character_needs',
        sa.Column(
            'stamina',
            sa.Integer(),
            nullable=False,
            server_default='80',
            comment='0=collapsed, 50=fatigued, 100=fresh. Physical capacity.',
        )
    )
    op.add_column(
        'character_needs',
        sa.Column(
            'sleep_pressure',
            sa.Integer(),
            nullable=False,
            server_default='0',
            comment='0=well-rested, 50=tired, 100=desperately sleepy. Homeostatic sleep debt.',
        )
    )

    # Migrate data: stamina = old energy, sleep_pressure = 100 - old energy
    op.execute("""
        UPDATE character_needs
        SET stamina = energy,
            sleep_pressure = GREATEST(0, 100 - energy)
    """)

    # Remove server defaults (not needed after migration)
    op.alter_column('character_needs', 'stamina', server_default=None)
    op.alter_column('character_needs', 'sleep_pressure', server_default=None)

    # Drop old energy and energy_craving columns
    op.drop_column('character_needs', 'energy')
    op.drop_column('character_needs', 'energy_craving')


def downgrade() -> None:
    # Add back energy and energy_craving columns
    op.add_column(
        'character_needs',
        sa.Column(
            'energy',
            sa.Integer(),
            nullable=False,
            server_default='80',
            comment='0=exhausted, 50=tired, 100=energized. Optimal: 60-100',
        )
    )
    op.add_column(
        'character_needs',
        sa.Column(
            'energy_craving',
            sa.Integer(),
            nullable=False,
            server_default='0',
            comment='Temporary fatigue urgency boost from stimuli (0-100)',
        )
    )

    # Migrate data back: energy = stamina (approximate, loses sleep_pressure info)
    op.execute("""
        UPDATE character_needs
        SET energy = stamina
    """)

    # Remove server defaults
    op.alter_column('character_needs', 'energy', server_default=None)
    op.alter_column('character_needs', 'energy_craving', server_default=None)

    # Drop new columns
    op.drop_column('character_needs', 'stamina')
    op.drop_column('character_needs', 'sleep_pressure')
