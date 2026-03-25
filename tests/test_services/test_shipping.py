"""Tests for the shipping service layer and routes."""

from decimal import Decimal

import pytest

from app.models.audit_log import AuditLog
from app.models.shipment import Shipment
from app.services import invoice_service, order_service
from app.services import shipping_service
from app.services.shipping_service import FlatRateProvider
from tests.factories import CustomerFactory, ServiceOrderFactory, ShipmentFactory


# ======================================================================
# Provider tests
# ======================================================================


@pytest.mark.unit
class TestFlatRateProvider:
    """Tests for FlatRateProvider rate calculation."""

    def test_flat_rate_provider_light_package(self, app, db_session):
        """A 3 lb package should cost $9.99 (first tier)."""
        provider = FlatRateProvider()
        rate = provider.calculate_rate(Decimal("3"))
        assert rate == Decimal("9.99")

    def test_flat_rate_provider_medium_package(self, app, db_session):
        """A 12 lb package should cost $14.99 (second tier)."""
        provider = FlatRateProvider()
        rate = provider.calculate_rate(Decimal("12"))
        assert rate == Decimal("14.99")

    def test_flat_rate_provider_heavy_package(self, app, db_session):
        """A 25 lb package should cost $24.99 (third tier)."""
        provider = FlatRateProvider()
        rate = provider.calculate_rate(Decimal("25"))
        assert rate == Decimal("24.99")

    def test_flat_rate_provider_very_heavy_package(self, app, db_session):
        """A 50 lb package should cost $39.99 (highest tier)."""
        provider = FlatRateProvider()
        rate = provider.calculate_rate(Decimal("50"))
        assert rate == Decimal("39.99")

    def test_flat_rate_provider_boundary_weight(self, app, db_session):
        """A 5 lb package is exactly at the first tier boundary."""
        provider = FlatRateProvider()
        rate = provider.calculate_rate(Decimal("5"))
        assert rate == Decimal("9.99")

    def test_flat_rate_provider_available_methods(self, app, db_session):
        """Provider should return its available shipping methods."""
        provider = FlatRateProvider()
        methods = provider.get_available_methods()
        assert len(methods) == 1
        assert methods[0]["code"] == "flat_rate"
        assert methods[0]["name"] == "Flat Rate Shipping"

    def test_quote_shipping_tracks_destination_metadata(self, app, db_session):
        """Destination details should flow through provider quotes."""
        quote = shipping_service.quote_shipping(
            weight_lbs=Decimal("5.00"),
            provider_code="ups",
            method="ups_ground",
            destination_postal_code="V6B1A1",
            destination_country="CA",
        )

        assert quote.provider_code == "ups"
        assert quote.metadata["destination_postal_code"] == "V6B1A1"
        assert quote.metadata["destination_country"] == "CA"
        assert quote.metadata["international"] is True
        assert quote.amount > Decimal("0.00")

    def test_local_pickup_quote_requires_no_weight(self, app, db_session):
        """Local pickup should quote successfully with no package measurements."""
        quote = shipping_service.quote_shipping(
            provider_code="local_pickup",
            method="local_pickup",
        )

        assert quote.amount == Decimal("0.00")
        assert quote.method_code == "local_pickup"

    def test_local_pickup_is_workflow_default_provider(self, monkeypatch, app, db_session):
        """UI workflows should default to local pickup when available."""
        monkeypatch.setattr(
            shipping_service.config_service,
            "get_config",
            lambda key, default=None: default,
        )

        assert shipping_service.get_workflow_default_provider_code() == "local_pickup"

    def test_required_providers_always_enabled(self, monkeypatch, app, db_session):
        """Local pickup and flat rate should remain available even if config omits them."""
        monkeypatch.setattr(
            shipping_service.config_service,
            "get_config",
            lambda key, default=None: ["ups"] if key == "shipping.enabled_providers" else default,
        )

        enabled_codes = shipping_service.get_enabled_provider_codes()
        assert enabled_codes[0] == "local_pickup"
        assert "ups" in enabled_codes
        assert "flat_rate" in enabled_codes

    def test_disabled_provider_is_rejected(self, monkeypatch, app, db_session):
        """Disabled providers should not be usable via direct requests."""
        monkeypatch.setattr(
            shipping_service.config_service,
            "get_config",
            lambda key, default=None: ["ups"] if key == "shipping.enabled_providers" else default,
        )

        with pytest.raises(ValueError, match="disabled"):
            shipping_service.get_provider("fedex")


