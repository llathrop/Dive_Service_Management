"""P0-2: Add notification_reads table for per-user broadcast read tracking

Broadcast notifications (user_id IS NULL) are shared rows.  This table
stores per-user read receipts so that marking a broadcast as read for
one user does not affect other users.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-03-08 01:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'notification_reads',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('notification_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('read_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ['notification_id'], ['notifications.id'],
            ondelete='CASCADE',
        ),
        sa.ForeignKeyConstraint(
            ['user_id'], ['users.id'],
            ondelete='CASCADE',
        ),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint(
            'notification_id', 'user_id',
            name='uq_notification_user_read',
        ),
    )


def downgrade():
    op.drop_table('notification_reads')
