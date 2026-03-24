"""Add service_interval_days to service_items table.

Revision ID: k1f2g3h4i5j6
Revises: h8c9d0e1f2g3
Create Date: 2026-03-24

Adds an optional integer column for tracking how many days between
required services.  NULL means no automatic reminders.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "k1f2g3h4i5j6"
down_revision = "l2g3h4i5j6k7"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "service_items",
        sa.Column("service_interval_days", sa.Integer(), nullable=True),
    )


def downgrade():
    op.drop_column("service_items", "service_interval_days")
