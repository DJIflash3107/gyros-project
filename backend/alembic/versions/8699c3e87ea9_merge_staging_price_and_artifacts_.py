"""merge staging price and artifacts branches

Revision ID: 8699c3e87ea9
Revises: a2b3c4d5e6f7, a7b8c9d0e1f2
Create Date: 2026-10-18 11:08:15.633635

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '8699c3e87ea9'
down_revision: Union[str, Sequence[str], None] = ('a2b3c4d5e6f7', 'a7b8c9d0e1f2')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
