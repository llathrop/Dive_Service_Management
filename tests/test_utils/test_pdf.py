"""Tests for app/utils/pdf.py -- invoice and price list PDF generation."""

import re
import zlib
from datetime import date
from decimal import Decimal

import pytest

from tests.factories import (
    BaseFactory,
    CustomerFactory,
    InvoiceFactory,
    InvoiceLineItemFactory,
    PaymentFactory,
    PriceListCategoryFactory,
    PriceListItemFactory,
)

pytestmark = pytest.mark.unit


def _set_session(db_session):
    """Point all factories at the current test session."""
    BaseFactory._meta.sqlalchemy_session = db_session
    CustomerFactory._meta.sqlalchemy_session = db_session
    InvoiceFactory._meta.sqlalchemy_session = db_session
    InvoiceLineItemFactory._meta.sqlalchemy_session = db_session
    PaymentFactory._meta.sqlalchemy_session = db_session
    PriceListCategoryFactory._meta.sqlalchemy_session = db_session
    PriceListItemFactory._meta.sqlalchemy_session = db_session


def _extract_pdf_text(pdf_bytes):
    """Extract visible text from PDF by decompressing content streams.

    fpdf2 compresses page streams with zlib.  This helper decompresses
    all streams and concatenates the text found in PDF text operators
    (Tj and TJ).
    """
    raw = bytes(pdf_bytes)
    streams = re.findall(rb"stream\r?\n(.+?)\r?\nendstream", raw, re.DOTALL)
    text_parts = []
    for stream in streams:
        try:
            decompressed = zlib.decompress(stream)
        except zlib.error:
            decompressed = stream
        # Extract text from Tj operator: (some text) Tj
        tj_matches = re.findall(rb"\((.+?)\)\s*Tj", decompressed)
        text_parts.extend(m.decode("latin-1", errors="replace") for m in tj_matches)
        # Extract text from TJ operator: [(text) kern (text)] TJ
        tj_array_matches = re.findall(rb"\[(.+?)\]\s*TJ", decompressed)
        for arr in tj_array_matches:
            inner = re.findall(rb"\((.+?)\)", arr)
            text_parts.extend(m.decode("latin-1", errors="replace") for m in inner)
    return " ".join(text_parts)


# =========================================================================
# Invoice PDF tests
# =========================================================================


