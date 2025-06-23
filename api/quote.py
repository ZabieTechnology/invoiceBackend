# api/quote.py
from flask import Blueprint, request, jsonify, session
import logging
from bson import ObjectId

# ** FIX **
# Changed the relative import 'from ..db...' to an absolute import 'from db...'
# This resolves the "attempted relative import beyond top-level package" error.
from db.quote_dal import create_quote, get_all_quotes, get_quote_by_id
from db.database import get_db

quote_bp = Blueprint(
    'quote_bp',
    __name__,
    url_prefix='/api/quotes'
)

logging.basicConfig(level=logging.INFO)

# Helper functions to get user and tenant from session
def get_current_user():
    return session.get('username', 'System_User')

def get_current_tenant_id():
    return "default_tenant_placeholder" # Static value for testing

@quote_bp.route('/', methods=['POST'], strict_slashes=False)
def handle_create_quote():
    """
    API endpoint to create a new quote.
    Added strict_slashes=False to handle requests with or without a trailing slash.
    """
    tenant_id = get_current_tenant_id()
    if not tenant_id:
        return jsonify({"message": "Unauthorized: No tenant ID found in session."}), 401

    if not request.json:
        return jsonify({"message": "No JSON data provided"}), 400

    quote_data = request.json
    user = get_current_user()

    try:
        db = get_db()
        inserted_id = create_quote(db, quote_data, user, tenant_id)
        created_quote = get_quote_by_id(db, str(inserted_id), tenant_id)

        return jsonify({
            "message": "Quote created successfully",
            "data": created_quote
        }), 201

    except Exception as e:
        logging.error(f"Error in handle_create_quote for tenant {tenant_id}: {e}")
        return jsonify({"message": "Failed to create quote", "error": str(e)}), 500


@quote_bp.route('/', methods=['GET'], strict_slashes=False)
def handle_get_all_quotes():
    """
    API endpoint to fetch all quotes for the tenant.
    Added strict_slashes=False to handle requests with or without a trailing slash.
    """
    tenant_id = get_current_tenant_id()
    if not tenant_id:
        return jsonify({"message": "Unauthorized: No tenant ID found in session."}), 401

    try:
        db = get_db()
        quotes = get_all_quotes(db, tenant_id)
        return jsonify({"data": quotes}), 200

    except Exception as e:
        logging.error(f"Error in handle_get_all_quotes for tenant {tenant_id}: {e}")
        return jsonify({"message": "Failed to fetch quotes", "error": str(e)}), 500


@quote_bp.route('/<quote_id>', methods=['GET'])
def handle_get_quote(quote_id):
    """
    API endpoint to fetch a single quote by its ID.
    """
    tenant_id = get_current_tenant_id()
    if not tenant_id:
        return jsonify({"message": "Unauthorized: No tenant ID found in session."}), 401

    if not ObjectId.is_valid(quote_id):
        return jsonify({"message": "Invalid quote ID format"}), 400

    try:
        db = get_db()
        quote = get_quote_by_id(db, quote_id, tenant_id)

        if quote:
            return jsonify(quote), 200
        else:
            return jsonify({"message": "Quote not found"}), 404

    except Exception as e:
        logging.error(f"Error in handle_get_quote for ID {quote_id}: {e}")
        return jsonify({"message": "Failed to fetch quote", "error": str(e)}), 500
