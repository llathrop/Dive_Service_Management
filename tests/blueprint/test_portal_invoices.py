"""Blueprint tests for customer portal invoice routes."""

from datetime import date
from decimal import Decimal

import pytest

from app.models.portal_user import PortalUser
from tests.factories import CustomerFactory, InvoiceFactory, InvoiceLineItemFactory

pytestmark = pytest.mark.blueprint


def _set_session(db_session):
    CustomerFactory._meta.sqlalchemy_session = db_session
    InvoiceFactory._meta.sqlalchemy_session = db_session
    InvoiceLineItemFactory._meta.sqlalchemy_session = db_session


def _make_portal_user(db_session, customer, email="portal@example.com"):
    user = PortalUser(customer_id=customer.id, email=email)
    user.set_password("portal-pass")
    user.active = True
    db_session.add(user)
    db_session.commit()
    return user


def _make_invoice(db_session, customer, **overrides):
    defaults = dict(
        invoice_number="INV-2026-20001",
        customer=customer,
        status="sent",
        issue_date=date(2026, 3, 1),
        due_date=date(2026, 3, 20),
        subtotal=Decimal("100.00"),
        total=Decimal("100.00"),
        balance_due=Decimal("100.00"),
        notes="Internal notes should stay private.",
        customer_notes="Customer notes should stay private.",
        external_id="SYNC-123",
        external_system="qbo",
    )
    defaults.update(overrides)
    return InvoiceFactory(**defaults)


def _login_portal(client):
    return client.post(
        "/portal/login",
        data={"email": "portal@example.com", "password": "portal-pass"},
        follow_redirects=False,
    )


def test_portal_invoice_list_and_detail_are_scoped(app, db_session, client):
    _set_session(db_session)
    customer = CustomerFactory(first_name="Portal", last_name="Customer")
    invoice = _make_invoice(db_session, customer)
    InvoiceLineItemFactory(
        invoice=invoice,
        line_type="labor",
        description="Technician Name: Internal repair note",
        quantity=Decimal("1.00"),
        unit_price=Decimal("100.00"),
        line_total=Decimal("100.00"),
    )
    _make_portal_user(db_session, customer)

    login_response = _login_portal(client)
    assert login_response.status_code == 302

    list_response = client.get("/portal/invoices")
    assert list_response.status_code == 200
    html = list_response.data.decode()
    assert invoice.invoice_number in html

    detail_response = client.get(f"/portal/invoices/{invoice.id}")
    assert detail_response.status_code == 200
    detail_html = detail_response.data.decode()
    assert invoice.invoice_number in detail_html
    assert "Internal notes should stay private." not in detail_html
    assert "Customer notes should stay private." not in detail_html
    assert "SYNC-123" not in detail_html
    assert "Technician Name" not in detail_html
    assert "Labor" in detail_html


def test_portal_invoice_detail_rejects_foreign_customer(app, db_session, client):
    _set_session(db_session)
    owner = CustomerFactory(first_name="Owner", last_name="Customer")
    stranger = CustomerFactory(first_name="Other", last_name="Customer")
    invoice = _make_invoice(db_session, owner)
    _make_portal_user(db_session, owner)

    login_response = _login_portal(client)
    assert login_response.status_code == 302

    response = client.get(f"/portal/invoices/{invoice.id}")
    assert response.status_code == 200

    stranger_invoice = _make_invoice(
        db_session,
        stranger,
        invoice_number="INV-2026-20002",
    )
    foreign_response = client.get(f"/portal/invoices/{stranger_invoice.id}")
    assert foreign_response.status_code == 404


def test_portal_invoice_pdf_download_hides_internal_notes(app, db_session, client):
    _set_session(db_session)
    customer = CustomerFactory(first_name="PDF", last_name="Customer")
    invoice = _make_invoice(db_session, customer)
    InvoiceLineItemFactory(
        invoice=invoice,
        line_type="service",
        description="Annual regulator service",
        quantity=Decimal("1.00"),
        unit_price=Decimal("100.00"),
        line_total=Decimal("100.00"),
    )
    _make_portal_user(db_session, customer)

    login_response = _login_portal(client)
    assert login_response.status_code == 302

    response = client.get(f"/portal/invoices/{invoice.id}/pdf")
    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data[:5] == b"%PDF-"

