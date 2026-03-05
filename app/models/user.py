"""User and Role models for authentication and authorization.

Uses Flask-Security-Too which requires specific fields on the User model:
``email``, ``password``, ``active``, ``fs_uniquifier``, and a ``roles``
relationship.  See https://flask-security-too.readthedocs.io/ for details.
"""

import uuid
from datetime import datetime, timezone

from flask_security import RoleMixin, UserMixin

from app.extensions import db
from app.models.mixins import TimestampMixin


# ---------------------------------------------------------------------------
# Association table (not a model) for the many-to-many User <-> Role link.
# ---------------------------------------------------------------------------

user_roles = db.Table(
    "user_roles",
    db.Column(
        "user_id",
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    db.Column(
        "role_id",
        db.Integer,
        db.ForeignKey("roles.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


# ---------------------------------------------------------------------------
# Role model
# ---------------------------------------------------------------------------

class Role(db.Model, RoleMixin):
    """Authorization role (e.g. admin, technician, viewer).

    Flask-Security requires ``name`` at minimum.  We also store an optional
    ``description`` and a free-form ``permissions`` text field (can be used
    for fine-grained permission strings in the future).
    """

    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=False, index=True)
    description = db.Column(db.String(255), nullable=True)
    permissions = db.Column(db.Text, nullable=True)
    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self):
        return f"<Role {self.name!r}>"


# ---------------------------------------------------------------------------
# User model
# ---------------------------------------------------------------------------

class User(TimestampMixin, db.Model, UserMixin):
    """Application user with Flask-Security integration.

    Includes all fields required by Flask-Security-Too plus application-
    specific extras like ``username``, ``first_name``, ``last_name``.

    The ``password`` column stores the hashed password (Flask-Security
    manages hashing transparently).  Do **not** rename this to
    ``password_hash`` -- Flask-Security expects ``password``.
    """

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    # --- Identity ---
    username = db.Column(db.String(80), unique=True, nullable=False, index=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)

    # --- Flask-Security required fields ---
    password = db.Column(db.String(255), nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    fs_uniquifier = db.Column(
        db.String(64),
        unique=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )
    confirmed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # --- Login tracking (SECURITY_TRACKABLE = True) ---
    last_login_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_login_ip = db.Column(db.String(45), nullable=True)
    current_login_at = db.Column(db.DateTime(timezone=True), nullable=True)
    current_login_ip = db.Column(db.String(45), nullable=True)
    login_count = db.Column(db.Integer, default=0)

    # --- Relationships ---
    roles = db.relationship(
        "Role",
        secondary=user_roles,
        backref=db.backref("users", lazy="dynamic"),
    )

    # ------------------------------------------------------------------
    # Convenience properties / methods
    # ------------------------------------------------------------------

    @property
    def display_name(self):
        """Return the user's full display name."""
        return f"{self.first_name} {self.last_name}"

    @property
    def is_active(self):
        """Flask-Security checks ``is_active``; proxy to ``active`` column."""
        return self.active

    @is_active.setter
    def is_active(self, value):
        self.active = value

    def __repr__(self):
        return f"<User {self.username!r}>"
