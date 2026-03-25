"""Add provider metadata columns to shipments.

Revision ID: r5b6c7d8e9f0
Revises: q4a5b6c7d8e9
Create Date: 2026-03-25
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "r5b6c7d8e9f0"
down_revision = "q4a5b6c7d8e9"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("shipments", sa.Column("provider_code", sa.String(length=50), nullable=True))
    op.add_column("shipments", sa.Column("quote_metadata", sa.JSON(), nullable=True))


def downgrade():
    op.drop_column("shipments", "quote_metadata")
    op.drop_column("shipments", "provider_code")
