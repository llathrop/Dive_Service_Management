"""Tests for invoice PDF download and price list PDF routes."""

from datetime import date
from decimal import Decimal

import pytest

from tests.factories import (
    BaseFactory,
    CustomerFactory,
    InvoiceFactory,
    InvoiceLineItemFactory,
    PriceListCategoryFactory,
    PriceListItemFactory,
)


def _set_session(db_session):
    """Point all factories at the current test session."""
    BaseFactory._meta.sqlalchemy_session = db_session
    CustomerFactory._meta.sqlalchemy_session = db_session
    InvoiceFactory._meta.sqlalchemy_session = db_session
    InvoiceLineItemFactory._meta.sqlalchemy_session = db_session
    PriceListCategoryFactory._meta.sqlalchemy_session = db_session
    PriceListItemFactory._meta.sqlalchemy_session = db_session


# =========================================================================
# Invoice PDF route tests
# =========================================================================


class TestInvoicePDFRoute:
    """Tests for GET /invoices/<id>/pdf."""

    def test_pdf_download_returns_200(self, app, db_session, logged_in_client):
        """Authenticated technician can download invoice PDF."""
        _set_session(db_session)
        customer = CustomerFactory(first_name="Test", last_name="User")
        invoice = InvoiceFactory(
            customer=customer, invoice_number="INV-2026-00099"
        )
        InvoiceLineItemFactory(invoice=invoice, description="Test Service")

        response = logged_in_client.get(f"/invoices/{invoice.id}/pdf")
        assert response.status_code == 200

    def test_pdf_download_content_type(self, app, db_session, logged_in_client):
        """Response has application/pdf content type."""
        _set_session(db_session)
        customer = CustomerFactory(first_name="CT", last_name="Test")
        invoice = InvoiceFactory(customer=customer)

        response = logged_in_client.get(f"/invoices/{invoice.id}/pdf")
        assert response.content_type == "application/pdf"

    def test_pdf_download_attachment_disposition(self, app, db_session, logged_in_client):
        """Response has attachment Content-Disposition with filename."""
        _set_session(db_session)
        customer = CustomerFactory(first_name="Disp", last_name="Test")
        invoice = InvoiceFactory(
            customer=customer, invoice_number="INV-2026-00077"
        )

        response = logged_in_client.get(f"/invoices/{invoice.id}/pdf")
        assert "attachment" in response.headers.get("Content-Disposition", "")
        assert "INV-2026-00077.pdf" in response.headers.get("Content-Disposition", "")

    def test_pdf_inline_preview(self, app, db_session, logged_in_client):
        """With ?inline=1, Content-Disposition is 'inline'."""
        _set_session(db_session)
        customer = CustomerFactory(first_name="Inline", last_name="Test")
        invoice = InvoiceFactory(customer=customer)

        response = logged_in_client.get(f"/invoices/{invoice.id}/pdf?inline=1")
        assert response.status_code == 200
        assert "inline" in response.headers.get("Content-Disposition", "")

    def test_pdf_download_valid_pdf(self, app, db_session, logged_in_client):
        """Downloaded content starts with %PDF magic bytes."""
        _set_session(db_session)
        customer = CustomerFactory(first_name="Valid", last_name="PDF")
        invoice = InvoiceFactory(customer=customer)

        response = logged_in_client.get(f"/invoices/{invoice.id}/pdf")
        assert response.data[:5] == b"%PDF-"

    def test_pdf_requires_authentication(self, app, db_session, client):
        """Unauthenticated request is redirected to login."""
        _set_session(db_session)
        customer = CustomerFactory(first_name="Auth", last_name="Test")
        invoice = InvoiceFactory(customer=customer)

        response = client.get(f"/invoices/{invoice.id}/pdf")
        # Should redirect to login
        assert response.status_code in (302, 401)

    def test_pdf_viewer_role_forbidden(self, app, db_session, viewer_client):
        """Viewer role cannot download invoice PDF (requires admin/technician)."""
        _set_session(db_session)
        customer = CustomerFactory(first_name="Viewer", last_name="Test")
        invoice = InvoiceFactory(customer=customer)

        response = viewer_client.get(f"/invoices/{invoice.id}/pdf")
        assert response.status_code == 403

    def test_pdf_admin_can_download(self, app, db_session, admin_client):
        """Admin role can download invoice PDF."""
        _set_session(db_session)
        customer = CustomerFactory(first_name="Admin", last_name="Test")
        invoice = InvoiceFactory(customer=customer)

        response = admin_client.get(f"/invoices/{invoice.id}/pdf")
        assert response.status_code == 200
        assert response.content_type == "application/pdf"

    def test_pdf_404_nonexistent_invoice(self, app, db_session, logged_in_client):
        """Requesting PDF for non-existent invoice returns 404."""
        response = logged_in_client.get("/invoices/99999/pdf")
        assert response.status_code == 404


# =========================================================================
# Price List PDF route tests
# =========================================================================


class TestPriceListPDFRoute:
    """Tests for GET /price-list/pdf."""

    def test_price_list_pdf_returns_200(self, app, db_session, logged_in_client):
        """Authenticated user can download price list PDF."""
        _set_session(db_session)
        cat = PriceListCategoryFactory(name="Test Category")
        PriceListItemFactory(
            category=cat, name="Test Item", price=Decimal("50.00")
        )

        response = logged_in_client.get("/price-list/pdf")
        assert response.status_code == 200
        assert response.content_type == "application/pdf"

    def test_price_list_pdf_valid_content(self, app, db_session, logged_in_client):
        """Price list PDF starts with %PDF magic bytes."""
        _set_session(db_session)
        cat = PriceListCategoryFactory(name="PDF Cat")
        PriceListItemFactory(category=cat, name="PDF Item")

        response = logged_in_client.get("/price-list/pdf")
        assert response.data[:5] == b"%PDF-"

    def test_price_list_pdf_attachment(self, app, db_session, logged_in_client):
        """Price list PDF has correct Content-Disposition."""
        response = logged_in_client.get("/price-list/pdf")
        assert "price-list.pdf" in response.headers.get("Content-Disposition", "")

    def test_price_list_pdf_requires_auth(self, app, db_session, client):
        """Unauthenticated request is redirected."""
        response = client.get("/price-list/pdf")
        assert response.status_code in (302, 401)

    def test_price_list_pdf_inline(self, app, db_session, logged_in_client):
        """With ?inline=1, Content-Disposition is 'inline'."""
        response = logged_in_client.get("/price-list/pdf?inline=1")
        assert response.status_code == 200
        assert "inline" in response.headers.get("Content-Disposition", "")

    def test_price_list_pdf_empty(self, app, db_session, logged_in_client):
        """Price list PDF generates even with no categories/items."""
        response = logged_in_client.get("/price-list/pdf")
        assert response.status_code == 200
        assert response.data[:5] == b"%PDF-"
