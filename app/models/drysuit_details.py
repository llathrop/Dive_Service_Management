"""DrysuitDetails model -- one-to-one extension of ServiceItem.

Stores detailed specifications for drysuit-type service items, including
seal types, zipper configuration, valve details, and boot information.
This avoids cluttering the generic ServiceItem table with drysuit-only
columns.
"""

from app.extensions import db
from app.models.mixins import TimestampMixin


class DrysuitDetails(TimestampMixin, db.Model):
    """Extended details for a drysuit service item (1:1 relationship)."""

    __tablename__ = "drysuit_details"

    id = db.Column(db.Integer, primary_key=True)

    # --- Link to parent ServiceItem (unique = 1:1) ---
    service_item_id = db.Column(
        db.Integer,
        db.ForeignKey("service_items.id"),
        unique=True,
        nullable=False,
    )

    # --- Suit basics ---
    size = db.Column(db.String(50), nullable=True)
    material_type = db.Column(db.String(100), nullable=True)
    material_thickness = db.Column(db.String(50), nullable=True)
    color = db.Column(db.String(100), nullable=True)
    suit_entry_type = db.Column(db.String(50), nullable=True)

    # --- Seals ---
    neck_seal_type = db.Column(db.String(50), nullable=True)
    neck_seal_system = db.Column(db.String(100), nullable=True)
    wrist_seal_type = db.Column(db.String(50), nullable=True)
    wrist_seal_system = db.Column(db.String(100), nullable=True)

    # --- Zipper ---
    zipper_type = db.Column(db.String(100), nullable=True)
    zipper_length = db.Column(db.String(50), nullable=True)
    zipper_orientation = db.Column(db.String(50), nullable=True)

    # --- Inflate valve ---
    inflate_valve_brand = db.Column(db.String(100), nullable=True)
    inflate_valve_model = db.Column(db.String(100), nullable=True)
    inflate_valve_position = db.Column(db.String(50), nullable=True)

    # --- Dump valve ---
    dump_valve_brand = db.Column(db.String(100), nullable=True)
    dump_valve_model = db.Column(db.String(100), nullable=True)
    dump_valve_type = db.Column(db.String(50), nullable=True)

    # --- Boots ---
    boot_type = db.Column(db.String(50), nullable=True)
    boot_size = db.Column(db.String(20), nullable=True)

    # --- Relationships ---
    service_item = db.relationship(
        "ServiceItem",
        back_populates="drysuit_details",
    )

    def __repr__(self):
        return f"<DrysuitDetails service_item_id={self.service_item_id}>"
