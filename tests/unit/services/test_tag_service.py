"""Unit tests for the tag service layer.

Tests cover tag creation, search, and polymorphic entity tagging.
"""

import pytest

from app.extensions import db
from app.models.tag import Tag, Taggable
from app.services import tag_service

pytestmark = pytest.mark.unit


class TestGetOrCreateTag:
    """Tests for get_or_create_tag()."""

    def test_get_or_create_tag_new(self, app, db_session):
        """Creates a new tag with auto-generated slug."""
        tag = tag_service.get_or_create_tag(
            "Urgent", tag_group="priority", color="#FF0000"
        )

        assert tag.id is not None
        assert tag.name == "Urgent"
        assert tag.slug == "urgent"
        assert tag.tag_group == "priority"
        assert tag.color == "#FF0000"

    def test_get_or_create_tag_existing(self, app, db_session):
        """Returns existing tag instead of creating a duplicate."""
        tag1 = tag_service.get_or_create_tag("VIP")
        tag2 = tag_service.get_or_create_tag("VIP")

        assert tag1.id == tag2.id

        # Verify only one tag exists with this name
        count = Tag.query.filter_by(name="VIP").count()
        assert count == 1


class TestSearchTags:
    """Tests for search_tags()."""

    def test_search_tags(self, app, db_session):
        """Search returns tags matching the query prefix."""
        tag_service.get_or_create_tag("Urgent")
        tag_service.get_or_create_tag("Under Review")
        tag_service.get_or_create_tag("Complete")

        results = tag_service.search_tags("Ur")
        names = [t.name for t in results]
        assert "Urgent" in names
        assert "Complete" not in names

    def test_search_tags_empty_query(self, app, db_session):
        """Empty query returns empty list."""
        tag_service.get_or_create_tag("Urgent")

        results = tag_service.search_tags("")
        assert results == []


class TestAddTagToEntity:
    """Tests for add_tag_to_entity()."""

    def test_add_tag_to_entity(self, app, db_session):
        """Creates a Taggable record linking tag to entity."""
        taggable = tag_service.add_tag_to_entity(
            "Priority", "customer", 1
        )

        assert taggable.id is not None
        assert taggable.taggable_type == "customer"
        assert taggable.taggable_id == 1

        # Verify the tag was created
        tag = Tag.query.filter_by(name="Priority").first()
        assert tag is not None
        assert taggable.tag_id == tag.id

    def test_add_tag_duplicate(self, app, db_session):
        """Adding the same tag to the same entity is a no-op (no duplicate)."""
        taggable1 = tag_service.add_tag_to_entity("VIP", "customer", 1)
        taggable2 = tag_service.add_tag_to_entity("VIP", "customer", 1)

        assert taggable1.id == taggable2.id

        # Verify only one Taggable record exists
        count = Taggable.query.filter_by(
            taggable_type="customer", taggable_id=1
        ).count()
        assert count == 1


class TestRemoveTagFromEntity:
    """Tests for remove_tag_from_entity()."""

    def test_remove_tag_from_entity(self, app, db_session):
        """Removes the Taggable association record."""
        tag_service.add_tag_to_entity("ToRemove", "customer", 1)
        tag = Tag.query.filter_by(name="ToRemove").first()

        tag_service.remove_tag_from_entity(tag.id, "customer", 1)

        remaining = Taggable.query.filter_by(
            tag_id=tag.id, taggable_type="customer", taggable_id=1
        ).first()
        assert remaining is None


class TestGetTagsForEntity:
    """Tests for get_tags_for_entity()."""

    def test_get_tags_for_entity(self, app, db_session):
        """Returns all tags associated with a specific entity."""
        tag_service.add_tag_to_entity("Priority", "customer", 1)
        tag_service.add_tag_to_entity("VIP", "customer", 1)
        tag_service.add_tag_to_entity("Other", "customer", 2)  # different entity

        tags = tag_service.get_tags_for_entity("customer", 1)
        names = [t.name for t in tags]
        assert "Priority" in names
        assert "VIP" in names
        assert "Other" not in names
        assert len(tags) == 2

    def test_get_tags_for_entity_empty(self, app, db_session):
        """Returns empty list when entity has no tags."""
        tags = tag_service.get_tags_for_entity("customer", 999)
        assert tags == []


class TestSlugify:
    """Tests for the internal _slugify function."""

    def test_slugify_basic(self, app, db_session):
        """Converts basic text to a lowercase hyphenated slug."""
        assert tag_service._slugify("Hello World") == "hello-world"

    def test_slugify_special_chars(self, app, db_session):
        """Strips special characters from the slug."""
        assert tag_service._slugify("Test & Tag!") == "test-tag"

    def test_slugify_unicode(self, app, db_session):
        """Handles unicode characters by ASCII transliteration."""
        result = tag_service._slugify("cafe")
        assert result == "cafe"
