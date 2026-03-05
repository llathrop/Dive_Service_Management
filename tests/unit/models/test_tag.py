"""Unit tests for the Tag and Taggable models.

Tests cover tag creation, uniqueness constraints, polymorphic tagging,
the unique constraint on (tag_id, taggable_type, taggable_id), and
tagging different entity types with the same tag.
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models.tag import Tag, Taggable
from tests.factories import TagFactory, TaggableFactory

pytestmark = pytest.mark.unit


def _set_session(db_session):
    """Configure all factories to use the given session."""
    TagFactory._meta.sqlalchemy_session = db_session
    TaggableFactory._meta.sqlalchemy_session = db_session


class TestTag:
    """Tests for the Tag model."""

    def test_create_tag(self, app, db_session):
        """A tag persists with name, slug, color, and group."""
        _set_session(db_session)
        tag = TagFactory(
            name="urgent",
            slug="urgent",
            color="#FF0000",
            tag_group="priority",
        )

        fetched = db_session.get(Tag, tag.id)
        assert fetched is not None
        assert fetched.name == "urgent"
        assert fetched.slug == "urgent"
        assert fetched.color == "#FF0000"
        assert fetched.tag_group == "priority"
        assert fetched.created_at is not None

    def test_tag_unique_name(self, app, db_session):
        """Duplicate tag names raise IntegrityError."""
        _set_session(db_session)
        TagFactory(name="duplicate-name", slug="duplicate-name")

        with pytest.raises(IntegrityError):
            TagFactory(name="duplicate-name", slug="duplicate-name-2")
            db_session.flush()

    def test_tag_unique_slug(self, app, db_session):
        """Duplicate tag slugs raise IntegrityError."""
        _set_session(db_session)
        TagFactory(name="tag-one", slug="same-slug")

        with pytest.raises(IntegrityError):
            TagFactory(name="tag-two", slug="same-slug")
            db_session.flush()


class TestTaggable:
    """Tests for the Taggable model (polymorphic join)."""

    def test_create_taggable(self, app, db_session):
        """A taggable association persists correctly."""
        _set_session(db_session)
        tag = TagFactory(name="vip", slug="vip")
        taggable = TaggableFactory(
            tag=tag,
            taggable_type="customer",
            taggable_id=42,
        )

        fetched = db_session.get(Taggable, taggable.id)
        assert fetched is not None
        assert fetched.tag_id == tag.id
        assert fetched.taggable_type == "customer"
        assert fetched.taggable_id == 42
        assert fetched.tag.name == "vip"

    def test_taggable_unique_constraint(self, app, db_session):
        """The same tag+type+id combination raises IntegrityError."""
        _set_session(db_session)
        tag = TagFactory(name="repeat", slug="repeat")
        TaggableFactory(
            tag=tag,
            taggable_type="customer",
            taggable_id=1,
        )

        with pytest.raises(IntegrityError):
            TaggableFactory(
                tag=tag,
                taggable_type="customer",
                taggable_id=1,
            )
            db_session.flush()

    def test_tag_different_entity_types(self, app, db_session):
        """The same tag can be applied to different entity types."""
        _set_session(db_session)
        tag = TagFactory(name="shared-tag", slug="shared-tag")

        # Apply to a customer
        t1 = TaggableFactory(
            tag=tag,
            taggable_type="customer",
            taggable_id=10,
        )
        # Apply to a service_item
        t2 = TaggableFactory(
            tag=tag,
            taggable_type="service_item",
            taggable_id=10,
        )
        # Apply to an inventory_item
        t3 = TaggableFactory(
            tag=tag,
            taggable_type="inventory_item",
            taggable_id=10,
        )

        # All three should exist
        all_taggables = db_session.query(Taggable).filter_by(
            tag_id=tag.id
        ).all()
        assert len(all_taggables) == 3
        types = {t.taggable_type for t in all_taggables}
        assert types == {"customer", "service_item", "inventory_item"}

    def test_same_tag_same_type_different_ids(self, app, db_session):
        """The same tag can be applied to multiple entities of the same type."""
        _set_session(db_session)
        tag = TagFactory(name="multi", slug="multi")

        TaggableFactory(tag=tag, taggable_type="customer", taggable_id=1)
        TaggableFactory(tag=tag, taggable_type="customer", taggable_id=2)
        TaggableFactory(tag=tag, taggable_type="customer", taggable_id=3)

        count = db_session.query(Taggable).filter_by(
            tag_id=tag.id,
            taggable_type="customer",
        ).count()
        assert count == 3
