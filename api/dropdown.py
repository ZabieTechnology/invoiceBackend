# api/dropdown.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from bson import ObjectId
import logging
from functools import wraps

# Import DAL functions for dropdowns
from db.dropdown_dal import (
    get_all_dropdowns,
    add_dropdown,
    update_dropdown,
    delete_dropdown,
    get_dropdown_by_id,
    is_dropdown_locked,
    get_dropdown_items_by_type # New DAL function
)
from db.database import get_db
from db.user_dal import get_user_by_id

dropdown_bp = Blueprint(
    'dropdown_bp',
    __name__,
    url_prefix='/api/global/dropdowns' # Changed to global endpoint
)

logging.basicConfig(level=logging.INFO)

# --- Admin Role-Based Access Control Decorator ---
def admin_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        claims = get_jwt()
        if claims.get("role") != "admin":
            return jsonify({"message": "Admins only! Access forbidden."}), 403
        return fn(*args, **kwargs)
    return wrapper

def get_requesting_user_name():
    user_id = get_jwt_identity()
    user = get_user_by_id(user_id)
    return user.get("username", "System") if user else "System"

@dropdown_bp.route("", methods=["GET"])
@jwt_required() # Accessible to all authenticated users
def handle_get_dropdowns():
    """ Fetches all global dropdown values for the management UI. """
    try:
        db = get_db()
        # Removed tenant_id from the call
        dropdown_list = get_all_dropdowns(db_conn=db)
        return jsonify(dropdown_list), 200
    except Exception as e:
        logging.error(f"Error in handle_get_dropdowns: {e}")
        return jsonify({"message": "Failed to fetch dropdown values"}), 500

@dropdown_bp.route("/<dropdown_type>", methods=['GET'])
@jwt_required() # Accessible to all authenticated users
def handle_get_dropdown_by_type(dropdown_type):
    """ Fetches all items for a specific dropdown type (e.g., 'gst_type'). """
    try:
        db = get_db()
        items = get_dropdown_items_by_type(db_conn=db, dropdown_type=dropdown_type)
        return jsonify(items), 200
    except Exception as e:
        logging.error(f"Error fetching dropdown type '{dropdown_type}': {e}")
        return jsonify({"message": "Failed to fetch dropdown items by type"}), 500

@dropdown_bp.route("", methods=["POST"])
@admin_required # Admins only
def handle_add_dropdown():
    data = request.get_json()
    if not data or not data.get("type") or not data.get("value") or not data.get("label"):
        return jsonify({"message": "Missing required fields: type, value, and label"}), 400
    try:
        db = get_db()
        current_user = get_requesting_user_name()
        # Removed tenant_id
        new_id = add_dropdown(db_conn=db, data=data, user=current_user)
        return jsonify({"message": "Dropdown value added successfully", "id": str(new_id)}), 201
    except Exception as e:
        logging.error(f"Error in handle_add_dropdown: {e}")
        return jsonify({"message": "Failed to add dropdown value"}), 500

@dropdown_bp.route("/<item_id>", methods=["PUT"])
@admin_required # Admins only
def handle_update_dropdown(item_id):
    data = request.get_json()
    try:
        db = get_db()
        if not data.get('is_locked') and is_dropdown_locked(db, item_id):
             return jsonify({"message": "Cannot update a locked item."}), 403

        current_user = get_requesting_user_name()
        # Removed tenant_id
        success = update_dropdown(db_conn=db, item_id=item_id, data=data, user=current_user)
        if success:
            return jsonify({"message": "Dropdown value updated successfully"}), 200
        return jsonify({"message": "Dropdown value not found or no changes made"}), 404
    except Exception as e:
        logging.error(f"Error in handle_update_dropdown for ID {item_id}: {e}")
        return jsonify({"message": "Failed to update dropdown value"}), 500

@dropdown_bp.route("/<item_id>", methods=["DELETE"])
@admin_required # Admins only
def handle_delete_dropdown(item_id):
    try:
        db = get_db()
        if is_dropdown_locked(db, item_id):
            return jsonify({"message": "Cannot delete a locked item."}), 403

        current_user = get_requesting_user_name()
        # Removed tenant_id
        success = delete_dropdown(db_conn=db, item_id=item_id, user=current_user)
        if success:
            return jsonify({"message": "Dropdown value deleted successfully"}), 200
        return jsonify({"message": "Dropdown value not found"}), 404
    except Exception as e:
        logging.error(f"Error in handle_delete_dropdown for ID {item_id}: {e}")
        return jsonify({"message": "Failed to delete dropdown value"}), 500
