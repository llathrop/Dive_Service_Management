"""Factory Boy factories for all application models.

Each factory generates realistic test data using Faker and follows
the project convention of using ``class Meta: model = ...`` with
``sqlalchemy_session`` injected at test time.

Usage in tests::

    from tests.factories import CustomerFactory

    def test_something(db_session):
        CustomerFactory._meta.sqlalchemy_session = db_session
        customer = CustomerFactory()
        ...
"""

import re
import uuid
from datetime import date
from decimal import Decimal

import factory
from factory import Faker, LazyAttribute, SubFactory, Trait
from factory.alchemy import SQLAlchemyModelFactory
from faker import Faker as FakerInstance

from app.models.applied_service import AppliedService
from app.models.customer import Customer
from app.models.drysuit_details import DrysuitDetails
from app.models.inventory import InventoryItem
from app.models.labor import LaborEntry
from app.models.parts_used import PartUsed
from app.models.price_list import (
    PriceListCategory,
    PriceListItem,
    PriceListItemPart,
)
from app.models.service_item import ServiceItem
from app.models.service_note import ServiceNote
from app.models.service_order import ServiceOrder
from app.models.service_order_item import ServiceOrderItem
from app.models.tag import Tag, Taggable
from app.models.user import Role, User

fake = FakerInstance()


# ---------------------------------------------------------------------------
# Base factory
# ---------------------------------------------------------------------------

class BaseFactory(SQLAlchemyModelFactory):
    """Base factory with shared Meta configuration."""

    class Meta:
        abstract = True
        sqlalchemy_session = None
        sqlalchemy_session_persistence = "commit"


# ---------------------------------------------------------------------------
# User / Role factories
# ---------------------------------------------------------------------------

class RoleFactory(BaseFactory):
    """Factory for the Role model."""

    class Meta:
        model = Role

    name = factory.Sequence(lambda n: f"role_{n}")
    description = Faker("sentence", nb_words=5)


class UserFactory(BaseFactory):
    """Factory for the User model."""

    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user_{n}")
    email = factory.LazyAttribute(lambda o: f"{o.username}@example.com")
    first_name = Faker("first_name")
    last_name = Faker("last_name")
    password = "password"
    active = True
    fs_uniquifier = LazyAttribute(lambda o: str(uuid.uuid4()))


# ---------------------------------------------------------------------------
# Customer factory
# ---------------------------------------------------------------------------

class CustomerFactory(BaseFactory):
    """Factory for the Customer model.

    By default creates an individual customer.  Use the ``business``
    trait to create a business customer instead::

        CustomerFactory(business=True)
    """

    class Meta:
        model = Customer

    customer_type = "individual"
    first_name = Faker("first_name")
    last_name = Faker("last_name")
    email = Faker("email")
    phone_primary = Faker("phone_number")
    address_line1 = Faker("street_address")
    city = Faker("city")
    state_province = Faker("state_abbr")
    postal_code = Faker("zipcode")
    country = "US"
    preferred_contact = "email"

    class Params:
        business = Trait(
            customer_type="business",
            first_name=None,
            last_name=None,
            business_name=Faker("company"),
            contact_person=Faker("name"),
        )


# ---------------------------------------------------------------------------
# ServiceItem factory
# ---------------------------------------------------------------------------

class ServiceItemFactory(BaseFactory):
    """Factory for the ServiceItem model."""

    class Meta:
        model = ServiceItem

    name = Faker("catch_phrase")
    item_category = factory.LazyFunction(
        lambda: factory.Faker._get_faker().random_element(
            ["Regulator", "BCD", "Drysuit", "Wetsuit", "Tank", "Computer"]
        )
    )
    serviceability = "serviceable"
    brand = Faker("company")
    model = Faker("bothify", text="??-####")
    customer = None


# ---------------------------------------------------------------------------
# DrysuitDetails factory
# ---------------------------------------------------------------------------

class DrysuitDetailsFactory(BaseFactory):
    """Factory for the DrysuitDetails model.

    Automatically creates a parent ServiceItem with category='Drysuit'.
    """

    class Meta:
        model = DrysuitDetails

    service_item = SubFactory(
        ServiceItemFactory,
        item_category="Drysuit",
        name="Test Drysuit",
    )
    size = factory.LazyFunction(
        lambda: factory.Faker._get_faker().random_element(
            ["S", "M", "L", "XL", "XXL", "Custom"]
        )
    )
    material_type = factory.LazyFunction(
        lambda: factory.Faker._get_faker().random_element(
            ["Trilaminate", "Neoprene", "Crushed Neoprene", "Vulcanized Rubber"]
        )
    )
    material_thickness = "4mm"
    color = "Black"
    neck_seal_type = "Latex"
    wrist_seal_type = "Latex"
    zipper_type = "YKK Aquaseal"


