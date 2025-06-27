# api/credit_note.py
from flask import Blueprint, request, jsonify, session
import logging
from bson import ObjectId
import traceback

from db.credit_note_dal import create_credit_note, get_credit_note_by_id, get_all_credit_notes
from db.database import get_db

credit_note_bp = Blueprint(
    'credit_note_bp',
    __name__,
    url_prefix='/api/credit-notes'
)

logging.basicConfig(level=logging.INFO)

def get_current_user():
    return session.get('username', 'System_User')

def get_current_tenant_id():
    return "default_tenant_placeholder"

@credit_note_bp.route('/', methods=['POST'], strict_slashes=False)
def handle_create_credit_note():
    """
    Handles POST requests to create a new credit note.
    """
    if not request.json:
        return jsonify({"message": "No JSON data provided"}), 400

    data = request.json
    tenant_id = get_current_tenant_id()
    user = get_current_user()

    try:
        db = get_db()
        note_id = create_credit_note(db, data, user, tenant_id)
        created_note = get_credit_note_by_id(db, str(note_id), tenant_id)
        return jsonify({"message": "Credit note created successfully", "data": created_note}), 201
    except Exception as e:
        logging.error(f"Error in handle_create_credit_note: {e}\n{traceback.format_exc()}")
        return jsonify({"message": "Failed to create credit note", "error": str(e)}), 500

@credit_note_bp.route('/', methods=['GET'], strict_slashes=False)
def handle_get_all_credit_notes():
    """
    Handles GET requests to fetch all credit notes for the tenant.
    """
    tenant_id = get_current_tenant_id()
    try:
        db = get_db()
        notes = get_all_credit_notes(db, tenant_id)
        return jsonify({"data": notes}), 200
    except Exception as e:
        logging.error(f"Error in handle_get_all_credit_notes: {e}\n{traceback.format_exc()}")
        return jsonify({"message": "Failed to fetch credit notes", "error": str(e)}), 500
