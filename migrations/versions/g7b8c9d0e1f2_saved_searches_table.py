"""Add saved_searches table for per-user saved filter configurations.

Revision ID: g7b8c9d0e1f2
Revises: f6a7b8c9d0e1
Create Date: 2026-03-17
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'g7b8c9d0e1f2'
down_revision = 'f6a7b8c9d0e1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'saved_searches',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('search_type', sa.String(length=50), nullable=False),
        sa.Column('filters_json', sa.Text(), nullable=False),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'name', 'search_type', name='uq_saved_search_user_name_type'),
    )
    op.create_index('ix_saved_search_user_type', 'saved_searches', ['user_id', 'search_type'])
    op.create_index('ix_saved_searches_user_id', 'saved_searches', ['user_id'])


def downgrade():
    op.drop_index('ix_saved_searches_user_id', table_name='saved_searches')
    op.drop_index('ix_saved_search_user_type', table_name='saved_searches')
    op.drop_table('saved_searches')