# ---------------------------------------------------------------------------
# InventoryItem factory
# ---------------------------------------------------------------------------

class InventoryItemFactory(BaseFactory):
    """Factory for the InventoryItem model."""

    class Meta:
        model = InventoryItem

    sku = factory.Sequence(lambda n: f"SKU-{n:05d}")
    name = Faker("catch_phrase")
    category = factory.LazyFunction(
        lambda: factory.Faker._get_faker().random_element(
            ["Seals", "O-Rings", "Zippers", "Valves", "Adhesives", "Hardware"]
        )
    )
    purchase_cost = factory.LazyFunction(
        lambda: Decimal(str(round(factory.Faker._get_faker().pyfloat(
            min_value=1, max_value=100, right_digits=2
        ), 2)))
    )
    resale_price = factory.LazyFunction(
        lambda: Decimal(str(round(factory.Faker._get_faker().pyfloat(
            min_value=5, max_value=200, right_digits=2
        ), 2)))
    )
    quantity_in_stock = 10
    reorder_level = 5
    unit_of_measure = "each"
    is_active = True


# ---------------------------------------------------------------------------
# PriceList factories
# ---------------------------------------------------------------------------

class PriceListCategoryFactory(BaseFactory):
    """Factory for the PriceListCategory model."""

    class Meta:
        model = PriceListCategory

    name = factory.Sequence(lambda n: f"Category {n}")
    description = Faker("sentence", nb_words=8)
    sort_order = factory.Sequence(lambda n: n)
    is_active = True


class PriceListItemFactory(BaseFactory):
    """Factory for the PriceListItem model."""

    class Meta:
        model = PriceListItem

    category = SubFactory(PriceListCategoryFactory)
    code = factory.Sequence(lambda n: f"SVC-{n:04d}")
    name = Faker("catch_phrase")
    description = Faker("sentence", nb_words=10)
    price = factory.LazyFunction(
        lambda: Decimal(str(round(factory.Faker._get_faker().pyfloat(
            min_value=10, max_value=500, right_digits=2
        ), 2)))
    )
    cost = factory.LazyFunction(
        lambda: Decimal(str(round(factory.Faker._get_faker().pyfloat(
            min_value=5, max_value=200, right_digits=2
        ), 2)))
    )
    is_per_unit = True
    default_quantity = Decimal("1")
    unit_label = "each"
    is_taxable = True
    is_active = True


class PriceListItemPartFactory(BaseFactory):
    """Factory for the PriceListItemPart model."""

    class Meta:
        model = PriceListItemPart

    price_list_item = SubFactory(PriceListItemFactory)
    inventory_item = SubFactory(InventoryItemFactory)
    quantity = Decimal("1")
    notes = None


# ---------------------------------------------------------------------------
# Tag factories
# ---------------------------------------------------------------------------

def _slugify(text):
    """Convert text to a URL-friendly slug."""
    slug = text.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug)
    return slug.strip("-")


class TagFactory(BaseFactory):
    """Factory for the Tag model."""

    class Meta:
        model = Tag

    name = factory.Sequence(lambda n: f"tag-{n}")
    slug = LazyAttribute(lambda o: _slugify(o.name))
    color = Faker("hex_color")
    tag_group = None


class TaggableFactory(BaseFactory):
    """Factory for the Taggable model."""

    class Meta:
        model = Taggable

    tag = SubFactory(TagFactory)
    taggable_type = "customer"
    taggable_id = factory.Sequence(lambda n: n + 1)


# ---------------------------------------------------------------------------
# ServiceOrder factories
# ---------------------------------------------------------------------------

class ServiceOrderFactory(BaseFactory):
    """Factory for the ServiceOrder model."""

    class Meta:
        model = ServiceOrder

    order_number = factory.LazyFunction(
        lambda: f"SO-2026-{fake.unique.random_int(min=1, max=99999):05d}"
    )
    customer = SubFactory(CustomerFactory)
    status = "intake"
    priority = "normal"
    date_received = factory.LazyFunction(date.today)
    description = Faker("sentence")


