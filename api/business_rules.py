from flask import Blueprint, request, jsonify, session
import logging

# Import DAL functions and db utility
from db.business_rules_dal import get_business_rules, save_business_rules, get_default_business_types
from db.database import get_db

# Create a new blueprint named 'business_rules_bp'
business_rules_bp = Blueprint(
    'business_rules_bp',
    __name__,
    url_prefix='/api/business-rules' # Updated URL prefix
)

logging.basicConfig(level=logging.INFO)

# --- Helper functions to get user/tenant from session ---
def get_current_user():
    return session.get('username', 'System_User_Placeholder')

def get_current_tenant_id():
    return session.get('tenant_id', 'default_tenant')


@business_rules_bp.route('', methods=['GET'])
def handle_get_business_rules():
    """
    Handles GET requests to fetch all business rules for the current tenant.
    """
    try:
        db = get_db()
        tenant_id = get_current_tenant_id()
        rules = get_business_rules(db, tenant_id=tenant_id)

        if rules is not None:
            return jsonify(rules), 200
        else:
            logging.info(f"No business rules found for tenant {tenant_id}. Returning default set.")
            default_rules = get_default_business_types()
            return jsonify(default_rules), 200
    except Exception as e:
        logging.error(f"Error in handle_get_business_rules: {e}")
        return jsonify({"message": "Failed to fetch business rules", "error": str(e)}), 500


@business_rules_bp.route('', methods=['POST'])
def handle_save_business_rules():
    """
    Handles POST requests to save all business rules for the current tenant.
    """
    data = request.json
    if not data or not isinstance(data, list):
        return jsonify({"message": "Invalid data format. Expected a list of rules."}), 400

    try:
        db = get_db()
        user = get_current_user()
        tenant_id = get_current_tenant_id()

        save_business_rules(db, rules_data=data, user=user, tenant_id=tenant_id)
        return jsonify({"message": "Business rules saved successfully"}), 200
    except Exception as e:
        logging.error(f"Error in handle_save_business_rules: {e}")
        return jsonify({"message": "Failed to save business rules", "error": str(e)}), 500
