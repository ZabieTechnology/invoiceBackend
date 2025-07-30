# src/api/regional_settings_api.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
import logging
from functools import wraps

# Import updated DAL functions for global data
from db.regional_settings_dal import (
    get_all_regional_settings,
    add_regional_setting,
    update_regional_setting,
    delete_regional_setting,
    update_states_for_region,
    bulk_add_regional_settings
)
from db.user_dal import get_user_by_id
from db.database import get_db

regional_settings_bp = Blueprint(
    'regional_settings_bp',
    __name__,
    url_prefix='/api/regional-settings'
)

logging.basicConfig(level=logging.INFO)

# --- Admin Role-Based Access Control Decorator ---
def admin_required(fn):
    """A decorator to protect routes so only users with an 'admin' role can access them."""
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        claims = get_jwt()
        if claims.get("role") != "admin":
            return jsonify({"message": "Admins only! Access forbidden."}), 403
        return fn(*args, **kwargs)
    return wrapper

def _get_request_user_details():
    """Helper function to get username from JWT identity."""
    user_id = get_jwt_identity()
    user = get_user_by_id(user_id)
    return user.get("username", "System") if user else "System"

@regional_settings_bp.route('', methods=['GET'])
@jwt_required()
def handle_get_settings():
    """Fetches all global regional settings. Accessible to all authenticated users."""
    try:
        db = get_db()
        settings = get_all_regional_settings(db)
        return jsonify(settings), 200
    except Exception as e:
        logging.error(f"Error in handle_get_settings: {e}")
        return jsonify({"message": "Failed to fetch regional settings", "error": str(e)}), 500

@regional_settings_bp.route('', methods=['POST'])
@admin_required
def handle_add_region():
    """Adds a new regional setting to the global list. Admins only."""
    data = request.get_json()
    if not data or not data.get('regionName'):
        return jsonify({"message": "Region name is required"}), 400
    try:
        db = get_db()
        user_name = _get_request_user_details()
        new_id = add_regional_setting(db, data, user=user_name)
        return jsonify({"message": "Regional setting added successfully", "id": new_id}), 201
    except ValueError as ve:
        logging.warning(f"Duplicate region warning in handle_add_region: {ve}")
        return jsonify({"message": str(ve)}), 409
    except Exception as e:
        logging.error(f"Error in handle_add_region: {e}")
        return jsonify({"message": "Failed to add regional setting", "error": str(e)}), 500

@regional_settings_bp.route('/bulk-import', methods=['POST'])
@admin_required
def handle_bulk_import():
    """Handles bulk import of global regional settings. Admins only."""
    data = request.get_json()
    if not data or 'regions' not in data or not isinstance(data['regions'], list):
        return jsonify({"message": "Request body must contain a 'regions' array."}), 400
    try:
        db = get_db()
        user_name = _get_request_user_details()
        result = bulk_add_regional_settings(db, data['regions'], user=user_name)
        return jsonify({
            "message": f"Bulk import completed. {result.get('inserted', 0)} new settings added, {result.get('skipped', 0)} duplicates skipped.",
            "insertedCount": result.get("inserted", 0),
            "skippedCount": result.get("skipped", 0)
        }), 201
    except Exception as e:
        logging.error(f"Error in handle_bulk_import: {e}")
        return jsonify({"message": "Failed to import regional settings", "error": str(e)}), 500

@regional_settings_bp.route('/<region_id>', methods=['PUT'])
@admin_required
def handle_update_region(region_id):
    """Updates an existing regional setting. Admins only."""
    data = request.get_json()
    if not data:
        return jsonify({"message": "Request body is required"}), 400
    try:
        db = get_db()
        user_name = _get_request_user_details()
        success = update_regional_setting(db, region_id, data, user=user_name)
        if not success:
            return jsonify({"message": "Setting not found or no changes made"}), 404
        return jsonify({"message": "Regional setting updated successfully"}), 200
    except ValueError as ve:
        logging.warning(f"Update failed due to duplicate name: {ve}")
        return jsonify({"message": str(ve)}), 409
    except Exception as e:
        logging.error(f"Error in handle_update_region: {e}")
        return jsonify({"message": "Failed to update regional setting", "error": str(e)}), 500

@regional_settings_bp.route('/<region_id>', methods=['DELETE'])
@admin_required
def handle_delete_region(region_id):
    """Deletes a regional setting. Admins only."""
    try:
        db = get_db()
        user_name = _get_request_user_details()
        success = delete_regional_setting(db, region_id, user=user_name)
        if not success:
            return jsonify({"message": "Setting not found"}), 404
        return jsonify({"message": "Regional setting deleted successfully"}), 200
    except Exception as e:
        logging.error(f"Error in handle_delete_region: {e}")
        return jsonify({"message": "Failed to delete regional setting", "error": str(e)}), 500

@regional_settings_bp.route('/states/<region_id>', methods=['PUT'])
@admin_required
def handle_update_states(region_id):
    """Updates the states for a specific region. Admins only."""
    data = request.get_json()
    if 'states' not in data or not isinstance(data['states'], list):
        return jsonify({"message": "A 'states' array is required"}), 400
    try:
        db = get_db()
        user_name = _get_request_user_details()
        updated_states = update_states_for_region(db, region_id, data['states'], user=user_name)
        if updated_states is None:
             return jsonify({"message": "Region not found or states unchanged"}), 404
        return jsonify({"message": "States updated successfully", "states": updated_states}), 200
    except Exception as e:
        logging.error(f"Error in handle_update_states: {e}")
        return jsonify({"message": "Failed to update states", "error": str(e)}), 500
