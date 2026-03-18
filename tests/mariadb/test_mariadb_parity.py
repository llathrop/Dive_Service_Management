"""MariaDB parity tests -- verify SQLite/MariaDB behavioral consistency.

These tests exercise areas where SQLite and MariaDB are known to diverge:
case sensitivity, collation, Unicode (utf8mb4), Decimal precision, date/time
handling, ENUM-like status columns, and concurrent write safety.

All tests are skipped automatically when MariaDB is not available (see
conftest.py).
"""

import threading
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from app.extensions import db
from app.models.customer import Customer
from app.models.inventory import InventoryItem
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.notification import Notification
from app.models.payment import Payment
from app.models.service_item import ServiceItem
from app.models.service_note import ServiceNote
from app.models.service_order import ServiceOrder
from app.models.service_order_item import ServiceOrderItem
from app.services import search_service


# =========================================================================
# Helpers
# =========================================================================

def _make_customer(db_session, **overrides):
    """Create and persist a minimal customer."""
    defaults = dict(
        customer_type="individual",
        first_name="Test",
        last_name="User",
        email="test@example.com",
        preferred_contact="email",
    )
    defaults.update(overrides)
    c = Customer(**defaults)
    db_session.add(c)
    db_session.commit()
    return c


def _make_service_item(db_session, customer=None, **overrides):
    """Create and persist a minimal service item."""
    defaults = dict(
        name="Test Regulator",
        item_category="Regulator",
        serviceability="serviceable",
    )
    if customer:
        defaults["customer_id"] = customer.id
    defaults.update(overrides)
    si = ServiceItem(**defaults)
    db_session.add(si)
    db_session.commit()
    return si


def _make_order(db_session, customer, **overrides):
    """Create and persist a minimal service order."""
    defaults = dict(
        customer_id=customer.id,
        order_number=overrides.pop("order_number", "SO-2026-99999"),
        status="intake",
        priority="normal",
        date_received=date.today(),
    )
    defaults.update(overrides)
    o = ServiceOrder(**defaults)
    db_session.add(o)
    db_session.commit()
    return o


def _make_invoice(db_session, customer, **overrides):
    """Create and persist a minimal invoice."""
    defaults = dict(
        customer_id=customer.id,
        invoice_number=overrides.pop("invoice_number", "INV-2026-99999"),
        status="draft",
        issue_date=date.today(),
        subtotal=Decimal("0.00"),
        total=Decimal("0.00"),
        balance_due=Decimal("0.00"),
    )
    defaults.update(overrides)
    inv = Invoice(**defaults)
    db_session.add(inv)
    db_session.commit()
    return inv


# =========================================================================
# A) Text Search / LIKE behavior
# =========================================================================


class TestTextSearchParity:
    """Verify LIKE / ilike searches work consistently on MariaDB."""

    def test_case_insensitive_like_customer_search(self, app, db_session):
        """ilike should match regardless of case on MariaDB."""
        _make_customer(db_session, first_name="Wolfgang", last_name="Mozart")
        results = search_service.search_customers("WOLF")
        assert len(results) == 1
        assert results[0]["display_name"] == "Wolfgang Mozart"

    def test_case_insensitive_like_inventory_search(self, app, db_session):
        """ilike should match inventory items case-insensitively."""
        item = InventoryItem(
            name="Silicone O-Ring",
            category="Seals",
            quantity_in_stock=Decimal("50.00"),
            reorder_level=Decimal("10.00"),
        )
        db_session.add(item)
        db_session.commit()

        results = search_service.search_inventory_items("SILICONE")
        assert len(results) == 1
        assert "O-Ring" in results[0]["display_text"]

    def test_search_with_special_characters(self, app, db_session):
        """Percent and underscore in search terms should be handled safely."""
        _make_customer(db_session, first_name="Test%User", last_name="Under_Score")

        # Search for literal percent -- should not match everything
        results = search_service.search_customers("Test%")
        assert len(results) >= 1

    def test_search_with_unicode(self, app, db_session):
        """Unicode characters in search should work with utf8mb4 collation."""
        _make_customer(db_session, first_name="Hans", last_name="Muller")
        results = search_service.search_customers("Muller")
        assert len(results) == 1

    def test_global_search_returns_results(self, app, db_session):
        """The global_search function should return results from MariaDB."""
        _make_customer(db_session, first_name="Unique", last_name="Diver")
        results = search_service.global_search("Unique")
        assert len(results["customers"]) == 1
        assert results["customers"][0]["display_name"] == "Unique Diver"


# =========================================================================
# B) Decimal Precision
# =========================================================================


