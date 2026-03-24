"""Blueprint tests for service order template CRUD and apply routes."""

import json
from datetime import date
from decimal import Decimal

import pytest

from app.extensions import db
from app.models.customer import Customer
from app.models.inventory import InventoryItem
from app.models.price_list import PriceListCategory, PriceListItem
from app.models.service_order_template import ServiceOrderTemplate
from app.models.service_order import ServiceOrder
from app.models.service_item import ServiceItem
from app.models.service_order_item import ServiceOrderItem
from app.models.user import User
from app.services import template_service

pytestmark = pytest.mark.blueprint


def _create_customer(session):
    """Create a minimal customer for use in tests."""
    c = Customer(
        customer_type="individual",
        first_name="Test",
        last_name="Customer",
        preferred_contact="email",
        country="US",
    )
    session.add(c)
    session.flush()
    return c


def _create_order_with_item(session, customer_id, created_by=None):
    """Create a service order with one service item attached."""
    from app.models.service_item import ServiceItem

    order = ServiceOrder(
        order_number="SO-2026-99999",
        customer_id=customer_id,
        status="intake",
        priority="normal",
        date_received=date.today(),
        created_by=created_by,
    )
    session.add(order)
    session.flush()

    item = ServiceItem(
        name="Test Regulator",
        item_category="regulator",
        customer_id=customer_id,
    )
    session.add(item)
    session.flush()

    oi = ServiceOrderItem(order_id=order.id, service_item_id=item.id)
    session.add(oi)
    session.commit()

    return order


def _create_other_technician(app, db_session, username="othertech", email="othertech@example.com"):
    """Create a second technician user for visibility tests."""
    from flask_security import hash_password

    user_datastore = app.extensions["security"].datastore
    tech_role = user_datastore.find_or_create_role(name="technician")
    user = user_datastore.create_user(
        username=username,
        email=email,
        password=hash_password("password"),
        first_name="Other",
        last_name="Tech",
    )
    user_datastore.add_role_to_user(user, tech_role)
    db_session.commit()
    return user


