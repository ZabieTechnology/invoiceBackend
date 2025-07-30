# src/api/document_rules_api.py
from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
import logging
from functools import wraps

# Import the updated DAL functions
from db.document_rules_dal import get_or_create_rules, save_rules
from db.user_dal import get_user_by_id
from db.database import get_db

document_rules_bp = Blueprint(
    'document_rules_bp',
    __name__,
    url_prefix='/api/document-rules'
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

@document_rules_bp.route('', methods=['GET'])
@jwt_required()
def handle_get_rules():
    """
    Handles GET requests to fetch the entire global document of rules.
    Accessible to all authenticated users.
    """
    try:
        db = get_db()
        rules_document = get_or_create_rules(db)
        return jsonify(rules_document), 200
    except Exception as e:
        logging.error(f"Error in handle_get_rules: {e}")
        return jsonify({"message": "Failed to fetch document rules", "error": str(e)}), 500

@document_rules_bp.route('', methods=['POST'])
@admin_required
def handle_save_rules():
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
            # This case might occur if the submitted data is identical to the stored data
            return jsonify({"message": "No changes were made to the document rules"}), 200
    except Exception as e:
        logging.error(f"Error in handle_save_rules: {e}")
        return jsonify({"message": "Failed to save document rules", "error": str(e)}), 500
