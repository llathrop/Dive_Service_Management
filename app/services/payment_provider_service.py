"""Pluggable payment-provider groundwork for customer portal invoices.

The current implementation is intentionally lightweight: it provides a
registry, a default manual provider, and a stable context shape for the
portal UI.  Future providers can plug into the same interface without
changing portal templates.
"""

from abc import ABC, abstractmethod
from decimal import Decimal
from threading import RLock

from app.services import config_service


_PROVIDER_REGISTRY = {}
_REGISTRY_LOCK = RLock()


def _invoice_amount_due(invoice):
    if getattr(invoice, "balance_due", None) is not None:
        return Decimal(str(invoice.balance_due))
    if getattr(invoice, "total", None) is not None:
        return Decimal(str(invoice.total))
    return Decimal("0")


class PaymentProvider(ABC):
    """Base class for portal payment providers."""

    code = "base"
    name = "Base Payment Provider"

    def get_code(self):
        return self.code

    def get_name(self):
        return self.name

    def build_invoice_context(self, invoice):
        """Return a portal-safe payment context for an invoice."""
        return {
            "provider_code": self.get_code(),
            "provider_name": self.get_name(),
            "supports_checkout": False,
            "checkout_url": None,
            "amount_due": _invoice_amount_due(invoice),
            "instructions": "Online payments are not configured yet. Contact the shop to arrange payment.",
        }

    @abstractmethod
    def create_checkout_session(self, invoice, **kwargs):
        """Create a checkout/payment session for the provider."""
        raise NotImplementedError


class ManualPaymentProvider(PaymentProvider):
    """Default provider used until a real gateway is wired in."""

    code = "manual"
    name = "Manual Payment"

    def create_checkout_session(self, invoice, **kwargs):
        return None

    def build_invoice_context(self, invoice):
        context = super().build_invoice_context(invoice)
        context.update(
            {
                "supports_checkout": False,
                "checkout_url": None,
                "instructions": (
                    "Online payments are not enabled for this account yet. "
                    "Call the shop or settle the invoice in person."
                ),
            }
        )
        return context


def register_provider(provider):
    """Register a payment provider instance."""
    if not isinstance(provider, PaymentProvider):
        raise TypeError("provider must be a PaymentProvider instance")

    with _REGISTRY_LOCK:
        _PROVIDER_REGISTRY[provider.get_code()] = provider
    return provider


def get_registered_provider_codes():
    """Return the currently registered provider codes."""
    with _REGISTRY_LOCK:
        return tuple(sorted(_PROVIDER_REGISTRY))


def get_provider(provider_code=None):
    """Return the active payment provider.

    The provider code can come from a caller override or from the
    `payment.provider` system config key. Missing/unknown codes fall
    back to the manual provider.
    """
    code = provider_code or config_service.get_config("payment.provider") or "manual"
    with _REGISTRY_LOCK:
        provider = _PROVIDER_REGISTRY.get(code)
        if provider is None:
            provider = _PROVIDER_REGISTRY["manual"]
    return provider


def build_invoice_context(invoice, provider_code=None):
    """Return the payment-provider context for a portal invoice."""
    provider = get_provider(provider_code)
    context = provider.build_invoice_context(invoice)
    context.setdefault("provider_code", provider.get_code())
    context.setdefault("provider_name", provider.get_name())
    context.setdefault("amount_due", _invoice_amount_due(invoice))
    return context


register_provider(ManualPaymentProvider())