class TestInvoicePDFGeneration:
    """Tests for generate_invoice_pdf()."""

    def test_pdf_returns_valid_bytes(self, app, db_session):
        """PDF output starts with the %PDF magic bytes."""
        _set_session(db_session)
        customer = CustomerFactory(first_name="John", last_name="Doe")
        invoice = InvoiceFactory(customer=customer, invoice_number="INV-2026-00001")

        from app.utils.pdf import generate_invoice_pdf

        pdf_bytes = generate_invoice_pdf(invoice)
        assert isinstance(pdf_bytes, (bytes, bytearray))
        assert pdf_bytes[:5] == b"%PDF-"

    def test_pdf_contains_invoice_number(self, app, db_session):
        """The invoice number appears in the PDF content."""
        _set_session(db_session)
        customer = CustomerFactory(first_name="Jane", last_name="Smith")
        invoice = InvoiceFactory(
            customer=customer, invoice_number="INV-2026-00042"
        )

        from app.utils.pdf import generate_invoice_pdf

        pdf_bytes = generate_invoice_pdf(invoice)
        text = _extract_pdf_text(pdf_bytes)
        assert "INV-2026-00042" in text

    def test_pdf_contains_customer_name(self, app, db_session):
        """The customer name appears in the PDF."""
        _set_session(db_session)
        customer = CustomerFactory(first_name="Alice", last_name="Wonder")
        invoice = InvoiceFactory(customer=customer)

        from app.utils.pdf import generate_invoice_pdf

        pdf_bytes = generate_invoice_pdf(invoice)
        text = _extract_pdf_text(pdf_bytes)
        assert "Alice Wonder" in text

    def test_pdf_contains_business_customer_name(self, app, db_session):
        """Business customer name appears in the PDF."""
        _set_session(db_session)
        customer = CustomerFactory(business=True, business_name="Ocean Divers Inc")
        invoice = InvoiceFactory(customer=customer)

        from app.utils.pdf import generate_invoice_pdf

        pdf_bytes = generate_invoice_pdf(invoice)
        text = _extract_pdf_text(pdf_bytes)
        assert "Ocean Divers Inc" in text

    def test_pdf_contains_line_item_descriptions(self, app, db_session):
        """Line item descriptions appear in the PDF."""
        _set_session(db_session)
        customer = CustomerFactory(first_name="Bob", last_name="Builder")
        invoice = InvoiceFactory(customer=customer)
        InvoiceLineItemFactory(
            invoice=invoice,
            description="Regulator Annual Service",
            quantity=Decimal("1"),
            unit_price=Decimal("75.00"),
            line_total=Decimal("75.00"),
        )

        from app.utils.pdf import generate_invoice_pdf

        pdf_bytes = generate_invoice_pdf(invoice)
        text = _extract_pdf_text(pdf_bytes)
        assert "Regulator Annual Service" in text

    def test_pdf_handles_no_line_items(self, app, db_session):
        """PDF generates successfully with no line items."""
        _set_session(db_session)
        customer = CustomerFactory(first_name="Empty", last_name="Invoice")
        invoice = InvoiceFactory(customer=customer)

        from app.utils.pdf import generate_invoice_pdf

        pdf_bytes = generate_invoice_pdf(invoice)
        assert pdf_bytes[:5] == b"%PDF-"
        text = _extract_pdf_text(pdf_bytes)
        assert "No line items" in text

    def test_pdf_handles_no_payments(self, app, db_session):
        """PDF generates successfully with no payments."""
        _set_session(db_session)
        customer = CustomerFactory(first_name="No", last_name="Pay")
        invoice = InvoiceFactory(customer=customer)
        InvoiceLineItemFactory(invoice=invoice)

        from app.utils.pdf import generate_invoice_pdf

        pdf_bytes = generate_invoice_pdf(invoice)
        assert pdf_bytes[:5] == b"%PDF-"
        text = _extract_pdf_text(pdf_bytes)
        # Payment History heading should not appear
        assert "Payment History" not in text

    def test_pdf_includes_payment_history(self, app, db_session):
        """Payment history section appears when payments exist."""
        _set_session(db_session)
        customer = CustomerFactory(first_name="Has", last_name="Payment")
        invoice = InvoiceFactory(customer=customer)
        PaymentFactory(
            invoice=invoice,
            payment_type="payment",
            amount=Decimal("50.00"),
            payment_method="cash",
            payment_date=date(2026, 3, 1),
        )

        from app.utils.pdf import generate_invoice_pdf

        pdf_bytes = generate_invoice_pdf(invoice)
        text = _extract_pdf_text(pdf_bytes)
        assert "Payment History" in text

    def test_pdf_handles_long_descriptions(self, app, db_session):
        """PDF handles long descriptions that need text wrapping."""
        _set_session(db_session)
        customer = CustomerFactory(first_name="Long", last_name="Desc")
        invoice = InvoiceFactory(customer=customer)
        long_desc = "Complete overhaul and rebuild of first and second stage regulator assembly including all seals and o-rings and performance testing"
        InvoiceLineItemFactory(
            invoice=invoice,
            description=long_desc,
            quantity=Decimal("1"),
            unit_price=Decimal("250.00"),
            line_total=Decimal("250.00"),
        )

        from app.utils.pdf import generate_invoice_pdf

        pdf_bytes = generate_invoice_pdf(invoice)
        assert pdf_bytes[:5] == b"%PDF-"
        text = _extract_pdf_text(pdf_bytes)
        assert "Complete overhaul" in text

    def test_pdf_shows_tax_when_present(self, app, db_session):
        """Tax info appears in totals when tax_rate > 0."""
        _set_session(db_session)
        customer = CustomerFactory(first_name="Tax", last_name="Payer")
        invoice = InvoiceFactory(
            customer=customer,
            tax_rate=Decimal("0.0825"),
            tax_amount=Decimal("8.25"),
            subtotal=Decimal("100.00"),
            total=Decimal("108.25"),
            balance_due=Decimal("108.25"),
        )

        from app.utils.pdf import generate_invoice_pdf

        pdf_bytes = generate_invoice_pdf(invoice)
        text = _extract_pdf_text(pdf_bytes)
        assert "Tax" in text

    def test_pdf_shows_discount_when_present(self, app, db_session):
        """Discount appears in totals when discount_amount > 0."""
        _set_session(db_session)
        customer = CustomerFactory(first_name="Disc", last_name="Ount")
        invoice = InvoiceFactory(
            customer=customer,
            discount_amount=Decimal("10.00"),
            subtotal=Decimal("100.00"),
            total=Decimal("90.00"),
            balance_due=Decimal("90.00"),
        )

        from app.utils.pdf import generate_invoice_pdf

        pdf_bytes = generate_invoice_pdf(invoice)
        text = _extract_pdf_text(pdf_bytes)
        assert "Discount" in text

    def test_pdf_contains_thank_you(self, app, db_session):
        """Footer includes thank-you message."""
        _set_session(db_session)
        customer = CustomerFactory(first_name="Thanks", last_name="Test")
        invoice = InvoiceFactory(customer=customer)

        from app.utils.pdf import generate_invoice_pdf

        pdf_bytes = generate_invoice_pdf(invoice)
        text = _extract_pdf_text(pdf_bytes)
        assert "Thank you for your business" in text

    def test_pdf_multiple_line_items(self, app, db_session):
        """PDF handles multiple line items."""
        _set_session(db_session)
        customer = CustomerFactory(first_name="Multi", last_name="Item")
        invoice = InvoiceFactory(customer=customer)
        for i in range(5):
            InvoiceLineItemFactory(
                invoice=invoice,
                description=f"Service item {i + 1}",
                quantity=Decimal("1"),
                unit_price=Decimal("50.00"),
                line_total=Decimal("50.00"),
            )

        from app.utils.pdf import generate_invoice_pdf

        pdf_bytes = generate_invoice_pdf(invoice)
        assert pdf_bytes[:5] == b"%PDF-"
        text = _extract_pdf_text(pdf_bytes)
        assert "Service item 1" in text
        assert "Service item 5" in text

    def test_pdf_has_reasonable_size(self, app, db_session):
        """PDF with content is larger than an empty PDF."""
        _set_session(db_session)
        customer = CustomerFactory(first_name="Size", last_name="Check")
        invoice = InvoiceFactory(customer=customer)
        for i in range(3):
            InvoiceLineItemFactory(invoice=invoice)

        from app.utils.pdf import generate_invoice_pdf

        pdf_bytes = generate_invoice_pdf(invoice)
        # A PDF with content should be at least a few KB
        assert len(pdf_bytes) > 1000


