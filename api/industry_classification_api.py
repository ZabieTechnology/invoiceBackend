# src/api/industry_classification_api.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
import logging
from functools import wraps

# Import updated DAL functions for global data
from db.industry_classification_dal import (
    get_all_classifications,
    add_classification,
    update_classification,
    delete_classification
)
from db.user_dal import get_user_by_id
from db.database import get_db

industry_classification_bp = Blueprint(
    'industry_classification_bp',
    __name__,
    url_prefix='/api/industry-classifications'
)

logging.basicConfig(level=logging.INFO)

# --- Admin Role-Based Access Control Decorator ---
def admin_required(fn):
    """
    A decorator to protect routes so that only users with an 'admin' role can access them.
    """
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        claims = get_jwt()
        # Check for 'admin' role in the JWT claims
        if claims.get("role") != "admin":
            return jsonify({"message": "Admins only! Access forbidden."}), 403
        return fn(*args, **kwargs)
    return wrapper

def _get_request_user_details():
    """Helper function to get username from JWT identity."""
    user_id = get_jwt_identity()
    user = get_user_by_id(user_id)
    return user.get("username", "System") if user else "System"

@industry_classification_bp.route('', methods=['GET'])
@jwt_required()
def handle_get_classifications():
    """
    Fetches the global list of industry classifications.
    Accessible to all authenticated users.
    """
    try:
        db = get_db()
        # Fetches the single global document of classifications
        classifications = get_all_classifications(db)
        return jsonify(classifications), 200
    except Exception as e:
        logging.error(f"Error in handle_get_classifications: {e}")
        return jsonify({"message": "Failed to fetch classifications", "error": str(e)}), 500

@industry_classification_bp.route('', methods=['POST'])
@admin_required
def handle_add_classification():
    """
    Adds a new classification to the global list.
    Protected: Admins only.
    """
    data = request.get_json()
    if not data:
        return jsonify({"message": "Request body cannot be empty"}), 400
    try:
        user_name = _get_request_user_details()
        db = get_db()
        new_id = add_classification(db, data, user=user_name)
        if not new_id:
             return jsonify({"message": "Failed to add classification"}), 500
        return jsonify({"message": "Classification added successfully", "id": new_id}), 201
    except Exception as e:
        logging.error(f"Error in handle_add_classification: {e}")
        return jsonify({"message": "Failed to add classification", "error": str(e)}), 500

@industry_classification_bp.route('/<item_id>', methods=['PUT'])
@admin_required
def handle_update_classification(item_id):
    """
    Updates an existing classification in the global list.
    Protected: Admins only.
    """
    data = request.get_json()
    if not data:
        return jsonify({"message": "Request body cannot be empty"}), 400
    try:
        user_name = _get_request_user_details()
        db = get_db()
        success = update_classification(db, item_id, data, user=user_name)
        if not success:
            return jsonify({"message": "Classification not found or no changes made"}), 404
        return jsonify({"message": "Classification updated successfully"}), 200
    except Exception as e:
        logging.error(f"Error in handle_update_classification: {e}")
        return jsonify({"message": "Failed to update classification", "error": str(e)}), 500

@industry_classification_bp.route('/<item_id>', methods=['DELETE'])
@admin_required
def handle_delete_classification(item_id):
    """
    Deletes a classification from the global list.
    Protected: Admins only.
    """
    try:
        user_name = _get_request_user_details()
        db = get_db()
        success = delete_classification(db, item_id, user=user_name)
        if not success:
            return jsonify({"message": "Classification not found"}), 404
        return jsonify({"message": "Classification deleted successfully"}), 200
    except Exception as e:
        logging.error(f"Error in handle_delete_classification: {e}")
        return jsonify({"message": "Failed to delete classification", "error": str(e)}), 500
