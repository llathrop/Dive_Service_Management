"""Create shipments table.

Revision ID: l2g3h4i5j6k7
Revises: i9d0e1f2g3h4
Create Date: 2026-03-24

Stores shipping details (weight, dimensions, cost, tracking) for
service orders.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'l2g3h4i5j6k7'
down_revision = 'i9d0e1f2g3h4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'shipments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('order_id', sa.Integer(), nullable=False),
        sa.Column('weight_lbs', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('length_in', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('width_in', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('height_in', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('shipping_method', sa.String(length=100), nullable=True),
        sa.Column('shipping_cost', sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column('tracking_number', sa.String(length=255), nullable=True),
        sa.Column('carrier', sa.String(length=100), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=False, server_default='pending'),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['order_id'], ['service_orders.id']),
        sa.ForeignKeyConstraint(['created_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_shipments_order_id', 'shipments', ['order_id'])


def downgrade():
    op.drop_index('ix_shipments_order_id', table_name='shipments')
    op.drop_table('shipments')
