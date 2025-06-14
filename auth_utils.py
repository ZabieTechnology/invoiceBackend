# invoiceBackend/auth_utils.py
from functools import wraps
from flask import jsonify, g, session, current_app # Added current_app for debug check
from bson import ObjectId
import logging

# auth_logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # g.user_id and g.tenant_id should be populated by the @app.before_request middleware
        # The middleware is responsible for fetching from session and converting to ObjectId

        # Check if user_id exists and is an ObjectId instance on g
        if not hasattr(g, 'user_id') or not g.user_id or not isinstance(g.user_id, ObjectId):
            logging.warning(f"Authentication required: g.user_id is missing or not an ObjectId. Value: {getattr(g, 'user_id', 'Not Set')}, Type: {type(getattr(g, 'user_id', None))}")
            return jsonify({"message": "Authentication required (user context missing). Please log in."}), 401

        # Check if tenant_id exists and is an ObjectId instance on g
        # Note: app.py's middleware sets g.company_id from session['tenant_id'].
        # For consistency, auth_utils.py should check for g.company_id if app.py sets it,
        # or g.tenant_id if app.py sets g.tenant_id.
        # Based on previous logs, app.py sets g.company_id. Let's stick to that for now,
        # but be aware of the naming. If app.py is changed to set g.tenant_id, this should also change.

        # Assuming app.py's middleware populates `g.company_id` from `session['tenant_id']`
        # and ensures it's an ObjectId.
        # If you've changed app.py to set `g.tenant_id` instead of `g.company_id`, then this check should be:
        # if not hasattr(g, 'tenant_id') or not g.tenant_id or not isinstance(g.tenant_id, ObjectId):

        if not hasattr(g, 'company_id') or not g.company_id or not isinstance(g.company_id, ObjectId):
            logging.warning(f"Authentication required: g.company_id (from tenant_id) is missing or not an ObjectId. Value: {getattr(g, 'company_id', 'Not Set')}, Type: {type(getattr(g, 'company_id', None))}")
            return jsonify({"message": "Authentication required (tenant context missing). Please log in."}), 401

        # The explicit isinstance checks here are somewhat redundant if the @app.before_request
        # middleware in app.py already correctly converts them to ObjectId or sets them to None.
        # However, they provide an additional layer of safety.

        return f(*args, **kwargs)
    return decorated_function

# --- END OF auth_utils.py ---
