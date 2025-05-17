# api/contact_details.py
from flask import Blueprint, request, jsonify, session, current_app
import logging

# Import specific DAL functions for the new contacts collection
from db.contact_dal import get_contacts_by_company, replace_all_contacts

# Define the blueprint
contact_details_bp = Blueprint(
    'contact_details_bp',
    __name__,
    url_prefix='/api/contacts' # Keep the same prefix
)

# Configure basic logging
logging.basicConfig(level=logging.INFO)

# Helper function to get current user
def get_current_user():
    return session.get('username', 'System')

@contact_details_bp.route('', methods=['GET'])
def handle_get_contacts():
    """Handles GET requests to fetch the list of contacts for the company."""
    try:
        contacts = get_contacts_by_company()
        # Convert ObjectIds to strings for JSON
        for contact in contacts:
            contact['_id'] = str(contact['_id'])
            # Convert company_id as well if needed for frontend, though maybe not necessary
            if 'company_id' in contact:
                contact['company_id'] = str(contact['company_id'])
        return jsonify(contacts), 200
    except Exception as e:
        logging.error(f"Error in handle_get_contacts: {e}")
        return jsonify({"message": "Failed to fetch contact details"}), 500

@contact_details_bp.route('', methods=['PUT'])
def handle_update_contacts():
    """
    Handles PUT requests to replace the entire list of contacts for the company.
    Expects a JSON array in the request body.
    """
    contacts_data = request.get_json()
    if not isinstance(contacts_data, list):
        return jsonify({"message": "Invalid input: Expected a JSON array of contacts."}), 400

    try:
        current_user = get_current_user()
        # Call the DAL function to replace contacts
        success = replace_all_contacts(contacts_data, user=current_user)

        if success:
            # Fetch the updated list to return it
            updated_contacts = get_contacts_by_company()
            # Convert ObjectIds for response
            for contact in updated_contacts:
                 contact['_id'] = str(contact['_id'])
                 if 'company_id' in contact:
                    contact['company_id'] = str(contact['company_id'])
            return jsonify({"message": "Contacts updated successfully", "data": updated_contacts}), 200
        else:
             # DAL function handles logging the specific error
             return jsonify({"message": "Failed to update contacts. Check server logs."}), 500

    except Exception as e:
        # Catch any unexpected errors from the DAL or processing
        logging.error(f"Unexpected error in handle_update_contacts: {e}")
        return jsonify({"message": "An internal error occurred while updating contacts"}), 500

