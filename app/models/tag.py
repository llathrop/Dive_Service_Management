"""Tag and Taggable models for polymorphic tagging.

Implements a generic tagging system where any model can be tagged using
a polymorphic association (taggable_type + taggable_id).  The TaggableMixin
provides convenience methods for models that want tag support.

Models:
    Tag      -- a named label with optional color and group
    Taggable -- the polymorphic join between tags and taggable entities

Mixin:
    TaggableMixin -- adds tag helper methods to any model
"""

from sqlalchemy import Index, UniqueConstraint

from app.extensions import db


# ---------------------------------------------------------------------------
# Tag
# ---------------------------------------------------------------------------

class Tag(db.Model):
    """A named tag/label that can be applied to any entity."""

    __tablename__ = "tags"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    color = db.Column(db.String(7), nullable=True)  # hex color, e.g. #FF5733
    tag_group = db.Column(db.String(50), nullable=True)

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=db.func.now(),
    )

    __table_args__ = (
        Index("ix_tags_tag_group", "tag_group"),
    )

    def __repr__(self):
        return f"<Tag {self.name!r}>"


# ---------------------------------------------------------------------------
# Taggable (polymorphic join table)
# ---------------------------------------------------------------------------

class Taggable(db.Model):
    """Polymorphic association linking a Tag to any entity.

    The ``taggable_type`` identifies the model (e.g. 'customer',
    'service_item') and ``taggable_id`` is the primary key of that
    entity.
    """

    __tablename__ = "taggables"

    id = db.Column(db.Integer, primary_key=True)

    tag_id = db.Column(
        db.Integer,
        db.ForeignKey("tags.id"),
        nullable=False,
    )
    taggable_type = db.Column(db.String(50), nullable=False)
    taggable_id = db.Column(db.Integer, nullable=False)

    created_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=db.func.now(),
    )

    # --- Relationships ---
    tag = db.relationship("Tag")

    __table_args__ = (
        UniqueConstraint(
            "tag_id", "taggable_type", "taggable_id",
            name="uq_taggable_unique",
        ),
        Index("ix_taggable_type_id", "taggable_type", "taggable_id"),
    )

    def __repr__(self):
        return (
            f"<Taggable tag_id={self.tag_id} "
            f"type={self.taggable_type!r} id={self.taggable_id}>"
        )


# ---------------------------------------------------------------------------
# TaggableMixin
# ---------------------------------------------------------------------------

class TaggableMixin:
    """Mixin that adds tagging helper methods to any model.

    The model must define a ``__taggable_type__`` class attribute that
    identifies the entity type string used in the ``taggables`` table.
    If not set, it defaults to the lowercase class name.

    Usage::

        class Customer(TaggableMixin, TimestampMixin, db.Model):
            __taggable_type__ = "customer"
            ...

        customer.add_tag(tag, session)
        customer.remove_tag(tag, session)
        tags = customer.get_tags(session)
    """

    @classmethod
    def _get_taggable_type(cls):
        """Return the taggable_type string for this model."""
        return getattr(cls, "__taggable_type__", cls.__name__.lower())

    def add_tag(self, tag, session=None):
        """Associate a Tag with this entity.

        Creates a Taggable record linking the given tag to this instance.
        If the association already exists, this is a no-op.

        Args:
            tag: A Tag instance to associate.
            session: The SQLAlchemy session to use.  Falls back to
                db.session if not provided.
        """
        if session is None:
            session = db.session
        taggable_type = self._get_taggable_type()
        existing = session.query(Taggable).filter_by(
            tag_id=tag.id,
            taggable_type=taggable_type,
            taggable_id=self.id,
        ).first()
        if not existing:
            taggable = Taggable(
                tag_id=tag.id,
                taggable_type=taggable_type,
                taggable_id=self.id,
            )
            session.add(taggable)

    def remove_tag(self, tag, session=None):
        """Remove a tag association from this entity.

        Args:
            tag: A Tag instance to disassociate.
            session: The SQLAlchemy session to use.
        """
        if session is None:
            session = db.session
        taggable_type = self._get_taggable_type()
        session.query(Taggable).filter_by(
            tag_id=tag.id,
            taggable_type=taggable_type,
            taggable_id=self.id,
        ).delete()

    def get_tags(self, session=None):
        """Return all Tag objects associated with this entity.

        Args:
            session: The SQLAlchemy session to use.

        Returns:
            A list of Tag instances.
        """
        if session is None:
            session = db.session
        taggable_type = self._get_taggable_type()
        taggables = session.query(Taggable).filter_by(
            taggable_type=taggable_type,
            taggable_id=self.id,
        ).all()
        tag_ids = [t.tag_id for t in taggables]
        if not tag_ids:
            return []
        return session.query(Tag).filter(Tag.id.in_(tag_ids)).all()
