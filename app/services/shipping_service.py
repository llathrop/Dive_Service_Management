"""Shipping service layer - rate calculation, quote metadata, and shipment CRUD."""

from copy import deepcopy
import json
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from flask import abort

from app.extensions import db
from app.models.shipment import Shipment, VALID_STATUSES
from app.services import audit_service, config_service


DEFAULT_FLAT_RATE_TIERS = [
    {"max_weight": 5, "rate": "9.99"},
    {"max_weight": 15, "rate": "14.99"},
    {"max_weight": 30, "rate": "24.99"},
    {"max_weight": 9999, "rate": "39.99"},
]

DEFAULT_ENABLED_PROVIDER_CODES = [
    "usps",
    "ups",
    "fedex",
    "dhl",
    "local_pickup",
    "flat_rate",
]

DEFAULT_CARRIER_PROFILES = {
    "usps": {
        "name": "USPS",
        "description": "Mock-ready USPS services with dimensional pricing support.",
        "base_rate": "5.25",
        "per_lb_rate": "0.78",
        "dimensional_divisor": "166",
        "oversize_threshold_cuin": "1728",
        "oversize_surcharge": "3.50",
        "methods": [
            {
                "code": "usps_ground_advantage",
                "name": "Ground Advantage",
                "description": "Economy ground delivery for domestic shipments.",
                "delivery_window": "2-5 business days",
                "multiplier": "1.00",
                "minimum_charge": "6.95",
            },
            {
                "code": "usps_priority_mail",
                "name": "Priority Mail",
                "description": "Priority mail with faster delivery targets.",
                "delivery_window": "1-3 business days",
                "multiplier": "1.24",
                "minimum_charge": "9.95",
            },
            {
                "code": "usps_priority_mail_express",
                "name": "Priority Mail Express",
                "description": "Fastest USPS mock quote option.",
                "delivery_window": "1-2 business days",
                "multiplier": "1.68",
                "minimum_charge": "18.95",
            },
        ],
    },
    "ups": {
        "name": "UPS",
        "description": "Mock UPS rates with heavier package bias and air upgrades.",
        "base_rate": "6.40",
        "per_lb_rate": "0.92",
        "dimensional_divisor": "139",
        "oversize_threshold_cuin": "1944",
        "oversize_surcharge": "5.00",
        "methods": [
            {
                "code": "ups_ground",
                "name": "UPS Ground",
                "description": "Standard UPS ground service.",
                "delivery_window": "1-5 business days",
                "multiplier": "1.00",
                "minimum_charge": "8.95",
            },
            {
                "code": "ups_three_day_select",
                "name": "3 Day Select",
                "description": "Mid-speed UPS air service.",
                "delivery_window": "3 business days",
                "multiplier": "1.28",
                "minimum_charge": "12.95",
            },
            {
                "code": "ups_second_day_air",
                "name": "2nd Day Air",
                "description": "Faster UPS air delivery.",
                "delivery_window": "2 business days",
                "multiplier": "1.52",
                "minimum_charge": "16.95",
            },
            {
                "code": "ups_next_day_air",
                "name": "Next Day Air",
                "description": "Highest-priority UPS service.",
                "delivery_window": "Next business day",
                "multiplier": "2.05",
                "minimum_charge": "26.95",
            },
        ],
    },
    "fedex": {
        "name": "FedEx",
        "description": "Mock FedEx services tuned for dimensional packages.",
        "base_rate": "6.10",
        "per_lb_rate": "0.89",
        "dimensional_divisor": "139",
        "oversize_threshold_cuin": "1944",
        "oversize_surcharge": "4.50",
        "methods": [
            {
                "code": "fedex_ground",
                "name": "FedEx Ground",
                "description": "Standard FedEx ground delivery.",
                "delivery_window": "1-5 business days",
                "multiplier": "1.00",
                "minimum_charge": "8.49",
            },
            {
                "code": "fedex_express_saver",
                "name": "Express Saver",
                "description": "Three-day express delivery.",
                "delivery_window": "3 business days",
                "multiplier": "1.31",
                "minimum_charge": "12.49",
            },
            {
                "code": "fedex_two_day",
                "name": "2Day",
                "description": "FedEx two-day delivery.",
                "delivery_window": "2 business days",
                "multiplier": "1.57",
                "minimum_charge": "17.49",
            },
            {
                "code": "fedex_standard_overnight",
                "name": "Standard Overnight",
                "description": "Overnight delivery option.",
                "delivery_window": "Next business day",
                "multiplier": "2.10",
                "minimum_charge": "27.49",
            },
        ],
    },
    "dhl": {
        "name": "DHL",
        "description": "Mock DHL services suited for international-capable workflows.",
        "base_rate": "7.25",
        "per_lb_rate": "1.02",
        "dimensional_divisor": "139",
        "oversize_threshold_cuin": "1728",
        "oversize_surcharge": "6.25",
        "methods": [
            {
                "code": "dhl_ground_connect",
                "name": "Ground Connect",
                "description": "Economy ground-style DHL mock quote.",
                "delivery_window": "2-6 business days",
                "multiplier": "1.00",
                "minimum_charge": "9.95",
            },
            {
                "code": "dhl_express_worldwide",
                "name": "Express Worldwide",
                "description": "Fast DHL express service.",
                "delivery_window": "1-3 business days",
                "multiplier": "1.74",
                "minimum_charge": "21.95",
            },
        ],
    },
}

