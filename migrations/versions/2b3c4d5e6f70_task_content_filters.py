"""add task content filters

Revision ID: 2b3c4d5e6f70
Revises: 1a2b3c4d5e6f
Create Date: 2026-11-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2b3c4d5e6f70"
down_revision: Union[str, None] = "1a2b3c4d5e6f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "collector_tasks",
        sa.Column("content_sort", sa.String(length=16), nullable=False, server_default="general"),
    )
    op.add_column(
        "collector_tasks",
        sa.Column("publish_time_days", sa.Integer(), nullable=False, server_default="0"),
    )
    op.alter_column("collector_tasks", "content_sort", server_default=None)
    op.alter_column("collector_tasks", "publish_time_days", server_default=None)


def downgrade() -> None:
    op.drop_column("collector_tasks", "publish_time_days")
    op.drop_column("collector_tasks", "content_sort")
