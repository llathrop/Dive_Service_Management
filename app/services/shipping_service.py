"""Shipping service layer — rate calculation and shipment CRUD.

Provides a pluggable provider framework for shipping rate calculations
and functions to create, update, and query shipment records.

Future integration note: When generating invoices from orders, shipping
costs should be added as a line item on the invoice.  This integration
is not yet implemented — currently shipping is tracked separately from
invoices.  To add it, modify invoice_service.generate_from_order() to
query order.shipments and include a "Shipping" line item with the total
shipping cost.
"""

import json
from decimal import Decimal

from flask import abort

from app.extensions import db
from app.models.shipment import Shipment, VALID_STATUSES
from app.services import audit_service, config_service


# ---------------------------------------------------------------------------
# Default flat-rate tiers (used when SystemConfig has no override)
# ---------------------------------------------------------------------------

DEFAULT_FLAT_RATE_TIERS = [
    {"max_weight": 5, "rate": "9.99"},
    {"max_weight": 15, "rate": "14.99"},
    {"max_weight": 30, "rate": "24.99"},
    {"max_weight": 9999, "rate": "39.99"},
]

MAX_TEXT_LENGTHS = {
    "shipping_method": 100,
    "carrier": 100,
    "tracking_number": 255,
}
MAX_DECIMAL_VALUE = Decimal("999999.99")
NON_CANCELLED_STATUSES = tuple(
    status for status in VALID_STATUSES if status != "cancelled"
)
AUDIT_NOTES_MAX_LENGTH = 500


# ---------------------------------------------------------------------------
# Provider framework
# ---------------------------------------------------------------------------

class ShippingProvider:
    """Base class for shipping rate providers.

    Subclass this and implement the three methods to add new carriers
    or rate calculation strategies.
    """

    def get_name(self):
        """Return the human-readable provider name."""
        raise NotImplementedError

    def calculate_rate(self, weight_lbs, length_in=None, width_in=None,
                       height_in=None, method=None):
        """Return estimated shipping cost as a Decimal.

        Parameters
        ----------
        weight_lbs : Decimal
            Package weight in pounds.
        length_in, width_in, height_in : Decimal, optional
            Package dimensions in inches (not used by all providers).
        method : str, optional
            Shipping method code.

        Returns
        -------
        Decimal
            The calculated shipping rate.
        """
        raise NotImplementedError

    def get_available_methods(self):
        """Return a list of available shipping methods.

        Each method is a dict with keys: code, name, description.
        """
        raise NotImplementedError


class FlatRateProvider(ShippingProvider):
    """Flat-rate shipping based on weight tiers from SystemConfig."""

    def get_name(self):
        return "Flat Rate"

    def calculate_rate(self, weight_lbs, length_in=None, width_in=None,
                       height_in=None, method=None):
        """Calculate flat-rate shipping cost based on weight tiers.

        Tiers are read from SystemConfig key ``shipping.flat_rate_tiers``.
        Falls back to DEFAULT_FLAT_RATE_TIERS if not configured.
        """
        tiers = self._get_tiers()
        weight = Decimal(str(weight_lbs))

        for tier in sorted(tiers, key=lambda t: t["max_weight"]):
            if weight <= Decimal(str(tier["max_weight"])):
                return Decimal(str(tier["rate"]))

        # If weight exceeds all tiers, use the highest tier rate
        if tiers:
            highest = max(tiers, key=lambda t: t["max_weight"])
            return Decimal(str(highest["rate"]))

        return Decimal("0.00")

    def get_available_methods(self):
        return [
            {
                "code": "flat_rate",
                "name": "Flat Rate Shipping",
                "description": "Standard shipping by weight",
            }
        ]

    def _get_tiers(self):
        """Load tiers from SystemConfig or fall back to defaults."""
        raw = config_service.get_config("shipping.flat_rate_tiers")
        if raw:
            try:
                return json.loads(raw) if isinstance(raw, str) else raw
            except (json.JSONDecodeError, TypeError):
                pass
        return DEFAULT_FLAT_RATE_TIERS


# ---------------------------------------------------------------------------
# Provider registry
# ---------------------------------------------------------------------------

def get_provider():
    """Return the active shipping provider.

    Currently returns FlatRateProvider.  Extend this function to support
    multiple providers selected via SystemConfig.
    """
    return FlatRateProvider()


