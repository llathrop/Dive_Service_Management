"""Add lookup_values table

Revision ID: 8f53c00bcf23
Revises: r5b6c7d8e9f0
Create Date: 2026-04-04 23:17:01.650522

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '8f53c00bcf23'
down_revision = 'r5b6c7d8e9f0'
branch_labels = None
depends_on = None


def upgrade():
    # Create lookup_values table
    op.create_table('lookup_values',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('category', sa.String(length=50), nullable=False),
        sa.Column('value', sa.String(length=100), nullable=False),
        sa.Column('display_name', sa.String(length=100), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.Column('sort_order', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('category', 'value', name='_category_value_uc'),
        sa.ForeignKeyConstraint(['created_by'], ['users.id'], name='fk_lookup_values_created_by')
    )
    with op.batch_alter_table('lookup_values', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_lookup_values_category'), ['category'], unique=False)


def downgrade():
    op.drop_table('lookup_values')