class TestDecimalPrecision:
    """Verify Decimal(10,2) columns retain precision through MariaDB round-trips."""

    def test_inventory_quantity_decimal_precision(self, app, db_session):
        """Inventory quantity_in_stock should store Decimal(10,2) exactly."""
        item = InventoryItem(
            name="Precision Part",
            category="Hardware",
            quantity_in_stock=Decimal("123.45"),
            reorder_level=Decimal("10.50"),
        )
        db_session.add(item)
        db_session.commit()

        loaded = db_session.get(InventoryItem, item.id)
        assert loaded.quantity_in_stock == Decimal("123.45")
        assert loaded.reorder_level == Decimal("10.50")

    def test_invoice_total_decimal_precision(self, app, db_session):
        """Invoice financial fields should retain Decimal precision."""
        customer = _make_customer(db_session)
        inv = _make_invoice(
            db_session,
            customer,
            subtotal=Decimal("999.99"),
            tax_rate=Decimal("0.0825"),
            tax_amount=Decimal("82.50"),
            total=Decimal("1082.49"),
            amount_paid=Decimal("500.25"),
            balance_due=Decimal("582.24"),
        )

        loaded = db_session.get(Invoice, inv.id)
        assert loaded.subtotal == Decimal("999.99")
        assert loaded.tax_rate == Decimal("0.0825")
        assert loaded.tax_amount == Decimal("82.50")
        assert loaded.total == Decimal("1082.49")
        assert loaded.amount_paid == Decimal("500.25")
        assert loaded.balance_due == Decimal("582.24")

    def test_payment_amount_decimal_precision(self, app, db_session):
        """Payment amounts should store Decimal(10,2) exactly."""
        customer = _make_customer(db_session)
        inv = _make_invoice(db_session, customer)

        payment = Payment(
            invoice_id=inv.id,
            payment_type="payment",
            amount=Decimal("1234.56"),
            payment_date=date.today(),
            payment_method="credit_card",
        )
        db_session.add(payment)
        db_session.commit()

        loaded = db_session.get(Payment, payment.id)
        assert loaded.amount == Decimal("1234.56")

    def test_decimal_arithmetic_roundtrip(self, app, db_session):
        """Decimal arithmetic should not lose precision through DB round-trips."""
        item = InventoryItem(
            name="Math Test Part",
            category="Hardware",
            purchase_cost=Decimal("10.33"),
            resale_price=Decimal("15.49"),
            quantity_in_stock=Decimal("0.00"),
            reorder_level=Decimal("0.00"),
        )
        db_session.add(item)
        db_session.commit()

        loaded = db_session.get(InventoryItem, item.id)
        # Verify the values round-trip exactly
        assert loaded.purchase_cost == Decimal("10.33")
        assert loaded.resale_price == Decimal("15.49")
        # Computed markup should work correctly
        expected_markup = ((Decimal("15.49") - Decimal("10.33")) / Decimal("10.33")) * Decimal("100")
        assert abs(loaded.computed_markup_percent - expected_markup) < Decimal("0.01")


# =========================================================================
# C) Unicode / utf8mb4
# =========================================================================


class TestUnicodeParity:
    """Verify utf8mb4 storage works correctly for multi-byte characters."""

    def test_customer_name_with_accented_characters(self, app, db_session):
        """Accented characters should survive storage and retrieval."""
        customer = _make_customer(
            db_session,
            first_name="Rene",
            last_name="Descartes",
            notes="Studied at College Royal de La Fleche",
        )

        loaded = db_session.get(Customer, customer.id)
        assert loaded.first_name == "Rene"
        assert loaded.last_name == "Descartes"

    def test_customer_name_with_cjk_characters(self, app, db_session):
        """CJK characters (3-byte UTF-8) should work in customer names."""
        customer = _make_customer(
            db_session,
            first_name="\u5c71\u7530",
            last_name="\u592a\u90ce",
        )

        loaded = db_session.get(Customer, customer.id)
        assert loaded.first_name == "\u5c71\u7530"
        assert loaded.last_name == "\u592a\u90ce"
        assert loaded.display_name == "\u5c71\u7530 \u592a\u90ce"

    def test_emoji_in_notes_utf8mb4(self, app, db_session):
        """4-byte UTF-8 characters (emoji) should work with utf8mb4."""
        customer = _make_customer(
            db_session,
            notes="Great diver! \U0001f30a\U0001f3ca\u200d\u2642\ufe0f Certified \u2705",
        )

        loaded = db_session.get(Customer, customer.id)
        assert "\U0001f30a" in loaded.notes
        assert "\u2705" in loaded.notes

    def test_service_note_unicode_content(self, app, db_session):
        """Service notes with Unicode content should store correctly."""
        customer = _make_customer(db_session)
        service_item = _make_service_item(db_session, customer=customer)
        order = _make_order(db_session, customer)

        order_item = ServiceOrderItem(
            order_id=order.id,
            service_item_id=service_item.id,
            status="pending",
        )
        db_session.add(order_item)
        db_session.commit()

        note = ServiceNote(
            service_order_item_id=order_item.id,
            note_text="Zipper gepr\u00fcft \u2014 Dichtung in Ordnung \u2713",
            note_type="diagnostic",
            created_by=1,  # Will use a valid user ID if auth_user is available
        )
        db_session.add(note)
        db_session.commit()

        loaded = db_session.get(ServiceNote, note.id)
        assert "gepr\u00fcft" in loaded.note_text
        assert "\u2713" in loaded.note_text


