"""Blueprint tests for invoice routes.

Tests listing, creating, viewing, editing, and voiding invoices via
the invoices blueprint.  Verifies role-based access control for
anonymous, viewer, technician, and admin users, as well as line item
management, payment recording, and status changes.
"""

from datetime import date
from decimal import Decimal

import pytest

from app.extensions import db
from app.models.customer import Customer
from app.models.invoice import Invoice, InvoiceLineItem
from app.models.payment import Payment

pytestmark = pytest.mark.blueprint


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_customer(db_session, **overrides):
    """Create and persist a Customer with sensible defaults."""
    defaults = dict(
        customer_type="individual",
        first_name="Jane",
        last_name="Diver",
        email="jane@example.com",
        phone_primary="555-0100",
    )
    defaults.update(overrides)
    customer = Customer(**defaults)
    db.session.add(customer)
    db.session.commit()
    return customer


def _create_invoice(db_session, customer=None, **overrides):
    """Create and persist an Invoice with sensible defaults."""
    if customer is None:
        customer = _create_customer(db_session)
    defaults = dict(
        invoice_number="INV-2026-00001",
        customer_id=customer.id,
        status="draft",
        issue_date=date.today(),
        subtotal=Decimal("100.00"),
        total=Decimal("100.00"),
        balance_due=Decimal("100.00"),
    )
    defaults.update(overrides)
    invoice = Invoice(**defaults)
    db.session.add(invoice)
    db.session.commit()
    return invoice


def _create_invoice_with_line_item(db_session, customer=None):
    """Create an invoice with a customer and one line item."""
    if customer is None:
        customer = _create_customer(db_session)
    invoice = _create_invoice(db_session, customer=customer)
    line_item = InvoiceLineItem(
        invoice_id=invoice.id,
        line_type="service",
        description="Test Service",
        quantity=Decimal("1.00"),
        unit_price=Decimal("100.00"),
        line_total=Decimal("100.00"),
    )
    db.session.add(line_item)
    db.session.commit()
    return invoice, line_item, customer


# ---------------------------------------------------------------------------
# Anonymous access (should redirect to login)
# ---------------------------------------------------------------------------

class TestUnauthenticated:
    """Anonymous users are redirected to the login page."""

    def test_list_redirects(self, client):
        response = client.get("/invoices/")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_detail_redirects(self, client, app, db_session):
        with app.app_context():
            invoice = _create_invoice(db_session)
            inv_id = invoice.id
        response = client.get(f"/invoices/{inv_id}")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_create_get_redirects(self, client):
        response = client.get("/invoices/new")
        assert response.status_code == 302
        assert "/login" in response.location

    def test_create_post_redirects(self, client):
        response = client.post("/invoices/new", data={"customer_id": "1"})
        assert response.status_code == 302
        assert "/login" in response.location


# ---------------------------------------------------------------------------
# Viewer role (read-only -- 403 on write operations)
# ---------------------------------------------------------------------------

class TestViewerAccess:
    """Viewer users can list/view invoices but get 403 on write operations."""

    def test_viewer_can_list_invoices(self, viewer_client, app, db_session):
        response = viewer_client.get("/invoices/")
        assert response.status_code == 200

    def test_viewer_can_view_invoice_detail(self, viewer_client, app, db_session):
        with app.app_context():
            invoice = _create_invoice(db_session)
            inv_id = invoice.id
        response = viewer_client.get(f"/invoices/{inv_id}")
        assert response.status_code == 200

    def test_viewer_cannot_create_invoice(self, viewer_client):
        response = viewer_client.get("/invoices/new")
        assert response.status_code == 403

    def test_viewer_cannot_create_invoice_post(self, viewer_client, app, db_session):
        with app.app_context():
            customer = _create_customer(db_session)
            cid = customer.id
        response = viewer_client.post(
            "/invoices/new",
            data={
                "customer_id": str(cid),
                "issue_date": date.today().isoformat(),
                "status": "draft",
            },
        )
        assert response.status_code == 403

    def test_viewer_cannot_edit_invoice(self, viewer_client, app, db_session):
        with app.app_context():
            invoice = _create_invoice(db_session)
            inv_id = invoice.id
        response = viewer_client.get(f"/invoices/{inv_id}/edit")
        assert response.status_code == 403

    def test_viewer_cannot_void_invoice(self, viewer_client, app, db_session):
        with app.app_context():
            invoice = _create_invoice(db_session)
            inv_id = invoice.id
        response = viewer_client.post(f"/invoices/{inv_id}/void")
        assert response.status_code == 403

    def test_viewer_cannot_change_status(self, viewer_client, app, db_session):
        with app.app_context():
            invoice = _create_invoice(db_session)
            inv_id = invoice.id
        response = viewer_client.post(
            f"/invoices/{inv_id}/status",
            data={"new_status": "sent"},
        )
        assert response.status_code == 403


