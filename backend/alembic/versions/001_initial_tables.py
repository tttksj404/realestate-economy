"""initial tables

Revision ID: 001_initial_tables
Revises: 
Create Date: 2026-03-31 00:00:00
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "001_initial_tables"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "real_estate_listings",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("region_code", sa.String(length=10), nullable=False),
        sa.Column("region_name", sa.String(length=100), nullable=False),
        sa.Column("property_type", sa.String(length=20), nullable=False),
        sa.Column("listing_price", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("actual_price", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("jeonse_price", sa.Numeric(precision=15, scale=2), nullable=True),
        sa.Column("area_sqm", sa.Float(), nullable=True),
        sa.Column("floor", sa.Integer(), nullable=True),
        sa.Column("built_year", sa.Integer(), nullable=True),
        sa.Column("listed_at", sa.Date(), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_real_estate_listings_listed_at", "real_estate_listings", ["listed_at"], unique=False)
    op.create_index("ix_real_estate_listings_property_type", "real_estate_listings", ["property_type"], unique=False)
    op.create_index("ix_real_estate_listings_region_code", "real_estate_listings", ["region_code"], unique=False)
    op.create_index("ix_listings_region_property", "real_estate_listings", ["region_code", "property_type"], unique=False)
    op.create_index("ix_listings_region_listed_at", "real_estate_listings", ["region_code", "listed_at"], unique=False)
    op.create_index("ix_listings_region_listing_price", "real_estate_listings", ["region_code", "listing_price"], unique=False)

    op.create_table(
        "real_estate_transactions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("region_code", sa.String(length=10), nullable=False),
        sa.Column("region_name", sa.String(length=100), nullable=False),
        sa.Column("property_type", sa.String(length=20), nullable=False),
        sa.Column("deal_amount", sa.Numeric(precision=15, scale=2), nullable=False),
        sa.Column("area_sqm", sa.Float(), nullable=True),
        sa.Column("deal_date", sa.Date(), nullable=True),
        sa.Column("floor", sa.Integer(), nullable=True),
        sa.Column("built_year", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_real_estate_transactions_deal_date", "real_estate_transactions", ["deal_date"], unique=False)
    op.create_index("ix_real_estate_transactions_property_type", "real_estate_transactions", ["property_type"], unique=False)
    op.create_index("ix_real_estate_transactions_region_code", "real_estate_transactions", ["region_code"], unique=False)
    op.create_index("ix_transactions_region_property", "real_estate_transactions", ["region_code", "property_type"], unique=False)
    op.create_index("ix_transactions_region_deal_date", "real_estate_transactions", ["region_code", "deal_date"], unique=False)
    op.create_index("ix_transactions_region_deal_amount", "real_estate_transactions", ["region_code", "deal_amount"], unique=False)

    op.create_table(
        "economy_indicators",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("region_code", sa.String(length=10), nullable=False),
        sa.Column("region_name", sa.String(length=100), nullable=False),
        sa.Column("period", sa.String(length=6), nullable=False),
        sa.Column("low_price_listing_ratio", sa.Float(), nullable=True),
        sa.Column("listing_count_change", sa.Float(), nullable=True),
        sa.Column("price_gap_ratio", sa.Float(), nullable=True),
        sa.Column("regional_price_index", sa.Float(), nullable=True),
        sa.Column("sale_speed", sa.Float(), nullable=True),
        sa.Column("jeonse_ratio", sa.Float(), nullable=True),
        sa.Column("signal", sa.String(length=10), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("region_code", "period", name="uq_economy_region_period"),
    )
    op.create_index("ix_economy_indicators_period", "economy_indicators", ["period"], unique=False)
    op.create_index("ix_economy_indicators_region_code", "economy_indicators", ["region_code"], unique=False)
    op.create_index("ix_economy_indicators_signal", "economy_indicators", ["signal"], unique=False)
    op.create_index("ix_economy_region_period", "economy_indicators", ["region_code", "period"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_economy_region_period", table_name="economy_indicators")
    op.drop_index("ix_economy_indicators_signal", table_name="economy_indicators")
    op.drop_index("ix_economy_indicators_region_code", table_name="economy_indicators")
    op.drop_index("ix_economy_indicators_period", table_name="economy_indicators")
    op.drop_table("economy_indicators")

    op.drop_index("ix_transactions_region_deal_amount", table_name="real_estate_transactions")
    op.drop_index("ix_transactions_region_deal_date", table_name="real_estate_transactions")
    op.drop_index("ix_transactions_region_property", table_name="real_estate_transactions")
    op.drop_index("ix_real_estate_transactions_region_code", table_name="real_estate_transactions")
    op.drop_index("ix_real_estate_transactions_property_type", table_name="real_estate_transactions")
    op.drop_index("ix_real_estate_transactions_deal_date", table_name="real_estate_transactions")
    op.drop_table("real_estate_transactions")

    op.drop_index("ix_listings_region_listing_price", table_name="real_estate_listings")
    op.drop_index("ix_listings_region_listed_at", table_name="real_estate_listings")
    op.drop_index("ix_listings_region_property", table_name="real_estate_listings")
    op.drop_index("ix_real_estate_listings_region_code", table_name="real_estate_listings")
    op.drop_index("ix_real_estate_listings_property_type", table_name="real_estate_listings")
    op.drop_index("ix_real_estate_listings_listed_at", table_name="real_estate_listings")
    op.drop_table("real_estate_listings")
