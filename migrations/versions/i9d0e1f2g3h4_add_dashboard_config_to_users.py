"""Add dashboard_config column to users table.

Revision ID: i9d0e1f2g3h4
Revises: h8c9d0e1f2g3
Create Date: 2026-03-23

Stores per-user dashboard card visibility and ordering as a JSON string.
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'i9d0e1f2g3h4'
down_revision = 'h8c9d0e1f2g3'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(
            sa.Column('dashboard_config', sa.Text(), nullable=True)
        )


def downgrade():
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_column('dashboard_config')
