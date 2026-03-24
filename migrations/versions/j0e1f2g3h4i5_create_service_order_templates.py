"""Create service_order_templates table for reusable order configurations.

Revision ID: j0e1f2g3h4i5
Revises: h8c9d0e1f2g3
Create Date: 2026-03-24
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'j0e1f2g3h4i5'
down_revision = 'm1n2o3p4q5r6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'service_order_templates',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_by_id', sa.Integer(), nullable=False),
        sa.Column('is_shared', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('template_data', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['created_by_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        'ix_service_order_templates_created_by_id',
        'service_order_templates',
        ['created_by_id'],
    )


def downgrade():
    op.drop_index(
        'ix_service_order_templates_created_by_id',
        table_name='service_order_templates',
    )
    op.drop_table('service_order_templates')