# ---------------------------------------------------------------------------
# Rate estimation
# ---------------------------------------------------------------------------

def estimate_shipping(weight_lbs, length_in=None, width_in=None,
                      height_in=None, method=None):
    """Calculate estimated shipping cost using the active provider.

    Returns
    -------
    Decimal
        The estimated shipping cost, or Decimal("0.00") if weight is
        not provided.
    """
    if weight_lbs is None:
        return Decimal("0.00")

    provider = get_provider()
    return provider.calculate_rate(
        weight_lbs, length_in, width_in, height_in, method,
    )


# ---------------------------------------------------------------------------
# Shipment CRUD
# ---------------------------------------------------------------------------

def create_shipment(
    order_id,
    weight_lbs=None,
    length_in=None,
    width_in=None,
    height_in=None,
    shipping_method=None,
    carrier=None,
    tracking_number=None,
    notes=None,
    user_id=None,
    ip_address=None,
    user_agent=None,
):
    """Create a new shipment record for a service order.

    Automatically calculates shipping cost based on the active provider
    if weight is provided.

    Returns
    -------
    Shipment
        The newly created shipment.
    """
    shipping_method = _clean_text(
        shipping_method or "flat_rate",
        "shipping_method",
    )
    carrier = _clean_text(carrier, "carrier")
    tracking_number = _clean_text(tracking_number, "tracking_number")
    notes = notes.strip() if isinstance(notes, str) and notes.strip() else None

    weight_lbs = _validate_decimal(weight_lbs, "weight_lbs", allow_zero=False)
    length_in = _validate_decimal(length_in, "length_in")
    width_in = _validate_decimal(width_in, "width_in")
    height_in = _validate_decimal(height_in, "height_in")

    # Calculate cost if weight is provided
    cost = Decimal("0.00")
    if weight_lbs is not None:
        cost = estimate_shipping(
            weight_lbs, length_in, width_in, height_in, shipping_method,
        )

    shipment = Shipment(
        order_id=order_id,
        weight_lbs=weight_lbs,
        length_in=length_in,
        width_in=width_in,
        height_in=height_in,
        shipping_method=shipping_method,
        shipping_cost=cost,
        carrier=carrier,
        tracking_number=tracking_number,
        notes=notes,
        status="pending",
        created_by=user_id,
    )
    db.session.add(shipment)
    db.session.commit()

    try:
        audit_service.log_action(
            action="create",
            entity_type="shipment",
            entity_id=shipment.id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            additional_data=_shipment_audit_data(shipment),
        )
    except Exception:
        pass  # Audit logging must never break the main flow

    return shipment


def update_shipment(
    shipment_id,
    user_id=None,
    ip_address=None,
    user_agent=None,
    **kwargs,
):
    """Update a shipment record.

    Accepted kwargs: tracking_number, carrier, status, notes,
    weight_lbs, length_in, width_in, height_in, shipping_method.

    If weight changes, shipping cost is recalculated.

    Returns
    -------
    Shipment
        The updated shipment.
    """
    shipment = get_shipment(shipment_id)

    allowed_fields = {
        "tracking_number", "carrier", "status", "notes",
        "weight_lbs", "length_in", "width_in", "height_in",
        "shipping_method",
    }

    old_values = {}
    status = kwargs.get("status")
    if status is not None and status not in VALID_STATUSES:
        raise ValueError(f"Invalid shipment status: {status}")

    for key, value in kwargs.items():
        if key in allowed_fields:
            if key in {"shipping_method", "carrier", "tracking_number"}:
                value = _clean_text(value, key)
            elif key in {"weight_lbs", "length_in", "width_in", "height_in"}:
                value = _validate_decimal(
                    value,
                    key,
                    allow_zero=(key != "weight_lbs"),
                )
            elif key == "notes":
                value = value.strip() if isinstance(value, str) and value.strip() else None

            old_values[key] = getattr(shipment, key)
            setattr(shipment, key, value)

    # Recalculate cost if weight changed
    if "weight_lbs" in kwargs and kwargs["weight_lbs"] is not None:
        shipment.shipping_cost = estimate_shipping(
            shipment.weight_lbs,
            shipment.length_in,
            shipment.width_in,
            shipment.height_in,
            shipment.shipping_method,
        )

    db.session.commit()

    changed_fields = {}
    for key, old_value in old_values.items():
        new_value = getattr(shipment, key)
        if old_value != new_value:
            changed_fields[key] = (
                None if old_value is None else str(old_value),
                None if new_value is None else str(new_value),
            )

    for field_name, (old_value, new_value) in changed_fields.items():
        try:
            audit_service.log_action(
                action="update",
                entity_type="shipment",
                entity_id=shipment.id,
                user_id=user_id,
                field_name=field_name,
                old_value=old_value,
                new_value=new_value,
                ip_address=ip_address,
                user_agent=user_agent,
                additional_data=json.dumps(
                    {
                        "order_id": shipment.order_id,
                        "shipment_status": shipment.status,
                    }
                ),
            )
        except Exception:
            pass

    return shipment


