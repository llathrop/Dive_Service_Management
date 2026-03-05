"""Forms package.

Custom WTForms form classes used throughout the application.
Flask-Security-Too provides its own login/register forms; custom
extensions live in the sub-modules here.

Convenience imports are provided so that views can do::

    from app.forms import CustomerForm, ServiceItemForm
"""

from app.forms.applied_service import AppliedServiceForm
from app.forms.auth import ExtendedLoginForm
from app.forms.customer import CustomerForm, CustomerSearchForm
from app.forms.inventory import InventoryItemForm, InventorySearchForm, StockAdjustmentForm
from app.forms.item import DrysuitDetailsForm, ServiceItemForm
from app.forms.labor import LaborEntryForm
from app.forms.note import ServiceNoteForm
from app.forms.order import ServiceOrderForm, OrderSearchForm
from app.forms.parts_used import PartUsedForm
from app.forms.price_list import PriceListCategoryForm, PriceListItemForm
from app.forms.invoice import InvoiceForm, InvoiceSearchForm, InvoiceLineItemForm, PaymentForm
from app.forms.search import GlobalSearchForm
from app.forms.service_order_item import ServiceOrderItemForm

__all__ = [
    "AppliedServiceForm",
    "ExtendedLoginForm",
    "CustomerForm",
    "CustomerSearchForm",
    "DrysuitDetailsForm",
    "GlobalSearchForm",
    "InvoiceForm",
    "InvoiceSearchForm",
    "InvoiceLineItemForm",
    "InventoryItemForm",
    "InventorySearchForm",
    "LaborEntryForm",
    "OrderSearchForm",
    "PartUsedForm",
    "PaymentForm",
    "PriceListCategoryForm",
    "PriceListItemForm",
    "ServiceItemForm",
    "ServiceNoteForm",
    "ServiceOrderForm",
    "ServiceOrderItemForm",
    "StockAdjustmentForm",
]