# =========================================================================
# Price List PDF tests
# =========================================================================


class TestPriceListPDFGeneration:
    """Tests for generate_price_list_pdf()."""

    def test_price_list_pdf_returns_valid_bytes(self, app, db_session):
        """Price list PDF starts with %PDF magic bytes."""
        _set_session(db_session)
        cat = PriceListCategoryFactory(name="Regulator Service")
        item = PriceListItemFactory(
            category=cat, name="Annual Service", price=Decimal("75.00")
        )

        from app.utils.pdf import generate_price_list_pdf

        pdf_bytes = generate_price_list_pdf({cat: [item]})
        assert pdf_bytes[:5] == b"%PDF-"

    def test_price_list_pdf_contains_category(self, app, db_session):
        """Category name appears in the price list PDF."""
        _set_session(db_session)
        cat = PriceListCategoryFactory(name="BCD Service")
        item = PriceListItemFactory(category=cat, name="BCD Inspect")

        from app.utils.pdf import generate_price_list_pdf

        pdf_bytes = generate_price_list_pdf({cat: [item]})
        text = _extract_pdf_text(pdf_bytes)
        assert "BCD Service" in text

    def test_price_list_pdf_contains_items(self, app, db_session):
        """Item names appear in the price list PDF."""
        _set_session(db_session)
        cat = PriceListCategoryFactory(name="Tank Service")
        item = PriceListItemFactory(
            category=cat, name="Visual Inspection", price=Decimal("25.00")
        )

        from app.utils.pdf import generate_price_list_pdf

        pdf_bytes = generate_price_list_pdf({cat: [item]})
        text = _extract_pdf_text(pdf_bytes)
        assert "Visual Inspection" in text

    def test_price_list_pdf_contains_footer(self, app, db_session):
        """Price list PDF contains the 'prices subject to change' notice."""
        _set_session(db_session)
        cat = PriceListCategoryFactory(name="Misc")
        item = PriceListItemFactory(category=cat)

        from app.utils.pdf import generate_price_list_pdf

        pdf_bytes = generate_price_list_pdf({cat: [item]})
        text = _extract_pdf_text(pdf_bytes)
        assert "Prices subject to change" in text

    def test_price_list_pdf_empty_categories(self, app, db_session):
        """Price list PDF handles an empty dict gracefully."""
        from app.utils.pdf import generate_price_list_pdf

        pdf_bytes = generate_price_list_pdf({})
        assert pdf_bytes[:5] == b"%PDF-"

    def test_price_list_pdf_multiple_categories(self, app, db_session):
        """Price list PDF renders multiple categories."""
        _set_session(db_session)
        cat1 = PriceListCategoryFactory(name="Regulators")
        cat2 = PriceListCategoryFactory(name="Drysuits")
        item1 = PriceListItemFactory(category=cat1, name="Reg Overhaul")
        item2 = PriceListItemFactory(category=cat2, name="Seal Replacement")

        from app.utils.pdf import generate_price_list_pdf

        pdf_bytes = generate_price_list_pdf({cat1: [item1], cat2: [item2]})
        text = _extract_pdf_text(pdf_bytes)
        assert "Regulators" in text
        assert "Drysuits" in text
