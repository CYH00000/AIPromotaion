"""store keyword matches on each comment observation

Revision ID: c275aba14e33
Revises: 9df4a6b1c30e
Create Date: 2026-11-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c275aba14e33"
down_revision: Union[str, None] = "9df4a6b1c30e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "collector_comment_snapshots",
        sa.Column("matched_keywords", sa.JSON(), nullable=True),
    )
    op.execute(
        sa.text(
            "UPDATE collector_comment_snapshots "
            "SET matched_keywords = '[]'::json "
            "WHERE matched_keywords IS NULL"
        )
    )
    op.alter_column("collector_comment_snapshots", "matched_keywords", nullable=False)


def downgrade() -> None:
    op.drop_column("collector_comment_snapshots", "matched_keywords")
