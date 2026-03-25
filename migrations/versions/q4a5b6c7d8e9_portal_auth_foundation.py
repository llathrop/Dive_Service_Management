"""Portal auth foundation tables.

Revision ID: q4a5b6c7d8e9
Revises: j0e1f2g3h4i5, l2g3h4i5j6k7
Create Date: 2026-03-24
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "q4a5b6c7d8e9"
down_revision = ("j0e1f2g3h4i5", "l2g3h4i5j6k7")
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "portal_users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "login_count",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_portal_users_customer_id", "portal_users", ["customer_id"])
    op.create_index("ix_portal_users_email", "portal_users", ["email"])

    op.create_table(
        "portal_access_tokens",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=False),
        sa.Column("portal_user_id", sa.Integer(), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column(
            "purpose",
            sa.String(length=32),
            nullable=False,
            server_default="activation",
        ),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["portal_user_id"], ["portal_users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index(
        "ix_portal_access_tokens_customer_id",
        "portal_access_tokens",
        ["customer_id"],
    )
    op.create_index(
        "ix_portal_access_tokens_email",
        "portal_access_tokens",
        ["email"],
    )
    op.create_index(
        "ix_portal_access_tokens_expires_at",
        "portal_access_tokens",
        ["expires_at"],
    )
    op.create_index(
        "ix_portal_access_tokens_portal_user_id",
        "portal_access_tokens",
        ["portal_user_id"],
    )
    op.create_index(
        "ix_portal_access_tokens_purpose",
        "portal_access_tokens",
        ["purpose"],
    )
    op.create_index(
        "ix_portal_access_tokens_token_hash",
        "portal_access_tokens",
        ["token_hash"],
    )


def downgrade():
    op.drop_table("portal_access_tokens")
    op.drop_table("portal_users")
