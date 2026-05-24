"""add cover_url to user

Revision ID: 9364db12d60f
Revises: 7e232784a7b2
Create Date: 2026-05-24 20:44:51.118740

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '9364db12d60f'
down_revision: Union[str, None] = '7e232784a7b2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('cover_url', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'cover_url')
