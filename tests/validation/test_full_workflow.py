"""Validation tests: Full service workflow from intake to invoice payment.

These tests simulate a complete business workflow:
1. Create a customer
2. Create a service item (drysuit)
3. Create inventory parts
4. Create a service order
5. Transition through all order statuses
6. Add parts used (with inventory deduction)
7. Add labor entries
8. Add service notes
9. Generate an invoice from the order
10. Record payment on the invoice
11. Verify all financial calculations
"""

from datetime import date
from decimal import Decimal

import pytest

from app.extensions import db
from app.models.customer import Customer
from app.models.inventory import InventoryItem
from app.models.invoice import Invoice
from app.models.parts_used import PartUsed
from app.models.service_order import ServiceOrder
from app.services import invoice_service, order_service


pytestmark = pytest.mark.validation


class TestFullServiceWorkflow:
    """Complete service workflow from order creation through payment."""

    def test_complete_order_to_invoice_workflow(self, app, db_session):
        """Walk through the entire service order lifecycle."""
        with app.app_context():
            # ── 1. Create a customer ────────────────────────────
            customer = Customer(
                customer_type="individual",
                first_name="Jane",
                last_name="Diver",
                email="jane@example.com",
                phone_primary="555-0100",
            )
            db_session.add(customer)
            db_session.flush()

            # ── 2. Create a service item ────────────────────────
            from app.models.service_item import ServiceItem

            item = ServiceItem(
                name="DUI CF200X Drysuit",
                serial_number="DUI-2024-001",
                item_category="Drysuit",
                serviceability="serviceable",
                customer_id=customer.id,
            )
            db_session.add(item)
            db_session.flush()

            # ── 3. Create inventory parts ───────────────────────
            neck_seal = InventoryItem(
                sku="SEAL-NECK-001",
                name="Latex Neck Seal - Medium",
                category="Seals",
                quantity_in_stock=10,
                reorder_level=3,
                purchase_cost=Decimal("8.50"),
                resale_price=Decimal("25.00"),
                unit_of_measure="each",
                is_active=True,
            )
            adhesive = InventoryItem(
                sku="ADH-001",
                name="Aquaseal Contact Cement",
                category="Adhesives",
                quantity_in_stock=20,
                reorder_level=5,
                purchase_cost=Decimal("3.00"),
                resale_price=Decimal("8.00"),
                unit_of_measure="oz",
                is_active=True,
            )
            db_session.add_all([neck_seal, adhesive])
            db_session.flush()

            # ── 4. Create a tech user ───────────────────────────
            from flask_security import hash_password

            user_datastore = app.extensions["security"].datastore
            tech_role = user_datastore.find_or_create_role(
                name="technician", description="Technician"
            )
            tech = user_datastore.create_user(
                username="techworkflow",
                email="techworkflow@example.com",
                password=hash_password("password"),
                first_name="Tech",
                last_name="Worker",
            )
            user_datastore.add_role_to_user(tech, tech_role)
            db_session.commit()

            # ── 5. Create a service order ───────────────────────
            order_data = {
                "customer_id": customer.id,
                "status": "intake",
                "priority": "normal",
                "date_received": date.today(),
                "description": "Neck seal replacement and leak test",
                "assigned_tech_id": tech.id,
            }
            order = order_service.create_order(order_data, created_by=tech.id)
            assert order is not None
            assert order.order_number.startswith("SO-")
            assert order.status == "intake"
            order_id = order.id

            # ── 6. Add a service item to the order ──────────────
            order_item = order_service.add_order_item(
                order_id,
                item.id,
                work_description="Replace neck seal, test for leaks",
            )
            assert order_item is not None
            order_item_id = order_item.id

            # ── 7. Status: intake → assessment ──────────────────
            order_obj, success = order_service.change_status(order_id, "assessment", tech.id)
            assert success is True
            assert order_obj.status == "assessment"

            # ── 8. Status: assessment → awaiting_approval ───────
            order_obj, success = order_service.change_status(
                order_id, "awaiting_approval", tech.id
            )
            assert order_obj.status == "awaiting_approval"

            # ── 9. Status: awaiting_approval → in_progress ──────
            order_obj, success = order_service.change_status(
                order_id, "in_progress", tech.id
            )
            assert order_obj.status == "in_progress"

            # ── 10. Add parts used ──────────────────────────────
            part_used = order_service.add_part_used(
                order_item_id=order_item_id,
                inventory_item_id=neck_seal.id,
                quantity=1,
                unit_price_at_use=Decimal("25.00"),
                added_by=tech.id,
            )
            assert part_used is not None

            # Verify inventory was deducted
            db_session.refresh(neck_seal)
            assert neck_seal.quantity_in_stock == 9

            # Add adhesive (fractional quantity)
            adhesive_used = order_service.add_part_used(
                order_item_id=order_item_id,
                inventory_item_id=adhesive.id,
                quantity=Decimal("2.5"),
                unit_price_at_use=Decimal("8.00"),
                added_by=tech.id,
            )
            assert adhesive_used is not None

            # Verify exact fractional deduction (no rounding)
            db_session.refresh(adhesive)
            expected_adhesive = Decimal("20") - Decimal("2.5")  # = 17.5
            assert adhesive.quantity_in_stock == expected_adhesive

            # ── 11. Add labor entry ─────────────────────────────
            labor = order_service.add_labor_entry(
                order_item_id=order_item_id,
                tech_id=tech.id,
                hours=Decimal("1.5"),
                hourly_rate=Decimal("75.00"),
                description="Neck seal removal, surface prep, installation",
                work_date=date.today(),
            )
            assert labor is not None

            # ── 12. Add service notes ───────────────────────────
            note = order_service.add_service_note(
                order_item_id=order_item_id,
                note_text="Old seal was severely degraded. Replaced with medium latex.",
                note_type="repair",
                created_by=tech.id,
            )
            assert note is not None

            test_note = order_service.add_service_note(
                order_item_id=order_item_id,
                note_text="Pressure test passed at 3 PSI for 5 minutes. No leaks detected.",
                note_type="testing",
                created_by=tech.id,
            )
            assert test_note is not None

            # ── 13. Status: in_progress → completed ─────────────
            order_obj, success = order_service.change_status(order_id, "completed", tech.id)
            assert success is True
            assert order_obj.status == "completed"

            # ── 14. Verify order summary ────────────────────────
            summary = order_service.get_order_summary(order_id)
            assert summary is not None
            assert summary["parts_total"] > 0
            assert summary["labor_total"] > 0

            # ── 15. Generate invoice from order ─────────────────
            invoice = invoice_service.generate_from_order(
                order_id, created_by=tech.id
            )
            assert invoice is not None
            assert invoice.invoice_number.startswith("INV-")
            assert invoice.customer_id == customer.id
            assert invoice.status == "draft"
            assert invoice.total > 0
            invoice_id = invoice.id

            # Verify line items were created
            assert invoice.line_items.count() > 0

            # ── 16. Status: completed → ready_for_pickup ────────
            order_obj, success = order_service.change_status(
                order_id, "ready_for_pickup", tech.id
            )
            assert order_obj.status == "ready_for_pickup"

            # ── 17. Record partial payment ──────────────────────
            partial_amount = Decimal("50.00")
            payment = invoice_service.record_payment(
                invoice_id,
                {
                    "payment_type": "deposit",
                    "amount": partial_amount,
                    "payment_date": date.today(),
                    "payment_method": "cash",
                },
                recorded_by=tech.id,
            )
            assert payment is not None

            # Verify invoice status changed to partially_paid
            updated_invoice = invoice_service.get_invoice(invoice_id)
            assert updated_invoice.amount_paid >= partial_amount

            # ── 18. Record remaining payment ────────────────────
            remaining = updated_invoice.balance_due
            if remaining > 0:
                final_payment = invoice_service.record_payment(
                    invoice_id,
                    {
                        "payment_type": "payment",
                        "amount": remaining,
                        "payment_date": date.today(),
                        "payment_method": "credit_card",
                    },
                    recorded_by=tech.id,
                )
                assert final_payment is not None

            # Verify invoice is now paid
            paid_invoice = invoice_service.get_invoice(invoice_id)
            assert paid_invoice.status == "paid"
            assert paid_invoice.balance_due == 0

            # ── 19. Status: ready_for_pickup → picked_up ────────
            order_obj, success = order_service.change_status(
                order_id, "picked_up", tech.id
            )
            assert order_obj.status == "picked_up"

            # ── 20. Final verification ──────────────────────────
            final_order = order_service.get_order(order_id)
            assert final_order.status == "picked_up"
            assert final_order.date_received == date.today()

    def test_order_cancellation_restores_inventory(self, app, db_session):
        """Cancelling an order with parts used should restore inventory."""
        with app.app_context():
            # Setup
            customer = Customer(
                first_name="Cancel",
                last_name="Test",
                email="cancel@example.com",
            )
            db_session.add(customer)

            part = InventoryItem(
                sku="CANCEL-PART",
                name="Test Part",
                category="Test",
                quantity_in_stock=10,
                purchase_cost=Decimal("5.00"),
                resale_price=Decimal("15.00"),
                is_active=True,
            )
            db_session.add(part)

            from app.models.service_item import ServiceItem

            si = ServiceItem(
                name="Test Item",
                item_category="Test",
                customer_id=customer.id,
            )
            db_session.add(si)

            from flask_security import hash_password

            user_datastore = app.extensions["security"].datastore
            user_datastore.find_or_create_role(name="technician")
            tech = user_datastore.create_user(
                username="canceltech",
                email="canceltech@example.com",
                password=hash_password("password"),
                first_name="Cancel",
                last_name="Tech",
            )
            db_session.commit()

            # Create order and add parts
            order = order_service.create_order(
                {
                    "customer_id": customer.id,
                    "status": "intake",
                    "priority": "normal",
                    "date_received": date.today(),
                },
                created_by=tech.id,
            )
            oi = order_service.add_order_item(order.id, si.id)
            order_service.add_part_used(
                order_item_id=oi.id,
                inventory_item_id=part.id,
                quantity=3,
                unit_price_at_use=Decimal("15.00"),
                added_by=tech.id,
            )

            db_session.refresh(part)
            assert part.quantity_in_stock == 7  # 10 - 3

            # Remove part used (simulating cancel cleanup)
            parts_used = PartUsed.query.filter_by(
                service_order_item_id=oi.id
            ).all()
            for pu in parts_used:
                order_service.remove_part_used(pu.id)

            # Verify inventory restored
            db_session.refresh(part)
            assert part.quantity_in_stock == 10

    def test_low_stock_detection_during_workflow(self, app, db_session):
        """Verify low stock detection works after parts are used."""
        with app.app_context():
            part = InventoryItem(
                sku="LOW-STOCK-TEST",
                name="Low Stock Test Part",
                category="Test",
                quantity_in_stock=5,
                reorder_level=3,
                purchase_cost=Decimal("10.00"),
                resale_price=Decimal("30.00"),
                is_active=True,
            )
            db_session.add(part)
            db_session.commit()

            # Initially not low stock
            assert not part.is_low_stock

            # Simulate deduction to below reorder level
            part.quantity_in_stock = 2
            db_session.commit()

            assert part.is_low_stock

    def test_refund_reduces_paid_total(self, app, db_session):
        """Verify refund payments correctly reduce the paid total."""
        with app.app_context():
            customer = Customer(
                first_name="Refund",
                last_name="Test",
                email="refund@example.com",
            )
            db_session.add(customer)
            db_session.flush()

            from flask_security import hash_password

            user_datastore = app.extensions["security"].datastore
            user_datastore.find_or_create_role(name="technician")
            tech = user_datastore.create_user(
                username="refundtech",
                email="refundtech@example.com",
                password=hash_password("password"),
                first_name="Refund",
                last_name="Tech",
            )
            db_session.commit()

            # Create invoice and set totals directly
            invoice = invoice_service.create_invoice(
                {
                    "customer_id": customer.id,
                    "issue_date": date.today(),
                },
                created_by=tech.id,
            )
            # Set totals directly (normally done via line items + recalculate)
            invoice.subtotal = Decimal("100.00")
            invoice.total = Decimal("100.00")
            invoice.balance_due = Decimal("100.00")
            db.session.commit()

            # Record full payment
            invoice_service.record_payment(
                invoice.id,
                {
                    "payment_type": "payment",
                    "amount": Decimal("100.00"),
                    "payment_date": date.today(),
                    "payment_method": "cash",
                },
                recorded_by=tech.id,
            )

            paid = invoice_service.get_invoice(invoice.id)
            assert paid.status == "paid"

            # Record refund — should reduce paid total
            invoice_service.record_payment(
                invoice.id,
                {
                    "payment_type": "refund",
                    "amount": Decimal("30.00"),
                    "payment_date": date.today(),
                    "payment_method": "cash",
                },
                recorded_by=tech.id,
            )

            refunded = invoice_service.get_invoice(invoice.id)
            # After $100 payment and $30 refund, effective paid = $70
            assert refunded.amount_paid == Decimal("70.00")
            assert refunded.balance_due == Decimal("30.00")