# ---------------------------------------------------------------------------
# Technician role (can create/edit but not void)
# ---------------------------------------------------------------------------

class TestTechnicianAccess:
    """Technician users can create and edit invoices but cannot void."""

    def test_tech_can_list_invoices(self, logged_in_client, app, db_session):
        response = logged_in_client.get("/invoices/")
        assert response.status_code == 200

    def test_tech_can_view_invoice_detail(self, logged_in_client, app, db_session):
        with app.app_context():
            invoice = _create_invoice(db_session)
            inv_id = invoice.id
        response = logged_in_client.get(f"/invoices/{inv_id}")
        assert response.status_code == 200

    def test_tech_cannot_void_invoice(self, logged_in_client, app, db_session):
        """Technicians cannot void invoices (admin-only)."""
        with app.app_context():
            invoice = _create_invoice(db_session)
            inv_id = invoice.id
        response = logged_in_client.post(f"/invoices/{inv_id}/void")
        assert response.status_code == 403

    def test_tech_can_change_status(self, logged_in_client, app, db_session):
        with app.app_context():
            invoice = _create_invoice(db_session, status="draft")
            inv_id = invoice.id
        response = logged_in_client.post(
            f"/invoices/{inv_id}/status",
            data={"new_status": "sent"},
            follow_redirects=False,
        )
        assert response.status_code == 302

    def test_tech_can_add_line_item(self, logged_in_client, app, db_session):
        with app.app_context():
            invoice = _create_invoice(db_session)
            inv_id = invoice.id
        response = logged_in_client.post(
            f"/invoices/{inv_id}/line-items/add",
            data={
                "line_type": "service",
                "description": "Test Service",
                "quantity": "1.00",
                "unit_price": "100.00",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

    def test_tech_can_add_payment(self, logged_in_client, app, db_session):
        with app.app_context():
            invoice = _create_invoice(db_session)
            inv_id = invoice.id
        response = logged_in_client.post(
            f"/invoices/{inv_id}/payments/add",
            data={
                "payment_type": "payment",
                "amount": "50.00",
                "payment_date": date.today().isoformat(),
                "payment_method": "cash",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302


# ---------------------------------------------------------------------------
# Admin role (full access)
# ---------------------------------------------------------------------------

class TestAdminCRUD:
    """Admin users have full access to invoice routes."""

    def test_admin_can_list_invoices(self, admin_client, app, db_session):
        response = admin_client.get("/invoices/")
        assert response.status_code == 200

    def test_admin_can_view_create_form(self, admin_client, app, db_session):
        response = admin_client.get("/invoices/new")
        assert response.status_code == 200

    def test_admin_can_create_invoice(self, admin_client, app, db_session):
        with app.app_context():
            customer = _create_customer(db_session)
            cid = customer.id
        response = admin_client.post(
            "/invoices/new",
            data={
                "customer_id": str(cid),
                "status": "draft",
                "issue_date": date.today().isoformat(),
                "tax_rate": "0.0000",
                "discount_amount": "0.00",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        with app.app_context():
            invoice = Invoice.query.filter_by(customer_id=cid).first()
            assert invoice is not None

    def test_admin_can_view_invoice_detail(self, admin_client, app, db_session):
        with app.app_context():
            invoice = _create_invoice(db_session)
            inv_id = invoice.id
        response = admin_client.get(f"/invoices/{inv_id}")
        assert response.status_code == 200

    def test_admin_can_edit_invoice(self, admin_client, app, db_session):
        with app.app_context():
            invoice = _create_invoice(db_session)
            inv_id = invoice.id
            cid = invoice.customer_id
        response = admin_client.post(
            f"/invoices/{inv_id}/edit",
            data={
                "customer_id": str(cid),
                "status": "sent",
                "issue_date": date.today().isoformat(),
                "tax_rate": "0.0000",
                "discount_amount": "0.00",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        with app.app_context():
            updated = db.session.get(Invoice, inv_id)
            assert updated.status == "sent"

    def test_admin_can_void_invoice(self, admin_client, app, db_session):
        with app.app_context():
            invoice = _create_invoice(db_session, status="sent")
            inv_id = invoice.id
        response = admin_client.post(
            f"/invoices/{inv_id}/void",
            follow_redirects=False,
        )
        assert response.status_code == 302

        with app.app_context():
            updated = db.session.get(Invoice, inv_id)
            assert updated.status == "void"

    def test_admin_can_change_status(self, admin_client, app, db_session):
        with app.app_context():
            invoice = _create_invoice(db_session, status="draft")
            inv_id = invoice.id
        response = admin_client.post(
            f"/invoices/{inv_id}/status",
            data={"new_status": "sent"},
            follow_redirects=False,
        )
        assert response.status_code == 302

        with app.app_context():
            updated = db.session.get(Invoice, inv_id)
            assert updated.status == "sent"


# ---------------------------------------------------------------------------
# Line item management
# ---------------------------------------------------------------------------

class TestLineItemRoutes:
    """Tests for adding and removing line items via routes."""

    def test_add_line_item_to_invoice(self, admin_client, app, db_session):
        with app.app_context():
            invoice = _create_invoice(db_session)
            inv_id = invoice.id
        response = admin_client.post(
            f"/invoices/{inv_id}/line-items/add",
            data={
                "line_type": "service",
                "description": "Regulator Service",
                "quantity": "1.00",
                "unit_price": "150.00",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        with app.app_context():
            items = InvoiceLineItem.query.filter_by(invoice_id=inv_id).all()
            assert len(items) == 1
            assert items[0].description == "Regulator Service"

    def test_remove_line_item_from_invoice(self, admin_client, app, db_session):
        with app.app_context():
            invoice, line_item, _ = _create_invoice_with_line_item(db_session)
            inv_id = invoice.id
            item_id = line_item.id
        response = admin_client.post(
            f"/invoices/line-items/{item_id}/remove",
            follow_redirects=False,
        )
        assert response.status_code == 302

        with app.app_context():
            items = InvoiceLineItem.query.filter_by(invoice_id=inv_id).all()
            assert len(items) == 0


# ---------------------------------------------------------------------------
# Payment recording
# ---------------------------------------------------------------------------

class TestPaymentRoutes:
    """Tests for recording payments via routes."""

    def test_add_payment_to_invoice(self, admin_client, app, db_session):
        with app.app_context():
            invoice = _create_invoice(db_session)
            inv_id = invoice.id
        response = admin_client.post(
            f"/invoices/{inv_id}/payments/add",
            data={
                "payment_type": "payment",
                "amount": "50.00",
                "payment_date": date.today().isoformat(),
                "payment_method": "cash",
            },
            follow_redirects=False,
        )
        assert response.status_code == 302

        with app.app_context():
            payments = Payment.query.filter_by(invoice_id=inv_id).all()
            assert len(payments) == 1
            assert payments[0].amount == Decimal("50.00")


# ---------------------------------------------------------------------------
# Search / filter
# ---------------------------------------------------------------------------

class TestInvoiceSearch:
    """Verify search and filter query parameters on the list page."""

    def test_search_by_invoice_number(self, logged_in_client, app, db_session):
        with app.app_context():
            _create_invoice(db_session, invoice_number="INV-2026-99999")
        response = logged_in_client.get("/invoices/?q=99999")
        assert response.status_code == 200
        assert b"INV-2026-99999" in response.data

    def test_filter_by_status(self, logged_in_client, app, db_session):
        with app.app_context():
            _create_invoice(
                db_session,
                status="sent",
                invoice_number="INV-2026-88888",
            )
        response = logged_in_client.get("/invoices/?status=sent")
        assert response.status_code == 200
        assert b"INV-2026-88888" in response.data
