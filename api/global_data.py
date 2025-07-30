# api/global_data.py
from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
from functools import wraps
import logging

# Import the DAL functions for global data
from db.global_data_dal import (
    get_all_countries,
    add_country,
    update_country,
    delete_country,
    get_all_industries,
    add_industry,
    update_industry,
    delete_industry
)
# Import DAL functions for Document Rules
from db.document_rules_dal import get_or_create_rules, save_rules
from db.user_dal import get_user_by_id
from db.database import get_db

global_data_bp = Blueprint(
    'global_data_bp',
    __name__,
    url_prefix='/api/global'
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

def _get_request_user_details():
    """Helper function to get username from JWT identity."""
    user_id = get_jwt_identity()
    user = get_user_by_id(user_id)
    return user.get("username", "System") if user else "System"

# --- Country Routes ---

@global_data_bp.route('/countries', methods=['GET'])
@jwt_required()
def handle_get_countries():
    """Fetches the global list of countries for all authenticated users."""
    try:
        db = get_db()
        countries = get_all_countries(db)
        return jsonify(countries), 200
    except Exception as e:
        logging.error(f"Error fetching global countries: {e}")
        return jsonify({"message": "Failed to fetch countries", "error": str(e)}), 500

@global_data_bp.route('/countries', methods=['POST'])
@admin_required
def handle_add_country():
    """Adds a new country to the global list. Admins only."""
    data = request.get_json()
    if not data:
        return jsonify({"message": "Request body is required"}), 400
    try:
        db = get_db()
        new_id = add_country(db, data)
        return jsonify({"message": "Country added successfully", "id": new_id}), 201
    except Exception as e:
        logging.error(f"Error adding country: {e}")
        return jsonify({"message": "Failed to add country", "error": str(e)}), 500

@global_data_bp.route('/countries/<item_id>', methods=['PUT'])
@admin_required
def handle_update_country(item_id):
    """Updates a country in the global list. Admins only."""
    data = request.get_json()
    try:
        db = get_db()
        success = update_country(db, item_id, data)
        if not success:
            return jsonify({"message": "Country not found or no changes made"}), 404
        return jsonify({"message": "Country updated successfully"}), 200
    except Exception as e:
        logging.error(f"Error updating country {item_id}: {e}")
        return jsonify({"message": "Failed to update country", "error": str(e)}), 500

@global_data_bp.route('/countries/<item_id>', methods=['DELETE'])
@admin_required
def handle_delete_country(item_id):
    """Deletes a country from the global list. Admins only."""
    try:
        db = get_db()
        success = delete_country(db, item_id)
        if not success:
            return jsonify({"message": "Country not found"}), 404
        return jsonify({"message": "Country deleted successfully"}), 200
    except Exception as e:
        logging.error(f"Error deleting country {item_id}: {e}")
        return jsonify({"message": "Failed to delete country", "error": str(e)}), 500


# --- Industry Routes ---

@global_data_bp.route('/industries', methods=['GET'])
@jwt_required()
def handle_get_industries():
    """Fetches the global list of industries for all authenticated users."""
    try:
        db = get_db()
        industries = get_all_industries(db)
        return jsonify(industries), 200
    except Exception as e:
        logging.error(f"Error fetching global industries: {e}")
        return jsonify({"message": "Failed to fetch industries", "error": str(e)}), 500

@global_data_bp.route('/industries', methods=['POST'])
@admin_required
def handle_add_industry():
    """Adds a new industry. Admins only."""
    data = request.get_json()
    try:
        db = get_db()
        new_id = add_industry(db, data)
        return jsonify({"message": "Industry added successfully", "id": new_id}), 201
    except Exception as e:
        logging.error(f"Error adding industry: {e}")
        return jsonify({"message": "Failed to add industry", "error": str(e)}), 500

@global_data_bp.route('/industries/<item_id>', methods=['PUT'])
@admin_required
def handle_update_industry(item_id):
    """Updates an industry. Admins only."""
    data = request.get_json()
    try:
        db = get_db()
        success = update_industry(db, item_id, data)
        if not success:
            return jsonify({"message": "Industry not found or no changes made"}), 404
        return jsonify({"message": "Industry updated successfully"}), 200
    except Exception as e:
        logging.error(f"Error updating industry {item_id}: {e}")
        return jsonify({"message": "Failed to update industry", "error": str(e)}), 500

@global_data_bp.route('/industries/<item_id>', methods=['DELETE'])
@admin_required
def handle_delete_industry(item_id):
    """Deletes an industry. Admins only."""
    try:
        db = get_db()
        success = delete_industry(db, item_id)
        if not success:
            return jsonify({"message": "Industry not found"}), 404
        return jsonify({"message": "Industry deleted successfully"}), 200
    except Exception as e:
        logging.error(f"Error deleting industry {item_id}: {e}")
        return jsonify({"message": "Failed to delete industry", "error": str(e)}), 500

# --- Document Rules Routes ---

@global_data_bp.route('/docrules', methods=['GET'])
@jwt_required()
def handle_get_docrules():
    """
    Handles GET requests to fetch the entire global document of rules.
    Accessible to all authenticated users.
    """
    try:
        db = get_db()
        rules_document = get_or_create_rules(db)
        return jsonify(rules_document), 200
    except Exception as e:
        logging.error(f"Error in handle_get_docrules: {e}")
        return jsonify({"message": "Failed to fetch document rules", "error": str(e)}), 500

@global_data_bp.route('/docrules', methods=['POST'])
@admin_required
def handle_save_docrules():
    """
    Handles POST requests to save the entire global document of rules.
    Protected: Admins only.
    """
    data = request.json
    if not data or not isinstance(data, dict):
        return jsonify({"message": "Invalid data format. Expected a JSON object."}), 400

    try:
        db = get_db()
        user_name = _get_request_user_details()

        success = save_rules(db, data=data, user=user_name)
        if success:
            return jsonify({"message": "Document rules saved successfully"}), 200
        else:
            return jsonify({"message": "No changes were made to the document rules"}), 200
    except Exception as e:
        logging.error(f"Error in handle_save_docrules: {e}")
        return jsonify({"message": "Failed to save document rules", "error": str(e)}), 500