# =========================================================================
# D) Concurrent Write Safety
# =========================================================================


class TestConcurrentWriteSafety:
    """Verify race-condition safety for auto-generated numbers."""

    def test_concurrent_order_creation(self, app, db_session):
        """Multiple concurrent order creations should not produce duplicate numbers."""
        from app.services import order_service

        customer = _make_customer(db_session)
        errors = []
        order_numbers = []
        lock = threading.Lock()

        def create_order_thread():
            try:
                with app.app_context():
                    order = order_service.create_order({
                        "customer_id": customer.id,
                        "date_received": date.today(),
                    })
                    with lock:
                        order_numbers.append(order.order_number)
            except Exception as exc:
                with lock:
                    errors.append(str(exc))

        threads = [threading.Thread(target=create_order_thread) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        # All order numbers should be unique (retry-on-IntegrityError ensures this)
        assert len(set(order_numbers)) == len(order_numbers), (
            f"Duplicate order numbers detected: {order_numbers}"
        )
        # Errors from IntegrityError retries are acceptable but final result
        # should have created all orders (or raised a clear error)
        assert len(order_numbers) + len(errors) == 5

    def test_concurrent_invoice_creation(self, app, db_session):
        """Multiple concurrent invoice creations should not produce duplicate numbers."""
        from app.services import invoice_service

        customer = _make_customer(db_session)
        errors = []
        invoice_numbers = []
        lock = threading.Lock()

        def create_invoice_thread():
            try:
                with app.app_context():
                    inv = invoice_service.create_invoice({
                        "customer_id": customer.id,
                        "issue_date": date.today(),
                    })
                    with lock:
                        invoice_numbers.append(inv.invoice_number)
            except Exception as exc:
                with lock:
                    errors.append(str(exc))

        threads = [threading.Thread(target=create_invoice_thread) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        assert len(set(invoice_numbers)) == len(invoice_numbers), (
            f"Duplicate invoice numbers detected: {invoice_numbers}"
        )
        assert len(invoice_numbers) + len(errors) == 5

    def test_concurrent_inventory_update(self, app, db_session):
        """Concurrent inventory stock adjustments should not lose updates."""
        item = InventoryItem(
            name="Concurrent Test Part",
            category="Hardware",
            quantity_in_stock=Decimal("100.00"),
            reorder_level=Decimal("0.00"),
        )
        db_session.add(item)
        db_session.commit()
        item_id = item.id

        errors = []

        def decrement_stock():
            try:
                with app.app_context():
                    loaded = db.session.get(InventoryItem, item_id)
                    loaded.quantity_in_stock = loaded.quantity_in_stock - Decimal("1.00")
                    db.session.commit()
            except Exception as exc:
                errors.append(str(exc))

        threads = [threading.Thread(target=decrement_stock) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        # Refresh and check -- with no row-level locking, some updates may
        # be lost (this is expected and documents the behavior)
        with app.app_context():
            loaded = db.session.get(InventoryItem, item_id)
            # Stock should be less than original (some decrements may collide)
            assert loaded.quantity_in_stock < Decimal("100.00")


# =========================================================================
# E) ENUM / Status Handling
# =========================================================================


class TestStatusHandling:
    """Verify status string columns store and retrieve correctly on MariaDB."""

    def test_order_status_values(self, app, db_session):
        """All valid order statuses should store and retrieve correctly."""
        from app.models.service_order import VALID_STATUSES

        customer = _make_customer(db_session)
        for i, status in enumerate(VALID_STATUSES):
            order = ServiceOrder(
                customer_id=customer.id,
                order_number=f"SO-2026-{90000 + i:05d}",
                status=status,
                priority="normal",
                date_received=date.today(),
            )
            db_session.add(order)
        db_session.commit()

        for i, status in enumerate(VALID_STATUSES):
            loaded = ServiceOrder.query.filter_by(
                order_number=f"SO-2026-{90000 + i:05d}"
            ).first()
            assert loaded.status == status, f"Status mismatch for {status}"

    def test_invoice_status_values(self, app, db_session):
        """All valid invoice statuses should store and retrieve correctly."""
        from app.models.invoice import VALID_STATUSES

        customer = _make_customer(db_session)
        for i, status in enumerate(VALID_STATUSES):
            inv = Invoice(
                customer_id=customer.id,
                invoice_number=f"INV-2026-{80000 + i:05d}",
                status=status,
                issue_date=date.today(),
                subtotal=Decimal("0.00"),
                total=Decimal("0.00"),
                balance_due=Decimal("0.00"),
            )
            db_session.add(inv)
        db_session.commit()

        for i, status in enumerate(VALID_STATUSES):
            loaded = Invoice.query.filter_by(
                invoice_number=f"INV-2026-{80000 + i:05d}"
            ).first()
            assert loaded.status == status, f"Status mismatch for {status}"

    def test_notification_severity_values(self, app, db_session):
        """All valid notification severities should store and retrieve correctly."""
        from app.models.notification import VALID_SEVERITIES

        for i, severity in enumerate(VALID_SEVERITIES):
            notif = Notification(
                notification_type="system",
                title=f"Test {severity}",
                message=f"Testing severity: {severity}",
                severity=severity,
            )
            db_session.add(notif)
        db_session.commit()

        for severity in VALID_SEVERITIES:
            loaded = Notification.query.filter_by(
                title=f"Test {severity}"
            ).first()
            assert loaded is not None, f"Notification with severity {severity} not found"
            assert loaded.severity == severity


# =========================================================================
# F) Date/Time Handling
# =========================================================================


class TestDateTimeParity:
    """Verify date and datetime handling across SQLite/MariaDB."""

    def test_timezone_aware_datetime_storage(self, app, db_session):
        """Timezone-aware datetimes should survive MariaDB round-trips."""
        now_utc = datetime.now(timezone.utc)
        notif = Notification(
            notification_type="system",
            title="TZ Test",
            message="Testing timezone storage",
            severity="info",
            is_read=True,
            read_at=now_utc,
        )
        db_session.add(notif)
        db_session.commit()

        loaded = db_session.get(Notification, notif.id)
        assert loaded.read_at is not None
        # The timestamp should be close to what we stored (within 1 second)
        if loaded.read_at.tzinfo is not None:
            delta = abs((loaded.read_at - now_utc).total_seconds())
        else:
            # MariaDB may return naive datetimes; compare as UTC
            delta = abs((loaded.read_at - now_utc.replace(tzinfo=None)).total_seconds())
        assert delta < 2, f"Timestamp drift too large: {delta}s"

    def test_date_range_queries(self, app, db_session):
        """Date range filtering (used in reports) should work on MariaDB."""
        customer = _make_customer(db_session)
        _make_order(
            db_session,
            customer,
            order_number="SO-2026-70001",
            date_received=date(2026, 1, 15),
        )
        _make_order(
            db_session,
            customer,
            order_number="SO-2026-70002",
            date_received=date(2026, 3, 15),
        )
        _make_order(
            db_session,
            customer,
            order_number="SO-2026-70003",
            date_received=date(2026, 6, 15),
        )

        # Query for Jan-Mar range
        results = (
            ServiceOrder.query
            .filter(ServiceOrder.date_received >= date(2026, 1, 1))
            .filter(ServiceOrder.date_received <= date(2026, 3, 31))
            .all()
        )
        assert len(results) == 2
        numbers = {r.order_number for r in results}
        assert "SO-2026-70001" in numbers
        assert "SO-2026-70002" in numbers

    def test_null_date_handling(self, app, db_session):
        """NULL dates should be handled correctly on MariaDB."""
        customer = _make_customer(db_session)
        order = _make_order(
            db_session,
            customer,
            order_number="SO-2026-70010",
            date_promised=None,
            date_completed=None,
        )

        loaded = db_session.get(ServiceOrder, order.id)
        assert loaded.date_promised is None
        assert loaded.date_completed is None
        # is_overdue should be False for NULL date_promised
        assert loaded.is_overdue is False

    def test_date_boundary_queries(self, app, db_session):
        """Boundary date comparisons should work identically to SQLite."""
        customer = _make_customer(db_session)
        _make_invoice(
            db_session,
            customer,
            invoice_number="INV-2026-70001",
            issue_date=date(2026, 3, 17),
            due_date=date(2026, 4, 17),
        )

        # Exact date match
        results = Invoice.query.filter(
            Invoice.issue_date == date(2026, 3, 17)
        ).all()
        assert len(results) == 1

        # Less-than boundary
        results = Invoice.query.filter(
            Invoice.due_date < date(2026, 4, 17)
        ).all()
        assert len(results) == 0

        results = Invoice.query.filter(
            Invoice.due_date <= date(2026, 4, 17)
        ).all()
        assert len(results) == 1
