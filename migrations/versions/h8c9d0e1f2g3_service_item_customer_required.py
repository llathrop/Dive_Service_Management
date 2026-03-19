"""Make service_items.customer_id NOT NULL with smart orphan resolution.

Revision ID: h8c9d0e1f2g3
Revises: g7b8c9d0e1f2
Create Date: 2026-03-19

Three-tier orphan resolution:
1. Items linked to orders — assign from most recent order's customer_id
2. Remaining orphans — assign to a "Legacy / Unassigned" placeholder customer
3. ALTER COLUMN customer_id SET NOT NULL
"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'h8c9d0e1f2g3'
down_revision = 'g7b8c9d0e1f2'
branch_labels = None
depends_on = None


def upgrade():
    conn = op.get_bind()

    # --- Tier 1: resolve orphans via service order history ---
    # Find service items with NULL customer_id that have appeared in orders.
    # Use the customer_id from the most recent order (by date_received).
    orphan_rows = conn.execute(
        sa.text(
            "SELECT si.id "
            "FROM service_items si "
            "WHERE si.customer_id IS NULL"
        )
    ).fetchall()

    for (item_id,) in orphan_rows:
        # Find the most recent order's customer_id for this item
        result = conn.execute(
            sa.text(
                "SELECT so.customer_id "
                "FROM service_order_items soi "
                "JOIN service_orders so ON so.id = soi.order_id "
                "WHERE soi.service_item_id = :item_id "
                "ORDER BY so.date_received DESC "
                "LIMIT 1"
            ),
            {"item_id": item_id},
        ).fetchone()

        if result:
            conn.execute(
                sa.text(
                    "UPDATE service_items SET customer_id = :cid WHERE id = :id"
                ),
                {"cid": result[0], "id": item_id},
            )

    # --- Tier 2: create placeholder customer for remaining orphans ---
    remaining = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM service_items WHERE customer_id IS NULL"
        )
    ).scalar()

    if remaining > 0:
        # Create a placeholder customer
        conn.execute(
            sa.text(
                "INSERT INTO customers "
                "(customer_type, first_name, last_name, preferred_contact, country) "
                "VALUES ('individual', 'Legacy', 'Unassigned', 'email', 'US')"
            )
        )
        # Get the placeholder's id
        placeholder_id = conn.execute(
            sa.text(
                "SELECT id FROM customers "
                "WHERE first_name = 'Legacy' AND last_name = 'Unassigned' "
                "ORDER BY id DESC LIMIT 1"
            )
        ).scalar()

        conn.execute(
            sa.text(
                "UPDATE service_items SET customer_id = :cid "
                "WHERE customer_id IS NULL"
            ),
            {"cid": placeholder_id},
        )

    # --- Tier 3: set NOT NULL ---
    with op.batch_alter_table('service_items') as batch_op:
        batch_op.alter_column(
            'customer_id',
            existing_type=sa.Integer(),
            nullable=False,
        )


def downgrade():
    with op.batch_alter_table('service_items') as batch_op:
        batch_op.alter_column(
            'customer_id',
            existing_type=sa.Integer(),
            nullable=True,
        )
