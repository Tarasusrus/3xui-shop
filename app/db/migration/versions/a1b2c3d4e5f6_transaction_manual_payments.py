"""transaction manual payments: add expires_at, payment_type, extend status enum

Revision ID: a1b2c3d4e5f6
Revises: 032f2bef8d8d
Create Date: 2026-04-18 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "032f2bef8d8d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    new_enum = sa.Enum(
        "pending", "completed", "canceled", "refunded", "expired", "rejected",
        name="transactionstatus",
    )

    op.create_table(
        "transactions_new",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tg_id", sa.Integer(), nullable=False),
        sa.Column("payment_id", sa.String(length=64), nullable=False),
        sa.Column("subscription", sa.String(length=255), nullable=False),
        sa.Column("status", new_enum, nullable=False),
        sa.Column("payment_type", sa.String(length=32), nullable=True),
        sa.Column("expires_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tg_id"], ["users.tg_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payment_id", name="uq_transactions_payment_id"),
    )

    op.execute(
        "INSERT INTO transactions_new "
        "(id, tg_id, payment_id, subscription, status, payment_type, expires_at, created_at, updated_at) "
        "SELECT id, tg_id, payment_id, subscription, status, NULL, NULL, created_at, updated_at "
        "FROM transactions"
    )

    op.drop_table("transactions")
    op.rename_table("transactions_new", "transactions")


def downgrade() -> None:
    old_enum = sa.Enum(
        "pending", "completed", "canceled", "refunded",
        name="transactionstatus",
    )

    op.create_table(
        "transactions_new",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tg_id", sa.Integer(), nullable=False),
        sa.Column("payment_id", sa.String(length=64), nullable=False),
        sa.Column("subscription", sa.String(length=255), nullable=False),
        sa.Column("status", old_enum, nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["tg_id"], ["users.tg_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("payment_id", name="uq_transactions_payment_id"),
    )

    op.execute(
        "INSERT INTO transactions_new "
        "(id, tg_id, payment_id, subscription, status, created_at, updated_at) "
        "SELECT id, tg_id, payment_id, subscription, "
        "CASE WHEN status IN ('expired','rejected') THEN 'canceled' ELSE status END, "
        "created_at, updated_at FROM transactions"
    )

    op.drop_table("transactions")
    op.rename_table("transactions_new", "transactions")
