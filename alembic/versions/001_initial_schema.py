"""Initial schema — datasets, region_budgets, communes, region_stats.

Revision ID: 001
Revises: None
Create Date: 2025-01-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "datasets",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("title", sa.String(512), nullable=False),
        sa.Column("slug", sa.String(512)),
        sa.Column("description", sa.Text),
        sa.Column("organization", sa.String(256)),
        sa.Column("license", sa.String(64)),
        sa.Column("last_modified", sa.DateTime),
        sa.Column("ingested_at", sa.DateTime, server_default=sa.func.now()),
    )

    op.create_table(
        "region_budgets",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("year", sa.Integer, nullable=False, index=True),
        sa.Column("region_code", sa.String(8), nullable=False, index=True),
        sa.Column("region_name", sa.String(256)),
        sa.Column("total_revenue", sa.Float),
        sa.Column("total_expenditure", sa.Float),
        sa.Column("operating_revenue", sa.Float),
        sa.Column("operating_expenditure", sa.Float),
        sa.Column("investment_revenue", sa.Float),
        sa.Column("investment_expenditure", sa.Float),
        sa.Column("debt", sa.Float),
        sa.Column("population", sa.Integer),
    )

    op.create_table(
        "communes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("code_insee", sa.String(8), nullable=False, index=True),
        sa.Column("name", sa.String(256), nullable=False),
        sa.Column("region_code", sa.String(8), index=True),
        sa.Column("region_name", sa.String(256)),
        sa.Column("department_code", sa.String(8)),
        sa.Column("department_name", sa.String(256)),
        sa.Column("population", sa.Integer),
        sa.Column("area_km2", sa.Float),
        sa.Column("density", sa.Float),
    )

    op.create_table(
        "region_stats",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("year", sa.Integer, index=True),
        sa.Column("region_code", sa.String(8), index=True),
        sa.Column("region_name", sa.String(256)),
        sa.Column("total_population", sa.Integer),
        sa.Column("total_revenue", sa.Float),
        sa.Column("total_expenditure", sa.Float),
        sa.Column("revenue_per_capita", sa.Float),
        sa.Column("expenditure_per_capita", sa.Float),
        sa.Column("num_communes", sa.Integer),
    )


def downgrade() -> None:
    op.drop_table("region_stats")
    op.drop_table("communes")
    op.drop_table("region_budgets")
    op.drop_table("datasets")