class ServiceOrderItemFactory(BaseFactory):
    """Factory for the ServiceOrderItem model."""

    class Meta:
        model = ServiceOrderItem

    order = SubFactory(ServiceOrderFactory)
    service_item = SubFactory(ServiceItemFactory)
    work_description = Faker("sentence")
    status = "pending"


class ServiceNoteFactory(BaseFactory):
    """Factory for the ServiceNote model.

    The ``created_by`` field is required (NOT NULL).  Pass either
    ``created_by=<user_id>`` or let the test set it explicitly.
    When using this factory standalone, be sure to provide a valid
    ``created_by`` value.
    """

    class Meta:
        model = ServiceNote

    order_item = SubFactory(ServiceOrderItemFactory)
    note_text = Faker("paragraph")
    note_type = "general"
    # created_by must be set by the caller (NOT NULL FK to users.id)


class PartUsedFactory(BaseFactory):
    """Factory for the PartUsed model."""

    class Meta:
        model = PartUsed

    order_item = SubFactory(ServiceOrderItemFactory)
    inventory_item = SubFactory(InventoryItemFactory)
    quantity = factory.LazyFunction(lambda: Decimal("1.00"))
    unit_cost_at_use = factory.LazyFunction(lambda: Decimal("10.00"))
    unit_price_at_use = factory.LazyFunction(lambda: Decimal("25.00"))


class LaborEntryFactory(BaseFactory):
    """Factory for the LaborEntry model.

    The ``tech`` (or ``tech_id``) field is required (NOT NULL).
    Pass ``tech=<UserInstance>`` or ``tech_id=<int>`` explicitly.
    """

    class Meta:
        model = LaborEntry

    order_item = SubFactory(ServiceOrderItemFactory)
    hours = factory.LazyFunction(lambda: Decimal("1.00"))
    hourly_rate = factory.LazyFunction(lambda: Decimal("75.00"))
    work_date = factory.LazyFunction(date.today)
    # tech / tech_id must be set by the caller (NOT NULL FK to users.id)


class AppliedServiceFactory(BaseFactory):
    """Factory for the AppliedService model."""

    class Meta:
        model = AppliedService

    order_item = SubFactory(ServiceOrderItemFactory)
    service_name = Faker("sentence", nb_words=3)
    quantity = factory.LazyFunction(lambda: Decimal("1.00"))
    unit_price = factory.LazyFunction(lambda: Decimal("100.00"))
    discount_percent = factory.LazyFunction(lambda: Decimal("0.00"))
    line_total = factory.LazyFunction(lambda: Decimal("100.00"))


# ---------------------------------------------------------------------------
# Invoice / Payment factories
# ---------------------------------------------------------------------------

from app.models.invoice import Invoice, InvoiceLineItem
from app.models.payment import Payment


class InvoiceFactory(BaseFactory):
    """Factory for the Invoice model."""

    class Meta:
        model = Invoice

    invoice_number = factory.LazyFunction(
        lambda: f"INV-2026-{fake.unique.random_int(min=1, max=99999):05d}"
    )
    customer = SubFactory(CustomerFactory)
    status = "draft"
    issue_date = factory.LazyFunction(date.today)
    subtotal = factory.LazyFunction(lambda: Decimal("100.00"))
    total = factory.LazyFunction(lambda: Decimal("100.00"))
    balance_due = factory.LazyFunction(lambda: Decimal("100.00"))


class InvoiceLineItemFactory(BaseFactory):
    """Factory for the InvoiceLineItem model."""

    class Meta:
        model = InvoiceLineItem

    invoice = SubFactory(InvoiceFactory)
    line_type = "service"
    description = Faker("sentence", nb_words=4)
    quantity = factory.LazyFunction(lambda: Decimal("1.00"))
    unit_price = factory.LazyFunction(lambda: Decimal("100.00"))
    line_total = factory.LazyFunction(lambda: Decimal("100.00"))


class PaymentFactory(BaseFactory):
    """Factory for the Payment model."""

    class Meta:
        model = Payment

    invoice = SubFactory(InvoiceFactory)
    payment_type = "payment"
    amount = factory.LazyFunction(lambda: Decimal("50.00"))
    payment_date = factory.LazyFunction(date.today)
    payment_method = "cash"


# ---------------------------------------------------------------------------
# Notification factory
# ---------------------------------------------------------------------------

from app.models.notification import Notification


class NotificationFactory(BaseFactory):
    """Factory for the Notification model."""

    class Meta:
        model = Notification

    notification_type = "system"
    title = Faker("sentence", nb_words=4)
    message = Faker("sentence", nb_words=8)
    severity = "info"
    is_read = False
