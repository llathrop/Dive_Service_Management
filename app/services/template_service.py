"""Template service layer — CRUD and application logic for order templates.

Provides functions for creating, listing, updating, deleting, and applying
service order templates.  Templates store reusable configurations that can
be applied to existing orders to pre-populate services, parts, and settings.
"""

from decimal import Decimal

from sqlalchemy.exc import SQLAlchemyError

from flask import abort
from sqlalchemy import or_

from app.extensions import db
from app.models.inventory import InventoryItem
from app.models.price_list import PriceListItem
from app.models.service_order_template import ServiceOrderTemplate
from app.services import audit_service, order_service


# =========================================================================
# Template CRUD
# =========================================================================

def create_template(name, description, created_by_id, is_shared, template_data,
                    ip_address=None, user_agent=None):
    """Create a new service order template.

    Args:
        name: Template name (required, non-empty).
        description: Optional description.
        created_by_id: User ID of the creator.
        is_shared: Whether the template is visible to all users.
        template_data: Dict of template configuration.
        ip_address: Optional IP for audit logging.
        user_agent: Optional user agent for audit logging.

    Returns:
        The newly created ServiceOrderTemplate.

    Raises:
        ValueError: If name is empty.
    """
    if not name or not name.strip():
        raise ValueError("Template name is required.")

    template = ServiceOrderTemplate(
        name=name.strip(),
        description=description,
        created_by_id=created_by_id,
        is_shared=is_shared,
        template_data=template_data or {},
    )
    db.session.add(template)
    db.session.commit()

    try:
        audit_service.log_action(
            action="create",
            entity_type="service_order_template",
            entity_id=template.id,
            user_id=created_by_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except Exception:
        pass

    return template


def get_templates(user_id, include_shared=True):
    """Return templates visible to a given user.

    Args:
        user_id: The user's ID.
        include_shared: If True, include shared templates from other users.

    Returns:
        List of ServiceOrderTemplate instances.
    """
    if include_shared:
        query = ServiceOrderTemplate.query.filter(
            or_(
                ServiceOrderTemplate.created_by_id == user_id,
                ServiceOrderTemplate.is_shared == True,  # noqa: E712
            )
        )
    else:
        query = ServiceOrderTemplate.query.filter_by(created_by_id=user_id)

    return query.order_by(ServiceOrderTemplate.name).all()


def _template_is_visible(template, user_id, include_shared=True):
    """Return True when the template is visible to the given user."""
    if template is None:
        return False
    if template.created_by_id == user_id:
        return True
    if include_shared and template.is_shared:
        return True
    return False


def _template_is_owned_by(template, user_id):
    """Return True when the template belongs to the given user."""
    return template is not None and template.created_by_id == user_id


def get_template(template_id, user_id=None, include_shared=True):
    """Return a single template by ID or abort 404 if not visible.

    Args:
        template_id: The primary key.
        user_id: Optional user ID used for visibility checks.
        include_shared: Whether shared templates are visible.

    Returns:
        A ServiceOrderTemplate instance.

    Raises:
        404 HTTPException if not found.
    """
    template = db.session.get(ServiceOrderTemplate, template_id)
    if template is None:
        abort(404)
    if user_id is not None and not _template_is_visible(template, user_id, include_shared):
        abort(404)
    return template


def update_template(template_id, user_id=None, ip_address=None,
                    user_agent=None, **kwargs):
    """Update an existing template.

    Args:
        template_id: The primary key of the template.
        user_id: Optional user ID for audit logging.
        ip_address: Optional IP for audit logging.
        user_agent: Optional user agent for audit logging.
        **kwargs: Fields to update (name, description, is_shared, template_data).

    Returns:
        The updated ServiceOrderTemplate.
    """
    template = db.session.get(ServiceOrderTemplate, template_id)
    if template is None or not _template_is_owned_by(template, user_id):
        abort(404)

    for field in ("name", "description", "is_shared", "template_data"):
        if field in kwargs:
            value = kwargs[field]
            if field == "name":
                if not value or not value.strip():
                    raise ValueError("Template name is required.")
                value = value.strip()
            setattr(template, field, value)

    db.session.commit()

    try:
        audit_service.log_action(
            action="update",
            entity_type="service_order_template",
            entity_id=template.id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except Exception:
        pass

    return template


def delete_template(template_id, user_id=None, ip_address=None, user_agent=None):
    """Delete a template permanently.

    Args:
        template_id: The primary key.
        user_id: Optional user ID for audit logging.
        ip_address: Optional IP for audit logging.
        user_agent: Optional user agent for audit logging.

    Returns:
        True if deleted.
    """
    template = db.session.get(ServiceOrderTemplate, template_id)
    if template is None or not _template_is_owned_by(template, user_id):
        abort(404)
    tid = template.id
    db.session.delete(template)
    db.session.commit()

    try:
        audit_service.log_action(
            action="delete",
            entity_type="service_order_template",
            entity_id=tid,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except Exception:
        pass

    return True


def apply_template(order_id, template_id, user_id=None, ip_address=None,
                   user_agent=None):
    """Apply a template's configuration to an existing service order.

    Updates the order's priority, rush_fee, discount_percent, and description
    from the template.  For services and parts, they are added to the first
    order item (if one exists).

    Args:
        order_id: The service order's primary key.
        template_id: The template's primary key.
        user_id: Optional user ID for audit logging.
        ip_address: Optional IP for audit logging.
        user_agent: Optional user agent for audit logging.

    Returns:
        A dict summarizing what was applied.
    """
    template = get_template(template_id, user_id=user_id)
    order = order_service.get_order(order_id)
    data = template.template_data or {}
    summary = {"services_added": 0, "parts_added": 0, "fields_updated": []}
    has_item_lines = bool(data.get("services") or data.get("parts"))

    if has_item_lines:
        order_items = order.order_items.all()
        if len(order_items) != 1:
            raise ValueError(
                "Template application requires exactly one order item when "
                f"services or parts are included; found {len(order_items)}."
            )
        target_item = order_items[0]
    else:
        target_item = None

    # Preflight validation so we do not half-apply a template.
    for svc in data.get("services", []):
        price_list_item_id = svc.get("price_list_item_id")
        if price_list_item_id is not None:
            price_item = db.session.get(PriceListItem, price_list_item_id)
            if price_item is None or not price_item.is_active:
                raise ValueError(
                    f"Price list item {price_list_item_id} is not available "
                    "for this template."
                )

    for part in data.get("parts", []):
        inventory_item_id = part.get("inventory_item_id")
        inv_item = db.session.get(InventoryItem, inventory_item_id)
        if inv_item is None or inv_item.is_deleted or not inv_item.is_active:
            raise ValueError(
                f"Inventory item {inventory_item_id} is not available for "
                "this template."
            )

    # Apply order-level fields
    update_fields = {}
    if "priority" in data and data["priority"]:
        update_fields["priority"] = data["priority"]
        summary["fields_updated"].append("priority")
    if "rush_fee" in data:
        update_fields["rush_fee"] = Decimal(str(data["rush_fee"]))
        summary["fields_updated"].append("rush_fee")
    if "discount_percent" in data:
        update_fields["discount_percent"] = Decimal(str(data["discount_percent"]))
        summary["fields_updated"].append("discount_percent")
    if "notes" in data and data["notes"]:
        update_fields["description"] = data["notes"]
        summary["fields_updated"].append("description")

    if update_fields:
        order_service.update_order(
            order_id,
            update_fields,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            commit=False,
        )

    try:
        if target_item is not None:
            for svc in data.get("services", []):
                svc_data = {
                    "price_list_item_id": svc.get("price_list_item_id"),
                    "quantity": Decimal(str(svc.get("quantity", 1))),
                }
                if svc.get("override_price") is not None:
                    svc_data["unit_price"] = Decimal(str(svc["override_price"]))
                    svc_data["price_overridden"] = True
                order_service.add_applied_service(
                    target_item.id,
                    svc_data,
                    added_by=user_id,
                    commit=False,
                )
                summary["services_added"] += 1

            for part in data.get("parts", []):
                order_service.add_part_used(
                    order_item_id=target_item.id,
                    inventory_item_id=part["inventory_item_id"],
                    quantity=Decimal(str(part.get("quantity", 1))),
                    added_by=user_id,
                    commit=False,
                )
                summary["parts_added"] += 1

        db.session.commit()
    except (ValueError, SQLAlchemyError) as exc:
        db.session.rollback()
        raise ValueError(f"Failed to apply template: {exc}") from exc
    except Exception as exc:
        db.session.rollback()
        raise ValueError(f"Failed to apply template: {exc}") from exc

    try:
        audit_service.log_action(
            action="apply_template",
            entity_type="service_order",
            entity_id=order_id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            additional_data=f'{{"template_id": {template_id}}}',
        )
    except Exception:
        pass

    return summary
