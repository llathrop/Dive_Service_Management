"""Add service_reminder_deliveries ledger table.

Revision ID: m1n2o3p4q5r6
Revises: k1f2g3h4i5j6
Create Date: 2026-03-24
"""

from alembic import op
import sqlalchemy as sa


revision = "m1n2o3p4q5r6"
down_revision = "k1f2g3h4i5j6"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "service_reminder_deliveries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("service_item_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("delivery_date", sa.Date(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["service_item_id"],
            ["service_items.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "service_item_id",
            "user_id",
            "delivery_date",
            name="uq_service_reminder_delivery",
        ),
    )


def downgrade():
    op.drop_table("service_reminder_deliveries")
