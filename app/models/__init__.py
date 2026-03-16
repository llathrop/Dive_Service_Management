"""Models package.

Import all models here so that ``from app.models import User, Role``
works throughout the application and so Alembic's ``env.py`` can
discover every model by importing this single package.
"""

from app.models.user import Role, User, user_roles
from app.models.customer import Customer
from app.models.service_item import ServiceItem
from app.models.drysuit_details import DrysuitDetails
from app.models.inventory import InventoryItem
from app.models.price_list import PriceListCategory, PriceListItem, PriceListItemPart
from app.models.tag import Tag, Taggable
from app.models.service_order import ServiceOrder
from app.models.service_order_item import ServiceOrderItem
from app.models.service_note import ServiceNote
from app.models.parts_used import PartUsed
from app.models.labor import LaborEntry
from app.models.applied_service import AppliedService
from app.models.invoice import Invoice, InvoiceLineItem, invoice_orders
from app.models.payment import Payment
from app.models.notification import Notification
from app.models.notification_read import NotificationRead
from app.models.system_config import SystemConfig
from app.models.audit_log import AuditLog
from app.models.attachment import Attachment

__all__ = [
    "Role",
    "User",
    "user_roles",
    "Customer",
    "ServiceItem",
    "DrysuitDetails",
    "InventoryItem",
    "PriceListCategory",
    "PriceListItem",
    "PriceListItemPart",
    "Tag",
    "Taggable",
    "ServiceOrder",
    "ServiceOrderItem",
    "ServiceNote",
    "PartUsed",
    "LaborEntry",
    "AppliedService",
    "Invoice",
    "InvoiceLineItem",
    "invoice_orders",
    "Payment",
    "Notification",
    "NotificationRead",
    "SystemConfig",
    "AuditLog",
    "Attachment",
]
