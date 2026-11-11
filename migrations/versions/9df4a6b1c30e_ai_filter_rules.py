"""add approved AI filter rule versions and comment decision snapshots

Revision ID: 9df4a6b1c30e
Revises: 460d9a7bda17
Create Date: 2026-11-01
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "9df4a6b1c30e"
down_revision: Union[str, None] = "460d9a7bda17"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "collector_filter_rules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("lineage_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("parent_rule_id", sa.String(length=36), nullable=True),
        sa.Column("intent", sa.Text(), nullable=False),
        sa.Column("definition", sa.JSON(), nullable=False),
        sa.Column("model_name", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["parent_rule_id"], ["collector_filter_rules.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("lineage_id", "version", name="uq_collector_filter_rule_lineage_version"),
    )
    op.add_column("collector_tasks", sa.Column("filter_rule_id", sa.String(length=36), nullable=True))
    op.create_foreign_key(
        "fk_collector_tasks_filter_rule_id",
        "collector_tasks",
        "collector_filter_rules",
        ["filter_rule_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.add_column("collector_comment_snapshots", sa.Column("filter_rule_id", sa.String(length=36), nullable=True))
    op.add_column("collector_comment_snapshots", sa.Column("filter_rule_version", sa.Integer(), nullable=True))
    op.add_column("collector_comment_snapshots", sa.Column("filter_reason", sa.String(length=240), nullable=True))


def downgrade() -> None:
    op.drop_column("collector_comment_snapshots", "filter_reason")
    op.drop_column("collector_comment_snapshots", "filter_rule_version")
    op.drop_column("collector_comment_snapshots", "filter_rule_id")
    op.drop_constraint("fk_collector_tasks_filter_rule_id", "collector_tasks", type_="foreignkey")
    op.drop_column("collector_tasks", "filter_rule_id")
    op.drop_table("collector_filter_rules")