class TestCreateTemplate:
    """POST /orders/templates/new creates a template."""

    def test_create_template(self, logged_in_client, app, db_session):
        resp = logged_in_client.post("/orders/templates/new", data={
            "name": "Annual Service",
            "description": "Standard yearly service",
            "priority": "normal",
            "rush_fee": "0.00",
            "notes": "Check all seals",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"Template created successfully" in resp.data

        with app.app_context():
            tmpl = ServiceOrderTemplate.query.filter_by(name="Annual Service").first()
            assert tmpl is not None
            assert tmpl.description == "Standard yearly service"
            assert tmpl.template_data.get("priority") == "normal"
            assert tmpl.template_data.get("notes") == "Check all seals"

    def test_create_template_empty_name(self, logged_in_client):
        """Submitting an empty name shows an error."""
        resp = logged_in_client.post("/orders/templates/new", data={
            "name": "",
            "description": "No name",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"Template name is required" in resp.data


class TestListTemplates:
    """GET /orders/templates lists templates."""

    def test_list_templates(self, logged_in_client, app, db_session):
        user = User.query.first()
        tmpl = ServiceOrderTemplate(
            name="My Template",
            created_by_id=user.id,
            is_shared=False,
            template_data={"priority": "high"},
        )
        db.session.add(tmpl)
        db.session.commit()

        resp = logged_in_client.get("/orders/templates")
        assert resp.status_code == 200
        assert b"My Template" in resp.data

    def test_list_templates_excludes_others_private(self, admin_client, app, db_session):
        """Other users' private templates should not appear."""
        from flask_security import hash_password

        user_datastore = app.extensions["security"].datastore
        tech_role = user_datastore.find_or_create_role(name="technician")
        other_user = user_datastore.create_user(
            username="other", email="other@example.com",
            password=hash_password("password"),
            first_name="Other", last_name="User",
        )
        user_datastore.add_role_to_user(other_user, tech_role)
        db.session.commit()

        # Create private template as other user
        tmpl = ServiceOrderTemplate(
            name="Private Other",
            created_by_id=other_user.id,
            is_shared=False,
            template_data={},
        )
        db.session.add(tmpl)
        db.session.commit()

        resp = admin_client.get("/orders/templates")
        assert resp.status_code == 200
        assert b"Private Other" not in resp.data

    def test_list_shows_shared_from_others(self, admin_client, app, db_session):
        """Shared templates from other users should appear."""
        from flask_security import hash_password

        user_datastore = app.extensions["security"].datastore
        tech_role = user_datastore.find_or_create_role(name="technician")
        other_user = user_datastore.create_user(
            username="other2", email="other2@example.com",
            password=hash_password("password"),
            first_name="Other2", last_name="User",
        )
        user_datastore.add_role_to_user(other_user, tech_role)
        db.session.commit()

        tmpl = ServiceOrderTemplate(
            name="Shared Template",
            created_by_id=other_user.id,
            is_shared=True,
            template_data={},
        )
        db.session.add(tmpl)
        db.session.commit()

        resp = admin_client.get("/orders/templates")
        assert resp.status_code == 200
        assert b"Shared Template" in resp.data

    def test_shared_template_list_hides_owner_controls_for_non_owner(self, admin_client, app, db_session):
        other_user = _create_other_technician(app, db_session, username="listcontrols", email="listcontrols@example.com")
        tmpl = ServiceOrderTemplate(
            name="Shared List Controls",
            created_by_id=other_user.id,
            is_shared=True,
            template_data={},
        )
        db.session.add(tmpl)
        db.session.commit()

        resp = admin_client.get("/orders/templates")
        assert resp.status_code == 200
        assert b"Shared List Controls" in resp.data
        assert f"/orders/templates/{tmpl.id}/edit".encode() not in resp.data
        assert f"/orders/templates/{tmpl.id}/delete".encode() not in resp.data


class TestUpdateTemplate:
    """POST /orders/templates/<id>/edit updates a template."""

    def test_update_template(self, logged_in_client, app, db_session):
        user = User.query.first()
        tmpl = ServiceOrderTemplate(
            name="Old Name",
            created_by_id=user.id,
            is_shared=False,
            template_data={"priority": "low"},
        )
        db.session.add(tmpl)
        db.session.commit()
        tmpl_id = tmpl.id

        resp = logged_in_client.post(f"/orders/templates/{tmpl_id}/edit", data={
            "name": "New Name",
            "description": "Updated desc",
            "priority": "high",
        }, follow_redirects=True)
        assert resp.status_code == 200
        assert b"Template updated successfully" in resp.data

        with app.app_context():
            updated = db.session.get(ServiceOrderTemplate, tmpl_id)
            assert updated.name == "New Name"
            assert updated.template_data.get("priority") == "high"

    def test_shared_template_cannot_be_edited_by_non_owner(self, admin_client, app, db_session):
        other_user = _create_other_technician(app, db_session)
        tmpl = ServiceOrderTemplate(
            name="Shared But Not Mine",
            created_by_id=other_user.id,
            is_shared=True,
            template_data={"priority": "normal"},
        )
        db.session.add(tmpl)
        db.session.commit()

        resp = admin_client.get(f"/orders/templates/{tmpl.id}/edit")
        assert resp.status_code == 404

    def test_edit_form_renders_existing_template(self, logged_in_client, app, db_session):
        """GET /orders/templates/<id>/edit should render without crashing."""
        user = User.query.first()
        tmpl = ServiceOrderTemplate(
            name="Edit Render",
            description="Render test",
            created_by_id=user.id,
            is_shared=False,
            template_data={
                "priority": "rush",
                "rush_fee": "25.00",
                "discount_percent": "5.00",
                "estimated_labor_hours": "2.5",
                "notes": "Prefill notes",
            },
        )
        db.session.add(tmpl)
        db.session.commit()

        resp = logged_in_client.get(f"/orders/templates/{tmpl.id}/edit")
        assert resp.status_code == 200
        assert b"Edit Template: Edit Render" in resp.data
        assert b"Prefill notes" in resp.data


class TestDeleteTemplate:
    """POST /orders/templates/<id>/delete deletes a template."""

    def test_delete_template(self, logged_in_client, app, db_session):
        user = User.query.first()
        tmpl = ServiceOrderTemplate(
            name="To Delete",
            created_by_id=user.id,
            is_shared=False,
            template_data={},
        )
        db.session.add(tmpl)
        db.session.commit()
        tmpl_id = tmpl.id

        resp = logged_in_client.post(
            f"/orders/templates/{tmpl_id}/delete",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Template deleted" in resp.data

        with app.app_context():
            assert db.session.get(ServiceOrderTemplate, tmpl_id) is None

    def test_shared_template_cannot_be_deleted_by_non_owner(self, admin_client, app, db_session):
        other_user = _create_other_technician(app, db_session, username="deleteother", email="deleteother@example.com")
        tmpl = ServiceOrderTemplate(
            name="Shared Delete",
            created_by_id=other_user.id,
            is_shared=True,
            template_data={},
        )
        db.session.add(tmpl)
        db.session.commit()

        resp = admin_client.post(f"/orders/templates/{tmpl.id}/delete")
        assert resp.status_code == 404


class TestTemplateDetail:
    """GET /orders/templates/<id> renders detail page."""

    def test_template_detail_page(self, logged_in_client, app, db_session):
        user = User.query.first()
        tmpl = ServiceOrderTemplate(
            name="Detail Test",
            description="A test template",
            created_by_id=user.id,
            is_shared=True,
            template_data={"priority": "rush", "notes": "Urgent service"},
        )
        db.session.add(tmpl)
        db.session.commit()

        resp = logged_in_client.get(f"/orders/templates/{tmpl.id}")
        assert resp.status_code == 200
        assert b"Detail Test" in resp.data
        assert b"Urgent service" in resp.data
        assert b"Shared" in resp.data

    def test_shared_template_detail_hides_owner_controls_for_non_owner(self, admin_client, app, db_session):
        other_user = _create_other_technician(app, db_session, username="detailcontrols", email="detailcontrols@example.com")
        tmpl = ServiceOrderTemplate(
            name="Shared Detail Controls",
            created_by_id=other_user.id,
            is_shared=True,
            template_data={"priority": "rush"},
        )
        db.session.add(tmpl)
        db.session.commit()

        resp = admin_client.get(f"/orders/templates/{tmpl.id}")
        assert resp.status_code == 200
        assert b"Shared Detail Controls" in resp.data
        assert f"/orders/templates/{tmpl.id}/edit".encode() not in resp.data
        assert f"/orders/templates/{tmpl.id}/delete".encode() not in resp.data

    def test_preview_template_returns_json(self, logged_in_client, app, db_session):
        user = User.query.first()
        tmpl = ServiceOrderTemplate(
            name="Preview Test",
            description="A test template",
            created_by_id=user.id,
            is_shared=True,
            template_data={"priority": "rush", "notes": "Urgent service"},
        )
        db.session.add(tmpl)
        db.session.commit()

        resp = logged_in_client.get(f"/orders/templates/{tmpl.id}/preview")
        assert resp.status_code == 200
        payload = json.loads(resp.data)
        assert payload["id"] == tmpl.id
        assert payload["template_data"]["priority"] == "rush"

    def test_private_template_is_hidden_from_other_user(self, admin_client, app, db_session):
        other_user = _create_other_technician(app, db_session)
        tmpl = ServiceOrderTemplate(
            name="Hidden Detail",
            description="Should not leak",
            created_by_id=other_user.id,
            is_shared=False,
            template_data={},
        )
        db.session.add(tmpl)
        db.session.commit()

        resp = admin_client.get(f"/orders/templates/{tmpl.id}")
        assert resp.status_code == 404

    def test_private_template_edit_delete_apply_are_hidden(self, admin_client, app, db_session):
        other_user = _create_other_technician(app, db_session, username="hiddenops", email="hiddenops@example.com")
        customer = _create_customer(db_session)
        order = _create_order_with_item(db_session, customer.id, created_by=other_user.id)
        tmpl = ServiceOrderTemplate(
            name="Hidden Ops",
            description="Should not be editable",
            created_by_id=other_user.id,
            is_shared=False,
            template_data={"priority": "high"},
        )
        db.session.add(tmpl)
        db.session.commit()

        edit_resp = admin_client.get(f"/orders/templates/{tmpl.id}/edit")
        delete_resp = admin_client.post(f"/orders/templates/{tmpl.id}/delete")
        apply_resp = admin_client.post(f"/orders/templates/{tmpl.id}/apply/{order.id}")
        assert edit_resp.status_code == 404
        assert delete_resp.status_code == 404
        assert apply_resp.status_code == 404


class TestApplyTemplate:
    """POST /orders/templates/<id>/apply/<order_id> applies template."""

    def test_apply_template_to_order(self, logged_in_client, app, db_session):
        user = User.query.first()
        customer = _create_customer(db_session)
        order = _create_order_with_item(db_session, customer.id, created_by=user.id)

        tmpl = ServiceOrderTemplate(
            name="Apply Test",
            created_by_id=user.id,
            is_shared=False,
            template_data={
                "priority": "high",
                "rush_fee": "50.00",
                "notes": "Applied notes",
            },
        )
        db.session.add(tmpl)
        db.session.commit()

        resp = logged_in_client.post(
            f"/orders/templates/{tmpl.id}/apply/{order.id}",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Template applied" in resp.data

        with app.app_context():
            updated_order = db.session.get(ServiceOrder, order.id)
            assert updated_order.priority == "high"

    def test_shared_template_can_be_applied_by_non_owner(self, admin_client, app, db_session):
        other_user = _create_other_technician(app, db_session, username="applyother", email="applyother@example.com")
        customer = _create_customer(db_session)
        order = _create_order_with_item(db_session, customer.id, created_by=other_user.id)
        tmpl = ServiceOrderTemplate(
            name="Shared Apply",
            created_by_id=other_user.id,
            is_shared=True,
            template_data={"priority": "rush"},
        )
        db.session.add(tmpl)
        db.session.commit()

        resp = admin_client.post(
            f"/orders/templates/{tmpl.id}/apply/{order.id}",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Template applied" in resp.data

        with app.app_context():
            updated_order = db.session.get(ServiceOrder, order.id)
            assert updated_order.priority == "rush"

    def test_apply_template_with_services_and_parts_to_single_item_order(self, logged_in_client, app, db_session):
        user = User.query.first()
        customer = _create_customer(db_session)
        order = _create_order_with_item(db_session, customer.id, created_by=user.id)
        order_item = ServiceOrderItem.query.filter_by(order_id=order.id).first()

        category = PriceListCategory(
            name="Service",
            description="Service category",
            sort_order=1,
            is_active=True,
        )
        db.session.add(category)
        db.session.flush()

        price_item = PriceListItem(
            category_id=category.id,
            name="Full Service",
            price=Decimal("150.00"),
            is_active=True,
        )
        inventory_item = InventoryItem(
            sku="PART-001",
            name="O-Ring Kit",
            category="Seals",
            purchase_cost=Decimal("2.00"),
            resale_price=Decimal("5.00"),
            quantity_in_stock=10,
            reorder_level=2,
            unit_of_measure="each",
            is_active=True,
        )
        db.session.add_all([price_item, inventory_item])
        db.session.commit()

        tmpl = ServiceOrderTemplate(
            name="Service + Part",
            created_by_id=user.id,
            is_shared=False,
            template_data={
                "priority": "high",
                "services": [{"price_list_item_id": price_item.id, "quantity": 1}],
                "parts": [{"inventory_item_id": inventory_item.id, "quantity": 2}],
            },
        )
        db.session.add(tmpl)
        db.session.commit()

        resp = logged_in_client.post(
            f"/orders/templates/{tmpl.id}/apply/{order.id}",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"Template applied" in resp.data

        with app.app_context():
            updated_order = db.session.get(ServiceOrder, order.id)
            assert updated_order.priority == "high"

            updated_item = db.session.get(ServiceOrderItem, order_item.id)
            assert updated_item.applied_services.count() == 1
            assert updated_item.parts_used.count() == 1
            assert db.session.get(InventoryItem, inventory_item.id).quantity_in_stock == 8

    def test_apply_template_fails_when_order_has_multiple_items(self, logged_in_client, app, db_session):
        user = User.query.first()
        customer = _create_customer(db_session)
        order = _create_order_with_item(db_session, customer.id, created_by=user.id)

        extra_item = ServiceItem(
            name="Second Item",
            item_category="regulator",
            customer_id=customer.id,
        )
        db_session.add(extra_item)
        db_session.flush()
        db_session.add(ServiceOrderItem(order_id=order.id, service_item_id=extra_item.id))
        db_session.commit()

        tmpl = ServiceOrderTemplate(
            name="Ambiguous Apply",
            created_by_id=user.id,
            is_shared=False,
            template_data={
                "priority": "high",
                "services": [{"price_list_item_id": 1, "quantity": 1}],
            },
        )
        db_session.add(tmpl)
        db_session.commit()

        resp = logged_in_client.post(
            f"/orders/templates/{tmpl.id}/apply/{order.id}",
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"requires exactly one order item" in resp.data

        with app.app_context():
            updated_order = db.session.get(ServiceOrder, order.id)
            assert updated_order.priority == "normal"

    def test_preview_template_respects_visibility(self, admin_client, app, db_session):
        other_user = _create_other_technician(app, db_session, username="previewtech", email="previewtech@example.com")
        tmpl = ServiceOrderTemplate(
            name="Hidden Preview",
            created_by_id=other_user.id,
            is_shared=False,
            template_data={"priority": "high"},
        )
        db.session.add(tmpl)
        db.session.commit()

        resp = admin_client.get(f"/orders/templates/{tmpl.id}/preview")
        assert resp.status_code == 404

    def test_apply_template_blocks_unknown_items(self, logged_in_client, app, db_session):
        user = User.query.first()
        customer = _create_customer(db_session)
        order = _create_order_with_item(db_session, customer.id, created_by=user.id)

        tmpl = ServiceOrderTemplate(
            name="Broken Template",
            created_by_id=user.id,
            is_shared=False,
            template_data={
                "priority": "high",
                "services": [{"price_list_item_id": 99999, "quantity": 1}],
            },
        )
        db.session.add(tmpl)
        db.session.commit()

        with app.app_context():
            with pytest.raises(ValueError, match="not available"):
                template_service.apply_template(
                    order_id=order.id,
                    template_id=tmpl.id,
                    user_id=user.id,
                )

            updated_order = db.session.get(ServiceOrder, order.id)
            assert updated_order.priority == "normal"

    def test_create_template_shows_validation_errors_for_bad_line_items(
        self, logged_in_client
    ):
        resp = logged_in_client.post(
            "/orders/templates/new",
            data={
                "name": "Malformed Template",
                "service_pli_id[]": ["abc", "1"],
                "service_qty[]": ["1", "two"],
                "part_inv_id[]": ["xyz", "1"],
                "part_qty[]": ["1", "3.5"],
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"valid numeric service IDs" in resp.data
        assert b"whole numbers" in resp.data
        assert b"valid numeric inventory IDs" in resp.data

    def test_edit_template_shows_validation_errors_for_bad_line_items(
        self, logged_in_client, app, db_session
    ):
        user = User.query.first()
        tmpl = ServiceOrderTemplate(
            name="Editable Template",
            created_by_id=user.id,
            is_shared=False,
            template_data={},
        )
        db.session.add(tmpl)
        db.session.commit()

        resp = logged_in_client.post(
            f"/orders/templates/{tmpl.id}/edit",
            data={
                "name": "Editable Template",
                "service_pli_id[]": ["1"],
                "service_qty[]": ["oops"],
                "part_inv_id[]": ["bad"],
                "part_qty[]": ["1"],
            },
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert b"whole numbers" in resp.data
        assert b"valid numeric inventory IDs" in resp.data


class TestViewerAccess:
    """Viewer role cannot access template routes."""

    def test_viewer_cannot_access(self, viewer_client):
        resp = viewer_client.get("/orders/templates")
        assert resp.status_code == 403

    def test_viewer_cannot_create(self, viewer_client):
        resp = viewer_client.post("/orders/templates/new", data={
            "name": "Should Fail",
        })
        assert resp.status_code == 403

    def test_viewer_cannot_view_private_template_detail(self, viewer_client, app, db_session):
        other_user = _create_other_technician(app, db_session, username="viewerhidden", email="viewerhidden@example.com")
        tmpl = ServiceOrderTemplate(
            name="Viewer Hidden",
            created_by_id=other_user.id,
            is_shared=False,
            template_data={},
        )
        db.session.add(tmpl)
        db.session.commit()

        resp = viewer_client.get(f"/orders/templates/{tmpl.id}")
        assert resp.status_code == 403