def delete_shipment(
    shipment_id,
    user_id=None,
    ip_address=None,
    user_agent=None,
):
    """Delete a shipment record.

    Returns
    -------
    None
    """
    shipment = get_shipment(shipment_id)

    try:
        audit_service.log_action(
            action="delete",
            entity_type="shipment",
            entity_id=shipment.id,
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            additional_data=_shipment_audit_data(shipment),
        )
    except Exception:
        pass

    db.session.delete(shipment)
    db.session.commit()


def get_shipment(shipment_id):
    """Get a shipment by ID or abort 404."""
    shipment = db.session.get(Shipment, shipment_id)
    if shipment is None:
        abort(404)
    return shipment


def get_shipment_for_order(order_id, shipment_id):
    """Get a shipment scoped to a specific order or abort 404."""
    shipment = (
        Shipment.query
        .filter_by(id=shipment_id, order_id=order_id)
        .first()
    )
    if shipment is None:
        abort(404)
    return shipment


def get_order_shipments(order_id):
    """Return all shipments for a given order, newest first."""
    return (
        Shipment.query
        .filter_by(order_id=order_id)
        .order_by(Shipment.created_at.desc())
        .all()
    )


def get_order_shipping_total(order_id):
    """Return the total shipping cost for an order as Decimal."""
    shipments = [
        shipment
        for shipment in get_order_shipments(order_id)
        if shipment.status in NON_CANCELLED_STATUSES
    ]
    return sum(
        (s.shipping_cost or Decimal("0.00") for s in shipments),
        Decimal("0.00"),
    )


def _clean_text(value, field_name):
    """Normalize and validate a text field."""
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None

    max_length = MAX_TEXT_LENGTHS[field_name]
    if len(value) > max_length:
        raise ValueError(
            f"{field_name.replace('_', ' ').title()} must be {max_length} characters or fewer."
        )
    return value


def _validate_decimal(value, field_name, allow_zero=True):
    """Validate Decimal-compatible numeric inputs against DB precision."""
    if value is None:
        return None

    decimal_value = Decimal(str(value))
    if not decimal_value.is_finite():
        raise ValueError(f"{field_name.replace('_', ' ').title()} must be a valid number.")

    if decimal_value < 0 or (not allow_zero and decimal_value <= 0):
        comparator = "greater than zero" if not allow_zero else "zero or greater"
        raise ValueError(f"{field_name.replace('_', ' ').title()} must be {comparator}.")

    if decimal_value > MAX_DECIMAL_VALUE:
        raise ValueError(
            f"{field_name.replace('_', ' ').title()} exceeds the maximum allowed value."
        )

    if decimal_value.as_tuple().exponent < -2:
        raise ValueError(
            f"{field_name.replace('_', ' ').title()} must have at most 2 decimal places."
        )

    return decimal_value


def _shipment_audit_data(shipment):
    """Serialize shipment context for audit logs with bounded note size."""
    notes = shipment.notes
    if notes and len(notes) > AUDIT_NOTES_MAX_LENGTH:
        notes = f"{notes[:AUDIT_NOTES_MAX_LENGTH]}..."

    return json.dumps(
        {
            "order_id": shipment.order_id,
            "shipping_method": shipment.shipping_method,
            "carrier": shipment.carrier,
            "tracking_number": shipment.tracking_number,
            "status": shipment.status,
            "shipping_cost": str(shipment.shipping_cost or "0.00"),
            "notes": notes,
        }
    )