# ======================================================================
# Service CRUD tests
# ======================================================================


@pytest.mark.unit
class TestShipmentCRUD:
    """Tests for shipment CRUD operations."""

    def _set_sessions(self, db_session):
        CustomerFactory._meta.sqlalchemy_session = db_session
        ServiceOrderFactory._meta.sqlalchemy_session = db_session
        ShipmentFactory._meta.sqlalchemy_session = db_session

    def test_create_shipment(self, app, db_session):
        """Creating a shipment should calculate cost and persist."""
        self._set_sessions(db_session)
        order = ServiceOrderFactory()
        db_session.flush()

        shipment = shipping_service.create_shipment(
            order_id=order.id,
            weight_lbs=Decimal("10.00"),
        )

        assert shipment.id is not None
        assert shipment.order_id == order.id
        assert shipment.weight_lbs == Decimal("10.00")
        assert shipment.shipping_cost == Decimal("14.99")
        assert shipment.status == "pending"

    def test_create_shipment_persists_provider_quote_metadata(self, app, db_session):
        """Shipments should persist provider and destination quote metadata."""
        self._set_sessions(db_session)
        order = ServiceOrderFactory()
        db_session.flush()

        shipment = shipping_service.create_shipment(
            order_id=order.id,
            weight_lbs=Decimal("8.00"),
            provider_code="fedex",
            shipping_method="fedex_two_day",
            destination_postal_code="33139",
            destination_country="US",
        )

        assert shipment.provider_code == "fedex"
        assert shipment.quote_metadata["provider_name"] == "FedEx"
        assert shipment.quote_metadata["metadata"]["destination_postal_code"] == "33139"
        assert shipment.carrier == "FedEx"

    def test_update_shipment_tracking(self, app, db_session):
        """Updating tracking number should persist."""
        self._set_sessions(db_session)
        order = ServiceOrderFactory()
        db_session.flush()

        shipment = shipping_service.create_shipment(
            order_id=order.id,
            weight_lbs=Decimal("3.00"),
        )

        updated = shipping_service.update_shipment(
            shipment.id,
            tracking_number="1Z999AA10123456784",
            carrier="UPS",
            status="shipped",
        )

        assert updated.tracking_number == "1Z999AA10123456784"
        assert updated.carrier == "UPS"
        assert updated.status == "shipped"

    def test_get_order_shipments(self, app, db_session):
        """Should return all shipments for an order."""
        self._set_sessions(db_session)
        order = ServiceOrderFactory()
        db_session.flush()

        shipping_service.create_shipment(
            order_id=order.id, weight_lbs=Decimal("5.00"),
        )
        shipping_service.create_shipment(
            order_id=order.id, weight_lbs=Decimal("10.00"),
        )

        shipments = shipping_service.get_order_shipments(order.id)
        assert len(shipments) == 2

    def test_delete_shipment(self, app, db_session):
        """Deleting a shipment should remove it from the database."""
        self._set_sessions(db_session)
        order = ServiceOrderFactory()
        db_session.flush()

        shipment = shipping_service.create_shipment(
            order_id=order.id, weight_lbs=Decimal("5.00"),
        )
        sid = shipment.id

        shipping_service.delete_shipment(sid)
        assert db_session.get(Shipment, sid) is None

    def test_get_order_shipping_total(self, app, db_session):
        """Should sum up all shipment costs for an order."""
        self._set_sessions(db_session)
        order = ServiceOrderFactory()
        db_session.flush()

        shipping_service.create_shipment(
            order_id=order.id, weight_lbs=Decimal("3.00"),
        )
        shipping_service.create_shipment(
            order_id=order.id, weight_lbs=Decimal("20.00"),
        )

        total = shipping_service.get_order_shipping_total(order.id)
        # 9.99 + 24.99 = 34.98
        assert total == Decimal("34.98")

    def test_update_shipment_rejects_invalid_status(self, app, db_session):
        """Invalid shipment status should be rejected at the service layer."""
        self._set_sessions(db_session)
        order = ServiceOrderFactory()
        db_session.flush()

        shipment = shipping_service.create_shipment(
            order_id=order.id, weight_lbs=Decimal("5.00"),
        )

        with pytest.raises(ValueError, match="Invalid shipment status"):
            shipping_service.update_shipment(
                shipment.id,
                status="teleported",
            )

    def test_create_shipment_truncates_audit_user_agent(self, app, db_session):
        """Audit log should not fail on oversized user-agent values."""
        self._set_sessions(db_session)
        order = ServiceOrderFactory()
        db_session.flush()

        shipping_service.create_shipment(
            order_id=order.id,
            weight_lbs=Decimal("10.00"),
            user_agent="x" * 700,
        )

        audit_entry = AuditLog.query.filter_by(
            entity_type="shipment",
            action="create",
        ).order_by(AuditLog.id.desc()).first()
        assert audit_entry is not None
        assert len(audit_entry.user_agent) == 500

    def test_delete_shipment_audit_preserves_context(self, app, db_session):
        """Delete audit log should retain shipment context after hard-delete."""
        self._set_sessions(db_session)
        order = ServiceOrderFactory()
        db_session.flush()

        shipment = shipping_service.create_shipment(
            order_id=order.id,
            weight_lbs=Decimal("5.00"),
            carrier="UPS",
            tracking_number="1Z123",
        )

        shipping_service.delete_shipment(shipment.id)

        audit_entry = AuditLog.query.filter_by(
            entity_type="shipment",
            entity_id=shipment.id,
            action="delete",
        ).first()
        assert audit_entry is not None
        assert '"order_id"' in audit_entry.additional_data
        assert '"tracking_number": "1Z123"' in audit_entry.additional_data

    def test_get_order_shipping_total_excludes_cancelled(self, app, db_session):
        """Cancelled shipments should not count toward totals."""
        self._set_sessions(db_session)
        order = ServiceOrderFactory()
        db_session.flush()

        active = shipping_service.create_shipment(
            order_id=order.id, weight_lbs=Decimal("5.00"),
        )
        cancelled = shipping_service.create_shipment(
            order_id=order.id, weight_lbs=Decimal("10.00"),
        )
        shipping_service.update_shipment(active.id, status="shipped")
        shipping_service.update_shipment(cancelled.id, status="cancelled")

        total = shipping_service.get_order_shipping_total(order.id)
        assert total == Decimal("9.99")

    def test_order_summary_includes_shipping(self, app, db_session):
        """Order summary estimated total should include shipping charges."""
        self._set_sessions(db_session)
        order = ServiceOrderFactory(rush_fee=Decimal("5.00"))
        db_session.flush()

        shipping_service.create_shipment(
            order_id=order.id, weight_lbs=Decimal("10.00"),
        )

        summary = order_service.get_order_summary(order.id)
        assert summary["shipping_total"] == Decimal("14.99")
        assert summary["estimated_total"] == Decimal("19.99")

    def test_invoice_preview_includes_shipping(self, app, db_session):
        """Order cost preview should include shipping as a line item."""
        self._set_sessions(db_session)
        order = ServiceOrderFactory()
        db_session.flush()

        shipping_service.create_shipment(
            order_id=order.id, weight_lbs=Decimal("10.00"),
        )

        preview = invoice_service.get_order_cost_preview(order.id)
        assert preview["shipping"] == "14.99"
        assert preview["grand_total"] == "14.99"
        assert any(
            item["description"] == "Shipping" for item in preview["line_items"]
        )

    def test_invoice_preview_applies_percent_discount_to_shipping(
        self, app, db_session
    ):
        """Order cost preview should apply percentage discounts after shipping."""
        self._set_sessions(db_session)
        order = ServiceOrderFactory(discount_percent=Decimal("10.00"))
        db_session.flush()

        shipping_service.create_shipment(
            order_id=order.id, weight_lbs=Decimal("10.00"),
        )

        preview = invoice_service.get_order_cost_preview(order.id)
        assert preview["grand_total"] == "13.49"
        assert any(
            item["description"] == "Discount (10.00%)"
            for item in preview["line_items"]
        )

    def test_generate_from_order_includes_shipping(self, app, db_session):
        """Generated invoices should bill shipping charges."""
        self._set_sessions(db_session)
        order = ServiceOrderFactory()
        db_session.flush()

        shipping_service.create_shipment(
            order_id=order.id, weight_lbs=Decimal("10.00"),
        )

        invoice = invoice_service.generate_from_order(order.id)
        shipping_line = invoice.line_items.filter_by(description="Shipping").first()

        assert shipping_line is not None
        assert shipping_line.line_type == "fee"
        assert shipping_line.line_total == Decimal("14.99")
        assert invoice.total == Decimal("14.99")

    def test_generate_from_order_applies_percent_discount_to_shipping(
        self, app, db_session
    ):
        """Generated invoice totals should include percent discounts on shipping."""
        self._set_sessions(db_session)
        order = ServiceOrderFactory(discount_percent=Decimal("10.00"))
        db_session.flush()

        shipping_service.create_shipment(
            order_id=order.id, weight_lbs=Decimal("10.00"),
        )

        invoice = invoice_service.generate_from_order(order.id)
        discount_line = invoice.line_items.filter_by(
            description="Discount (10.00%)"
        ).first()

        assert discount_line is not None
        assert discount_line.line_total == Decimal("-1.50")
        assert invoice.total == Decimal("13.49")


