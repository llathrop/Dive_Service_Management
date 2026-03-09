"""P0-1: Change inventory stock columns from Integer to Numeric(10,2)

Allows fractional inventory quantities (e.g. 2.5 ft of tape) to be
tracked without truncation.  Fixes stock drift caused by int() casts
on decimal part quantities.

Revision ID: a1b2c3d4e5f6
Revises: c3d4e5f6a7b8
Create Date: 2026-03-08 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'c3d4e5f6a7b8'
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        'inventory_items',
        'quantity_in_stock',
        existing_type=sa.Integer(),
        type_=sa.Numeric(precision=10, scale=2),
        existing_nullable=False,
        existing_server_default=sa.text('0'),
    )
    op.alter_column(
        'inventory_items',
        'reorder_level',
        existing_type=sa.Integer(),
        type_=sa.Numeric(precision=10, scale=2),
        existing_nullable=False,
        existing_server_default=sa.text('0'),
    )


def downgrade():
    op.alter_column(
        'inventory_items',
        'reorder_level',
        existing_type=sa.Numeric(precision=10, scale=2),
        type_=sa.Integer(),
        existing_nullable=False,
        existing_server_default=sa.text('0'),
    )
    op.alter_column(
        'inventory_items',
        'quantity_in_stock',
        existing_type=sa.Numeric(precision=10, scale=2),
        type_=sa.Integer(),
        existing_nullable=False,
        existing_server_default=sa.text('0'),
    )
