"""Customer service layer — business logic for customer CRUD operations.

Provides module-level functions for creating, reading, updating, deleting,
and searching customers.  All queries exclude soft-deleted records by default.
"""

from flask import abort
from sqlalchemy import or_

from app.extensions import db
from app.models.customer import Customer


def get_customers(
    page=1,
    per_page=25,
    search=None,
    customer_type=None,
    sort="last_name",
    order="asc",
):
    """Return paginated, filtered, sorted customers (excluding soft-deleted).

    Args:
        page: Page number (1-indexed).
        per_page: Number of results per page.
        search: Optional search string to match against name, business_name,
            email, or phone.
        customer_type: Optional filter for 'individual' or 'business'.
        sort: Column name to sort by.  Defaults to 'last_name'.
        order: Sort direction, 'asc' or 'desc'.

    Returns:
        A SQLAlchemy pagination object.
    """
    query = Customer.not_deleted()

    # Apply search filter
    if search:
        pattern = f"%{search}%"
        query = query.filter(
            or_(
                Customer.first_name.ilike(pattern),
                Customer.last_name.ilike(pattern),
                Customer.business_name.ilike(pattern),
                Customer.email.ilike(pattern),
                Customer.phone_primary.ilike(pattern),
            )
        )

    # Apply customer_type filter
    if customer_type:
        query = query.filter(Customer.customer_type == customer_type)

    # Apply sorting
    sort_column = getattr(Customer, sort, Customer.last_name)
    if order == "desc":
        query = query.order_by(sort_column.desc())
    else:
        query = query.order_by(sort_column.asc())

    return db.paginate(query, page=page, per_page=per_page)


def get_customer(customer_id):
    """Return a single customer by ID or raise 404.

    Args:
        customer_id: The primary key of the customer.

    Returns:
        A Customer instance.

    Raises:
        404 HTTPException if the customer does not exist.
    """
    customer = db.session.get(Customer, customer_id)
    if customer is None or customer.is_deleted:
        abort(404)
    return customer


def create_customer(data, created_by=None):
    """Create a new customer from a data dict.

    Args:
        data: Dictionary of customer fields (e.g. from a form).
        created_by: Optional user ID of the creator.

    Returns:
        The newly created Customer instance.
    """
    customer = Customer(
        customer_type=data.get("customer_type", "individual"),
        first_name=data.get("first_name"),
        last_name=data.get("last_name"),
        business_name=data.get("business_name"),
        contact_person=data.get("contact_person"),
        email=data.get("email"),
        phone_primary=data.get("phone_primary"),
        phone_secondary=data.get("phone_secondary"),
        address_line1=data.get("address_line1"),
        address_line2=data.get("address_line2"),
        city=data.get("city"),
        state_province=data.get("state_province"),
        postal_code=data.get("postal_code"),
        country=data.get("country", "US"),
        preferred_contact=data.get("preferred_contact", "email"),
        tax_exempt=data.get("tax_exempt", False),
        tax_id=data.get("tax_id"),
        payment_terms=data.get("payment_terms"),
        credit_limit=data.get("credit_limit"),
        notes=data.get("notes"),
        referral_source=data.get("referral_source"),
        created_by=created_by,
    )
    customer.validate_name()
    db.session.add(customer)
    db.session.commit()
    return customer


def update_customer(customer_id, data):
    """Update an existing customer from a data dict.

    Args:
        customer_id: The primary key of the customer to update.
        data: Dictionary of fields to update.

    Returns:
        The updated Customer instance.

    Raises:
        404 HTTPException if the customer does not exist.
    """
    customer = get_customer(customer_id)

    for field in (
        "customer_type",
        "first_name",
        "last_name",
        "business_name",
        "contact_person",
        "email",
        "phone_primary",
        "phone_secondary",
        "address_line1",
        "address_line2",
        "city",
        "state_province",
        "postal_code",
        "country",
        "preferred_contact",
        "tax_exempt",
        "tax_id",
        "payment_terms",
        "credit_limit",
        "notes",
        "referral_source",
    ):
        if field in data:
            setattr(customer, field, data[field])

    customer.validate_name()
    db.session.commit()
    return customer


def delete_customer(customer_id):
    """Soft-delete a customer.

    Args:
        customer_id: The primary key of the customer to delete.

    Returns:
        The soft-deleted Customer instance.

    Raises:
        404 HTTPException if the customer does not exist.
    """
    customer = get_customer(customer_id)
    customer.soft_delete()
    db.session.commit()
    return customer


def get_customer_orders(customer_id, active_only=None):
    """Return orders for a customer. active_only=True for open, False for completed."""
    from app.models.service_order import ServiceOrder

    ACTIVE_STATUSES = [
        "intake", "assessment", "awaiting_approval", "in_progress", "awaiting_parts",
    ]
    query = ServiceOrder.not_deleted().filter_by(customer_id=customer_id)
    if active_only is True:
        query = query.filter(ServiceOrder.status.in_(ACTIVE_STATUSES))
    elif active_only is False:
        query = query.filter(~ServiceOrder.status.in_(ACTIVE_STATUSES))
    return query.order_by(ServiceOrder.date_received.desc()).all()


