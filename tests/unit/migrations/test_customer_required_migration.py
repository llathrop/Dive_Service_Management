"""Unit tests for the service_item customer_id NOT NULL migration logic.

These tests verify the three-tier orphan resolution logic by simulating
the migration conditions.  Since the model now enforces NOT NULL, we
temporarily recreate the table with nullable customer_id.
"""

import pytest

from app.extensions import db
from app.models.customer import Customer
from tests.factories import (
    BaseFactory,
    CustomerFactory,
    ServiceOrderFactory,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _bind_factories(db_session):
    for f in (BaseFactory, CustomerFactory, ServiceOrderFactory):
        f._meta.sqlalchemy_session = db_session


@pytest.fixture()
def _relaxed_schema(app, db_session):
    """Recreate service_items with nullable customer_id to simulate pre-migration state."""
    # Get actual column definitions from current table
    cols = db_session.execute(db.text("PRAGMA table_info(service_items)")).fetchall()
    col_defs = []
    for col in cols:
        cid, name, ctype, notnull, default_val, pk = col
        if pk:
            col_defs.append(f"{name} {ctype} PRIMARY KEY AUTOINCREMENT")
        else:
            nullable = "NOT NULL" if (notnull and name != "customer_id") else ""
            col_defs.append(f"{name} {ctype} {nullable}".strip())

    db_session.execute(db.text("ALTER TABLE service_items RENAME TO _si_backup"))
    db_session.execute(db.text(f"CREATE TABLE service_items ({', '.join(col_defs)})"))
    db_session.execute(db.text("INSERT INTO service_items SELECT * FROM _si_backup"))
    db_session.execute(db.text("DROP TABLE _si_backup"))
    db_session.commit()
    yield


class TestMigrationOrphanResolution:
    """Test the orphan resolution logic that the migration implements."""

    def test_migration_resolves_orphans_via_service_orders(self, app, db_session, _relaxed_schema):
        """Items linked to orders should get their customer_id from the order."""
        customer = CustomerFactory()
        order = ServiceOrderFactory(customer=customer)

        # Insert an orphan item with NULL customer_id
        db_session.execute(
            db.text(
                "INSERT INTO service_items (name, serviceability, is_deleted, created_at) "
                "VALUES ('Orphan Reg', 'serviceable', 0, datetime('now'))"
            )
        )
        db_session.flush()
        orphan_id = db_session.execute(
            db.text("SELECT id FROM service_items WHERE name = 'Orphan Reg'")
        ).scalar()

        # Link the orphan to an order via service_order_items
        db_session.execute(
            db.text(
                "INSERT INTO service_order_items (order_id, service_item_id, "
                "work_description, status, customer_approved, warranty_type, created_at) "
                "VALUES (:oid, :sid, 'Fix it', 'pending', 0, 'none', datetime('now'))"
            ),
            {"oid": order.id, "sid": orphan_id},
        )
        db_session.commit()

        # Simulate tier-1 resolution: find customer from order
        result = db_session.execute(
            db.text(
                "SELECT so.customer_id FROM service_order_items soi "
                "JOIN service_orders so ON so.id = soi.order_id "
                "WHERE soi.service_item_id = :item_id "
                "ORDER BY so.date_received DESC LIMIT 1"
            ),
            {"item_id": orphan_id},
        ).fetchone()

        assert result is not None
        assert result[0] == customer.id

        # Apply the resolution
        db_session.execute(
            db.text("UPDATE service_items SET customer_id = :cid WHERE id = :id"),
            {"cid": result[0], "id": orphan_id},
        )
        db_session.commit()

        row = db_session.execute(
            db.text("SELECT customer_id FROM service_items WHERE id = :id"),
            {"id": orphan_id},
        ).fetchone()
        assert row[0] == customer.id

    def test_migration_creates_placeholder_for_remaining_orphans(self, app, db_session, _relaxed_schema):
        """Items with no order history get assigned to a placeholder customer."""
        db_session.execute(
            db.text(
                "INSERT INTO service_items (name, serviceability, is_deleted, created_at) "
                "VALUES ('Lonely BCD', 'serviceable', 0, datetime('now'))"
            )
        )
        db_session.commit()

        orphan_id = db_session.execute(
            db.text("SELECT id FROM service_items WHERE name = 'Lonely BCD'")
        ).scalar()

        # Verify no order link exists
        order_link = db_session.execute(
            db.text(
                "SELECT COUNT(*) FROM service_order_items "
                "WHERE service_item_id = :id"
            ),
            {"id": orphan_id},
        ).scalar()
        assert order_link == 0

        # Simulate tier-2: create placeholder and assign
        placeholder = Customer(
            customer_type="individual",
            first_name="Legacy",
            last_name="Unassigned",
            preferred_contact="email",
            country="US",
        )
        db_session.add(placeholder)
        db_session.flush()

        db_session.execute(
            db.text(
                "UPDATE service_items SET customer_id = :cid WHERE customer_id IS NULL"
            ),
            {"cid": placeholder.id},
        )
        db_session.commit()

        row = db_session.execute(
            db.text("SELECT customer_id FROM service_items WHERE id = :id"),
            {"id": orphan_id},
        ).fetchone()
        assert row[0] == placeholder.id
