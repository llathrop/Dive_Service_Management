"""Unit tests for the portal payment-provider groundwork."""

from decimal import Decimal

import pytest

from app.services import payment_provider_service
from tests.factories import CustomerFactory, InvoiceFactory

pytestmark = pytest.mark.unit


def _set_session(db_session):
    CustomerFactory._meta.sqlalchemy_session = db_session
    InvoiceFactory._meta.sqlalchemy_session = db_session


class TestPaymentProviderRegistry:
    """Tests for the provider registry and default provider."""

    def test_default_provider_is_manual(self, app, db_session):
        _set_session(db_session)
        provider = payment_provider_service.get_provider()
        assert provider.get_code() == "manual"
        assert provider.get_name() == "Manual Payment"

    def test_zero_balance_due_is_preserved(self, app, db_session):
        _set_session(db_session)
        customer = CustomerFactory()
        invoice = InvoiceFactory(
            customer=customer,
            total=Decimal("125.00"),
            balance_due=Decimal("0.00"),
        )

        context = payment_provider_service.build_invoice_context(invoice)
        assert context["amount_due"] == Decimal("0.00")

