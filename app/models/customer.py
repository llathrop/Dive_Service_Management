"""Customer model for tracking individuals and businesses.

Customers are the people or organizations that bring equipment in for
service.  A customer can be either an individual (first_name + last_name)
or a business (business_name + optional contact_person).

Includes soft-delete support and audit trail.
"""

from sqlalchemy import Index
from sqlalchemy.orm import validates

from app.extensions import db
from app.models.mixins import AuditMixin, SoftDeleteMixin, TimestampMixin


class Customer(TimestampMixin, SoftDeleteMixin, AuditMixin, db.Model):
    """A customer -- individual person or business entity."""

    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)

    # --- Customer type ---
    customer_type = db.Column(
        db.String(20), nullable=False, default="individual"
    )

    # --- Name fields ---
    first_name = db.Column(db.String(100), nullable=True)
    last_name = db.Column(db.String(100), nullable=True)
    business_name = db.Column(db.String(255), nullable=True)
    contact_person = db.Column(db.String(200), nullable=True)

    # --- Contact info ---
    email = db.Column(db.String(255), nullable=True)
    phone_primary = db.Column(db.String(20), nullable=True)
    phone_secondary = db.Column(db.String(20), nullable=True)

    # --- Address ---
    address_line1 = db.Column(db.String(255), nullable=True)
    address_line2 = db.Column(db.String(255), nullable=True)
    city = db.Column(db.String(100), nullable=True)
    state_province = db.Column(db.String(100), nullable=True)
    postal_code = db.Column(db.String(20), nullable=True)
    country = db.Column(db.String(100), nullable=True, default="US")

    # --- Preferences ---
    preferred_contact = db.Column(
        db.String(20), nullable=False, default="email"
    )

    # --- Financial ---
    tax_exempt = db.Column(db.Boolean, nullable=False, default=False)
    tax_id = db.Column(db.String(50), nullable=True)
    payment_terms = db.Column(db.String(100), nullable=True)
    credit_limit = db.Column(db.Numeric(10, 2), nullable=True)

    # --- Service flags ---
    do_not_service = db.Column(db.Boolean, nullable=False, default=False)
    do_not_service_reason = db.Column(db.String(500), nullable=True)

    # --- Notes ---
    notes = db.Column(db.Text, nullable=True)
    referral_source = db.Column(db.String(100), nullable=True)

    # --- Relationships ---
    service_items = db.relationship(
        "ServiceItem",
        back_populates="customer",
        lazy="dynamic",
    )

    # --- Table indexes ---
    __table_args__ = (
        Index("ix_customers_last_first", "last_name", "first_name"),
        Index("ix_customers_business_name", "business_name"),
        Index("ix_customers_email", "email"),
    )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    @validates("customer_type")
    def validate_customer_type(self, key, value):
        """Ensure customer_type is one of the allowed values."""
        allowed = ("individual", "business")
        if value not in allowed:
            raise ValueError(
                f"customer_type must be one of {allowed}, got {value!r}"
            )
        return value

    @validates("preferred_contact")
    def validate_preferred_contact(self, key, value):
        """Ensure preferred_contact is one of the allowed values."""
        allowed = ("email", "phone", "text", "none")
        if value not in allowed:
            raise ValueError(
                f"preferred_contact must be one of {allowed}, got {value!r}"
            )
        return value

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def display_name(self):
        """Return a human-readable name for the customer.

        For individuals, returns "First Last".
        For businesses, returns the business_name.
        """
        if self.business_name:
            return self.business_name
        parts = [p for p in (self.first_name, self.last_name) if p]
        return " ".join(parts) if parts else ""

    @property
    def full_address(self):
        """Return the full mailing address as a multi-line string."""
        lines = []
        if self.address_line1:
            lines.append(self.address_line1)
        if self.address_line2:
            lines.append(self.address_line2)
        city_state = ", ".join(
            p for p in (self.city, self.state_province) if p
        )
        if city_state and self.postal_code:
            city_state = f"{city_state} {self.postal_code}"
        elif self.postal_code:
            city_state = self.postal_code
        if city_state:
            lines.append(city_state)
        if self.country and self.country != "US":
            lines.append(self.country)
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Name validation (must have individual OR business name)
    # ------------------------------------------------------------------

    def validate_name(self):
        """Ensure either individual or business name is provided.

        Raises ValueError if neither (first_name AND last_name) nor
        business_name is set.
        """
        has_individual = bool(self.first_name and self.last_name)
        has_business = bool(self.business_name)
        if not has_individual and not has_business:
            raise ValueError(
                "Customer must have either (first_name and last_name) "
                "or business_name."
            )

    def __repr__(self):
        return f"<Customer {self.id} {self.display_name!r}>"
