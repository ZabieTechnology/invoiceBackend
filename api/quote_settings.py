# api/quote_settings.py
from flask import Blueprint, request, jsonify, session
import logging
from datetime import datetime

# Import DAL function and db utility
from db.quote_settings_dal import get_quote_settings, save_quote_settings
from db.database import get_db

quote_settings_bp = Blueprint(
    'quote_settings_bp',
    __name__,
    url_prefix='/api/quote-settings'
)

logging.basicConfig(level=logging.INFO)

# Helper functions to get user and tenant from session
def get_current_user():
    # Continues to get the user from the session, or a default
    return session.get('username', 'System_User')

def get_current_tenant_id():
    """
    MODIFIED FOR DEBUGGING:
    This function now returns a static tenant_id.
    This allows testing the API without a valid user session.
    The original line is commented out below.
    """
    return "default_tenant_placeholder" # Static value for testing
    # return session.get('tenant_id', None) # Original line

@quote_settings_bp.route('/', methods=['GET'])
def handle_get_quote_settings():
    """
    API endpoint to fetch the current quotation settings for the tenant.
    """
    tenant_id = get_current_tenant_id()
    if not tenant_id:
        # This check is less likely to fail now but is good practice
        return jsonify({"message": "Unauthorized: No tenant ID found."}), 401

    try:
        db = get_db()
        settings = get_quote_settings(db, tenant_id)
        if settings:
            return jsonify(settings), 200
        else:
            return jsonify({"message": "Settings not found"}), 404
    except Exception as e:
        logging.error(f"Error in handle_get_quote_settings for tenant {tenant_id}: {e}")
        return jsonify({"message": "Failed to fetch settings", "error": str(e)}), 500

@quote_settings_bp.route('/', methods=['POST'])
def handle_save_quote_settings():
    """
    API endpoint to save or update quotation settings for the tenant.
    """
    tenant_id = get_current_tenant_id()
    if not tenant_id:
        return jsonify({"message": "Unauthorized: No tenant ID found."}), 401

    if not request.json:
        return jsonify({"message": "No JSON data provided"}), 400

    settings_data = request.json
    user = get_current_user()

    try:
        db = get_db()
        result = save_quote_settings(db, settings_data, user, tenant_id)

        if result and result.acknowledged:
            updated_settings = get_quote_settings(db, tenant_id)
            return jsonify({
                "message": "Settings saved successfully.",
                "data": updated_settings
            }), 200
        else:
            return jsonify({"message": "Failed to save settings."}), 500

    except Exception as e:
        logging.error(f"Error in handle_save_quote_settings for tenant {tenant_id}: {e}")
        return jsonify({"message": "Failed to save settings", "error": str(e)}), 500