# ======================================================================
# Route tests
# ======================================================================


@pytest.mark.blueprint
class TestShippingRoutes:
    """Tests for shipping blueprint routes."""

    def _create_order(self, db_session):
        CustomerFactory._meta.sqlalchemy_session = db_session
        ServiceOrderFactory._meta.sqlalchemy_session = db_session
        order = ServiceOrderFactory()
        db_session.flush()
        return order

    def test_shipping_page(self, app, db_session, logged_in_client):
        """Shipping management page should render for technicians."""
        order = self._create_order(db_session)
        response = logged_in_client.get(f"/orders/{order.id}/shipping")
        assert response.status_code == 200
        assert b"Shipping Management" in response.data
        assert b"Local pickup stays at $0.00" in response.data

    def test_estimate_endpoint(self, app, db_session, logged_in_client):
        """HTMX estimate endpoint should return cost fragment."""
        order = self._create_order(db_session)
        response = logged_in_client.get(
            f"/orders/{order.id}/shipping/estimate?provider_code=ups&shipping_method=ups_ground&weight_lbs=10&destination_postal_code=77002&destination_country=US"
        )
        assert response.status_code == 200
        assert b"UPS" in response.data
        assert b"77002" in response.data
        assert b"text-success" in response.data

    def test_estimate_endpoint_rejects_nan(self, app, db_session, logged_in_client):
        """Non-finite numeric inputs should be treated as invalid."""
        order = self._create_order(db_session)
        response = logged_in_client.get(
            f"/orders/{order.id}/shipping/estimate?weight_lbs=NaN"
        )
        assert response.status_code == 200
        assert b"Enter weight and optional dimensions to estimate shipping" in response.data

    def test_estimate_endpoint_invalid_provider_shows_error(self, app, db_session, logged_in_client):
        """Malformed provider inputs should render an error fragment instead of 500ing."""
        order = self._create_order(db_session)
        response = logged_in_client.get(
            f"/orders/{order.id}/shipping/estimate?provider_code={'x' * 51}"
        )

        assert response.status_code == 200
        assert b"Provider Code must be 50 characters or fewer." in response.data

    def test_create_shipment_via_form(self, app, db_session, logged_in_client):
        """POST should create a shipment and redirect."""
        order = self._create_order(db_session)
        response = logged_in_client.post(
            f"/orders/{order.id}/shipping",
            data={
                "weight_lbs": "10.00",
                "provider_code": "usps",
                "shipping_method": "usps_priority_mail",
                "destination_postal_code": "30301",
                "destination_country": "US",
                "tracking_number": "TEST123",
            },
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b"Shipment created successfully" in response.data

        shipments = shipping_service.get_order_shipments(order.id)
        assert len(shipments) == 1
        assert shipments[0].provider_code == "usps"
        assert shipments[0].carrier == "USPS"

    def test_create_local_pickup_without_weight(self, app, db_session, logged_in_client):
        """Local pickup shipments should be creatable without weight."""
        order = self._create_order(db_session)
        response = logged_in_client.post(
            f"/orders/{order.id}/shipping",
            data={
                "provider_code": "local_pickup",
                "shipping_method": "local_pickup",
                "destination_country": "US",
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert b"Shipment created successfully" in response.data
        shipments = shipping_service.get_order_shipments(order.id)
        assert shipments[0].provider_code == "local_pickup"
        assert shipments[0].shipping_cost == Decimal("0.00")

    def test_order_detail_financial_summary_includes_shipping(
        self, app, db_session, logged_in_client
    ):
        """Order detail page should show shipping in the main summary."""
        order = self._create_order(db_session)
        shipping_service.create_shipment(
            order_id=order.id, weight_lbs=Decimal("10.00"),
        )

        response = logged_in_client.get(f"/orders/{order.id}")
        assert response.status_code == 200
        assert b"Total Shipping Cost" in response.data
        assert b"Shipping" in response.data
        assert response.data.count(b"$14.99") >= 2

    def test_viewer_cannot_access(self, app, db_session, viewer_client):
        """Viewer role should get 403 on shipping page."""
        order = self._create_order(db_session)
        response = viewer_client.get(f"/orders/{order.id}/shipping")
        assert response.status_code == 403

    def test_create_shipment_invalid_text_shows_flash_not_500(
        self, app, db_session, logged_in_client
    ):
        """Create route should handle validation failures with a redirect and flash."""
        order = self._create_order(db_session)
        response = logged_in_client.post(
            f"/orders/{order.id}/shipping",
            data={
                "weight_lbs": "10.00",
                "carrier": "X" * 101,
            },
            follow_redirects=True,
        )

        assert response.status_code == 200
        assert b"Carrier must be 100 characters or fewer." in response.data

    def test_cannot_update_shipment_for_different_order(
        self, app, db_session, logged_in_client
    ):
        """Shipment update should be scoped to the current order."""
        order = self._create_order(db_session)
        other_order = self._create_order(db_session)

        shipment = shipping_service.create_shipment(
            order_id=order.id, weight_lbs=Decimal("5.00"),
        )

        response = logged_in_client.post(
            f"/orders/{other_order.id}/shipping/{shipment.id}/update",
            data={"status": "shipped"},
        )
        assert response.status_code == 404

    def test_cannot_delete_shipment_for_different_order(
        self, app, db_session, logged_in_client
    ):
        """Shipment delete should be scoped to the current order."""
        order = self._create_order(db_session)
        other_order = self._create_order(db_session)

        shipment = shipping_service.create_shipment(
            order_id=order.id, weight_lbs=Decimal("5.00"),
        )

        response = logged_in_client.post(
            f"/orders/{other_order.id}/shipping/{shipment.id}/delete",
        )
        assert response.status_code == 404
