"""V2 indicators: R-ONE based columns

Revision ID: 002_v2_indicators
Revises: 001_initial_tables
Create Date: 2026-04-01 00:00:00
"""

from alembic import op
import sqlalchemy as sa

revision = "002_v2_indicators"
down_revision = "001_initial_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add V2 columns
    op.add_column("economy_indicators", sa.Column("sale_index_change", sa.Float(), nullable=True))
    op.add_column("economy_indicators", sa.Column("unsold_change", sa.Float(), nullable=True))
    op.add_column("economy_indicators", sa.Column("tx_count_change", sa.Float(), nullable=True))
    op.add_column("economy_indicators", sa.Column("supply_demand", sa.Float(), nullable=True))
    op.add_column("economy_indicators", sa.Column("auction_change", sa.Float(), nullable=True))

    # Drop V1 columns that are no longer used
    op.drop_column("economy_indicators", "low_price_listing_ratio")
    op.drop_column("economy_indicators", "listing_count_change")
    op.drop_column("economy_indicators", "price_gap_ratio")
    op.drop_column("economy_indicators", "regional_price_index")
    op.drop_column("economy_indicators", "sale_speed")
    # jeonse_ratio is kept (same name in V2)


def downgrade() -> None:
    op.add_column("economy_indicators", sa.Column("low_price_listing_ratio", sa.Float(), nullable=True))
    op.add_column("economy_indicators", sa.Column("listing_count_change", sa.Float(), nullable=True))
    op.add_column("economy_indicators", sa.Column("price_gap_ratio", sa.Float(), nullable=True))
    op.add_column("economy_indicators", sa.Column("regional_price_index", sa.Float(), nullable=True))
    op.add_column("economy_indicators", sa.Column("sale_speed", sa.Float(), nullable=True))

    op.drop_column("economy_indicators", "sale_index_change")
    op.drop_column("economy_indicators", "unsold_change")
    op.drop_column("economy_indicators", "tx_count_change")
    op.drop_column("economy_indicators", "supply_demand")
    op.drop_column("economy_indicators", "auction_change")
