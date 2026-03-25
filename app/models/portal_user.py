"""Portal customer-auth models.

Portal accounts are distinct from internal Flask-Security users. They are
linked to customers and use a separate password hash plus a separate token
table for invite/activation flows.
"""

import hashlib
import secrets
from datetime import datetime, timedelta

from sqlalchemy.orm import validates
from werkzeug.security import check_password_hash, generate_password_hash

from app.extensions import db
from app.models.mixins import TimestampMixin


PORTAL_TOKEN_PURPOSE_ACTIVATION = "activation"
PORTAL_TOKEN_PURPOSE_INVITE = "invite"
PORTAL_TOKEN_PURPOSE_PASSWORD_RESET = "password_reset"
PORTAL_TOKEN_PURPOSES = (
    PORTAL_TOKEN_PURPOSE_ACTIVATION,
    PORTAL_TOKEN_PURPOSE_INVITE,
    PORTAL_TOKEN_PURPOSE_PASSWORD_RESET,
)


def _normalize_email(value):
    if value is None:
        return None
    return value.strip().lower()


def _hash_token(raw_token):
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _utcnow():
    return datetime.utcnow()


class PortalUser(TimestampMixin, db.Model):
    """Customer portal account.

    A portal user belongs to exactly one customer and can be activated via a
    separate invite token. Internal staff accounts remain in ``users``.
    """

    __tablename__ = "portal_users"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(
        db.Integer,
        db.ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=False)
    confirmed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)
    current_login_at = db.Column(db.DateTime(timezone=True), nullable=True)
    login_count = db.Column(db.Integer, nullable=False, default=0)

    customer = db.relationship("Customer", back_populates="portal_users")
    access_tokens = db.relationship(
        "PortalAccessToken",
        back_populates="portal_user",
        lazy="dynamic",
    )

    @validates("email")
    def validate_email(self, key, value):
        value = _normalize_email(value)
        if not value:
            raise ValueError("email is required for portal users")
        return value

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    @property
    def display_name(self):
        if self.customer and self.customer.display_name:
            return self.customer.display_name
        return self.email

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    @property
    def is_active(self):
        return bool(self.active)

    def get_id(self):
        return str(self.id)

    def __repr__(self):
        return f"<PortalUser {self.email!r}>"


class PortalAccessToken(TimestampMixin, db.Model):
    """Hashed invite/activation token for portal accounts."""

    __tablename__ = "portal_access_tokens"

    id = db.Column(db.Integer, primary_key=True)
    customer_id = db.Column(
        db.Integer,
        db.ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    portal_user_id = db.Column(
        db.Integer,
        db.ForeignKey("portal_users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    email = db.Column(db.String(255), nullable=False, index=True)
    purpose = db.Column(
        db.String(32),
        nullable=False,
        default=PORTAL_TOKEN_PURPOSE_ACTIVATION,
        index=True,
    )
    token_hash = db.Column(db.String(64), unique=True, nullable=False, index=True)
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    used_at = db.Column(db.DateTime(timezone=True), nullable=True)

    customer = db.relationship(
        "Customer",
        backref=db.backref("portal_access_tokens", lazy="dynamic"),
    )
    portal_user = db.relationship("PortalUser", back_populates="access_tokens")

    @validates("email")
    def validate_email(self, key, value):
        value = _normalize_email(value)
        if not value:
            raise ValueError("email is required for portal tokens")
        return value

    @validates("purpose")
    def validate_purpose(self, key, value):
        if value not in PORTAL_TOKEN_PURPOSES:
            raise ValueError(
                f"purpose must be one of {PORTAL_TOKEN_PURPOSES}, got {value!r}"
            )
        return value

    @property
    def is_expired(self):
        return self.expires_at <= _utcnow()

    @property
    def is_used(self):
        return self.used_at is not None

    @property
    def is_valid(self):
        return not self.is_used and not self.is_expired

    @classmethod
    def issue_activation(cls, customer, email, expires_in=timedelta(hours=72)):
        """Create a fresh activation token and return the row plus raw token."""
        customer_id = getattr(customer, "id", customer)
        if customer_id is None:
            raise ValueError("customer is required for portal activation tokens")
        normalized_email = _normalize_email(email)
        if not normalized_email:
            raise ValueError("email is required for portal activation tokens")

        existing_user = PortalUser.query.filter_by(
            customer_id=customer_id,
            email=normalized_email,
        ).one_or_none()

        # Revoke any previously-issued unused activation links for the same
        # customer/email pair before creating the new one.
        db.session.query(cls).filter(
            cls.customer_id == customer_id,
            cls.email == normalized_email,
            cls.purpose == PORTAL_TOKEN_PURPOSE_ACTIVATION,
            cls.used_at.is_(None),
        ).update({cls.used_at: _utcnow()}, synchronize_session=False)

        raw_token = secrets.token_urlsafe(32)
        token = cls(
            customer_id=customer_id,
            email=normalized_email,
            purpose=PORTAL_TOKEN_PURPOSE_ACTIVATION,
            token_hash=_hash_token(raw_token),
            expires_at=_utcnow() + expires_in,
            portal_user=existing_user,
        )
        db.session.add(token)
        return token, raw_token

    @classmethod
    def lookup_valid_token(cls, raw_token):
        token_hash = _hash_token(raw_token)
        token = cls.query.filter_by(token_hash=token_hash).first()
        if token is None or not token.is_valid:
            return None
        return token

    def consume(self, portal_user):
        self.portal_user = portal_user
        self.used_at = _utcnow()

    def __repr__(self):
        return f"<PortalAccessToken {self.purpose!r} {self.email!r}>"
