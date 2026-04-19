"""merge heads

Revision ID: c1d2e3f4a5b6
Revises: 5e7a9c2b1d3f, b2c3d4e5f6a7
Create Date: 2026-04-19

"""
from typing import Sequence, Union
from alembic import op

revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, Sequence[str], None] = ("5e7a9c2b1d3f", "b2c3d4e5f6a7")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
