"""Tests verifying that notification triggers are wired into service operations.

Each test performs a service operation and verifies that the appropriate
notification function is called with the correct arguments.  Also verifies
that notification failures never break the main service flow.
"""

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from app.extensions import db
from app.services import inventory_service, invoice_service, order_service
from tests.factories import (
    CustomerFactory,
    InventoryItemFactory,
    InvoiceFactory,
    ServiceOrderFactory,
    UserFactory,
)


def _set_session(db_session, *factories):
    for f in factories:
        f._meta.sqlalchemy_session = db_session


# ── Order status change notifications ──────────────────────────────────


class TestOrderStatusChangeNotification:
    """Verify notify_order_status_change is called on status transitions."""

    def test_status_change_triggers_notification(self, app, db_session):
        _set_session(db_session, ServiceOrderFactory, CustomerFactory, UserFactory)
        order = ServiceOrderFactory(status="intake")
        db_session.commit()

        with patch(
            "app.services.order_service.notification_service.notify_order_status_change"
        ) as mock_notify:
            result_order, success = order_service.change_status(
                order.id, "assessment"
            )
            assert success is True
            mock_notify.assert_called_once_with(result_order, "intake", "assessment")

    def test_failed_status_change_does_not_trigger(self, app, db_session):
        _set_session(db_session, ServiceOrderFactory, CustomerFactory, UserFactory)
        order = ServiceOrderFactory(status="intake")
        db_session.commit()

        with patch(
            "app.services.order_service.notification_service.notify_order_status_change"
        ) as mock_notify:
            # "intake" -> "completed" is not a valid transition
            _, success = order_service.change_status(order.id, "completed")
            assert success is False
            mock_notify.assert_not_called()

    def test_notification_failure_does_not_break_status_change(self, app, db_session):
        _set_session(db_session, ServiceOrderFactory, CustomerFactory, UserFactory)
        order = ServiceOrderFactory(status="intake")
        db_session.commit()

        with patch(
            "app.services.order_service.notification_service.notify_order_status_change",
            side_effect=RuntimeError("Notification system down"),
        ):
            result_order, success = order_service.change_status(
                order.id, "assessment"
            )
            assert success is True
            assert result_order.status == "assessment"


# ── Low stock notifications ────────────────────────────────────────────


