"""Tag service layer — business logic for tag management.

Provides module-level functions for creating, searching, and managing
tags and their polymorphic associations with any entity.
"""

import re
import unicodedata

from app.extensions import db
from app.models.tag import Tag, Taggable


def _slugify(text):
    """Convert text to a URL-safe slug.

    Normalises unicode, lowercases, replaces non-alphanumeric characters
    with hyphens, and strips leading/trailing hyphens.

    Args:
        text: The string to slugify.

    Returns:
        A lowercase, hyphen-separated slug string.
    """
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    text = text.strip("-")
    return text


def get_or_create_tag(name, tag_group=None, color=None):
    """Get an existing tag by name or create a new one.

    If a tag with the given name already exists, it is returned as-is
    (tag_group and color are NOT updated on existing tags).

    Args:
        name: The tag name.
        tag_group: Optional group/category for the tag.
        color: Optional hex color (e.g. '#FF5733').

    Returns:
        A Tag instance (existing or newly created).
    """
    existing = Tag.query.filter(Tag.name == name).first()
    if existing:
        return existing

    tag = Tag(
        name=name,
        slug=_slugify(name),
        tag_group=tag_group,
        color=color,
    )
    db.session.add(tag)
    db.session.commit()
    return tag


def get_tags(tag_group=None):
    """Return all tags, optionally filtered by group.

    Args:
        tag_group: Optional group name to filter by.

    Returns:
        A list of Tag instances ordered by name.
    """
    query = Tag.query.order_by(Tag.name)
    if tag_group:
        query = query.filter(Tag.tag_group == tag_group)
    return query.all()


def search_tags(query, limit=10):
    """Search tags by name prefix for autocomplete.

    Args:
        query: The search prefix.
        limit: Maximum number of results to return.

    Returns:
        A list of Tag instances matching the prefix.
    """
    if not query:
        return []

    pattern = f"%{query}%"
    return (
        Tag.query
        .filter(Tag.name.ilike(pattern))
        .order_by(Tag.name)
        .limit(limit)
        .all()
    )


def add_tag_to_entity(tag_name, entity_type, entity_id):
    """Add a tag to any entity.  Creates the tag if it does not exist.

    If the tag is already associated with the entity, this is a no-op.

    Args:
        tag_name: The name of the tag.
        entity_type: The entity type string (e.g. 'customer', 'service_item').
        entity_id: The primary key of the entity.

    Returns:
        The Taggable association record (new or existing).
    """
    tag = get_or_create_tag(tag_name)

    existing = Taggable.query.filter_by(
        tag_id=tag.id,
        taggable_type=entity_type,
        taggable_id=entity_id,
    ).first()

    if existing:
        return existing

    taggable = Taggable(
        tag_id=tag.id,
        taggable_type=entity_type,
        taggable_id=entity_id,
    )
    db.session.add(taggable)
    db.session.commit()
    return taggable


def remove_tag_from_entity(tag_id, entity_type, entity_id):
    """Remove a tag from an entity.

    Args:
        tag_id: The primary key of the tag.
        entity_type: The entity type string.
        entity_id: The primary key of the entity.
    """
    Taggable.query.filter_by(
        tag_id=tag_id,
        taggable_type=entity_type,
        taggable_id=entity_id,
    ).delete()
    db.session.commit()


def get_tags_for_entity(entity_type, entity_id):
    """Get all tags for a specific entity.

    Args:
        entity_type: The entity type string (e.g. 'customer').
        entity_id: The primary key of the entity.

    Returns:
        A list of Tag instances associated with the entity.
    """
    taggables = Taggable.query.filter_by(
        taggable_type=entity_type,
        taggable_id=entity_id,
    ).all()

    tag_ids = [t.tag_id for t in taggables]
    if not tag_ids:
        return []

    return Tag.query.filter(Tag.id.in_(tag_ids)).order_by(Tag.name).all()
