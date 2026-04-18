"""Add device and email to users

Revision ID: 5e7a9c2b1d3f
Revises: 032f2bef8d8d
Create Date: 2026-04-18 12:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "5e7a9c2b1d3f"
down_revision: Union[str, None] = "032f2bef8d8d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.add_column(sa.Column("device", sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column("email", sa.String(length=255), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("users", schema=None) as batch_op:
        batch_op.drop_column("email")
        batch_op.drop_column("device")
