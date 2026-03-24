"""Blueprints package.

All blueprint instances are imported here for convenient registration
in the application factory.
"""

from app.blueprints.admin import admin_bp
from app.blueprints.attachments import attachments_bp
from app.blueprints.auth import auth_bp
from app.blueprints.customers import customers_bp
from app.blueprints.dashboard import dashboard_bp
from app.blueprints.docs import docs_bp
from app.blueprints.export import export_bp
from app.blueprints.health import health_bp
from app.blueprints.inventory import inventory_bp
from app.blueprints.invoices import invoices_bp
from app.blueprints.items import items_bp
from app.blueprints.notifications import notifications_bp
from app.blueprints.orders import orders_bp
from app.blueprints.price_list import price_list_bp
from app.blueprints.reports import reports_bp
from app.blueprints.search import search_bp
from app.blueprints.tools import tools_bp

__all__ = [
    "admin_bp",
    "attachments_bp",
    "auth_bp",
    "customers_bp",
    "dashboard_bp",
    "docs_bp",
    "export_bp",
    "health_bp",
    "inventory_bp",
    "invoices_bp",
    "items_bp",
    "notifications_bp",
    "orders_bp",
    "price_list_bp",
    "reports_bp",
    "search_bp",
    "tools_bp",
]
