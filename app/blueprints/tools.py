"""Tools blueprint — utility calculators and reference tools for dive service."""

from decimal import Decimal, InvalidOperation

from flask import Blueprint, render_template, request
from flask_security import login_required

from app.services import shipping_service

tools_bp = Blueprint("tools", __name__, url_prefix="/tools")


@tools_bp.route("/")
@login_required
def hub():
    """Tools hub — grid of available tools."""
    return render_template("tools/hub.html")


@tools_bp.route("/seal-calculator")
@login_required
def seal_calculator():
    """Seal size calculator for drysuit neck and wrist seals."""
    return render_template("tools/seal_calculator.html")


@tools_bp.route("/material-estimator")
@login_required
def material_estimator():
    """Material quantity estimator for common drysuit repairs."""
    return render_template("tools/material_estimator.html")


@tools_bp.route("/pricing-calculator")
@login_required
def pricing_calculator():
    """Quick pricing calculator for service estimates."""
    return render_template("tools/pricing_calculator.html")


@tools_bp.route("/shipping-calculator")
@login_required
def shipping_calculator():
    """Standalone shipping calculator using the shared shipping framework."""
    default_provider_code = shipping_service.get_workflow_default_provider_code()
    return render_template(
        "tools/shipping_calculator.html",
        providers=shipping_service.get_provider_catalog(),
        default_provider_code=default_provider_code,
        quote_placeholder=_get_quote_placeholder(default_provider_code),
        default_destination_country="US",
    )


@tools_bp.route("/shipping-calculator/estimate")
@login_required
def shipping_calculator_estimate():
    """Return a provider-aware quote fragment for the tools calculator."""
    provider_code = request.args.get("provider_code") or None
    method = request.args.get("shipping_method") or request.args.get("method")
    weight_lbs = _parse_decimal(request.args.get("weight_lbs"))
    length_in = _parse_decimal(request.args.get("length_in"))
    width_in = _parse_decimal(request.args.get("width_in"))
    height_in = _parse_decimal(request.args.get("height_in"))
    destination_postal_code = request.args.get("destination_postal_code") or None
    destination_country = request.args.get("destination_country") or None

    try:
        requires_weight = shipping_service.provider_requires_weight(provider_code, method)
    except ValueError as exc:
        return render_template(
            "partials/shipping_quote.html",
            quote=None,
            placeholder_text=str(exc),
        )

    if requires_weight and (weight_lbs is None or weight_lbs <= 0):
        return render_template(
            "partials/shipping_quote.html",
            quote=None,
            placeholder_text=_get_quote_placeholder(provider_code, method),
        )

    try:
        quote = shipping_service.quote_shipping(
            weight_lbs=weight_lbs,
            length_in=length_in,
            width_in=width_in,
            height_in=height_in,
            method=method,
            provider_code=provider_code,
            destination_postal_code=destination_postal_code,
            destination_country=destination_country,
        )
    except ValueError as exc:
        return render_template(
            "partials/shipping_quote.html",
            quote=None,
            placeholder_text=str(exc),
        )

    return render_template(
        "partials/shipping_quote.html",
        quote=quote.to_dict(),
        placeholder_text=_get_quote_placeholder(provider_code, method),
    )


@tools_bp.route("/leak-test-log")
@login_required
def leak_test_log():
    """Leak test logger for structured test documentation."""
    return render_template("tools/leak_test_log.html")


@tools_bp.route("/valve-reference")
@login_required
def valve_reference():
    """Valve service reference and compatibility guide."""
    return render_template("tools/valve_reference.html")


@tools_bp.route("/converter")
@login_required
def converter():
    """Unit converter for dive service measurements."""
    return render_template("tools/converter.html")


def _parse_decimal(value):
    """Parse a string to Decimal, returning None on failure."""
    if not value:
        return None
    try:
        parsed = Decimal(value.strip())
        if not parsed.is_finite():
            return None
        return parsed
    except (InvalidOperation, ValueError, AttributeError):
        return None


def _get_quote_placeholder(provider_code=None, shipping_method=None):
    """Return contextual placeholder text for the selected provider."""
    try:
        if shipping_service.provider_requires_weight(provider_code, shipping_method):
            return "Enter weight and optional dimensions to estimate shipping."
    except ValueError:
        pass
    return "Local pickup stays at $0.00 and does not require package weight."