MAX_TEXT_LENGTHS = {
    "provider_code": 50,
    "shipping_method": 100,
    "carrier": 100,
    "tracking_number": 255,
    "destination_postal_code": 20,
    "destination_country": 100,
}
MAX_DECIMAL_VALUE = Decimal("999999.99")
MONEY_QUANTUM = Decimal("0.01")
MEASUREMENT_QUANTUM = Decimal("0.01")
NON_CANCELLED_STATUSES = tuple(
    status for status in VALID_STATUSES if status != "cancelled"
)
AUDIT_NOTES_MAX_LENGTH = 500


@dataclass(frozen=True)
class ShippingQuoteRequest:
    """Normalized inputs used by provider adapters."""

    weight_lbs: Decimal | None = None
    length_in: Decimal | None = None
    width_in: Decimal | None = None
    height_in: Decimal | None = None
    provider_code: str | None = None
    method_code: str | None = None
    destination_postal_code: str | None = None
    destination_country: str | None = None


@dataclass
class ShippingQuote:
    """Carrier/provider quote with normalized metadata."""

    provider_code: str
    provider_name: str
    method_code: str
    method_name: str
    amount: Decimal
    currency: str = "USD"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-safe representation for routes and templates."""
        return {
            "provider_code": self.provider_code,
            "provider_name": self.provider_name,
            "method_code": self.method_code,
            "method_name": self.method_name,
            "amount": _format_decimal(self.amount),
            "amount_display": f"${self.amount:.2f}",
            "currency": self.currency,
            "metadata": _json_safe(self.metadata),
        }

    def to_record_metadata(self) -> dict[str, Any]:
        """Return compact metadata for persistence on Shipment rows."""
        payload = self.to_dict()
        payload["quote_captured"] = True
        return payload


class ShippingProvider:
    """Base class for pluggable shipping providers."""

    code = "base"
    name = "Base Provider"
    description = ""

    def get_name(self):
        return self.name

    def get_description(self):
        return self.description

    def get_available_methods(self):
        raise NotImplementedError

    def get_default_method(self):
        methods = self.get_available_methods()
        if not methods:
            raise ValueError(f"Provider {self.code} has no configured methods.")
        return methods[0]

    def get_method(self, method_code=None):
        if not method_code:
            return self.get_default_method()
        for method in self.get_available_methods():
            if method["code"] == method_code:
                return method
        raise ValueError(
            f"Shipping method '{method_code}' is not available for provider '{self.code}'."
        )

    def requires_weight(self, method_code=None):
        return True

    def quote(self, request: ShippingQuoteRequest) -> ShippingQuote:
        raise NotImplementedError

    def calculate_rate(
        self,
        weight_lbs,
        length_in=None,
        width_in=None,
        height_in=None,
        method=None,
    ):
        """Retain the legacy cost-only API for existing callers and tests."""
        quote = self.quote(
            ShippingQuoteRequest(
                weight_lbs=_validate_decimal(weight_lbs, "weight_lbs", allow_zero=False),
                length_in=_normalize_dimension(length_in, "length_in"),
                width_in=_normalize_dimension(width_in, "width_in"),
                height_in=_normalize_dimension(height_in, "height_in"),
                provider_code=self.code,
                method_code=method,
            )
        )
        return quote.amount

    def as_catalog_dict(self):
        methods = []
        for method in self.get_available_methods():
            method_entry = dict(method)
            method_entry.setdefault("provider_code", self.code)
            methods.append(_json_safe(method_entry))
        return {
            "code": self.code,
            "name": self.get_name(),
            "description": self.get_description(),
            "default_method_code": self.get_default_method()["code"],
            "requires_weight": self.requires_weight(self.get_default_method()["code"]),
            "methods": methods,
        }


class FlatRateProvider(ShippingProvider):
    """Flat-rate shipping based on weight tiers from config."""

    code = "flat_rate"
    name = "Flat Rate"
    description = "Fallback flat-rate pricing by package weight."

    def get_available_methods(self):
        return [
            {
                "code": "flat_rate",
                "name": "Flat Rate Shipping",
                "description": "Standard fallback shipping by weight tier.",
                "delivery_window": "2-5 business days",
            }
        ]

    def quote(self, request: ShippingQuoteRequest) -> ShippingQuote:
        method = self.get_method(request.method_code)
        if request.weight_lbs is None:
            raise ValueError("Weight is required for the selected shipping provider.")

        matched_tier = None
        tiers = self._get_tiers()
        weight = request.weight_lbs
        amount = Decimal("0.00")

        for tier in sorted(tiers, key=lambda tier: Decimal(str(tier["max_weight"]))):
            if weight <= Decimal(str(tier["max_weight"])):
                matched_tier = tier
                amount = Decimal(str(tier["rate"]))
                break

        if matched_tier is None and tiers:
            matched_tier = max(tiers, key=lambda tier: Decimal(str(tier["max_weight"])))
            amount = Decimal(str(matched_tier["rate"]))

        metadata = {
            "quote_source": "flat_rate_schedule",
            "estimated_delivery_days": method.get("delivery_window"),
            "billable_weight_lbs": _format_decimal(weight),
            "tier_label": (
                f"Up to {_format_decimal(matched_tier['max_weight'])} lbs"
                if matched_tier is not None
                else None
            ),
            "destination_postal_code": request.destination_postal_code,
            "destination_country": request.destination_country,
            "destination_summary": _format_destination_summary(
                request.destination_postal_code,
                request.destination_country,
            ),
        }
        return ShippingQuote(
            provider_code=self.code,
            provider_name=self.get_name(),
            method_code=method["code"],
            method_name=method["name"],
            amount=_quantize_money(amount),
            metadata=metadata,
        )

    def _get_tiers(self):
        raw = config_service.get_config("shipping.flat_rate_tiers")
        if raw:
            try:
                return json.loads(raw) if isinstance(raw, str) else raw
            except (json.JSONDecodeError, TypeError):
                pass
        return DEFAULT_FLAT_RATE_TIERS


class LocalPickupProvider(ShippingProvider):
    """Zero-cost local pickup option."""

    code = "local_pickup"
    name = "Local Pickup"
    description = "Customer pickup at the shop with zero shipping cost."

    def get_available_methods(self):
        return [
            {
                "code": "local_pickup",
                "name": "Customer Pickup",
                "description": "No carrier shipment. Customer collects locally.",
                "delivery_window": "Ready when service is complete",
            }
        ]

    def requires_weight(self, method_code=None):
        return False

    def quote(self, request: ShippingQuoteRequest) -> ShippingQuote:
        method = self.get_method(request.method_code)
        metadata = {
            "quote_source": "local_pickup",
            "estimated_delivery_days": method.get("delivery_window"),
            "pickup_message": "No carrier charge will be added for local pickup.",
            "zero_cost": True,
            "destination_postal_code": request.destination_postal_code,
            "destination_country": request.destination_country,
            "destination_summary": _format_destination_summary(
                request.destination_postal_code,
                request.destination_country,
            ),
        }
        return ShippingQuote(
            provider_code=self.code,
            provider_name=self.get_name(),
            method_code=method["code"],
            method_name=method["name"],
            amount=Decimal("0.00"),
            metadata=metadata,
        )


class FormulaCarrierProvider(ShippingProvider):
    """Config-driven mock carrier adapter with room for live API overrides."""

    credential_keys = ()

    def get_name(self):
        return self._get_profile()["name"]

    def get_description(self):
        return self._get_profile()["description"]

    def get_available_methods(self):
        return self._get_profile()["methods"]

    def quote(self, request: ShippingQuoteRequest) -> ShippingQuote:
        method = self.get_method(request.method_code)
        if request.weight_lbs is None:
            raise ValueError("Weight is required for the selected shipping provider.")
        return self._build_formula_quote(request, method)

    def credentials_configured(self):
        return all(
            bool(config_service.get_config(key))
            for key in self.credential_keys
        ) if self.credential_keys else False

    def _get_profile(self):
        profile = deepcopy(DEFAULT_CARRIER_PROFILES[self.code])
        overrides = _get_provider_overrides().get(self.code, {})
        if not isinstance(overrides, dict):
            return profile

        methods = {method["code"]: method for method in profile.get("methods", [])}
        override_methods = overrides.get("methods", [])
        if isinstance(override_methods, list):
            for override in override_methods:
                if not isinstance(override, dict) or not override.get("code"):
                    continue
                base_method = deepcopy(methods.get(override["code"], {}))
                base_method.update(override)
                methods[override["code"]] = base_method

        for key, value in overrides.items():
            if key == "methods":
                continue
            profile[key] = value

        profile["methods"] = list(methods.values())
        return profile

    def _build_formula_quote(self, request: ShippingQuoteRequest, method: dict[str, Any]):
        profile = self._get_profile()
        weight = request.weight_lbs
        divisor = _decimal_or_zero(profile.get("dimensional_divisor"))
        volume = _package_volume(request.length_in, request.width_in, request.height_in)
        dimensional_weight = weight
        if volume is not None and divisor > 0:
            dimensional_weight = _quantize_measure(volume / divisor)
        billable_weight = max(weight, dimensional_weight)

        base_rate = _decimal_or_zero(profile.get("base_rate"))
        per_lb_rate = _decimal_or_zero(profile.get("per_lb_rate"))
        oversize_threshold = _decimal_or_zero(profile.get("oversize_threshold_cuin"))
        oversize_surcharge = Decimal("0.00")
        if volume is not None and oversize_threshold > 0 and volume > oversize_threshold:
            oversize_surcharge = _decimal_or_zero(profile.get("oversize_surcharge"))
        destination_country = request.destination_country or "US"
        destination_postal_code = request.destination_postal_code
        international = destination_country.upper() not in {"US", "USA", "UNITED STATES"}
        destination_surcharge = Decimal("0.00")
        if international:
            destination_surcharge = Decimal("12.00")
        elif destination_postal_code and len(destination_postal_code.replace(" ", "")) > 5:
            destination_surcharge = Decimal("1.50")

        multiplier = _decimal_or_zero(method.get("multiplier") or "1.00")
        minimum_charge = _decimal_or_zero(method.get("minimum_charge"))
        amount = (
            base_rate
            + (billable_weight * per_lb_rate)
            + oversize_surcharge
            + destination_surcharge
        ) * multiplier
        amount = max(_quantize_money(amount), _quantize_money(minimum_charge))

        metadata = {
            "quote_source": "mock_formula",
            "estimated_delivery_days": method.get("delivery_window"),
            "billable_weight_lbs": _format_decimal(billable_weight),
            "dimensional_weight_lbs": (
                _format_decimal(dimensional_weight)
                if dimensional_weight != weight or volume is not None
                else None
            ),
            "oversize_applied": oversize_surcharge > 0,
            "credentials_configured": self.credentials_configured(),
            "live_adapter_ready": False,
            "destination_postal_code": destination_postal_code,
            "destination_country": destination_country,
            "destination_summary": _format_destination_summary(
                destination_postal_code,
                destination_country,
            ),
            "international": international,
            "destination_surcharge": (
                _format_decimal(destination_surcharge)
                if destination_surcharge > 0
                else None
            ),
        }
        return ShippingQuote(
            provider_code=self.code,
            provider_name=self.get_name(),
            method_code=method["code"],
            method_name=method["name"],
            amount=amount,
            metadata=metadata,
        )


class USPSProvider(FormulaCarrierProvider):
    code = "usps"
    credential_keys = ("shipping.usps.client_id", "shipping.usps.client_secret")


class UPSProvider(FormulaCarrierProvider):
    code = "ups"
    credential_keys = ("shipping.ups.client_id", "shipping.ups.client_secret")


class FedExProvider(FormulaCarrierProvider):
    code = "fedex"
    credential_keys = ("shipping.fedex.api_key", "shipping.fedex.api_secret")


class DHLProvider(FormulaCarrierProvider):
    code = "dhl"
    credential_keys = ("shipping.dhl.api_key", "shipping.dhl.api_secret")


PROVIDER_REGISTRY = {
    "flat_rate": FlatRateProvider,
    "local_pickup": LocalPickupProvider,
    "usps": USPSProvider,
    "ups": UPSProvider,
    "fedex": FedExProvider,
    "dhl": DHLProvider,
}


def get_enabled_provider_codes():
    """Return enabled providers in display order."""
    raw = config_service.get_config("shipping.enabled_providers")
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            raw = [part.strip() for part in raw.split(",") if part.strip()]

    if not isinstance(raw, list):
        raw = DEFAULT_ENABLED_PROVIDER_CODES

    enabled_codes = []
    for code in raw:
        if not isinstance(code, str):
            continue
        normalized = code.strip().lower()
        if normalized in PROVIDER_REGISTRY and normalized not in enabled_codes:
            enabled_codes.append(normalized)

    if not enabled_codes:
        enabled_codes = list(DEFAULT_ENABLED_PROVIDER_CODES)

    if "local_pickup" in enabled_codes:
        enabled_codes = ["local_pickup"] + [
            code for code in enabled_codes if code != "local_pickup"
        ]
    else:
        enabled_codes.insert(0, "local_pickup")

    if "flat_rate" not in enabled_codes:
        enabled_codes.append("flat_rate")

    return enabled_codes


def get_provider_catalog():
    """Return provider and method metadata for UI rendering."""
    catalog = []
    for code in get_enabled_provider_codes():
        catalog.append(get_provider(code).as_catalog_dict())
    return catalog


def get_default_provider_code():
    """Return the configured default provider or a safe fallback."""
    enabled_codes = get_enabled_provider_codes()
    configured = config_service.get_config("shipping.default_provider")
    if isinstance(configured, str):
        normalized = configured.strip().lower()
        if normalized in enabled_codes:
            return normalized
    if "flat_rate" in enabled_codes:
        return "flat_rate"
    return enabled_codes[0]


def get_workflow_default_provider_code():
    """Return the UI default provider for quote-first workflows."""
    enabled_codes = get_enabled_provider_codes()
    if "local_pickup" in enabled_codes:
        return "local_pickup"
    return get_default_provider_code()


def get_provider(provider_code=None):
    """Return a provider instance by code, or the default provider."""
    normalized = _normalize_provider_code(provider_code)
    if normalized is None:
        normalized = get_default_provider_code()
    if normalized not in get_enabled_provider_codes():
        raise ValueError(f"Shipping provider is disabled: {normalized}")
    provider_cls = PROVIDER_REGISTRY.get(normalized)
    if provider_cls is None:
        raise ValueError(f"Unknown shipping provider: {provider_code}")
    return provider_cls()


def provider_requires_weight(provider_code=None, method=None):
    """Return whether the selected provider/method requires weight input."""
    resolved_code = _resolve_provider_code(provider_code, method)
    provider = get_provider(resolved_code)
    method_code = method or provider.get_default_method()["code"]
    return provider.requires_weight(method_code)


def quote_shipping(
    weight_lbs=None,
    length_in=None,
    width_in=None,
    height_in=None,
    method=None,
    provider_code=None,
    destination_postal_code=None,
    destination_country=None,
):
    """Return a normalized shipping quote for the selected provider."""
    prepared = _prepare_quote_request(
        weight_lbs=weight_lbs,
        length_in=length_in,
        width_in=width_in,
        height_in=height_in,
        shipping_method=method,
        provider_code=provider_code,
        destination_postal_code=destination_postal_code,
        destination_country=destination_country,
    )
    return prepared["quote"]


def estimate_shipping(
    weight_lbs,
    length_in=None,
    width_in=None,
    height_in=None,
    method=None,
    provider_code=None,
    destination_postal_code=None,
    destination_country=None,
):
    """Retain the cost-only estimator used by order/invoice integrations."""
    try:
        return quote_shipping(
            weight_lbs=weight_lbs,
            length_in=length_in,
            width_in=width_in,
            height_in=height_in,
            method=method,
            provider_code=provider_code,
            destination_postal_code=destination_postal_code,
            destination_country=destination_country,
        ).amount
    except ValueError as exc:
        if "Weight is required" in str(exc):
            return Decimal("0.00")
        raise


def create_shipment(
    order_id,
    weight_lbs=None,
    length_in=None,
    width_in=None,
    height_in=None,
    shipping_method=None,
    provider_code=None,
    destination_postal_code=None,
    destination_country=None,
    carrier=None,
    tracking_number=None,
    notes=None,
    user_id=None,
    ip_address=None,
    user_agent=None,
):
    """Create a new shipment record for a service order."""
    carrier = _clean_text(carrier, "carrier")
    tracking_number = _clean_text(tracking_number, "tracking_number")
    notes = notes.strip() if isinstance(notes, str) and notes.strip() else None

    prepared = _prepare_quote_request(
        weight_lbs=weight_lbs,
        length_in=length_in,
        width_in=width_in,
        height_in=height_in,
        shipping_method=shipping_method,
        provider_code=provider_code,
        destination_postal_code=destination_postal_code,
        destination_country=destination_country,
    )
    quote = prepared["quote"]

    shipment = Shipment(
        order_id=order_id,
        provider_code=prepared["provider_code"],
        weight_lbs=prepared["weight_lbs"],
        length_in=prepared["length_in"],
        width_in=prepared["width_in"],
        height_in=prepared["height_in"],
        shipping_method=prepared["shipping_method"],
        shipping_cost=quote.amount,
        quote_metadata=quote.to_record_metadata(),
        carrier=carrier or quote.provider_name,
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
        pass

    return shipment


def update_shipment(
    shipment_id,
    user_id=None,
    ip_address=None,
    user_agent=None,
    **kwargs,
):
    """Update a shipment record."""
    shipment = get_shipment(shipment_id)

    allowed_fields = {
        "tracking_number",
        "carrier",
        "status",
        "notes",
        "weight_lbs",
        "length_in",
        "width_in",
        "height_in",
        "provider_code",
        "shipping_method",
        "destination_postal_code",
        "destination_country",
    }
    quote_fields = {
        "weight_lbs",
        "length_in",
        "width_in",
        "height_in",
        "provider_code",
        "shipping_method",
        "destination_postal_code",
        "destination_country",
    }

    old_values = {}
    status = kwargs.get("status")
    if status is not None and status not in VALID_STATUSES:
        raise ValueError(f"Invalid shipment status: {status}")

    for field_name in {"tracking_number", "carrier", "notes", "status"}:
        if field_name not in kwargs or field_name not in allowed_fields:
            continue
        old_values[field_name] = getattr(shipment, field_name)
        value = kwargs[field_name]
        if field_name in {"tracking_number", "carrier"}:
            value = _clean_text(value, field_name)
        elif field_name == "notes":
            value = value.strip() if isinstance(value, str) and value.strip() else None
        setattr(shipment, field_name, value)

    if quote_fields.intersection(kwargs):
        quote_metadata = shipment.quote_metadata or {}
        quote_meta_detail = (
            quote_metadata.get("metadata", {})
            if isinstance(quote_metadata, dict)
            else {}
        )
        prepared = _prepare_quote_request(
            weight_lbs=kwargs.get("weight_lbs", shipment.weight_lbs),
            length_in=kwargs.get("length_in", shipment.length_in),
            width_in=kwargs.get("width_in", shipment.width_in),
            height_in=kwargs.get("height_in", shipment.height_in),
            shipping_method=kwargs.get("shipping_method", shipment.shipping_method),
            provider_code=kwargs.get("provider_code", shipment.provider_code),
            destination_postal_code=kwargs.get(
                "destination_postal_code",
                quote_meta_detail.get("destination_postal_code"),
            ),
            destination_country=kwargs.get(
                "destination_country",
                quote_meta_detail.get("destination_country"),
            ),
        )
        quote = prepared["quote"]
        for field_name in (
            "provider_code",
            "shipping_method",
            "weight_lbs",
            "length_in",
            "width_in",
            "height_in",
            "shipping_cost",
            "quote_metadata",
        ):
            old_values.setdefault(field_name, getattr(shipment, field_name))

        shipment.provider_code = prepared["provider_code"]
        shipment.shipping_method = prepared["shipping_method"]
        shipment.weight_lbs = prepared["weight_lbs"]
        shipment.length_in = prepared["length_in"]
        shipment.width_in = prepared["width_in"]
        shipment.height_in = prepared["height_in"]
        shipment.shipping_cost = quote.amount
        shipment.quote_metadata = quote.to_record_metadata()

    db.session.commit()

    changed_fields = {}
    for key, old_value in old_values.items():
        new_value = getattr(shipment, key)
        if old_value != new_value:
            changed_fields[key] = (
                _audit_string_value(old_value),
                _audit_string_value(new_value),
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
                        "provider_code": shipment.provider_code,
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
    """Delete a shipment record."""
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
        (shipment.shipping_cost or Decimal("0.00") for shipment in shipments),
        Decimal("0.00"),
    )


def _prepare_quote_request(
    *,
    weight_lbs=None,
    length_in=None,
    width_in=None,
    height_in=None,
    shipping_method=None,
    provider_code=None,
    destination_postal_code=None,
    destination_country=None,
):
    resolved_provider_code = _resolve_provider_code(provider_code, shipping_method)
    provider = get_provider(resolved_provider_code)
    method_code = _clean_text(
        shipping_method or provider.get_default_method()["code"],
        "shipping_method",
    )
    provider.get_method(method_code)

    requires_weight = provider.requires_weight(method_code)
    normalized_weight = _validate_decimal(
        weight_lbs,
        "weight_lbs",
        allow_zero=not requires_weight,
    )
    if normalized_weight == Decimal("0.00"):
        normalized_weight = None

    if requires_weight and normalized_weight is None:
        raise ValueError("Weight is required for the selected shipping provider.")

    normalized_length = _normalize_dimension(length_in, "length_in")
    normalized_width = _normalize_dimension(width_in, "width_in")
    normalized_height = _normalize_dimension(height_in, "height_in")
    normalized_destination_postal_code = _clean_text(
        destination_postal_code,
        "destination_postal_code",
    )
    normalized_destination_country = _normalize_country(destination_country)

    quote = provider.quote(
        ShippingQuoteRequest(
            weight_lbs=normalized_weight,
            length_in=normalized_length,
            width_in=normalized_width,
            height_in=normalized_height,
            provider_code=resolved_provider_code,
            method_code=method_code,
            destination_postal_code=normalized_destination_postal_code,
            destination_country=normalized_destination_country,
        )
    )
    return {
        "provider_code": resolved_provider_code,
        "shipping_method": method_code,
        "weight_lbs": normalized_weight,
        "length_in": normalized_length,
        "width_in": normalized_width,
        "height_in": normalized_height,
        "destination_postal_code": normalized_destination_postal_code,
        "destination_country": normalized_destination_country,
        "quote": quote,
    }


def _resolve_provider_code(provider_code=None, shipping_method=None):
    normalized_provider = _normalize_provider_code(provider_code)
    if normalized_provider:
        return normalized_provider

    cleaned_method = _clean_text(shipping_method, "shipping_method") if shipping_method else None
    if cleaned_method:
        for code, provider_cls in PROVIDER_REGISTRY.items():
            provider = provider_cls()
            try:
                provider.get_method(cleaned_method)
                return code
            except ValueError:
                continue

    return get_default_provider_code()


def _normalize_provider_code(provider_code):
    if provider_code is None:
        return None
    cleaned = _clean_text(str(provider_code).lower(), "provider_code")
    return cleaned.lower() if cleaned else None


def _normalize_country(value):
    cleaned = _clean_text(value or "US", "destination_country")
    return cleaned.upper() if cleaned else "US"


def _get_provider_overrides():
    raw = config_service.get_config("shipping.provider_overrides")
    if not raw:
        return {}
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except json.JSONDecodeError:
            return {}
    return raw if isinstance(raw, dict) else {}


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

    return decimal_value.quantize(MEASUREMENT_QUANTUM, rounding=ROUND_HALF_UP)


def _normalize_dimension(value, field_name):
    normalized = _validate_decimal(value, field_name)
    if normalized in {None, Decimal("0.00")}:
        return None
    return normalized


def _package_volume(length_in, width_in, height_in):
    if not all([length_in, width_in, height_in]):
        return None
    return Decimal(str(length_in)) * Decimal(str(width_in)) * Decimal(str(height_in))


def _decimal_or_zero(value):
    if value in (None, ""):
        return Decimal("0.00")
    return Decimal(str(value))


def _quantize_money(value):
    return Decimal(str(value)).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _quantize_measure(value):
    return Decimal(str(value)).quantize(MEASUREMENT_QUANTUM, rounding=ROUND_HALF_UP)


def _format_decimal(value):
    if value is None:
        return None
    return f"{Decimal(str(value)).quantize(MEASUREMENT_QUANTUM, rounding=ROUND_HALF_UP):.2f}"


def _json_safe(value):
    if isinstance(value, Decimal):
        return _format_decimal(value)
    if isinstance(value, dict):
        return {key: _json_safe(val) for key, val in value.items() if val is not None}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    return value


def _audit_string_value(value):
    if value is None:
        return None
    if isinstance(value, dict):
        return json.dumps(_json_safe(value), sort_keys=True)
    return str(value)


def _shipment_audit_data(shipment):
    """Serialize shipment context for audit logs with bounded note size."""
    notes = shipment.notes
    if notes and len(notes) > AUDIT_NOTES_MAX_LENGTH:
        notes = f"{notes[:AUDIT_NOTES_MAX_LENGTH]}..."

    return json.dumps(
        {
            "order_id": shipment.order_id,
            "provider_code": shipment.provider_code,
            "shipping_method": shipment.shipping_method,
            "carrier": shipment.carrier,
            "tracking_number": shipment.tracking_number,
            "status": shipment.status,
            "shipping_cost": str(shipment.shipping_cost or "0.00"),
            "quote_metadata": _json_safe(shipment.quote_metadata or {}),
            "notes": notes,
        }
    )


def _format_destination_summary(postal_code, country):
    postal = postal_code.strip() if isinstance(postal_code, str) and postal_code.strip() else None
    normalized_country = _normalize_country(country)
    if postal and normalized_country and normalized_country != "US":
        return f"{postal}, {normalized_country}"
    if postal:
        return postal
    if normalized_country and normalized_country != "US":
        return normalized_country
    return None
