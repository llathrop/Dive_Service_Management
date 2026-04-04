from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from app.extensions import db
from app.models.lookup import LookupValue

lookups_bp = Blueprint('lookups', __name__, url_prefix='/api/lookups')

@lookups_bp.route('/create', methods=['POST'])
@login_required
def quick_create():
    """API endpoint to quickly create a new lookup value."""
    data = request.get_json() or {}
    category = data.get('category')
    name = data.get('name', '').strip()

    if not category or not name:
        return jsonify({'error': 'Category and name are required'}), 400

    # Check if it already exists (case-insensitive check if needed, but here using exact)
    existing = LookupValue.query.filter_by(category=category, value=name).first()
    if existing:
        return jsonify({
            'id': existing.id,
            'value': existing.value,
            'display_name': existing.display_name
        }), 200

    # Create new lookup
    try:
        new_lookup = LookupValue(
            category=category,
            value=name,
            display_name=name,
            created_by=current_user.id
        )
        db.session.add(new_lookup)
        db.session.commit()

        return jsonify({
            'id': new_lookup.id,
            'value': new_lookup.value,
            'display_name': new_lookup.display_name
        }), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500
