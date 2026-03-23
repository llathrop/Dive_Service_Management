"""Tests for SORTABLE_FIELDS consistency and security config verification.

Ensures that SORTABLE_FIELDS definitions in blueprint modules are imported
from (and therefore identical to) the service layer, and that production
config has DEBUG explicitly disabled.
"""

import pytest


class TestSortableFieldsInvoices:
    """Invoice SORTABLE_FIELDS should be the single source from the service."""

    def test_invoice_blueprint_uses_service_sortable_fields(self):
        """The invoices blueprint SORTABLE_FIELDS must be the same object
        as the one defined in invoice_service."""
        from app.blueprints.invoices import SORTABLE_FIELDS as bp_fields
        from app.services.invoice_service import SORTABLE_FIELDS as svc_fields

        # They should be the exact same object (imported, not duplicated)
        assert bp_fields is svc_fields

    def test_invoice_sortable_fields_contents(self):
        """Verify the invoice SORTABLE_FIELDS contains expected columns."""
        from app.services.invoice_service import SORTABLE_FIELDS

        expected = {
            "invoice_number",
            "status",
            "issue_date",
            "due_date",
            "total",
            "balance_due",
            "created_at",
        }
        assert set(SORTABLE_FIELDS) == expected


class TestSortableFieldsOrders:
    """Order SORTABLE_FIELDS should be the single source from the service."""

    def test_order_blueprint_uses_service_sortable_fields(self):
        """The orders blueprint SORTABLE_FIELDS must be the same object
        as the one defined in order_service."""
        from app.blueprints.orders import SORTABLE_FIELDS as bp_fields
        from app.services.order_service import SORTABLE_FIELDS as svc_fields

        # They should be the exact same object (imported, not duplicated)
        assert bp_fields is svc_fields

    def test_order_sortable_fields_contents(self):
        """Verify the order SORTABLE_FIELDS contains expected columns."""
        from app.services.order_service import SORTABLE_FIELDS

        expected = {
            "order_number",
            "status",
            "priority",
            "date_received",
            "date_promised",
            "estimated_total",
            "created_at",
        }
        assert set(SORTABLE_FIELDS) == expected


class TestProductionConfig:
    """Production configuration security checks."""

    def test_production_debug_is_false(self):
        """ProductionConfig.DEBUG must be explicitly False."""
        from app.config import ProductionConfig

        assert ProductionConfig.DEBUG is False

    def test_dockerfile_runs_as_non_root(self):
        """Verify the Dockerfile contains a USER directive for non-root."""
        import os

        # Find the Dockerfile relative to the project root
        project_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        dockerfile_path = os.path.join(project_root, "Dockerfile")

        with open(dockerfile_path) as f:
            content = f.read()

        # The Dockerfile should contain a USER directive for 'dsm'
        assert "USER dsm" in content, (
            "Dockerfile must run as non-root 'dsm' user"
        )
