"""add run progress fields

Revision ID: 1a2b3c4d5e6f
Revises: c275aba14e33
Create Date: 2026-11-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "1a2b3c4d5e6f"
down_revision: Union[str, None] = "c275aba14e33"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "collector_runs",
        sa.Column("phase", sa.String(length=24), nullable=False, server_default="queued"),
    )
    op.add_column(
        "collector_runs",
        sa.Column("progress", sa.JSON(), nullable=False, server_default=sa.text("'{}'::json")),
    )
    op.add_column(
        "collector_runs",
        sa.Column("last_activity_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.alter_column("collector_runs", "phase", server_default=None)
    op.alter_column("collector_runs", "progress", server_default=None)


def downgrade() -> None:
    op.drop_column("collector_runs", "last_activity_at")
    op.drop_column("collector_runs", "progress")
    op.drop_column("collector_runs", "phase")
