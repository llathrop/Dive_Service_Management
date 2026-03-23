"""Tests for service layer wiring in blueprint edit routes.

Verifies that edit routes delegate to service functions instead of using
form.populate_obj() directly, and that password validation uses the
SystemConfig minimum length setting.
"""

from unittest.mock import patch

import pytest

from tests.factories import (
    BaseFactory,
    CustomerFactory,
    InventoryItemFactory,
    PriceListCategoryFactory,
    PriceListItemFactory,
    SystemConfigFactory,
)

pytestmark = pytest.mark.blueprint


@pytest.fixture(autouse=True)
def _bind_factories(db_session):
    for f in (
        BaseFactory,
        CustomerFactory,
        InventoryItemFactory,
        PriceListCategoryFactory,
        PriceListItemFactory,
        SystemConfigFactory,
    ):
        f._meta.sqlalchemy_session = db_session


class TestCustomerEditServiceLayer:
    """Customer edit route delegates to customer_service.update_customer()."""

    def test_edit_customer_calls_update_service(self, logged_in_client, db_session):
        """POST to customer edit should call update_customer with correct args."""
        customer = CustomerFactory(
            first_name="Original", last_name="Name", customer_type="individual"
        )
        db_session.commit()

        with patch(
            "app.blueprints.customers.customer_service.update_customer",
            wraps=None,
            return_value=customer,
        ) as mock_update:
            resp = logged_in_client.post(
                f"/customers/{customer.id}/edit",
                data={
                    "customer_type": "individual",
                    "first_name": "Updated",
                    "last_name": "Name",
                },
                follow_redirects=False,
            )

            mock_update.assert_called_once()
            call_args = mock_update.call_args
            assert call_args[0][0] == customer.id  # first positional arg is ID
            assert call_args[0][1]["first_name"] == "Updated"

    def test_edit_customer_redirects_on_success(self, logged_in_client, db_session):
        """Successful customer edit should redirect to detail page."""
        customer = CustomerFactory(customer_type="individual")
        db_session.commit()

        resp = logged_in_client.post(
            f"/customers/{customer.id}/edit",
            data={
                "customer_type": "individual",
                "first_name": "NewFirst",
                "last_name": "NewLast",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert f"/customers/{customer.id}" in resp.location


class TestInventoryEditServiceLayer:
    """Inventory edit route delegates to inventory_service.update_inventory_item()."""

    def test_edit_inventory_calls_update_service(self, logged_in_client, db_session):
        """POST to inventory edit should call update_inventory_item."""
        item = InventoryItemFactory(name="Old Widget", category="Parts")
        db_session.commit()

        with patch(
            "app.blueprints.inventory.inventory_service.update_inventory_item",
            wraps=None,
            return_value=item,
        ) as mock_update:
            resp = logged_in_client.post(
                f"/inventory/{item.id}/edit",
                data={
                    "name": "New Widget",
                    "category": "Parts",
                    "quantity_in_stock": "5",
                    "reorder_level": "2",
                    "unit_of_measure": "each",
                },
                follow_redirects=False,
            )

            mock_update.assert_called_once()
            call_args = mock_update.call_args
            assert call_args[0][0] == item.id
            assert call_args[0][1]["name"] == "New Widget"

    def test_edit_inventory_redirects_on_success(self, logged_in_client, db_session):
        """Successful inventory edit should redirect to detail page."""
        item = InventoryItemFactory(name="Widget", category="Parts")
        db_session.commit()

        resp = logged_in_client.post(
            f"/inventory/{item.id}/edit",
            data={
                "name": "Widget Updated",
                "category": "Parts",
                "quantity_in_stock": "10",
                "reorder_level": "3",
                "unit_of_measure": "each",
            },
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert f"/inventory/{item.id}" in resp.location


class TestPriceListEditServiceLayer:
    """Price list edit routes delegate to price_list_service functions."""

    def test_edit_price_list_item_calls_update_service(
        self, admin_client, db_session
    ):
        """POST to price list item edit should call update_price_list_item."""
        category = PriceListCategoryFactory()
        item = PriceListItemFactory(category=category)
        db_session.commit()

        with patch(
            "app.blueprints.price_list.price_list_service.update_price_list_item",
            wraps=None,
            return_value=item,
        ) as mock_update:
            resp = admin_client.post(
                f"/price-list/{item.id}/edit",
                data={
                    "category_id": str(category.id),
                    "name": "Updated Service",
                    "price": "99.99",
                    "is_per_unit": "y",
                    "default_quantity": "1",
                    "unit_label": "each",
                    "is_taxable": "y",
                    "sort_order": "0",
                    "is_active": "y",
                },
                follow_redirects=False,
            )

            mock_update.assert_called_once()
            call_args = mock_update.call_args
            assert call_args[0][0] == item.id  # item_id
            assert call_args[0][1]["name"] == "Updated Service"
            assert call_args[1]["updated_by"] is not None  # keyword arg

    def test_edit_category_calls_update_service(self, admin_client, db_session):
        """POST to category edit should call update_category."""
        category = PriceListCategoryFactory(name="Old Name")
        db_session.commit()

        with patch(
            "app.blueprints.price_list.price_list_service.update_category",
            wraps=None,
            return_value=category,
        ) as mock_update:
            resp = admin_client.post(
                f"/price-list/categories/{category.id}/edit",
                data={
                    "name": "New Name",
                    "sort_order": "1",
                    "is_active": "y",
                },
                follow_redirects=False,
            )

            mock_update.assert_called_once()
            call_args = mock_update.call_args
            assert call_args[0][0] == category.id
            assert call_args[0][1]["name"] == "New Name"


class TestPasswordPolicyConfig:
    """Password validation uses SystemConfig min length."""

    def test_create_user_uses_config_min_length(self, admin_client, app, db_session):
        """User creation should enforce SystemConfig password_min_length."""
        SystemConfigFactory(
            config_key="security.password_min_length",
            config_value="12",
            config_type="integer",
            category="security",
            description="Minimum password length",
        )
        db_session.commit()

        resp = admin_client.post(
            "/admin/users/new",
            data={
                "username": "shortpw",
                "email": "shortpw@example.com",
                "first_name": "Short",
                "last_name": "Password",
                "password": "only10char",  # 10 chars, less than 12
                "roles": [],
            },
            follow_redirects=True,
        )
        html = resp.data.decode()
        assert "at least 12 characters" in html

    def test_create_user_default_min_length(self, admin_client, app, db_session):
        """Without config, password validation defaults to 8 characters."""
        # No SystemConfig entry for password min length
        resp = admin_client.post(
            "/admin/users/new",
            data={
                "username": "shortpw2",
                "email": "shortpw2@example.com",
                "first_name": "Short",
                "last_name": "Password",
                "password": "short",  # 5 chars, less than default 8
                "roles": [],
            },
            follow_redirects=True,
        )
        html = resp.data.decode()
        assert "at least 8 characters" in html

    def test_reset_password_uses_config_min_length(
        self, admin_client, app, db_session
    ):
        """Password reset should enforce SystemConfig password_min_length."""
        from flask_security import hash_password
        user_datastore = app.extensions["security"].datastore
        target_user = user_datastore.create_user(
            username="target",
            email="target@example.com",
            password=hash_password("validpassword123"),
            first_name="Target",
            last_name="User",
        )
        db_session.commit()

        SystemConfigFactory(
            config_key="security.password_min_length",
            config_value="15",
            config_type="integer",
            category="security",
            description="Minimum password length",
        )
        db_session.commit()

        resp = admin_client.post(
            f"/admin/users/{target_user.id}/reset-password",
            data={"new_password": "only12chars!"},  # 12 chars, less than 15
            follow_redirects=True,
        )
        html = resp.data.decode()
        assert "at least 15 characters" in html
