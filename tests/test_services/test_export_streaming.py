"""Tests for streaming CSV export functionality."""

import csv
import io

import pytest

from app.services import export_service
from tests.factories import (
    CustomerFactory,
    InventoryItemFactory,
    InvoiceFactory,
    ServiceOrderFactory,
)

pytestmark = pytest.mark.unit


def _set_sessions(db_session):
    """Set the SQLAlchemy session on all factories used in these tests."""
    for factory_cls in [
        CustomerFactory,
        InventoryItemFactory,
        InvoiceFactory,
        ServiceOrderFactory,
    ]:
        factory_cls._meta.sqlalchemy_session = db_session


def _collect_streaming_rows(entity_type, query=None):
    """Collect all rows from a streaming CSV export into a list of strings."""
    return list(export_service.stream_csv_export(entity_type, query=query))


class TestStreamCsvExport:
    """Tests for export_service.stream_csv_export()."""

    def test_streaming_customers_yields_header(self, app, db_session):
        rows = _collect_streaming_rows("customers")
        assert len(rows) >= 1
        # First row should be BOM + header
        assert rows[0].startswith("\ufeff")
        assert "ID" in rows[0]
        assert "First Name" in rows[0]

    def test_streaming_customers_includes_data(self, app, db_session):
        _set_sessions(db_session)
        CustomerFactory(first_name="StreamTest", last_name="Customer")

        rows = _collect_streaming_rows("customers")
        assert len(rows) == 2  # header + 1 data row
        assert "StreamTest" in rows[1]

    def test_streaming_empty_dataset_yields_only_header(self, app, db_session):
        rows = _collect_streaming_rows("customers")
        assert len(rows) == 1  # Just the header

    def test_streaming_inventory_yields_valid_csv(self, app, db_session):
        _set_sessions(db_session)
        InventoryItemFactory(name="Stream Widget", sku="SKU-STREAM-01")

        rows = _collect_streaming_rows("inventory")
        assert len(rows) == 2
        # Parse the CSV to verify structure
        reader = csv.reader(io.StringIO("".join(rows).lstrip("\ufeff")))
        parsed = list(reader)
        assert parsed[0][0] == "ID"  # header
        assert "Stream Widget" in parsed[1]

    def test_streaming_orders_yields_data(self, app, db_session):
        _set_sessions(db_session)
        ServiceOrderFactory(order_number="SO-STREAM-001")

        rows = _collect_streaming_rows("orders")
        assert len(rows) == 2
        assert "SO-STREAM-001" in rows[1]

    def test_streaming_invoices_yields_data(self, app, db_session):
        _set_sessions(db_session)
        InvoiceFactory(invoice_number="INV-STREAM-001")

        rows = _collect_streaming_rows("invoices")
        assert len(rows) == 2
        assert "INV-STREAM-001" in rows[1]

    def test_streaming_unknown_entity_raises_valueerror(self, app, db_session):
        with pytest.raises(ValueError, match="Unknown entity type"):
            _collect_streaming_rows("nonexistent")

    def test_streaming_multiple_records(self, app, db_session):
        _set_sessions(db_session)
        CustomerFactory(first_name="StreamA", last_name="One")
        CustomerFactory(first_name="StreamB", last_name="Two")
        CustomerFactory(first_name="StreamC", last_name="Three")

        rows = _collect_streaming_rows("customers")
        assert len(rows) == 4  # header + 3 data rows

    def test_streaming_csv_rows_are_valid_csv(self, app, db_session):
        _set_sessions(db_session)
        CustomerFactory(
            first_name="Comma,Name",
            last_name="Quote\"Test",
            email="test@example.com",
        )

        rows = _collect_streaming_rows("customers")
        # Parse all rows as CSV -- should not raise
        all_text = "".join(rows).lstrip("\ufeff")
        reader = csv.reader(io.StringIO(all_text))
        parsed = list(reader)
        assert len(parsed) == 2
        # Verify the comma and quote were properly escaped
        data_row = parsed[1]
        assert "Comma,Name" in data_row
        assert 'Quote"Test' in data_row


class TestStreamingExportBlueprint:
    """Tests for streaming CSV via the export blueprint."""

    def test_export_customers_csv_streams(self, logged_in_client, app, db_session):
        _set_sessions(db_session)
        CustomerFactory(first_name="ExportStream", last_name="Test")

        resp = logged_in_client.get("/export/customers/csv")
        assert resp.status_code == 200
        assert resp.content_type == "text/csv; charset=utf-8"
        data = resp.get_data(as_text=True)
        assert "ExportStream" in data

    def test_export_inventory_csv_streams(self, logged_in_client, app, db_session):
        _set_sessions(db_session)
        InventoryItemFactory(name="ExportStreamItem")

        resp = logged_in_client.get("/export/inventory/csv")
        assert resp.status_code == 200
        data = resp.get_data(as_text=True)
        assert "ExportStreamItem" in data