class TestLowStockNotification:
    """Verify notify_low_stock is called when stock drops to/below reorder level."""

    def test_stock_below_reorder_triggers_notification(self, app, db_session):
        _set_session(db_session, InventoryItemFactory)
        item = InventoryItemFactory(quantity_in_stock=Decimal("10"), reorder_level=Decimal("5"))
        db_session.commit()

        with patch(
            "app.services.inventory_service.notification_service.notify_low_stock"
        ) as mock_notify:
            # Adjust stock down to 3 (below reorder level of 5)
            result = inventory_service.adjust_stock(item.id, Decimal("-7"), "test")
            assert result.quantity_in_stock == Decimal("3")
            mock_notify.assert_called_once_with(result)

    def test_stock_at_reorder_triggers_notification(self, app, db_session):
        _set_session(db_session, InventoryItemFactory)
        item = InventoryItemFactory(quantity_in_stock=Decimal("10"), reorder_level=Decimal("5"))
        db_session.commit()

        with patch(
            "app.services.inventory_service.notification_service.notify_low_stock"
        ) as mock_notify:
            # Adjust stock down to exactly 5 (equal to reorder level)
            result = inventory_service.adjust_stock(item.id, Decimal("-5"), "test")
            assert result.quantity_in_stock == Decimal("5")
            mock_notify.assert_called_once_with(result)

    def test_stock_above_reorder_does_not_trigger(self, app, db_session):
        _set_session(db_session, InventoryItemFactory)
        item = InventoryItemFactory(quantity_in_stock=Decimal("10"), reorder_level=Decimal("5"))
        db_session.commit()

        with patch(
            "app.services.inventory_service.notification_service.notify_low_stock"
        ) as mock_notify:
            # Adjust stock down to 8 (still above reorder level of 5)
            result = inventory_service.adjust_stock(item.id, Decimal("-2"), "test")
            assert result.quantity_in_stock == Decimal("8")
            mock_notify.assert_not_called()

    def test_stock_increase_above_reorder_does_not_trigger(self, app, db_session):
        _set_session(db_session, InventoryItemFactory)
        item = InventoryItemFactory(quantity_in_stock=Decimal("10"), reorder_level=Decimal("5"))
        db_session.commit()

        with patch(
            "app.services.inventory_service.notification_service.notify_low_stock"
        ) as mock_notify:
            result = inventory_service.adjust_stock(item.id, Decimal("5"), "restock")
            assert result.quantity_in_stock == Decimal("15")
            mock_notify.assert_not_called()

    def test_no_reorder_level_does_not_trigger(self, app, db_session):
        _set_session(db_session, InventoryItemFactory)
        item = InventoryItemFactory(
            quantity_in_stock=Decimal("10"), reorder_level=None
        )
        db_session.commit()

        with patch(
            "app.services.inventory_service.notification_service.notify_low_stock"
        ) as mock_notify:
            result = inventory_service.adjust_stock(item.id, Decimal("-8"), "test")
            assert result.quantity_in_stock == Decimal("2")
            mock_notify.assert_not_called()

    def test_notification_failure_does_not_break_stock_adjust(self, app, db_session):
        _set_session(db_session, InventoryItemFactory)
        item = InventoryItemFactory(quantity_in_stock=Decimal("10"), reorder_level=Decimal("5"))
        db_session.commit()

        with patch(
            "app.services.inventory_service.notification_service.notify_low_stock",
            side_effect=RuntimeError("Notification system down"),
        ):
            result = inventory_service.adjust_stock(item.id, Decimal("-8"), "test")
            assert result.quantity_in_stock == Decimal("2")


# ── Payment received notifications ─────────────────────────────────────


class TestPaymentReceivedNotification:
    """Verify notify_payment_received is called when a payment is recorded."""

    def test_payment_triggers_notification(self, app, db_session):
        _set_session(
            db_session, InvoiceFactory, CustomerFactory, UserFactory
        )
        invoice = InvoiceFactory(
            status="sent",
            total=Decimal("100.00"),
            balance_due=Decimal("100.00"),
            amount_paid=Decimal("0.00"),
        )
        db_session.commit()

        payment_data = {
            "payment_type": "payment",
            "amount": Decimal("50.00"),
            "payment_date": date.today(),
            "payment_method": "cash",
        }

        with patch(
            "app.services.invoice_service.notification_service.notify_payment_received"
        ) as mock_notify:
            payment = invoice_service.record_payment(invoice.id, payment_data)
            assert payment is not None
            mock_notify.assert_called_once()
            call_args = mock_notify.call_args
            assert call_args[0][0].id == invoice.id
            assert call_args[0][1].id == payment.id

    def test_notification_failure_does_not_break_payment(self, app, db_session):
        _set_session(
            db_session, InvoiceFactory, CustomerFactory, UserFactory
        )
        invoice = InvoiceFactory(
            status="sent",
            total=Decimal("100.00"),
            balance_due=Decimal("100.00"),
            amount_paid=Decimal("0.00"),
        )
        db_session.commit()

        payment_data = {
            "payment_type": "payment",
            "amount": Decimal("50.00"),
            "payment_date": date.today(),
            "payment_method": "cash",
        }

        with patch(
            "app.services.invoice_service.notification_service.notify_payment_received",
            side_effect=RuntimeError("Notification system down"),
        ):
            payment = invoice_service.record_payment(invoice.id, payment_data)
            assert payment is not None
            assert payment.amount == Decimal("50.00")
